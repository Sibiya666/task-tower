# Independent postmerge worker review

Verdict: **approved for the reviewed local implementation scope**. No unresolved Important findings in the scoped re-review on 2026-11-01. This is code acceptance, not proof of a real model run, all-platform CI or completed postmerge delivery.

## Findings and resolution

- **Task acceptance race: fixed for detected changes.** Original reproduction edited title at the accept_task boundary and resulted in an unreviewed card being done. Worker now supplies the claimed snapshot to accept_task, which checks its own reread; task writes compare original bytes immediately before atomic replacement. The new boundary regression passes and preserves the changed requirement without approval. The documentation correctly limits this to detected conflicts: compare-then-replace does not provide a transaction against an uncooperative external process writing in the final filesystem instruction window. No stronger isolation is established here.
- **Watch resilience: fixed.** Iteration-level handling keeps watch alive after sanitized GitHub/fetch failures and retries after the configured interval. --once still returns an error. The regression simulates a first-iteration source failure and verifies the second poll occurs.
- **Interrupted claims: fixed.** --recover TASK COMMIT --confirm-stopped calls the journal's atomic running-only recovery. Missing confirmation, missing rows and completed rows refuse recovery. Running does not automatically rerun. The operator must actually establish that the old reviewer stopped.
- **Old unavailable artifacts: fixed.** Run failures are isolated so unrelated valid bundles survive; source_errors remain visible and affect --once exit status. Newer unavailable runs with the same head suppress older passed bundles; unknown run identity fails closed; zero matching artifacts are unavailable. Relevant regression tests pass.

## Verification evidence

Independent commands used bundled Python at `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

- Initial complete suite: `-m unittest discover -s tests -v`: **111 tests, OK, 2 skips**, 28.985 seconds. Integration continued after that run; final full-suite evidence belongs to the implementer's subsequent run.
- Final scoped re-review: `-m unittest discover -s tests -p 'test_*worker*.py' -v`: **10 tests, OK**, 8.533 seconds.
- Final GitHub source suite: `-m unittest discover -s tests -p 'test_github_source.py' -v`: **24 tests, OK**.
- Final journal suite: `-m unittest discover -s tests -p 'test_postmerge_journal.py' -v`: **8 tests, OK, 1 skip** (symlink creation unavailable).
- Independent crash injection immediately after save_review/before apply persisted `reviewed`; restarted worker applied the saved result, card became done, reviewer counter remained `x`. The subsequent permanent regression also passes.

Reviewed ZIP bounds/digest and provenance, redirect Authorization stripping, child GH_TOKEN/GITHUB_TOKEN filtering, strict reviewer identity/result validation, timeouts, exact detached SHA checkout, main-only reference pin/revalidation, cross-process durable claims and stale prior-evidence refusal. No further Important finding in those inspected paths.

This reviewer did not execute real GitHub/model receipt. Implementer reports a real authenticated GitHub receipt separately; no credential or raw private response is included here. Real model evidence must be recorded separately before claiming that verification passed. Legacy stale acceptance remains blocking.

## Final selection/replay follow-up

Accepted the latest verified run/attempt selection per task+SHA, followed by latest run selection per task across SHAs. Old task+SHA journal entries remain historical and carry active=false; --once failure considers active task errors plus source_errors. Existing done protection remains intact.

Independent fresh worker/CLI regression suite: **11 tests, OK**, 10.596 seconds, including the old-failed/new-passed selection regression and saved-result replay. Additional fixture reproduction preloaded a historical needs_input journal row, accepted the current SHA, and verified historical=false/current=true active flags; a repeat poll left reviewer counter at `x`. No new Important finding.

## Missing local card follow-up

Accepted missing/non-file card deferral: receipt records waiting without creating a card or launching a reviewer, then retries once the card is available. Existing stale/malformed files still follow validation failure handling. Existing running/reviewed claims cannot be reclaimed by the missing-file branch, preserving duplicate prevention and saved-result state. Independent fresh `test_postmerge_worker.py` run: **11 tests, OK**, 11.158 seconds, including card arrival, stale evidence, saved review replay and acceptance boundary regressions. No new Important finding.

## Source SHA-256 at final review capture

- `task_tower/github_source.py`: `82c6b83753560e8d8aae6bc2d2ecef82297aab1e983a71a7dff37dcd383f4c85`
- `task_tower/reviewer.py`: `91dfa8f4333730c30e68249385042867cda157897498add913827a49ea5a4ea2`
- `task_tower/postmerge_journal.py`: `31ee8dca1dc5da0fe43180d16d5d69725ad4a2f7d4910ff4795e37fd029c88bb`
- `task_tower/postmerge_worker.py`: `094e8fc3d8609ef271232f3d301a37071b1d693f5b145bcbdff0105bd5f3f204`
- `task_tower/tasks.py`: `937a76c11fab14ac5ee840feb0ba145d6497bfc576b0e8dff7ac257b074473b4`
- `task_tower/processes.py`: `dadfa275cc1666f8dcb93578c38e07dd1b9543ca24d5e4c09c046a00487fdade`
- `task_tower/windows_job.py`: `1d478f3a7352b95d3cdc30daab5d7e0cb5a1caf0c3751488e7981a296a78deb3`
