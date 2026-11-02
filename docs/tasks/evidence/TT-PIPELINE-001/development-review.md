# Whole development review — frozen 8981c6d

Fresh independent reviewer `/root/pipeline_development_acceptance`, distinct from product implementers; 2026-11-02. **REJECT: one P2 checkpoint freshness finding.** Task7's new installed pilot was still running when this review was frozen; no result is inferred from either historical blocked pilot. This is development-stage review, not test, exact PR head/base, main/postmerge, Issue closure or unattended-readiness acceptance.

## Reviewed inputs

Reviewed the whole actual 59-file difference from accepted main `56f8ab12f21ab91030ffe54de96520fcd979dc04` to source HEAD `8981c6d183980b286d2bf6423b69f88da4773f7a`: all new policy, inputs, journal, roles, worker, publication and CLI code; shared routing/default-source/executor/path/process/PID changes; all changed tests/fixtures; specification, plan, operator/shared docs, card and historical evidence. Repository AGENTS and all thirteen implementation rulings govern this review. The proposed header in the spec is historical; its current accepted clarification is recorded separately.

Canonical spec SHA256: `4fe7ff944bd39c59ba74e90ef10405c9020311fd3035554c0870d5e31648c72d`. Canonical plan SHA256: `4af0a9f7114e3e253658455fc3f579dde91c935d6fd5d5971d30ef7511dea83c`. Both independently match. An independently computed manifest of the 59 changed Git blobs has SHA256 `2bd89806f0cef8d657f93f66e969b323ea47c0dbacb65c31360f44465abcb652`: ordered `git diff --name-only BASE...HEAD` rows `{path,raw_sha256,canonical_sha256}`, canonical text strict UTF-8 with CRLF/bare CR to LF preserving BOM, JSON sorted keys/compact separators/ensure_ascii true/allow_nan false/no final newline. Exact committed blobs, rather than unrelated untracked runtime files, define this binding.

## Blocking finding

**P2 — ordinary and rework checkpoints omit effect-boundary external freshness checks (`task_tower/pipeline_inputs.py:341–356`; normal caller `task_tower/pipeline_worker.py:309–314`).** The controller checks authority before entering checkpoint preparation, then the freeze enumerates/hashes product, constructs a private index and writes the tree. Its immediate pre-intent/pre-commit/pre-ref callback is explicitly restricted to host-evidence publication. Normal and rework checkpoints receive no such guard. An authoritative main/policy change during preparation therefore still permits a new checkpoint commit and branch-ref update. A later controller authority check parks the run, but does not prevent the stale effect. The accepted spec requires revalidation immediately before checkpoint commit and before effects; the publication path already demonstrates this pattern.

Independent real-Git reproduction, without product edits or fabricated journal transitions: instantiate existing `WorkerTests`; run its normal preparation and spec-executor ticks; wrap only `pipeline_inputs._git` so that after the real `write-tree` returns, change the fixture's authoritative main SHA to `b` repeated 40 times; run the normal checkpoint tick. Observed `needs_input / policy_revoked`, zero verdicts, **a newly persisted checkpoint SHA and a completed `commit` effect**. The old checkpoint was null. Thus current tests and eventual parking do not enforce the specified pre-effect boundary.

Required correction: provide trusted journal/run/owner-bound fresh authority checks to normal and rework freeze paths immediately before their effect intent, commit and ref update, while retaining all existing product/Git/CAS and unresolved-intent fences. Add real-Git regressions for revocation during preparation and after intent. Before-intent revocation must prevent commit/ref effects; after-intent uncertainty must retain the intent and never replay. A fresh review is required after the correction. Do not modify the running pilot's source or reset any preserved pilot.

## Independent verification

Used existing absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` from this checkout:

- `-m unittest tests.test_pipeline_policy tests.test_pipeline_cli tests.test_pipeline_default_source tests.test_safe_config_race tests.test_process_pid -v`: **46 tests, 9.245s, OK, one unavailable-symlink privilege skip**.
- `-m unittest tests.test_pipeline_journal tests.test_pipeline_inputs tests.test_pipeline_roles tests.test_pipeline_publish.HostCommitBlobTests -q`: **90 tests, 104.900s, OK, one POSIX executable-mode skip on Windows**.
- Separate actual-Git boundary probe above: reproduced the finding in 5.280s. No source or test file was edited.

These are 136 independently executed focused tests, not a full-suite claim. Root's integration and CI observations remain separate evidence. `git diff --check BASE...HEAD` reports new blank EOF lines in five files; this is nonblocking whitespace, not a passing check. Exact-head three-OS CI remains a separate gate and was not independently observed complete here.

## Preserved evidence and limits

The authority, canonical hashing/BOM/size limits, strict six-role outputs and fresh instances, actual host checks, append-only supersession/rework, local atomic repository/action exclusion, bounded contained host helpers, role/check token stripping, safe publication mapping, typed PR identity and unknown-no-replay structure are otherwise coherent in this review. Different-repository overlap and same-repository serialization are explicit limits; local SQLite is not distributed fencing. No new scope, installation, model selection, merge or Issue-close authority is introduced.

Historical rejections remain in task1-review.md, task2-review.md, task3-review.md, task6-review.md and task6-r1-review.md with their later content-bound corrections; they are not erased by this review. The original Task6 unexplained unknown remains unproven and is not attributed to any later race/Unicode/blob correction. The expanded run with invocation/fixture errors is not relabeled green. Task5 owner-loss-after-POST evidence remains an unknown fenced effect with no replay.

The negative two-role pilot and later six-role V2 pilot retain their respective blocked outcomes, audited in installed-codex-blocked-review.md and v2-evidence-review.md. The Unicode-reading and typed-blob corrections have their own scoped reviews. Read-only validation of V2's preserved checkpoint never advances its parked journal. V3 is a new distinct lower-HTTP-transport fixture-source experiment using installed models; its final frozen report still requires independent audit. No live GitHub Project pilot, final ready boundary, installed-runtime acceptance or night readiness is claimed here.

This reviewer changed only this report. No product, card, spec, private configuration/journal, Git ref, commit, push or GitHub state was changed. Changed source or evidence inputs require a fresh affected verdict.

## R1 whole-development re-review — current verdict

2026-11-02, same independent reviewer after the author's correction: **ACCEPT whole development at the frozen inputs below.** The original 8981c6d rejection above remains historical and is not rewritten. No blocking findings remain within this development review. This is development acceptance only; independent test/full-suite/current three-OS CI, exact-head/base PR, main/postmerge and automatic Issue closure remain separate gates.

HEAD remains `8981c6d183980b286d2bf6423b69f88da4773f7a`, base remains `56f8ab12f21ab91030ffe54de96520fcd979dc04`. This verdict binds the original whole 59-file committed diff plus the following uncommitted correction and documentation inputs; HEAD alone does not represent the corrected source. Independently verified author freeze `runtime-task7-freshness-freeze.json` SHA256 `9149e814d3175f487b1157de2157cf4ab49a4866aecdb4c240d576008ddc51e0` and all three raw/canonical bindings before verification.

| Corrected file | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline_inputs.py | `88eb9edab82264695f32de485218caab7beefc3bde72b290e49e76af47ef00a2` | same |
| task_tower/pipeline_worker.py | `48293d71ef3ce977a5b4cf8eb3404056e79c6377282e77dd9b809aa5dc788f6a` | `375ff613e471fbe0be46c4390ce62d775221879c3c8932aa6601d93fc2ff577d` |
| tests/test_pipeline_worker.py | `5e49ac61f555748b971ddeac89eada81a51930d2e160609fa2a3e9af3930a32d` | `543f1a6ab13dd768f1f0b54a82a3f015b877ad842c398a98c8f3009c8d00bc0c` |

The whole correction is narrow: `_checkpoint_policy` produces a transient worker-owned task-policy copy carrying the existing actual `_authority` check captured to this config/run/journal/owner. Normal checkpoint and stale/rework paths use it. `_freeze_checkpoint` permits that callable at its existing pre-intent, pre-commit and pre-ref boundaries for ordinary/rework checkpoints as well as publication. These calls refresh real snapshot/main/Issue/dependency/policy/pins, cancellation, owner/PID/input/CAS and deadline checks. No alternate permissive authority predicate is introduced. Installed task JSON, normalized policy digests, journal/result schemas and model request/protocol/guidance are unchanged; the callable is neither a serialized policy key nor model-supplied data. Existing publication guards, durable intents, source checks and unknown fences remain intact.

Independently reran the original real-Git finding probe, again changing authoritative main only after the actual `write-tree`. Corrected result: `needs_input / policy_revoked`, unchanged checkpoint/ref, no new effect, no commit-tree or update-ref command. The reproduction now passes its intended safety assertions; this is separate from the author's tests.

Fresh independent command, using the existing absolute Python documented above:

```text
-m unittest tests.test_pipeline_worker.CheckpointFreshnessTests tests.test_pipeline_worker.WorkerTests.test_six_roles_in_order_with_receipt_bindings tests.test_pipeline_worker.WorkerTests.test_completed_checkpoint_recovery_does_not_create_second_commit tests.test_pipeline_worker.WorkerTests.test_test_executor_mutation_consumes_development_rework_with_real_snapshot -q
```

**7 tests in 172.627s, OK, zero skips/failures/errors.** The four new multi-scenario tests exercise normal pre-intent main/policy/Issue/pins/cancellation loss; rework pre-intent main/policy loss; both normal and rework revocation after durable intent and after actual commit creation; preserved dirty source and unchanged ref/checkpoint; unresolved intent/unknown ownership and no subsequent replay. Three additional real subprocess/Git flows independently confirm six-role progression, completed-checkpoint recovery and failed-test mutation returning through fresh development rework. The original 136-test independent baseline above remains earlier-source evidence, not a claimed rerun of every test after this correction. Author RED4/GREEN4 and broader46-test results in the freeze are separate author evidence.

### Updated operational evidence and docs

Read the complete new independent V3 public audit, `installed-codex-smoke-review.md`, raw/canonical SHA256 `8b76a458bf35099fff76c648a882edb919c876a5cdcc9f5caf6fef70d66d4461`. It records a qualified local six-real-role/three-approval/fixed-check/ready_for_pr success at **committed 8981c6d**, with fixture GitHub HTTP transport and publishing disabled. The distinct audit independently checked443 V3 file bindings and retained166 original plus445 V2 bindings. This development review relies on that distinct auditor for the private pilot audit and does not claim to have rehashed those1054 private files itself.

The later checkpoint-freshness correction was **not** exercised by that installed-model pilot. This review accepts its specific source behavior through the new actual-Git fault regressions, not a fabricated model rerun. V3 does not override the original development rejection, diagnose the earlier unexplained unknown, erase either parked pilot or establish live GitHub/remote publication/service/night readiness.

Reviewed all five current shared/operator document deltas against the actual behavior and qualified V3 audit. A stale six-role-pending sentence in development-process.md was identified and corrected by the coordinator before this binding. Current bindings:

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| AGENTS.md | `ad3e7d8a57f3c954cf81e002f224ce57c2872e23d895a67826fae02141892d25` | `2f5afd0f5d79300e1caf34065068d6db3b8fe757577e0c794e9e15e1ce5dd03b` |
| README.md | `6de51aac462a993138397e9f4bfa3ab134535127c42d2b3bc2febaaa6472817c` | `3ad6429dedb29fa464b5d0bb8bbcf50c2036d80c329db0e9c31a09c904bcf6bb` |
| docs/roadmap.md | `45a9168ca633b79b002d393bca435e8588bb942354ecb4b7c89cb5fbfef49d9a` | `857dbf1ac3fcf8a4f2d2d0c90362cd4166df74e50a27a481e41d2eb3d126b504` |
| docs/development-process.md | `d32061e437fe18b062ac580e8d400f266e992626d431c124cfb4e908de827f2a` | `844d2bdfa3c8809dee9bdf35bd506056e73343ce1e4a92c5f2b476d5579283ce` |
| docs/pipeline.md | `5503bfd50141e88dacbd4e3ea08369c1875bc013f0ea4b4479293a15d6debd73` | `f8848e8c29449a740c961a076a72cc0369cebc72697f33df311da784abb4ce95` |

The docs distinguish qualified pilot source from the later authority guard, local different-repository overlap from same-repository serialization, fixture transport from live GitHub and ready_for_pr from integration completion. No broader credential or unattended claim is introduced. Only this review report was edited by this reviewer; no product/configuration/journal/model invocation/commit/push/GitHub write occurred. Changing bound source or documentation invalidates the affected acceptance and requires fresh review.


## R2 whole-development and combined security review — current verdict

2026-11-02, fresh combined review by the same independent development acceptor, distinct from implementers: **ACCEPT whole current development at the exact combined source/document bindings below.** No blocking development/security finding remains in this review. Original REJECT and R1 ACCEPT are preserved byte-for-byte as the prefix whose SHA256 is `da935ae536b6ae72c7c06771c2ee53660298b205d4d6006b4a5b6e4dfe3cbaa4`. This supersedes affected prior development bindings, not the separate TEST rejection or required current-head CI/PR/main gates.

Reviewed the complete new combined diff against HEAD `a569285d1966e53a5abe52a8b7f368d43321cc75`, with accepted main base `56f8ab12f21ab91030ffe54de96520fcd979dc04`, in the context of the previously reviewed whole branch. Exact combined ten-file freeze: `runtime-task7-combined-residual-freeze.json`, SHA256 `7b1885011282c846266b8060ca1952fe4f7a326cd6c2d20414f7052bc212d4d5`. Independently verified every raw/canonical binding at entry and again after verification. These working-tree inputs, rather than HEAD alone, are the reviewed correction. Specification and plan were not amended or waived.

| Combined file | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline_worker.py | `8e64df3ff9d77c6b43631b07e3709725fd285c900a70248347f5c1801b3bc650` | `3ac0ab44af3b67862b310f252b915fd98ab29bec120066707123e68c3e036dcb` |
| task_tower/pipeline_journal.py | `06f912afdd63a406ea29b60744dc1e33db5d76bebee1aff69cda063c842a5bf0` | same |
| task_tower/pipeline.py | `54a8473512c534497f12f3eebcacc978d6f8e8bec82cb6514df737073410bf47` | same |
| tests/test_pipeline_scheduling.py | `2ba9f1bb12999d500bf97c0129a86e04d526d56f36d87839ccb2b384b02a8ed2` | same |
| tests/test_pipeline_watch.py | `56b35edb3589d4119544afa486c5efd024876c20533057c270396c9ee988b9dc` | same |
| tests/fixtures/pipeline_http_site/sitecustomize.py | `e9ce2c0f8baf4323be00c9c929d843662c8dfee1125c2533e2708104fb9fb503` | same |
| task_tower/executor.py | `1bfda46856c3137f78052aa52779b2c634f859c0ce53df9355cec5dfbdc0d801` | same |
| tests/test_safe_config_race.py | `ec68ffff21642f49dcb5a20fe7aa9e5889c32e8929a7993725729733149e4f69` | same |
| task_tower/executor_queue.py | `febd031b51a835900e1bc4fad8548f3779e09afff3caa35e3ae80e1a8acf01b3` | `ead14695dd319def66baa4ecbfab8e6259e8ab97edc49ac87f9c0419803dd11c` |
| tests/test_private_sqlite_stat.py | `24d56bc226ea497da5e81f1d7580ad572c724a9e2af53e683b6876396cd3e211` | same |

### Scheduling, source and private-state assessment

Read the complete scheduling adjudication, earlier typed-transient security review and current test-review history. The adjudication correctly identifies the previous priority omission; its rejected priority-waiver alternative is not applied. Production queued claims now obtain genuine `collect_snapshot`/`select_ready` ordering outside the DB transaction, observe the real `verified_done` result/error state, and pass only a validated finite transient priority hint to the atomic claim. Safe ready continuation remains first. Queued priority then sorts P0-P3/repository/Issue, skips conflicts, and excludes arrivals absent from the source-pass queue snapshot. Private mapping, initial preparation and fresh continuation authority still govern execution; an ordering hint is not admission or effect authority. No priority is hidden in persisted fields and no DDL/protocol migration was introduced.

Known clean queued revocation uses an exact full-row comparison under BEGIN IMMEDIATE and is restricted to unowned, zero-process, no-admission/no-worktree/no-deadline/no-attempt/effect/verdict rows. It creates a visible needs_input/policy_revoked outcome without fabricating frozen criteria or launching work. Stale, cancelled, active and unknown rows cannot be released this way. Criteria first bind at actual preparation. Unavailable source and captured partial dependency evidence leave uncertain candidates queued; later source polls cannot erase the verifier failure already observed for classification. Healthy independent work continues with a source warning. No-run source-unavailable reporting is bounded and unbound, not a new journal state or role-result schema. Public work returns exit1 for that unavailable result; internal transport may complete successfully. Queued read retries use the capped backoff, while eligible safe ready continuations bypass queued backoff.

The explicit `_paths` transient role is derived only from actual DB arguments and their exact three sidecars. Merely naming a config/request/result/main file with a sidecar suffix does not confer that role. `_private_stat` is used by both queue/journal safety checks only for their own exact sidecars; zero-link acceptance requires observed regular non-reparse metadata and a no-follow current-leaf recheck. Main/input snapshots remain strict, including inputs whose names end -journal/-wal/-shm. Hardlink, directory, junction/symlink, collision and checkout guards remain active. Queue alias disappearance is tolerated only for its own sidecar while the forbidden input is rechecked strictly; initially missing optional outputs retain their old behavior. These are narrow transient observations, not descriptor-level immunity to hostile filesystem replacement.

The five adjusted HTTP fault fixtures now delay only after read-only observation of actual matching process ownership. This keeps their existing post-claim cancellation/unknown assertions and timing limits meaningful after preclaim source selection was added. No journal write, weakened assertion, changed timeout or forced-true readiness verifier is used. The distinct preclaim cancellation case correctly expects an unowned queued row with no execution effects.

### Fresh independent verification

Used existing absolute Python `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`:

```text
-m unittest tests.test_pipeline_scheduling tests.test_private_sqlite_stat tests.test_safe_config_race tests.test_executor_queue tests.test_pipeline_journal tests.test_pipeline_cli tests.test_pipeline_watch.WatchTests.test_real_dispatch_adapter_to_six_roles_and_host_tests tests.test_pipeline_watch.WatchTests.test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain -q
```

**124 tests in98.887s, OK, one unavailable-symlink privilege skip.** This independently exercises current genuine-source ordering/dependency/error handling, malformed hints, queued denial/CAS, strict sidecar/main/input roles and current replacements, capacity/unknown history, public unavailable exit/backoff/preclaim cancellation, and the actual six-role dispatcher/watch ready boundary.

```text
-m unittest tests.test_executor_adapter tests.test_pipeline_watch.WatchTests.test_shutdown_budget_with_external_sqlite_lock_and_live_owned_helper tests.test_pipeline_watch.WatchTests.test_watch_interrupt_uses_shared_shutdown_budget_and_preserves_unknown tests.test_pipeline_watch.WatchTests.test_cancelled_owned_action_is_contained_and_fenced tests.test_pipeline_watch.WatchTests.test_public_work_task_budget_stops_real_blocked_host -q
```

**7 tests in15.744s, OK, no skips.** Together these131 fresh focused tests preserve all five changed post-claim containment/cancellation/deadline regressions plus the legacy adapter. This is not a repeat of the earlier666-test complete run or a current full-suite/CI claim.

Separate independent probes also passed. Reversed the priorities in the actual HTTP-backed WorkerOrdering fixture: fresh P0 Issue16 was selected ahead of the formerly higher-priority Issue20, confirming behavior follows current genuine source rather than delivery/cached ordering. Ran both actual `_safe` methods under fresh disposable SQLite counter-table churn, with no application schema/rows/effects involved: ExecutionQueue1169 checks/676 commits, PipelineJournal1013 checks/650 commits, zero errors, both writers stopped. This short independent churn did not instrument/count zero-link observations and is not represented as proving that event occurred during this probe. Deterministic supplied tests separately use actual deleted-file metadata at controlled observation seams.

The author's frozen longer diagnostic observes old Queue28 errors (8 zero-link unsafe,20 disappearance), old Journal1 zero-link unsafe, and new Queue/Journal zero errors with13 actual zero-link observations combined; writers stopped. These are distinct author observations, not this reviewer's repeated counts. They support a demonstrated residual liveness correction, **not attribution of the original macOS generic policy_revoked failure**. That original cause remains unproven. Reported RED runs, earlier errors and later green runs remain distinct evidence.

### Current documentation and remaining acceptance gates

Reviewed all five current operator/shared documentation deltas against actual source and qualified pilot evidence. They describe priority/source-warning/unavailable/backoff behavior, preserve same-repository serialization and no fairness/distributed claim, and move live task phases to Issues/Project rather than embedding immediately stale active-Issue lists. Current exact bindings:

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| AGENTS.md | `37658c72eb33805fb63d1b17764aa351e46fe8469df2a9bc2e2fa3175d0e0f52` | `b5f0c8ce25a6d0c4266446be8865a150dd388c4232b9611589583b97fd284800` |
| README.md | `a51a640a81bf863905b8afac8872e113a869b0526308652b2e8229084c1fc9a6` | `58cbf2d73e841cb0275df4a2a83e089c39a2c8e2de18287a2edf23eb4fea06a4` |
| docs/roadmap.md | `3de88f1768b1738c96bab7bbc268706c044e2d1930ccf16fafb410e618b1609a` | `00dfeda5bc61f360a80d946dded9e9b0ecd6236ccc9cee16703cfe36db51f73a` |
| docs/development-process.md | `4f451b70679f750036741c3bbb04ca0b0c37e2338af735ce03ced5657b3ee915` | `d875f616cc88d96734357e796084cef8958ca45e5ae977d2abf14a51c2e21c47` |
| docs/pipeline.md | `76a4059996aff483b41e2c687a2172f2975bd95fd8a1e8d82c04769367c02cbc` | `48a007946b6bf7f97c2fdae04f910fa1f07158c60b32dae05f1295ad83b2b184` |

The installed-model pilot remains qualified solely to source8981c6d and fixture GitHub transport, publication disabled. It does not test later checkpoint-authority, scheduler/source or SQLite-sidecar corrections. Original166+445+443 pilot files and their distinct outcomes remain preserved; this review did not launch a model or claim a new private1054-file audit. The original unrelated Task6 unknown and macOS failure remain unproven as to cause.

The separate TEST review rejects a569 macOS CI despite its independent local666-test green run and Windows/Linux evidence. This development/security verdict does not turn that rejected head green. Required later work remains independent current-source testing/current three-OS CI, whole actual exact-head/base PR acceptance, serialized merge/main CI, independent postmerge acceptance and automatic Issue closure. No service/night/live-GitHub readiness is granted.

Only this report was changed by this reviewer. No product/docs/card, private installed configuration or pilot journal, Git ref, commit/push, API write or installed-model execution was performed. Changed source or documentation invalidates affected content-bound acceptance.


## R3 fixture-only APFS portability rebind — current development verdict

2026-11-02, same independent development reviewer: **ACCEPT the exact two-file fixture correction and retain whole-development acceptance for the current combined inputs.** No blocking finding in this delta. All original rejection/R1/R2 evidence remains byte-for-byte as the prefix SHA256 `ed30109c2a549839fe7048ff5c652fbc4c5cc13d306f060d6df2be7ea5865312`. This verdict supplies development reacceptance, not functional TEST, final-head CI, PR or main acceptance.

HEAD `e59d736157185f59bf7cf7cf01b47b7b673f249b`; base `56f8ab12f21ab91030ffe54de96520fcd979dc04`. Independently verified freeze `runtime-task7-apfs-directory-freeze.json` SHA256 `36907966f59bdb474c0b5b540254c93efb3ff1f657980f69ab9847f0fe93e942`, both changed test bindings, and all five production raw/canonical bindings against the prior combined source. All five accepted operator/shared docs also remain byte-identical to the R2 bindings above. Only the two test fixtures change:

| File | Raw and canonical SHA256 |
| --- | --- |
| tests/test_safe_config_race.py | `5b3f4978888fd5ef3d9915ff0967b3e5d7d0bf23af621564f29155e68cc34f44` |
| tests/test_private_sqlite_stat.py | `a2421b6c88af30409e914fd069a91244c01b0fa6634d0c147bf5d5f3434c81a8` |

Read the entire actual two-file diff. The helper still creates and removes a real inode, obtains actual fstat metadata, and verifies the path is gone. For regular files it additionally requires actual regular mode and link count0. For directories it requires actual directory mode without assuming a filesystem-universal link count. Thus APFS's observed deleted-directory count2 can reach the intended negative product guard, instead of failing in fixture setup. Production still rejects directory metadata regardless of link count.

The separate `modeled_directory_zero_info` explicitly labels its modified count as synthetic; the APFS-style count2 fixture contract likewise models only the link count on genuine removed-directory metadata. These are not claimed as actual APFS execution on this Windows host. Explicit modeled-zero negative tests retain coverage in executor `_paths` and both SQLite `_safe` layers. There is no guard change, new skip, timeout adjustment or relaxed hardlink/junction/collision assertion.

Independent existing bundled-Python command:

```text
-m unittest tests.test_safe_config_race tests.test_private_sqlite_stat tests.test_executor_queue tests.test_pipeline_journal tests.test_pipeline_cli -q
```

**96 tests in10.804s, OK, one existing unavailable-symlink privilege skip.** Added a separate independent probe using genuine removed-directory mode with explicitly modeled link counts0,2,17: all nine combinations across executor `_paths`, ExecutionQueue and PipelineJournal rejected the directory snapshots. No actual APFS host run is inferred. Reverified the two test and five production bindings after these checks.

Read the independent test review's completed e59 CI evidence: Windows713-test full pass and Ubuntu success are genuine completed observations; macOS has two fixture failures before the intended negative guards. This correction addresses that specifically identified fixture assumption. The older a569 generic policy_revoked cause remains unproven. The corrected-source local session that disappeared without terminal metadata remains incomplete; its65536-byte prefix is neither a full pass nor a diagnosed failure. No restart/substituted result is claimed by this development review.

The qualified source8981c6d installed pilot, prior parked outcomes and preserved1054-file evidence remain separate and unchanged; no installed model rerun exercised this fixture correction. Independent functional TEST and final exact-head six-context CI/whole-PR approval remain mandatory before merge, followed by serialized exact-main/postmerge/automatic closure. This review does not waive or predeclare those gates. Only this report was edited by this reviewer; no product, docs, card, configuration, pilot/journal, commit, push or external state was changed.
