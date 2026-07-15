"""Self-critique / confidence scoring and review-queue routing."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.graph.state import MeetingGraphState
from app.schemas.meeting_record import (
    EscalationItem,
    ItemStatus,
    ReviewQueueItem,
)


def _score_item(confidence: float, source_refs: list, inferred_flags: list[bool]) -> float:
    score = confidence
    if not source_refs:
        score = min(score, 0.4)
    if any(inferred_flags):
        score = min(score, 0.6)
    return score


def critique_confidence_node(state: MeetingGraphState) -> dict[str, Any]:
    threshold = get_settings().confidence_threshold
    decisions = list(state.get("decisions") or [])
    actions = list(state.get("action_items") or [])
    blockers = list(state.get("blockers") or [])
    follow_ups = list(state.get("follow_ups") or [])
    escalations = list(state.get("escalations") or [])
    queue: list[ReviewQueueItem] = []

    for d in decisions:
        d.confidence = _score_item(d.confidence, d.source_refs, [])
        if d.confidence >= threshold and d.source_refs:
            d.status = ItemStatus.AUTO_APPROVED
        else:
            d.status = ItemStatus.NEEDS_REVIEW
            queue.append(
                ReviewQueueItem(
                    id=d.id,
                    item_type="decision",
                    payload=d.model_dump(),
                    reason="low_confidence" if d.confidence < threshold else "missing_sources",
                )
            )

    for a in actions:
        a.confidence = _score_item(
            a.confidence,
            a.source_refs,
            [a.owner_inferred, a.due_date_inferred, a.owner is None, a.due_date is None],
        )
        if a.is_proposal or a.confidence < threshold or not a.owner or not a.due_date:
            a.status = ItemStatus.NEEDS_REVIEW
            reason = "proposal" if a.is_proposal else "inferred_or_missing_owner_or_date"
            if a.confidence < threshold:
                reason = "low_confidence"
            queue.append(
                ReviewQueueItem(
                    id=a.id,
                    item_type="action_item",
                    payload=a.model_dump(),
                    reason=reason,
                )
            )
        else:
            a.status = ItemStatus.AUTO_APPROVED

    for b in blockers:
        b.confidence = _score_item(b.confidence, b.source_refs, [])
        if b.confidence < threshold or not b.source_refs:
            b.status = ItemStatus.NEEDS_REVIEW
            queue.append(
                ReviewQueueItem(
                    id=b.id,
                    item_type="blocker",
                    payload=b.model_dump(),
                    reason="low_confidence",
                )
            )
        else:
            b.status = ItemStatus.AUTO_APPROVED

    for f in follow_ups:
        f.status = ItemStatus.NEEDS_REVIEW
        queue.append(
            ReviewQueueItem(
                id=f.id,
                item_type="follow_up",
                payload=f.model_dump(),
                reason="open_thread",
            )
        )

    for e in escalations:
        e_status_item = ReviewQueueItem(
            id=e.id,
            item_type="escalation",
            payload=e.model_dump(),
            reason=e.reason,
        )
        # Restricted content escalations stay visible but aren't "auto decisions"
        queue.append(e_status_item)

    # Promote low-confidence actions to explicit escalations if zero sources
    for a in actions:
        if not a.source_refs:
            escalations.append(
                EscalationItem(
                    id=f"LC-{a.id}",
                    description=a.task,
                    reason="low_confidence",
                    source_refs=[],
                )
            )

    paused = len(queue) > 0
    return {
        "decisions": decisions,
        "action_items": actions,
        "blockers": blockers,
        "follow_ups": follow_ups,
        "escalations": escalations,
        "review_queue": queue,
        "paused_for_review": paused,
        "node_trace": [
            {
                "node": "critique_confidence",
                "threshold": threshold,
                "auto_approved": sum(
                    1
                    for x in decisions + actions + blockers
                    if x.status == ItemStatus.AUTO_APPROVED
                ),
                "review_queue_size": len(queue),
                "paused_for_review": paused,
            }
        ],
    }
