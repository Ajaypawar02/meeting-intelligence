"""CLI entry point for meeting intelligence pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON

from app.llm.llm_provider import active_llm_label
from app.pipeline import run_meeting_pipeline

app = typer.Typer(
    name="meeting-intel",
    help="Agent-led meeting intelligence (LangGraph). Mock LLM by default.",
    add_completion=False,
)
console = Console()


@app.command("run")
def run(
    transcript: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to transcript JSON",
    ),
    audience_role: str = typer.Option("general", help="Output audience role for permission filter"),
    force_continue: bool = typer.Option(
        False,
        "--force-continue",
        help="Publish partial record even if review queue is non-empty",
    ),
    approvals: Optional[Path] = typer.Option(
        None,
        help="JSON file of human resolutions: {item_id: {action, edited_payload?}}",
    ),
    out: Optional[Path] = typer.Option(None, help="Write full result JSON to this path"),
) -> None:
    """Run the pipeline on a sample (or custom) transcript."""
    console.print(
        f"[bold]LLM mode:[/bold] {active_llm_label()} | "
        f"[bold]audience:[/bold] {audience_role}"
    )
    human = {}
    if approvals and approvals.exists():
        human = json.loads(approvals.read_text(encoding="utf-8"))

    result = run_meeting_pipeline(
        transcript,
        audience_role=audience_role,
        human_resolutions=human,
        force_continue=force_continue,
    )

    if result["paused_for_review"]:
        console.print("[yellow]Paused for human review[/yellow]")
        console.print(f"Review queue: {result['record'].get('pending_review_count')}")
    else:
        console.print("[green]Pipeline complete[/green]")

    console.print(JSON.from_data({
        "run_id": result["run_id"],
        "paused_for_review": result["paused_for_review"],
        "handback_paths": result["handback_paths"],
        "summary": result["record"].get("summary"),
        "redacted_segments_count": result["record"].get("redacted_segments_count"),
        "auto_published_count": result["record"].get("auto_published_count"),
        "pending_review_count": result["record"].get("pending_review_count"),
        "decisions": result["record"].get("decisions"),
        "action_items": result["record"].get("action_items"),
        "escalations": result["record"].get("escalations"),
        "review_queue": result["record"].get("review_queue"),
    }))

    if out:
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        console.print(f"Wrote {out}")


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(8000),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("app.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
