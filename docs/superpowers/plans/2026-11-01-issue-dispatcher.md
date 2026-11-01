# Issue Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver explicitly authorized ready GitHub Issue identities once per local installation to a trusted custom harness.

**Architecture:** Separate fresh GitHub snapshot/selection from SQLite delivery state and trusted subprocess protocol. CLI composes them without GitHub writes or a development executor. A committed unknown intent permanently forbids a second submit.

**Tech Stack:** Python 3.11+ standard library, SQLite, unittest, existing GitHubTasks/GitHubSource/project connections.

**Spec:** `docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md`

## Global Constraints

- Python 3.11+ standard library only.
- No Issue field supplies executable paths, arguments, environment, shell fragments, working directories, or adapter configuration.
- Dispatcher never changes GitHub Issues, comments, Projects or labels.
- Existing rows never become eligible for submit again.
- No enabled allowlist or no backend means no execution, with visible disabled reasons.
- Canonical text hashes use `sha256-utf8-lf-v1`.

## Review Focus

- Case aliases and bool Issue numbers cannot bypass repository/Issue authorization (Task 1).
- Incomplete pagination and cross-project dependencies fail closed without starving independent projects (Task 1).
- Crash after reservation before launch and concurrent processes preserve one submit attempt (Task 2).
- Changed backend, oversized/duplicate-key result and cleanup failure retain unknown delivery (Task 2).
- Missing read-only journal and symlink/temp-path behavior do not mutate disk or break platform CI (Task 3).

## File responsibilities and stable interfaces

- Create `task_tower/dispatch_selection.py`: private config validation plus immutable per-tick snapshot/selection. Export `load_dispatch_config(path: Path, connections: list) -> dict`, `collect_snapshot(connections: list, *, store_factory, source_factory) -> dict`, `select_ready(snapshot: dict, allowlist: list, *, verify_done) -> dict`. Snapshot maps normalized repository to connection/store/source/issues/index/error; selection returns `ready`, `excluded`, `projects`. Ready rows contain only repository, issue, task_id, runner_label, priority. `verify_done(connection, store, source, issue)` is injected production verified_done.
- Create `task_tower/dispatch_delivery.py`: export `DeliveryJournal(path: Path, *, readonly: bool = False)`, methods `rows() -> list[dict]`, `reserve(candidate: dict, backend_fingerprint: str) -> tuple[dict, bool]`, `accept(delivery_id: str, receipt_id: str) -> None`, `lookup_rows(limit: int = 8) -> list[dict]` (durable round-robin cursor advanced before each lookup invocation); `backend_fingerprint(backend: dict) -> str`; `run_backend(backend: dict, request: dict) -> dict`; `deliver(candidate: dict, backend: dict, journal: DeliveryJournal, *, invoke=run_backend) -> dict`. Result is sanitized state/reason/identity only. Read-only journal construction never creates schema/path. Existing row returns winner=False.
- Create `task_tower/dispatcher.py`: `tick(connections: list, config: dict, journal_path: Path, *, dry_run: bool = False, store_factory, source_factory, invoke) -> dict`; `main(argv=None) -> int`. Production defaults use existing clients and verified_done. Tick report contains projects, selection and deliveries plus operational failure flag.
- Modify `task_tower/__main__.py` only for dispatcher subcommand forwarding. Reuse `task_tower/processes.py` run_command unchanged; do not modify it or windows_job.py. Use managed request/result files and trusted argv templates as in ReviewRunner.
- Create focused `tests/test_dispatch_selection.py`, `tests/test_dispatch_delivery.py`, `tests/test_dispatcher.py`. Modify README/AGENTS/roadmap and task evidence only in integration task.

### Task 1: Fresh snapshot, authorization and dependency selection

**Interfaces:** Produces dispatch_selection exports above; consumes existing connections, GitHubTasks.metadata, issue_lifecycle and verified_done signature. No delivery/journal import.

- [ ] Write failing unittest cases: empty allowlist/backend disables with exit 0 and no GitHub/backend calls even if source factories would fail; strict config rejects duplicates, bool Issue, unknown repo/keys and conflicting aliases; open/autonomous/task exact allowlist passes while closed/idea/blocked/malformed fails; missing priority is P3; invalid priority fails; sorted P0..P3/repo/Issue output is stable under shuffled input.
- [ ] Add dependency tests: canonical qualified-string references (`owner/repository#N`, matching current backlog); local legacy IDs; both forms equal versus inconsistent; duplicate/self/unknown/ambiguous refs; connected cross-repo proof; closed-only false; stale receipt false; verified_done fresh each tick; incomplete source blocks affected consumers while another project remains ready. Assert lifecycle running/needs_input excludes stale open body.
- [ ] Run `python -m unittest discover -s tests -p test_dispatch_selection.py -v`; confirm failures exercise missing behavior.
- [ ] Implement strict private config and snapshot/selection functions. Distinguish source/listing identity failures (project unavailable) from valid Issue identity with malformed metadata (individual exclusion). Capture only fixed diagnostic codes; use complete indexes, per-tick proof caching and effective lifecycle open check. Match exact schema/limits in spec.
- [ ] Run the targeted tests until passing. Independent reviewer checks actual selector diff and spec coverage before stage acceptance; record evidence and commit the reviewed unit.

### Task 2: Atomic intent journal and bounded backend protocol

**Interfaces:** Consumes candidate rows from Task 1; produces dispatch_delivery exports. No selection/source calls; backend receives six-key protocol only.

- [ ] Write failing tests for committed unknown before invocation, one submit for repeated tick/restart, accepted never invokes again, lookup accepted recovery, not_found/unknown never resubmits, changed task/backend invokes neither, stale negative lookup cannot downgrade accepted.
- [ ] Add SQLite failure/corruption/schema/unsafe-path tests and a multiprocessing race on one canonical TemporaryDirectory journal; assert exactly one reserve winner/submit invocation. Simulate crash between reserve and process start; restart performs lookup only.
- [ ] Add trusted Python adapter fixtures asserting shell=False/managed request JSON/cwd and trusted request/result/checkout template substitution and testing accepted receipt, lookup-only not_found, mismatched ID, duplicate keys, bool version, extra/trailing JSON, invalid UTF-8, >64 KiB result and linked/nonregular result paths, nonzero exit, launch failure, timeout and cleanup failure. Assert no raw output/config secrets in reports or rows; receipt tokens use the ASCII allowlist and are not echoed. Cover config/connections/journal/sidecar case and hard-link aliases, checkout containment and pre-open path checks.
- [ ] Run `python -m unittest discover -s tests -p test_dispatch_delivery.py -v`; confirm meaningful failures.
- [ ] Implement journal with unique repository/Issue primary key, BEGIN IMMEDIATE insert, unknown durable commit, UUID and fingerprint; no retry/reclaim/reset. Implement read-only access and monotonic accepted update. Implement bounded file protocol over unchanged run_command lifecycle; reject unsupported placeholders and keep stdout/stderr out of the protocol.
- [ ] Run targeted delivery and affected process tests until passing. Independent reviewer checks concurrency/crash/protocol diff before stage acceptance; record evidence and commit reviewed unit.

### Task 3: CLI, loop, dry-run and integration documentation

**Interfaces:** Consumes Task 1/2 exports; produces dispatcher tick/main and CLI forwarding. Inject client factories/invoke/sleep to test without live GitHub or wall-clock waits.

- [ ] Write failing CLI tests for --once, default foreground polling and interrupt, interval 5/3600 bounds, --status no GitHub/backend/write, missing journal read-only empty state, --dry-run no directories/SQLite/backend/GitHub mutations, invalid flag combinations, exit 0/1/2, disabled config and per-project operational error isolation. Snapshot journal/config bytes and directory inventory before/after dry-run.
- [ ] Run `python -m unittest discover -s tests -p test_dispatcher.py -v`; confirm failures.
- [ ] Implement tick composition and CLI. Enforce separate fixed budgets of 8 submits and 8 lookups per tick; test new-submit progression, durable lookup fairness across restarts and deferred non-error reporting. Before reserve/send refetch Issue/lifecycle and revalidate authorization/metadata/dependencies with fresh per-send proofs; test changed metadata prevents send and document the remaining non-atomic race. Reserve only revalidated ready rows; reconcile existing unknown rows by lookup even when no longer ready only when original private allowlist/task identity/backend still match (otherwise needs_input); accepted rows remain untouched. Do not allow allowlist removal, unavailable/malformed source, identity mismatch or unsafe configuration to trigger any adapter call. Stop loop on global config/journal integrity failure; keep per-project failures visible and continue other projects.
- [ ] Document private config/adapter examples, installation journal preservation, command/exit semantics and capability limits. Update README, AGENTS and roadmap (#24 done, #14 current, #15 next). Keep continuous authorized chat work distinct from foreground polling and planned executor/daemon orchestration.
- [ ] Run `python -m unittest discover -s tests -v`; require complete success. Run CLI help and hermetic dry-run/status smoke tests with canonical temp paths on supported CI platforms. Confirm processes.py/windows_job.py remain unchanged and existing lifecycle regression tests pass.
- [ ] Record independent specification/development/test evidence; source manifest excludes mutable task/evidence self-reference and canonicalizes UTF-8 LF. Fresh whole-diff reviewer verifies security boundaries and all acceptance criteria. Commit implementation/docs/evidence only after relevant gates.

### Integration handoff

- [ ] Reconcile GitHub/Project status without claiming completion early. Require current CI successful and fresh independent whole-PR verdict bound to exact head AND base in task-tower/pr-acceptance; re-review after either SHA changes.
- [ ] Verify mergeability/no unresolved blocking findings; merge with expected head SHA under authorized policy. Serialize repository merges.
- [ ] Verify exact main commit, successful postmerge CI, independent exact-main postmerge acceptance and automatic #14 closure. Only then update completion evidence and begin next eligible authorized #15 work; never infer a shipped development daemon from this dispatcher.
