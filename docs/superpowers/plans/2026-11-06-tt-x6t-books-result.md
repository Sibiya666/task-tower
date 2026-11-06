# Public Beads result implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, with separate independent TEST/review contexts. Do not implement before design/plan approval.

**Goal:** Show one strictly typed source result in real Books for tt-x6t.

**Architecture:** Parse only the bounded explicit notes block. Project exact typed
data through Python, C# and browser boundaries. Derive two existing supported
GitHub source links without accepting URLs or prose in the block.

**Tech stack:** Existing Python 3.11 standard library, C# BooksBridge, vanilla JS.

**Spec:** [Design](../specs/2026-11-06-tt-x6t-books-result-design.md).

## Constraints and review focus

- Preserve task ownership/history/source-state and mixed-source progressive/stale behavior.
- No arbitrary input strings/URLs, unknown nested keys, raw notes/errors or private paths.
- Missing/malformed/oversize blocks remain visible missing/unavailable, without task loss.
- Public projection mismatch marks chronology partial; private-only notes do not.
- A recorded result must never increase accepted progress or alter verification.
- No local native harness/smoke/actual-app execution without precise separate permission.
- Full runtime CI and real protected PR/main acceptance; Books observation before closure.

### 1. Bounded adapter and public envelope

Files: task_tower/beads_books.py, task_tower/overlay_books.py;
tests/test_beads_books.py, tests/test_overlay_books.py.

Interface: `project_result(notes) -> dict` with the exact missing/unavailable/recorded
schema; `validate_result(value) -> dict` validates public typed values without
copying unknown fields. Use shared validation in parser and Python envelope.

- [ ] Add tests for valid projection with surrounding private sentinel, missing,
  duplicated/unmatched LF/CRLF markers, duplicate/unknown keys, wrong types,
  unsafe integers, bad SHA, NaN/Infinity, multibyte byte boundary and surrogates.
- [ ] Run focused Python tests; observe failures due to missing behavior.
- [ ] Implement minimal parser/projection and enforce nested envelope validation
  only on Beads entries. All invalid parser input yields unavailable, no raw error.
- [ ] Add history tests: changed public result makes chronology partial and retains
  record; private-only change does not. Compare projections in current consistency.
- [ ] Run focused Python suite and confirm existing mixed-source cases pass.

### 2. Native/browser boundary and detail

Files: overlay/BooksBridge.cs, overlay/web/books-policy.js,
overlay/web/books-view.js, overlay/test-books-policy.cjs,
overlay/test-books-browser.cjs, overlay/test-books-host.cjs.

Interface: optional `result_evidence` on Beads entries only; old frames lacking it
render missing. Recorded requires exactly status/version/pr/main_sha; other states
require exactly status. Derived receipt URL uses validated e.bead_id at main_sha.

- [ ] Add policy tests showing record preserved, missing default, bad keys/types and
  remote-entry evidence rejected, source closed/not_required and accepted count unchanged.
- [ ] Run policy tests and observe new assertions fail.
- [ ] Implement exact JS schema and C# schema with safe integer validation.
- [ ] Add browser test rendering missing/unavailable/recorded, source disclaimer,
  actual derived PR/receipt actions, no executable HTML or invented acceptance.
- [ ] Run browser regression with existing bundled dependencies, no installation.
- [ ] Extend native harness fixtures for real valid/invalid nested field cases;
  execute only after separate action-specific authorization. No static test replaces it.
- [ ] Run permitted focused Python/JS tests and inspect actual diff.

### 3. Public documentation, independent validation and PR

Files: docs/local-beads-books.md, docs/beads-results/tt-x6t.md, spec/plan above.

- [ ] Describe exact marker/schema and source-record semantics; record current
  factual result/test scope in receipt without predicting acceptance/merge facts.
- [ ] Independent TEST context reads original criteria and full actual source;
  checks privacy/behavior, permitted tests only. Resolve all findings with TDD.
- [ ] Full `python -m unittest discover -s tests -v`; overlay `python -m unittest -v`
  and applicable Node suite; separate authorization for native test/smoke.
- [ ] Fresh fetch main (60s) and local exact Git validation (10s), commit/push/PR.
- [ ] Independent whole-PR approval pinned actual H/B, genuine status, full runtime
  CI, protection/mergeability/resolved findings, serialize protected expected-H merge.

### 4. Exact main and real Books

- [ ] Fresh fetch/validation, exact-M full postmerge CI and authentic ZIP artifact.
- [ ] Separate independent main acceptor checks exact M/artifact/full result.
- [ ] Recheck own native owner/dependencies; heartbeat; guarded append exact typed
  record with real PR/M; bounded source readback. Do not assert closure yet.
- [ ] Under separately authorized bounded actual-app step observe real existing
  Books source, scoped tt-x6t/owner/state/dependencies/history/result; no config scan.
- [ ] Only after complete real result, guarded canonical close and events/readback,
  then actual source closed state without treating it as automatic acceptance.

If authorization/source/runtime evidence is absent or unknown, stop that effect,
preserve receipts/fences and leave task incomplete. No backlog task expansion.
