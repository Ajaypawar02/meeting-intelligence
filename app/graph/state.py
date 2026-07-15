"""LangGraph shared state for the meeting intelligence pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.schemas.meeting_record import (
    ActionItem,
    BlockerItem,
    BoundedAnswer,
    ContextSnippet,
    DecisionItem,
    EscalationItem,
    FollowUpItem,
    MeetingMetadata,
    MeetingRecord,
    ReviewQueueItem,
    TranscriptLine,
    TranscriptSegment,
)


def _merge_lists(left: list, right: list) -> list:
    return (left or []) + (right or [])


class MeetingGraphState(TypedDict, total=False):
    """Typed state flowing through every graph node."""

    run_id: str
    audience_role: str
    metadata: MeetingMetadata
    transcript: list[TranscriptLine]
    filtered_transcript: list[TranscriptLine]
    redacted_count: int
    context_snippets: list[ContextSnippet]
    segments: list[TranscriptSegment]
    decisions: list[DecisionItem]
    action_items: list[ActionItem]
    blockers: list[BlockerItem]
    follow_ups: list[FollowUpItem]
    escalations: list[EscalationItem]
    bounded_answers: list[BoundedAnswer]
    review_queue: list[ReviewQueueItem]
    human_resolutions: dict[str, Any]
    meeting_record: MeetingRecord
    handback_paths: list[str]
    node_trace: Annotated[list[dict[str, Any]], operator.add]
    paused_for_review: bool
    error: str | None
    # Internal pass-throughs between adjacent nodes
    _extraction_cache: dict[str, Any]
    _draft_summary: str
