# Whole test review — a569 rejection and completed local evidence

Independent whole-test reviewer `/root/books_native_smoke_impl`, distinct from implementers and development acceptor; 2026-11-02. **REJECT test acceptance at `a569285d1966e53a5abe52a8b7f368d43321cc75`: current-head macOS CI failed.** The initial rejection below was recorded while the required local run was in progress; its completed green result is appended. That local pass does not erase the macOS failure or establish three-platform acceptance. No source fix, timeout increase or retry has been accepted by this review.

## Source and stage binding

Started with HEAD8981c6d plus the frozen three-file checkpoint-freshness correction, manifest `runtime-task7-freshness-freeze.json` SHA-256 `9149e814d3175f487b1157de2157cf4ab49a4866aecdb4c240d576008ddc51e0`. The coordinator subsequently committed those identical source bytes, five identical documentation updates and the development/pilot receipts/card as `a569285d1966e53a5abe52a8b7f368d43321cc75`, based on accepted main `56f8ab12f21ab91030ffe54de96520fcd979dc04`. The three correction hashes still match; all five documentation bytes match the local run's starting snapshot.

The separate independent development re-review approved the correction; the task card binds its canonical evidence digest `da935ae536b6ae72c7c06771c2ee53660298b205d4d6006b4a5b6e4dfe3cbaa4`. That stage approval is necessary but does not override a failed test/CI gate.

## Preserved current-head macOS failure

Authoritative [Portable CLI run41419194473](https://github.com/Sibiya666/task-tower/actions/runs/41419194473), exact head `a569285d1966e53a5abe52a8b7f368d43321cc75`. The GitHub connector's per-job log was available before the entire matrix finished:

- macOS job `125190366182`: **666 tests in717.337s, FAILED, failures1/skipped7**, Python3.11.9. Failed `test_pipeline_watch.WatchTests.test_real_dispatch_adapter_to_six_roles_and_host_tests`, line67 awaiting ready_for_pr through line63's watch-condition assertion.
- The saved run had already parked at `needs_input / spec / policy_revoked`, generation1, process_count0 and checkpoint=null, with a bound Issue/source/base/worktree. The park timestamp was approximately0.24s after initial claim, long before the test's eventual wait timeout. No model/custom role was launched in this failed path.
- The current log does **not** identify the underlying authority-check failure. `policy_revoked` is a fixed generic outcome, not proof of actual policy editing or a diagnosed portability cause. The exact lower-level cause remains **unproven**; increasing a timeout is not justified by this evidence.

Decoded per-job log was preserved privately, 134960 UTF-8 bytes, SHA-256 `eac58e82dfdf787d1c077b2598364411122d58909180f3d53f9652cdbe98fc7e`. Raw private worktree paths and transport details are not reproduced here. Ubuntu completed successfully; Windows was still running when this rejection was recorded. The earlier all-green CI for8981c6d does not cover this newer head.

## Required local run — pending completion

Actual unmodified child command: bundled Python3.12.14 `-m unittest discover -s tests -v`, genuine normal Windows-user execution. Test PID131800, private capture wrapper134768; test start2026-11-02T09:14:38.026864Z. No child environment patch, test instrumentation, additional timeout, source edit or concurrent journal reset was introduced. Capture is bounded to an8MiB prefix plus128KiB tail with full observed stream digest and exit/duration metadata at completion. No final count or local verdict is claimed yet.

The starting snapshot binds537 tracked files. Mid-run comparison found only the expected newly committed development/pilot review files and task-card stage receipt; all product/test files and the five documentation files remained unchanged. The first64KiB captured434 verbose test entries without a recorded FAIL/ERROR marker; this is a partial prefix, not a final result. Recorded skips so far concern unavailable symlink creation and POSIX executable-mode transition. Complete skip/abnormal-output review remains pending the terminal summary.

Read the four new actual-Git multi-scenario freshness tests: normal pre-intent main/policy/Issue/pins/cancellation revocation; rework pre-intent main/policy; normal/rework post-intent and post-commit revocation; unchanged refs, preserved dirty source and unresolved intent/no replay. Those cases are included in the single full run. The separate development acceptor's seven focused tests are earlier independent development evidence, not this reviewer's complete-test result.

## Pilot and operator evidence remain qualified

The independent installed pilot receipt remains bound to committed8981c6d, digest `8b76a458bf35099fff76c648a882edb919c876a5cdcc9f5caf6fef70d66d4461`. It supports six actual installed roles, three approvals, a real fixed check and local ready_for_pr with fixture GitHub transport and publication disabled. It does not claim execution of the later authority guard or replace its fault regressions. The five updated operator/shared docs retain this distinction, same-repository serialization, unknown no-reset, fixed-host authentication versus model/check stripping, and no service/night/live-GitHub acceptance claim.

The three pilot sets (166+445+443 files) and their original outcomes must remain preserved. The original unrelated Task6 unknown remains unproven. TEST acceptance stays blocked until the current failure is diagnosed/corrected, affected checks pass independently and the new exact head has successful Ubuntu/macOS/Windows CI. The full local result will be appended without erasing this rejected-head history. PR/main/postmerge/automatic Issue closure are separate later gates.

## Completed independent local full suite — green, rejection unchanged

The same single unmodified command completed: **666 tests in1396.694s, OK, skipped6, exit0**. Private observer elapsed1397.093s. Bundled Python was3.12.14; CI separately uses3.11. No timeout was added or weakened, no test instrumentation or child environment patch was used, and no second/reset local suite is substituted for this run.

All100130 output bytes were captured, without truncation. Full observed/saved log SHA-256 `c603fb3552ca93c4aeb441baf34ed208d362ff85130dfb9b788b918e40ebc175`; observer result metadata SHA-256 `63f30ec5d9e48be9b6613908e2c6a55d03aa98bed55a433ef172c4fe447342da`. Starting tracked-file snapshot SHA-256 `fe2fec84b3c192fa257b373aa628a3c0f363bb27aba269a391df07e8033da775`; ending snapshot SHA-256 `0649993f2df74710f490dfbfd3eb1574844bab77bce5d5b8cf637a23da8a5ebe`. The only snapshot differences are the coordinator's expected task-card development receipt and newly tracked development/V3 review files; no product, test or five-documentation bytes changed during execution. The tested three-file correction remains exactly bound to freeze9149e814 above and commit a569285.

Inspected complete output, not merely the exit status: no FAIL/ERROR summary, traceback, unhandled-thread exception, ResourceWarning or RuntimeWarning was recorded. Six skips were:

| Test | Reason |
| --- | --- |
| ExecutorProcessesTests.test_alias_capture_directory_rejected | symlink privilege unavailable |
| ExecutorProfilesTests.test_symlinked_instruction_file_rejected | symlink privilege unavailable |
| HarnessTests.test_refuses_symlink_state_directory | symlinks unavailable |
| PortablePathTests.test_worktree_executable_mode_change_is_bound | POSIX executable mode transition |
| JournalTests.test_rejects_symlinked_database_parent (postmerge journal) | symlink creation unavailable |
| SafeConfigRaceTests.test_leaf_and_ancestor_symlinks_stay_rejected | symlink creation unavailable |

These are declared environment/platform skips, not erased assertions. Windows junction and hardlink guards ran; POSIX/symlink behavior remains covered by the platform matrix rather than being claimed from this Windows host. The full run includes the actual checkpoint-authority boundary, role/check/publication, journal/concurrency, CLI/watch and legacy suites. New freshness tests passed within that complete run. The qualified six-role V3 audit remains source8981c6d evidence, not a claimed fourth model run.

Independently rehashed all1054 preserved pilot files after the full suite:166 original,445 V2 and443 V3 all unchanged. No pilot journal reset/replay or installed-model invocation occurred. The recorded macOS failure remains a real current-head blocker despite this local green run; its generic policy_revoked outcome is not retroactively diagnosed by a different later probe. A future correction and independent current-head evidence must be appended as a new review rather than relabeling this head accepted.
