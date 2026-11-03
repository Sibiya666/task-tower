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


## Same-Issue postmerge timeout recovery — scoped development acceptance

2026-11-02, independent development reviewer distinct from recovery author: **ACCEPT the exact bounded workflow correction below.** Original development review history remains byte-for-byte as prefix SHA256 `6601b78698608d4051d5f7963865997424488507cdcdce11c12ee6d69fdd5abb`. Recovery base is exact merged main `d5cf8953b70caf5329d5173b7fb4a15eaa4df978`. This is the same Issue16's incomplete postmerge cycle, not authorization to pass its barrier or integrate unrelated work.

Reviewed the actual entire workflow delta and new recovery evidence. The sole operational change is `.github/workflows/postmerge.yml` verify-merge job timeout15 to45 minutes. Independently compared normalized workflow bytes with the base Git blob: they are identical after precisely this single substitution. The three-platform matrix, exact merge-commit checkout, read-only contents permission, disabled persisted checkout credentials, Python3.11 full unittest command, failure export/artifact and explicit failed-test gate are unchanged. Product source and test behavior are unchanged; no cancelled run gains approval.

| Reviewed file | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| .github/workflows/postmerge.yml | `7dd1c8797dbddf1232ab88985d8dfbbba50c9419d40618a7935ed0e6028233ee` | `194fca1f6743aac62dbbf7b29e15a2ff402f70e92ff260a91b66bc9c79a1d570` |
| docs/tasks/evidence/TT-PIPELINE-001/postmerge-timeout-recovery.md | `ce77c22d21b6b4148d51122214d803508181443c9c732ee6fc48d45a936aacdf` | same |

The recovery evidence records postmerge run41451105738 Windows job125296237186 exceeding the explicit15-minute maximum, Linux/macOS success, and a preceding successful Windows full-suite job taking about30 minutes including setup/cleanup. A bounded45-minute job budget accommodates the demonstrated runtime without weakening checks or inferring that timeout means product correctness. This differs from the older unproven a569 authority failure; that uncertainty remains preserved. No full product suite was rerun for this configuration-only delta. Fresh six-context CI, independent TEST/whole-PR review, exact-head/base merge controls and a successful new exact-main postmerge/automatic publication cycle remain required.

The recovery note honestly keeps Issue16 open and main acceptance pending. No Issue closure, delivery/journal reset, installed-model invocation or pilot rewrite is supplied by this review. The reviewer appended only this report and refreshed only the task card's development evidence digest as explicitly authorized; no source, workflow, shared docs, test receipt, commit, push or external state was changed by this reviewer.


## Recovery cancellation-observation correction — scoped development reacceptance

2026-11-02, independent development reviewer distinct from implementer: **ACCEPT the exact two-file correction below.** No blocking finding within this correction. All prior history is retained byte-for-byte as prefix SHA256 `8e6cee7741aa56212aab75ff11775b2f744b45b76101ce8f7beadc6b712124ca`. This is source/behavior acceptance, not current functional CI, PR or main/postmerge acceptance.

Reviewed entire actual diff at HEAD `3de7f94c7b7f40293a8cf673bc68877fba377830`. Freeze `runtime-pr42-observation-freeze.json` SHA256 `ffd0ba0b725174a1107ba19b8b12d41c9fc6fea2d7608ea0535897228a8af051` matches independently. Its `base=56f8ab1` is the historical original Issue16 baseline, not a claim that the current recovery PR targets that old main. This scoped review compares the working-tree correction with actual HEAD3de, descended from the merged D5 recovery baseline. Final PR acceptance must bind its actual then-current head/base separately.

| File | Raw and canonical SHA256 |
| --- | --- |
| task_tower/pipeline.py | `8a8ca085c51ca9c932cb5513da06603b01c26bdbda86a5321b90d3691ff170d5` |
| tests/test_pipeline_watch.py | `98fd4e207996bf1ff8d15eb0a2e4100be09e964ca9bfe3efeb6caf8da99a824b` |

Production changes only the internal cancellation-read observation budget from0.2s to1.0s and rechecks stop immediately after successful status read. Stop-before-read remains first. Actual deadline/SQLite/ownership errors still propagate into the existing unknown/fenced runner path; no failure is converted to False. The task UTC/monotonic deadline, role/check limits, process containment, five-second shutdown budget, journal schema/API, source authority, proofs and no-replay behavior are unchanged. A one-second observation tolerance accommodates the demonstrated350ms validated read without increasing task/model/test budgets or granting uncertain work permission. Reads exceeding that budget still fail closed.

Fresh independent existing bundled-Python command:

```text
-m unittest tests.test_pipeline_watch.WatchTests.test_owned_role_survives_350ms_validated_cancellation_read tests.test_pipeline_watch.WatchTests.test_owned_role_read_beyond_one_second_retains_unknown_intent tests.test_pipeline_watch.WatchTests.test_stop_during_validated_cancel_read_remains_bounded tests.test_pipeline_watch.WatchTests.test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain tests.test_pipeline_cli.ControllerTests.test_host_budget_is_own_run_bound_and_monotonic -q
```

**5 tests in34.128s, OK, no skips.** These use actual contained role launches and durable owned executing/launch-intent observations before delaying real path validation.350ms completes ready with actual cleanup;1.2s retains unknown/unresolved launch intent, positive role death and no replay; stop during the read cancels and cleans up within five seconds. The held exclusive-SQLite public-work interrupt and independent monotonic owner budget also pass. All supplied assertions remain intact, with no replacement authorization predicate or completed-result invention. Independently rechecked both raw bindings after execution. Author three-test RED/GREEN and87-test watch/journal/worker results are separate evidence, not this reviewer's reruns.

The observed local cancellation-read trip and controlled actual-role delay support this narrow correction. They do not establish the cause of the original macOS failure; twenty instrumented macOS debug passes are diagnostic observations, not qualification. The earlier PR42 Windows readonly-database errors are a separate issue and are **not claimed fixed by this patch**. Current full new-head CI and fresh independent PR review remain required; no green legacy run is substituted for those gates.

All preserved model pilots remain source-bound historical evidence; no new installed-model run, pilot reset, private schema change or credential/OS configuration action occurred here. The reviewer changed only this report and the explicitly authorized development evidence digest in the task card. Separate TEST receipt and all source/workflow/shared documentation were left unchanged. No commit, push, external write, merge or Issue-completion claim is supplied.


## Whole recovery candidate development/security review — current verdict

2026-11-02, independent development acceptor distinct from implementers: **ACCEPT whole current recovery development/security at the exact code and documentation inputs below.** No blocking finding remains in this reviewed candidate. All prior original rejection/R1/R2/R3, timeout and observation-window reviews remain byte-for-byte as prefix SHA256 `9778ece08b5b1798551279a15a5cef816e8d06e7682eb222ec78cbd3e1a174aa`. This is development acceptance, not fresh functional TEST, CI, PR or exact-main/postmerge completion.

Reviewed the whole actual recovery diff against merged main `d5cf8953b70caf5329d5173b7fb4a15eaa4df978`, current committed HEAD `3de7f94c7b7f40293a8cf673bc68877fba377830` plus frozen working-tree inputs. Final six-file source freeze `runtime-pr42-delivery-final-freeze.json` SHA256 `32eef1c127f4d0ec68ff9b1ad434e853972dc0feff04dcfafca85f5ee6e571c7` independently matches. Its actual PR42 base is D5; original56f8ab1 remains historical Issue16 foundation. No exact-head/base acceptance is inferred for the eventual new commit.

| Source/test input | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| task_tower/pipeline.py | `e78ad0862980afb4b16df631ac4143cca8f79179b93d89319cceab09bf46a9c5` | same |
| task_tower/pipeline_journal.py | `139383295cb16ffc05fd80224e8d8c78932ea71e091f2cfd4ed50e2f96141cc0` | same |
| tests/test_pipeline_watch.py | `64e052410070f33dedd78b89fc95ffb29ce11f4c004e54d6c5c4fe14b760184e` | same |
| tests/test_pipeline_shutdown_recovery.py | `969ec9fb06160c72c42917b7b66c92b46361757bf357858712d00ec3a5d5c392` | same |
| task_tower/dispatch_delivery.py | `f99517ddaea8b46d2bbe02b1feb087f880b21faa8ee06f388e51595113d0343e` | `c5f247aa6433b84e7db814ffe3b32e2d8e7dd2fc3e3cfdd562448adb8c58bbb4` |
| tests/test_delivery_sqlite_race.py | `dd119c7bbdf569473e727347c62fff55c446bb2659cca1586749b2307ddb8a16` | same |

### Preserved initial hot-fallback rejection and corrected existing-only boundary

Initial four-file freeze04e0e38642100dd32b25f48b7efe4f1d7e766662c243ac565ddef32e92ad99d8 was independently **REJECTED P2**. Private rejection receipts: JSON SHA256 `74988a7db34ce49fb3c13e44610bd50c119eadfb5ceb67cd6a425f2a66207dfb`, Markdown `e50e6ae29a771ded2a016c315b28f43cb259975fdfef38c034f1eda19cdfaedd`. The actual-hot SQLite probe created80valid rows, used genuine cache spill/os._exit23 and actual contained cleanup, observed genuine read-only rollback error776, then removed the database only after successful real recovery. The initial fallback reported confirmed=True with database_exists=False because its follow-up public status treated absence as an empty journal. The inline probe's temporary DB was cleaned afterward; the private receipts preserve actual tool output/provenance without inventing retained raw files. The earlier9778 two-line observation acceptance never accepted this initial fallback.

The corrected private existing-database context spans strict recovery, subsequent RO status, cancellation/controller/release writes and final confirmation. It uses URI existing-only connection semantics and disables initialization/parent creation for every write in that context. Physical dev/inode identity, regular/single-link/non-reparse metadata, unchanged exact APP_ID/version/schema/DELETE/FULL and remaining shared operation budget remain checked; write transactions additionally check physical identity before commit. Missing/empty/foreign/replaced state cannot become empty success or fresh initialization. The context finalizer only restores private state and performs no I/O. Public status stays read-only and ordinary startup/public recover compatibility is retained. This is bounded same-host path evidence, not a claim of descriptor-level immunity to hostile concurrent replacement or distributed fencing. SCHEMAS AST was independently compared with HEAD and is unchanged.

Fallback is limited to a real chained sqlite3.Error extended code776, after every actual host has completed with positive contained cleanup proof. It retains the original4.8-second shutdown deadline and does not retry/reset/replay unknown work. Explicit cancellation applies only to exact worker owner UUIDs, including the newly recovered unknown state; normal completion invents no cancellation and unrelated owners are not cancelled. Unknown ownership/effects remain fenced. A pre-commit deletion test initially expected path absence, but actual SQLite rollback restored the original valid state. The revised expectation requires failed confirmation, exact original rows/schema/history/owner/cancel/controller state and no replay; deleting a valid restored DB would be wrong. The original failed assertion and diagnostic are preserved separately.

Independently reran the original actual776/recovery/unlink reproduction at corrected V2: confirmed=False, DB remains absent, no recreation,1.992s. Independently ran all `tests.test_pipeline_shutdown_recovery` plus `WatchTests.test_shutdown_recovers_actual_hot_journal_only_after_contained_cleanup`: **9 tests in21.248s, OK, no skips**. These cover actual hot recovery with cancelTrue/False and unrelated owner, unconfirmed cleanup/deadline, no initialization, app0/foreign/malformed/WAL, disappearance before/after recovery and later writes, physical replacement, commit rollback preservation and no replay. These four code/test bindings remain unchanged in the final six-file freeze.

### Delivery-journal guard correction and causal limits

The next author96-test run failed one delivery read; its complete log SHA256 `1801f38e646fe3527c8e44e205c75fefba99dc85404d6aa34c6c211fd658dd79` remains a failed/unattributed observation. Its cleaned fixture and suppressed original cause prevent assigning that failure to a particular race. A later churn pass and one watch pass likewise do not diagnose it.

Separate deterministic real-SQLite writer timing barriers demonstrate actual sidecar disappearance between a genuine positive existence/stat observation and later stat/alias operations. Barrier proof SHA256 `30844230309ba10d4716052fefdba4a2e52311995f426766088339da4ca98438` independently matches. These prove the guard races themselves, not the lost96-test or original CI cause. The correction reuses the existing private-stat helper only for the journal's exact three derived transient sidecars. Main and positively observed forbidden inputs remain strict, including suffix-named files. Validated snapshots support samestat alias checks without a second racy lookup; canonical/checkout, type/link/reparse, optional-initially-absent, DELETE/WAL, readonly, schema/backend/identity and no-replay contracts remain intact. Actual OSError/sqlite3.Error causes are chained privately; generic public error text and neutral CLI JSON remain unchanged. No recovery or delivery resubmit policy is added.

Independent actual command `-m unittest tests.test_delivery_sqlite_race tests.test_dispatch_delivery tests.test_dispatcher -q`: **44 tests in5.371s, OK, no skips**. Includes both actual SQLite commit timing barriers, genuine deleted-file metadata, strict main/input loss, hardlink/directory/junction replacements, causal errors, neutral CLI and cold imports in both module orders. The earlier independent five observation-window controls remain their separately bound scoped evidence; the reviewed window/stop behavior is unchanged. No redundant complete suite is claimed by this reviewer.

The final author combined log `runtime-pr42-delivery-current-combined.log` SHA256 `1c16bea0d050c0d499aff0171a7b9807d60ef4c3d37d3fd3aff59ef747f29ebe` reports **169 tests in760.633s, OK, one existing privilege skip**. Independently checked its hash, read the entire decoded output and scanned for failure/error/traceback/thread/resource/runtime warnings: none recorded. This is verified author-run evidence, separate from the independent9+44 executions. Earlier96 failure, initial P2 rejection and preliminary fixture/probe errors are not relabeled green. No current-head full CI success follows from this focused run.

### Complete recovery documentation and remaining gates

The timeout workflow remains exactly the previously accepted15-to45-minute substitution; full tests, exact merged checkout, read-only permissions, three-platform matrix, failed export and failure gate are unchanged. Read the entire new recovery-observations note, prior timeout note and actual card/test/development-history deltas. Notes preserve cancelled/unknown/rejected runs, the initial P2, SQLite rollback-restoration finding, unattributed96 failure, independently proven mechanisms and qualification limits.

Reviewed all current coordination/setup document changes. They record the user's resource-based coordination decision while explicitly preserving this v1 binary's originally specified numeric two-slot limit until separately specified/reviewed #18 work. They do not rewrite Issue16's admitted criteria, journals/backend bindings or runtime validators. Per-repository serialized integration and unknown fences remain required. Setup's existing CLI/PATH clarification adds no login/scope grant; it distinguishes launch-environment visibility from credential authority. Current canonical/raw documentation bindings:

| Input | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| .github/workflows/postmerge.yml | `7dd1c8797dbddf1232ab88985d8dfbbba50c9419d40618a7935ed0e6028233ee` | `194fca1f6743aac62dbbf7b29e15a2ff402f70e92ff260a91b66bc9c79a1d570` |
| AGENTS.md | `3c6b107b29251033682e2ea1581a17dd07dea2ff52dffae969728b2a3884f411` | `b55c1a19836822248e3584b94b2c51a9e509d8e7785c0df50b7ec0772d4a0330` |
| README.md | `81b4ffcaf4d2be5d7ec2aa92b465eaeac962975d32296c7942a591862f161487` | `9100c9ae81e5eaffd07b1d0fff39746d675e76263089b9db53ef36a8c2dcc2e4` |
| docs/development-process.md | `9d8bea073e7c41b4ca451219a4d58260ae76f843dd9b29775c7b7b8b5ecc3211` | `564f46de80ffb69a25c5307add2b992dd47d48235214ed3f8e37b42b8628a56d` |
| docs/roadmap.md | `0f922d9b958b22bd21faea67493a72432901d5abeaf7510ff7754af0ce77595c` | `2c195aa55dc6a67f6548744322fc2ece58ca032e377ec875d35cba84b38cb0f3` |
| docs/github-setup.md | `e0e70b807150a3877a36f5449b9aab454f481009231b29b8a88963f86c4b3ad1` | `e825e8ea62c13263a843d6cd42757a48c1cef4931105ffde1f5166186b798df9` |
| docs/tasks/evidence/TT-PIPELINE-001/recovery-observations.md | `9a081dd0c0f2f219e243c48916b903fafd5fa23a5fab684711688969336773f9` | same |

Original macOS unknown and Windows readonly CI causes remain **UNPROVEN**; twenty instrumented macOS debug passes are not qualification. The new causal mechanisms are real but cannot retrospectively identify uncaptured failures. No fresh complete final-head CI/functional TEST/PR verdict is fabricated. The current card still projects previously scoped receipts pending coordinator reconciliation; editing it cannot grant acceptance.

All1054 original/V2/V3 pilot artifacts remain their separately preserved source-qualified evidence; this reviewer did not run a new model or claim an additional private1054-file audit. The source8981c6d fixture-transport/publish-disabled pilot does not test later recovery code. Same Issue16 remains incomplete until independent current TEST, new complete exact-head CI, fresh whole-PR head/base acceptance and successful exact-main/postmerge/automatic Issue publication. This review grants none of those later gates.

Only this public development report was edited by this reviewer. No code, tests, card, shared docs, workflow, installed configuration/journal/pilot, commit/push, API or model execution was changed/performed. All earlier prefix bytes remain intact; changed bound inputs require fresh affected acceptance.


## Windows release recovery: whole-development/security re-review — ACCEPT (2026-11-02)

This verdict binds the complete current recovery candidate against accepted main base `d5cf8953b70caf5329d5173b7fb4a15eaa4df978`, parent HEAD `a7e69ae364d892b44667e36af35e5c10bfbc3175`, plus the frozen working delta. It is development-stage acceptance, not current CI, PR, main/postmerge, Issue closure or night-readiness acceptance. The exact 22-file freeze `runtime/pr-acceptance/pr42-windows-candidate-freeze.json` has SHA-256 `953915f2a325a393c1563778b1ed321a6ea6e16d3d8d966cb24a2cfe72fda137`. Independently recomputed every declared raw/canonical file hash and all four log/source-manifest hashes; all match. Canonical v1 preserves BOM and changes CRLF to LF only. Stage projections are excluded from that source freeze and remain append-only; every previous byte of this report, SHA-256 `48510ed4c6b418687091e9f646211ccea8f0b8491a220efbbc17f6af1ccc1c8c`, is retained.

The user-approved dated Windows scope amendment has fresh independent specification receipt `d495c4b735952ef34808a6f0671bf453888c96337ecff95050d3b99909fa0d8e`. Reviewed actual source/test/document deltas and platform matrix together with the prior whole review and rejection history. Public work/watch/internal action/dispatch reject unsupported platforms before `_runtime`, journal initialization or launch; direct work/watch/watch_tick/action/dispatch and host construction also reject before effects. Adapter admission/lookup/status/cancel/inspect remain portable; cancellation never asserts cleanup. Fixed helper authority, role contracts, source/criteria boundaries and unknown/no-replay remain unchanged. Actual existing process/role/test-role bytes match a7 after LF normalization; saved POSIX scope/bootstrap modules are absent. Their remote WIP and future native qualification do not grant current execution authority. Three-platform generic CI remains mandatory.

Ordinary and hot-journal shutdown retain the physical read-only noninheritable OS descriptor through the whole existing-only context. Windows share-read/write/delete permits real SQLite writes and deletion without denying the identity test. Missing initial state retains prior startup behavior; existing state uses strict no-init/no-mkdir writes, regular/nonreparse/single-link identity checks against the held FD, precommit and final checks, close before proof and the same 4.8-second deadline inside the five-second parent contract. Public recover defaults and exact SCHEMAS are unchanged (independently compared AST values to D5). The fallback remains actual SQLite extended error776 only, after positive contained-host cleanup; no general readonly autoheal, unknown clearance or replay. Delivery transient treatment remains limited to its exact three derived sidecars, with strict primary/forbidden inputs and validated-stat alias comparison.

The late normal-path P2 was a rejection of the previous pin candidate: the held FD existed but only the hot fallback activated identity enforcement. An actual inline Issue1→replacement Issue999 probe returned confirmedTrue; that disposable fixture/script was not retained, and no retained-fixture claim is made. The correction enters existing-only enforcement before the initial read for every nonNone pin and retains it through final proof. Independent retained probes now return confirmedFalse for both deletion (path absent) and valid replacement (original Issue1 retained separately, current Issue999). Six no-host pin/normal/close/deadline tests passed in1.300s. Script SHA-256 `1138e01c815890b11a815a5625ad5068724c4a33ecad1d2d49ce1e1d638c667a`; JSON result `9575afb4aa4b0507aafab9930e4925b6619dbeac8d25c96b796dbba99adbf132`. An initial script-path invocation lacked PYTHONPATH and failed import; corrected repository PYTHONPATH invocation passed, not a product failure.

The initial hot-fallback P2 rejection (`74988a7...` / `e50e6ae...`), corrected strict context, precommit rollback expectation failure, deterministic delivery barrier `308442...`, and unattributed failed96 log `1801f38...` remain preserved above. The later mutable59 run failed one six-role cleanup_unknown case, log `c205b91985eb1486aa1f0963365ac6b392b3516344e3c52eb424ae6b13dbf754`; changing dependencies prevent whole-source qualification or causal attribution. Native Ubuntu actual inode reuse and live POSIX orphans are separately documented evidence, not retroactive proof of the original generic macOS/Windows CI causes, which remain unproven. Historical failures are not relabeled passing by the amended scope.

Inspected complete bounded log endings and verified their hashes: author Windows full suite751 tests1485.720s OK7skips at unchanged production pipeline `5af888...`; subsequent final20 targeted tests9.401s OK1skip cover the three late test-only edits. Those edits preserve Windows assertions: a capability seam isolates the already mocked CLI result mapper; three actual helper/native scheduling cases are individually classified; the actual unsupported-host test now states unsupported rather than simulating Windows qualification. Native watch cases are individually Windows-only; portable source/dependency controls exercise actual dispatcher/transport directly. No mixed module blanket skip, new timeout waiver or CI matrix removal. Independent prior current-source delivery44/strict9 and observation5 evidence remains qualified by its exact unchanged seams; no redundant full suite was launched by this reviewer. All1054 installed-Codex artifacts retain their historical source qualification: no new installed-model pilot is claimed for this candidate.

No remaining blocking development/security finding in this frozen Windows scope. Fresh functional-test acceptance, all six current push/PR CI jobs, independent whole-PR exact head/base acceptance, mergeability/protection checks, and exact-main postmerge acceptance plus verified automatic closure remain required.

Exact source/document bindings (raw / canonical SHA-256):

| File | Raw | Canonical |
| --- | --- | --- |
| `.github/workflows/postmerge.yml` | `7dd1c8797dbddf1232ab88985d8dfbbba50c9419d40618a7935ed0e6028233ee` | `194fca1f6743aac62dbbf7b29e15a2ff402f70e92ff260a91b66bc9c79a1d570` |
| `AGENTS.md` | `1309feb8579ae49e6c845d736fcfe1975d359273940777bf1bc6e8e39165b473` | `1bd73cdc828169daaa9f0f004cc47f39086a7e25e9954f53701fc017985bf2a6` |
| `README.md` | `cdd9c76082bc07c9ba8cd43d4bfc7a7757fe33956f0456aa686054138ea6ae60` | `15d38379daf48c0f38fa8f75f01e62618fa155f539088af841aac68e1530fc94` |
| `docs/development-process.md` | `9d8bea073e7c41b4ca451219a4d58260ae76f843dd9b29775c7b7b8b5ecc3211` | `564f46de80ffb69a25c5307add2b992dd47d48235214ed3f8e37b42b8628a56d` |
| `docs/github-setup.md` | `e0e70b807150a3877a36f5449b9aab454f481009231b29b8a88963f86c4b3ad1` | `e825e8ea62c13263a843d6cd42757a48c1cef4931105ffde1f5166186b798df9` |
| `docs/pipeline.md` | `6228f59bf8c7010375403a17322c2b7b8842a5d6918f9499f389aee90f33c312` | `36573d58920ce65c1cd0521bcdeee3787e6e62ce4a5a4d7c3190f40166155253` |
| `docs/platform-support.md` | `339b2d6d51b5d2faa30054c51e0b042ec720b99dbba617cdaa3c6865a13ef089` | `1c7a94a048101a82e1a951c71168d1ca71ba111502c2ab30c01cb16c8e4fccaf` |
| `docs/roadmap.md` | `0f922d9b958b22bd21faea67493a72432901d5abeaf7510ff7754af0ce77595c` | `2c195aa55dc6a67f6548744322fc2ece58ca032e377ec875d35cba84b38cb0f3` |
| `docs/superpowers/plans/2026-11-01-stage-pipeline.md` | `d48b782e476349103455996bebb9144149326842c59b7ff1959a8390c1a05ee3` | `9ad15e11bbd107f605ee07fbc772c43a3bc068d5405c48430b8730312aeac3f9` |
| `docs/superpowers/specs/2026-11-01-stage-pipeline-design.md` | `5524d16570530662e25006e91e4159afecbecd103f327d1c1b9b48fc3d3fc6f5` | `e6356de1429dadae88f1263c3bd20dcb71528b2f3c9616f1a07b206e1acb40ca` |
| `docs/tasks/evidence/TT-PIPELINE-001/postmerge-timeout-recovery.md` | `ce77c22d21b6b4148d51122214d803508181443c9c732ee6fc48d45a936aacdf` | `ce77c22d21b6b4148d51122214d803508181443c9c732ee6fc48d45a936aacdf` |
| `docs/tasks/evidence/TT-PIPELINE-001/recovery-observations.md` | `03317108b37ccfca411b3e78242c26aa88eeb5f25588997f889690632e08490b` | `03317108b37ccfca411b3e78242c26aa88eeb5f25588997f889690632e08490b` |
| `docs/tasks/evidence/TT-PIPELINE-001/task6-spec-review.md` | `d495c4b735952ef34808a6f0671bf453888c96337ecff95050d3b99909fa0d8e` | `d495c4b735952ef34808a6f0671bf453888c96337ecff95050d3b99909fa0d8e` |
| `task_tower/dispatch_delivery.py` | `f99517ddaea8b46d2bbe02b1feb087f880b21faa8ee06f388e51595113d0343e` | `c5f247aa6433b84e7db814ffe3b32e2d8e7dd2fc3e3cfdd562448adb8c58bbb4` |
| `task_tower/pipeline.py` | `5af888019504a829b99ac56a194b6156c790d00f90d20405ac844d88d055890a` | `233d20d9324c554d886f912f61c52976d01cb882cf0522a67ab2f65cb86b5931` |
| `task_tower/pipeline_journal.py` | `c86e51acc4ae87e199a08c6982f7fb0debcab4e0a7a2fd1e2d59ec3bbd13fa66` | `c86e51acc4ae87e199a08c6982f7fb0debcab4e0a7a2fd1e2d59ec3bbd13fa66` |
| `tests/test_delivery_sqlite_race.py` | `dd119c7bbdf569473e727347c62fff55c446bb2659cca1586749b2307ddb8a16` | `dd119c7bbdf569473e727347c62fff55c446bb2659cca1586749b2307ddb8a16` |
| `tests/test_pipeline_cli.py` | `5fe436ac7b790812da4d94218c0f92fdf368c00fdef762f20d3b5b720d4d9b7a` | `f10cf60d69fb4812a65060b99002be8e0f98f73bcbda3de18e1b658d607426be` |
| `tests/test_pipeline_platform.py` | `72c6c5b0b2df54bdf642012ad32989296df6f38efde5b0d4245ea020290700f4` | `25b0f153b53f57636e2070348b36bd5d7ef4a0d86781cbf73d43efeb8b972da6` |
| `tests/test_pipeline_scheduling.py` | `5a7b931e27a202d5f4b1248376df2b39baacfb4c6755d0932d3e2bcc63d5fb29` | `40a3d064291e7a65a8234db02bef2e0574c4516ba76f15e4176dbaa4c0ea721c` |
| `tests/test_pipeline_shutdown_recovery.py` | `0056e4acc7c1f1b4c0e00caa2310bcc9507a48c73a68ac4e79ca6d9453a495dc` | `0056e4acc7c1f1b4c0e00caa2310bcc9507a48c73a68ac4e79ca6d9453a495dc` |
| `tests/test_pipeline_watch.py` | `7e3bfaf5998d2ac1cd30cd1f2329207f3b35b9e5e440e6f38d1d25b39774e4af` | `729b2716e5b7f7897166f1c6890394aa0be8aac487ac205202d8f76db358bff6` |
