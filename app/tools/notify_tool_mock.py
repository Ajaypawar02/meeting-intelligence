"""Mock notify-owner tool."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings


def notify_owner_mock(owner: str, message: str, run_id: str) -> dict[str, Any]:
    settings = get_settings()
    out_dir = settings.output_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": "mock-slack",
        "to": owner,
        "message": message,
        "status": "sent_mock",
    }
    safe_owner = "".join(c if c.isalnum() else "_" for c in owner) or "unknown"
    path = out_dir / f"notify_{safe_owner}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {**payload, "path": str(path)}
