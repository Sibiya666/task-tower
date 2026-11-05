# Windows CI results — 2026-11-05

The PR-based route now avoids duplicate push runs, partitions the complete runtime inventory across four Windows jobs, and gives qualifying prose a separate bounded validation route. Code implementation was independently accepted at main `0156c0800a8817a54960103937287f601ecba6b5`: exact-main postmerge ran 850 tests, with 3 skips and no failures/errors. This report is the useful prose-only pilot for the separate documentation route.

## Measured wall time

| Completed run | Route | Observed wall time |
| --- | --- | ---: |
| [PR76 CI41906263956](https://github.com/Sibiya666/task-tower/actions/runs/41906263956) | Serial full runtime suite | 23:19 |
| [PR77 CI41914080190](https://github.com/Sibiya666/task-tower/actions/runs/41914080190) | Four full-inventory shards and aggregate | 11:59 |
| [PR79 CI41947320349](https://github.com/Sibiya666/task-tower/actions/runs/41947320349) | Scope, four runtime shards and aggregate | 10:14 |
| [PR79 exact-main CI41948930524](https://github.com/Sibiya666/task-tower/actions/runs/41948930524) | Exact-merge full runtime verification | 10:28 |

Times use recorded workflow start/completion timestamps. The latest PR run reached its first job after 2 seconds; scope took 16 seconds, the slowest shard 565 seconds and the aggregate 24 seconds. The six job durations sum to 29:51; this is job wall time, not a billing calculation. Parallel execution trades runner capacity for shorter elapsed time.

These are different-source hosted-runner observations, not a controlled benchmark or a guaranteed speedup. Test inventory changed between revisions. Do not attribute all observed improvement to sharding or temporary-directory placement. See the [original investigation](2026-11-04-windows-ci.md) for the trigger overlap and targeted-method measurements.

## What remains checked

Only the PR workflow and one exact-merge postmerge workflow run the runtime suite; ordinary branch/main push duplicates were removed. New updates supersede only the same PR. Direct pushes and merge queues are outside this route.

Runtime shards retain actual discovered test objects and fixtures. Stable aggregate gates require successful jobs, matching actual source SHA and full inventory, and exact-once prescribed selections verified against fresh source discovery. PR79 postmerge selected 213/213/212/212 tests, covering 850 identities once. All five downloaded postmerge archive digests matched GitHub; the runtime event identifies PR79, the actual main commit and Windows checks passed. Independent source acceptance is separate from that CI evidence.

## What a documentation result means

The fast route applies only to normal two-parent merges of regular root README/AGENTS or nonhidden Markdown under docs, excluding templates. Full first-parent changes, file modes, deleted/renamed targets and existing referrers participate. Code, workflow, mixed or uncertain changes retain full runtime checks. Bounded validation reads Git objects and checks whitespace plus newly broken supported local links against baseline; it is not a complete CommonMark or external-URL checker.

For this prose-only pilot, acceptance requires successful live scope and stable PR checks, expected skipped runtime jobs, then independent exact-main source acceptance and a genuine `task-tower-docs-<PR>-windows` report. That report must identify the actual merge, repository and PR, with kind `documentation.validation`, checks `passed`, and runtime_tests `not_run`. The corresponding runtime artifact must be absent. A skipped runtime suite is never a runtime pass, and task completion is not inferred from a merge alone. The [fast-path spec](../superpowers/specs/2026-11-05-docs-ci-fastpath.md) defines the full contract.

## Retained failure and mitigation limits

PR77's first postmerge attempt failed during fixture preparation; one bounded unchanged repeat passed. Both outcomes remain recorded. Later failed PR79/PR80 revisions remain failures, not hidden green runs.

The accepted bounded observer ultimately captured two original PR79 preparation failures at `PipelineJournal._wait_seconds()` line 119, reached from `_db()` line 199 before SQLite connection. The original one-second cancellation-read operation budget had expired; containment and shutdown succeeded. This establishes the failure boundary, not whether filesystem latency, scheduling or another preconnection delay consumed that wall time. It does not prove SQLite lock contention.

A fixed local synthetic profile measured 96 versus 136 lstat calls for paths differing by five ancestor levels; all samples passed in milliseconds. It proves workload scaling only. Runtime shard prechecks and suite commands now use identical step-local TMPDIR/TEMP/TMP settings from the runner temporary directory. Unique children, normal cleanup, production security checks, test assertions and deadlines are unchanged. The precheck emits numeric depth or fixed path-free failure text. This is a workload mitigation, not proof the intermittent bug is fixed; Beads bug `tt-qrk.4` remains open.

GitHub documents [temporary-directory lifetime](https://docs.github.com/en/actions/reference/workflows-and-actions/variables) and [expression availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts). Runner expressions belong in step-level environment here, not job-level environment. No runner/account/authentication configuration was changed.

The CLI workflow does not establish overlay/native UI acceptance, unattended execution, another operating system or multi-machine readiness. Canonical Beads closure is coordinated after the applicable evidence and independent gates; this work does not ship an automatic Beads development daemon.
