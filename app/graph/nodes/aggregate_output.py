"""Aggregate final meeting record and mock handback distribution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.graph.state import MeetingGraphState
from app.schemas.meeting_record import ItemStatus, MeetingRecord
from app.tools.notify_tool_mock import notify_owner_mock
from app.tools.ticket_tool_mock import create_ticket_mock


def aggregate_output_node(state: MeetingGraphState) -> dict[str, Any]:
    meta = state["metadata"]
    decisions = list(state.get("decisions") or [])
    actions = list(state.get("action_items") or [])
    blockers = list(state.get("blockers") or [])
    follow_ups = list(state.get("follow_ups") or [])
    escalations = list(state.get("escalations") or [])
    queue = list(state.get("review_queue") or [])
    context = list(state.get("context_snippets") or [])
    summary = state.get("_draft_summary") or (  # type: ignore[attr-defined]
        "Structured meeting record generated. See decisions and action items below."
    )

    # Fold bounded answers into summary briefly
    answers = state.get("bounded_answers") or []
    answered = [a for a in answers if a.within_authority and a.answer]
    if answered:
        summary += " Agent answered in-authority questions using retrieved context."

    finalized_statuses = {ItemStatus.AUTO_APPROVED, ItemStatus.APPROVED}
    auto_pub = sum(
        1
        for x in decisions + actions + blockers
        if x.status in finalized_statuses
    )
    pending = len(queue) + sum(
        1
        for x in decisions + actions + follow_ups
        if x.status == ItemStatus.NEEDS_REVIEW
    )

    record = MeetingRecord(
        meeting_id=meta.meeting_id,
        title=meta.title,
        date=meta.date,
        summary=summary,
        decisions=decisions,
        action_items=actions,
        blockers=blockers,
        follow_ups=follow_ups,
        escalations=escalations,
        review_queue=queue,
        context_used=context,
        redacted_segments_count=state.get("redacted_count") or 0,
        audience_role=state.get("audience_role") or "general",
        auto_published_count=auto_pub,
        pending_review_count=pending,
    )

    settings = get_settings()
    run_id = state.get("run_id") or meta.meeting_id
    out_dir = settings.output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "meeting_record.json"
    md_path = out_dir / "meeting_recap.md"
    json_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(record), encoding="utf-8")

    handback = [str(json_path), str(md_path)]

    # Mock distribution for finalized action items only
    for a in actions:
        if a.status in finalized_statuses and a.owner:
            ticket = create_ticket_mock(a.model_dump(), run_id)
            handback.append(ticket["path"])
            note = notify_owner_mock(
                a.owner,
                f"Action item {a.id}: {a.task[:120]}",
                run_id,
            )
            handback.append(note["path"])

    return {
        "meeting_record": record,
        "handback_paths": handback,
        "paused_for_review": False,
        "node_trace": [
            {
                "node": "aggregate_output",
                "handback": handback,
                "auto_published": auto_pub,
                "pending_review": pending,
            }
        ],
    }


def _to_markdown(record: MeetingRecord) -> str:
    lines = [
        f"# {record.title}",
        f"Date: {record.date} | Meeting ID: {record.meeting_id}",
        f"Audience role: {record.audience_role}",
        "",
        "## Summary",
        record.summary,
        "",
        f"_Redacted segments (pre-LLM): {record.redacted_segments_count}_",
        "",
        "## Decisions (finalized / auto-approved)",
    ]
    finalized = {ItemStatus.AUTO_APPROVED, ItemStatus.APPROVED}
    for d in record.decisions:
        if d.status in finalized:
            refs = ", ".join(r.line_id for r in d.source_refs)
            lines.append(
                f"- **{d.id}** ({d.status.value}, conf={d.confidence:.2f}): "
                f"{d.description} _(sources: {refs})_"
            )
    lines.append("")
    lines.append("## Action items — auto-published")
    for a in record.action_items:
        if a.status in finalized:
            lines.append(
                f"- **{a.id}** owner={a.owner} due={a.due_date}: {a.task}"
            )
    lines.append("")
    lines.append("## Pending human review")
    for q in record.review_queue:
        lines.append(f"- **{q.id}** [{q.item_type}] reason={q.reason}")
    if not record.review_queue:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Blockers")
    for b in record.blockers:
        lines.append(f"- **{b.id}**: {b.description} (blocking: {b.blocking})")
    lines.append("")
    lines.append("## Escalations")
    for e in record.escalations:
        lines.append(f"- **{e.id}** [{e.reason}]: {e.description}")
    lines.append("")
    lines.append("## Follow-ups")
    for f in record.follow_ups:
        lines.append(f"- **{f.id}**: {f.topic} — {f.reason_open}")
    lines.append("")
    lines.append("## Context used")
    for c in record.context_used:
        lines.append(f"- {c.doc_id} (score={c.score}): {c.text[:120]}...")
    return "\n".join(lines)
