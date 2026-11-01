# TT-MERGE-HOOK-001 independent TEST acceptance

Reviewer: independent test acceptance agent /root/merge_hook_test_acceptance; distinct from implementation. Date: 2026-11-01. Verdict: PASS for local TEST stage and static workflow contract, scoped to the source hashes below.

Read repository AGENTS.md, docs/merge-events.md and docs/superpowers/specs/2026-11-01-merge-event-design.md. Applied verification-before-completion: conclusions follow fresh executed checks.

## Executed checks

Runtime: C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe, Python 3.12.14 AMD64. Platform: Windows-10-10.0.19045-SP0. Working directory: task-tower.

Command: `python -m unittest discover -s tests -v` using the runtime above. Exit 0; 69 tests in 17.427 seconds, 68 passed and one skipped (`test_refuses_symlink_state_directory`: symlinks unavailable). This includes eight merge-event tests and evidence normalization, legacy raw hashing, stale text, and real Git CRLF checkout regression tests.

Separate subprocess CLI exercise used a temporary fixture outside the repository and a nonexistent nested output parent. A closed merged PR for owner/repo, number 12, uppercase 40-character A SHA and duplicate Task-Tower markers exited 0 and created the parent/output. Inspected JSON: checks=passed; task_ids=[TT-MERGE-HOOK-001]; merge_commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; platform=windows; run_url=https://github.com/owner/repo/actions/runs/123; kind=pull_request.merged; version=1. Delivery key: 5d52f70d289ff8f04bf75cc306056ad0442d399ebe4c96e1d7e888a691c40325. This is synthetic fixture data, not a real Actions run.

Changing merged to false exited 2 with `invalid merge event: pull_request.merged must be true`. Existing output bytes were unchanged. Repeating against another nonexistent output hierarchy exited 2 without creating its directory. Temporary files were automatically cleaned up.

## Static workflow review

postmerge.yml listens to pull_request.closed on main, gates on merged=true, checks out the exact merge_commit_sha and declares Linux/macOS/Windows runners. Only contents:read permission is declared; checkout persist-credentials=false. No explicit secrets input or write permission is configured. PR body is read as JSON by Python, not interpolated into shell source. Tests continue on error so export/upload can publish a failed checks result; the final always-conditioned `Fail if postmerge tests failed` step exits 1 whenever test outcome is not success. Upload includes hidden files for .task-tower. Export is gated on successful checkout/Python setup. No actual GitHub Actions execution was performed or inferred; local Windows execution does not establish macOS/Linux runtime success.

## Source identity (raw SHA-256)

- task_tower/merge_events.py: 1b5a67c40e19d667f43ff2ad7e7bc1a70fc6d74c24ff25828016a1b5b9815d00
- task_tower/tasks.py: ebbab6f0a2003d127e2ea87ba70c67d1aadb55221fbca9debefe73ebe12f81cc
- tests/test_merge_events.py: 6f614ec473a8d5701882f8d051f5dbf5ec3aad17119c914452fdab45d4c78ff6
- tests/test_tasks.py: 7fd86fca4021b3db988c134613ebccd94c9d8be559d7c5c8c15207321a387e42
- .github/workflows/postmerge.yml: 01d87ec61cce50d622b22d5c49fbdc8564495750b71a6c2e3a0403539124e1fb

Only this acceptance report was written by this reviewer. Source files and task cards were not edited; no commit or push. Legacy bootstrap stale evidence remains unresolved by design. This report does not mark either task done and does not claim independent final postmerge acceptance or automatic local synchronization.
