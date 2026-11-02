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
