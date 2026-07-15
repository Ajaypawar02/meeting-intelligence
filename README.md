# Meeting Intelligence

Agent-led meeting capture built with **LangChain + LangGraph**: ingest a transcript, retrieve org context, **filter private content before any LLM call**, extract decisions/action items with source refs, answer only in-authority questions, and route low-confidence / out-of-authority items to a human review queue.

**No paid API key required** — defaults to a deterministic mock LLM. Optional real models: **Groq** / **OpenRouter** (free API keys), **Ollama** (local), or **OpenAI**. Extraction falls back to mock if the model call fails.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# End-to-end on the sample transcript (mock LLM — no key needed)
python -m app.main run data/sample_transcripts/sprint_sync_001.json --force-continue

# API + Swagger
python -m app.main serve
# open http://localhost:8000/docs
# POST /meetings  {"transcript_path": "data/sample_transcripts/sprint_sync_001.json", "force_continue": true}

# Optional Streamlit UI (API must be running)
streamlit run streamlit_app.py
```

## LLM providers

| Provider | Env | Cost |
|----------|-----|------|
| `mock` (default) | `LLM_PROVIDER=mock` | none |
| `groq` | `GROQ_API_KEY` + `GROQ_MODEL` | free-tier cloud API |
| `openrouter` | `OPENROUTER_API_KEY` + model with `:free` | free/cheap cloud API |
| `ollama` | local daemon + `OLLAMA_MODEL` | free local |
| `openai` | `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`) | paid, or any compatible free host |

```bash
pip install -e ".[llm]"
# .env → LLM_PROVIDER=groq  GROQ_API_KEY=gsk-...
```

See `.env.example`. Graders should leave `LLM_PROVIDER=mock`.

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
| Handback to team | JSON + markdown + mock tickets/notify |
| Human approval | Review queue + `POST .../items/{id}/review` |

## Architecture (LangGraph)

```
ingest → retrieve_context → permission_filter → segment_classify
      → extract_structured → bounded_qa → critique_confidence
      → human_review_gate ─┬→ aggregate → END
                           └→ await_human → END (resume later)
```

Privacy gate runs **before** generation so restricted lines never enter extraction prompts for that audience.

## Configuration

Copy `.env.example` → `.env`. Default `LLM_PROVIDER=mock` needs no key. Never commit `.env`.

## Tests & eval

```bash
pytest -q
```

Manual scored checklist: [`tests/eval_checklist.md`](tests/eval_checklist.md).

## Reviewer guidance

1. **Zero-key path (required):** `LLM_PROVIDER=mock` (or unset key) →  
   `python -m app.main run data/sample_transcripts/sprint_sync_001.json --force-continue`
2. Confirm output under `artifacts/runs/` has summary, decisions, action items, blockers, escalations, `source_refs`, and `needs_review` / confidence fields.
3. **Privacy hard check:** with `audience_role=general`, confirm `confidential-hr` / hiring language and finance `$40k` do **not** appear in the record; `redacted_segments_count` ≥ 1.
4. **HITL:** submit via Swagger `POST /meetings` with `force_continue=false`, then `POST /meetings/{run_id}/items/{item_id}/review` for a queue id (e.g. approve/edit an action item). Item should leave `review_queue` and show `status=approved`.
5. Read [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) and [`artifacts/steering_transcript.md`](artifacts/steering_transcript.md) for tooling + one reject/accept steering cycle.
6. Optional: set Groq/OpenRouter key to compare live vs mock extraction quality.

## Assumptions

- “Join call” = sanitized transcript feed, not live audio/video dial-in.
- Sample markdown docs stand in for Confluence / Drive / Slack history.
- Role → sensitivity tag map stands in for live IAM.
- Mock tickets/notify write local JSON files instead of real Slack/Jira.

## Limitations

- Mock LLM is regex/rule-based — good for offline demos, weaker on messy real transcripts.
- Live LLM quality depends on the free-tier model; JSON parse failures fall back to mock.
- In-memory LangGraph checkpoints + API `_RUNS` reset when the server restarts.
- Permissions are static tags on transcript lines, not enterprise DLP.
- “Join call” is simulated; no Zoom/Meet bot or streaming ASR.
- Streamlit UI is a thin client over the API; production auth is out of scope.

## Future improvements

- Persist checkpoints/runs (SQLite/Postgres) across restarts.
- Streaming transcript chunks with incremental extraction.
- Real Slack/Jira adapters behind the existing mock tool interfaces.
- Stronger structured-output binding (`with_structured_output`) for live models.
- Eval harness with labeled precision/recall metrics in CI.
- Fine-grained ACL (per-attendee redaction) and audit logs.

## Repo map

- `app/graph/` — LangGraph assembly + nodes  
- `app/llm/` — provider + extractor + mock fallback  
- `app/permissions/` — access map  
- `data/` — sample transcript + docs  
- `tests/` — pytest + `eval_checklist.md`  
- `artifacts/steering_transcript.md` — required steering artifact  
- `AGENT_WORKFLOW.md` — AI vs manual change log  
