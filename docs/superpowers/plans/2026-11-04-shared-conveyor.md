# Shared conveyor implementation

Spec: docs/superpowers/specs/2026-11-04-shared-conveyor.md
Use Superpowers executing-plans, TDD and independent task/final acceptance.

### Task 1: Shared GitHub ownership and single-launch gate

Add shared_queue.py, reusing GitHubTasks request transport. Implement strict
claim/state messages, atomic reference create, known-owner read, exact-parent
fast-forward intent CAS, conservative unknown handling. No expiry/reassignment.
Tests: two independent processes through a shared HTTP server, duplicate claim,
lost claim response, lost intent response, changed Issue identity and restart.
Expected: at most one launch permit per immutable Issue and no local DB lock.

### Task 2: Superpowers worker and automatic refill

Add shared_worker.py and CLI integration, strict private config/paths/allowlist,
worktree preparation, pinned Superpowers request and configured trusted harness
adapter. Capture real process facts, record awaiting_acceptance/needs_input and
move to the next Issue without declaring completion. Reuse existing GitHub-ready
selection and process runner. Do not silently consume unsupported legacy proofs.
Tests: actual two OS workers and actual helper processes executing prepared
Superpowers tasks; overlap, automatic refill, one-task race, interruption and
no duplicate execution. Full integration command must pass before task complete.

### Task 3: Actual GitHub pilot and integration handoff

Prepare reviewable operator profile and named pilot Issues in the existing
project, verify real GitHub CAS race and native harness path. Wire accepted
results to independent PR/main consumer without inventing provenance. Verify
accepted-main automatic closure before claiming whole conveyor ready. Document
remaining external access/platform requirements accurately. Run full regression,
independent exact head/base PR review, CI and authorized main integration.
