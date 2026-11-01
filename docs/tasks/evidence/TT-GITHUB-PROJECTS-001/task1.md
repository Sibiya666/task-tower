# Task 1 implementation evidence

2026-11-01, isolated `task-tower-github` checkout. No overlay changes, commits, pushes or remote writes.

Python: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

TDD: initial focused run failed because project connection/store modules were absent. Added implementation and observed first four tests pass. A subsequent stage-validation test failed (invalid stages were accepted), then passed after stage-order and evidence validation. A done-verification integration test failed (`needs_input` instead of remotely proven `done`), then passed after fresh verifier integration. Connections CLI first failed absent main, then passed after implementation.

Command: `python -m unittest discover -s tests -p test_github_projects.py -v`: 10 tests passed, including namespaces, pagination bound, failure isolation, HTML escaping, import idempotency, historical evidence preservation, pinned library sources, metadata validation, private connections lifecycle and fresh completion verification.

Command: `python -m unittest discover -s tests -v`: first integrated run 143 tests passed with 2 skipped in 32.629 seconds. This preceded final completion verifier integration and is not the final whole-diff verification. Parent agent owns independent review and final rerun.

External services are substituted at the transport boundary in focused tests. No claim of a real Issue import, physical runner registration, board mutation or accepted project completion follows from these unit results.

Follow-up full run: 146 tests passed, 2 skipped, 33.855 seconds (`runtime/task1-final-tests.txt`). After this run a focused regression corrected repository-root URL trailing-slash redirect handling: 10 focused tests passed in 0.065 seconds. Final whole-diff verification remains parent's responsibility.

Real read-only smoke after that correction: `python -m task_tower books --connections ../runtime/github-projects/connections.json --format json --output runtime/books-smoke.json` exited 0; 41 Markdown library entries, zero source errors. This used existing credential resolution, no remote writes, and no credentials/configuration were copied into tracked evidence. The actual repository contained zero Issues at smoke time, so Issue pagination and import remain transport-fixture coverage only.

Independent acceptance found three consequential failures: books could overwrite the connections file, overwrite an existing user report, and silently discard malformed Issue rows. Reproduced all three failures before correction. Added default no-clobber atomic publication, explicit `--overwrite`, input alias protection (samefile/hardlink and symlink/reparse checks), source-directory protection, and malformed-row rejection. Connected checkout report destinations must be `runtime/` or `.task-tower/`. Added focused hardlink/source protection and lifecycle comment tests. Books now reads the project worker's bounded `issue_lifecycle` helper for managed tasks and still independently verifies done receipts.

Command `python -m unittest discover -s tests -p 'test_github_projects*.py' -v`: 20 tests passed in 0.123 seconds after acceptance corrections. A transient board fixture error during concurrent integration (missing comment request method) was corrected by the owning reviewer/agent; final combined focused run has zero failures.
