# Task6 R2 independent re-review and separate operator-docs review

Reviewer: fresh independent `/root/books_native_smoke_impl`, distinct from source and documentation authors; 2026-11-02. **ACCEPT Task6 R2 at the exact content bindings below.** The original and R1 rejection receipts remain historical evidence. This verdict is task-level implementation reacceptance, not whole-branch testing, PR/main/postmerge acceptance, an installed-Codex pilot or unattended readiness.

## Source freeze and scope

Checkout HEAD `6ff859791d0deed0dfe8608bb625e45ee48acc8b`; supplied origin/main snapshot `918554a1e7f6dec10f81a366c1dececa845ff072`. Freeze `runtime-task6-r2-freeze.json` SHA-256: `053bc154572a040b11ac990f016d72344c3d1bc27da94c86ea9e5e54b559f7eb`. Independently recomputed every raw and canonical hash for all **21** bound files before and after verification; all match. Eighteen R1 bindings are unchanged. R2 changed bindings:

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| task_tower/project_connections.py | `6d5953d4adb8779f31a5e79016e205cc8eba121851d5bbdfa8dabf1c4ed4ece6` | `a3119c74cd24ddf95710ad9f91ac966ad457eb70dd9c98820da2fcdaa2e80247` |
| tests/test_safe_config_race.py | `9cab9778a8c7a3630558f983724cf3def211295fc1826f34fc6eb070e9f32201` | same |
| tests/test_pipeline_publish.py | `95c6bae852f0cd8b4ec4b3e07f9b4dc04bd308297f576010814927924d6efcae` | same |

This continues the whole-Task6 review recorded in `task6-r1-review.md`: complete new CLI/watch implementation and fixtures plus shared journal/executor/worker/publisher/routing changes, against the accepted R2 spec and plan. The separate Root executor-queue correction remains a separately accepted bound dependency. This re-review inspects the entire R2 delta rather than assuming the earlier rejection was resolved by green tests alone.

## Findings and correction

No blocking findings remain within this task scope. The transient-sidecar race is corrected narrowly: `safe_config_path` uses the already captured no-follow leaf `lstat` mode to reject a nonregular leaf, instead of a second `exists()`/`is_file()` pair. A regular leaf disappearing after observation no longer becomes a false directory rejection. Every observed symlink/reparse ancestor is still rejected before this check, and an observed directory remains rejected even when removed immediately afterward. Caller hardlink guards remain unchanged. This does not promise general immunity to hostile concurrent filesystem replacement.

The new regressions cover both observed deletion orders, missing/regular/directory leaves, directory deletion, real Windows junction leaf/ancestor/deletion, and actual journal hardlinks. The Windows environment cannot create a symlink, so that explicit test skips; real junction/reparse tests run and pass. The corrected typed-PR fixture now enters `publishing` through genuine `worker._record` after the valid `ready` boundary, before reserving a PR effect. It preserves typed-observation/forgery/database-reload assertions and changes no production publication authority.

The original public-work stop-first/shared shutdown deadline, unknown exit1 and positive temporary-root corrections remain unchanged and verified. Unknown reservations are retained; the correction introduces no reset, retry or journal-deletion recovery.

## Independent verification

Absolute Python: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.

```text
-m unittest tests.test_safe_config_race tests.test_pipeline_journal.CompetingJournalTests tests.test_executor_queue tests.test_bootstrap_connections tests.test_pipeline_publish.PublicationTests.test_typed_pr_observation_and_database_reload_reject_forgery tests.test_pipeline_watch.WatchTests.test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain tests.test_pipeline_watch.WatchTests.test_shutdown_budget_with_external_sqlite_lock_and_live_owned_helper -v
```

**38 tests in 45.935s, OK, exit0; one symlink-privilege skip.** Includes deterministic actual-path observations, real concurrent worker claims, legacy queue/private-path/bootstrap callers, hardlinked SQLite sidecars, typed PR forgery rejection, actual contained helpers, exclusive SQLite locks, stop-first public work/exit reporting and shared shutdown bounds.

An independent repeated real-process probe created 20 disposable journals with four competing claim children each: **80 children, every exit0, maximum two claims per batch**. It used actual `PipelineJournal` and ownership contexts, no replaced guard/claim result. The R1 real competing-child failure and deterministic RED remain preserved in the earlier receipt.

I did not repeat the full 77-test primary command: the 18 earlier source bindings are unchanged, and the independent R1 tests plus current focused correction/caller/lock probes cover the delta. Author evidence is distinguished from independent execution: 77-test primary run passed in 476.179s with one skip; broader caller run passed 179 tests in 66.149s with three skips. The expanded 164-test run had 159 passes, four runner import-path errors and one stale typed-publication fixture error; these are not relabeled as a green full run. Corrected 24 targets passed in 31.369s, and I independently ran the corrected publication target above. Full repository and current three-OS CI remain integration gates.

The earlier unexplained R1 `unknown` during publication setup remains unproven: the original fixture journal was deleted, so neither this race nor this correction is claimed to explain/fix that occurrence. Later author and independent publication passes are separate observations. A real installed-model pilot remains a Task7 gate.

## Separate five-file operator-documentation verdict

**ACCEPT the following frozen documentation content only.** Reviewed the complete new operator guide and all four shared-doc diffs against actual CLI/parser/policy/dispatcher/role source. This supplies documentation review, not Task7 pilot or whole-branch acceptance.

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| docs/pipeline.md | `6ca8ef7ad406f676b862a7bbb3292b0edf4086893fcb7c5fbd1926d405127a05` | `26a0f8c4c1c7a8715ca9f7988db7fa48d868bdd26a8afc8c06b10ab7944013f5` |
| AGENTS.md | `746b04d22f4455dd1a18f2ba1b1d33d40c93d9a34b763ac07faea0877c09bdbd` | same |
| README.md | `5d58e8b838568815f4ac330f428788d1b21f75ecf86f45b00b76a60d5017b708` | same |
| docs/roadmap.md | `f54623f3cb1ab0119651780bd7851686f6279d1db54ad00bbd391b24201d6e1a` | same |
| docs/development-process.md | `6fb8083518f68b1f563c1a9b03ea1381a26f06670f037749a1ffe1c22998ed10` | `f7710ac0d25e4bc18b73879f4eb807dea3c58f69e71c3287020623ce7a4acd42` |

All five raw bindings independently match. Both JSON blocks parse. Seven documented operator command forms parse with the actual CLI. The backend example, substituting the actual Python and repository root only, passes genuine dispatcher validation and produces exactly `pipeline._fixed(...,'adapter')` plus request/result placeholders: argv[0] slash spelling is normalized by dispatcher validation, while native private-path argument spelling/order matches the exact backend identity.

Task fields/defaults/ranges, publisher mapping even when disabled, checks and explicit CI substitution match implementation. The guide and shared docs clearly distinguish same-repository serialized actions from different-repository two-slot overlap, local ownership from distributed fencing, active-chat coordination from a running watch host, and fixture evidence from the unrun installed pipeline pilot. The existing-token exception is limited to fixed trusted contained host helpers; model/custom/check children still strip keys case-insensitively. Unknown work has no reset/replay-by-deletion command. No new credential scope, service, automatic merge/closure or night-readiness authority is claimed.

No source, tests, private installed configuration, commits or remote state were changed by this review. Acceptance expires for changed bound inputs.
