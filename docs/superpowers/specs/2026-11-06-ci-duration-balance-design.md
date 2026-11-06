# Duration-balanced Windows unittest shards

Date: 2026-11-06
Parent: tt-qrk (owner task-tower-ci-wait-coordinator)
Status: independently reviewed APPROVE; awaiting human design approval
Base: 6f5afb95c76a14e3ea422ccdcd376ef78cbd66e8

## Intent and evidence

Reduce the slowest runtime shard by balancing measured test cost, retaining the complete existing test inventory and all acceptance gates. Accepted trigger deduplication, documentation validation and four-way runtime sharding remain in place.

PR103 run 42250697164 attempt 1 API head f5d99780fe1010448a73fca5ae1c58a9ac06ff06 tested proposed merge c9a3e2d929b673f9841b6083cbf75b3781e3a836 (tree 4be9c8db8019170b6c3aa920e83b168889dafd6b). Four authentic manifests cover 892 tests exactly once, 3 skips. Test sums: 303.009 / 503.133 / 543.334 / 347.777 seconds; slowest job 567 seconds. Start delays since run creation: 53 / 28 / 28 / 29 seconds; these include dependency waiting and are NOT pure runner queue times.

Exact merge 087fab3f684f70be8206aa5eb7ac2d9f3c5acf1d run 42266696012 attempt 1 uses the same tree and inventory. Test sums: 403.850 / 460.004 / 539.205 / 329.577 seconds; slowest job 575 seconds. Shard start delays since run creation: 21 seconds each. Per-test measurements exclude class/module fixtures. Retained ZIPs are SHA256 checked against authentic artifact metadata; real logs independently agree with PR test totals and tested SHA.

## Approaches

Recommended coordinator choice, awaiting human approval: source-controlled rounded cost hints plus deterministic greedy balancing. It targets the measured imbalance without network or artifact input during CI.

Alternatives considered: hashing IDs changes placement without using cost; module-only buckets may leave large modules dominating one job. Dynamic downloaded timing history adds availability and provenance dependencies. Altering tests, sleeps, security checks or deadlines is out of scope.

## Scheduling contract

1. Keep full unittest discovery as the membership authority, including original discovered objects and load_tests exclusions. Never load tests again by dotted name.
2. Add one small source-controlled JSON mapping for the 55 measured expensive IDs (PR103 per-test duration at least 5 seconds), rounded to positive integer seconds. Other IDs, including new tests, receive a cost of 1. Unused hints never introduce tests.
3. Reject malformed hint data, duplicate JSON keys, non-string/empty IDs, boolean/noninteger/nonpositive or greater-than-86400 costs. Read only the fixed package-relative file; no CLI-supplied file, network input, cache or environment override.
4. Sort all discovered IDs by descending estimated cost then lexical ID. Assign each to the shard with lowest accumulated cost, ties by numeric shard index. Sort selected discovered objects by ID before passing them to the existing unittest runner.
5. Runner and aggregate independently recompute the prescribed plan from their exact source and actual full inventory. Use manifest version 2 with explicit schedule identity duration-balanced-v1. Reject old/wrong schedules, duplicate/missing/stale/failed/inventory-only manifests and wrong assignments. Keep full exact-once union and fresh-checkout inventory checks.
6. Keep four isolated Windows jobs and existing serial unittest entry point. Workflow triggers, temporary-root checks, stable aggregate names, matrix-success requirement and postmerge artifact/event identity stay intact. No acceptance from timing data alone.

## Expected result and limits

Replay of the new assignment against recorded PR103 durations predicts 421.985 / 418.735 / 422.747 / 433.787 seconds. The independently recorded exact-merge durations predict 443.334 / 433.887 / 428.241 / 427.174 seconds using the same PR-derived hints. These are scheduling estimates, not new executions or proven speedup. Hosted noise, fixture overhead and queue changes may reduce the benefit. Unknown or renamed tests still execute with default weight.

## Implementation boundary

Expected source changes: task_tower/ci_unittest.py, one fixed cost JSON, tests/test_ci_unittest.py, and public documentation of evidence/method/results. Inspect other existing tests for assertions of the old prescribed partition; update only genuine scheduling-contract expectations. No new task engine, service, monitor or dependency. No product runtime behavior changes. No installation/auth/model/account/ACL/policy changes.

This does not diagnose or fix tt-qrk.4, resume paused tt-qrk.5, transfer their owners, or accept PR85. The parent epic remains open while its unresolved obligations remain. If approved, create one child for this scheduling delivery with these concrete criteria and native claim/readback; do not duplicate either protected defect.

## Validation and delivery criteria

- TDD for deterministic scheduling under reordered input; complete object identity preservation; unknown IDs; invalid costs; a meaningful unequal-cost case; corrupted/wrong schedules; omissions/duplicates; stale SHA; inventory-only/failure rejection; genuine skip handling; class/module fixture lifecycle; existing load_tests exclusion regression.
- Focused helper and workflow contract checks, then complete dependency-free CLI suite. No repeated full suites without changed source or a concrete failure requiring verification.
- Actual PR CI must run the complete current inventory across all four successful Windows jobs and pass fail-closed aggregation at the real tested source SHA. Verify authentic ZIP identities/digests and full inventory/selection/outcomes; API head is not automatically tested SHA.
- Report actual per-shard test totals, slowest job, job/step timestamps and queue measures where available. Label run-to-job start delay separately from pure queue. Compare with the same-tree PR103 baseline and account for changed inventory; do not claim a controlled speedup from non-comparable observations.
- Fresh independent whole-PR exact head/base approval, genuine task-tower/pr-acceptance, all applicable CI/protection/resolved findings and protected expected-head merge. Serialize acceptance. Fresh main fetch <=60s/local validation <=10s; exact-main full CI with authentic runtime event and shard artifacts; separate independent main acceptance before guarded child close/readback/history.
- UI/visual/native-window/Books UI/smoke acceptance stays deferred under current AGENTS. Existing automated/security tests remain required. Parent epic cannot close merely because this child delivers.
