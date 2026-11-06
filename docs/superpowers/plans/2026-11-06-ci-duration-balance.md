# Duration-balanced CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce runtime shard imbalance without reducing coverage or acceptance.

**Architecture:** Fixed source cost hints drive deterministic greedy assignment of discovered unittest objects. Execution and aggregation recompute the same prescribed selections; manifests identify the new schedule.

**Tech Stack:** Python 3.11 standard library, existing four Windows GitHub Actions jobs.

**Spec:** [Approved design](../specs/2026-11-06-ci-duration-balance-design.md). Human approved design and implementation on 2026-11-06; execute in this isolated session with independent review.

## Global Constraints

- Preserve discovered objects, load_tests exclusions, fixtures, skips and serial entry point.
- Preserve four isolated Windows jobs, successful-matrix gates and exact-source fresh inventory verification.
- Hint costs are positive integers <=86400, default cost 1; no network/cache/environment selection inputs.
- All PR/main gates remain; tt-qrk.4, paused tt-qrk.5, PR85 HOLD and original WIP remain untouched.
- No UI/native-window observation or smoke acceptance.

## Review Focus

- New/renamed tests must execute despite absent or obsolete hints: Task 1 unknown-ID test.
- Equal costs/input permutations must produce stable selections: Task 1 deterministic tie tests.
- Invalid fixed JSON must fail before tests execute: Task 1 loader/runner tests.
- Old or forged selections must not pass aggregation: Task 2 version/schedule/assignment tests.
- Reordering must preserve actual multi-class/module fixtures: Task 2 lifecycle test.

### Task 1: Cost profile and deterministic scheduling

**Files:** modify `task_tower/ci_unittest.py`, `tests/test_ci_unittest.py`; create `task_tower/ci_unittest_costs.json`.

**Interfaces:** `load_costs()` reads only the fixed package-relative mapping; `schedule(ids, count, costs)` returns sorted ID lists for every shard. `partition(suite,index,count)` retains its public signature and returns the original discovered objects.

- [ ] Add failing tests: unequal weights reduce maximum predicted load versus index slicing; ties and reversed input produce identical groups; original objects appear exactly once; unknown IDs default to 1, unused hints introduce nothing. Invalid counts, IDs and hints reject.
- [ ] Run `python -m unittest discover -s tests -p test_ci_unittest.py -v`; verify new assertions fail for absent scheduling behavior.
- [ ] Implement fixed JSON duplicate-key rejection and integer bounds, deterministic decreasing-cost/lexical sort, lowest-load/numeric-shard assignment and lexical selected order.
- [ ] Derive exactly 55 hints from digest-verified PR103 artifacts: durations >=5 seconds rounded with Python round, minimum 1. Record provenance in documentation, not runtime network input.
- [ ] Run focused tests; inspect deterministic exact-once output with the actual discovery inventory. Commit implementation and tests after Task 2 makes the complete contract coherent.

### Task 2: Fail-closed manifest integration and lifecycle

**Files:** modify `task_tower/ci_unittest.py`, `tests/test_ci_unittest.py`.

**Interfaces:** manifest version 2, `schedule: duration-balanced-v1`; `verify(manifests,source_sha,count)` recomputes prescribed selections from the same fixed source profile. Main aggregate still compares all IDs with fresh checkout discovery.

- [ ] Add failing tests rejecting version 1/wrong schedule/round-robin forged selections even with complete union; retain stale SHA, omitted/duplicate IDs, failed and inventory-only cases.
- [ ] Add fixture test executing multiple classes/modules across all synthetic shards, checking module/class/per-test setup and cleanup, real skip behavior and no excluded load_tests objects.
- [ ] Implement runner/aggregate schedule identity and independent recomputation, preserving current matrix/result checks and source discovery comparison.
- [ ] Run focused CI helper and existing workflow contract tests; all pass. Run whitespace check and commit source/profile/tests/spec/plan.

### Task 3: Full verification and repository delivery

**Files:** create `docs/research/2026-11-06-ci-duration-balance.md` with baseline provenance, methodology, predictions and actual available hosted observations.

- [ ] Run `python -m unittest discover -s tests -v` once on final implementation; inspect full outcome. Investigate concrete failures without weakening checks.
- [ ] Obtain independent whole-diff DEV/TEST scrutiny. Address findings and repeat only affected checks.
- [ ] Open normal PR and verify actual complete four-shard CI, exact tested SHA and authentic manifests. Record per-shard test sums, slowest job and dependency/scheduling delays separately from pure queue. No controlled speedup claim from changed-inventory/non-comparable runs.
- [ ] Obtain fresh independent exact head/base whole-PR approval; publish genuine task-tower/pr-acceptance using reviewed fixed host helper; verify all CI/protection/findings and expected-head merge under repository serialization.
- [ ] Fresh fetch main <=60 seconds/local validation <=10 seconds. Verify exact-main full matrix and authentic runtime event/shard ZIPs; separate independent main acceptance.
- [ ] Guarded close/readback/history only for this child after all evidence. Parent epic remains unresolved; do not activate another task.
