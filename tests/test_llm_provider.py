"""Tests for HybridExtractor fallback and JSON parsing."""

from __future__ import annotations

from app.llm.extractor import HybridExtractor, _parse_json_object


class _BrokenModel:
    def invoke(self, prompt, **kwargs):
        raise RuntimeError("model down")


class _JsonModel:
    def invoke(self, prompt, **kwargs):
        return """
        {
          "summary": "LLM summary",
          "segments": [],
          "decisions": [{
            "id": "D001",
            "description": "TTL is five minutes",
            "decided_by": "Priya",
            "source_refs": [{"line_id": "L004", "timestamp": "10:05", "speaker": "Priya", "excerpt": "decided"}],
            "confidence": 0.91
          }],
          "action_items": [],
          "blockers": [],
          "follow_ups": [],
          "escalations": []
        }
        """


def test_hybrid_falls_back_to_mock_on_model_error():
    lines = [
        {
            "line_id": "L004",
            "speaker": "Priya",
            "timestamp": "10:05",
            "text": "We've decided to go with a five-minute TTL.",
            "sensitivity_tag": "general",
        }
    ]
    ext = HybridExtractor(_BrokenModel(), backend_name="ollama")
    result = ext.classify_and_extract(lines)
    assert result["_extractor_backend"] == "ollama->mock_fallback"
    assert result["decisions"]


def test_hybrid_uses_model_json_when_valid():
    lines = [
        {
            "line_id": "L004",
            "speaker": "Priya",
            "timestamp": "10:05",
            "text": "We've decided to go with a five-minute TTL.",
            "sensitivity_tag": "general",
        }
    ]
    ext = HybridExtractor(_JsonModel(), backend_name="ollama")
    result = ext.classify_and_extract(lines)
    assert result["_extractor_backend"] == "ollama"
    assert result["summary"] == "LLM summary"
    assert result["decisions"][0]["id"] == "D001"


def test_parse_json_strips_fences():
    raw = _parse_json_object("```json\n{\"a\": 1}\n```")
    assert raw == {"a": 1}
