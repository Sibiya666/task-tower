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

## Corrected-source attempt — incomplete observation, no acceptance

The next full-suite attempt verified all ten raw source bindings in combined freeze `7b1885011282c846266b8060ca1952fe4f7a326cd6c2d20414f7052bc212d4d5` before launching the unchanged complete command. Test PID154352 started2026-11-02T11:45:22.106781Z, observer153808, tool session13048. On resumption that session was unavailable and neither process remained. No terminal summary, exit code, result metadata or ending snapshot was saved. The exact termination cause is unproven. This attempt cannot establish a full-suite pass; no automatic restart or substitute count is claimed.

The preserved65536-byte prefix ends mid-test name, last written11:55:21Z, SHA-256 `b2b6cbaa0b478f23191777792435dbc47ba86a5aab21aab8450e14a73685681c`. Initial snapshot SHA-256 `efbdea40a16967a68c9bddc02c9109f130cc33db470368d5e9753d5af30d845b`. This evidence is retained separately from the earlier completed666-test green run. TEST acceptance remains pending a genuinely completed corrected-source verification and current CI. The earlier a569 macOS failure and its unproven lower-level cause remain unchanged history.

## Completed corrected-code CI at e59 — Windows full pass, macOS fixture failure

Independently fetched the actual decoded job logs and verified [push run41439682203](https://github.com/Sibiya666/task-tower/actions/runs/41439682203) binds exact commit `e59d736157185f59bf7cf7cf01b47b7b673f249b`. This is genuine completed CI evidence, separate from the incomplete local attempt. The coordinator committed the combined frozen source and development receipt; a later fixture correction is not covered by this run.

- Windows job125258117812 completed successfully: **713 tests in1372.835s, OK, skipped1**. The only skip was the POSIX executable-mode transition. Inspected the complete decoded log: no unittest failure/error, traceback, unhandled-thread exception, ResourceWarning or RuntimeWarning. Actions itself emitted Node deprecation notices during setup/cleanup; these are not suppressed test warnings. Privately preserved decoded log SHA-256 `1b1753affa1b47ec767b3b9e67bc81e3cd9f24e155cf1c5f221e945bad456e20`.
- Ubuntu job125258117146 completed successfully.
- macOS job125258117540 completed with **713 tests in563.359s, failures2/skipped7**. Both failures occur in shared fixture `ExecutorTransientLinkTests.unlinked_info(directory=True)` at its assertion that deleted-directory metadata must have link count0; actual observed count was2. The affected tests are `PrivateSQLiteStatTests.test_observed_directory_zero_never_becomes_missing_sidecar` and `ExecutorTransientLinkTests.test_deleted_directory_snapshot_is_never_treated_as_sidecar`. These fixture assertions abort before the intended product negative guard assertion. Privately preserved decoded log SHA-256 `143b58334c41eb0b30da3f19824285736d94cb70500a365b6d942240aa9892d5`.

The matrix therefore completed **failure**, not portable acceptance. This new fixture failure is separately identified; it does not establish the underlying cause of the older a569 policy_revoked failure. No local full-suite replacement, timeout increase, installed model invocation or replay was performed. Functional TEST remains pending independent review and focused verification of the fixture correction and its exact source binding. Exact final-head CI across all required contexts remains a separate mandatory premerge gate; this earlier Windows full pass cannot claim final-head macOS success.


## Current functional TEST verdict — ACCEPT, final-head CI remains mandatory

2026-11-02, independent reviewer `/root/books_native_smoke_impl`: **ACCEPT functional TEST for the current content-bound candidate: committed source C=e59d736157185f59bf7cf7cf01b47b7b673f249b plus exactly the two frozen fixture corrections below**, based on accepted main56f8ab12f21ab91030ffe54de96520fcd979dc04. No blocking functional finding remains in this reviewed scope. This is a stage verdict before the final candidate commit, not a successful final-head CI/PR/main verdict. Changed source bytes invalidate the applicable binding.

Independently verified fixture freeze SHA-256 `36907966f59bdb474c0b5b540254c93efb3ff1f657980f69ab9847f0fe93e942`, both current test hashes, all five production hashes, all five documentation hashes and the independent current DEV ACCEPT report raw/canonical SHA-256 `6601b78698608d4051d5f7963865997424488507cdcdce11c12ee6d69fdd5abb`. All five production and documentation files canonically match committed C; the only test-source delta from C is the reviewed fixture correction. Current exact bindings (canonical means UTF-8 without BOM, CRLF/CR normalized to LF):

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| tests/test_safe_config_race.py | `5b3f4978888fd5ef3d9915ff0967b3e5d7d0bf23af621564f29155e68cc34f44` | `5b3f4978888fd5ef3d9915ff0967b3e5d7d0bf23af621564f29155e68cc34f44` |
| tests/test_private_sqlite_stat.py | `a2421b6c88af30409e914fd069a91244c01b0fa6634d0c147bf5d5f3434c81a8` | `a2421b6c88af30409e914fd069a91244c01b0fa6634d0c147bf5d5f3434c81a8` |
| task_tower/pipeline_worker.py | `8e64df3ff9d77c6b43631b07e3709725fd285c900a70248347f5c1801b3bc650` | `3ac0ab44af3b67862b310f252b915fd98ab29bec120066707123e68c3e036dcb` |
| task_tower/pipeline_journal.py | `06f912afdd63a406ea29b60744dc1e33db5d76bebee1aff69cda063c842a5bf0` | `06f912afdd63a406ea29b60744dc1e33db5d76bebee1aff69cda063c842a5bf0` |
| task_tower/pipeline.py | `54a8473512c534497f12f3eebcacc978d6f8e8bec82cb6514df737073410bf47` | `54a8473512c534497f12f3eebcacc978d6f8e8bec82cb6514df737073410bf47` |
| task_tower/executor.py | `1bfda46856c3137f78052aa52779b2c634f859c0ce53df9355cec5dfbdc0d801` | `1bfda46856c3137f78052aa52779b2c634f859c0ce53df9355cec5dfbdc0d801` |
| task_tower/executor_queue.py | `febd031b51a835900e1bc4fad8548f3779e09afff3caa35e3ae80e1a8acf01b3` | `ead14695dd319def66baa4ecbfab8e6259e8ab97edc49ac87f9c0419803dd11c` |
| AGENTS.md | `37658c72eb33805fb63d1b17764aa351e46fe8469df2a9bc2e2fa3175d0e0f52` | `b5f0c8ce25a6d0c4266446be8865a150dd388c4232b9611589583b97fd284800` |
| README.md | `a51a640a81bf863905b8afac8872e113a869b0526308652b2e8229084c1fc9a6` | `58cbf2d73e841cb0275df4a2a83e089c39a2c8e2de18287a2edf23eb4fea06a4` |
| docs/roadmap.md | `3de88f1768b1738c96bab7bbc268706c044e2d1930ccf16fafb410e618b1609a` | `00dfeda5bc61f360a80d946dded9e9b0ecd6236ccc9cee16703cfe36db51f73a` |
| docs/development-process.md | `4f451b70679f750036741c3bbb04ca0b0c37e2338af735ce03ced5657b3ee915` | `d875f616cc88d96734357e796084cef8958ca45e5ae977d2abf14a51c2e21c47` |
| docs/pipeline.md | `76a4059996aff483b41e2c687a2172f2975bd95fd8a1e8d82c04769367c02cbc` | `48a007946b6bf7f97c2fdae04f910fa1f07158c60b32dae05f1295ad83b2b184` |

Read the entire two-file diff. The genuine removed-directory fixture now verifies actual directory mode and absent pathname without a nonportable link-count assumption. Genuine removed regular-file metadata must still have regular mode and actual link count0. Separate explicitly modeled directory-zero tests preserve the zero boundary in executor `_paths`, ExecutionQueue and PipelineJournal; the APFS-style count2 helper contract honestly models only that field. No production guard, skip, timeout, authority or process-protocol change accompanies this correction.

Independent current focused command: bundled Python3.12.14 `-m unittest tests.test_safe_config_race tests.test_private_sqlite_stat tests.test_executor_queue tests.test_pipeline_journal tests.test_pipeline_cli -q`: **96 tests in8.899s, OK, skipped1, exit0**. The existing skip is unavailable symlink privilege; physical junction/hardlink controls ran. Private focused log SHA-256 `a061237f426717f8a7a08eb15cdfa2ca3144ee05fb6a17f931a561591d592d3b`. Source hashes and current DEV receipt were verified after this run. Independent DEV also records nine directory-count0/2/17 negative controls across all three guards; that separate evidence is not relabeled as this reviewer's run.

The whole required command has genuine completed CI coverage for the identical production code at C: Windows713 tests/1372.835s/one skip and Ubuntu713 tests/192.513s/seven skips. The Windows complete log and digest are preserved above; the Ubuntu summary was independently read from job125258117146. The e59 macOS713-test run still has its two recorded fixture failures and is not declared green. These completed full-C observations plus current independently tested fixture-only correction support this functional stage verdict. No complete local713 result or complete corrected macOS run is invented; the disappeared local session remains incomplete with unknown termination cause.

The original a569 macOS policy_revoked cause remains unproven, even though the later current-code workflow case passed. Both rejected-head histories remain above. A new exact final candidate must pass **all six required push/PR platform CI contexts**, with fresh independent whole-PR head/base acceptance, before merge. The coordinator must also preserve the serialized prior-main barrier, then exact-main CI/postmerge acceptance and automatic Issue closure. This TEST verdict does not waive any of those gates or predeclare their future success.

Rehashed all1054 pilot artifacts against their immutable manifests after current verification:166 original,445 V2,443 V3 unchanged. Their outcomes and the qualified installed six-role source8981c6d receipt remain intact. That fixture-transport/publication-disabled pilot supports local process/protocol behavior only; it is not a model execution of the later checkpoint, priority, sidecar or fixture changes, live GitHub publication, night/service readiness or self-evaluation acceptance. No extra installed model run, pilot mutation/replay or unknown-state reset was used.

Only this test report and private verification evidence were written by this reviewer. No production/test/docs/card edits, commit/push, GitHub write, account/configuration/global setting or model invocation occurred. The candidate source remains held at these exact bindings for integration.


## Same-Issue postmerge timeout recovery — scoped functional TEST ACCEPT

2026-11-02, independent reviewer: **ACCEPT this configuration-only recovery**, exact base `d5cf8953b70caf5329d5173b7fb4a15eaa4df978`. Original test history remains the unchanged prefix SHA-256 `e6edf44d49b0d5de73b65028ee3efb512acd7565357fb7f8c15237755cc225c9`. The only operational delta is `.github/workflows/postmerge.yml` timeout15 to45 minutes. Independently compared the entire normalized base/current workflow: exactly that single substitution, no other byte change. All tracked product modules and tests remain canonically identical to the accepted merged base.

Workflow raw SHA-256 `7dd1c8797dbddf1232ab88985d8dfbbba50c9419d40618a7935ed0e6028233ee`, canonical `194fca1f6743aac62dbbf7b29e15a2ff402f70e92ff260a91b66bc9c79a1d570`. Recovery note raw/canonical SHA-256 `ce77c22d21b6b4148d51122214d803508181443c9c732ee6fc48d45a936aacdf`. Current independent DEV acceptance canonical SHA-256 `8e6cee7741aa56212aab75ff11775b2f744b45b76101ce8f7beadc6b712124ca` verified. Read the complete workflow: unchanged exact merge-commit checkout, three-platform matrix, Python3.11 full-suite command, read-only permission, persist-credentials=false, always-run failed-outcome export/artifact and explicit failed-test gate. The longer finite job budget does not alter test assertions, source/provenance checks or publication authority.

Independently queried job125296237186 in run41451105738: cancelled,13:13:27Z to13:28:43Z, explicit GitHub annotation `The job has exceeded the maximum execution time of 15m0s`. This is an observed timeout, not a passing postmerge run. The preceding independently captured Windows full-suite duration1372.835s exceeds15 minutes, supporting a bounded45-minute recovery. Older a569 policy_revoked cause remains unproven and the incomplete local attempt remains incomplete.

Located relevant tests with rg, then independently ran bundled Python `-m unittest tests.test_merge_events tests.test_github_source -q`: **32 tests in0.355s, OK, exit0**, no skips. Private focused log SHA-256 `6e127aa4935ce007d2f8b3b5ad15e260b174cc82f688d1a87673b63824403648`. These cover merge-event and source/provenance contracts; they do not simulate a45-minute GitHub runner or constitute a new full suite. No full local repeat or installed-model run was needed/performed for this timeout-only delta.

Fresh six-context exact-head full CI and independent whole-PR head/base approval remain required before recovery merge. The same Issue16 remains incomplete until a successful new exact-main postmerge workflow, independent main acceptance and publisher-driven automatic closure. No cancelled outcome is relabeled, no unrelated merge barrier is passed, and no journal/delivery is reset. Prior1054 pilot artifacts and their qualified source8981c6d outcomes were not modified or newly executed. This reviewer changed only this appended test receipt, its task-card test digest and private verification evidence; no source/workflow/shared docs, commit/push or GitHub write.
