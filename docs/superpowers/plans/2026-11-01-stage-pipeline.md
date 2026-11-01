# Automatic Stage Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run authorized tasks through independently accepted spec, development and tests, then create reviewable PRs with durable local watch/refill and no blind replay.

**Architecture:** A pipeline-specific adapter/journal owns admission, stages, local slots and effect intents; it never shares execution ownership with the legacy executor queue. Reuse existing profiles, instruction pins, role-aware additive harness APIs, process containment and genuine dispatcher/dependency verification. Host checkpoints and configured tests bind fresh reviewer receipts; only the host publishes accepted outputs.

**Tech Stack:** Python 3.11+ standard library, Git, installed Codex or trusted custom executable, existing GitHub transport/auth, SQLite DELETE mode.

**Spec:** `docs/superpowers/specs/2026-11-01-stage-pipeline-design.md`

## Global Constraints

- Python 3.11+ standard library only; Windows, macOS and Linux.
- Defaults: max_active=2 (1..2), interval_seconds=5 (1..60), task_timeout_seconds=7200 (1..86400), role_timeout_seconds=900 (1..3600), max_reworks=2 (0..5 per target stage), max_processes=36 (6..100), log_max_bytes=1048576 (1..67108864); profile timeout/log ceilings also apply.
- Preserve executor v1 configuration, v2 queue, existing CLI/six-key result, manual tasks and postmerge ReviewRunner behavior.
- No model selection, installation, new scopes, protection bypass, merge or Issue closure. #16 host creates PRs; #17 owns merge/main barrier.
- Product text uses `sha256-utf8-lf-v2`: strict UTF-8, optional BOM preserved as content, CRLF/bare CR -> LF, final-newline presence preserved. New designated spec/plan/criteria/MD-evidence artifacts require BOM-free UTF-8. Hashing never rewrites source or redefines legacy tasks._hash v1 proofs. Canonical JSON uses sorted keys, compact separators, ensure_ascii=True, allow_nan=False.
- Designated spec/plan/criteria/MD-evidence artifacts are at most 1 MiB each; other ordinary product blobs, text or binary, are at most 16 MiB each. Product manifest is at most 100,000 paths and 16 MiB. Size failures are explicit; no asset is silently excluded.
- Every role invocation has a fresh process/instance UUID; fresh reviewers differ from every contributing executor. Process completion alone never accepts a stage.
- Unknown launch/cleanup/effect retains fencing, execution slot and component locks. No lease expiry, unknown replay, destructive reset or automatic migration.
- Private state stays outside connected checkouts and rejects alias/link collisions. Model/custom/check children strip GH_TOKEN/GITHUB_TOKEN case-insensitively; only fixed trusted contained host CLI worker/dispatcher helpers may inherit existing host credentials as specified in Task6. Git child filtering is unchanged; credentials never enter arguments, JSON, configuration, logs or artifacts.
- User delegated routine choices and continuous two-Issue execution; no extra per-task chat approval. Independent stage acceptance remains mandatory.

## Review Focus

- An Issue's mutable stage/status projection changes while stable criteria do not: continuation stays privately owner-bound; foreign lifecycle or actual criteria changes block it (Task 1).
- A valid-looking approval arrives after source/policy/main changes: preserve it as rejected/stale history and never advance/publish from it (Tasks 2, 4, 5).
- A custom role or host test edits accepted source, Git refs or excluded evidence: detect it and invalidate affected acceptance; never silently trust custom sandbox claims (Tasks 2, 3, 4).
- Worker death or lost commit/push/POST response occurs after its intent: retain unknown ownership and never launch or write twice (Tasks 2, 5, 6).
- One task needs external input while another is ready, or a second watcher starts: refill unrelated capacity without stealing ownership, exceeding two slots or claiming cross-host safety (Task 6).

---

## File structure and dependency order

Create focused `task_tower/pipeline_policy.py`, `pipeline_inputs.py`, `pipeline_journal.py`, `pipeline_roles.py`, `pipeline_publish.py`, `pipeline_worker.py`, `pipeline.py`. Add role APIs to executor_harness.py and command routing to __main__.py only. Tests: `tests/test_pipeline_policy.py`, `test_pipeline_inputs.py`, `test_pipeline_journal.py`, `test_pipeline_roles.py`, `test_pipeline_worker.py`, `test_pipeline_publish.py`, `test_pipeline_integration.py`; fixture helper `tests/fixtures/pipeline_role.py`. Docs: `docs/pipeline.md`. Shared README/AGENTS/process/roadmap and integration evidence are coordinator-owned. #23 books/overlay work is separate.

Tasks 1–3 establish contracts; Task 4 joins them into stages; Task 5 adds publishing; Task 6 adds CLI/watch and integration; Task 7 freezes evidence for independent acceptance. Do not begin product code before fresh spec acceptance. Each task has a meaningful RED/GREEN and independent review boundary; no task may invent a second process runner or weaken genuine dependency verification.

### Task 1: Private pipeline policy and continuation authority

**Files:** Create pipeline_policy.py and tests/test_pipeline_policy.py.

**Interfaces:**
- `load_pipeline_config(path:Path, connections:list, executor_config:dict) -> dict`: strict normalized schema/defaults from spec; retain no credentials.
- `criteria_snapshot(issue:dict, metadata:dict, repository:str) -> dict`: exact stable criteria projection.
- `admission_authorized(config:dict, task:dict, snapshot:dict) -> dict|None`: return validated immutable Issue identity/criteria evidence only for existing select_ready eligibility.
- `continuation_authorized(config:dict, run:dict, snapshot:dict) -> bool`: fresh private owner-bound authority defined in spec; no remote metadata shortcut.
- Reuse existing `_pins`, profile_fingerprint, private path helpers and collect_snapshot/select_ready/verified_done. Provide injected store/source factories only at transport seams, with production defaults unchanged.

- [ ] Write failing tests `test_defaults_and_strict_bounds`, `test_alias_and_policy_escalation_rejected`, `test_criteria_excludes_only_mutable_metadata`, `test_initial_ready_and_owned_continuation_are_distinct`, `test_foreign_lifecycle_revocation_and_dependency_loss_block`. Assert all exact default values; reject Boolean integers, extra/duplicate keys, overlapping queue ownership, mismatched task mappings/publisher and unsafe relative paths. Confirm stage/phase metadata changes do not alter criteria, while title/prose/dependencies/Issue ID do.
- [ ] Run `python -m unittest tests.test_pipeline_policy -v`; confirm missing APIs/expected RED, not environment failure.
- [ ] Implement interfaces and exact configuration in spec, preserving legacy _authorized. Private component declarations, allowed-path policy, host check argv, CI substitution and publisher mapping are installed authority; model data never extends them. Revalidate unchanged saved bytes/pins on every authority call.
- [ ] Run `python -m unittest tests.test_pipeline_policy tests.test_executor_profiles tests.test_dispatch_selection -v`; require PASS and independent task review.
- [ ] Commit only Task 1 files with `feat: validate pipeline policy and continuation authority` after coordinator staging review.

### Task 2: Canonical immutable checkpoints and durable journal

**Files:** Create pipeline_inputs.py, pipeline_journal.py and corresponding tests.

**Interfaces:**
- `canonical_text(data:bytes) -> bytes` preserves optional BOM and normalizes CRLF/bare CR without writing source; `canonical_artifact(data:bytes) -> bytes` additionally rejects BOM for designated new artifacts. `canonical_json(value:object) -> bytes`, `digest_manifest(value:dict) -> str` use the spec's exact JSON scheme.
- `product_manifest(worktree:Path, task_policy:dict) -> dict`: sorted path/mode/scheme/digest records, exact exclusions/limits from spec; reject unsafe/model-evidence/card changes.
- `freeze_checkpoint(run:dict, task_policy:dict, journal:PipelineJournal, owner_id:str) -> dict`: host private index/tree/commit; return source/checkpoint/product/spec/plan digests, record intent before effects.
- `stage_manifest(run:dict, checkpoint:dict, *, stage:str, generation:int, prior_receipt:dict|None, checks:dict|None) -> dict`: exact spec fields.
- `PipelineJournal(path:Path, *, checkouts:tuple=(), forbidden_paths:tuple=())`; methods `submit(request:dict, policy:dict)->dict`, `lookup(delivery_id:str)->dict|None`, `status(run_id:str|None=None)->dict`, `claim(owner_id:str,max_active:int)->dict|None`, `record(run_id:str,owner_id:str,expected:dict,transition:dict)->dict`, `begin_attempt(run_id:str,owner_id:str,binding:dict)->dict`, `finish_attempt(attempt_id:str,owner_id:str,evidence:dict)->dict`, `save_verdict(run_id:str,owner_id:str,receipt:dict)->dict`, `begin_effect(run_id:str,owner_id:str,intent:dict)->dict`, `finish_effect(effect_id:str,owner_id:str,observation:dict)->dict`, `cancel(run_id:str)->None`, `recover()->list[str]`.
- `expected` in record is exactly state/stage/generation/input_sha256; all transitions CAS these and owner. `transition` carries only schema-validated next state/neutral evidence; methods enforce the spec state machine, not callers' arbitrary status. Canonical receipt/effect IDs and immutable bodies are journal-owned.

- [ ] Write RED cases `test_mixed_line_endings_are_stable_but_content_change_is_not`, `test_bom_powershell_lf_crlf_equal_and_bom_presence_changes_hash`, `test_hashing_preserves_source_bytes_and_legacy_v1_proofs`, `test_generated_artifacts_reject_bom`, `test_binary_asset_above_1mib_is_included_but_above_16mib_blocks`, `test_designated_artifact_1mib_limit_is_separate`, `test_no_card_or_evidence_self_reference`, `test_model_git_or_evidence_mutation_rejected`, `test_admission_identity_idempotent`, `test_fresh_db_schema_and_foreign_schema_rejection`, `test_cas_claims_component_locks_and_unknown_capacity`, `test_checkpoint_crash_before_and_after_ref_update`. Assert BOM-bearing Cyrillic PS1 LF/CRLF variants have equal v2 digests, removing BOM changes digest, checked-out bytes never change, binary/control-bearing product paths use raw scheme, and a 4 MiB image remains represented. Assert application_id=1414808656/user_version=1/DELETE/FULL, duplicate delivery no new run, second identity same Issue rejected, fresh claim cannot steal live/PID-uncertain owner, no schema reset.
- [ ] Run `python -m unittest tests.test_pipeline_inputs tests.test_pipeline_journal -v`; verify meaningful RED.
- [ ] Implement schema/constants/closed enumerations and validation together; use BEGIN IMMEDIATE with 5-second contention bound and existing safe-path/liveness patterns. Store canonical manifests/events, preserve superseded receipts, journal commit/ref intents before Git effects. Disable hooks through a private empty directory; reject unexpected HEAD, worktree alias, symlink/submodule and path-budget violation.
- [ ] Run targeted tests plus `tests.test_executor_queue tests.test_tasks`; require PASS. Independently review invariants and checkpoint effects before committing.
- [ ] Commit Task 2 files with `feat: persist fenced pipeline checkpoints and stage history`.

### Task 3: Fresh role processes and host test evidence

**Files:** Modify executor_harness.py; create pipeline_roles.py, tests/test_pipeline_roles.py and tests/fixtures/pipeline_role.py.

**Interfaces:**
- Add exact `build_role_invocation`, `role_result_schema`, `validate_role_result` signatures and strict v2 schemas from spec; preserve legacy functions.
- `run_role(config:dict, run:dict, binding:dict, role:str, journal:PipelineJournal, owner_id:str) -> dict`: launch one fresh role, return validated neutral outcome/result digest, store private result/log files separately. Record launch intent/count first.
- `run_checks(config:dict, run:dict, checkpoint:dict, journal:PipelineJournal, owner_id:str) -> dict`: run exactly saved checks with existing process runner; return the spec host test manifest, not model supplied command/status.

- [ ] Write RED cases `test_legacy_six_key_protocol_unchanged`, `test_fresh_ids_and_readonly_reviewer_invocation`, `test_wrong_input_generation_or_instance_rejected`, `test_extra_duplicate_and_oversize_output_rejected`, `test_exit_zero_without_proof_does_not_accept`, `test_tokens_removed_logs_capped_and_cleanup_required`, `test_test_mutation_invalidates_product`, `test_unwritable_temp_is_environment_not_product`, `test_ci_substitution_requires_explicit_exact_source_policy`.
- [ ] Run `python -m unittest tests.test_pipeline_roles -v`; confirm RED. Preserve real subprocess fixture execution for process semantics; mocks alone are insufficient.
- [ ] Implement stage-specific prompts/requests, instruction snapshots and six fresh role bindings. Use existing run_command cancellation/capture/containment; reviewers and test executor use read-only Codex. Trusted custom fixture writes only allowed outputs and returns strict binding; document custom OS access. Rehash product/HEAD before and after roles/checks. Run host checks from accepted checkpoint with private temp; do not run model argv. Separate no-op coverage rejection from actual configured-command success.
- [ ] Run `python -m unittest tests.test_pipeline_roles tests.test_executor_harness tests.test_executor_processes tests.test_reviewer -v`; require PASS and independent task review.
- [ ] Commit with `feat: run fresh pipeline roles and bound host test evidence`.

### Task 4: Deterministic bounded stage controller

**Files:** Create pipeline_worker.py; test in tests/test_pipeline_worker.py.

**Interfaces:**
- `next_action(run:dict, history:dict) -> str|None`: deterministic spec/development/test role/check/checkpoint/publish action from durable evidence.
- `step(config:dict, journal:PipelineJournal, *, owner_id:str|None=None) -> dict`: one bounded action, fresh authority before effects, no role replay.
- `apply_verdict(config:dict, run:dict, binding:dict, result:dict, journal:PipelineJournal, owner_id:str) -> dict`: validate current input/process proofs and reviewer independence, persist append-only receipt, advance/rework/park atomically.
- Return fixed run/status/stage/generation/reason and digests only. `step` consumes Task 1 policy, Task 2 journal/checkpoint and Task 3 role/check APIs.

- [ ] Write RED cases `test_six_roles_in_order_with_receipt_bindings`, `test_forged_card_or_model_completed_cannot_advance`, `test_reject_targets_invalidate_downstream_and_keep_history`, `test_two_returns_then_third_parks`, `test_stale_source_policy_or_main_never_accepts`, `test_ready_restart_does_not_repeat_completed_role`, `test_cancel_timeout_and_process_budget`, `test_started_unknown_cannot_rework`.
- [ ] Run `python -m unittest tests.test_pipeline_worker -v`; verify expected RED.
- [ ] Implement exact normal state sequence and typed reject routes; generation changes only for frozen new stage input. Enforce persisted deadlines/process counters, per-stage rework allowance and positive cleanup before release. A test source mutation consumes development rework and invalidates development/test receipts. Preserve all first rejections and superseded inputs; only a new fresh reviewer may replace a decision.
- [ ] Run Task 1–4 suites together; require PASS. Independent reviewer checks stage admission cannot be synthesized through journal status or untrusted result.
- [ ] Commit with `feat: orchestrate bounded independently accepted pipeline stages`.

### Task 5: Trusted publication with durable effect fencing

**Files:** Create pipeline_publish.py and tests/test_pipeline_publish.py.

**Interfaces:**
- `project_evidence(run:dict, history:dict, task_policy:dict) -> dict`: canonical host-only MD projections/manifest, no self-reference or private model prose.
- `publish_one(config:dict, run:dict, journal:PipelineJournal, owner_id:str, *, store_factory=GitHubTasks) -> dict`: one next commit/push/pr_create effect, never merge; use real default authenticated host transport.
- `inspect_effect(config:dict, effect:dict, *, store_factory=GitHubTasks) -> dict`: read-only observations, no replay or unfencing.

- [ ] Write RED cases `test_only_current_three_stage_acceptance_can_publish`, `test_projection_does_not_change_accepted_product_hash`, `test_exact_task_marker_and_private_mapping_required`, `test_remote_repository_and_changed_branch_rejected`, `test_host_push_then_pr_with_no_closing_keywords`, `test_commit_push_post_intents_precede_effects`, `test_lost_response_never_repeats_write`, `test_multiple_or_mismatched_prs_fence`, `test_changed_base_invalidates_pending_evidence`, `test_no_merge_or_issue_close_api`.
- [ ] Run `python -m unittest tests.test_pipeline_publish -v`; confirm RED. Use a real local bare Git remote and transport fixture for irreversible-effect ordering, never a live unauthorized repo.
- [ ] Implement exact publication intents/markers and response checks from spec; private task/publisher mapping and existing auth only. Use fixed no-force Git argv and compare remote ref; validate full PR identities. Return ready_for_pr if publish disabled, awaiting_pr only after positive durable PR observation. An ambiguous POST remains unknown even after no-match lookup; never retry POST based on absence.
- [ ] Run Task 1–5 suites plus existing publication acceptance tests; require PASS and independent publication security/effect review.
- [ ] Commit with `feat: publish accepted pipeline outputs with fenced host effects`.

### Task 6: CLI, local watch/refill and end-to-end fault tests

**Files:** Create pipeline.py and tests/test_pipeline_integration.py (focused CLI/watch test modules or fixtures may be split); modify __main__.py command dispatch and pipeline_worker.py watch controller. Add narrowly scoped journal-owned controller ownership/heartbeat/health APIs and their tests to pipeline_journal.py; preserve existing run ownership and state gates.

**Interfaces:**
- `pipeline.main(argv:list[str]|None=None) -> int`: exact CLI forms/exit codes from spec; adapter v1 wire response unchanged.
- `watch_tick(config:dict, journal:PipelineJournal, *, dispatch_tick=dispatcher.tick) -> dict`: one bounded source refresh/recovery/refill pass, at most one genuine dispatcher tick.
- `watch(config:dict, journal:PipelineJournal) -> int`: local controller loop, bounded workers, cleanup and backoff; one controller owner per journal.
- `adapter(request:dict, config:dict, journal:PipelineJournal) -> dict`: exact six-field request and durable pipeline receipt, no executor queue row.
- Journal-owned controller context/claim, heartbeat, release and read-only health accessors use actual owner UUID/PID and advisory-lock proof; no caller SQL, unknown-run reset or arbitrary takeover. Choose focused helper names consistently with the existing controller schema, and expose only validated fixed health counters/reasons.
- Fixed trusted host worker/dispatcher helper invocations use the existing contained runner and may inherit existing host GH_TOKEN/GITHUB_TOKEN for API authentication. Model/custom/check children keep child_environment stripping; Git transport filtering is unchanged. Helpers never persist or print secrets. Run genuine dispatcher.tick in a cancellable helper so slow source reads do not block watch cancellation/refill observation.

- [ ] Write RED cases `test_real_dispatch_adapter_to_six_roles_and_host_tests`, `test_duplicate_delivery_and_ticks_do_not_rerun`, `test_two_slots_refill_and_conflicting_keys_skip`, `test_clean_blocked_task_does_not_stall_unrelated_task`, `test_second_watch_and_multiple_workers_cannot_steal`, `test_unknown_retains_slot_and_components`, `test_preintent_transport_backoff_not_delivery_resubmit`, `test_restart_at_every_intent_boundary`, `test_status_cancel_inspect_after_profile_revocation`, `test_sigint_cleanup_and_fixed_public_json`.
- [ ] Run `python -m unittest tests.test_pipeline_integration -v`; verify RED. Integration substitutes only GitHub transport; genuine selection/dependency verifiers must consume well-formed fixtures instead of a true-returning predicate.
- [ ] Add real-process regressions for environment-only host API authentication versus stripped role/check environments, a slow genuine source helper interrupted within the cleanup budget, duplicate controller claims and controller exit retaining unknown run locks. Assert no credentials in any arguments/result/log/config artifact and no backend resubmit after a committed delivery intent.
- [ ] Implement parser/routing and existing dispatcher integration with separate private journal; validate backend identity and no overlapping legacy ownership. Spawn at most two local bounded task workers; process groups/Jobs come from existing runner, not naked uncontained Popen. Persist controller heartbeat/health, poll completion, skip conflicts and refill without chat intervention. Preserve unknown locks and terminal parked identity. Implement read-only inspect and status/cancel without requiring executable pins. Backoff exact 5/10/20/40/60 seconds only for pre-intent read failures.
- [ ] Run full `python -m unittest discover -s tests -v`; require PASS, then current three-OS CI on exact integration head. Independent task reviewer checks actual watch lifecycle and no implicit distributed claims.
- [ ] Commit with `feat: operate durable local pipeline watch and automatic refill`.

### Task 7: Operational evidence and whole-branch acceptance

**Files:** Create docs/pipeline.md; coordinator owns shared docs/card/evidence integration and GitHub status.

**Interfaces:** Documentation consumes exact shipped CLI/config/result/state contracts; no new product APIs.

- [ ] Document private configuration example with all task row fields, trusted publisher mapping, default bounds, role source/temp policy, genuine dispatcher backend, start/stop/status/cancel/inspect, conflict declarations, parked/unknown behavior, and explicit #16/#17/#18/#19 boundaries. Say local watch requires a running host process; no service installation/night-ready claim.
- [ ] Run a bounded installed-Codex scratch pipeline with existing authentication and approved pins, no external repo writes, fixed benign task/check and role/deadline budget. Preserve private requests/results; report hashes, six fresh instances, input bindings, process/cleanup outcomes and actual limitations. If environment prevents a role, record blocked rather than claiming custom fixtures prove Codex.
- [ ] Run full suite once after final changes; inspect exact diff against current main, freeze canonical product/spec/plan/evidence manifests and request distinct independent development and test acceptance. A changed source or evidence input invalidates affected acceptance and requires fresh bounded review.
- [ ] Coordinator obtains fresh whole actual PR diff acceptance bound to exact head/base, records task-tower/pr-acceptance, requires all current CI/mergeability/no blocking findings, and merges with expected head only behind the prior main acceptance barrier.
- [ ] Verify exact main CI, distinct independent postmerge acceptance, automatic verified Issue #16 closure and Project projection. Only then release this Issue's integration cycle and automatically select the next eligible authorized backlog task. A created PR or passing CI alone does not complete this Issue.

## Plan self-review

Spec coverage: policy/authority and criteria (Task 1), canonical source/checkpoints/journal/recovery (Task 2), roles/checks/temp/CI limitations (Task 3), bounded stage proofs and history (Task 4), host reviewable PR effects (Task 5), actual watch/two slots/refill/restart/transport fencing (Task 6), installed-runtime evidence and serialized integration (Task 7). All five Review Focus entries have named tests. Signatures above are the integration contract; builders may choose focused helper names/SQL column ordering within those interfaces, but cannot weaken schemas, limits, states, authority or evidence gates. No product implementation is contained in this plan.
