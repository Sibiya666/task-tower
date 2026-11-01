# Live automatic publication: Issue 9

2026-11-01. Target: [Sibiya666/task-tower#9](https://github.com/Sibiya666/task-tower/issues/9), task TT-GITHUB-PROJECTS-001, independently accepted merge commit `a788cfd5e507e9fa75abc119a6c2c099a519c497` already in main.

The installed watcher was replaced only after tests/review. Its existing SQLite journal was retained. Activation held an immediate SQLite transaction while checking no active reviews and stopping the verified previous PID; no reviewer was interrupted. Private configuration maps only this task to Issue 9 and explicitly trusts publisher account Sibiya666. No GitHub close or lifecycle comment was issued manually by the chat.

Before activation, GitHub Issue 9 was open with zero comments; the local journal already held a done/approve result. Its result, input snapshot, evidence report and Issue prose were hashed before the pilot.

The first publication attempt failed before posting a comment; its generic error did not establish a root cause. The watcher retried automatically. It created [one lifecycle receipt](https://github.com/Sibiya666/task-tower/issues/9#issuecomment-6558366496) and closed the Issue as completed at `2026-11-01T13:09:09Z` (16:09:09 Moscow time), authenticated as the configured account. Durable publication identity: `a7755205b18ec5396c4ecaf819236b62a372e1fefd8cf69c778f5d89a850c54b`; journal publication state: published.

A separate normal `worker --once` cycle then returned exit 0 with the target active, local done and publication published. GitHub still had exactly the same single comment. Issue prose, journal review result, review snapshot and evidence report were unchanged. The review output files and report still predated activation, corroborating that publication did not launch another model review.

The public books CLI returned exit 0, task status done and no source errors using fresh remote verification and configured author trust. Thus this pilot exercised source -> independent local acceptance already persisted -> automatic receipt -> GitHub close -> book projection, including a real failed-publication retry and duplicate cycle.

Final implementation verification: 214 tests run, exit 0, 65.435 seconds, two Windows symlink privilege skips. Independent whole-suite acceptance recorded 210 tests before the final mapped-task guard/diagnostics additions; those additions separately passed scoped independent review and the 24-test focused suite. No claim of physical multi-machine execution or installed Actions acceptance runners is made. Existing conflicting lifecycle histories require explicit reconciliation; this pilot Issue had no such history.

Private before/after/duplicate snapshots and raw watcher logs remain outside product source under the installation runtime. Credentials and user project connections are not committed.
