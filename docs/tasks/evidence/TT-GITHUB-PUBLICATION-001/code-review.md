# Independent code review: GitHub publication

Reviewer: independent `github_publication_review` agent, 2026-11-01.

Disposition: no remaining blocking findings for the explicitly agreed scope. This review does not claim live Issue 9 rollout or the complete suite passed; those are separate executor gates.

Reviewed the publication specification and plan, `github_publication.py`, journal publication claims and persisted receipts, worker integration, real GitHub client request validation, connection trust configuration, and local receipt verification in `project_worker.py`.

Found and reported one concrete production blocker: `GitHubTasks.request` rejected every path containing `..`, including the required `/compare/<full SHA>...main` route. Fake stores hid the failure. The implementer narrowed the exception to the exact full-SHA-to-main comparison route. This was a static code finding; the fix landed before the independent regression command, so no pre-fix failing run is claimed. The regression confirms both the legitimate comparison and rejection of `/issues/../secrets`.

Independent validation command, run in the `task-tower-github` checkout:

```powershell
& 'C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -p test_github_publication_acceptance.py -v
```

Result: 5 tests passed in 6.590 seconds. The tests use the actual GitHubTasks client with a deterministic byte-returning transport, the real worker, local temporary Git checkout, SQLite journal, and subprocess reviewer fixture. They verify successful state-only close, unchanged Issue prose, duplicate tick without a second comment or reviewer call, and blocking a rejection, changed actual comment author, or local evidence mutation between receipt creation and close. Each blocked publication preserves local acceptance, avoids PATCH, and does not rerun the reviewer on the next tick.

Code inspection additionally confirmed explicit task mapping, immutable Issue ID binding, canonical persisted receipt comparison, accepted snapshot and matching journal/report validation, fresh source checks before posting and closing, owner/lease checks before mutation, matching-comment discovery after ambiguous responses, and sanitized publication failure state separate from local review state. Book trust defaults to nobody and uses the API comment author; workflow artifact verification remains a separate path.

Scope and limitations: the parent explicitly accepted conservative rejection of preexisting unrelated workflow/rejection lifecycle history rather than automatic cross-mode reconciliation. Such history requires operator reconciliation and cannot silently be overridden by a later posted approval. The GitHub comment-read/Issue-close interval is not atomic; a later rejection can invalidate book completion without automatically reopening the Issue. Trusted publisher credential holders can attest local results; this is not cryptographic proof of execution. These limitations are not treated as blockers for the clean-history Issue 9 pilot.

## Scoped integration follow-up

Reviewed the worker mapping guard added after the initial review. Unmapped task IDs now skip publication before API access, and any previously projected publication field is removed from the returned row without modifying durable local acceptance or historical journal entries. The regression verifies no false publication failure, no comment, and no second reviewer invocation. No blocking finding for this change.

Independent command:

```powershell
& 'C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s tests -p test_github_publication.py -v
```

Result: 21 tests passed in 25.964 seconds, including `test_unmapped_done_task_has_no_publication_failure`. The parent remains responsible for the final complete suite and live rollout.

A read-only glance at the separate runtime activation script confirmed PID/command checking, a read-only journal running-count check, retained journal, and hidden replacement process. Reported the operational interval between the idle check and process stop to the parent: these operations are not atomic, so strict interruption prevention would need coordination, or confirmed current source containing only already-accepted tasks. The activation script was not executed or edited by this reviewer.

## Safe diagnostics follow-up

Accepted the narrow diagnostics addition after a live publication failure whose cause was not yet identified. `GitHubRequestError` retains only a bounded integer HTTP status or an allowlisted category. Publisher journal details combine code-owned phase constants with these safe categories; remote error reason, body, headers, URL, and arbitrary exception strings are not emitted. Existing source-error catch compatibility and publication proof, lease, and close guards remain intact. No root-cause claim is made from the initial generic failure.

Reran the same `test_github_publication.py` command above: 24 tests passed in 27.026 seconds. The added cases inject sensitive HTTP/network error strings and verify only sanitized diagnostics, including durable `comment_post: http_403` while local acceptance remains done.

Reinspected the updated runtime activation script without executing it. It now holds SQLite `BEGIN IMMEDIATE` while checking zero running reviews and zero unexpired publishing claims and stopping the verified watcher PID. This addresses the earlier claim-creation interval; it does not claim atomicity with remote API operations. Journal decisions are not rewritten by the helper.
