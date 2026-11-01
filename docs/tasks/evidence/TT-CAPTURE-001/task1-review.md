# TT-CAPTURE-001 Task 1 independent review

Verdict: REJECTED pending R1. Reviewer: independent `/root/capture_task1_review`; not the implementer. Date: 2026-11-01. Worktree `task-tower-capture`, branch `feat/session-capture`.

This is the Task 1 implementation/testing gate only. Task 2 must wait for a fresh accepted verdict. No PR, main, closure or unattended-operation acceptance is implied.

## Findings history

R1 (open, P2): `relationship_projection` in `task_tower/capture.py` calls GET `/issues/N/parent` directly and converts every GitHubSourceError, including GitHubRequestError(http_status=404), to `parent={status: unavailable}` and `Native parent unavailable`. The same module's `_native_parent` explicitly recognizes GitHub's 404 no-parent response. Consequently ordinary root Issues produce spurious partial-source errors in real books projections. The current projection fixture returns Python None, so it does not exercise the actual transport boundary. Normalize a no-parent 404 to absent parent consistently, while preserving non-404 failures as unavailable; add a regression exercising the typed request exception.

Independent reproduction: a store whose parent GET raises GitHubRequestError(http_status=404) and whose sub-issues GET returns [] produces `{'parent': {'status': 'unavailable'}, 'sub_issues': [], 'milestone': None}` with `['Native parent unavailable']`. Exit 0 confirmed the faulty result. No remote access was used.

## Review and verification

Read accepted spec/plan and spec-review, repository/workspace AGENTS and coordinator development-process reference. Inspected all eight actual Task 1 files and existing Project preflight, metadata/lifecycle/verified completion and journal contracts. Stable capture identity/payload binding, committed unknown-outcome fence, Project-first flow, inert lossless provenance, title/body escaping, same-Issue promotion/serialization, same-connected-repository mutation bounds and qualified relationship reads were reviewed. No new execution or private authority follows from capture intent. Existing ordinary v1 parsing remains subject to its original checks.

Runtime: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

- `python -m unittest discover -s tests -p 'test_capture*.py' -v`: exit 0, 27 passed.
- `python -m unittest discover -s tests -v`: exit 0, 326 tests, 2 skipped (75.955 seconds).
- `git diff --check`: exit 0.
- Independent adversarial probes: a valid 32 KiB apostrophe original_text expands escaped display plus encoded provenance beyond the composed-body limit and is rejected before journal creation and POST; forged closed/status=done task capture with execute_requested remains unverified and retains projected capture intent. Exit 0. An initial quote-only probe was rejected earlier at the envelope limit because JSON escaping expands it; the apostrophe probe exercises the intended composed-body check.

No production/test changes, remotes, commits or child agents. Only this evidence file was written. Cross-host first-create serialization and external promotion editing remain explicit limitations, not distributed/CAS claims.

## Exact source binding

Canonical normalization: decode UTF-8 with optional BOM, normalize CRLF/CR to LF, encode UTF-8 without BOM, preserving final-newline state. `sourceHash` hashes sorted records `path + NUL + canonical SHA-256 + LF`. Mutable cards, evidence and runtime files are excluded.

sourceHash: `cec0eba9db04fd00e1b61edbdbc2f5f37f8fc10f28b84e17eb0b3618147f6d8f`.

| Task 1 stable input | Canonical SHA-256 |
|---|---|
| `task_tower/capture.py` | `e5a33aada78a50d93ea26358c40e604af0c28a4af79fd1b30309fb298d168db3` |
| `task_tower/capture_cli.py` | `52451b848db60c8041bd7fa2b652981e769fa91a17f4ac93f0a5d260be43411c` |
| `tests/test_capture.py` | `00c116d59c8f6cc31b07d7757c6a27a606889070fde241cf1d90010e183ce422` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `task_tower/books.py` | `32702cca1c9370d32c4c76f171fcbd81155d127302700d5bc18427224457c052` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |

## R1 re-review supplement (current verdict)

Verdict: ACCEPTED for Task 1 implementation/testing against the refreshed exact source binding below. Reviewer remains independent `/root/capture_task1_review`. This supersedes the initial rejection for the current source set only; the original finding and verification history above are retained.

R1 resolved: `relationship_projection` now reuses `_native_parent`, consistently treating HTTP 404 as no parent. The new books regression uses real GitHubTasks byte transport with urllib HTTPError, verifies 404 yields `parent=None` and no false source errors, and verifies 403/500 still yield explicit unavailable plus source errors with secret-safe diagnostics. Independently inspected the one-line production fix and complete new regression. Canonical hash comparison confirms only capture.py and test_capture.py changed among the eight accepted Task 1 inputs.

Independent verification: focused `python -m unittest discover -s tests -p 'test_capture*.py' -v` exited 0, 28 tests passed (1.029 seconds); `git diff --check` exited 0. Earlier full 326-test/2-skip independent run remains recorded above, without claiming it tested this subsequent fix. Full Issue acceptance must include the eventual current complete suite. No production/test edits, remotes, commits or children were used by this reviewer.

No unresolved Task 1 findings remain. Task 2 may start; this is not migration/PR/main/closure acceptance. Cross-host creation and external-edit promotion serialization limitations remain explicit.

Current sourceHash (same canonical algorithm): `fef033b743ad74e5a5b95e6554a5500be3e36b0bc9c540750c4c493c8ca37183`.

| Current Task 1 stable input | Canonical SHA-256 |
|---|---|
| `task_tower/capture.py` | `aecb96e7ae4e9bd8fafbcd85f44ae548a183a4a6ef3a22192247321a93f3f331` |
| `task_tower/capture_cli.py` | `52451b848db60c8041bd7fa2b652981e769fa91a17f4ac93f0a5d260be43411c` |
| `tests/test_capture.py` | `445e6b294f6c6af74c65b2c329f0b90179b88607d33cb7ffba88511bca5ea7de` |
| `tests/test_capture_cli.py` | `66bbcd3b418b9aab8b1e84403d7cab7a713a7ad692a65f2f6f53f0fd6453be04` |
| `task_tower/creation_journal.py` | `c5c6be3332276d038d151d99d101893e00bf1a6638af7a1b64be336d340412e3` |
| `task_tower/github_tasks.py` | `7a59f38382fb9676536c1307fc863edca331be93cdd2858d3ebcfe8a85911519` |
| `task_tower/books.py` | `32702cca1c9370d32c4c76f171fcbd81155d127302700d5bc18427224457c052` |
| `task_tower/__main__.py` | `b233be3d4570816c4178d8e3a21af0cea6ac772fb2927eeb8c549a3844f75cdb` |
