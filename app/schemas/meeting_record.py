"""Shared domain schemas for meeting records and graph intermediate items."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class SensitivityTag(str, Enum):
    GENERAL = "general"
    FINANCE = "finance"
    CONFIDENTIAL_HR = "confidential-hr"


class SegmentClass(str, Enum):
    DISCUSSION = "discussion"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    BLOCKER = "blocker"
    OPEN_QUESTION = "open_question"
    OFF_TOPIC = "off_topic"
    ESCALATION = "escalation"


class ItemStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    ESCALATED = "escalated"
    APPROVED = "approved"
    REJECTED = "rejected"


class TranscriptLine(BaseModel):
    speaker: str
    timestamp: str
    text: str
    sensitivity_tag: SensitivityTag = SensitivityTag.GENERAL
    line_id: str | None = None


class MeetingMetadata(BaseModel):
    meeting_id: str
    title: str
    date: str
    attendees: list[dict[str, str]] = Field(default_factory=list)
    project: str | None = None
    team: str | None = None


class SourceRef(BaseModel):
    line_id: str
    timestamp: str
    speaker: str
    excerpt: str


class ContextSnippet(BaseModel):
    doc_id: str
    title: str
    text: str
    score: float = 0.0


class TranscriptSegment(BaseModel):
    segment_id: str
    line_ids: list[str]
    text: str
    classification: SegmentClass
    sensitivity_tags: list[SensitivityTag] = Field(default_factory=list)


class DecisionItem(BaseModel):
    id: str
    description: str
    decided_by: str | None = None
    rationale: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float = 0.0
    status: ItemStatus = ItemStatus.NEEDS_REVIEW
    sensitivity: SensitivityTag = SensitivityTag.GENERAL
    is_proposal: bool = False


class ActionItem(BaseModel):
    id: str
    task: str
    owner: str | None = None
    owner_inferred: bool = False
    due_date: str | None = None
    due_date_inferred: bool = False
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float = 0.0
    status: ItemStatus = ItemStatus.NEEDS_REVIEW
    sensitivity: SensitivityTag = SensitivityTag.GENERAL
    is_proposal: bool = False


class BlockerItem(BaseModel):
    id: str
    description: str
    blocking: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float = 0.0
    status: ItemStatus = ItemStatus.AUTO_APPROVED
    sensitivity: SensitivityTag = SensitivityTag.GENERAL


class FollowUpItem(BaseModel):
    id: str
    topic: str
    reason_open: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    status: ItemStatus = ItemStatus.NEEDS_REVIEW


class EscalationItem(BaseModel):
    id: str
    description: str
    reason: Literal["out_of_authority", "low_confidence", "restricted_content"]
    source_refs: list[SourceRef] = Field(default_factory=list)
    proposed_by_agent: str | None = None


class BoundedAnswer(BaseModel):
    question: str
    answer: str | None = None
    within_authority: bool
    sources: list[ContextSnippet] = Field(default_factory=list)
    escalation: EscalationItem | None = None


class ReviewQueueItem(BaseModel):
    id: str
    item_type: Literal["decision", "action_item", "follow_up", "escalation", "blocker"]
    payload: dict
    reason: str
    human_action: Literal["approve", "edit", "reject", "reassign"] | None = None
    edited_payload: dict | None = None


class MeetingRecord(BaseModel):
    meeting_id: str
    title: str
    date: str
    summary: str
    decisions: list[DecisionItem] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    blockers: list[BlockerItem] = Field(default_factory=list)
    follow_ups: list[FollowUpItem] = Field(default_factory=list)
    escalations: list[EscalationItem] = Field(default_factory=list)
    review_queue: list[ReviewQueueItem] = Field(default_factory=list)
    context_used: list[ContextSnippet] = Field(default_factory=list)
    redacted_segments_count: int = 0
    audience_role: str = "general"
    auto_published_count: int = 0
    pending_review_count: int = 0
