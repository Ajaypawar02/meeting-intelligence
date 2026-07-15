# AGENT_WORKFLOW.md

How this project was steered with AI tooling, what worked, and what was fixed manually.

## Tooling used

- **Cursor agent (Composer)** — scaffolding the LangGraph app from the design doc, implementing nodes/schemas/tests, and drafting sample I/O.
- **No paid LLM API** for the demo path — extraction uses a deterministic rule-based `MockLLM` so CI and graders need no keys.
- Optional **LangChain OpenAI** path behind `LLM_PROVIDER` / `OPENAI_API_KEY` for summary polish only.

## Where the agent helped

1. Mapping the planning doc → package layout (`graph/nodes`, permissions, schemas).
2. Wiring LangGraph conditional edges for critique → HITL → aggregate/await.
3. Generating a realistic sanitized transcript with intentional privacy + escalation traps.
4. Writing pytest coverage for redaction, confidence routing, and e2e mock runs.

## Where it failed / needed manual fixes

1. **State hygiene** — early drafts parked caches on ad-hoc keys; had to add `_extraction_cache` / `_draft_summary` to the TypedDict explicitly so LangGraph would retain them.
2. **Resume semantics** — “pause for human” cannot rely on a single invoke; the API stores `run_id`/`thread_id` and re-invokes with `human_resolutions` (or `--force-continue` for demos).
3. **Classification collision** — lines that are both questions and out-of-authority (e.g. slipping a launch date) must escalate first; authority checks were reordered to prefer safety.
4. **Privacy ordering** — an early sketch retrieved *and* prompted on the full transcript; the design requires filter-before-generation. Retrieval may see titles/early lines for recall, but extraction runs only on `filtered_transcript`.
5. **Proposal vs fact** — inferred owners had to be marked `is_proposal=True` and forced into `needs_review`, not auto-ticketed.

## Preferred steering pattern

1. Paste the architecture constraints (authority list, privacy-before-LLM, mock fallback).
2. Ask for a single vertical slice: ingest → filter → extract → critique on the sample file.
3. Reject outputs that auto-approve items without `source_refs` or that leak `confidential-hr` into general audience JSON.
4. Only then expand CLI/API/Docker.

See [`artifacts/steering_transcript.md`](artifacts/steering_transcript.md) for one concrete prompt → reject/accept cycle.
