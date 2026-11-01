# Independent specification and plan review — TT-PR-WORKER-001

Reviewer: fresh independent software-engineer acceptor `/root/pr_worker_spec_review`, 2026-11-02. No product edits, commits, authentication changes or external mutations were performed.

## Exact document binding

- Base: `918554a1e7f6dec10f81a366c1dececa845ff072`.
- Spec: `docs/superpowers/specs/2026-11-02-pr-worker-design.md`, raw SHA256 `564ca0cb5b166d23391b58e87528930280fe1235038e9473854765cd147a31ba`.
- Plan: `docs/superpowers/plans/2026-11-02-pr-worker.md`, raw SHA256 `482410944a137852d8a5792711ae7b944b0d1aa77727c11a10b01c0cffc0f3a3`.
- Both on-disk hashes were checked with Get-FileHash; these are frozen BOM-free LF bindings supplied for review, not legacy evidence hash substitutions.

## Phase 1: builder check

Applied the exact brainstorming/builder-check-prompt.md software-engineer workflow, reading the specification before the plan and repository-seam inspection and without consulting its author.

nothing important left

This answers only the initial design-only planning-questions check. The subsequent acceptance phase independently inspected actual integration seams and found the blocking feasibility conflict below.

## Phase 2: independent overall acceptance

**Verdict: REJECT — one important feasibility conflict must be resolved before implementation acceptance.** This is not PR acceptance, implementation acceptance, pilot readiness or Issue completion.

### P1 — the mandated unchanged postmerge driver cannot honor the bounded effect contract

The spec requires each tick to perform at most one external write or one role launch; the plan repeats that invariant in Task5 `step`. The spec simultaneously requires driving existing `postmerge_worker.Worker` with existing `GitHubPublisher`, and the plan permits modifying Worker only for task_provider/default-preserving path injection. Actual `Worker.once` can launch the postmerge reviewer and, in the same call, invoke publisher.publish. Actual `GitHubPublisher.publish` can POST the lifecycle comment and then PATCH Issue closure in that single call (github_publication.py lines 134-155). A task_provider path seam cannot split these actions. max_reviews=1 limits reviews, not effects, and publisher=None prevents automatic closure rather than satisfying the cycle.

The plan must explicitly select a compatible bounded bridge: either authorize a narrow additive resumable effect boundary around the existing postmerge/publisher workflow, preserving default callers and genuine receipt/verified_done semantics, with durable individual intents and lost-response tests; or explicitly revise the tick invariant to a bounded inherited postmerge transaction and describe its multi-effect uncertainty/recovery contract. Do not let the builder silently choose between these materially different contracts. Cover a postmerge review plus publication and comment-success/closure-unknown crash scenario, and verify one permitted action per step if retaining the current invariant.

## Requirements, authority and focus assessment

All other examined areas are sufficiently concrete for planning, subject to the stated integration and external setup gates:

- Persistent explicit private policy, whole actual local Git diff, exact head/base/task marker receipts, independent fresh processes and public head-bound status are covered. Unknown CI, current failure, forged same-name success, incomplete pagination, stale authority and blocking findings fail closed.
- Exact-base guarantee is honestly conditional on actual operator-authorized exclusive writers AND verified non-bypassed server protection. Current chat authorization does not establish global exclusivity. Missing setup correctly blocks the real pilot without blocking complete implementation; no invented readiness or new protection/scope grant is authorized.
- The async request fixes direct_merge/merge/bypass_rules=false and head-only sha, excludes queues/stacked scope, and fences lost UUID/409/expired results. Official GitHub documentation checked during review confirms head-only binding, pending/merged/enqueued/failed distinctions and expiry 24 hours after most recent update: [GitHub REST pull requests](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request-asynchronously). Expiry is not proof of no merge.
- Serialized repository barrier extends through exact main, authoritative latest platform bundle, independent postmerge, publisher receipt and genuine verified_done plus completed Issue closure. No closed-only or Boolean verifier bypass is planned.
- PR37-style immutable original event identity is preserved; the private recovery_of provenance and same-Issue follow-up with fresh event is a concrete recovery mechanism. Neither live-body edits nor old-event reruns are treated as refreshed provenance.
- Trusted pipeline host history is the authority; public MD/model metadata is not. The sibling Task16 actual pipeline_journal.history, receipt/process validation and pipeline_publish.project_evidence/validate_publication_current/_pr_observation provide concrete seams for chain, final product and publication checks. Its aggregate committed MD projection can support the private legacy card, provided the host reproduces it byte-for-byte and computes legacy v1 digests separately. No automatic import guess is needed: Task3 explicitly waits for accepted integration and requires contract adaptation/review.
- The proposed provider is feasible for both Worker card lookups (review and publication) and must never fall back after an invalid provider. A private Git-root mirror preserves project_root=../.. and existing tasks._check_evidence requirements without overwriting a tracked card. tasks.py v1 LF normalization and supported scheme enumeration were inspected; pipeline v2 hashes must remain distinct.

## Six-task interface and evidence audit

1. Policy/journal: strict identities, aliases, fixed transitions, durable deadline/counters, owner CAS and full completion proof are specified. Genuine writer attestation is an external prerequisite, not a routine missing design choice.
2. Source/review: complete Git objects, bounded pagination, trusted CI attempts/app identities, strict result envelope, token stripping, cleanup and immutable request binding are specified. Uncertain effective rule API details require primary-source fixtures during implementation.
3. Authority/card: actual sibling journal and final evidence projection support the stated adapter; integrated schema acceptance remains a deliberate dependency gate. Default provider behavior and invalid-provider failure need concrete tests.
4. Effects: durable publication and sole async merge intents plus positive exact-parent/main reconciliation are adequately specified; no automatic replay on ambiguity.
5. Controller/recovery: identity, barrier proof, fixed public output and inspect-only recovery are specified, but the postmerge action granularity conflict above blocks acceptance.
6. Pilot: real installed watch, real independent profiles, real provenance and no chat integration actions are necessary. Missing exclusive-writer/protection setup must leave Issue17 unfulfilled. A fixture subprocess does not replace this gate.

Read-only checks included repository AGENTS, development-process policy, architecture spec, Issue17 cached body, full frozen spec/plan, existing Worker/ReviewRunner/tasks/postmerge-journal/GitHubPublisher/project_worker interfaces, sibling Task16 spec/journal/publication source, Git status and raw document hashes. No implementation tests were run because this is design/plan acceptance and no product implementation was changed. A nonexistent guessed sibling spec filename was corrected to the actual 2026-11-01-stage-pipeline-design.md before inspection.
## R1 independent re-review — 2026-11-02

**Verdict: ACCEPT specification and implementation plan for the exact R1 bindings below.** The original rejection above is retained as historical evidence and does not apply to these revised bytes.

- Spec `docs/superpowers/specs/2026-11-02-pr-worker-design.md`: raw SHA256 `a987e1df4cf20c2e6531f80f0f6852325c250638b427d86bcd97c7c347b32efa`.
- Plan `docs/superpowers/plans/2026-11-02-pr-worker.md`: raw SHA256 `2ae227f87bd58f9f72c2d0ab2f7ead75ec8add18296e6724151f4b9b76c2fb9f`.
- Source base remains `918554a1e7f6dec10f81a366c1dececa845ff072`; same fresh independent acceptor `/root/pr_worker_spec_review`. Get-FileHash confirms both frozen raw bindings.

Builder-question recheck: **nothing important left**. No remaining material design decision must be guessed before planning.

The original P1 is resolved explicitly rather than hidden by loosening the action bound. Worker.review_one has one selected task/bundle, at most one launch, no publication and a PRJournal prelaunch intent. GitHubPublisher.publish_step owns the opt-in publication through PRJournal and performs comment POST and closure PATCH on separate ticks. Full v1 receipt preparation and exact barrier binding precede effects; each request has its own durable intent, and each acknowledgment ends that call. Closure requires fresh receipt/source/local/lifecycle proof; publication completion requires a subsequent read-only genuine verified_done proof. Lost acknowledgments, before-send committed intents, owner loss and ambiguous observations stay fenced without replay or barrier release.

Re-inspected actual Worker.once review/claim/save_review/_apply flow and GitHubPublisher receipt/_remote/_verify_current_source/publish flow. Their existing validators and local apply helpers can be reused by the explicitly authorized additive APIs without invoking batching methods or changing v1 lifecycle/publication identities. The new plan includes the necessary github_publication.py ownership, PRJournal publication methods and substates, exact publish_step return schema, Task5 completion publication argument, per-action crash/lost-response tests and whole-cycle actual launch/write counting. Existing default once/publish behavior is preserved by explicit regression requirements. No unsupported existing resumable seam is assumed.

Rechecked the current documents across all six tasks and five review-focus faults. Task1/2 may proceed; Task3 must still wait for accepted Task16 integration and validate its actual current publication/process/receipt schema. No public MD or model identity becomes authority, no legacy hash reinterpretation or invalid-provider fallback is permitted, and no external setting is automatically changed. The honest exclusive-writer plus server-protection condition, async head-only boundary, UUID fencing, immutable original-event recovery and exact-main/independent-postmerge/automatic-closure barrier remain intact.

This acceptance authorizes implementation against these exact documents under the existing backlog policy. It does not establish implementation correctness, accepted integration of Task16, a globally exclusive writer, available protection access, successful pilot, PR acceptance, main acceptance or Issue17 completion. The real pilot still requires concrete operator authorization over all writers and verified enforced server protection; missing prerequisites must be reported as actual blockers after preparing the reviewable setup. No new product edits, tests, commits, pushes or external mutations occurred in this re-review.