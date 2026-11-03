# Issue17 Task4/5 independent binding specification review

Verdict: APPROVE for the affected Task4/5 specification and plan amendment, not implementation or whole Issue17 acceptance.

Reviewer: fresh independent review instance /root/pr17_task4_binding_review, 2026-11-03. I did not author the proposal, specification amendment, plan amendment or Task4 product code.

## Exact reviewed identity

Source HEAD: 090872095f4c49fd71270d4822da37fddf43d7b4 (verified with process-local safe.directory; no Git configuration mutation).

- docs/superpowers/specs/2026-11-02-pr-worker-design.md SHA256 9e533197315d7bad799bd3ccca0af6d972585dd872dc6cc632f8ca36c7726c16
- docs/superpowers/plans/2026-11-02-pr-worker.md SHA256 12b2c780654ea557b5fca3e465956bd25395d1c165d73d324ad6e7cd59701297
- docs/tasks/evidence/TT-PR-WORKER-001/task4-binding-proposal.md SHA256 fe0f3207e2d1c13ac073d6209f856458b3ed14278de4a25d4fab921d41d978a0

All three raw file digests were recomputed and match the requested freeze. Read root and checkout AGENTS, full spec/plan, handoff/diff/proposal, coordinator primary API preflight and applicable Superpowers review instructions. Inspected actual pr_policy, pipeline._runtime, PRSource snapshot/prepare_review/read transport, PRReviewRunner/validate_pr_review, StageAuthorityContext/read_pipeline_authority/validate_pipeline_publication/load_stage_authority and PRJournal payload/observation/state/effect guards.

## Findings and source coherence

No blocking affected-spec finding.

The explicit execution-only pipeline locator supplies the genuinely missing input to pipeline._runtime; it does not extend closed v1 JSON or infer historical authority. Metadata inspection remains separate from execution context/pins. Mandatory typed context and current() require actual loaders, source identity/bytes, current criteria/full profile pins, genuine read-only source transaction and exact immutable Git objects before effects. The retained actual request/envelope bridge closes the gap left by receipt scalars, while distinguishing full-request SHA from Task1 input SHA. The normative spec/plan additionally require private-input provenance manifests and the fixed authority_error-only negative path; those more specific contracts govern implementation over the earlier audit proposal's shorthand result fields.

Actual PRJournal.begin_effect supports pending only in validating/reviewing with input SHA, success only in publishing_acceptance with saved receipt SHA, and failure with receipt or input SHA. Its acceptance_review gate requires publishing_acceptance. The amended negative-review ordering preserves these guards: valid negative receipts may publish COMMENT before entering a side state; host failure without a completed strict receipt uses failure status only. No journal schema or fictional receipt is required.

Default omission of remote pending avoids asserting an unqualified own-status isolation contract. Blocked/unstable/unknown and self-required acceptance contexts remain parked, rather than receiving inferred readiness or relaxed source gates. Exact acknowledged own COMMENT comparison is narrow enough to preserve new/edited/ambiguous external feedback and actual gate changes. Final merge still requires fresh clean server state, full source gates, genuine authority, operator all-writer boundary and nonbypass protection proof.

Writes are explicitly separated from PRSource._request's read-only/status200 API. The status201/review200/async202-or200 allowlists, conservative default HTTPError uncertainty, intent-before-send plus second freshness check, no replay and individual action limits are coherent with existing transport and journal contracts. Named fault tests cover genuine installed loaders/current input drift, retained process provenance, phase-specific lost responses, own COMMENT comparison and unsupported pending topology. Task4 context-first RED/GREEN and Task5 lifecycle/metadata wiring are assigned clearly.

## Limits

This is specification acceptance only. No tests, live journal/database reads, model/native execution, remote API/auth/protection effects, Git mutation or product implementation were performed. API facts were assessed against the supplied coordinator primary-source preflight, not a new remote probe. Current CI correction acceptance remains separate. Task3L is still required and unmet; pipeline-only Task4/5 progress neither waives it nor completes Task3/Issue17/Task6. Actual all-writer authorization and strict server-protection qualification remain unattested external pilot gates. No native pilot or unattended readiness is approved.
