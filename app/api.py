"""Minimal FastAPI surface: submit / fetch / approve."""

from __future__ import annotations

import os
# Force this before LangGraph initializes
os.environ["LANGGRAPH_STRICT_MSGPACK"] = "false"

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm.llm_provider import active_llm_label
from app.pipeline import run_meeting_pipeline


import warnings

warnings.filterwarnings("ignore")


app = FastAPI(
    title="Meeting Intelligence API",
    description="Agent-led meeting capture with privacy gates and human review",
    version="0.1.0",
)

# In-memory run store (demo). Keyed by run_id.
_RUNS: dict[str, dict[str, Any]] = {}


class SubmitRequest(BaseModel):
    transcript_path: str | None = Field(
        default=None,
        description="Server-side path to transcript JSON (preferred for samples)",
    )
    transcript: dict[str, Any] | None = Field(
        default=None,
        description="Inline transcript payload if not using a path",
    )
    audience_role: str = "general"
    force_continue: bool = False


class ApproveRequest(BaseModel):
    action: str = Field(description="approve | edit | reject | reassign")
    edited_payload: dict[str, Any] | None = None
    force_continue: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm": active_llm_label(),
    }


@app.post("/meetings")
def submit_meeting(body: SubmitRequest) -> dict[str, Any]:
    settings = get_settings()
    path: Path

    if body.transcript_path:
        path = Path(body.transcript_path)
        if not path.is_absolute():
            path = (settings.data_dir.parent / path).resolve()
            if not path.exists():
                path = Path(body.transcript_path).resolve()
    elif body.transcript:
        tmp_dir = settings.output_dir / "_uploads"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        path = tmp_dir / f"upload_{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(body.transcript), encoding="utf-8")
    else:
        raise HTTPException(400, "Provide transcript_path or transcript")

    if not path.exists():
        raise HTTPException(404, f"Transcript not found: {path}")

    result = run_meeting_pipeline(
        path,
        audience_role=body.audience_role,
        force_continue=body.force_continue,
    )
    _RUNS[result["run_id"]] = {
        **result,
        "transcript_path": str(path),
        "audience_role": body.audience_role,
        "approvals": {},
    }
    return {
        "run_id": result["run_id"],
        "paused_for_review": result["paused_for_review"],
        "record": result["record"],
        "handback_paths": result["handback_paths"],
    }


@app.get("/meetings/{run_id}")
def fetch_meeting(run_id: str) -> dict[str, Any]:
    if run_id not in _RUNS:
        raise HTTPException(404, "Unknown run_id")
    stored = _RUNS[run_id]
    return {
        "run_id": run_id,
        "paused_for_review": stored.get("paused_for_review"),
        "record": stored.get("record"),
        "handback_paths": stored.get("handback_paths"),
        "node_trace": stored.get("node_trace"),
    }


@app.post("/meetings/{run_id}/items/{item_id}/review")
def approve_item(run_id: str, item_id: str, body: ApproveRequest) -> dict[str, Any]:
    if run_id not in _RUNS:
        raise HTTPException(404, "Unknown run_id")
    stored = _RUNS[run_id]
    approvals = dict(stored.get("approvals") or {})
    approvals[item_id] = {
        "action": body.action,
        "edited_payload": body.edited_payload,
    }
    if body.force_continue:
        approvals["_force_continue"] = True

    result = run_meeting_pipeline(
        stored["transcript_path"],
        audience_role=stored.get("audience_role", "general"),
        run_id=run_id,
        human_resolutions=approvals,
        force_continue=body.force_continue,
        thread_id=stored.get("thread_id") or run_id,
    )
    # Preserve cumulative approvals across reviews (do not wipe prior item ids).
    _RUNS[run_id] = {
        **result,
        "transcript_path": stored["transcript_path"],
        "audience_role": stored.get("audience_role", "general"),
        "approvals": approvals,
        "thread_id": result.get("thread_id") or stored.get("thread_id") or run_id,
    }
    return {
        "run_id": run_id,
        "paused_for_review": result["paused_for_review"],
        "record": result["record"],
        "handback_paths": result["handback_paths"],
    }
