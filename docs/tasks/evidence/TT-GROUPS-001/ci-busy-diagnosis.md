# Task1R-L CI busy-writer diagnosis and isolated test correction

Systematic Debugging before changes; author /root/groups18_task3a_acceptor. Pending fresh independent test review, not a production fix or Mac qualification. No commit/staging/push/full/CI retry or native group/model/provider/auth/live-state effects. Only tests/test_group_migration.py changed for this task. All10 frozen Task3B-R source hashes and draft spec0e1070a4/plan21a59e4a remain unchanged; original failed CI/reviews/source freezes and unrelated runtime-escaped-library-freeze.json preserved.

## Exact failure and what can be concluded

CI41606865860 at2967c633eac8d32bc048f70b47dd33d404456e17: parent reports Ubuntu/Windows successful. Retained macOS log shows882 tests291.433s,FAILED1/29skip. Only failure: old test_busy_writer_wait_is_capped_and_never_creates_backup asserted whole migrate_groups duration7.753076832999994 <7 at line683. That interval includes all private-path/pin/schema/RO integrity/owner/snapshot preflight before BEGIN IMMEDIATE. Actual contract is SQLite busy timeout<=5000ms under a shared60s migration deadline; the old test applied its busy-wait allowance to both phases together.

The Mac log has no real-BEGIN timing or observed PRAGMA, so its excess cannot be attributed precisely to preflight versus scheduler overshoot inside SQLite. This report does not claim Mac's timeout was5000 or its busy wait was<7, or guarantee a future Mac pass. The definite test defect is conflated measurement. The corrected test still fails actual busy-wait wall time>=7 and reports phase diagnostics.

## Pre-fix real-SQLite evidence

Read-only git archive exported2967 task_tower/tests into runtime/groups18-ci-busy-source2967. Archive export uses CRLF while Git blobs/working-before use LF; normalized source matches. No checkout/Git mutation. Runtime groups18-ci-busy-diagnose.py delegates real sqlite3.connect/Connection.execute, reads actual PRAGMA busy_timeout before actual BEGIN IMMEDIATE, measures its duration and shared deadline, observes actual held writer.in_transaction and real SQLITE_BUSY5; no result or lock response is fabricated. Original DB bytes/no backup are checked.

Exact2967 normal: actual timeout5000ms, real wait5.531s, preflight/other0.047s,total5.578s. Writer held before/after; original unchanged/no backup. With controlled2.8s runtime-only delay at existing after_inspection checkpoint: same5000ms, wait5.547s, other2.844s,total8.391s; old total<7 predicate fails while lock policy is unchanged. This demonstrates causal fixture conflation, not CI's unknown exact phase timing.

Run the ORIGINAL unmodified2967 unittest with that delay:1 test8.401s,FAILED1,exit1; original assertion8.375 not less than7. Log groups18-ci-busy-original-red.log preserved.

WIP comparison: normal5000ms/wait5.547s/other0.047s/total5.594s; delayed5000ms/wait5.531s/other2.844s/total8.375s. Same observed migration-v1 lock behavior; final correction verification uses exact2967 production independently of WIP. Windows observed5000ms configuration produced5.5s real wall waits; no claim that this is <=5s wall time. The original test already provided a7s scheduling allowance, unchanged by the correction.

## One-test-only correction

The existing test now uses a delegating Connection factory/subclass to read actual SQLite busy_timeout and time only actual blocking BEGIN IMMEDIATE. It asserts one attempt, writer held throughout, real wrapped SQLITE_BUSY5, positive actual timeout<=5000ms, and UNCHANGED real-wait wall allowance<7s. It observes/delegates the actual after_inspection checkpoint, verifies its shared deadline equals the writer deadline, positive remaining budget<=60, whole operation<60 and deadline restoration. Source bytes unchanged/no backup remain checked. Failure messages include wait,timeout,total,preflight/other and deadline. No production/schema/SQL timeout setting changes.

## Actual verification and controls

Python: C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe. Corrected source snapshot runtime/groups18-ci-busy-corrected2967 contains identical archived2967 production, with ONLY corrected tests/test_group_migration.py substituted.

From that snapshot, process-local PYTHONPATH=tests:

`-m unittest test_group_migration.MigrationTests.test_busy_writer_wait_is_capped_and_never_creates_backup test_group_migration.MigrationTests.test_deadline_expired_after_backup_rolls_back_and_preserves_failed_backup test_group_migration.MigrationTests.test_reader_blocking_commit_leaves_exact_v1_and_retained_backup test_group_migration.MigrationTests.test_replaced_journal_before_writer_open_is_rejected_without_touching_replacement -v`

Actual4 tests6.141s,OK,exit0,no skips. Log groups18-ci-busy-corrected-focused.log.

The same groups18-ci-busy-original-red.py pointed to corrected2967 applies the identical runtime-only2.8s preflight delay to the named test. Actual1 test8.423s,OK,exit0. Whole time may exceed7 without hiding a busy-budget violation. Log groups18-ci-busy-corrected-slow-preflight.log.

Negative fault control groups18-ci-busy-overbudget-control.py delegates every SQL statement but REALLY sets SQLite PRAGMA busy_timeout=6000 via Connection subclass. Corrected test actual1 test6.692s,FAILED1,exit1 at6000 not <=5000; real wait6.594s,total6.656s (<7),writer held. Thus the test rejects an actual over-budget setting even when the wall threshold would pass. This is an expected RED, never a passed suite; no returned PRAGMA/BUSY is mocked. Log groups18-ci-busy-overbudget-control.log.

## Isolation for coordinator commit/review

Read-only git show confirmed HEAD049db662a507c7fa4c7a0f6429acd576046c7cb3 and2967 have IDENTICAL test blobs/raw SHA256f80edde0be88ff036a071e3643595df51e8d23cac4cf38bae63a7370f0276c32, equal to saved working-before runtime/groups18-ci-busy-test-before.py. This file is NOT among10 WIP files; no prior Task3B hunk exists in it. Current working test and corrected2967 snapshot test both have raw SHA2566e001382c32e79abf0ff03da174d52b6bed6f38e140f5505f255d71070e535f4.

runtime/groups18-ci-busy-test.diff is exactly git diff049db -- tests/test_group_migration.py:1 file41 insertions/4 deletions, SHA2569d62e18adabe2b61e07e470ce2ed98c792b9016cf7930d88fb9b8198cef3e809. No source/docs/WIP hunks are in that patch. git diff --check completed exit0. Root can review/commit this exact file/hunk plus scoped report evidence; never blanket stage this checkout.

runtime/groups18-ci-busy-test-freeze.json records before/after/diff and all evidence hashes. Archived diagnostic relevant source SHA256: group_storage.py7efc29660c1ea723f1c2472b152cf4230c17dfaa274e36c92d92c7525078a0e5; pipeline_journal.py149a892251990e26d7ca18abdcf7cf4cea4b2f1561cf9afe29b16e9a6fe5cf88; archive original test20a13c19d911f5708e1f3aa069ee9b7c40b1b8e7f0df6378fefd84146dea4c45 (CRLF export, LF-normalized equal to original blob). Production files in original/corrected snapshots are byte-identical.

Root must obtain fresh distinct independent TEST review before preservation/commit/new exact-source CI. Mac remains failed until a reviewed corrected source actually passes; no retry/disable happened here. Task3B production/docs remain held, not approved by these migration tests; whole18/current Windows65 remain incomplete, nativePOSIX61 deferred.
