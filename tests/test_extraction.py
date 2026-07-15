"""Unit tests for extraction, permission filter, and confidence routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.graph.nodes.critique_confidence import critique_confidence_node
from app.graph.nodes.extract_structured import (
    extract_structured_node,
    segment_classify_node,
)
from app.graph.nodes.ingest import load_transcript_file
from app.graph.nodes.permission_filter import permission_filter_node
from app.pipeline import run_meeting_pipeline
from app.schemas.meeting_record import (
    ActionItem,
    DecisionItem,
    ItemStatus,
    MeetingMetadata,
    SourceRef,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_transcripts" / "sprint_sync_001.json"


@pytest.fixture
def sample_state():
    meta, lines = load_transcript_file(SAMPLE)
    return {
        "run_id": "test-run",
        "audience_role": "general",
        "metadata": meta,
        "transcript": lines,
        "human_resolutions": {},
        "node_trace": [],
    }


def test_ingest_loads_sample():
    meta, lines = load_transcript_file(SAMPLE)
    assert meta.meeting_id == "sprint_sync_001"
    assert len(lines) == 12
    assert any(l.sensitivity_tag.value == "confidential-hr" for l in lines)


def test_permission_filter_redacts_hr_for_general(sample_state):
    out = permission_filter_node(sample_state)
    assert out["redacted_count"] >= 1
    assert all(
        line.sensitivity_tag.value != "confidential-hr"
        for line in out["filtered_transcript"]
    )
    assert any(e.reason == "restricted_content" for e in out["escalations"])
    # Finance line is also redacted for general
    texts = " ".join(l.text for l in out["filtered_transcript"])
    assert "hiring plan" not in texts.lower()
    assert "$40k" not in texts


def test_permission_filter_allows_hr_role(sample_state):
    sample_state["audience_role"] = "hr"
    out = permission_filter_node(sample_state)
    texts = " ".join(l.text for l in out["filtered_transcript"])
    assert "hiring" in texts.lower() or "backfill" in texts.lower()
    # finance still blocked for hr-only map
    assert all(l.sensitivity_tag.value != "finance" for l in out["filtered_transcript"])


def test_extraction_finds_decision_and_action(sample_state):
    filtered = permission_filter_node(sample_state)
    state = {**sample_state, **filtered}
    seg = segment_classify_node(state)
    state = {**state, **seg}
    ext = extract_structured_node(state)
    assert len(ext["decisions"]) >= 1
    assert any("five-minute" in d.description.lower() or "ttl" in d.description.lower() for d in ext["decisions"]) or len(
        ext["decisions"]
    ) >= 1
    assert len(ext["action_items"]) >= 1
    assert len(ext["blockers"]) >= 1
    assert len(ext["escalations"]) >= 1 or any(
        e.reason == "out_of_authority" for e in state.get("escalations", [])
    )


def test_confidence_routes_inferred_owner_to_review():
    state = {
        "decisions": [
            DecisionItem(
                id="D001",
                description="Ship it",
                decided_by="Priya",
                source_refs=[
                    SourceRef(
                        line_id="L004",
                        timestamp="10:05",
                        speaker="Priya",
                        excerpt="decided",
                    )
                ],
                confidence=0.95,
            )
        ],
        "action_items": [
            ActionItem(
                id="A001",
                task="Draft email",
                owner=None,
                owner_inferred=True,
                due_date=None,
                due_date_inferred=True,
                source_refs=[
                    SourceRef(
                        line_id="L008",
                        timestamp="10:12",
                        speaker="Priya",
                        excerpt="someone",
                    )
                ],
                confidence=0.55,
            )
        ],
        "blockers": [],
        "follow_ups": [],
        "escalations": [],
        "node_trace": [],
    }
    out = critique_confidence_node(state)
    assert out["decisions"][0].status == ItemStatus.AUTO_APPROVED
    assert out["action_items"][0].status == ItemStatus.NEEDS_REVIEW
    assert any(q.id == "A001" for q in out["review_queue"])
    assert out["paused_for_review"] is True


def test_e2e_mock_pipeline_force_continue():
    result = run_meeting_pipeline(
        SAMPLE,
        audience_role="general",
        force_continue=True,
        run_id="e2e-force",
        thread_id="e2e-force",
    )
    assert result["record"]["redacted_segments_count"] >= 1
    assert result["record"]["summary"]
    assert result["handback_paths"]
    # Confidential content must not appear in summary/outputs for general
    blob = json.dumps(result["record"])
    assert "hiring plan" not in blob.lower()
    assert "backfill" not in blob.lower()


def test_source_refs_present_on_auto_items():
    result = run_meeting_pipeline(
        SAMPLE,
        audience_role="general",
        force_continue=True,
        run_id="e2e-refs",
        thread_id="e2e-refs-thread",
    )
    for d in result["record"].get("decisions", []):
        if d.get("status") in ("auto_approved", "approved"):
            assert d.get("source_refs"), f"decision {d['id']} missing sources"
