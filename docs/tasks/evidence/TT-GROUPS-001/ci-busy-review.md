# Independent test-only CI correction review

Verdict: **APPROVE** the single test correction. Reviewer: independent agent `/root/groups18_ci_busy_review`, distinct from the correction author. This is test-stage acceptance only, not PR/main acceptance or macOS qualification.

## Exact binding

- Failed CI: 41606865860, production source `2967c633eac8d32bc048f70b47dd33d404456e17`.
- Checkout parent: `049db662a507c7fa4c7a0f6429acd576046c7cb3` (reported documentation child; this verdict is bound to the exact patch and file bytes below).
- Scope: only `tests/test_group_migration.py`, 41 insertions / 4 deletions.
- Original raw SHA256: `f80edde0be88ff036a071e3643595df51e8d23cac4cf38bae63a7370f0276c32`.
- Corrected raw SHA256, independently checked: `6e001382c32e79abf0ff03da174d52b6bed6f38e140f5505f255d71070e535f4`.
- Patch `runtime/groups18-ci-busy-test.diff` SHA256, independently checked: `9d62e18adabe2b61e07e470ce2ed98c792b9016cf7930d88fb9b8198cef3e809`.
- All 46 tracked production files under `task_tower/` in corrected2967 were independently compared against actual 2967 Git blobs, normalizing CRLF to LF: identical. Read-only Git used per-command safe.directory, without changing Git configuration.

## Findings

No blocking findings. The spec (agent-groups-design.md, migration algorithm step 3) separates the one monotonic 60-second migration deadline from busy waits capped at five seconds and remaining time. Original source starts that deadline before read-only integrity/schema/owner/snapshot inspection. The previous assertion timed all inspection plus the writer wait against seven seconds; the retained macOS log confirms failure at whole-operation 7.753076833 seconds, without phase instrumentation. Its exact phase split remains unknown.

The replacement measures the actual SQLite `BEGIN IMMEDIATE` execution using a delegating Connection subclass. It reads the actual connection's PRAGMA immediately before the statement, never supplies a fake BUSY response, and preserves the seven-second wall allowance. It additionally rejects timeout settings above 5000 ms, requires one attempt and a real SQLITE_BUSY cause, checks that the real external writer remains in its transaction throughout, compares preflight/writer deadline identity, checks remaining/total 60-second budget and deadline restoration, and retains original bytes/no-backup assertions. There is no retry, skip, platform conditional, production change or raised busy threshold.

The extra PRAGMA adds a small observation before the blocking timer rather than replacing production lock behavior. The patch/checkpoint contexts restore on exceptions; writer connection closure also releases the lock on an unexpected exception, and the normal caught BUSY path explicitly rolls back. Exact-source `_db` closes its failed connection and wraps sqlite3.Error as ValueError. With a held writer, failure occurs before backup creation. This is consistent with the preserved safety assertions.

## Evidence inspected and independent probe

Inspected diagnosis, exact failed macOS log, original controlled-delay RED, corrected focused four-test PASS, corrected identical-delay PASS, and genuine 6000-ms timeout control RED. The negative control delegates actual SQL and sets real timeout=6000; it fails the new <=5000 assertion even though measured wait 6.594 seconds would satisfy the old seven-second allowance. The controlled preflight delay causally demonstrates the old measurement defect; it does not establish why the actual macOS runner exceeded seven seconds.

Fresh independent probe against actual2967 production plus corrected test: a SQLite authorizer callback inserted a real 2.5-second delay inside transaction BEGIN execution, then returned SQLITE_OK and let actual SQLite encounter the actual held writer. Actual timeout stayed 5000 ms; measured BEGIN duration was 8.015 seconds, total 10.562 seconds. The corrected test failed precisely at unchanged `wait['seconds'] < 7`, with real SQLITE_BUSY and held writer. Harness verified exactly one assertion failure, no test errors and timeout=5000, and exited 0 for the expected RED. Receipt: `runtime/groups18-ci-busy-independent-control.log`.

A preliminary probe placed delay in an outer Connection override before the candidate observer. It passed with measured BEGIN 5.562 seconds and other time 2.547 seconds (whole 8.109 seconds); its harness assertion failed because that injection was outside the intended measurement boundary. Moving injection into SQLite's actual authorizer established the intended fault. This distinction confirms the observed interval is actual SQL execution, rather than incidental wrapper/preflight work.

No full-suite rerun was performed by this reviewer. Existing Task3B source/spec/plan WIP was neither reviewed nor changed. This report approves no production or native-platform behavior. Fresh reviewed exact-source three-OS CI, whole actual PR head/base independent acceptance, serialized merge and exact-main postmerge acceptance remain required. The historical macOS CI remains failed until new corrected-source CI passes; no guarantee of a macOS pass is made here.
