"""Graph node: permission filter — redact before any generation prompt."""

from __future__ import annotations

from typing import Any

from app.graph.state import MeetingGraphState
from app.permissions.access_map import is_allowed
from app.schemas.meeting_record import EscalationItem, SourceRef


def permission_filter_node(state: MeetingGraphState) -> dict[str, Any]:
    role = state.get("audience_role") or "general"
    lines = state.get("transcript") or []
    kept = []
    redacted = 0
    restricted_escalations: list[EscalationItem] = []

    for line in lines:
        tag = line.sensitivity_tag
        if is_allowed(role, tag):
            kept.append(line)
        else:
            redacted += 1
            restricted_escalations.append(
                EscalationItem(
                    id=f"R{redacted:03d}",
                    description=(
                        f"Restricted item ({tag.value}) — contact owner; "
                        "content withheld from this audience."
                    ),
                    reason="restricted_content",
                    source_refs=[
                        SourceRef(
                            line_id=line.line_id or "unknown",
                            timestamp=line.timestamp,
                            speaker=line.speaker,
                            excerpt="[REDACTED]",
                        )
                    ],
                )
            )

    existing = list(state.get("escalations") or [])
    return {
        "filtered_transcript": kept,
        "redacted_count": redacted,
        "escalations": existing + restricted_escalations,
        "node_trace": [
            {
                "node": "permission_filter",
                "audience_role": role,
                "input_lines": len(lines),
                "kept": len(kept),
                "redacted": redacted,
            }
        ],
    }
