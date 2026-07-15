"""Human-in-the-loop gate: apply resolutions or pause for review."""

from __future__ import annotations

from typing import Any

from app.graph.state import MeetingGraphState
from app.schemas.meeting_record import ItemStatus


def human_review_gate_node(state: MeetingGraphState) -> dict[str, Any]:
    """Apply any human_resolutions already present; otherwise leave queue intact.

    LangGraph interrupt is wired in build_graph for interactive resume. In CLI/API
    batch mode, callers POST approvals into human_resolutions and re-invoke.
    """
    resolutions: dict[str, Any] = dict(state.get("human_resolutions") or {})
    # ingest / control keys — ignore for per-item application
    resolutions.pop("transcript_path", None)
    force_continue = bool(resolutions.pop("_force_continue", False))

    queue = list(state.get("review_queue") or [])
    decisions = list(state.get("decisions") or [])
    actions = list(state.get("action_items") or [])
    follow_ups = list(state.get("follow_ups") or [])
    blockers = list(state.get("blockers") or [])

    applied = 0
    remaining = []

    def _apply(items: list, item_id: str, action: str, edited: dict | None) -> bool:
        for item in items:
            if getattr(item, "id", None) != item_id:
                continue
            if action == "approve":
                item.status = ItemStatus.APPROVED
                if edited:
                    for k, v in edited.items():
                        if hasattr(item, k) and k not in ("id", "source_refs"):
                            setattr(item, k, v)
            elif action == "reject":
                item.status = ItemStatus.REJECTED
            elif action == "edit":
                item.status = ItemStatus.APPROVED
                if edited:
                    for k, v in edited.items():
                        if hasattr(item, k) and k != "id":
                            setattr(item, k, v)
                    # Explicit owner/date from a human edit are no longer inferences
                    if "owner" in edited and edited.get("owner"):
                        if hasattr(item, "owner_inferred"):
                            item.owner_inferred = False
                    if "due_date" in edited and edited.get("due_date"):
                        if hasattr(item, "due_date_inferred"):
                            item.due_date_inferred = False
            elif action == "reassign":
                item.status = ItemStatus.APPROVED
                if edited and "owner" in edited:
                    item.owner = edited["owner"]  # type: ignore[attr-defined]
                    item.owner_inferred = False  # type: ignore[attr-defined]
            return True
        return False

    for q in queue:
        res = resolutions.get(q.id)
        if not res or not isinstance(res, dict):
            remaining.append(q)
            continue
        action = res.get("action", "approve")
        edited = res.get("edited_payload") or None
        if edited == {}:
            edited = None
        q.human_action = action
        q.edited_payload = edited
        found = (
            _apply(decisions, q.id, action, edited)
            or _apply(actions, q.id, action, edited)
            or _apply(follow_ups, q.id, action, edited)
            or _apply(blockers, q.id, action, edited)
        )
        if found or q.item_type == "escalation":
            applied += 1
            # acknowledged escalations leave the active review queue
        else:
            remaining.append(q)

    still_paused = len(remaining) > 0 and not force_continue
    return {
        "decisions": decisions,
        "action_items": actions,
        "follow_ups": follow_ups,
        "blockers": blockers,
        "review_queue": remaining,
        "paused_for_review": still_paused,
        "human_resolutions": {
            **{k: v for k, v in (state.get("human_resolutions") or {}).items()},
            **({"_force_continue": True} if force_continue else {}),
        },
        "node_trace": [
            {
                "node": "human_review_gate",
                "applied": applied,
                "remaining": len(remaining),
                "paused_for_review": still_paused,
                "applied_ids": [
                    q.id for q in queue if q.id not in {r.id for r in remaining}
                ],
            }
        ],
    }


def route_after_review(state: MeetingGraphState) -> str:
    if state.get("paused_for_review") and not (state.get("human_resolutions") or {}).get(
        "_force_continue"
    ):
        return "await_human"
    return "aggregate"
