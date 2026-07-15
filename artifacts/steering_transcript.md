# Steering transcript — confidence + privacy

## Prompt (to coding agent)

> Implement extraction so action items with an explicit owner and due date auto-approve. Also make sure the general-audience meeting record never contains the confidential HR line from the sample transcript.

## Rejected output (first attempt)

Agent returned a pipeline that:

1. Auto-approved an action item whose owner was inferred (“someone from platform” → Ava) with `status=auto_approved` and immediately wrote a mock ticket.
2. Ran the LLM/mock extractor on the **full** transcript, then redacted strings from the final JSON with a regex — the HR hiring sentence still appeared in intermediate `node_trace` payloads and briefly in the draft summary before strip.

**Why rejected**

- Inferred owner must be a **proposal** / `needs_review`, not an auto-published fact.
- Privacy filter must run **before** generation so restricted text never enters the extraction prompt or traces of model I/O for that audience.

## Accepted output (after steering)

Constraints enforced in code:

1. `critique_confidence_node` sends inferred/missing owner or due date to `review_queue`; `is_proposal=True` items never auto-ticket.
2. `permission_filter_node` precedes `segment_classify` / `extract_structured`; `filtered_transcript` is the only line list used for classification.
3. Redacted lines become `escalations` with `reason=restricted_content` and excerpt `[REDACTED]` — no raw confidential text in the durable record for `audience_role=general`.

Verification:

```bash
pytest tests/test_permission_filter.py tests/test_confidence_routing.py -q
python -m app.main run data/sample_transcripts/sprint_sync_001.json --force-continue
# assert: hiring/backfill absent from printed JSON; A001-like inferred items in review_queue
```
