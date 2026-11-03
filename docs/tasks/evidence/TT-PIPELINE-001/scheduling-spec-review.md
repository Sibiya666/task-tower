# Independent scheduling contract adjudication

Date: 2026-11-02. Reviewer: independent `/root/pipeline_scheduling_spec_review`, distinct from implementation and PR acceptance. Scope: Issue #16 priority contract only; no product implementation or TEST acceptance.

## Verdict

**REJECT the claim that the current journal ordering already satisfies the unchanged accepted priority sentence. Implement priority ordering among queued runs while retaining ready-first continuation precedence.** Admission priority alone does not satisfy the accepted requirement. This is a bounded routine bug fix; no new user authorization is required.

The additive transient-order design below is **accepted in this narrow specification scope as a feasible implementation contract**, conditional on actual validation and tests. No priority waiver or original-spec amendment is recommended. This receipt does not accept unimplemented code. The finding remains blocking for whole-PR acceptance until the conforming implementation is independently reviewed.

## Exact reviewed bindings

Committed source: `a569285d1966e53a5abe52a8b7f368d43321cc75`; stated integration base `56f8ab1`. Git blob identities below bind the complete committed contents; concurrent working-tree edits to pipeline.py and other files are excluded.

| Path | Git blob |
| --- | --- |
| docs/superpowers/specs/2026-11-01-stage-pipeline-design.md | d49a1999052e4e19f9cac93a10c4a3175a7e13ac |
| docs/superpowers/plans/2026-11-01-stage-pipeline.md | ebaa2229d650184e7bb075e24c45d07da42925d0 |
| docs/tasks/evidence/TT-PIPELINE-001/task6-spec-review.md | 4cfa3dfe99e80db5aaf780bb04a9c474c1b9fa41 |
| task_tower/dispatch_selection.py | b4fac37462d60aba6c834c31e1ea6d5861fabfe6 |
| task_tower/dispatcher.py | 61bdb196f90cefcf88cddc94887800b151b2532e |
| task_tower/pipeline.py | c2e34e4b164e1c42fbc4e9a9ebe54087eedb186e |
| task_tower/pipeline_policy.py | 66551f6cddd0315939bb05a7c0d841d5c188e10a |
| task_tower/pipeline_worker.py | b30cb41d10b49bba86865ce7054d0aa675df4483 |
| task_tower/pipeline_journal.py | 452c6ad341dd5a248270e6d33961cf5c55bf7bb3 |

## Contract and code analysis

1. Spec lines 21 and 62 require existing select_ready for initial admission/start. dispatch_selection.select_ready (lines 130-194) validates P0-P3, defaults absent priority to P3, and sorts by numeric priority, repository and Issue. dispatcher.tick (lines 45-121) walks that sorted ready list, can submit up to eight identities per tick, and revalidates eligibility before each delivery. This establishes priority in remote candidate submission order.
2. pipeline.adapter (lines 34-51) accepts the existing six-field request, verifies the private mapping/authority and submits profile/policy/component/limit bindings. It does not persist priority. PipelineJournal.submit (lines 270-290) creates queued runs without priority. Admission is a durable delivery acknowledgment, not an execution-order reservation.
3. PipelineJournal.claim (lines 322-353) first considers safe ready continuations in repository/Issue order, then, if capacity remains, queued runs in repository/Issue order. It checks repository and component exclusions atomically. Neither saved delivery order nor priority is used. pipeline_policy.admission_authorized (lines 134-149), called by pipeline_worker._prepare (lines 161 onward), checks select_ready against a singleton task row. That establishes eligibility; it cannot compare a lower-priority claim with other queued tasks.
4. Consequently, an admitted batch containing `z/repo#20 P0` and `a/repo#10 P3` may execute the P3 run first when one slot is available. The dispatcher can submit both before a worker claims either. In one repository, a lower Issue number with P3 can similarly precede a higher Issue number with P0. No race assumption or priority mutation is needed. Reordering admitted queued tasks is therefore distinct from the explicitly allowed continuation precedence.
5. Spec line 104 places 'select deterministically by existing priority/repository/Issue order' directly in the durable atomic-claims/capacity paragraph, without limiting it to remote admission. The natural reading covers journal candidates. The spec's earlier ready-first paragraph and plan line 24 permit finishing an existing same-repository run without fair stage interleaving. They override strict preemption by new work, but do not remove priority among multiple queued runs. The prior Task 6 R2 acceptance expressly discusses ready-first/no fairness and same-repository serialization; it does not expressly adjudicate removal of queued priority. Its acceptance cannot be stretched to decide that omitted question.

## Recommended minimal conforming fix

pipeline_worker.step currently calls journal.claim after looking for an existing run owned by the same worker. The fixed host `_action` already executes step inside the contained host process, so fresh source reads for ordering belong there, before the journal write transaction, rather than in watch's controller thread or a model role. Reuse collect_snapshot and select_ready with genuine verified_done across the configured task allowlist. Build a transient canonical map/list of repository-qualified Issue identities and validated P0-P3 values from that actual host selection. Pass this to an additive optional claim keyword (for example queued_order); do not persist it. Exact helper naming is routine implementation detail.

The claim contract must be explicit:

- Preserve existing safe-ready continuation precedence and repository/Issue order within ready continuations. A continuation is not required to reenter select_ready's open-initial-lifecycle gate.
- For new queued claims, validate the supplied container, exact allowed keys/types, canonical repository identity, positive non-Boolean Issue numbers, unique identities and P0-P3 priorities. Sort eligible matched queued rows by numeric priority, repository, Issue inside the existing BEGIN IMMEDIATE transaction; retain all current capacity/CAS/repository/component checks and conflict skipping.
- Treat this data only as an ordering/eligible-candidate hint from the trusted host. It cannot authorize a role/effect, replace the private mapping, fabricate immutable admission evidence, or weaken _prepare/admission_authorized and subsequent fresh continuation checks.
- Prevent a concurrent newly submitted queued row absent from the snapshot from falling through to repository-only claim order. It must wait for a fresh pass. Unknown/unavailable/invalid source data must not receive an invented default priority. P3 default applies only to genuinely absent priority in otherwise valid metadata, exactly as select_ready defines.
- Missing optional ordering input may remain compatible with existing internal direct journal tests/callers, but every production queued-claim entry path, including public work --once and watch _action, must supply the genuine selection. Do not let a fallback silently retain the bug in production.
- Source unavailability must produce a bounded visible operational/source-unavailable result or appropriately fenced needs_input outcome; an empty hint silently reported as successful idle is insufficient. Distinguish genuine no-ready work from unavailable/invalid source. Avoid parking or releasing unknown ownership without existing proof. A failed unrelated source must not prevent a positively authorized safe continuation or unrelated genuinely verified work; report the partial failure explicitly and exclude unverified candidates.
- The map is one fresh scheduling snapshot, not an atomic remote lock or forever-valid priority. A priority change after collection may affect the next selection pass; _prepare still independently revalidates authority immediately before effects. No network access should occur while holding the journal transaction.

No schema, on-disk run row, manifest, limits, effect body, wire protocol or pilot mutation is needed. In particular, do not hide priority in a budget/effect field or claim such storage is compatible. Existing installed journal contents remain untouched. This is compatible with the Task 2 public claim signature through an additive optional keyword, which needs a focused plan/API note and review rather than altering admission authority.

Required focused regressions: dispatcher retains P0-before-P3; admitted queued P0 higher Issue beats P3 lower Issue; cross-repository priority precedes lexicographic repository; equal priorities break by repository/Issue; safe ready continuation remains first; conflicting high-priority work skips to eligible lower priority; new queued row absent from hint waits; source unavailable is visible and cannot claim unverified work; forged/malformed/duplicate/Boolean hint identities reject without state mutation; hint alone cannot bypass fresh preparation authority; old journal bytes/schema and six-field adapter remain compatible. Tests must use genuine selection/dependency fixtures, not forced-true authorization.

## Nonrecommended alternative considered

A deliberate policy amendment could instead remove queued priority, but the coordinator has selected honoring the existing contract. The following bounded text records the alternative considered; it is **not accepted as the current governing contract or recommended for implementation**:

Replace only the scheduling sentence in spec line 104:

> A clean external blocker does not prevent unrelated ready work. Remote dispatcher candidate submission uses existing select_ready priority/repository/Issue order. Local journal claims first select eligible safe ready continuations, then eligible queued runs, with repository/Issue order within each class, skipping conflicting/parked runs. The six-field adapter receipt does not reserve execution order; priority is not persisted or reapplied by the local journal. This MVP provides neither priority preemption nor fairness among admitted runs; richer scheduling belongs to #18.

Append to the existing plan Global Constraints ready-first bullet:

> Dispatcher submission preserves select_ready priority/repository/Issue ordering; local claims use ready-before-queued and repository/Issue ordering within each class, without persisted priority or an execution-order promise from admission. Add a focused regression proving an admitted mixed-priority batch follows this explicit local order while dispatcher selection still preserves priority.

This choice preserves genuine readiness/dependency verification, capacity, repository/component exclusion, unknown fencing and all stage/publication gates. It makes the existing difference visible rather than claiming priority scheduling that the journal cannot provide. It avoids altering legacy private journals, adding a priority field to the wire protocol or performing a forbidden schema migration. It is technically coherent for bounded #16 because its stated objective is durable independent stages and automatic refill, not general priority scheduling; #18 remains responsible for richer scheduling. The price is explicit: low-priority admitted work can start before high-priority admitted work, and ongoing continuations may delay queued work. This is an actual scoped design decision and must be recorded as such, not described as a typo or proof that unchanged requirements were met.

If the coordinator elects to preserve the existing line 104 requirement instead, the implementation must introduce an authoritative, compatibility-safe way to compare queued priorities, specify snapshot/update semantics, and independently review/test that contract. Do not reset, delete or schema-mutate installed journals/pilots to make that alternative pass.

## Limits and required follow-through

No product tests were run for this document-only adjudication. The reasoning uses direct code/control-flow inspection and the two-candidate counterexample, not a claimed passing runtime probe. A Python hashing attempt could not launch the WindowsApps python alias; exact bindings use independently queried Git blob IDs instead. No code, original spec/plan, task card, legacy journal or pilot was edited; no commit/push/external write was performed.

The current reported macOS failed-zero-role/policy_revoked incident is outside this review; its exact cause is unproven here. Typed-sidecar WIP is excluded. This receipt does not grant current TEST, CI, PR, main/postmerge or night-readiness acceptance. After the conforming fix, bind fresh relevant acceptance to the actual document/source inputs and verify the focused ordering regressions alongside current required suites/CI. Whole-PR exact-head/base and serialized merge/main gates remain mandatory.
