# macOS CI follow-up

2026-11-01. Original PR CI reported 15 fixture errors: the 12 shared project-worker tests and three acceptance tests passed macOS temporary paths through the system `/var` symlink. Canonicalizing fixture paths with `Path.resolve()` fixes the setup without changing production path validation. A distinct reviewer accepted the scoped fixture diff; subsequent macOS jobs passed.

A separate macOS run exposed a process-cleanup race: timeout group SIGKILL and parent wait succeeded (`exit_code=-9`), then redundant cleanup signaling returned EPERM. Apple's [XNU group-signaling implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sig.c) excludes zombies and may return EPERM when no signalable group members remain. The failure is consistent with a temporarily zombie-only group; no claim is made that a Windows reproduction proves that kernel state.

The fix retries only Darwin EPERM after a successful timeout group kill and parent reap, for at most 0.5 seconds. Persistent EPERM, EACCES, normal-exit failures and other platforms retain cleanup failure. Deterministic regression first reproduced cleanup_failed instead of timeout; seven new cases then passed. Original real parent/child tests are retained. A distinct reviewer found no issues and ran 14 process tests successfully.

Final local full command: `python -m unittest discover -s tests -q`. Result: 172 tests, exit 0, 34.166 seconds, two Windows symlink privilege skips. Real macOS CI for the final follow-up commit remains the platform verification.

Separately, the already-running legacy worker automatically received PR 7's merge event, obtained successful CI for all three platforms, ran its independent reviewer and recorded TT-POSTMERGE-WORKER-001 done at commit `5a219ce5dcec0be697d749cc5040fb49919d25ad`. The task card and exact postmerge report are preserved with this follow-up. The reviewer explicitly noted that its own read-only sandbox could not rerun the suite; approval used verified CI plus source and prior evidence inspection.
