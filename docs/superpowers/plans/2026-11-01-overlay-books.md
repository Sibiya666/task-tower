# Overlay Books Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show truthful, source-linked Ideas, Tasks hierarchy and versioned Project library inside the existing Windows overlay.

**Architecture:** Extend the shared Python books projection and serve a bounded private native-helper snapshot. A pure JavaScript policy builds filtered, paginated hierarchy; a separate view handles modal UI without changing session activity or collector payloads. Native host alone refreshes and opens validated configured GitHub sources.

**Tech Stack:** Python 3.11+ standard library; existing HTML/CSS/JavaScript and Node tests; WPF/.NET Composition WebView2; Windows PowerShell 5.1; existing Edge/Playwright test runtime.

**Spec:** `docs/superpowers/specs/2026-11-01-overlay-books-design.md`

## Global Constraints

- Canonical UI is `overlay/`; no second root overlay. Use `task_tower.books.aggregate` as the shared projection source for CLI and overlay.
- Three books: Ideas, Tasks, Project library. Display at most three record cards per page, including expanded feature children; group headings and navigation are not record cards. Detail view displays one selected record.
- No new framework, package installation, credential scope or implicit project discovery.
- No credential/configuration/checkout-path/raw-transport serialization; no WebView network or HTML execution; no executor/dispatcher/collector contract changes.
- Existing independent `verified_done` alone establishes accepted task progress; declared artifact state and closed Issues never do.
- Snapshot 8 MiB UTF-8 / 10,000 entries; stream 64 MiB / 32 newline-delimited frames; optional manifest 256 KiB / 1000 rows; refresh single-flight 120 s cap; stale after 300 s or immediately after failed refresh.
- Publish known Issue identity projections and library data before expensive fresh completion proofs. A slow verifier must not prevent already fetched records rendering; no prior-refresh proof reuse.
- Body projection 32 KiB UTF-8; phase/blocker labels 256 characters; blockers/results/history 100 entries with visible limit indicators.
- Preserve PowerShell 5.1 compatibility; scripts containing Cyrillic require UTF-8 BOM; Python runtime already supplied by launcher.
- Independent spec/plan acceptance before implementation; routine choices use existing delegated authorization, not another human prompt.

## Review Focus

- Ordinary unmanaged Issues and unrelated private projects must retain identities and hierarchy without requiring capture metadata; Task 1/3 tests.
- Partial trees, unavailable native relationships and refresh timeouts must never appear complete/fresh; Task 1/2/3 tests.
- Multi-stage parent/child graphs including cycles and filtered-away parents must retain each task once; Task 3 tests.
- Host URL spoofing, Unicode/space paths, shell metacharacters and unknown session URLs must not launch arbitrary targets or leak configuration; Task 2/4 tests.
- Narrow native room windows and Escape/Tab/context interactions must preserve focus, placement, transparent background and actual session state; Task 4/5 tests.

---

## Ownership and sequence

Task 1 owns Python shared projection/library files. Task 3 owns pure policy files and may run independently after this plan is accepted; it consumes the fixed envelope below using fixtures. Task 2 depends on Task 1 and owns helper/native bridge security. Task 4 depends on Tasks 2/3, owns UI and reconciles native refresh/focus integration serially. Task 5 is coordinator integration/evidence. Do not assign concurrent mutations to `TowerHost.cs`, `world-view.js`, `index.html` or launcher files. A separate fresh reviewer accepts each completed task; coordinator runs full integration. No commits/pushes by document author; implementing roles follow coordinator commit gates.

## Common interface

`BooksEnvelope = {kind:'books', version:1, sequence:positive-int, final:boolean, state:'ready'|'partial'|'unavailable'|'unconfigured'|'loading', fetched_at:string|null, entries:Array<BookEntry>, errors:Array<{project:string,source:string,error:string}>, stale?:boolean}`. Issue entries preserve existing fields plus `repository:string`, `number:int`, `verification:'pending'|'verified'|'unverified'|'not_required'`, `description:string`, `phase:string|null`, `blockers:Array<string>`, `results:Array<string>`, `history:Array<object>`, `relationships:{parent:null|{id,source}|{status:'unavailable'},sub_issues:Array<{id,source}>|{status:'unavailable'},milestone:null|{id,number,title,source}|{status:'unavailable'}}`; field unavailability/limits are surfaced through fixed errors. Library entries add `repository`, `path`, `commit`, `artifact_state:'working'|'accepted'|'superseded'|'unknown'`, `declaration_source:string|null`, `issues:Array<string>`, `milestone:null|{repository,number}`, `available:boolean`; IDs are `repository:path@commit`. Errors are public fixed diagnostics, never raw values/exceptions. Stream sequence is scoped to one native attempt; native loading/error envelopes may retain last sequence, and attempt identity is held natively rather than accepted from WebView.

### Task 1: Shared public projections and explicit library versions

**Files:**
- Modify: `task_tower/books.py`, `task_tower/github_tasks.py`
- Create: `task_tower/book_projection.py`, `task_tower/book_library.py`
- Test: `tests/test_book_projection.py`, `tests/test_book_library.py` (retain existing books tests wherever present).

**Interfaces:**
- Consumes existing `GitHubTasks.list_issues/library/request`, `capture.relationship_projection(connection,store,issue)`, `issue_lifecycle(store,issue)` and `verified_done` unchanged.
- Produces `project_issue(connection, store, issue, metadata) -> (dict, list[dict])` in `book_projection.py`, additive public fields only; `project_library(connection, store) -> (list[dict], list[dict])` in `book_library.py`; `aggregate(connections, store_factory=GitHubTasks, include_library=False, *, on_update=None)` returns its backward compatible final report and calls optional `on_update(report:dict) -> None` with independent public snapshots. Aggregate ordering is all available project Issue identity listings with immediate callback per project, then library pass, then detail/native/lifecycle pass, then fresh completion-verifier pass. No expensive enrichment/proof before known identities are published. Verification pending prevents done; only unchanged current-attempt verifier true sets verified/done. Existing CLI has no callback and retains its synchronous final-result semantics.
- `GitHubTasks.library()` stays callable by existing consumers, adding immutable repository/path/commit fields. Add `library_index(commit: str) -> dict|None` and `markdown_exists(commit: str, path: str) -> bool`; fetch through existing bounded authenticated transport; missing index only returns None on known 404.

- [ ] **Step 1: Write failing projection/library tests.** Assert unmanaged ordinary Issue gets native relationships; two repos with Issue 1 stay distinct; phase/blocker/results/history allowlists exclude token/config/private path/unknown metadata keys; missing and unavailable differ; malicious body is inert text; limits emit error; lifecycle unavailable retains Issue identity; closed Issue and accepted manifest cannot make status done. Use synchronization barriers around a fake slow unchanged verifier: callbacks must have published all fetched Issue identities and library before verifier enters; while blocked, status is never done and verification is pending. Release true to assert subsequent verified/done update; false/error remains unverified; prior snapshot done is never proof input. Assert callback snapshots are independent and CLI no-callback final behavior preserved. Manifest fixtures assert current/old commit versions, one current version per identity, unknown unindexed MD, missing index normal, invalid/oversized/conflicting index visible while tree survives, declared missing blob unavailable, explicit connected associations only, no title-derived links.
- [ ] **Step 2: Run** `python -m unittest tests.test_book_projection tests.test_book_library -v`; expect failures due missing projection interfaces or old minimal fields, not fixture import errors.
- [ ] **Step 3: Implement** interfaces above with exact spec manifest schema, path validation and bounded allowlisted public projection. Reuse existing lifecycle/native relationships and verified completion; isolate per-Issue/detail failures. Preserve existing flat HTML and CLI compatibility. Restrict artifact association targets using passed explicit connections, not transport discovery; `project_library` accepts optional `connected_repositories: set[str]|None` keyword, supplied by aggregate from its already materialized connections list; None means selected repository only.
- [ ] **Step 4: Run** the two modules and existing books/capture/GitHubTasks tests discovered with `rg --files tests`; expect pass and no changed completion semantics. Independently review resulting public JSON fixtures for absence of private fields.
- [ ] **Step 5: Record reviewable task evidence**, changed-file list and test output for fresh Task 1 reviewer; coordinator may commit only after acceptance.

### Task 2: Bounded native snapshot and source-launch boundary

**Files:**
- Create: `task_tower/overlay_books.py`, `tests/test_overlay_books.py`, `overlay/BooksBridge.cs`
- Modify: `overlay/TowerHost.cs`, `overlay/run-html-overlay.ps1`
- Test: `overlay/test-books-host.cjs` (source-contract tests supplement, never replace actual native smoke).

**Interfaces:**
- Consumes Task 1 aggregate and Common interface; trusted `TASK_TOWER_CONNECTIONS` host environment only.
- Produces Python `snapshot(config_path: Path|None, *, on_update=None) -> dict`, `main(argv=None) -> int`; fixed invocation `python -m task_tower.overlay_books`, no arguments sourced from WebView. `main` supplies aggregate callback and emits/flushed newline-delimited complete envelope frames immediately; never waits for proof/process completion to publish first identities. Exit 0 for ready/unconfigured, 1 for partial/unavailable. First callback cannot be coalesced away; intermediate callbacks may be coalesced with capacity reserved for final. Per-frame 8 MiB / whole-stream 64 MiB / 32 frames enforced on both ends; UTF-8 and sequence/final schema validated.
- `BooksBridge` owns immutable configured source allowlist, `IsAllowedSource(string url) -> bool`, and `QuoteArgument(string value) -> string` for .NET Framework ProcessStartInfo.Arguments. Native host `RefreshBooksAsync() -> Task` sends books envelope and `OpenBookSource(string url) -> bool` performs validated browser launch. Read private config natively only to build minimum repo/Project allowlist; do not send paths or config into WebView.
- Host messages exactly `{action:'books-refresh'}` or `{action:'books-open-source',url:string}`; reject extras/oversize (16 KiB), wrong source document and invalid URI. Existing actions keep their exact behavior.

- [ ] **Step 1: Write failing helper/host tests.** Missing config is unconfigured without transport; valid partial aggregate preserves data/error; 8 MiB/10k and cumulative 64 MiB/32 frame caps fail visibly; malformed/invalid UTF-8/decreasing-sequence/after-final stream rejected; credentials/checkout never leave helper. Controlled helper flushes identity and library frames then blocks on proof: native must display those before exit, timeout retains latest partial as interrupted/stale and pending (not done), last-success timestamp unchanged; previous-refresh accepted status invalidated immediately. A later successful proof frame updates only within current live attempt. C# native harness cases cover exact configured repo issues/pull/milestone/immutable MD and exact Project; reject lookalike host, userinfo, nondefault port, queries/fragments, encoded traversal/slash, external repo/session URL, nonimmutable blob, control/backslash and unknown action keys. Quote Windows executable/config paths containing spaces, Unicode, quotes and trailing backslashes without invoking a shell.
- [ ] **Step 2: Run** `python -m unittest tests.test_overlay_books -v` and `node --test overlay/test-books-host.cjs`; expect missing interfaces/old native action behavior failure.
- [ ] **Step 3: Implement** helper and bridge. Host reuses configured Python with fixed module arguments and canonical repo working directory; compile BooksBridge.cs in existing launcher Add-Type assembly. Asynchronously bounded-read each stdout line and forward validated current-attempt frames immediately; process exit is not a prerequisite. Discard/fence invalid output, enforce cumulative limits, own helper termination/reaping, 120s deadline and attempt identity, close cleanup, one in flight. Timeout/missing final frame retains latest valid partial interrupted/stale with pending proof; no last-success update. New refresh clears old proof claims; no cross-attempt verifier cache. Avoid logging raw stderr/JSON. Do not weaken CSP/navigation/new-window blocking; validate trusted source document before actions. Reuse existing source snapshot timer independently.
- [ ] **Step 4: Run** helper tests and native bridge harness; deliberately hang helper fixture to confirm timeout keeps UI responsive, no new freshness and late result discarded. Confirm no helper launched on second refresh while active; host close reaps own helper. Native source-launch tests use injected recording opener so malicious URLs never launch real browsers.
- [ ] **Step 5: Record bounded/error-path evidence** for fresh reviewer and coordinator commit gate.

### Task 3: Pure hierarchy, filters and pagination policy

**Files:** Create `overlay/web/books-policy.js`, `overlay/test-books-policy.cjs`.

**Interfaces:**
- Consumes Common interface with no DOM/native dependencies; export UMD `window.BooksPolicy` / `module.exports`.
- Produces `normalizeEnvelope(value, nowMs) -> BooksEnvelope`, `buildRows(entries, {book,project,status,grouping,expanded}) -> Array<{kind:'group'|'record'|'reference'|'warning',id,...}>`, `pageRows(rows, page, pageSize=3) -> {rows,page,pages,total}`, `isStale(envelope, nowMs) -> bool`. `pageRows` rejects pageSize outside 1..3; only record rows consume quota, references/warnings belong to their record. `buildRows` groups headings without incrementing record count, deduplicates canonical identity before flattening and marks relationship errors.

- [ ] **Step 1: Write failing Node tests.** Assert stage-vs-parent independence, parent spanning milestones one identity, unassigned and unknown milestone buckets, filtered-away parent source reference, cycles/self-links warning/once-only emission, unavailable children unknown count, accepted != closed counts, repository collisions, completed inclusion and same-Issue promotion. Four visible expanded records across multiple groups produce pages of 3 and 1. Source age 299s fresh/300s stale, failed refresh stale, empty filtered results page 0/1, negative/out-of-range page clamped, invalid source data rejected or visibly unavailable.
- [ ] **Step 2: Run** `node --test overlay/test-books-policy.cjs`; expect module missing or policy assertion failure.
- [ ] **Step 3: Implement** policy with stable qualified/numeric ordering and ancestor-cycle guard. Return data-only descriptors; DOM/view decides presentation. Keep immutable artifact identity/state independent from Issue completion.
- [ ] **Step 4: Run** policy suite; expect pass. Fresh reviewer compares fixture expectations against spec rather than only implementation.
- [ ] **Step 5: Submit task evidence**; no touching host/UI files while Task 2 runs.

### Task 4: Overlay modal, safe details and accessible interaction

**Files:**
- Create: `overlay/web/books-view.js`, `overlay/web/books.css`, `overlay/test-books-browser.cjs`
- Modify: `overlay/web/index.html`, `overlay/web/world-view.js`, `overlay/web/tower.js` only for focus/drag exclusions if required, `overlay/TowerHost.cs` only serialized integration fixes.

**Interfaces:**
- Consumes BooksPolicy, host envelope/actions. Exposes `window.BooksView = {open(projectId=null),close(),acceptSnapshot(value)}`. Only explicit connected project IDs select project; otherwise all. View listens to book messages and ignores collector snapshots, while Tower's existing handler ignores books envelopes.
- BooksView owns dialog focus, filters, expansion/page and selected immutable record ID; native placement/saved overview bounds remain untouched. World menu invokes `BooksView.open()` globally and scoped only using explicit trusted mapping if present; no speculative name mapping.

- [ ] **Step 1: Write failing real Edge browser tests.** Stub native bridge in browser and push synthetic public envelope. Context menu/Ctrl+B open; ContextMenu/Shift+F10 entry works; all book/project/status filters and both Tasks groupings work; max three cards including children; details show explicit missing/unavailable/blocked/result/lifecycle and artifact version states. Tab/Shift+Tab trap and Escape details/dialog restore invocation focus; background dragging/floor selection suppressed. At 340×300 every action remains reachable through scrolling; Unicode long strings wrap. Malicious HTML displayed text, unknown links inert, allowed source click emits fixed native action only. Progressive identity/library frames render before final proof, pending proof stays visibly unknown, timeout keeps latest partial stale, and a new refresh invalidates old accepted proof display. Snapshot refresh success/failure preserves selection/page appropriately and stale indicator. Assert tower agent/activity state and transparent body unchanged, no page errors/CSP errors.
- [ ] **Step 2: Run** `node --test overlay/test-books-browser.cjs`; expect missing dialog/actions failure.
- [ ] **Step 3: Implement** DOM via createElement/textContent with local scripts/styles loaded from index under unchanged CSP. Avoid innerHTML for external data. Render groups/cards/details with native controls, explicit declared artifact state, closed-vs-accepted progress and retained completion history. Use no permanent titlebar controls; suppress world context menu inside modal and restore focus on close. First open requests data; later opens reuse timestamped data until explicit refresh.
- [ ] **Step 4: Run** books policy/browser/host tests and existing `test-world-browser.cjs`, `test-presence-browser.cjs`, `test-scene-position.cjs`; expect pass. Inspect browser screenshots at narrow and overview viewports for clipping/readability and unchanged transparency.
- [ ] **Step 5: Record integration evidence** for fresh reviewer; coordinate any TowerHost changes serially with Task 2 owner.

### Task 5: Actual Windows evidence and repository integration

**Files:**
- Modify: `overlay/TowerHost.cs` smoke assertions only if needed, `overlay/README.md`, `docs/github-books.md`, root `README.md`, `AGENTS.md`, `docs/roadmap.md` through coordinator ownership.
- Create: `docs/evidence/2026-11-01-overlay-books.md`, focused raw screenshots under `docs/screenshots/`.

**Interfaces:** Consumes accepted Tasks 1–4; produces exact-revision commands/results, native/browser visual artifacts and truthful shipped/planned documentation. Does not publish fixture completion receipts or manually close Issue.

- [ ] **Step 1: Extend native smoke scenario** with deterministic local public fixture injection separate from genuine GitHub refresh. Verify Books opens/closes through real composition WebView2, keyboard focus/Escape/context handling, pin/close functioning, invalid source action rejection, native helper unavailable/partial state, transparent background, existing monitor clamp/overview restoration. Keep fixture injection smoke-only, never substitute it for real source evidence.
- [ ] **Step 2: Run complete checks** from repo: `python -m unittest discover -s tests -v`; from overlay: `python -m unittest -v`; then `node --test test-web.cjs test-room-skins.cjs test-presence.cjs test-presence-browser.cjs test-scene-position.cjs test-session-light.cjs test-tower-arrivals.cjs test-world-policy.cjs test-world-browser.cjs test-visual-audit.cjs test-books-policy.cjs test-books-host.cjs test-books-browser.cjs`. Expect all pass. Use provided cached Python/Node runtimes if PATH differs; record exact versions/paths, no installs.
- [ ] **Step 3: Run actual native** `powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay.ps1 -SmokeTest` from overlay; expect exit 0 and specific Books assertions in evidence, not only old smoke pass. Open real Windows overlay and exercise context entry, Ctrl+B, tab cycle and source details; record focused raw screenshot excluding unrelated/private content. Exercise explicit private-config real refresh and record sanitized source state/time; if access unavailable, preserve true unavailable state and note limitation instead of claiming live success.
- [ ] **Step 4: Update documentation** with entry/keyboard/setup variable, declared-artifact semantics, immutable versions, source allowlist, limits and no background polling; distinguish new overlay hierarchy from retained flat standalone HTML. Coordinator updates root status and source ownership notes with actual evidence only.
- [ ] **Step 5: Independent acceptance and integration.** Fresh reviewer reads whole actual diff, spec and evidence and reproduces key checks; fix/retest findings. Coordinator follows exact-head/base PR acceptance, all CI/mergeability gates, expected-head merge, independent exact-main postmerge and genuine automatic Issue closure. New main/head invalidates previous acceptance. Do not declare Done from merge or green CI alone.

## Plan self-review

All spec sections map to Tasks 1–5: projection/library and pre-proof reporting (1), bounded progressive refresh/security (2), hierarchy/paging (3), interaction/focus/minimality (4), actual native and integration (5). Review Focus cases each have owning tests. Shared envelope, identity and function names are fixed above; additive `on_update` callback and connected-repositories keyword preserve existing caller defaults. The real 137.64-second verifier finding is addressed by publishing base records before proofs within the unchanged 120-second cap, not by weakening proof or increasing an unbounded timeout. Concurrent work is limited to independent Python projection and pure JS policy; native/UI integrations are serialized. No requirement is deferred to a new credential scope, new framework or user choice.
