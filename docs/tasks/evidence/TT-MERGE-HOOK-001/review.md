# Independent review: TT-MERGE-HOOK-001

Reviewer: separate merge_hook_review agent. Date: 2026-11-01.
Verdict: approved for this exporter increment; no unresolved Important or Critical issues found.

## Resolved during review: missing output parent

`.github/workflows/postmerge.yml:58` writes `.task-tower/merge-event.json`, but the directory is neither tracked (`git ls-files .task-tower` is empty) nor created in the workflow. `task_tower/merge_events.py:84-87` passes the missing parent directly to NamedTemporaryFile. A clean runner therefore fails export with FileNotFoundError; upload is skipped because steps.event.outcome is failure. This prevents the core promised artifacts on all three platforms, even when tests pass. Create the output parent before writing (or target an existing runner directory), and add a CLI regression covering a nested output path with a missing parent. Existing CLI coverage uses an already existing temporary directory and misses this integration case.

The producer subsequently added output.parent.mkdir(parents=True, exist_ok=True) after validation. Independently inspected the correction and ran all 8 merge-event tests successfully, including a subprocess regression proving nested output creation and no directory creation for invalid input. The original blocker is resolved; the preceding paragraph records the finding against the earlier snapshot.

## Reviewed guarantees

Merged/closed/main, repository consistency, SHA shape, positive identifiers and explicit task markers are validated; generated run URLs use validated components. PR body is read as JSON data, without shell interpolation. Checkout explicitly targets merge_commit_sha; contents permission is read-only and checkout credentials are not persisted. Matrix has Windows/macOS/Linux and fail-fast false. Tests use step outcome, so continue-on-error does not falsely emit passed; the final step restores job failure for unsuccessful tests. Actual Actions execution was not performed and live artifact delivery remains unverified until GitHub runs the workflow.

Evidence hashes dispatch explicit schemes; legacy remains raw, unknown schemes reject, text CRLF normalization preserves substantive edit detection, and binary evidence remains raw. No automatic legacy rehash or task completion was added. This increment exports events only; importer/sync and independent postmerge acceptance remain future work. Existing stale bootstrap evidence remains a blocker by design.

## Verification

Ran bundled Python: `python -m unittest discover -s tests -v`.
Initial snapshot: 68 tests, OK, 1 skip (symlinks unavailable), 17.384 seconds. After the correction: all 8 merge-event tests passed in 0.372 seconds. Root agent is rerunning the full updated suite.
Read AGENTS.md, merge-event spec, implementation plan and docs/merge-events.md. Reviewed modified tasks.py/tests, merge_events.py/tests and postmerge.yml. No source edits or commits made.

## Reviewed source hashes (SHA256, exact working-tree bytes)

- task_tower/tasks.py: EBBAB6F0A2003D127E2EA87BA70C67D1AADB55221FBCA9DEBEFE73EBE12F81CC
- tests/test_tasks.py: 7FD86FCA4021B3DB988C134613EBCCD94C9D8BE559D7C5C8C15207321A387E42
- task_tower/merge_events.py: 1B5A67C40E19D667F43FF2AD7E7BC1A70FC6D74C24FF25828016A1B5B9815D00
- tests/test_merge_events.py: 6F614EC473A8D5701882F8D051F5DBF5EC3AAD17119C914452FDAB45D4C78FF6
- .github/workflows/postmerge.yml: 01D87EC61CCE50D622B22D5C49FBDC8564495750B71A6C2E3A0403539124E1FB

