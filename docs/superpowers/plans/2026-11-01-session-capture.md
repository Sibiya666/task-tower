# Explicit session capture implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Capture explicit session ideas/tasks into canonical GitHub Issues and safely register legacy migrations.

**Architecture:** Add bounded envelope validation and a capture coordinator around existing Project-first preflight, CreationJournal and GitHubTasks. Add a private migration registry that retains legacy files unchanged; books expose provenance/relationships while #23 owns hierarchy rendering.

**Tech Stack:** Python 3.11+, standard library, unittest, existing GitHub transport and SQLite CreationJournal.

**Spec:** `docs/superpowers/specs/2026-11-01-session-capture-design.md` (draft; independent exact-source acceptance required before production edits).

## Global constraints

- Python 3.11+ standard library; no dependencies, hooks, permissions, executor or Codex database writes.
- GitHub is the editable task truth; preserve `GitHubTasks.import_card(path)`, legacy card bytes, loader/publisher and postmerge snapshot hashes.
- Explicit connection only; private project authority and verified readiness are separate from capture intent.
- UTF-8/LF evidence hashing; exclude mutable TaskCards from self-referential source manifests.
- Issue #15 owns execution; #23 owns hierarchical overlay rendering. Coordinate shared CLI/docs changes and serialize integration after fresh head/base acceptance.
- Read coordinator-owned `../task-tower-github/docs/development-process.md`; do not edit/copy it in this branch.

## Review focus

- Lost POST response/restart: retain committed intent and reconcile without a second creation.
- Same event with changed payload: conflict; identical text with separate IDs: independent captures.
- Legacy active-card edits and alias/CAS races: preserve bytes/evidence, report stale drift, never clobber.
- Parent versus milestone and cross-repo Issue numbers: retain distinct native relationships and qualified identities.
- Untrusted original/session/title values containing task metadata, lifecycle or queue comment delimiters: lossless typed encoding and escaped display; fences/JSON quoting alone do not prevent injection.
- Closed or forged-done Issue and requested execution: never infer acceptance or private authority.

## Task 1: Explicit capture, recovery, promotion and relationship projection

**Files:** Create `task_tower/capture.py`, `task_tower/capture_cli.py`, `tests/test_capture.py`, `tests/test_capture_cli.py`; modify `task_tower/creation_journal.py`, `task_tower/github_tasks.py`, `task_tower/books.py`, `task_tower/__main__.py`; add tests to existing journal/books suites only as needed.

**Interfaces:** `validate_capture(envelope: dict) -> dict`; `capture(connection, envelope: dict, *, store=None) -> dict`; `promote(connection, number: int, *, store=None) -> dict`; `capture_cli.run(argv: list[str]) -> int`. Store injection uses existing GitHubTasks request/list/get/update/metadata interfaces. Results carry canonical `issue_url`, operation status and recoverable source errors; no original input in errors. Add narrowly scoped CreationJournal payload-binding methods preserving existing reserve/reconcile behavior and old journal compatibility.

- [ ] Write failing unittest cases for 64 KiB envelope, 32 KiB original text, title 1–256, provider/id 128, URL 2048, strict UTF-8/types/unknown keys/NUL; exact text retained (CRLF, Unicode, literal metadata/lifecycle/queue delimiters in original text and session fields); malformed encoded provenance rejected; serialized body has exactly one intended metadata block and no injected authority/queue blocks; HTTPS-only no-userinfo links; explicit bounded file/stdin; aliases rejected before network.
- [ ] Write failing transport/journal tests: Project preflight before POST, one POST per event, two events with identical text, changed digest conflict, crash after reserve, lost response, ambiguous/deleted remote identity, board failure then repair, local concurrent retry. Assert committed intent exists inside mocked POST, no blind replay and no token/input leakage.
- [ ] Write failing promotion/books tests: same Issue identity, preserved prose/metadata and session provenance, native parent/sub-issue versus milestone, connected cross-repo `owner/repo#N`, unavailable relationships/source errors, collision across repositories, escaped links, forged done/closed stays unverified, execute_requested never grants readiness or authority. Simulate detected body drift and cross-process simultaneous promotions; assert no clobber, lost provenance or duplicate transitions. Document/use conditional mutation when supported; otherwise require serialized external editing and disclose the remaining final-check/PATCH race.
- [ ] Run focused failing suites with `python -m unittest discover -s tests -p 'test_capture*.py' -v`; confirm missing behavior fails for the intended reason.
- [ ] Implement envelope validation and coordinator; extend existing CreationJournal backward compatibly for durable payload binding before POST; reuse preflight, remote identity discovery and Project repair. Keep creation serialized per project and document cross-host limitation. Use a versioned typed marker-inert encoding for lossless provenance and escaped human display; never decode payloads into authority. Validate/retain native links, serialize local same-Issue promotions across processes, update same Issue on promotion, project structured relationships/provenance through books and safe existing links without a hierarchy renderer.
- [ ] Implement CLI submit/promote delegation with exact spec command shape; safe bounded inputs, sanitized failures and explicit connection scope. Do not register executor callbacks or alter dispatch authority.
- [ ] Run focused capture, journal, onboarding, books and GitHubTasks suites; capture commands and exit codes. Obtain fresh independent implementation/test acceptance against actual changed sources; resolve findings and rerun affected checks.
- [ ] Commit only accepted source/tests with `feat: add explicit session capture and promotion`; preserve unrelated changes.

## Task 2: Legacy migration registry, compatibility evidence and delivery

**Files:** Create `task_tower/capture_migration.py`, `tests/test_capture_migration.py`, `docs/session-capture.md`; modify `task_tower/capture_cli.py`, `task_tower/books.py`, `docs/github-books.md`; coordinator reconciles README/AGENTS/roadmap and shared CLI documentation only after actual capability checks.

**Interfaces:** `migrate_card(connection, path: Path, *, store=None) -> dict`; `migration_state(connection, path: Path) -> dict`. Registry is private provenance-only data keyed by repository/legacy identity/source path, with raw SHA-256 and canonical Issue URL. Consume compatible `GitHubTasks.import_card(path)` and Task 1's existing result/error convention. New migration command does not replace the old import command.

- [ ] Write failing tests: repeated migration yields one canonical Issue, source bytes unchanged, legacy evidence retained and unverified completion stale; active `tasks.load_task`, publisher and postmerge snapshot hashes still match. Reuse representative existing worker fixtures rather than weakening them.
- [ ] Write failing tests for changed source hash, conflicting same-ID cards, interrupted registry publication then retry, symlink/hardlink/config/journal aliases, descriptor replacement (including between validation and import_card reread), source mutation after remote creation, concurrent cross-process registry updates and CAS target drift; assert source/target untouched on failure and no duplicate POST. Verify old import callers and pre-existing journal files still work.
- [ ] Write failing books/CLI tests: canonical Issue appears once, registry is not editable task truth, drift is visible, migrate supports explicit connection only, structured parent/milestone/session links survive, secrets/private runtime state stay excluded.
- [ ] Run `python -m unittest discover -s tests -p 'test_capture_migration.py' -v` and confirm intended failures.
- [ ] Implement bounded immutable-source migration via existing import_card using a private immutable snapshot of validated bytes, retaining original source provenance and rechecking the original before import/publication; handle post-creation source drift as a recoverable conflict without replay. Implement a provenance-only registry with source hash checks and locked/CAS same-directory atomic publication. Preserve active cards; no archive/delete/rewrite or historical hash regeneration. Expose visible migration drift in books.
- [ ] Document envelope/examples, stable ID retry discipline, explicit custom harness API, Project-first setup, private state, recovery, legacy compatibility, authority/readiness separation and #23 renderer boundary. Never claim background execution or all-chat capture.
- [ ] Run full `python -m unittest discover -s tests -v` using `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` when system Python is unavailable; record runtime, exact source hashes, commands and exit codes. No overlay checks needed unless overlay changes are added (outside current scope).
- [ ] Obtain independent spec-to-diff and testing acceptance, then commit accepted migration/docs changes. Coordinator updates waiting branch after main changes and reruns checks; obtains fresh whole-diff PR acceptance bound to actual head/base, successful current CI and mergeability, and merges with expected head SHA.
- [ ] Coordinator verifies exact-main CI, independent postmerge acceptance and automatic #22 closure before completion. Publish evidence and refresh Project/books status, then select next eligible authorized Issue within the two-Issue limit. No merge or closure claim from this plan alone.

Self-review: both tasks map to all seven acceptance criteria; focused failure tests cover the five review risks. Implementation is gated on independent spec/plan acceptance, not this unchecked plan.

## Coordinator integration scope addendum (2026-11-01)

The coordinator may integrate `docs/development-process.md` from the parallel #15 branch and reconcile `README.md`, `AGENTS.md`, `docs/roadmap.md`, `docs/dispatcher.md`, `docs/github-books.md` and `docs/session-capture.md` to describe actual capture capability and the explicitly authorized two-Issue automatic-refill policy. The earlier external-process-reference restriction applies to implementers; this bounded coordinator publication is now included in the integration scope. No unattended executor/pool capability may be claimed.

Integration also includes only the small authenticated default-source correction in `task_tower/dispatcher.py` (`_source` resolves and forwards existing host authentication) and its regression test in `tests/test_dispatcher.py`, independently accepted in #15 Task 1. This backport does not ship #15's executor, grant scopes/permissions, change capture APIs or weaken verification. Final independent development/test and exact-head/base review must inspect the entire actual integration diff, including these files; this addendum accepts scope, not implementation or test results. Serialized main acceptance and Issue closure gates remain required.
