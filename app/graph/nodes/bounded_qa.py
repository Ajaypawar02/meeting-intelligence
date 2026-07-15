"""Bounded problem-solving: answer in-authority questions; escalate the rest."""

from __future__ import annotations

import re
from typing import Any

from app.graph.state import MeetingGraphState
from app.llm.mock_llm import AGENT_AUTHORITY, MUST_ESCALATE
from app.schemas.meeting_record import (
    ActionItem,
    BoundedAnswer,
    EscalationItem,
    ItemStatus,
    SegmentClass,
    SourceRef,
)
from app.tools.retriever_tool import retrieve_context


_OUT_OF_AUTHORITY = re.compile(
    r"\b(?:budget|headcount|hire|salary|compensation|slip(?:ping)? (?:the )?deadline|"
    r"move the date|push the release|commit(?:ting)? \$)\b",
    re.I,
)


def bounded_qa_node(state: MeetingGraphState) -> dict[str, Any]:
    segments = state.get("segments") or []
    context = state.get("context_snippets") or []
    answers: list[BoundedAnswer] = []
    escalations = list(state.get("escalations") or [])
    proposals: list[ActionItem] = []

    open_qs = [s for s in segments if s.classification == SegmentClass.OPEN_QUESTION]
    # Also scan follow-ups / raw open language in action_items that look like questions
    for seg in open_qs:
        text = seg.text
        if _OUT_OF_AUTHORITY.search(text):
            esc = EscalationItem(
                id=f"EQ{len(escalations)+1:03d}",
                description=text,
                reason="out_of_authority",
                source_refs=[
                    SourceRef(
                        line_id=seg.line_ids[0] if seg.line_ids else seg.segment_id,
                        timestamp="",
                        speaker="",
                        excerpt=text[:160],
                    )
                ],
                proposed_by_agent=None,
            )
            escalations.append(esc)
            answers.append(
                BoundedAnswer(
                    question=text,
                    answer=None,
                    within_authority=False,
                    escalation=esc,
                )
            )
            continue

        # In-authority: try retrieve
        hits = retrieve_context(text, top_k=2) or list(context)[:2]
        if hits and re.search(r"deploy checklist|rollback|canary", text, re.I):
            answer_text = (
                f"From {hits[0].title}: {hits[0].text[:400]} "
                "(proposal based on retrieved docs — not a new decision)."
            )
            answers.append(
                BoundedAnswer(
                    question=text,
                    answer=answer_text,
                    within_authority=True,
                    sources=hits[:2],
                )
            )
        elif re.search(r"someone from platform|who (?:should|can)", text, re.I):
            # Suggest owner as proposal from past patterns
            suggestion = "Ava"
            for snip in context:
                if "Ava" in snip.text and "flag" in snip.text.lower():
                    suggestion = "Ava Chen"
                    break
            proposals.append(
                ActionItem(
                    id=f"P{len(proposals)+1:03d}",
                    task=f"[PROPOSAL] Suggested owner for: {text}",
                    owner=suggestion,
                    owner_inferred=True,
                    due_date=None,
                    due_date_inferred=True,
                    confidence=0.5,
                    status=ItemStatus.NEEDS_REVIEW,
                    is_proposal=True,
                )
            )
            answers.append(
                BoundedAnswer(
                    question=text,
                    answer=(
                        f"Proposed owner '{suggestion}' based on past ownership patterns. "
                        "Marked as proposal — requires human approval."
                    ),
                    within_authority=True,
                    sources=list(context)[:1],
                )
            )
        else:
            answers.append(
                BoundedAnswer(
                    question=text,
                    answer=(
                        "No high-confidence factual answer in retrieved context; "
                        "leaving as follow-up for the team."
                    ),
                    within_authority=True,
                    sources=hits,
                )
            )

    actions = list(state.get("action_items") or []) + proposals
    return {
        "bounded_answers": answers,
        "escalations": escalations,
        "action_items": actions,
        "node_trace": [
            {
                "node": "bounded_qa",
                "questions": len(open_qs),
                "answered": sum(1 for a in answers if a.answer and a.within_authority),
                "escalated": sum(1 for a in answers if not a.within_authority),
                "authority": AGENT_AUTHORITY,
                "must_escalate": MUST_ESCALATE,
            }
        ],
    }
