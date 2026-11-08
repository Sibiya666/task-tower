# Trusted project intake

Authorized scope: append-only reload of operator approvals and connector assignments;
explicit adoption of existing unassigned open native task snapshots. No new task engine.

Contract: adopt plans add `parents` to every task. They bind exact title, description,
blocking dependencies and parent-child IDs. Adoption writes no native task, owner,
status or history. Publication follows two fresh readbacks; unknown reads retain a
reconciliation fence. Claims recheck the approved parents as well as blockers.
Reload preserves every immutable trusted setting and all existing entries; only
new approved digests/assignments are admitted. Legacy import and static config work.

- [x] Adoption validation, readback, idempotency, restart and drift tests.
- [x] Scoped API/CLI adopt entry point.
- [x] Append-only service approval and connector assignment reload.
- [x] Focused tests and Reslop full-diff review (50 focused tests pass).
- [ ] Complete full-suite result and independent parent review; no runtime activation.
