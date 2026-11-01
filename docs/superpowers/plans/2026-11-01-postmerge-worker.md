# Postmerge worker implementation plan

> **For agentic workers:** Use Superpowers subagent-driven-development or executing-plans, TDD and independent final review.

Goal: complete event receipt → independent reviewer → durable local task status.

Spec: ../specs/2026-11-01-postmerge-worker-design.md.

Stack: Python3.11+ stdlib, SQLite, Git, GitHub REST, existing Codex exec/custom subprocess. Preserve unrelated checkout edits; no installs or model overrides.

1. github_source.py/tests: GitHubSource(repository, token=None), poll()->list[bundle]. API client paginated GET, bounded ZIP; verify PR/merge/run/markers/provenance. Bundle keys repository,pr_number,merge_commit,run_id,attempt,task_ids,platforms (dict OS->passed/failed),run_url,delivery_key. Auth helper separately default env/gh/git; errors never expose response tokens. Deterministic injected HTTP transport for tests.
2. reviewer.py/tests + optional env support processes/windows_job: ReviewRunner(config).review(checkout,task,bundle,output_dir)->dict validated task_id/commit/verdict/summary/findings. Codex read-only/schema/output file; custom review_argv protocol; timeout and secret env filtering; skill pin. Use existing bounded process runner.
3. tasks.py/tests: postmerge_state update helper and overall visible states; accept_task main_ref optional restricted to main refs, store and revalidate it. Existing cards unaffected. Root implements after module APIs stabilize.
4. postmerge_worker.py + tests: durable journal claim, aggregate mandatory OS, safe exact-SHA checkout, immutable snapshot check, dispatch review, persist evidence/acceptance; dedup, crash needs attention and retry. No direct writes to user's code or branch switch. CLI worker config/once/watch/status/retry integration; examples and docs.
5. Independent spec/code/test acceptance, local full suite, one bounded real poll/reviewer if existing credentials permit. Publish reviewable PR with Task-Tower marker; not done until main+postmerge. Don't claim all-OS support without CI.

Review focus: untrusted artifacts/redirects; duplicate/cross-process running; unsupported harness/no auth; stale card race; remote main validation and exact SHA; no false done on errors. Tests assigned to respective modules.
