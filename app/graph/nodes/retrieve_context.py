"""Graph node: retrieve prior context (RAG over sample docs)."""

from __future__ import annotations

from typing import Any

from app.graph.state import MeetingGraphState
from app.tools.retriever_tool import lookup_past_action_items, retrieve_context


def retrieve_context_node(state: MeetingGraphState) -> dict[str, Any]:
    meta = state["metadata"]
    lines = state.get("transcript") or []
    # Prefer filtered transcript if already present (normally retrieval runs before filter
    # on full meeting text for recall; privacy gate still strips before LLM generation).
    query_parts = [meta.title, meta.project or "", meta.team or ""]
    query_parts.extend(line.text for line in lines[:8])
    query = " ".join(p for p in query_parts if p)

    snippets = retrieve_context(query, top_k=3)
    past = lookup_past_action_items(meta.project)
    # Dedupe by doc_id
    by_id = {s.doc_id: s for s in snippets + past}
    merged = list(by_id.values())

    return {
        "context_snippets": merged,
        "node_trace": [
            {
                "node": "retrieve_context",
                "docs": [s.doc_id for s in merged],
                "count": len(merged),
            }
        ],
    }
