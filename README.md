# Meeting Intelligence

Agent-led meeting capture built with **LangChain + LangGraph**: ingest a transcript, retrieve org context, **filter private content before any LLM call**, extract decisions/action items with source refs, answer only in-authority questions, and route low-confidence / out-of-authority items to a human review queue.

**No paid API key required** — defaults to a deterministic mock LLM.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# End-to-end on the sample transcript (mock LLM)
python -m app.main run data/sample_transcripts/sprint_sync_001.json --force-continue

# API
python -m app.main serve
# POST /meetings  {"transcript_path": "data/sample_transcripts/sprint_sync_001.json", "force_continue": true}
```

Docker:

```bash
docker compose up --build
curl -s http://localhost:8000/health
```

## What it demonstrates

| Requirement | How |
|-------------|-----|
| Joins a discussion | Transcript ingest (sanitized demo) |
| Brings domain context | Local RAG over `data/sample_docs/` |
| Bounded problem-solving | `bounded_qa` node + authority lists |
| Structured outputs | Pydantic `MeetingRecord` with source refs |
| Autonomy vs escalate | Confidence + out-of-authority + restricted tags |
| Permissions / privacy | Pre-LLM redaction via role → tag map |
| Handback | JSON + markdown recap + mock tickets/notify |
| Human approval | Review queue + `/items/{id}/review` + `--force-continue` |

## Architecture (LangGraph)

```
ingest → retrieve_context → permission_filter → segment_classify
      → extract_structured → bounded_qa → critique_confidence
      → human_review_gate ─┬→ aggregate → END
                           └→ await_human → END (resume later)
```

Privacy gate runs **before** generation so restricted lines never enter extraction prompts for that audience.

## Configuration

Copy `.env.example` → `.env`. Leave `OPENAI_API_KEY` unset (or `LLM_PROVIDER=mock`) for offline mode. Optional real model: install `[llm]` extras and set a key.

## Tests & eval

```bash
pytest -q
```

Manual scored checklist: [`tests/eval_checklist.md`](tests/eval_checklist.md).

## Repo map

See design-aligned layout under `app/graph/nodes/`, `data/`, `artifacts/`, plus [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) and [`artifacts/steering_transcript.md`](artifacts/steering_transcript.md).

## Assumptions

- “Join call” = transcript feed, not live A/V.
- Sample docs stand in for Confluence/Drive.
- Static role→tag map stands in for IAM.
