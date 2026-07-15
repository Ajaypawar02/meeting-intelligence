"""Segment & classify + structured extraction nodes."""

from __future__ import annotations

from typing import Any

from app.graph.state import MeetingGraphState
from app.llm.llm_provider import get_extractor
from app.schemas.meeting_record import (
    ActionItem,
    BlockerItem,
    DecisionItem,
    EscalationItem,
    FollowUpItem,
    ItemStatus,
    SegmentClass,
    SourceRef,
    TranscriptSegment,
)


def _line_dicts(state: MeetingGraphState) -> list[dict[str, Any]]:
    lines = state.get("filtered_transcript") or state.get("transcript") or []
    out = []
    for line in lines:
        out.append(
            {
                "line_id": line.line_id,
                "speaker": line.speaker,
                "timestamp": line.timestamp,
                "text": line.text,
                "sensitivity_tag": (
                    line.sensitivity_tag.value
                    if hasattr(line.sensitivity_tag, "value")
                    else line.sensitivity_tag
                ),
            }
        )
    return out


def segment_classify_node(state: MeetingGraphState) -> dict[str, Any]:
    extractor = get_extractor()
    result = extractor.classify_and_extract(_line_dicts(state))
    segments = []
    for s in result["segments"]:
        raw_cls = str(s.get("classification") or "discussion").lower()
        try:
            classification = SegmentClass(raw_cls)
        except ValueError:
            classification = SegmentClass.DISCUSSION
        segments.append(
            TranscriptSegment(
                segment_id=s["segment_id"],
                line_ids=s["line_ids"],
                text=s["text"],
                classification=classification,
                sensitivity_tags=s.get("sensitivity_tags") or [],
            )
        )
    return {
        "segments": segments,
        "node_trace": [
            {
                "node": "segment_classify",
                "backend": result.get("_extractor_backend", "unknown"),
                "segment_count": len(segments),
                "classes": {
                    c.value: sum(1 for s in segments if s.classification == c)
                    for c in SegmentClass
                    if any(s.classification == c for s in segments)
                },
            }
        ],
        "_extraction_cache": result,  # type: ignore[typeddict-item]
    }


def extract_structured_node(state: MeetingGraphState) -> dict[str, Any]:
    extractor = get_extractor()
    cache = state.get("_extraction_cache")  # type: ignore[attr-defined]
    result = cache if isinstance(cache, dict) else extractor.classify_and_extract(_line_dicts(state))

    def refs(raw_refs: list[dict]) -> list[SourceRef]:
        return [SourceRef.model_validate(r) for r in raw_refs]

    decisions = [
        DecisionItem(
            id=d["id"],
            description=d["description"],
            decided_by=d.get("decided_by"),
            source_refs=refs(d.get("source_refs", [])),
            confidence=d.get("confidence", 0.5),
            status=ItemStatus.NEEDS_REVIEW,
        )
        for d in result.get("decisions", [])
    ]
    actions = [
        ActionItem(
            id=a["id"],
            task=a["task"],
            owner=a.get("owner"),
            owner_inferred=a.get("owner_inferred", False),
            due_date=a.get("due_date"),
            due_date_inferred=a.get("due_date_inferred", False),
            source_refs=refs(a.get("source_refs", [])),
            confidence=a.get("confidence", 0.5),
            status=ItemStatus.NEEDS_REVIEW,
        )
        for a in result.get("action_items", [])
    ]
    blockers = [
        BlockerItem(
            id=b["id"],
            description=b["description"],
            blocking=b.get("blocking"),
            source_refs=refs(b.get("source_refs", [])),
            confidence=b.get("confidence", 0.5),
        )
        for b in result.get("blockers", [])
    ]
    follow_ups = [
        FollowUpItem(
            id=f["id"],
            topic=f["topic"],
            reason_open=f.get("reason_open", "Unresolved"),
            source_refs=refs(f.get("source_refs", [])),
        )
        for f in result.get("follow_ups", [])
    ]
    new_escalations = [
        EscalationItem.model_validate(e) for e in result.get("escalations", [])
    ]
    existing = list(state.get("escalations") or [])
    summary = result.get("summary", "")
    backend = result.get("_extractor_backend", "unknown")

    return {
        "decisions": decisions,
        "action_items": actions,
        "blockers": blockers,
        "follow_ups": follow_ups,
        "escalations": existing + new_escalations,
        "_draft_summary": summary,  # type: ignore[typeddict-item]
        "node_trace": [
            {
                "node": "extract_structured",
                "backend": backend,
                "decisions": len(decisions),
                "action_items": len(actions),
                "blockers": len(blockers),
                "follow_ups": len(follow_ups),
                "escalations_new": len(new_escalations),
            }
        ],
    }
