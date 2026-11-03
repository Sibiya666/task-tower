# Independent specification and operational recovery review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: APPROVE specification and bounded operational recovery design. This is not development/test acceptance, a PR verdict, a postmerge verdict, or authority to close Issue16 manually.

Reviewed plan: task-tower-fetch-timeout/docs/superpowers/plans/2026-11-03-postmerge-fetch-budget.md

Plan raw SHA256: 762e1e554e526a9a4d09adb4ce3a4d7aece98b5e8d7eac5f107ad2d8cd60d806

Immutable release: 4875381be68282a7ad77ab7b1c5a3898cbc09304

Release task_tower/postmerge_worker.py raw SHA256: 724ab22274142fc92e3f789e979c4cf1c64ac1c4c6819546f751bb93788044c7

## Evidence and assessment

Independent sanitized Git Trace2 reproduction observed successful fetch exit0 after11.437s. Remote-ref acquisition completed in0.773s; the HTTPS helper exited after11.229s; maintenance ran afterward for0.062s. The existing10s subprocess timeout rejects a genuinely successful network operation. Later default0.782s and HTTP/1.1 5.406s samples show variability; they do not justify changing HTTP protocol, credentials or global configuration.

The immutable release already exposes Worker(refresh=...). Worker.once calls refresh before polling GitHubSource. Its exact-commit ancestry check, task snapshot, independent ReviewRunner, evidence binding and GitHubPublisher remain downstream. A private operational launcher using this existing seam can perform the same actual origin validation and exact real fetch with a60s subprocess timeout without altering the reviewed main source or fabricating a successful receipt. Increasing this host network budget changes neither accepted product content nor acceptance requirements. User authorization explicitly includes fixing the timeout and completing automatic acceptance/closure.

The product fix correctly keeps10s as the default local Git budget and uses60s solely at the worker's explicit fetch call. No retry loop, partial-success interpretation, changed source verification or acceptance waiver is needed.

## Required implementation and operational checks

1. Bind the recovery launcher and imported immutable release source hashes. Do not monkeypatch release modules or substitute tasks, source, reviewer, publisher, journal, bundle or verdict implementations.
2. The refresh must validate the actual configured origin against the repository with the release's existing matching semantics, then execute an argument-array git -C project fetch origin main with check=True and timeout=60. A timeout, nonzero exit or invalid origin must abort before source polling/review/publication. Output announcing FETCH_HEAD is never success evidence without exit0.
3. Preserve all platform requirements and the genuine current same-run/attempt GitHubSource bundle. Use the existing independently executing native reviewer and publisher, including publisher source revalidation. Leave Issue closure and Project transition to that publisher.
4. Stop the idle prior worker under the existing journal-lock checks for running reviews and live publication leases; preserve logs and database. Do not recover/reset/retry old review rows merely to obtain a pass. Run a single writer and preserve the original working-tree HEAD.
5. Independently review and test the concrete recovery launcher before running it. Verify actual main receipt, genuine review approve, published journal record, unique publication comment, closed Issue16 and Done Project projection afterward.
6. Label the60s setting as a subprocess network timeout, not a proof of hard process-tree termination or night readiness. Existing Python subprocess cleanup behavior remains a qualification; timeout failure must never grant progression.
7. Product changes still require their own focused RED/GREEN tests, independent development/test and exact-head/base PR review, green CI and serialized integration after Issue16's accepted main cycle. The recovery does not permit merging an unrelated product fix before that barrier clears.

No blocking specification findings. Implementation, launcher and live outcome are not yet inspected or accepted by this review.
