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


## R2 independent full specification and plan review — rejected binding

2026-11-02. Reviewer `/root/groups_policy_acceptance`, distinct from the author and future implementer. **REJECTED pending the representation conflict below.** This verdict supersedes neither the historical R1 acceptance nor Task1/Task2 implementation bindings; it declines the new R2 document binding only. The user's explicit removal of the fixed two-Issue ceiling takes precedence over older AGENTS capacity wording. That user decision is accepted scope, not the reason for rejection.

### Exact reviewed sources

Read the entire revised specification, implementation plan and private proposal in passes, the pending task card, repository AGENTS and applicable independent-review/verification instructions. Re-examined the actual provisional Issue16 noncreating recovery seams statically; neither that branch nor the D5 release is substituted for accepted final main/closure. No runtime import, native sampler, DDL, SQLite connection, model invocation, migration or implementation test was executed.

All three new author documents have identical raw and canonical SHA-256 (UTF-8-sig decode, CRLF/CR to LF, UTF-8 encode for canonical):

| Source | SHA-256 |
| --- | --- |
| docs/superpowers/specs/2026-11-02-agent-groups-design.md | `e33167f0eefc5eb273e559bfbb249095021760118898744d3e4b4102572396e8` |
| docs/superpowers/plans/2026-11-02-agent-groups.md | `22b17de1a7cd8f59171ca46efa33f2cf1f9457e5b3b88fa926e46f20f6c553ad` |
| private runtime/groups18-capacity-r2-proposal.md | `418c051e4b801dbbbaeca107e12cc4352d78e1108c09da52d5f21264811ca34b` |

The whole pre-append report was preserved byte-for-byte: raw `0e945a2671b354a3bd02f9b9ccdfcd3a694509605dab95f27c02ec59150c1348`, canonical `04aab5223e336739279dd4ab47d7c17e9e1c7e936e8ad123c672399f25fa6d2a`. Its earlier rejection and R1 acceptance remain intact. Task card is in_progress with SPEC/development/test/postmerge pending. Current delivery48c93982-4c79-468c-a3eb-e4f6d05db14d remains at its original owner/backend; no import/re-admission is approved.

### P1 — pre-registration legacy resource fences have no valid representation

Anchors: specification lines250–275 (resource observations/leases), lines314–335 (actions require nonnull capacity_epoch), lines426–428 (installation absent before registration and active/unknown migration slot held), line445 (migration creates no group actions/installation), line452 (slot_held equals held leases; synthetic migration legacy_fence). Equivalent private proposal lines102–126,160–178,278–280,297,304. Plan Task3A requires migration_unknown_estimate_fences and full v2 invariant validation.

A recognized v1 journal can contain a positively dead owner's unknown run with unresolved launch/cleanup. The contract explicitly permits migrating it without inventing cleanup. Migration must mark its slot+components held, and R2 says slot_held is exactly existence of a held resource lease. But a lease's action_id references group_actions; group_actions.capacity_epoch is NOT NULL and references group_capacity_epochs; every capacity epoch requires a group_installation row. Registration has not happened yet, group_installation must contain zero rows, and migration explicitly forbids group actions. Therefore no valid row set satisfies all the proposed SQL and typed invariants for this required input. Synthetic legacy_fence does not resolve it: it still lacks the required epoch/installation and contradicts the action prohibition. Deferred FKs only postpone checks until commit; they cannot create the missing authority.

This forces a builder to reject a promised lossless migration, weaken validation, invent G/policy authority or fabricate a release. It is a required representation/compatibility decision, not a routine helper choice to defer until implementation.

Required correction: explicitly define the pre-registration conservative legacy-fence representation (for example a typed migration-only holding with no resource-authorizing epoch, or defer resource materialization until G adoption while stating a precise pre-registration exception and retaining the old conservative fence). Reconcile DDL nullability/closed row dispatch, slot_held equality, migration action rules and the atomic registration conversion. Specify how absent/unknown estimates, original owners/PIDs and original history digests survive, how no claims bypass that fence, and how registration installs real estimates or preserves unknown_estimate blocking without asserting cleanup. Add named tests for unknown/dead legacy migration before G, v2 reopen/status/cancel, failed registration rollback and first G adoption with unchanged original rows/sequences. Do not solve it by creating a guessed installation/policy epoch, dropping unknowns or treating missing estimates as zero.

### P2 — remove the remaining fixed-two acceptance obligation from new R2 evidence

Specification line173 still requires competing processes to prove at most2 installation reservations in its live Acceptance evidence list, adjacent to >=3 real work/pilot obligations. R2's final audit says historical foundation count statements are old-only, but this is an acceptance requirement, not an old-runtime description. The plan also retains the old test_full_capacity_still_allows_reserved_continuation name despite R2 explicitly forbidding product-reservation resource bypass; its intended existing-active-action semantics should be stated if retained. Rewrite the acceptance item as v1 compatibility-cap evidence plus separate >=3 feasible R2 resource claims, and explicitly distinguish already-held live action continuation from a cleaned product-owner reacquisition. Keep the old requirement in historical reviews rather than an ambiguous current acceptance list. This is a document consistency correction; the user decision itself needs no reconfirmation.

### Sound R2 boundaries

- V2 auto/null capacity and positive optional caps replace a product-wide constant; exact closed v1 loaders/default caps remain compatibility semantics and deliberate v2 private opt-in is required. CPU/memory feasibility, explicit harness pool grants and optional count caps are minima; aliases cannot create extra account capacity. Provider/model/tool/credential quota or spend authority is not inferred.
- Fresh host resource samples have a two-second collection budget, five-second maximum age, boot/process/monotonic/policy provenance and same-transaction revalidation. Typed unknown/fallback paths do not silently mean unlimited capacity; explicit fallback only substitutes missing resource dimensions and adds its count cap. Conservative headroom plus checked held-envelope arithmetic supports zero capacity. Estimates are explicitly not OS reservations, child resource enforcement or a credential sandbox.
- Active action leases are separate from in-flight product/component ownership. Positive cleanup plus closed effects releases execution resources during clean CI/review/main waits while component/main barriers persist. Unknown launch/effect/cleanup retains fences; no PID-only release, lease stealing, deadline reset or replay is introduced. Fresh actions reacquire resources and debt blocks additions rather than killing owners.
- Same-J atomic claims/epochs/resource samples/owners and persisted omitted-G gates, stable backend argv/cwd/fingerprints, no existing delivery transfer, lossless backup/row/sequence preservation and noncreating existing-file recovery remain explicit. Seventeen new tables/two indexes are proposed, not executed. SQL rows/hashes/samples never replace host proof or acceptance.
- Native hierarchy/qualified dependency receipts and partial-source diagnostics remain unchanged. Immutable original S/B/source/profile/criteria, private initial-source/base-update grants, fresh accepted-main proof, disjoint raw deltas/exact tree union, full-ref guard, strict legacy/group wire dispatch and all-old-input invalidation remain required.
- Pilot evidence now requires >=3 actual independent installed tasks when authorized capacity exists, six fresh roles/three independent approvals each, actual overlap/cleanup and bounded actions. Insufficient installed resources/policy leaves pilot acceptance pending; fixtures cannot substitute, and no budget/provider grant is inferred.

### Declined to judge and remaining gates

- Platform sampler correctness and hard runtime deadline enforcement: no native probes executed; named Windows/Linux/macOS capability/unknown/timeout tests and actual supported-host evidence remain implementation/TEST gates.
- Real multi-process resource accounting, helper sizing, fairness, cleanup/debt races, crash backup/migration behavior and exact protocol implementation: design obligations only, requiring future actual diff and tests. No running scheduler behavior is accepted here.
- Issue16's current provisional recovery edits, CI, postmerge and automatic closure: external integration gate remains pending. After it passes, rebase/audit actual accepted main, freeze final APIs/schema and obtain affected acceptance before integration. D5 hashes or candidate test counts do not satisfy it.
- #17 PR merge worker, #19 distributed fencing and #25/#26 supervision/recovery remain separate; no service installation, source-grant widening, main merge or Issue closure is authorized by this review.

No additional major finding identified in the reviewed scope. Resolve both anchored items and freeze revised documents for fresh independent full R2 acceptance. Reviewer appended only this report; no spec/plan/card/product code, original review history, private proposal, DB/config, commit, push or GitHub state was changed.


---

# Issue18 capacity R3 — independent specification review

Reviewer: `/root/groups_capacity_r3_acceptance`, 2026-11-02, distinct from document author and implementers.

**Verdict: ACCEPT the specification/plan at the exact bindings below.** No blocking specification finding remains. This is document acceptance only: no implementation, migration, sampler, native pilot, test, PR/main or Issue completion is accepted.

| Reviewed document | Raw SHA-256 |
| --- | --- |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | `2b98f00a034878d649315972d77d1316b031a32956df6abcfc37854ded61f2b7` |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | `138523c0115a618027168a48817af888d72ab46bb654e96db3aa5deb5ca88817` |

Reviewed the revised contract, SQL proposal and implementation sequence, prior R2 rejection and historical acceptance, private proposal, and repository AGENTS. The user's explicit removal of a fixed two-Issue maximum supersedes older AGENTS wording. No product maximum is inferred from the chat's four tool slots.

## Previously rejected items

R2 P1 is resolved. The DDL now distinguishes execution actions from immutable provenance-only legacy_fence actions. The latter have NULL executable owner/PID/input/epoch and no completion receipt. Their pre-registration held unknown-estimate lease has NULL epoch/observation/numeric envelope and a real run/action binding. This admits the required dead-owner unknown migration without creating an installation, borrowing an owner or pretending cleanup. The seventeen-table/three-index catalog and typed invariants agree with this representation. Deferred keys are used only for real atomic initialization, not as a substitute for absent authority.

R3 explicitly carries original owner/PID/run/history digests in immutable neutral provenance, conservatively fences new pre-registration claims, allows inspection/cancel independently of G, and specifies positive original cleanup as the only release path. First G adoption reconciles current original history and inserts the actual installation/epoch plus known approved estimates or preserved unknowns in one transaction. Failed adoption leaves unregistered v2 intact. Adoption does not convert the historical fence into execution authority or advance fair cursors. Released historical fences remain inspectable; lease-aware per-run exclusion prevents a held fence coexisting with a new action. The plan names migration, reopen, claims, adoption failure/crash/idempotence and genuine cleanup cases.

R2 P2 is resolved. Current evidence separates exact v1 compatibility caps from resource-feasible v2 claims, including three or more actual simultaneous tasks when authorized resources permit. Already-held live actions finishing are explicitly distinguished from clean product owners reacquiring resources. The new path has no fixed-two ceiling. The independently bounded two-intent base-update budget remains unrelated to execution parallelism.

## Retained boundaries checked

- Exact closed v1 schemas/default caps and committed delivery/backend identities remain unchanged. Explicit private v2 opt-in does not silently widen existing policy or move Issue18's admitted delivery.
- CPU/memory headroom, checked envelope arithmetic, fresh same-process/boot/policy/monotonic samples and optional explicit pool/count caps form one same-J atomic feasibility decision. Unsupported observations block or use explicitly installed labeled fallback; zero capacity is valid. These estimates are not OS enforcement or provider/spend authority.
- Resource leases are distinct from product/component ownership. Clean CI/review waits can yield execution capacity while preserving conflicts and the serialized main barrier. Unknown launch/effect/cleanup remains fenced; no timeout stealing, PID-only release or replay is allowed.
- Registered same-J discovery applies to omitted-G and legacy claim paths. Unavailable/revoked policy does not disable status/cancel. One writer transaction covers samples, capacities, owners and resources; no distributed lock is claimed.
- Source/profile/criteria/admission baselines remain immutable. Authenticated accepted-main proofs, bounded disjoint imports, full task-delta/full-ref checks, strict wire versions and all-old-acceptance invalidation remain intact. Parent hierarchy is distinct from accepted-result dependency authority.
- Migration is explicit, stopped/no-live-owner, recognized-schema only, noncreating and lossless, with no-clobber backup, one shared deadline and rollback boundary. Original rows/sequences/history remain unchanged. The SQL catalog is a proposed implementation contract, not executed evidence.

## Mandatory remaining gates

Issue16 exact accepted main, successful main CI, independent postmerge acceptance and automatic Issue closure remain a hard prerequisite for Task3/runtime integration. Re-audit the actual final APIs/schema and recovery semantics, including pending descriptor/process fixes, update the contract map and obtain affected acceptance before integration. A provisional candidate or its tests do not satisfy this gate.

Pure Task1R policy rework may proceed under its stated independent-review/TDD boundaries. Runtime behavior still requires real migration/FK/crash tests, native resource observations or visible unavailable results on all three platforms, competing-process three-or-more feasibility tests, genuine cleanup and bounded installed pilot evidence. No DDL, SQLite connection, native sampler/model/pilot or implementation suite was executed in this document review. No card, source document, historical review, config, GitHub state, commit or push was changed; only this private report was created.


---

# Independent Windows release scope SPEC/PLAN review

Date: 2026-11-02. Reviewer: windows_scope_spec_acceptance (fresh instance, distinct from amendment author). Scope: the six-file Windows release amendment only; this does not re-approve unrelated historical specification content or implementation. No tests, native/model execution, installations, authentication changes, product/card/documentation writes or GitHub mutations were performed.

## Verdict

Issue #16: ACCEPT amendment for the exact two hashes below. Windows-only native pipeline execution, early work/watch/_action/_dispatch rejection before _runtime/journal initialization, direct-entry defense, portable admission/lookup/status/cancel/inspect and mandatory Windows containment/shutdown/physical-DB identity/recovery gates are coherent. No permission to ship saved POSIX scope/bootstrap WIP is given.

Issue #18: ACCEPT amendment for the exact two hashes below. Pure group policy/DAG/provenance remains portable; Windows resource admission and conditional real >=3 concurrency proof remain mandatory. Neither fallback resources nor pure Task1R acceptance enables unsupported native execution. The actual accepted #16 main/API/CI/postmerge/automatic-closure gate remains intact; this verdict does not open runtime integration now.

Issue #21: ACCEPT amendment for the exact two hashes below. Windows native OpenCode/custom qualification and new stdin/containment are separated from portable policy/parser/provenance/closed dispatch. Existing Codex/custom behavior is explicitly preserved. Exact accepted #16 main API re-audit remains required before Task1; this verdict does not authorize coding before that gate or native probes without installation-owned qualification.

No blocking amendment findings. The explicit dated precedence at line 5 in each file governs retained earlier native POSIX promises. Three-platform CI requirements remain requirements, not contradictions: they cover portable regressions and Windows native proof with explicit per-test classification. Historical POSIX-native Task3B and transport requirements are deferred by that precedence; they cannot be claimed accepted merely by running synthetic fixtures.

## Review evidence and implementation constraints

Compared every actual amendment against its preserved pre-amendment bytes with git diff --no-index. Independently recomputed all six current SHA256 hashes and all six prior SHA256 hashes; every value matches runtime/windows-scope-spec-manifest.json. Read repository instructions and inspected surrounding platform, native-evidence, dependency, legacy-interface and completion clauses. Diff contains the new normative sections, portability wording changes and explicit #61 collector deferral, not rewritten historical reviews.

The amendment is honest about saved commit 18e9a3985ad3b86a02d58703ef8e8a2afdd9a0e2: unaccepted WIP/manual diagnostics, no runtime authority. Feature #58 and children #59-62 are named deferred work. Their live GitHub milestone/admission state and remote-branch contents were supplied by coordinator and were not independently queried in this local content review; operational verification remains coordinator responsibility.

Required implementation review checks (already implied by the accepted text, not additional scope):

- Record per-test classification before changing mixed modules. Keep all applicable portable regressions in Ubuntu/macOS/Windows CI and Windows-native tests on Windows. Retained native POSIX checklist entries in #18 Task3B and #21 Task2 must be marked deferred to #61/#62 in execution evidence, never silently marked PASS or used to delete an entire mixed module.
- Prove unsupported-platform rejection at public and direct effect-producing paths, before helpers, checks, worktrees or publication. For #16 specifically prove no _runtime/journal side effect. Do not simulate a supported native OS as platform qualification.
- Keep resource fallback subordinate to platform capability; verify Windows physical SQLite pin and ordinary/hot recovery fixes independently. Windows-only scope does not excuse known Windows defects or shared shutdown-budget failures.
- Interpret #21 direct adapter/probe restriction as the new native OpenCode execution surface; preserve the established queue/protocol and existing Codex/custom surfaces. New stdin_spec native transport is Windows-only until #62 qualification; default None/DEVNULL legacy calls remain unchanged.
- Retain head/base-bound independent PR acceptance, successful current CI, serialized merge barrier and exact-main independent postmerge/automatic verified closure. This review is SPEC/PLAN scope acceptance only, not any of those later stage verdicts or a night-readiness claim.

## Exact reviewed raw SHA256

| File | SHA256 |
| --- | --- |
| task-tower-github/docs/superpowers/specs/2026-11-01-stage-pipeline-design.md | `5524d16570530662e25006e91e4159afecbecd103f327d1c1b9b48fc3d3fc6f5` |
| task-tower-github/docs/superpowers/plans/2026-11-01-stage-pipeline.md | `d48b782e476349103455996bebb9144149326842c59b7ff1959a8390c1a05ee3` |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | `c488845f3fcd2cf446f820452c7c2dd1b22d2cae6fbd257bb3813e7b8aeae867` |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | `cf8e7a6946c5a1c5fcf0869ed9b9a7f211212c62fd63d0422782638d7a28530a` |
| task-tower-opencode/docs/superpowers/specs/2026-11-02-opencode-adapter-design.md | `aafe165c23182656f85fe272b8fa2ee0fd03a73627fb7e515bf6fa18cf93c03b` |
| task-tower-opencode/docs/superpowers/plans/2026-11-02-opencode-adapter.md | `31369e1af8988d13fe97a20eeac5ef03723ae210d340a0b01b9521c94994a813` |
