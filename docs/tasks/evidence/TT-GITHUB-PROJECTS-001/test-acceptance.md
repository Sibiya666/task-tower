# Independent test acceptance

Reviewer: separate test-acceptance agent; no implementation edits or commits. Scope: GitHub connections/store/books/board and remote acceptance fixtures. Read AGENTS.md, architecture spec and implementation plan.

## Reproduced regressions and verification

Python executable: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

Initial independent command: `python -m unittest tests.test_github_projects tests.test_projects_board tests.test_github_projects_acceptance -v` exited 1, 23 tests, three failures: CLI overwrote its connections source, CLI overwrote existing user evidence, and malformed Issue page `[null]` silently appeared as an empty success. Implementation agent fixed these; acceptance tests retain the cases.

Latest focused command: `python -m unittest tests.test_github_projects tests.test_projects_board tests.test_github_projects_acceptance tests.test_project_worker -v` exited 0, 38 tests, no failures/errors/skips (2026-11-01).

Ten separately authored cases in `tests/test_github_projects_acceptance.py` cover malformed-source isolation, CLI source/output preservation, same legacy card ID and equal Issue numbers in two repositories with idempotent import, truncated library fail-closed, two scoped Project memberships and status projections on retry, omitted acceptance policy/checks, fresh-runner remote publication reuse, stale local approval after another runner's explicit recovery/rejection, and dispatch of pending publication retries.

Additional two-test regression command (the final two cases above) exited 1 with two failures before queue fixes: an old local approval could overwrite a newer remote rejection; reviewed attempts could not dispatch publication retry. After fixes, `python -m unittest tests.test_github_projects_acceptance tests.test_project_worker -v` exited 0, 22 tests, no failures/errors/skips.

The fresh-runner fixture starts runner B with an empty local state directory, fetches runner A's completed trusted Actions run and digest-bound ZIP receipt through the actual `verified_receipt` implementation, refreshes the mocked authoritative bundle, closes the Issue and preserves user prose. A reviewer invocation fails the test. This proves the fixture-level no-second-review path without replacing `_remote_receipt` with a stub.

## Boundaries

REST/GraphQL/Actions are stateful fixtures. Project retry tests demonstrate client scoping and mutation behavior; they do not prove account permissions or live server installation. Existing library tests verify commit-pinned Markdown URLs and bounded Issue pagination (20-page refusal); truncated trees fail closed instead of publishing partial Markdown lists. Existing task/harness tests exercise Windows junction/reparse rejection; worker state construction uses `tasks._safe_path`. Local trusted configuration/state remain host trust inputs.

No GitHub writes were made by this reviewer. Read-only smoke is separately recorded by the parent; it proves connectivity only. No installed project workflow, live distributed execution, physical runner B, or automated repository merge barrier is established here. Worker consumes externally produced postmerge evidence.

First full suite run exited 1, 165 tests, one fixture error and two privilege-related symlink skips. The cross-runner receipt fixture still declared Windows-only checks while a concurrent implementation revision temporarily required all three platforms. Updated the fixture to include Windows/macOS/Linux successful checks; no production code changed by this reviewer. A fresh full run is required below.

## Final settled verification

After the implementation settled (including configurable nonempty required-platform subset validation), ran `python -m unittest discover -s tests -v` from `task-tower-github` with the executable above. Result: **exit 0, 165 tests in 34.190 seconds, OK (skipped=2)**. The two skips are `test_refuses_symlink_state_directory` and `test_rejects_symlinked_database_parent` because this Windows account cannot create symbolic links. Windows junction/reparse tests ran and passed. Raw local output: `../runtime/github-projects/test-acceptance-full.log` (runtime-only, not committed).

Independent test acceptance passes for the implemented, documented scope. Earlier failing/in-flight runs are superseded by this settled result. No claim of main integration or project-level postmerge acceptance is made.
