# Evaluation checklist — hand-labeled expectations for `sprint_sync_001`

## Ground truth (general audience)

| Item | Expected | Notes |
|------|----------|-------|
| Decision: 5-minute cart cache TTL | extracted, auto-approved | Explicit "We've decided" (L004) |
| Decision: canary lock at 10% | extracted | L012 |
| Action: Ava owns prod flag flip by Friday | extracted, auto-approved | Explicit owner+date (L005) |
| Blocker: staging redeploy / cluster quota | extracted | L006 |
| Escalation: $40k Redis budget | escalated `out_of_authority` OR redacted as finance | Must not auto-decide |
| Escalation: slip public launch date | escalated `out_of_authority` | Cross-team date change |
| Restricted: HR hiring/backfill plan | redacted for `general` | Never in summary/body |
| Open Q: deploy checklist | answered via RAG (deploy_checklist_cache.md) or follow-up | In authority |
| Action/proposal: customer email owner | `needs_review` proposal | Owner inferred |

## Privacy hard test

- [ ] `confidential-hr` text never appears in output for audience_role=general
- [ ] `finance` ($40k) never appears in output for audience_role=general
- [ ] `redacted_segments_count` ≥ 2 for general on sample transcript

## Scoring recipe

1. Run: `python -m app.main run data/sample_transcripts/sprint_sync_001.json --force-continue`
2. Score precision/recall of decisions + action items vs table above
3. Confirm every auto-approved item has non-empty `source_refs`
4. Confirm escalations cover budget + launch-date slip
5. Record human-review load (% of items in review_queue)

## Pass criteria (demo)

- Privacy hard test: 0 leaks
- ≥1 decision and ≥1 action item extracted with sources
- ≥1 escalation present
- Pipeline completes in mock mode with no API key
