# Documentation CI Fast Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for the helper, then integrate through superpowers:executing-plans.

**Goal:** Validate pure prose quickly without falsely claiming runtime tests passed.

**Architecture:** A bounded Git-object classifier/validator routes stable Actions checks to documentation validation or the unchanged complete runtime matrix. Documentation postmerge evidence has its own typed artifact.

**Tech Stack:** Python3.11 standard library, Git, Windows Actions.

**Spec:** `docs/superpowers/specs/2026-11-05-docs-ci-fastpath.md`.

## Global Constraints

- Normal two-parent merge route only for fast classification; uncertain/mixed/source changes retain full checks.
- Prose source is tracked Git blobs only;16MiB/30seconds bounded, strict UTF-8, no network/private config/filesystem traversal.
- Runtime assertions/timeouts/containment and complete four-shard inventory remain unchanged.
- Separate documentation report explicitly declares `runtime_tests:not_run`; no legacy runtime consumer changes.

## Review Focus

- Never examine just the last commit of a multi-commit rebase and misclassify earlier code.
- Old and new rename paths, deleted targets and file mode changes must participate.
- Scope/validation failure or unexpected dependency skipping/cancellation must fail the stable final gate.
- Historical broken links may be tolerated only when the same broken reference existed at base; newly broken links must fail.
- Documentation artifacts must not be confused with runtime merge-event acceptance.

## Task1: Helper and meaningful regressions

**Files:** Create `task_tower/ci_docs.py`, `tests/test_ci_docs.py`; owner: isolated helper implementer, no workflow or entry-doc edits.

- [ ] Confirm independent design/buildability review.
- [ ] Write regression tests first and record real RED, implement fixed Git-object operations/classification/bounded blob validation and CLI, then GREEN.
- [ ] Independently review helper/tests for spec compliance, failure modes and privacy; fix substantive findings before integration.

## Task2: Stable routing and typed postmerge publication

**Files:** Modify `.github/workflows/cli.yml`, `.github/workflows/postmerge.yml`, README.md, AGENTS.md; coordinator owns integration.

- [ ] Add Windows scope job and scope-dependent full shards; stable final gate handles docs/full explicitly and fails closed.
- [ ] Preserve exact-merge checkout; runtime path retains full matrix/event contract, docs path publishes only typed docs artifact.
- [ ] Run helper regressions and source/classifier full-route checks, freeze complete committed head/base and obtain fresh independent whole-diff PR approval.
- [ ] Actual full matrix CI for this code change, expected-head merge, independent exact-main source and actual full-matrix/runtime artifact acceptance.

## Task3: Real documentation-only pilot

**Files:** Create `docs/research/2026-11-05-ci-results.md` with measured timings, retained first failure/unchanged rerun and open `tt-qrk.4` limitation.

- [ ] Open prose-only PR from fresh accepted main; independent head/base review remains required.
- [ ] Verify actual fast PR route, skipped runtime shards and successful stable doc validation; merge only after type-appropriate checks.
- [ ] Verify exact-main typed docs artifact, absent runtime artifact and independent main acceptance; close `tt-qrk.2` under verified original actor with real Beads history, never as product automatic closure.
