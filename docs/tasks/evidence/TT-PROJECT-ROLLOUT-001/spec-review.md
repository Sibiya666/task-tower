# Independent onboarding specification and plan acceptance

Date: 2026-11-01
Reviewer: independent `project_onboarding_spec_review` agent, distinct from implementation.
Decision: APPROVED for implementation, with the clarifications incorporated below.
Repository baseline: `4544611ac81294cb6b7dcf85b7afab3397496a54`.

Accepted inputs (SHA-256):

- `docs/superpowers/specs/2026-11-01-project-onboarding-design.md`: `5481a7debe890f601039dc25f0ad6894ce5859e3db0b5ad76894801d703fa85f`
- `docs/superpowers/plans/2026-11-01-project-onboarding.md`: `5e8a5e69869734c2c40e8308713953a1805c29e33dc83e88751a3124540f5959`

Reviewed against repository AGENTS, architecture and GitHub project contracts, existing connection validation/persistence, import identity behavior, and the user's project-first requirement. Project setup precedes new Issue creation; human-confirmed Projects authorization is explicit; README/AGENTS and installer documentation are required clean-clone deliverables. Existing Issues 13-28 remain authoritative and must be populated rather than recreated. Issue 24 precedes dispatcher Issue 14.

Clarifications incorporated during review:

- Canonical repository/owner/node identity, explicit board selection and same-ID connection retargeting protection.
- Bounded discovery exhaustion and ambiguous or partial responses fail closed rather than imply absence.
- Unknown Project and Issue creation outcomes reconcile before any further create; unresolved outcomes remain actionable failures.
- Preserve board visibility, unrelated items, existing fields/options and configuration; remote success followed by config failure remains recoverable without deleting resources.
- Conflict-detecting atomic configuration writes must also serialize competing Task Tower writers, rather than merely compare then replace without protection.
- Import recognizes explicit `task_id`, `legacy_id` and legacy `id` metadata aliases per repository, refuses conflicting/duplicate identity matches, and reuses Issue 24 for `TT-PROJECT-ROLLOUT-001`.
- Membership repair preserves existing prose/evidence and authoritative lifecycle; cross-API partial success exposes the retained Issue and recovery stage.

No unresolved specification blockers. The plan has focused failure and preservation coverage, installer forwarding tests and live repeat-setup evidence. Distributed creation locking, autonomous development, PR intake daemon, new credential storage and physical-runner claims remain outside this milestone.

This accepts the stated design and plan only. It does not attest code, live API state, tests, PR head/base, main, or postmerge acceptance. Those independent gates remain required. No implementation files or remote state were changed by this reviewer.
