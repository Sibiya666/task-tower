# Books test progress — not test acceptance

2026-11-02. Implementation source through `ba125ca` plus the test-only cwd correction is independently accepted in the current R2 development review. The task card records development accepted and test/postmerge pending. This progress report grants no test, PR or main acceptance.

Actual coordinator complete CLI run after migration/status corrections: `python -m unittest discover -s tests -q`, **455 tests, 138.231 seconds, OK, 4 skipped**. Python overlay suite: **18 tests, OK**; those modules were unchanged by the corrections.

The first complete corrected Node run from the documented `overlay/` directory failed because the new test fixture imported the repository's tests package relative to the inherited cwd. The implementer and independent native reviewer reproduced root success versus overlay failure. The test-only fix sets its process WorkingDirectory to the explicit repository root; production already did so. No assertion or product behavior was weakened.

On the final test-file bytes, the implementer ran the complete documented Node list: **42/42 passed, 16.953 seconds, exit 0**. The independent native reviewer separately reproduced both cwd commands and **42/42** for the full list. The separate development reviewer reproduced the corrected overlay invocation **2/2, 7.521 seconds, exit 0**, rebound all 34 reviewed artifacts and accepted R2. See the preserved rejected and accepted histories in development-review.md and task5-native-review.md.

The coordinator's actual native Windows PowerShell 5.1 smoke with the corrected BooksBridge exited 0. Independent R1 native smoke also exited 0 and regenerated matching fixture screenshots; its product source remained unchanged by the cwd correction. These are actual composition tests with deterministic data and synthetic DOM keyboard events, not physical input or genuine GitHub UI observations.

The authorized test window remains available for the user's manual Ctrl+B check. Automated Shift+F10 opened its actual world menu, but automated Ctrl+B did not open Books and Windows Graphics Capture timed out. The user's manual keyboard observation and actual configured Books refresh are still required. Issue #23 and its own GitHub Project are marked needs_input while this external gate is pending. The Issue is open; no PR merge or automatic completion is claimed.

## Manual keyboard gate failed

2026-11-02. The user explicitly confirmed in three replies that the visible test window did not open Books after clicking inside and pressing physical Ctrl+B. This supersedes the pending manual observation above: native keyboard acceptance FAILED. The failure is not attributed solely to automation. Root cause is under investigation across native composition focus/key routing, loaded assets and the test executable version; no cause or fix is yet established. Historical synthetic DOM passes remain limited to handler behavior. No test acceptance, merge or task completion is granted. Further confirmation of app access is unnecessary; access was already granted.

2026-11-02 follow-up: the user physically closed and reopened Books with Ctrl+B in the final corrected native window and confirmed success. The manual shortcut gate is now passed for the final native-keyboard-fix.md binding. Prior failure history is retained; broader test and integration gates remain separate.
