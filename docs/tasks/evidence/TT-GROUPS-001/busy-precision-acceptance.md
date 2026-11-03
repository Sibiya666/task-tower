# Busy-deadline numeric precision correction

Windows CI41658172817 at47b ran935 tests2140.005s and failed only the busy-writer test: deadline-start became60.00000000000003 while the original source had added exactly60. The raw log remains runtime/ci-groups18-47b-windows.log. A deterministic227.109 regression first reproduced that exact false failure. The test now compares original absolute deadline<=observed_at+60 and positive ordering, avoiding subtraction cancellation. No epsilon, larger budget, retry, skip, sleep or production change was introduced.

Root five affected cases passed14.536s, actual14.797s, exit0, cleanup/full EOF/unchanged source; runtime/verification/groups18-busy-precision-green, stderr SHA7aa9ad7bc3d3d6345b34620d823ab7b26e1a80fafdf40058adf13f16c949d9f5. Real SQLite held-writer, <=5000 requested busy timeout, original shared deadline, remaining outer budget, no-backup and unchanged database assertions remain.

Actual in-memory fault variants set SQLite busy_timeout5001 and renew the actual post-inspection deadline by1. Each runs one real contention case and fails1/errors0 as expected. Contained wrapper11.531s, exit0/cleanup/full EOF/source unchanged; runtime/verification/groups18-busy-precision-faults. Deterministic initial61-second and expired-window cases also remain rejected. Old failures and fault logs are preserved.

Independent reviewer cea5df5d-9b37-4603-b9c6-dce56efa06cd APPROVED the exact one-file source in busy-precision-source.json. Actual46.234s, exit0, cleanup confirmed, complete127215 stdout/8449 stderr, source/executable unchanged; verdict busy-precision-review.json. Reviewer inspected evidence without rerunning tests. No full-suite, whole18/65, PR/main or night-readiness acceptance is claimed. Fresh CI remains required.
