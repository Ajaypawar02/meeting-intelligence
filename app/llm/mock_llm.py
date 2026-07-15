"""Deterministic rule-based LLM fallback — no API key required."""

from __future__ import annotations

import json
import re
from typing import Any


# Patterns the mock extractor looks for in transcript text.
DECISION_PATTERNS = [
    re.compile(r"\b(?:we(?:'ve| have)? decided|decision is|going with|we'll go with|agreed (?:to|on))\b", re.I),
    re.compile(r"\blet'?s (?:ship|freeze|lock|adopt)\b", re.I),
]
ACTION_PATTERNS = [
    re.compile(r"\b(?:I(?:'| wi)?ll|you(?:'| wi)?ll|(?:can|will) you|please)\b.+\b(?:by|before|due)\b", re.I),
    re.compile(r"\b(?:action item|take point|own(?:s|ing)?|assigned to)\b", re.I),
    re.compile(r"\bI(?:'| wi)?ll\b.+\b(?:tomorrow|friday|monday|next week|by end of)\b", re.I),
]
BLOCKER_PATTERNS = [
    re.compile(r"\b(?:blocked|blocker|waiting on|stuck on|can'?t proceed)\b", re.I),
]
OPEN_Q_PATTERNS = [
    re.compile(r"\?(?:\s|$)"),
    re.compile(r"\b(?:open question|still unclear|need to decide|what(?:'s| is) (?:our|the))\b", re.I),
]
ESCALATION_PATTERNS = [
    re.compile(r"\b(?:budget|headcount|hire|fire|salary|compensation|layoff)\b", re.I),
    re.compile(r"\b(?:slip(?:ping)? (?:the )?deadline|move the date|push the release)\b", re.I),
    re.compile(r"\b(?:commit(?:ting)? \$|allocate .+ funds)\b", re.I),
]
OWNER_RE = re.compile(
    r"\b(?:assigned to|owner(?: is)?|(@)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)?))\b|"
    r"\b([A-Z][a-z]+) (?:will|owns|is owning)\b|"
    r"\bI(?:'| wi)?ll\b",
    re.I,
)
DATE_RE = re.compile(
    r"\b(?:by (?:end of )?(?:day|week|friday|monday|tuesday|wednesday|thursday|saturday|sunday)|"
    r"due (?:on |by )?[\w\s/-]+|"
    r"(?:tomorrow|next (?:week|monday|friday)|EOD|EOW))\b",
    re.I,
)


def _classify_line(text: str) -> str:
    if any(p.search(text) for p in ESCALATION_PATTERNS):
        return "escalation"
    if any(p.search(text) for p in BLOCKER_PATTERNS):
        return "blocker"
    if any(p.search(text) for p in DECISION_PATTERNS):
        return "decision"
    if any(p.search(text) for p in ACTION_PATTERNS):
        return "action_item"
    if any(p.search(text) for p in OPEN_Q_PATTERNS):
        return "open_question"
    return "discussion"


def _extract_owner(text: str, speaker: str) -> tuple[str | None, bool]:
    if re.search(r"\bI(?:'| wi)?ll\b", text, re.I):
        return speaker, False
    m = re.search(
        r"\b([A-Z][a-z]+) (?:will|owns|is owning|can you|please)\b",
        text,
    )
    if m:
        return m.group(1), False
    m = re.search(r"\b(?:assigned to|owner(?: is)?)\s+([A-Z][a-z]+)\b", text, re.I)
    if m:
        return m.group(1).title() if m.group(1).islower() else m.group(1), False
    # Weak inference from "someone from platform"
    if re.search(r"\bsomeone (?:from|on)\b", text, re.I):
        return None, True
    return None, False


def _extract_due(text: str) -> tuple[str | None, bool]:
    m = DATE_RE.search(text)
    if m:
        return m.group(0), False
    return None, True


class MockLLM:
    """Rule-based stand-in that produces structured extraction-like results."""

    def invoke(self, prompt: str | list | dict, **_: Any) -> str:
        text = prompt if isinstance(prompt, str) else json.dumps(prompt)
        if "summarize" in text.lower() or "summary" in text.lower():
            return self._summary_from_prompt(text)
        if "critique" in text.lower() or "confidence" in text.lower():
            return json.dumps({"ok": True, "note": "mock critique pass"})
        return text

    def _summary_from_prompt(self, text: str) -> str:
        # Pull a few speaker lines if present in the prompt for a short recap.
        lines = re.findall(r"\[(\d{2}:\d{2})\]\s+(\w+):\s+(.+)", text)
        if not lines:
            return (
                "The team reviewed sprint progress, recorded decisions and action items, "
                "flagged blockers, and left open questions for human follow-up."
            )
        speakers = sorted({s for _, s, _ in lines})
        return (
            f"Sprint sync covered delivery status among {', '.join(speakers)}. "
            "The team locked at least one delivery decision, assigned follow-up work, "
            "noted a blocker, and escalated out-of-authority topics for human review."
        )

    def classify_and_extract(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        decisions: list[dict] = []
        actions: list[dict] = []
        blockers: list[dict] = []
        follow_ups: list[dict] = []
        escalations: list[dict] = []
        segments: list[dict] = []

        for i, line in enumerate(lines):
            text = line["text"]
            speaker = line["speaker"]
            lid = line.get("line_id") or f"L{i+1:03d}"
            classification = _classify_line(text)
            segments.append(
                {
                    "segment_id": f"S{i+1:03d}",
                    "line_ids": [lid],
                    "text": f"{speaker}: {text}",
                    "classification": classification,
                    "sensitivity_tags": [line.get("sensitivity_tag", "general")],
                }
            )
            source = {
                "line_id": lid,
                "timestamp": line["timestamp"],
                "speaker": speaker,
                "excerpt": text[:160],
            }
            if classification == "decision":
                decisions.append(
                    {
                        "id": f"D{len(decisions)+1:03d}",
                        "description": text,
                        "decided_by": speaker,
                        "source_refs": [source],
                        "confidence": 0.9,
                    }
                )
            elif classification == "action_item":
                owner, owner_inf = _extract_owner(text, speaker)
                due, due_inf = _extract_due(text)
                conf = 0.88
                if owner is None or due is None:
                    conf = 0.55
                if owner_inf or due_inf:
                    conf = min(conf, 0.6)
                actions.append(
                    {
                        "id": f"A{len(actions)+1:03d}",
                        "task": text,
                        "owner": owner,
                        "owner_inferred": owner is None or owner_inf,
                        "due_date": due,
                        "due_date_inferred": due is None or due_inf,
                        "source_refs": [source],
                        "confidence": conf,
                    }
                )
            elif classification == "blocker":
                blockers.append(
                    {
                        "id": f"B{len(blockers)+1:03d}",
                        "description": text,
                        "blocking": "delivery progress",
                        "source_refs": [source],
                        "confidence": 0.85,
                    }
                )
            elif classification == "open_question":
                follow_ups.append(
                    {
                        "id": f"F{len(follow_ups)+1:03d}",
                        "topic": text,
                        "reason_open": "Unresolved question in discussion",
                        "source_refs": [source],
                    }
                )
            elif classification == "escalation":
                reason = "out_of_authority"
                if re.search(r"budget|funds|hire|salary|compensation", text, re.I):
                    reason = "out_of_authority"
                escalations.append(
                    {
                        "id": f"E{len(escalations)+1:03d}",
                        "description": text,
                        "reason": reason,
                        "source_refs": [source],
                        "proposed_by_agent": None,
                    }
                )

        summary_bits = []
        if decisions:
            summary_bits.append(f"{len(decisions)} decision(s)")
        if actions:
            summary_bits.append(f"{len(actions)} action item(s)")
        if blockers:
            summary_bits.append(f"{len(blockers)} blocker(s)")
        if escalations:
            summary_bits.append(f"{len(escalations)} escalation(s)")
        summary = (
            "Meeting captured "
            + (", ".join(summary_bits) if summary_bits else "discussion notes")
            + ". Items with weak evidence are flagged for human review; "
            "out-of-authority topics were escalated rather than auto-decided."
        )
        return {
            "summary": summary,
            "segments": segments,
            "decisions": decisions,
            "action_items": actions,
            "blockers": blockers,
            "follow_ups": follow_ups,
            "escalations": escalations,
        }


# Explicit agent authority (what mock/real path may answer vs escalate).
AGENT_AUTHORITY = [
    "factual lookups from retrieved prior notes/docs",
    "summarizing prior decisions",
    "suggesting an owner based on past ownership patterns (as a proposal)",
    "drafting a clarifying follow-up question",
]

MUST_ESCALATE = [
    "committing budget or headcount",
    "changing dates that affect other teams",
    "anything touching restricted-tag content for the audience",
    "any extraction below the confidence threshold",
]
