"""Assemble the LangGraph meeting-intelligence workflow."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from app.graph.nodes.aggregate_output import aggregate_output_node
from app.graph.nodes.bounded_qa import bounded_qa_node
from app.graph.nodes.critique_confidence import critique_confidence_node
from app.graph.nodes.extract_structured import (
    extract_structured_node,
    segment_classify_node,
)
from app.graph.nodes.human_review_gate import human_review_gate_node
from app.graph.nodes.ingest import ingest_node
from app.graph.nodes.permission_filter import permission_filter_node
from app.graph.nodes.retrieve_context import retrieve_context_node
from app.graph.state import MeetingGraphState
from app.schemas import meeting_record as meeting_schemas

# Allowlist custom Pydantic/enum types stored in LangGraph checkpoints.
# Without this, resume/deserialize emits "unregistered type" warnings.
_MSGPACK_SCHEMA_ALLOWLIST: tuple[tuple[str, str], ...] = tuple(
    ("app.schemas.meeting_record", name)
    for name, obj in vars(meeting_schemas).items()
    if isinstance(obj, type)
    and obj.__module__ == "app.schemas.meeting_record"
    and not name.startswith("_")
)


def _default_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(allowed_msgpack_modules=_MSGPACK_SCHEMA_ALLOWLIST)
    return MemorySaver(serde=serde)


def _route_after_critique(state: MeetingGraphState) -> Literal["human_review_gate", "aggregate"]:
    if state.get("paused_for_review"):
        return "human_review_gate"
    return "aggregate"


def _route_after_human(state: MeetingGraphState) -> Literal["aggregate", "await_human"]:
    resolutions = state.get("human_resolutions") or {}
    if state.get("paused_for_review") and not resolutions.get("_force_continue"):
        # Still waiting — end this invocation; caller resumes with resolutions.
        return "await_human"
    return "aggregate"


def build_graph(checkpointer: Any | None = None):
    graph = StateGraph(MeetingGraphState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("permission_filter", permission_filter_node)
    graph.add_node("segment_classify", segment_classify_node)
    graph.add_node("extract_structured", extract_structured_node)
    graph.add_node("bounded_qa", bounded_qa_node)
    graph.add_node("critique_confidence", critique_confidence_node)
    graph.add_node("human_review_gate", human_review_gate_node)
    graph.add_node("aggregate", aggregate_output_node)
    graph.add_node("await_human", lambda state: {
        "node_trace": [{
            "node": "await_human",
            "message": "Paused for human review",
            "review_queue_size": len(state.get("review_queue") or []),
        }]
    })

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "retrieve_context")
    graph.add_edge("retrieve_context", "permission_filter")
    graph.add_edge("permission_filter", "segment_classify")
    graph.add_edge("segment_classify", "extract_structured")
    graph.add_edge("extract_structured", "bounded_qa")
    graph.add_edge("bounded_qa", "critique_confidence")
    graph.add_conditional_edges(
        "critique_confidence",
        _route_after_critique,
        {
            "human_review_gate": "human_review_gate",
            "aggregate": "aggregate",
        },
    )
    graph.add_conditional_edges(
        "human_review_gate",
        _route_after_human,
        {
            "aggregate": "aggregate",
            "await_human": "await_human",
        },
    )
    graph.add_edge("await_human", END)
    graph.add_edge("aggregate", END)

    memory = checkpointer if checkpointer is not None else _default_checkpointer()
    return graph.compile(checkpointer=memory)


# Module-level compiled graph for API reuse
_GRAPH = None


def get_compiled_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
