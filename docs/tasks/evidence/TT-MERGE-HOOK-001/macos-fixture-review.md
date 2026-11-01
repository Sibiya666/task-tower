# Independent review: macOS fixture paths

Date: 2026-11-01. Reviewer: independent Codex review agent.
Reviewed branch: `fix/macos-test-paths`, based on merged commit
`8d0bbc88a28cd954a8fa16fa731c92fd861e2d1c` (PR #3).

Verdict: accept the scoped fixture correction; no blocking findings.

The reviewed source diff only canonicalizes `self.root` with
`Path(self.temp.name).resolve()` in `TaskTests.setUp` and the shared
`ProjectFixture.setUp`, with explanatory comments. This is sufficient for the
reported macOS `/var` -> `/private/var` temporary-directory alias: subsequent
card and repository paths now begin at the canonical directory. `TaskCliTests`
inherits `ProjectFixture`, so the CLI subprocess cases also receive canonical
card paths. Temporary-directory cleanup retains its original owner and path.

Production `task_tower/tasks.py` is unchanged. `_safe_path` still checks each
component with `lstat`, rejects symlinks and Windows reparse points, and only then
resolves the path. Canonicalizing the fixture root before constructing paths
does not canonicalize a malicious alias passed to this function. The explicit
junction regression still creates its alias beneath that root and passes the
alias directly to `load_task`; it passed in this review. Existing outside-repo,
hardlink, stale-evidence, legacy-hash and postmerge-stage regressions also passed.

Fresh local verification on Windows:

```text
C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest discover -s tests -v
Ran 69 tests in 17.404s
OK (skipped=1)
```

The skip was `test_refuses_symlink_state_directory` because symlinks were
unavailable on this machine; the Windows junction regressions passed.

The parent supplied the actual GitHub run `41299727423` result: macOS failed
with 13 errors and one failure, while Windows/Linux passed and all three event
artifacts were published. That remote result was not independently re-fetched
in this scoped review. A successful actual macOS CI run with this correction,
and checks for the final main commit, remain pending. This review accepts the
fixture change only; it does not mark the task done or accept postmerge.
