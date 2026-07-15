"""LLM-backed extractor with automatic fallback to deterministic MockLLM."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.llm.mock_llm import MockLLM


class ChatModel(Protocol):
    def invoke(self, prompt: str | list | dict, **kwargs: Any) -> Any: ...


_EXTRACTION_PROMPT = """You extract a structured meeting record from a transcript.
Return ONLY valid JSON (no markdown fences) with this exact shape:
{{
  "summary": "3-5 sentence recap",
  "segments": [
    {{
      "segment_id": "S001",
      "line_ids": ["L001"],
      "text": "Speaker: utterance",
      "classification": "discussion|decision|action_item|blocker|open_question|off_topic|escalation",
      "sensitivity_tags": ["general"]
    }}
  ],
  "decisions": [
    {{
      "id": "D001",
      "description": "...",
      "decided_by": "Name or null",
      "source_refs": [{{"line_id":"L004","timestamp":"10:05","speaker":"Priya","excerpt":"..."}}],
      "confidence": 0.0
    }}
  ],
  "action_items": [
    {{
      "id": "A001",
      "task": "...",
      "owner": "Name or null",
      "owner_inferred": false,
      "due_date": "string or null",
      "due_date_inferred": false,
      "source_refs": [{{"line_id":"L005","timestamp":"10:06","speaker":"Ava","excerpt":"..."}}],
      "confidence": 0.0
    }}
  ],
  "blockers": [
    {{
      "id": "B001",
      "description": "...",
      "blocking": "...",
      "source_refs": [],
      "confidence": 0.0
    }}
  ],
  "follow_ups": [
    {{
      "id": "F001",
      "topic": "...",
      "reason_open": "...",
      "source_refs": []
    }}
  ],
  "escalations": [
    {{
      "id": "E001",
      "description": "...",
      "reason": "out_of_authority|low_confidence|restricted_content",
      "source_refs": [],
      "proposed_by_agent": null
    }}
  ]
}}

Rules:
- Every decision/action/blocker/escalation MUST cite real line_id values from the transcript.
- If owner or due date is guessed (not explicit), set the *_inferred flag true and lower confidence (<0.7).
- Escalate (do not decide): budget/headcount commitments, slipping dates that affect other teams.
- Prefer explicit evidence; do not invent speakers or dates.

Transcript JSON:
{transcript_json}
"""


def _message_text(resp: Any) -> str:
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            else:
                parts.append(str(getattr(block, "text", block)))
        return "".join(parts)
    return str(resp)


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No JSON object in model response")
    return json.loads(text[start : end + 1])


def _valid_line_ids(lines: list[dict[str, Any]]) -> set[str]:
    return {str(line.get("line_id") or f"L{i+1:03d}") for i, line in enumerate(lines)}


def _normalize_extraction(raw: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Ensure required keys exist and drop source refs to unknown line ids."""
    allowed = _valid_line_ids(lines)
    line_by_id = {
        str(line.get("line_id") or f"L{i+1:03d}"): line for i, line in enumerate(lines)
    }

    def clean_refs(refs: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(refs, list):
            return out
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            lid = str(ref.get("line_id") or "")
            if lid not in allowed:
                continue
            src = line_by_id[lid]
            out.append(
                {
                    "line_id": lid,
                    "timestamp": ref.get("timestamp") or src.get("timestamp") or "",
                    "speaker": ref.get("speaker") or src.get("speaker") or "",
                    "excerpt": (ref.get("excerpt") or src.get("text") or "")[:160],
                }
            )
        return out

    segments = raw.get("segments") or []
    if not segments:
        # Build minimal segments so downstream classification counts still work.
        segments = []
        for i, line in enumerate(lines):
            lid = str(line.get("line_id") or f"L{i+1:03d}")
            segments.append(
                {
                    "segment_id": f"S{i+1:03d}",
                    "line_ids": [lid],
                    "text": f"{line.get('speaker')}: {line.get('text')}",
                    "classification": "discussion",
                    "sensitivity_tags": [line.get("sensitivity_tag", "general")],
                }
            )

    def scrub_items(items: Any, ref_key: str = "source_refs") -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        cleaned: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row[ref_key] = clean_refs(row.get(ref_key))
            cleaned.append(row)
        return cleaned

    return {
        "summary": raw.get("summary")
        or "Meeting record extracted by LLM; review flagged items before publishing.",
        "segments": segments if isinstance(segments, list) else [],
        "decisions": scrub_items(raw.get("decisions")),
        "action_items": scrub_items(raw.get("action_items")),
        "blockers": scrub_items(raw.get("blockers")),
        "follow_ups": scrub_items(raw.get("follow_ups")),
        "escalations": scrub_items(raw.get("escalations")),
    }


class HybridExtractor:
    """Prefer chat-model JSON extraction; fall back to MockLLM on any failure."""

    def __init__(self, chat_model: ChatModel | None = None, *, backend_name: str = "mock"):
        self.chat_model = chat_model
        self.backend_name = backend_name
        self._mock = MockLLM()

    def invoke(self, prompt: str | list | dict, **kwargs: Any) -> Any:
        if self.chat_model is None:
            return self._mock.invoke(prompt, **kwargs)
        return self.chat_model.invoke(prompt, **kwargs)

    def classify_and_extract(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        if self.chat_model is None:
            return self._mock.classify_and_extract(lines)

        prompt = _EXTRACTION_PROMPT.format(transcript_json=json.dumps(lines, indent=2))
        try:
            resp = self.chat_model.invoke(prompt)
            raw = _parse_json_object(_message_text(resp))
            result = _normalize_extraction(raw, lines)
            result["_extractor_backend"] = self.backend_name
            return result
        except Exception:
            fallback = self._mock.classify_and_extract(lines)
            fallback["_extractor_backend"] = f"{self.backend_name}->mock_fallback"
            return fallback
