# Independent final test acceptance

Reviewer: independent github_publication_spec_review agent, 2026-11-01.

Disposition: accepted for the configured trusted publisher credential holder boundary and conservative cross-mode reconciliation scope described in code-review.md. No blocking test failure found. This does not claim live Issue 9 closure or watcher rollout.

Command executed from C:/Users/sibiya666/Documents/projects/vizualization/task-tower-github:

```powershell
& 'C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -v
```

Actual runtime: Python 3.12.14, Windows-10-10.0.19045-SP0. Result: 210 tests run in 62.335 seconds, OK, 2 skipped (208 passed), exit code 0. Skips: test_refuses_symlink_state_directory (symlinks unavailable) and test_rejects_symlinked_database_parent (symlink creation unavailable). Full captured output: independent-tests.log. No implementation changes were made for this acceptance.

Read code-review.md and audited focused publisher, production-client acceptance and publication-books tests. They exercise real worker acceptance with temporary Git repositories, durable SQLite journal and subprocess reviewer fixtures; counters assert publication/retry does not trigger another reviewer. Deterministic GitHub transports exercise state-only close, unchanged Issue prose, duplicate tick, uncertain POST/PATCH recovery, and author/rejection/local evidence changes before close. The real-client comparison-route regression checks the production path validator while retaining traversal rejection.

Book coverage checks actual API author trust and default denial, Issue-body non-attestation, wrong repository/Issue/task/immutable Issue identity even with recomputed receipt identity, malformed evidence and review, missing/current failed CI, non-main commit, newer lifecycle rejection, old approval reposting, malformed lifecycle and the actual aggregate done projection. Existing Actions receipt tests remain included in the full discover run.

Limits: transport tests do not make live GitHub mutations. Publication claim tests use two SQLite Journal instances and controlled lease times, not simultaneous OS processes. Cross-mode preexisting workflow or rejection history is conservatively denied pending explicit reconciliation. The GitHub lifecycle-read/Issue-close interval remains non-atomic. Windows symlink protections were not executable in this environment. Installed watcher replacement, actual Issue 9 lifecycle receipt/close, remote book projection, and duplicate live tick remain required pilot evidence.
