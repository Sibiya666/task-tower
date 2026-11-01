# Task 3 independent implementation review

Verdict: ACCEPTED for the two source inputs below (2026-11-01).

Reviewer: executor_processes_review, distinct from implementer. Scope is the optional cancellable/bounded runner and its tests, against the accepted TT-EXECUTOR-001 spec/plan and main 9ba02c2 process/Windows Job baseline. No production edits or remote operations were made.

## Exact reviewed inputs

- `task_tower/processes.py`: SHA-256 `b3f7bc2aeae64002b043493dab36854555ad553e7947c884df07b19265e2c762` (actual file bytes).
- `tests/test_executor_processes.py`: SHA-256 `2c166bdbbfe1fa7d4a9ceb961d5d42273becb72c15650c61553ed9fda767b79f` (actual file bytes).

## Verification

- Windows bundled Python: `PYTHONPATH=tests python -m unittest tests.test_executor_processes tests.test_processes tests.test_worker_cli tests.test_project_worker tests.test_postmerge_worker -q`: 48 tests, PASS, one symlink-privilege skip. Real Windows junction test passed. Initial invocations used a nonexistent test_worker module and then lacked the postmerge fixture import path; the corrected command above passed.
- Independent real pipe probe generated 64 MiB on each stream with a 137-byte capture cap. Passed with correct total byte counts, independently checked complete-stream SHA-256 and exact prefix files; complete EOF with truncation true. Runner-only tracemalloc peak was 331,920 bytes. The earlier 32 MiB probe included reviewer hash-buffer allocation in its memory measurement; only the isolated measurement is used for the bounded-memory conclusion.
- Independent running cancellation-predicate exception returned unknown, started true and cleanup_confirmed true, without private exception text or argv.
- Independent repeated real success and invalid-cwd launch probes: 160 of each; process handle count plateaued at 133 across four batches after initial runtime warmup (initial 131), active threads stayed one. An initial no-warmup comparison grew by nine before collection; repeated batches with garbage collection established no continuing handle/thread growth. First handle-count prototype lacked ctypes signatures and was discarded.
- Existing real tests cover cancel before launch, running cancel, timeout, parent exit with delayed descendant marker, Windows close failure refusing success, overflow, existing-log preservation, default shape and literal argument compatibility.

## Review conclusions and limits

No blocking finding. Optional capture drains fixed-size pipe chunks and stores bounded prefixes; hashes/counts describe observed stream bytes and tail_unknown/truncated prevent incomplete EOF being reported complete. Cleanup failures and predicate exceptions cannot pass. Windows Job close is retained on every constructed-process exit path, with termination and bounded wait for interrupted parents; POSIX group termination and reap paths were inspected. POSIX real execution remains a CI requirement; this review ran on Windows.

Default tempfile-based behavior is deliberately preserved byte-for-byte for compatibility. New executor callers must supply bounded capture. Installation/checkouts/connections exclusions are Task 4 caller responsibilities. Static directory aliases/junctions and existing log files fail closed; capture uses exclusive creation. This review does not claim hostile concurrent filesystem mutation containment or a process sandbox.

No historical production finding was recorded in this review. Acceptance is invalidated by any change to either source hash above; other Issue 15 implementation stages and whole-diff/head-base acceptance are separate gates.

## Python 3.11 reparse-guard correction supplement — ACCEPTED

Independent reviewer executor_whole_development, 2026-11-01, distinct from implementation/fixer instances. Inspection HEAD `2022439e45e47816218a606ded73564f6c1e2627`, base main `f7ce385b89cdddda089985404ce11fffc36a0797`; corrections are actual uncommitted working-tree bytes. No blocking finding. Historical acceptance remains preserved but changed file bindings are superseded below. Fresh exact-head/base PR acceptance and current CI remain separate gates.

Inspected the actual four-file delta. `_capture_files` now lstat-checks the supplied directory and every ancestor, rejects the Windows reparse bit (portable constant/fallback 0x400), retains symlink rejection and raises fixed unsafe_capture_directory ValueError on lstat OSError. This runs before log creation or executable lookup and does not require Python 3.12 Path.is_junction. Existing files remain exclusively created. Both the target junction and an aliased ancestor are covered by a real Windows junction regression which temporarily removes Path.is_junction and restores it in finally. No process-launch, cleanup, output, authority or dependency behavior changed. Static path checks retain the existing limitation against hostile concurrent filesystem mutation.

The remaining changes canonicalize test-owned temporary roots before supplying legitimate fixture paths in process/harness/one worker test. Assertions and malformed-output cases remain intact; alias tests still explicitly create unsafe aliases and pass those raw aliases to production. This accommodates macOS temporary-root aliases without resolving untrusted production inputs. Source/spec/plan and installation authority remain unchanged apart from the corrected capture guard.

Independent bundled Python 3.12.14 Windows run with PYTHONPATH=tests: `-m unittest tests.test_executor_processes tests.test_processes tests.test_worker_cli tests.test_project_worker tests.test_postmerge_worker tests.test_executor_worker tests.test_executor_harness -q`: **76 tests OK (skipped=1), 33.201 seconds**. The real junction regression ran. Independent missing-directory, regular-file-as-directory and injected lstat PermissionError probes returned unsafe_capture_directory, did not call executable lookup and created no logs. Focused diff-check passed. This reviewer did not execute real Python 3.11 or macOS; mandatory current all-three-OS Python 3.11 CI remains the portability gate. Full-suite acceptance is separate. No downloaded CI failure log inspection is claimed.

Current Task 3 canonical UTF-8/LF bindings supersede the historical process/source-test hashes above:

| File | Canonical SHA-256 |
| --- | --- |
| `task_tower/processes.py` | `50d2feddcfad3530d3ab63c94bc514b78f082e330de99543e857259cc951c729` |
| `tests/test_executor_processes.py` | `39fa03f0a0b195871e431f3cbfe269efc70b2b500314ddc7670c7dec57020ee3` |
