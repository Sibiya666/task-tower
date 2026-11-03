# Task 6 R1 independent review — REJECT

Fresh reviewer `/root/books_native_smoke_impl`, independent of the Task6 implementer; 2026-11-02. This content-bound review is not PR/main acceptance or installed-Codex/live-pilot evidence. The historical `task6-review.md` rejection remains preserved.

## Exact scope and binding

Reviewed AGENTS, accepted R2 stage-pipeline specification and implementation plan, the entire new `pipeline.py`, CLI/watch tests and fixtures, and the actual Task6 shared integration diff: command routing, executor private-path handling, journal deadline/controller/ownership/serialization/recovery/publication gates, worker continuation and publisher ready boundaries. Also inspected current shared fixture portability diffs. The separate Root queue-sidecar correction is a separately accepted dependency, not work implemented by this reviewer.

Checkout HEAD: `6ff859791d0deed0dfe8608bb625e45ee48acc8b`; supplied origin/main snapshot: `918554a1e7f6dec10f81a366c1dececa845ff072`. Independently verified freeze manifest `runtime-task6-r1-freeze.json`, SHA-256 `9975cde339622f6e98f581e74bdecc7a3084fd4ea1cca096de1b6c48b90be03d`. All 19 listed raw and canonical file bindings matched before verification; all 19 raw bindings still matched afterward. This covers the manifest's 16 main/dependency rows and three separately owned shared-test rows, not just the three R1 edits.

R1 raw SHA-256 bindings:

- `task_tower/pipeline.py`: `77e508c0c0d83fefc2465b876a4b939a2c2f0a33eea4044e652c740b60f26210`.
- `tests/test_pipeline_cli.py`: `851fb5846d2868151feecd581c015891cb4a84c632125ab97c6f8d25f3fb80fd`.
- `tests/test_pipeline_watch.py`: `f453ab23f3210cf153807616d4dbba5eed5e62a138a5ed7026c0549da2d3f3ab`.

Additional reviewed bindings: specification `4fe7ff944bd39c59ba74e90ef10405c9020311fd3035554c0870d5e31648c72d`, plan `4af0a9f7114e3e253658455fc3f579dde91c935d6fd5d5971d30ef7511dea83c`, and unchanged guard dependency `task_tower/project_connections.py` `41d4efcf25021e1147ebfd22d32c5541f628f8991d0c59fe11e45118db7520c9`.

## Blocking finding

**P1 — concurrent journal workers can be rejected by a disappearing SQLite sidecar.** Independent unmodified `tests.test_pipeline_journal.CompetingJournalTests.test_real_competing_processes_cannot_exceed_capacity` failed: one actual child exited with `ValueError: Unsafe connections path`, from `PipelineJournal.__init__ -> _safe -> project_connections.safe_config_path`, line 79 (`if path.exists() and not path.is_file()`). The other children produced two claimed identities and `none`; capacity safety remained intact, but the supported concurrent worker path did not complete successfully.

That check uses two independent filesystem observations. If an ordinary SQLite `-journal` disappears after `exists()` returns true, `is_file()` returns false and the guard reports an unsafe path even though a missing sidecar is normal. The newer journal `_safe` catches disappearance in later `stat`/`samefile` operations, but calls this guard first and therefore does not cover the race. The separately accepted executor-queue fix does not remove this earlier boundary.

An independent deterministic probe created an ordinary disposable `pipeline.db-journal`, ran the actual `PipelineJournal._safe`, and coordinated another thread to delete that sidecar after `Path.exists()` captured its real true result and before `is_file()`. Only the observation/barrier was instrumented; guard return values were not fabricated. Result: `DETERMINISTIC_GUARD_FAILURE ValueError Unsafe connections path REMOVED True SIDECAR_EXISTS False`. Twelve additional batches of four unmodified journal children did not reproduce the race; that does not undo either the actual failing test or deterministic interleaving proof.

Correct the transient disappearance boundary using one consistent no-follow observation, while retaining rejection of real directories, links/reparse points and aliases. Add a deterministic regression rather than relying on repeated green races. No production or test source was edited by this reviewer.

## Original three findings

The original Ctrl-C ordering/budget finding is corrected: public work now shares `_shutdown`; stop is set before database access, one monotonic deadline bounds the caller, and unconfirmed ownership stays fenced. Independent real live-helper/exclusive-lock tests passed, including public parser/report/exit flow and retention of unknown state.

Unknown/incomplete public-work reports now return exit 1, while valid parked `needs_input` returns 0. Independent CLI exit tests passed. Positive CLI temporary roots are canonicalized without weakening the safe-path guard. An independent real Windows directory-junction temp-ancestor probe ran all 11 ControllerTests: **11 passed in 1.219s**, reparse attributes `0x410`. This is linked-ancestor portability evidence, not an actual macOS run.

## Independent verification

Used absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

1. `-m unittest tests.test_pipeline_cli tests.test_pipeline_watch.WatchTests.test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain tests.test_pipeline_watch.WatchTests.test_shutdown_budget_with_external_sqlite_lock_and_live_owned_helper tests.test_pipeline_watch.WatchTests.test_public_work_task_budget_stops_real_blocked_host tests.test_pipeline_watch.WatchTests.test_distinct_worker_processes_commit_push_and_create_one_pr tests.test_pipeline_watch.WatchTests.test_lost_pr_response_is_unknown_and_restart_never_posts_again -v`: **16 passed in 189.106s, exit 0**. Covers real fixture children, exclusive SQLite locking, contained shutdown, deadline, separate publication workers and no replay after a lost PR response.
2. `-m unittest tests.test_pipeline_journal tests.test_executor_adapter tests.test_process_pid -v`: **41 tests in 6.681s, failure 1, exit 1**. Failure is the concurrent-worker guard race above; the other 40 passed.
3. Real linked-temp probe: 11 ControllerTests passed as above. Deterministic disappearing-sidecar probe reproduced the error. Temporary junction and fixtures were removed through their local cleanup; no installed settings or user applications changed.

## Preserved uncertainty and limits

The author's first R1 69-test run had one unexplained `unknown` during six-role publication setup; its original fixture journal was deleted. Later author targeted/observed/standard runs passed, and both publication paths passed independently here. The newly reproduced guard race is a plausible source of operational unknown, but there is no evidence tying it to that original deleted journal; **the earlier unknown is not claimed diagnosed or fixed**.

No live GitHub writes, installed-Codex pilot, full-repository suite, three-OS CI, PR acceptance, merge, main/postmerge acceptance or Issue closure is established here. The residual concurrent-path failure blocks Task6 R1 acceptance despite correction of the original three findings.
