# Task1R-L fix round1 — fresh watch runtime guard

Implementer /root/groups18_task3a_acceptor; **pending same independent acceptor re-review**, not self-approved. No implementation commit/push or full suite. Only task_tower/pipeline.py and tests/test_pipeline_watch.py changed from rejected candidate.

## Preserved rejection and cause

Read complete independent review runtime/groups18-task1rl-independent-review.md SHA256825bd566f3cdc3fd1152db11883fedbfafbc97423dcb570dd5016eab66f648f2 and its actual-file reproducer before changing behavior. Prior14-file freeze SHA256f42ec55e46a53e22627d38521a028847b0645ed63da41e306cf285b324582584 and candidate diff43b4d87f622f6b6401fde273e974bdd2e2f4b3289e2327b05d7699007b02ab36 remain unchanged historical artifacts.

Root cause confirmed: watch_tick guarded cached config, then reloaded actual files but compared only pipeline policy_sha256. Upgrading only executor JSON v1 to v2 leaves that pipeline SHA unchanged; fresh executor2 could therefore reach journal.recover/helper construction under cached max_active.

## Meaningful RED and minimal fix

Added CapacityReloadTests to existing test_pipeline_watch.py. Disposable actual JSON files pass through actual pipeline._runtime and both actual loaders: cached executor1, fresh executor2, unchanged pipeline bytes and equal pipeline policy_sha256 are explicitly asserted. Recovery sentinel and helper constructor markers prove first-effect order, and watch state/missing journal remain unchanged.

Second regression starts the genuine local watch controller with no helper/role process. Fresh-file mode refusal propagates through the existing watch finally/_shutdown; it must still positively stop/release that controller with zero workers/dispatcher. No cleanup Boolean or stage approval is fabricated.

Before production fix: approved Python -m unittest tests.test_pipeline_watch.CapacityReloadTests -v returned exit1,2 tests1.385s,FAILED2. First failed at recovery reached before fresh capacity guard; second at helper reached. Preserved runtime/groups18-task1rl-fix1-red.log. This is the actual reviewed bypass, not only a cached synthetic version2 dictionary.

Production fix is one line: require_legacy_capacity(fresh) immediately after _runtime(args), before SHA comparison, recovery, watch state changes or helpers. Existing cached guard, native-platform precedence, v1 return shapes and watch finally shutdown/cancel semantics remain.

## Actual focused verification

Using C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe:

-m unittest tests.test_pipeline_watch.CapacityReloadTests tests.test_pipeline_cli tests.test_pipeline_shutdown_recovery tests.test_pipeline_platform tests.test_pipeline_watch.WatchTests.test_slow_source_helper_does_not_block_watch_and_cancels tests.test_pipeline_watch.WatchTests.test_cancelled_owned_action_is_contained_and_fenced tests.test_pipeline_watch.WatchTests.test_clean_dead_ready_run_cancels_after_profile_revocation tests.test_pipeline_watch.WatchTests.test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain -v

**40 tests32.145s,OK1skip, actual completed shell exit0 and EOF.** Log runtime/groups18-task1rl-fix1-focused.log; exit marker runtime/groups18-task1rl-fix1-focused-exit.json. Skip is Actual unsupported host regression on actual Windows, not skipped cancellation coverage. Both new regressions and real cancellation/shutdown/lock/slow-source controls passed.

No redundant365-test rerun or full suite was launched. Original broad import-error result and corrected migration59 result remain exactly as recorded; this correction does not relabel them. Root owns eventual full verification after code approval.

## Corrected source package

runtime/groups18-task1rl-v2-source-freeze.json binds all15 candidate files: prior14 with corrected pipeline.py plus new watch test file. Verified all other13 prior owned file hashes unchanged; removing the unique new guard line reconstructs exactly the old pipeline raw hash. No unrelated source correction.

- Corrected pipeline.py raw SHA256e7ea181a8bda0582116f1c44baa5f51118e74e809354733771882aa4a95f0964.
- tests/test_pipeline_watch.py raw SHA256e251db568d3dc18052e64f4b02f7a931e275a689fae1b6bb5795b159b574663d.
- Scoped two-file diff: runtime/groups18-task1rl-fix1.diff.
- Complete corrected candidate diff including new capacity_policy helper: runtime/groups18-task1rl-v2-candidate.diff.
- git diff --check clean; only line-ending conversion advisories.

No source journal/schema/event, registration, private installed config/live user DB, provider/auth/model/remote/probe changes. Tests use disposable fixtures and their existing contained Python/Git controls. Current native Windows scope, POSIX61 deferral and mandatory current hot recovery65 remain. Whole18/PR/main/night readiness not claimed.
