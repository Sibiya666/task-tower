# Handoff and recovery research implementation plan

> **For agentic workers:** Use superpowers:executing-plans to execute this plan in the assigned ordinary session. A distinct reviewer reviews the whole artifact; do not delegate authorship.

**Goal:** Deliver the bounded research artifact for Beads `tt-e4n.2`, not a recovery implementation.

**Architecture:** Beads is task/dependency/owner/history authority; Superpowers is the method; the installed harness executes; Books is read-only. Compare pinned source and sanitized observations, then propose a minimal handoff contract and a reproducible fresh-session evaluation.

**Tech stack:** Markdown, existing Git and documentation validation, read-only source inspection.

**Spec:** Canonical `tt-e4n.2` claim supplied by the coordinator; [approved unified design](../specs/2026-11-05-task-tower-unified-design.md). The coordinator accepted the four-criterion first-turn plan before assigning this worktree. The bounded ordinary-session pilot uses existing permissions without claiming G1/G2 provider qualification.

## Global constraints

- Intended changes are `docs/research/harness-engineering/02-handoff-and-recovery.md`, this plan, and the coordinator's single introductory pilot-authorization paragraph in `docs/superpowers/specs/2026-11-05-task-tower-unified-design.md`. Preserve that paragraph and include it in whole-diff review.
- Preserve the existing claim owner `task-tower-ordinary-session-pilot`; do not claim, transfer, merge or close Beads here.
- Windows local embedded source; no native/POSIX experiments, production runtime changes, new installation/account/model/auth/ACL or old-conveyor execution.
- Pin course `justxor/Harness_ru@6420da2d57c901c401fc909354a7f5f7fce81882` and Task Tower source `78e8d1b13847d9037da245a66653dd566be5b190`; mutable evidence must retain observation time and limits.
- Independent SPEC/DEV/TEST review, fresh exact-head/base PR acceptance, real applicable CI, expected-head merge and exact-main acceptance remain mandatory. Coordinator owns integration and closure.
- `runtime_tests:not_run`; document verification is not runtime acceptance. Fresh-session recovery experiment remains NOT RUN unless separately executed under its frozen protocol.

## Review focus

Stale handoff; changed main; unknown push/merge; double owner; unavailable source. For each, the artifact must name fresh evidence, a safe stop/decision, prohibited inference and an observable expected result. Narrative or old JSON cannot establish ownership or authorize replay.

## Task 1: Research and document

**Files:** Create `docs/research/harness-engineering/02-handoff-and-recovery.md`.

**Consumes:** Canonical four criteria, prior `.1` audit, pinned course, current Books/admission/harness sources, archival journals and sanitized pilot evidence.

**Produces:** Evidence register, current-versus-archive audit, proposed contract, scenario matrix, fresh-session protocol and boundary mapping.

- [ ] Read selected primary sources and record exact revisions/locations and observation limitations.
- [ ] Define repository/bead, branch/worktree, head/base, policy/input versions, stage, owner/attempt, evidence, blockers and next action, including missing/unknown treatment.
- [ ] Cover compaction, chat stop, process crash and runner change through the five mandatory failure scenarios.
- [ ] Specify frozen input packet and evaluator answer key, timing/reconnaissance/error metrics, pass/fail conditions and NOT RUN status.
- [ ] Delineate archived Issue16, tt-m9l, tt-auq.4 and tt-auq.5; self-check all four criteria against concrete sections.

## Task 2: Verify and hand off

**Consumes:** Entire actual diff and source/evidence register.

**Produces:** Independent review receipt outside Git, verified documentation commit and PR for coordinator acceptance.

- [ ] Run `git diff --check` and existing documentation link validation against the prospective source; expect no new broken supported local links or whitespace errors. Do not invent runtime test results.
- [ ] Distinct reviewer receives full actual diff, canonical requirements, source pointers and actual check results; obtain separate SPEC/DEV/TEST conclusions and address substantive findings.
- [ ] Commit only the three intended Markdown files, push the assigned branch and create a PR without an Issue52 closing footer.
- [ ] Report base/head/worktree/branch, PR, verification, review receipt and remaining gates; do not merge or close the bead.

## Execution rulings

This is a documentation research task: production-code RED/GREEN steps do not apply. Existing document checks and independent factual review provide verification. Runtime evidence/ledger remains outside Git and is retained for the coordinator; generic skill scratch cleanup must not remove pilot evidence. The explicitly assigned worktree is reused; no installation or new worktree is needed.
