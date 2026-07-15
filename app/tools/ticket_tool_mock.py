"""Mock create-ticket tool for approved action items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings


def create_ticket_mock(action_item: dict[str, Any], run_id: str) -> dict[str, Any]:
    settings = get_settings()
    out_dir = settings.output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ticket = {
        "ticket_id": f"TICKET-{action_item.get('id', 'X')}",
        "title": action_item.get("task", "")[:80],
        "assignee": action_item.get("owner") or "unassigned",
        "due_date": action_item.get("due_date"),
        "status": "created_mock",
        "source_action_id": action_item.get("id"),
    }
    path = out_dir / f"ticket_{ticket['ticket_id']}.json"
    path.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
    return {**ticket, "path": str(path)}
