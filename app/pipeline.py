"""Run helpers shared by CLI and API."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.graph.build_graph import build_graph, get_compiled_graph
from app.graph.nodes.ingest import load_transcript_file
from app.schemas.meeting_record import MeetingRecord


def run_meeting_pipeline(
    transcript_path: Path | str,
    *,
    audience_role: str = "general",
    run_id: str | None = None,
    human_resolutions: dict[str, Any] | None = None,
    force_continue: bool = False,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Execute (or resume) the LangGraph pipeline on a transcript file."""
    meta, lines = load_transcript_file(transcript_path)
    rid = run_id or f"{meta.meeting_id}-{uuid.uuid4().hex[:8]}"
    resolutions = dict(human_resolutions or {})
    if force_continue:
        resolutions["_force_continue"] = True
    resolutions.setdefault("transcript_path", str(transcript_path))

    graph = get_compiled_graph()
    tid = thread_id or rid
    config = {"configurable": {"thread_id": tid}}

    initial: dict[str, Any] = {
        "run_id": rid,
        "audience_role": audience_role,
        "metadata": meta,
        "transcript": lines,
        "human_resolutions": resolutions,
        "node_trace": [],
    }

    snapshot = graph.get_state(config)
    has_checkpoint = bool(snapshot.values)
    resuming = has_checkpoint and bool(human_resolutions or force_continue)

    if resuming:
        # Graph previously stopped at await_human → END. Plain invoke(None) does
        # not re-enter human_review_gate, so approvals would be ignored.
        # Treat the update as coming from critique_confidence so the next step
        # follows its conditional edge back into human_review_gate.
        graph.update_state(
            config,
            {
                "human_resolutions": resolutions,
                # Keep paused so routing still selects human_review_gate;
                # the gate itself clears pause after applying approvals /
                # force_continue.
                "paused_for_review": True,
            },
            as_node="critique_confidence",
        )
        final_state = graph.invoke(None, config)
    else:
        final_state = graph.invoke(initial, config)

    record = final_state.get("meeting_record")
    if isinstance(record, MeetingRecord):
        record_data = record.model_dump()
        record_data["status"] = "completed"
    elif isinstance(record, dict):
        record_data = dict(record)
        record_data.setdefault(
            "status",
            "completed" if not final_state.get("paused_for_review") else "paused_for_review",
        )
    else:
        # Paused before aggregate — build a partial view
        record_data = {
            "meeting_id": meta.meeting_id,
            "title": meta.title,
            "date": meta.date,
            "summary": "Pipeline paused pending human review.",
            "decisions": [
                d.model_dump() if hasattr(d, "model_dump") else d
                for d in final_state.get("decisions") or []
            ],
            "action_items": [
                a.model_dump() if hasattr(a, "model_dump") else a
                for a in final_state.get("action_items") or []
            ],
            "blockers": [
                b.model_dump() if hasattr(b, "model_dump") else b
                for b in final_state.get("blockers") or []
            ],
            "follow_ups": [
                f.model_dump() if hasattr(f, "model_dump") else f
                for f in final_state.get("follow_ups") or []
            ],
            "escalations": [
                e.model_dump() if hasattr(e, "model_dump") else e
                for e in final_state.get("escalations") or []
            ],
            "review_queue": [
                q.model_dump() if hasattr(q, "model_dump") else q
                for q in final_state.get("review_queue") or []
            ],
            "context_used": [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in final_state.get("context_snippets") or []
            ],
            "redacted_segments_count": final_state.get("redacted_count") or 0,
            "audience_role": audience_role,
            "auto_published_count": 0,
            "pending_review_count": len(final_state.get("review_queue") or []),
            "status": "paused_for_review",
        }

    return {
        "run_id": rid,
        "thread_id": tid,
        "paused_for_review": bool(final_state.get("paused_for_review")),
        "record": record_data,
        "handback_paths": final_state.get("handback_paths") or [],
        "node_trace": final_state.get("node_trace") or [],
        "bounded_answers": [
            a.model_dump() if hasattr(a, "model_dump") else a
            for a in final_state.get("bounded_answers") or []
        ],
    }


def new_graph_for_tests():
    """Fresh graph with isolated memory (for unit tests)."""
    return build_graph()
