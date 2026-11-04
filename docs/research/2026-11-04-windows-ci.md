# Windows CI investigation

Canonical Beads task: `tt-3d8`. Research method: Superpowers systematic debugging. Scope: existing Windows workflows and tests, not a revival of the archived custom development conveyor.

## Question and evidence

Why does a documentation change wait roughly half an hour, and which reductions preserve meaningful acceptance?

The read-only investigation captured four completed GitHub jobs, the latest 30 workflow runs, one full timestamped log, and the unchanged workflow definitions at main `19d230241b0f8472d77bf6c5ce22a0da34cbc836`. No workflow was dispatched for these measurements. Local raw evidence is retained under `runtime/ci-study/`; it is not a tracked product database or a substitute for the public runs below.

| Run | Trigger | Test step | Whole job |
| --- | --- | ---: | ---: |
| [41889387747](https://github.com/Sibiya666/task-tower/actions/runs/41889387747) | branch push, PR74 candidate | 31:48 | 32:02 |
| [41889466395](https://github.com/Sibiya666/task-tower/actions/runs/41889466395) | PR74 | 32:53 | 33:06 |
| [41895787363](https://github.com/Sibiya666/task-tower/actions/runs/41895787363) | main push, merge9ea1224 | 35:39 | 35:56 |
| [41895789544](https://github.com/Sibiya666/task-tower/actions/runs/41895789544) | postmerge PR74, checkout merge9ea1224 | 22:23 | 22:38 |

Checkout took 7–9 seconds; setup-python took 0–1 second. These jobs demonstrate that the test step, rather than installation, dominates. This is a small contemporary sample, not a long-term percentile or a speed guarantee. The two exact-main jobs differ by over 13 minutes despite testing the same source; their logs alone do not establish the cause of that runner/process variance.

## Findings

1. `.github/workflows/cli.yml` starts the same full unittest command on every ordinary branch push and on PR events. It has no documentation classifier. A README-only change therefore executes the entire CLI suite.
2. A default PR checkout tests GitHub's proposed merge revision, whereas a branch push normally tests the branch head. They overlap in purpose but are not guaranteed to be identical trees. Preserve PR merge-tree validation when removing redundant branch pushes. See [GitHub's event reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).
3. A merge starts both the main-push CLI suite and `postmerge.yml`. The latter explicitly checks out `pull_request.merge_commit_sha`, executes the full suite and publishes the existing merge-event artifact. For PR74 this repeated full testing of the identical main revision. One exact-main run with the existing artifact is sufficient for that route; direct pushes and merge queues need an explicit future policy rather than an assumed PR event.
4. The current workflows discover `tests/` only. Overlay Python/Node/native checks are not explicit workflow steps. A green CLI check does not prove overlay acceptance; do not disguise faster CLI execution as improved overall coverage.
5. The timestamped main log has long result-line gaps around `pipeline_watch`, `pipeline_publish` and `pipeline_worker`, including approximately 90, 87 and 81 seconds. These are candidate hotspots, not exact isolated test durations: output buffering and fixture work can affect attribution. The old engine is archived, but the code remains in the product; removing all its tests would leave retained behavior unverified.

## Targeted local reproduction

Two unchanged `WatchTests` cases were profiled at exact main19d2302 using the existing Windows host Python, a monotonic timer, and a 300-second contained-process budget. Both passed without skips; the outer process exited0 with actual EOF/cleanup confirmed, and the Python source hashes remained unchanged. Total test run: 149.50 seconds (outer supervisor:150.672 seconds).

| Case | setUp | Method |
| --- | ---: | ---: |
| `test_distinct_worker_processes_commit_push_and_create_one_pr` | 0.52s | 77.43s |
| `test_lost_pr_response_is_unknown_and_restart_never_posts_again` | 0.49s | 70.89s |

This reproduces the expensive methods locally and shows that their top-level `setUp` is not the dominant cost in this sample. The methods exercise many real contained subprocess stages. Instrumentation observed parent calls only; nested child commands and cleanup were not independently apportioned. This is neither exact CI test timing nor proof that a particular process-supervision implementation is at fault. No tests were removed, assertions changed or timeouts shortened. Reproducer and original process/hash facts are retained in `runtime/ci-study/{profile-sample.py,run-profile.py,targeted-profile.json,targeted-profile-process.json}`.

## Recommended work, in order

### A. Remove overlapping triggers without removing tests

Keep the full PR workflow and full exact-merge postmerge workflow. Remove ordinary push-triggered duplicates. Keep the existing PR job name and postmerge artifact contract; do not modify repository protection, credentials, acceptance requirements or test assertions. Cancel only superseded runs of the same PR, never a different PR or a main/postmerge run.

Acceptance: a branch push alone launches no duplicate CLI run; opening/updating a PR still runs the full suite against the proposed merge; merging runs the exact merge suite once and publishes `task-tower-merge-<PR>-windows`. Validate the changed workflow on its own PR and main. This initial policy assumes PR-based integration, matching the authorized process; do not silently claim direct-push or merge-queue coverage.

### B. Give documentation a bounded, truthful fast path

Classify the complete diff, including renamed/deleted paths, against a conservative prose-only allowlist. Unknown/mixed/code/workflow changes require full checks; unresolvable history must fail closed. Keep a stable final check rather than skip the entire required workflow. Validate Markdown links and path handling without executing content. Do not classify arbitrary files under `docs/` as prose: that tree also contains templates and configuration.

Acceptance: docs-only, mixed changes, workflow edits, renames across the boundary, deletions, unusual filenames and missing base all have regression coverage. The fast result must explicitly say documentation validation, not falsely represent a full Windows runtime acceptance or publish a `checks: passed` runtime artifact from skipped tests. Agree the postmerge receipt semantics in the implementation spec before using that path there. [GitHub documents that skipped workflows can leave required checks pending](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

### C. Accelerate measured test costs

Record per-test setup/method/cleanup durations and process categories using a monotonic clock. Start with the two slow publication/watch cases, then profile only demonstrated hotspots. Separate parent observations from nested child work; compare repeated samples before assigning causes. Consider fixture reuse, reduced redundant process/Git setup or isolated parallel groups only where safety and Windows process-cleanup assertions remain equivalent. Do not shorten correctness timeouts or delete archived-engine coverage merely to obtain a green number.

Acceptance: preserve discovered test identity/outcomes, run appropriate containment/security/recovery regressions, retain real EOF/cleanup facts, and report before/after measurements with source SHA and environment. A local sample is not a measured CI speedup.

## Process and limits

The research is accepted only after an independent reviewer checks the report against evidence. Record review provenance separately from source closure. Optimization tasks belong in local Beads with this report as rationale; completion still requires reviewed code in accepted main. The user's CI exception for docs PR75 is not authorization to suppress checks on workflow/code changes. No model/account/auth changes, private DB publication, macOS/Linux/WSL execution, VPS deployment, migration or old-conveyor development is part of this study.
