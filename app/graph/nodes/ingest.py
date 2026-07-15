"""Graph node: ingest transcript + metadata from path or in-memory payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.graph.state import MeetingGraphState
from app.schemas.meeting_record import MeetingMetadata, SensitivityTag, TranscriptLine


def _load_payload(raw: dict[str, Any]) -> tuple[MeetingMetadata, list[TranscriptLine]]:
    meta = MeetingMetadata(
        meeting_id=raw["meeting_id"],
        title=raw["title"],
        date=raw["date"],
        attendees=raw.get("attendees", []),
        project=raw.get("project"),
        team=raw.get("team"),
    )
    lines: list[TranscriptLine] = []
    for i, row in enumerate(raw.get("transcript", [])):
        lid = row.get("line_id") or f"L{i+1:03d}"
        tag = row.get("sensitivity_tag", "general")
        lines.append(
            TranscriptLine(
                line_id=lid,
                speaker=row["speaker"],
                timestamp=row["timestamp"],
                text=row["text"],
                sensitivity_tag=SensitivityTag(tag),
            )
        )
    return meta, lines


def ingest_node(state: MeetingGraphState) -> dict[str, Any]:
    """Expect either metadata+transcript already in state, or a path in node_trace seed."""
    if state.get("metadata") and state.get("transcript"):
        meta = state["metadata"]
        lines = state["transcript"]
        if isinstance(meta, dict):
            meta = MeetingMetadata.model_validate(meta)
        if lines and isinstance(lines[0], dict):
            lines = [TranscriptLine.model_validate(x) for x in lines]
        return {
            "metadata": meta,
            "transcript": lines,
            "node_trace": [
                {
                    "node": "ingest",
                    "lines": len(lines),
                    "meeting_id": meta.meeting_id,
                }
            ],
        }

    # Path-based load: look for ingest_path in human_resolutions or error clearly.
    path_str = (state.get("human_resolutions") or {}).get("transcript_path")
    if not path_str:
        return {
            "error": "ingest: no transcript provided",
            "node_trace": [{"node": "ingest", "error": "missing transcript"}],
        }
    raw = json.loads(Path(path_str).read_text(encoding="utf-8"))
    meta, lines = _load_payload(raw)
    return {
        "metadata": meta,
        "transcript": lines,
        "node_trace": [
            {
                "node": "ingest",
                "lines": len(lines),
                "meeting_id": meta.meeting_id,
                "source": path_str,
            }
        ],
    }


def load_transcript_file(path: Path | str) -> tuple[MeetingMetadata, list[TranscriptLine]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return _load_payload(raw)
