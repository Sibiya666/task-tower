# TT-BOOTSTRAP-001 independent postmerge acceptance

Reviewer: bootstrap-postmerge-acceptance (independent from executor). Date: 2026-11-01.

Verdict: FAIL / postmerge acceptance blocked. The merged CLI test suite passes, but the actual task card cannot be loaded because its evidence is stale. Do not mark this task done from this review.

## Tested revision and environment

- Repository: `C:/Users/sibiya666/Documents/projects/vizualization/task-tower`.
- Exact tested HEAD and local main: `60d78065a524378c920f293c346ef42b1639af87`.
- Active branch: `main`. Initial and post-test `git status --porcelain` were empty before this report was added. Git emitted inaccessible user ignore-file warnings; no tracked or untracked changes were listed.
- Windows 10 build 19045 (`Windows-10-10.0.19045-SP0`), PowerShell driver.
- Python: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, 3.12.14, MSC v.1944, 64-bit AMD64.
- Read-only Git invocations used per-command `-c safe.directory=C:/Users/sibiya666/Documents/projects/vizualization/task-tower`; Python subprocesses inherited equivalent process-local `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=safe.directory`, `GIT_CONFIG_VALUE_0` settings. No global Git configuration was changed.

## Fresh checks

`<python> -m unittest discover -s tests -v`: exit 0; 56 tests in 15.589s; OK, 1 skipped, 0 failures/errors. The skipped test was `test_refuses_symlink_state_directory` with reason `symlinks unavailable`. Thus 55 tests executed successfully. This includes fixture subprocess bootstrap coverage and native Windows launcher/junction checks.

`<python> bootstrap.py --help`: printed expected bootstrap options successfully.

`<python> -m task_tower task show docs/tasks/TT-BOOTSTRAP-001.json`: exit 2; output `task-tower: stale evidence for spec`. Repeated independently with the same result.

## Evidence mismatch diagnosis (read-only)

The configured `core.autocrlf` is `true`. Hashes are SHA-256 of exact bytes; committed hashes below were calculated from `git show HEAD:<path>` output.

| Stage | Card expected | Working-tree evidence | Committed evidence blob |
| --- | --- | --- | --- |
| spec | `2045f4266d7fa792948e10f3dd7d20824e274cd42614f610b8cc90f6da2afbd4` | `1feac991b0492c32ff16a0f1b00bb13e465f1a0f0b5f5f920999199fccdefe16` | `2045f4266d7fa792948e10f3dd7d20824e274cd42614f610b8cc90f6da2afbd4` |
| development | `e7ef4a50e8250dd16b91dba20ba80c8d35e86c0c97bc6df0eafcd33efa4f062a` | `a329cf7e3b7ad60a7cf31d3b2b3af59a6d2a2ef286001256982d182c433af7cb` | `f3b18b6f10e90f9815c6be82f9dc403b538271916888fe3c5a5b2acd6eba6726` |
| test | `38014c4e26db1ba4c5e168b551f2aa0acf425ff855b96761f2536cde2b66ba95` | `6af3e8108b251c25d8be53661bd72502096c59b2fd27402f298b6562878d5f38` | `ffeed80f60636780b7f818f1a17b43461a8d42791458a81f270515db1039321b` |

The spec committed blob matches its card hash, while the checked-out bytes do not. Development and test hashes disagree even with their committed blobs; checkout conversion alone does not explain those two mismatches. The existing stale-evidence guard correctly blocks progress. Source, card and earlier evidence were not modified by this reviewer.

## Scope

This report verifies only this Windows execution and exact merged SHA. macOS/Linux jobs were not executed or claimed. Native model/harness sessions, paid calls, authorization reads and overlay launch were not performed. The suite's fixture processes do not call a model. No commit or push was performed. This report alone is the reviewer-created change.
