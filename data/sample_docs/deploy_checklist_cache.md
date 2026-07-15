# Deploy Checklist — Cache Layer Changes

Use this checklist for any production cache TTL or Redis topology change.

1. Confirm canary metrics (p95, error rate) are within SLO for at least 30 minutes.
2. Verify rollback flag path is tested in staging.
3. Page on-call SRE before flipping the production flag.
4. Post a short note in #platform-deploys with before/after p95.
5. Keep canary ≤ 10% for the first business day unless explicitly approved.

Last reviewed: 2026-06-01. Owner: platform eng lead.
