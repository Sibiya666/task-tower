# Independent code review

Date: 2026-11-01. Reviewer: github_projects_code_review agent, distinct from implementation agents. Scope: GitHub connections/store/books/Project projection/remote postmerge worker, tests and both workflow templates, against AGENTS.md and the approved specification/plan. No implementation edits, commits, pushes or rollout actions by this reviewer.

Verdict: accepted for the documented postmerge-only implementation scope. No remaining consequential code findings identified after the fixes below. This is code review acceptance, not deployed project completion or physical distributed-run acceptance.

## Findings resolved

- Board CLI previously never supplied its completion verifier, causing valid accepted work to project needs_input. CLI now reads effective lifecycle and verifies remote completion before mapping Done. Independently ran the eight board tests successfully.
- Dispatch/recovery previously overwrote mutable lifecycle outside the serialization boundary. Dispatch now appends immutable queue intent; recovery executes within the same per-Issue workflow after checking the previous Actions run stopped. Consumer validates the actual main-branch workflow identity before preparation or review.
- Read-modify-write Issue publication could erase concurrent prose. Lifecycle now appends comments; closing uses a state-only PATCH. Books and board read the resulting lifecycle without rewriting Issue bodies.
- A stale runner-local receipt could override a newer recovered rejection on another machine. Independently reproduced: run 42 approval persisted on A; remote run 99 rejected; A run 100 republished run 42 and closed the Issue. Receipt reuse now requires authoritative run_id and run_attempt equality. Separate acceptance and worker regressions cover the scenario.
- Dispatch/reconcile refused pending publication retries for completed reviewed/running/done-but-open attempts. They now allow a completed recorded run to schedule publication retry without resetting its identity. Active runs remain skipped; missing evidence fails closed in consume without silently running another model review.
- Remote receipts now require trusted completed workflow provenance, artifact identity/digest, exact repository/Issue/attempt, main ancestry, current verified CI bundle, all platforms required by the owning project policy, independent executor/reviewer identities and a skill-policy digest. Fresh-runner tests exercise the actual remote verifier and reject a second model invocation.

Reviewed connections and books behavior includes repository-scoped identities, explicit private configuration, bounded transport/pagination, commit-pinned library, escaped HTML, import retention/idempotence, source/output preservation and malformed-source isolation. Output and malformed-row fixes identified by the independent test acceptor were inspected; no additional consequential finding remains.

## Verification

Independent final command, from the isolated task-tower-github checkout:

`C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest discover -s tests -v`

Result: exit 0, 165 tests in 33.039 seconds, two environment-dependent symlink skips; no failures or errors. This includes stale-receipt, publication-resume, two-repository/two-board, immutable prose and fresh-runner receipt regressions. An earlier overlapping-edit run had a transient pre-fix board test failure; the final run supersedes it.

GitHub queue:max syntax was independently checked against current official documentation: it permits 100 pending runs; overflow is canceled. It is valid syntax. Durable intent and reconciliation remain necessary. Source: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency

## Acceptance limits

The worker consumes independently produced merge evidence and performs postmerge acceptance; it does not implement development execution, automated merges or a repository merge barrier. Trusted installation configuration, maintained workflow source and host credential stores remain trust boundaries. Remote review artifacts have finite retention; unavailable evidence fails closed.

Project mutation and cross-machine execution are covered by fixtures. No installed project workflow, live Project permissions/membership, registered second physical runner or end-to-end remote acceptance was verified by this review. Read-only API smoke and any operator-authorized Issue import are separate evidence. No claim that this feature is merged into main or postmerge-accepted is made.

Scoped final policy correction reviewed: required_platforms is a nonempty unique valid subset selected by trusted project configuration and carried by the attested receipt (Task Tower defaults to all three). Preparation and receipt verification apply the same validation; Linux-only approval, failed required Linux and duplicate rejection are covered in the updated fixture. No additional finding. Parent and independent test acceptor are running final verification after this correction; the 165-test result above predates this scoped change.
