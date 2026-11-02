# Independent agent-groups specification and plan review

2026-11-02. Reviewer `/root/books_pr_acceptance`, distinct from specification author and future implementers. **REJECTED pending the single blocking contract correction below. Builder check: not implementation-ready at this binding.** This is a document/API-feasibility review only; no implementation, test, pilot, PR/main or Issue acceptance is granted.

## Exact reviewed documents

Authoring main `56f8ab12f21ab91030ffe54de96520fcd979dc04`, branch feat/agent-groups. Read the complete proposed design, plan and pending task card, repository AGENTS, applicable architecture/group/process clauses, current main dependency/profile/receipt APIs and the relevant read-only Issue16 candidate source invariants. Fetched actual GitHub Issue18 and compared its four primary and six continuous-parallel-process criteria; its current body records genuine admission48c93982-4c79-468c-a3eb-e4f6d05db14d. Admission/dependency acceptance history is coordinator/Issue evidence, not independently rerun admission by this reviewer.

Canonical SHA-256: UTF-8-sig decode, CRLF/CR to LF, UTF-8 bytes. All three were independently verified before and after review.

| File | SHA-256 |
| --- | --- |
| docs/superpowers/specs/2026-11-02-agent-groups-design.md | `ed3459bf485dba38bb77d75d23b0eebeb07ba8865dce19121ff4043b182ca52e` |
| docs/superpowers/plans/2026-11-02-agent-groups.md | `c0796fca4ca63c6b7d5b4df2fa0c86fab7cbb5cdc38d54d6388853ef399b2e05` |
| docs/tasks/TT-GROUPS-001.json | `5bb415b6b6120475f9795902ccf8e442005822d9e5022094d8d2a3acc8800e85` |

The actual tasks._read validation passed; card status is in_progress and all four stages are pending. That structural check is not specification acceptance.

## Blocking finding — P1: Define trusted base-update provenance and task diff authority

Location: design Repository integration and main changes (especially the base_update paragraph, currently lines70–78); plan Task3/Task5/Task6 integration interfaces, ownership and regressions.

The design introduces a host-only merge of fresh exact main into an existing stable task branch, then supersedes affected receipts. It does not define the new comparison authority after that merge: immutable original source/admission versus updated main/base epoch, the provenance of accepted external main content, task-only product delta for allowed_paths/host-owned evidence/card checks, or the exact reviewer diff inputs. Nor does its base_update precondition require a freshly authenticated accepted-main receipt/CI/postmerge/closure identity before importing that main; it currently binds observed remote main and pre-update head. General final-completion checks and the future actual-API audit do not define these launch-time semantics.

This is a concrete incompatibility with the very candidate seams the design proposes to extend. Current candidate product_manifest compares every changed path from immutable run.source_sha and checks each against allowed_paths; roles receive diff_base_sha=run.source_sha and whole-development-review obligations from that original source. PipelineJournal.record treats source_sha/base_sha/admission identities as immutable. When unrelated accepted main changes a path outside this task's scope, merging it into the stable task branch makes the legitimate next checkpoint fail Product change outside allowed_paths. A builder trying to make it run must otherwise overwrite original authority, exempt an undefined set of main changes or widen scope; those materially different choices can hide task mutations or invalidate old proofs incorrectly. The plan does not name/freeze the affected pipeline_inputs and role-request/checkpoint baseline integration alongside this operation. Deferring concrete SQL until #16 main is accepted is appropriate, but deferring this semantic authority choice is not sufficient for current spec acceptance.

Required correction before implementation:

1. Explicitly preserve immutable original admission/source/run/branch/workspace identity. Define an additive host-bound base-update epoch/provenance contract (or another equally concrete mechanism) carrying previous accepted base/epoch, expected pre-update task head, exact new main, authenticated accepted-main receipt/CI/postmerge/closure proof and observed resulting head. Require that proof immediately before the effect/continuation, not just eventual task completion; no arbitrary true predicate or editable JSON can stand in for it.
2. Define how accepted external main changes are distinguished from task changes without bypassing allowed_paths, protected host evidence/cards or full-ref guards. State which exact baseline(s)/manifests and history are used for scope checks, checkpoints, stage requests, model whole-diff review and final PR diff; ensure task edits cannot be laundered as external main content, including overlapping paths/conflicts. Freeze the semantic rules now and actual additive schema/protocol signatures against accepted #16 in Task3.
3. Explicitly supersede every prior source/base-input-bound stage/PR receipt and allocate fresh bound inputs/generations after successful update, without resetting deadlines/process/rework counts. A changed head/base cannot reuse an old approval because its stage was deemed unaffected; preserve all old rows/history as superseded.
4. Add named tests for accepted external main changes outside task allowed_paths without false scope failure, unauthorized task edits still failing before/after merge, overlapping/conflicting accepted-base edits, missing/revoked/stale accepted-main proof, reviewer/checkpoint baseline identity, all old receipts invalidation, and crash/unknown outcome preserving the epoch/intent without replay. Assign pipeline_inputs/role/checkpoint authority ownership in the plan where those contracts change.

This finding does not require a speculative #17 merge API or implementation code now. The already specified actual-#16-main integration gate remains mandatory; after accepted main, audit real APIs and obtain affected spec revalidation rather than importing unmerged runtime modules.

## Requirements and sound boundaries already present

- Explicit private routing/groups/six fresh role bindings satisfy actual Issue18 scope without inferring assignments. Missing/ambiguous routing parks only affected tasks; invalid global config stops its use. Same existing routed task executor_profile prevents group policy from widening executables, pins, budgets or source authority.
- Default installation2/group1, min(groups,pipeline) capacity and capacity-only epochs are explicit. Claims/reservations/components/one owner and cursor updates use one canonical pipeline SQLite authority under BEGIN IMMEDIATE. Canonical G/installation/J binding and old-claim bypass cases are assigned tests. Separate/copy-modified installations are not falsely presented as distributed fencing.
- Legacy active/unknown rows consume global capacity and preserve existing repository serialization. Positive cleanup, safe-ready handoff, unresolved effects and component ownership remain distinct; PID death/lease expiry cannot silently release unknown work. Additive migration explicitly preserves legacy values/history/backend delivery identity and refuses unsupported schemas.
- Dependency graph distinguishes native contains from explicit requires_result/aggregate_requires, verified accepted results from closed Issues, unavailable/cycles from ready, and readable cross-project references from execution authorization. Parent required children are explicit native children, with own integration acceptance; no implicit child-to-parent wait cycle is created.
- Independent Git directories for new runs retain complete ref guards; no weakened shared-ref snapshot is proposed. Legacy linked runs remain conservative. Real process/Git/SQLite/transport tests and a bounded installed-Codex pilot are assigned, with no fixture/night-readiness substitution.
- Existing #16 runtime is correctly NOT claimed in accepted main, #17 merge worker is separate, and #19/#25/#26 boundaries remain explicit. Only pure policy/DAG work may precede #16 integration after spec acceptance. Genuine verified_done and exact-main/publisher-driven automatic closure remain final gates.

No other blocking specification finding identified in the reviewed scope. Routine helper names and SQL column choices may be decided during the explicitly gated actual-main schema freeze; the base-update authority above is a required major contract, not such a routine choice.

## Review limits

No implementation tests, processes/pilot, code mutation, journal migration, GitHub status/comment, commit or push were performed. Read-only signature/source examination and tasks._read are feasibility checks, not implementation evidence. Only this requested review report was written. Keep this rejected binding/history when revising the documents; changed spec/plan/card requires fresh independent acceptance.


## R1 independent specification re-review — current verdict

2026-11-02. Fresh independent reviewer `/root/books_pr_acceptance` **ACCEPTS the revised Issue18 specification and implementation plan at the exact bindings below**. Builder check: **nothing important left within this design's explicit integration gates**. The original rejected verdict, its one P1 finding and original hashes remain preserved above; this section supersedes that rejected document binding only. No implementation, runtime concurrency, pilot, TEST/PR/main/postmerge or automatic Issue closure is accepted here.

Read both complete revised documents and the unchanged pending card, checked their requirements against the actual Issue18 body and applicable architecture, and re-examined the candidate #16 source/admission/checkpoint/full-ref/protocol seams as feasibility context. Candidate #16 remains unmerged/unaccepted main; its changing sibling HEAD is not substituted for accepted APIs. Task3 still stops until actual #16 exact-main CI, independent postmerge acceptance and automatic closure, then audits/rebases/freezes actual APIs and obtains affected independent design review if they differ. Only accepted pure policy/DAG work may precede that integration gate; no unmerged runtime imports or shadow stage engine is authorized.

### Exact current binding

Same canonical document scheme as the original review: UTF-8-sig decode, CRLF/CR to LF, UTF-8 SHA-256. Independently matched all three after the coordinator's final freeze; actual tasks._read also passed with all stages still pending.

| File | SHA-256 |
| --- | --- |
| docs/superpowers/specs/2026-11-02-agent-groups-design.md | `b3b5e7eb918622c7ca45761b9313cf266e29d12e81767af89ca3dd42465ec9bd` |
| docs/superpowers/plans/2026-11-02-agent-groups.md | `b6a1015ddeaf2c1a60689706f48d9a238d764c0f3854ca66449f82d4072d47b9` |
| docs/tasks/TT-GROUPS-001.json | `5bb415b6b6120475f9795902ccf8e442005822d9e5022094d8d2a3acc8800e85` |

The card hash binds the pending author draft reviewed here; coordinator's later mechanical acceptance update is separate. Changing design/plan semantics or any accepted source authority requires fresh affected acceptance; the old rejected source must not be treated as accepted.

### Original P1 resolved

The required base-update authority is now concrete rather than a generic future callback. Immutable original S/B/admission/profile/run/delivery/branch/workspace/criteria/scope remain untouched; additive chained host-owned base epochs carry exact current scope/diff baselines, accepted-main proof and pre/post checkpoint/product/task-delta provenance. Automatic update is explicitly private opt-in, disabled by default and capped at at most two committed intents within original budgets. Existing S!=B divergence and any T/E path overlap park conservatively without discarding content. This is a bounded local accepted-base import, not a new PR merge authority.

Accepted-main proof is required at launch and continuation, not only eventual completion: an authentic accepted anchor, every bounded first-parent step, all exact mapped task receipts/automatic closure, current required-platform CI, current main/verified remote agreement and completed repository barrier. Direct/unattributed steps, stale/revoked/unavailable proof or unknown pending integration cannot be guessed accepted. The complete proof remains freshly revalidated; a stored digest/Boolean or model result cannot authorize an operation.

Scope separation is explicit: old-baseline complete task delta T is checked against unchanged allowed_paths/protected host evidence/cards before exclusions; external accepted-main delta E must be disjoint. Host merge must equal their exact Git blob/mode union, with raw M-to-result delta equal T and no other changes. Current scope_base/diff_base=M is then journal-authoritative, not a caller-supplied source substitution or path exemption. Subsequent unauthorized edits to imported paths still fail. pipeline_inputs owns baseline/product/checkpoint logic; all post-update executors/reviewers receive the whole task diff at M, original admission and epoch history, full product/spec/criteria, with final PR independently bound to actual current head/base.

Safe-boundary cancellation/positive cleanup, old-scope output checkpointing, dedicated intent-before-fetch/merge phases, post-tree attestation, atomic epoch/input installation and proof-revocation quarantine are defined. Lost/unknown effects are inspect-only, never blindly replayed or reset. EVERY prior source/base-bound stage/check/CI/role/PR input is superseded, stage returns to spec with a fresh monotonic generation and all six fresh roles/checks; budgets/deadline/rework counts are not reset. Named regressions cover outside-scope external changes, unauthorized task changes before/after import, overlaps/conflicts, main-proof revocation, original identity, exact reviewer/checkpoint baselines and crash/unknown phases.

Strict group protocol versions are also specified instead of adding fields to closed legacy bodies: group stage/verdict/checkpoint/publication-input v2, role request/result v3 and host-check v2, all bound to current journal epoch/proof/task delta. Known legacy validation and bytes remain unchanged; unknown/wrong/legacy-for-group versions fail closed. External #17 PR receipts keep their own actual accepted protocol and exact head/base authority. Task3/Task5 ownership now includes the necessary journal, pipeline_inputs, roles, harness, worker, policy and publication seams.

### Final narrow clarifications checked

- Epoch0 proof semantics are consistent in epoch and protocol sections: previous/external/update identifiers are null; pinned-resolution epoch0 has null accepted_main_proof_sha256, while accepted_main epoch0 requires the identical immutable source_resolution.initial_main_proof_sha256 across journal/role/check/publication bindings. Fresh real proof revalidation remains mandatory. This is initial source authority, not a hidden base update or in-run source replacement.
- Accepted-main initial/queued source resolution is an explicit private per-profile/full-fingerprint/accepted-anchor grant. It derives S=B=M once into the owned clone, preserves fixed profile/source_ref and user checkout/dirty files/refs, uses the same accepted-main proof, and cannot rebind an existing run. Ungranted pinned sources honestly park stale; no hidden source widening or claim of default remote-ref support.
- In a group-bound canonical journal every public/legacy/groupless claim obeys the persisted validated global capacity epoch/debt and min(G,pipeline) maximum even when G is omitted. A caller's maximum2 cannot bypass G maximum1; that exact regression is required. Group-bound runs still cannot execute through omitted-G/legacy protocol paths. Status/cancel/inspect do not require valid executable/instruction pins.

### Remaining gates and limits

The original review's sound boundaries remain: explicit routing and same already-authorized role profiles, one local journal/owner/capacity authority, legacy unknown counting and positive cleanup, deterministic accepted-result DAG/parent/cycle semantics, independent Git directories with unchanged whole-ref guards, conservative mixed legacy mode, additive crash-safe migration and fair action/refill scheduling. Copies/other installations are not distributed fencing. #17 merge worker, #19 distributed ownership, #25 supervision and #26 recovery remain separate; no service installation, credential scope, model selection or night readiness is claimed.

No additional blocking design finding remains at this binding. Actual implementation still requires per-task reviews, real competing-process/Git/failure tests, bounded installed-Codex group pilot with truthful limitations, full/current three-platform checks, fresh whole-diff exact-head/base PR acceptance and exact-main independent postmerge plus publisher-driven automatic Issue18 closure. No implementation/pilot tests were run for this document review; read-only API/source examination and tasks._read establish feasibility/shape only. Reviewer wrote only this append-only review section, with no spec/plan/card/code/journal/API mutation, commit or push.
