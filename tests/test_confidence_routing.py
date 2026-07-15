"""Confidence routing tests."""

from app.config import get_settings
from app.graph.nodes.critique_confidence import critique_confidence_node
from app.schemas.meeting_record import ActionItem, ItemStatus, SourceRef


def test_empty_source_refs_force_review():
    out = critique_confidence_node(
        {
            "decisions": [],
            "action_items": [
                ActionItem(
                    id="A-x",
                    task="Do the thing by Friday",
                    owner="Ava",
                    due_date="by Friday",
                    source_refs=[],
                    confidence=0.99,
                )
            ],
            "blockers": [],
            "follow_ups": [],
            "escalations": [],
            "node_trace": [],
        }
    )
    assert out["action_items"][0].status == ItemStatus.NEEDS_REVIEW
    assert out["action_items"][0].confidence <= get_settings().confidence_threshold


def test_explicit_owner_and_date_auto_approve():
    out = critique_confidence_node(
        {
            "decisions": [],
            "action_items": [
                ActionItem(
                    id="A-y",
                    task="I'll flip the flag by Friday",
                    owner="Ava",
                    owner_inferred=False,
                    due_date="by Friday",
                    due_date_inferred=False,
                    source_refs=[
                        SourceRef(
                            line_id="L005",
                            timestamp="10:06",
                            speaker="Ava",
                            excerpt="I'll own the prod flag flip by Friday.",
                        )
                    ],
                    confidence=0.9,
                )
            ],
            "blockers": [],
            "follow_ups": [],
            "escalations": [],
            "node_trace": [],
        }
    )
    assert out["action_items"][0].status == ItemStatus.AUTO_APPROVED
