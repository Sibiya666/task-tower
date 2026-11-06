# Duration-balanced runtime CI

Task: `tt-qrk.6`, a bounded scheduling delivery under `tt-qrk`.

The four runtime jobs previously received every fourth alphabetical unittest ID. Equal test counts did not mean equal work. The helper now assigns discovered objects by decreasing estimated cost to the least-loaded shard, with lexical ID and numeric shard tie breaks. Selected objects execute in lexical order. A fixed source mapping contains 55 expensive test estimates; every other discovered test has cost 1. Hints change placement only and cannot add or exclude tests. Runtime CI does not download timing history.

## Baseline and profile provenance

[PR103 run 42250697164](https://github.com/Sibiya666/task-tower/actions/runs/42250697164), attempt 1: API head `f5d99780fe1010448a73fca5ae1c58a9ac06ff06`, actual tested proposed merge `c9a3e2d929b673f9841b6083cbf75b3781e3a836`. The four ZIPs are artifacts `13521041662`, `13520972166`, `13520223162`, `13520467298` for shards 0–3; verified SHA256 values:

```text
0 d08b43f03f91e17cc1d52a269c1ed31f81991fd42e03fb02f5e55f108189343e
1 1dc038c77190a7735f67dbd7c0115ff3ed728085de4ee9e3f0b21bf3ad28b177
2 59042e30617f0874910ed44905c0cff0bcc95bd179162fe805c8afdf59bbda05
3 fdb0ee36397428a2cbd945307cb27fa2f95e8ee2afa4ce8ed5f381658b7c13d2
```

Each test whose recorded duration is at least 5 seconds contributes `max(1, round(seconds))` to the fixed mapping, using Python integer rounding. These durations include per-test setup/cleanup, but not class/module fixture time. Independent review verified the ZIP digests, original complete inventory and numerical replay. Hints are estimates, not acceptance evidence; source changes to them require ordinary review and full CI.

The separate [exact-main run 42266696012](https://github.com/Sibiya666/task-tower/actions/runs/42266696012), attempt 1, tested merge `087fab3f684f70be8206aa5eb7ac2d9f3c5acf1d`. Both runs used tree `4be9c8db8019170b6c3aa920e83b168889dafd6b`, 892 tests and 3 skips. The second run is a holdout for the PR-derived profile.

| Measure | PR103 | Exact main |
| --- | --- | --- |
| Actual per-shard test sums, seconds (0–3) | 303.009 / 503.133 / 543.334 / 347.777 | 403.850 / 460.004 / 539.205 / 329.577 |
| Actual slowest job, seconds | 567 | 575 |
| Run creation to shard start, seconds (0–3) | 53 / 28 / 28 / 29 | 21 / 21 / 21 / 21 |
| Scope completion to shard start, seconds (0–3) | 27 / 2 / 2 / 3 | 3 / 3 / 3 / 3 |
| New assignment replay test sums, seconds (0–3) | 421.985 / 418.735 / 422.747 / 433.787 | 443.334 / 433.887 / 428.241 / 427.174 |

Start delays include workflow dependency/scheduling time. These API timestamps do not expose pure runner queue time. Replay redistributes recorded durations; it does not execute tests and does not prove speedup. Host variability, fixture time and changes in inventory affect actual outcomes. New delivery PR/main runs must report their actual times and inventories separately; a changed-inventory comparison is not a controlled performance experiment.

## Acceptance remains complete

The serial unittest command remains valid. All four Windows jobs still execute their prescribed subset of full discovery. Version-2 `duration-balanced-v1` manifests must agree on exact checkout SHA and complete inventory; the aggregate independently recomputes the assignment and checks exact-once coverage against fresh discovery. Old schedules, stale, incomplete, failed or inventory-only results cannot become runtime passes. Job-success gates, temporary-root checks, fixtures, `load_tests`, skips and runtime postmerge event identity remain intact.

Local helper regressions cover weighted imbalance, input ordering, unknown IDs, original object identity, invalid/duplicate cost data, wrong versions/schedules/assignments, incomplete inventories, failures, real skips and multiple module/class fixture lifecycles. Full local and hosted suite results belong to the delivery evidence; this document does not preclaim them.

This scheduling change does not diagnose or fix `tt-qrk.4`, resume paused `tt-qrk.5`, accept PR85, prove UI behavior or close the parent epic. Independent exact-head/base PR acceptance, genuine status, all applicable successful CI, protected expected-head merge and separate exact-main acceptance remain required.
