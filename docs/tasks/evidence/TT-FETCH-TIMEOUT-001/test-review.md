# Independent fetch-budget TEST acceptance

Reviewer: /root/fetch_timeout_test_acceptance

Verdict: APPROVE the scoped independent regression evidence for Issue63 / TT-FETCH-TIMEOUT-001. No blocking test finding. The coordinator's required complete suite, exact-head/base PR acceptance, current CI, merge and postmerge cycle remain separate gates; this report does not claim those completed.

## Exact reviewed product bytes

Base: exact main4875381be68282a7ad77ab7b1c5a3898cbc09304. Product checkout: task-tower-fetch-timeout. These raw SHA256 values were independently recomputed and match the development review:

| File | Raw SHA256 |
| --- | --- |
| AGENTS.md | 78befd653272d181565a87d16821c4223e9d09fee0e9660e5131e766a3bcf163 |
| README.md | d58cc0d68b6b1858d6a279b1acbde7892146369f4b564acac48aebd3361fdbd8 |
| docs/postmerge-worker.md | f44f6231d4a38c5b0260d0adbc71c3b326102bbc4d029d658250033afab4e662 |
| docs/superpowers/plans/2026-11-03-postmerge-fetch-budget.md | 762e1e554e526a9a4d09adb4ce3a4d7aece98b5e8d7eac5f107ad2d8cd60d806 |
| task_tower/tasks.py | f08ef728e6a19a22b9a43dbcdd94d5c35c56f27334ab7245960a703088271a65 |
| task_tower/postmerge_worker.py | cb47197c66737129854350a1b1c2a115b3c0c135695f0172fd792df6d8db9ced |
| tests/test_postmerge_fetch_budget.py | ef3d82ffb2e5d1f617ccc9ecd5cb69f2626ec0235856d8502258f67115b5ad53 |

## Independently executed verification

Executed Python unittest modules test_postmerge_fetch_budget, test_tasks, test_postmerge_journal, test_postmerge_worker, test_github_source and test_github_publication_acceptance:71 tests in29.053s, OK with one skip because symlink creation was unavailable. Log runtime/fetch-timeout-independent-targeted.log rawSHA256738793a2db2602b6411256c295ef97e604071bd180661e2b6e16e06a49307efd.

These include actual fixture Git/journal/reviewer/publication routes alongside mocked remote-boundary failures. Checked the new budget routing, unchanged local10s default, check=True, timeout/nonzero failure before source/review, origin rejection, task evidence freshness, durable claims/review recovery, workflow/artifact provenance and publication-boundary tamper rejection. No network GitHub or actual Issue-close effects were produced by this independent suite.

Also executed an independent real-process budget probe through the actual tasks._git wrapper. The transport executable was substituted with an actual Python process sleeping10.3s, while retaining the wrapper's timeout/check/capture options. Default local10s rejected with actual TimeoutExpired after10.016s. Explicit fetch60s accepted the same delayed child after10.328s. This demonstrates the behavioral regression beyond the old ten-second cutoff rather than only inspecting mock arguments. It does not test live GitHub transport or hard descendant cleanup.

Probe script runtime/fetch-timeout-independent-real-budget.py rawSHA2564f568b3cf74c5830d2fcc998a7d191a044df50e2d7a67972246227c15ae0b243. Result runtime/fetch-timeout-independent-real-budget.json rawSHA2562ab7afa3752432ab24565533c3d829186496ecc83e30fed6927e3f82f7916b02.

## Live recovery observation and limits

Read the product postmerge SQLite only using mode=ro. The actualM4875381 review progressed from running to done, and the genuine native review result says approve with findings[] for the exact commit. Its summary explicitly relies on the supplied verified three-platform CI bundle because its local Python test attempt could not start. The historical D5d5cf8953 failed/blocked record remains present. No live state was changed by this reviewer. Automatic publisher closure and Project projection were not verified by this TEST report and remain coordinator-owned.

The complete product suite was still running in runtime/fetch-budget-full-tests.log at report time. This report is not a whole-suite result, PR review or authorization to bypass the prior-main acceptance/Issue16 closure barrier. Native POSIX, deferred Claude, hard process-tree deadlines and unattended readiness are outside this change.
