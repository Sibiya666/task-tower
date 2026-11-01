# Noninteractive Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a durable authorized delivery as one bounded isolated development attempt and return validated execution evidence.

**Architecture:** Bridge the existing dispatcher file protocol into an installation-local SQLite queue. A foreground worker claims one job, prepares an isolated worktree and invokes Codex or a trusted custom profile through the shared process runner. Durable fencing prevents uncertain attempts from being replayed.

**Tech Stack:** Python 3.11+, standard library, SQLite, Git worktrees, installed Codex CLI.

**Spec:** `docs/superpowers/specs/2026-11-01-noninteractive-executor-design.md`

## Global Constraints

- Use Python 3.11+ standard library only and existing `processes.run_command` cleanup.
- A worktree is not a security or credential sandbox.
- Remove `GH_TOKEN` and `GITHUB_TOKEN` from every child environment, including custom profiles and probes; never serialize either value.
- `execution_completed` never means task done, accepted, merged or Issue closed.
- Unknown process start, push or external outcome is fenced for reconciliation. Never expire a lease into blind rerun.
- Private installation state stays outside connected checkouts; canonical source text is UTF-8/LF.
- No model publication/push, PR publication, stage pipeline, background daemon or distributed worker pool is implemented here.

## Review Focus

1. Lost adapter response after durable commit returns the original receipt on lookup; never duplicates a job (Task 2).
2. Worker dies between claim and process bookkeeping: restart fences ownership instead of rerunning (Tasks 2/4).
3. Child exits but descendants survive: cleanup failure blocks completion (Task 3).
4. Correct-looking model JSON from another attempt/source is rejected (Task 4).
5. Profile changes or credentials leak through a capability probe: launch blocks or strips credentials just like execution (Tasks 1/4).

## Ownership and gates

This branch owns executor modules, process extensions, dispatcher authentication regression and executor CLI wiring. Issue #22 owns books/UI in a separate worktree. Shared README/AGENTS/roadmap edits belong to coordinator reconciliation. Wait for independent specification acceptance before implementation; each implementation task gets a distinct review. Preserve authorization without asking for another per-task continue. Serialize merge/main acceptance; refresh waiting branch and invalidate head/base verdict after main changes.

### Task 1: Profiles, provenance and authenticated dependency source

**Files:** Create `task_tower/executor_profiles.py`, `tests/test_executor_profiles.py`; modify `task_tower/dispatcher.py`, `tests/test_dispatcher.py`.

**Interfaces:** `load_executor_config(path, connections) -> dict` validates installation-owned profiles, allowlist, bounds and path exclusions. `child_environment(environ) -> dict` removes both GitHub token names. `profile_fingerprint(profile) -> str` hashes canonical safe policy. Existing `_source(connection)` returns authenticated `GitHubSource`.

- [ ] Write RED tests: default dispatcher factory calls existing `resolve_token` and forwards returned token; `verified_done` remains unchanged. Test token names removed for execution/probes, unchanged host environment, custom explicit trust, unsafe alias paths, invalid limits and Superpowers file drift rejected.
- [ ] Run `python -m unittest tests.test_dispatcher tests.test_executor_profiles -v`; confirm new tests fail for missing implementation.
- [ ] Implement profile validation/fingerprinting, pinned instruction manifest validation and child environment; resolve/forward host token in `_source` without printing it.
- [ ] Rerun focused tests; require PASS. Obtain independent task review and record canonical input/output hashes.
- [ ] Commit only reviewed Task 1 files with message `feat: validate executor profiles and authenticated dispatch source`.

### Task 2: Durable queue and dispatcher adapter

**Files:** Create `task_tower/executor_queue.py`, `task_tower/executor.py`, `tests/test_executor_queue.py`, `tests/test_executor_adapter.py`; modify `task_tower/__main__.py`.

**Interfaces:** `ExecutionQueue(path, *, checkouts=(), forbidden_paths=())`; methods `submit(request, profile_fingerprint) -> dict`, `lookup(delivery_id) -> dict|None`, `claim(owner_id, *, max_active=2) -> dict|None`, `record(run_id, owner_id, state, evidence) -> None`, `cancel(run_id) -> None`, `status(run_id) -> dict`, `recover() -> list`. `executor.main(argv=None) -> int` supplies adapter/work/status/cancel subcommands; work implementation arrives in Task 4. Adapter preserves exact six-key dispatcher input and accepted/not_found/unknown output. Adapter/work require `--connections PATH --config PATH --queue PATH`; adapter additionally requires `--request PATH --result PATH`, work uses `--once`. Status/cancel require `--connections PATH --queue PATH --run-id UUID` and no config. Load existing connections for every command; adapter/work call `load_executor_config(path, connections)` and reuse connected trusted publishers for dependency verification. Preserve the current config/profile schema without a new connections-path key. Status/cancel validate private paths and connected stored repository/run identity without requiring live profile/pin validation, so policy revocation cannot disable cancellation. Cancellation only records a request for the current owner. Recheck unchanged connection/config authority before admission/preparation/launch.

- [ ] Write RED tests for required connections CLI contract, missing/invalid connections fail closed, status/cancel remain usable after execution-profile revocation, private queue/connection alias rejection, exact six-key identity/schema, duplicate UUID same receipt, identity collision rejection, durable admission before response, lost response lookup, competing claims with one winner, fixed max-active guard (default two, unknown ownership consumes capacity), recovery excludes claims and never fences a positively live owner, cancelled queued job never claimed, owner mismatch rejected and restart claimed/running -> fenced unknown without requeue. Inject crashes before/after transaction commits.
- [ ] Run `python -m unittest tests.test_executor_queue tests.test_executor_adapter -v`; confirm failures.
- [ ] Implement versioned validated SQLite schema using bounded `BEGIN IMMEDIATE` transactions and private-path protections. Persist UUID identities and claim/attempt intent before effects. Implement adapter atomic result writing and CLI routing; return only definitive absence as not_found.
- [ ] Rerun focused tests; require PASS. Obtain independent review, then commit `feat: bridge dispatcher deliveries to durable execution queue`.

### Task 3: Cancellable bounded process execution

**Files:** Modify `task_tower/processes.py`; create `tests/test_executor_processes.py`; preserve `task_tower/windows_job.py` unless a demonstrated compatibility failure requires a separately reviewed fix.

**Interfaces:** Extend `run_command(argv, cwd, timeout_seconds, env=None, *, cancel_requested=None, capture=None)`; `cancel_requested` is a zero-argument bool predicate, `capture` is a validated private directory plus per-stream byte cap. Defaults preserve existing callers/results. Optional results add cancellation/cleanup proof, private capture hashes/byte counts/truncation, never raw output.

- [ ] Write RED tests for cancellation before launch, cancellation while running within 250 ms polling plus cleanup bound, timeout with descendants, normal parent exit with descendant cleanup, log overflow truncation/hash/count, cleanup failure refusing success and old positional callers retaining their contract. Real helper subprocesses must establish cleanup, not only mocks.
- [ ] Run `python -m unittest tests.test_executor_processes -v`; confirm failures for new behavior.
- [ ] Implement bounded polling and output capture while retaining POSIX process-group cleanup, Windows Job close and five-second termination wait. Drain output without unbounded memory/disk growth; preserve digest/count for complete streams where available and label any unobserved tail honestly. Predicate errors fence execution, never produce success.
- [ ] Run focused process tests plus existing process/worker tests; require PASS on the current platform and CI coverage on Windows/POSIX. Obtain independent review, then commit `feat: support bounded cancellable executor processes`.

### Task 4: Worktree worker, Codex/custom harness and result validation

**Files:** Create `task_tower/executor_worker.py`, `task_tower/executor_harness.py`, `tests/test_executor_worker.py`, `tests/test_executor_harness.py`; complete `task_tower/executor.py`.

**Interfaces:** `execute_one(config, queue, *, owner_id=None) -> dict` claims/prepares/runs/validates one job. `prepare_attempt(job, profile) -> dict` records verified source SHA, branch/worktree and pinned provenance. `build_invocation(attempt, profile) -> list[str]` returns argument arrays. `validate_result(path, attempt, max_bytes) -> dict` enforces version/run/attempt/source binding and strict completed/failed/needs_input schema. `capabilities(profile) -> dict` distinguishes configured/probed/verified with evidence; resume remains unsupported.

- [ ] Write RED tests: isolated worktree exact source, dirty/reused/aliased paths rejected, intent-before-worktree/launch, revoked profile blocked, changed/closed Issue or lost dependency evidence before preparation/launch blocked, approved checkout/ref alone determines source SHA, Issue data cannot change argv/policy, inherited tokens stripped, missing/drifted Superpowers blocked, Codex flags exact and `--full-auto` absent, optional saved approve-for-me only, no selected model, custom trust/result files, invalid JSON/UTF-8/extra fields/oversize/symlink/wrong IDs/SHA rejected, zero-exit without result failed, cleanup uncertainty unknown. Cover cancellation/worker crashes at each effect boundary; never auto-reexecute unknown or started attempts.
- [ ] Write RED tests for explicit retry only with durable proof no child was created and attempts below profile bound. An unknown push/external result fences the run; no model publication/push or publisher is implemented. Capability help alone cannot mark execution/events/resume verified.
- [ ] Run `python -m unittest tests.test_executor_worker tests.test_executor_harness -v`; confirm failures.
- [ ] Implement interfaces using Tasks 1–3. Revalidate current authority/Issue/dependencies before preparation and launch using existing verified-done behavior. Supply pinned instructions and schema through private artifacts, preserve worktree evidence and bind final status to successful exit, local validation and cleanup. Add status/cancel/work CLI paths with fixed public reason codes. Do not implement stage transitions or PR publication.
- [ ] Rerun focused tests; obtain independent task review, then commit `feat: execute isolated noninteractive development attempts`.

### Task 5: End-to-end evidence and honest documentation

**Files:** Create `tests/test_executor_integration.py`, `docs/executor.md`; coordinator updates `README.md`, `AGENTS.md`, `docs/roadmap.md`, `docs/dispatcher.md` and task evidence after reconciling parallel docs.

**Interfaces:** Existing dispatcher `run_backend` -> executor adapter -> durable queue -> one worker -> run-bound structured result. This is a foreground queue consumer, not a stage controller or persistent pool.

- [ ] Write RED integration test using a real short trusted executable and a temporary Git repository. Assert repeated delivery admitted once, queued acknowledgement distinct from completion, isolated file change, private bounded logs, token removal, exact source/result hashes, restart fencing and cancel path.
- [ ] Run `python -m unittest tests.test_executor_integration -v`, implement only integration gaps, rerun to PASS.
- [ ] Run a bounded installed Codex smoke under explicit saved policy if authentication/capability is available. Record installed version, exact safe flags, source/result binding, output hashes and actual outcome. If unavailable, report blocked/unverified Codex capability and preserve custom verified evidence; never substitute help output or a fake for Codex success.
- [ ] Document profile/setup, exact adapter configuration, queue/work/status/cancel, pinning, retry/reconciliation, trust/auth boundary, platform cleanup limits and unimplemented #16–19 capabilities. Verify authenticated real #14 evidence without changing `verified_done`.
- [ ] Run `python -m unittest discover -s tests -v`; require complete PASS. Run current required CI and independent whole-diff review. Commit reviewed integration/docs/evidence.
- [ ] Coordinator obtains fresh PR acceptor verdict bound to actual head/base under `task-tower/pr-acceptance`, successful current checks and mergeability. Merge with expected head only after prior main acceptance. Verify exact-main CI, independent postmerge acceptance and automatic Issue closure; update Project/books and take next authorized ready Issue.

## Self-review

Every spec section maps to Tasks 1–5. Review-focus fault cases have named owning tests. Interfaces are shared without a second executor/process abstraction. Execution waits for independent spec acceptance, not a repeated user authorization. No test fixture or manual active-chat orchestration is evidence of unattended execution.
