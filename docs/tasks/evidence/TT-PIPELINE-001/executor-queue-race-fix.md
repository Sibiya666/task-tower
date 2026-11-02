# Executor queue disappearing SQLite sidecar: author fix evidence

Fixer `/root/pr_reviewer_review`, 2026-11-02, following coordinator's explicit authorization for this separate production bug. Requires independent coordinator review; no self-acceptance or commit. Dependency freeze must be rebound for subsequent Task6/whole-branch acceptance.

## Actual CI diagnosis

Read exact macOS job125015394586 in run41362407458. Earlier inherited child stderr at 23:30:41.751–23:30:41.752 includes the missing traceback: ExecutionQueue.claim -> _db(True) -> _safe line52 -> path.exists() then path.stat(), ending `FileNotFoundError: [Errno 2] No such file or directory: '/private/var/folders/.../queue.sqlite3-journal'`. That explains empty child stdout in the competing claim test. This is a pre-existing production TOCTOU (executor_queue.py last changed in b052c52), distinct from unresolved temporary root fixtures. SQLite can remove its normal rollback journal between existence and stat.

## RED and minimal correction

Added deterministic regression which creates an ordinary transient journal and removes it after the exact _safe exists() observation, before stat. The final calibrated RED raised FileNotFoundError at executor_queue.py:52, matching the CI stack, in0.123s. Earlier probe calibration removed the sidecar too early in safe_config_path; that was corrected before product changes and is not claimed as the reproducing RED.

Only _safe's queue-file metadata observation changed: retain safe_config_path, stat any existing file, and tolerate FileNotFoundError only for one of the fixed SQLite sidecars. A missing primary queue after a positive exists observation still raises. Existing hardlink checks, alias checks, forbidden path rules, WAL refusal, SQLite transactions, ownership and capacity are unchanged. Added explicit negative hardlink checks for all three fixed sidecars. No locking rewrite or catch-all exception relaxation.

Frozen content:

| File | Raw SHA-256 | Canonical LF SHA-256 |
| --- | --- | --- |
| task_tower/executor_queue.py | `58439347092de0d88095e0af26522c269e4db735d8fcec2162b9a4a572720202` | `4b5568f617b0dc7da0f2e9b732a2ddd265881d6f25c10f6154788e231bc3eb22` |
| tests/test_executor_queue.py | `180b282e4f12f781a5b7a874c6daac84ee825a1dcfed470863659809dfe4c5df` | same |

## GREEN

Absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`:

```text
python.exe -m unittest tests.test_executor_queue tests.test_executor_adapter -v
Ran 25 tests in 2.995s
OK
```

Includes deterministic disappearing-sidecar claim, actual competing claims/retries, hardlinked sidecars, unsafe private aliases, rollback/history and WAL no-mutation tests. No broad suite, macOS execution or successful remote rerun is claimed. No commits/pushes or live external writes. The earlier portability-fix report's uncertainty about this queue failure is superseded by this actual traceback diagnosis and separate reviewed fix boundary.

Independent coordinator acceptance, 2026-11-02: inspected exact production/test diff. The FileNotFoundError exception is confined to transient sidecars; main database disappearance still raises, and all existing path safety checks and link-count validation remain. Independently ran tests.test_executor_queue and tests.test_executor_adapter: 25 tests in 3.830s, OK. ACCEPT this narrow fix at the source/test hashes above. Remote CI is still required; no broader Task6 acceptance is implied.
