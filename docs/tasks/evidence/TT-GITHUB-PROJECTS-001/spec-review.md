# Independent specification acceptance

Date: 2026-11-01. Reviewer: independent specification-review agent; no implementation reviewed.

Inputs: AGENTS.md; docs/superpowers/specs/2026-11-01-github-projects-design.md; docs/superpowers/plans/2026-11-01-github-projects.md; architecture design revision 2. Verdict: **changes required before claiming the approved distributed project capability accepted**. The milestone can ship as an explicitly limited scaffold if these limitations remain visible.

## Blocking gaps

1. **Project ownership is not implemented by the plan.** Approved direction requires each repository to own Issues and a GitHub Project; Data and ownership only supplies an optional Project URL, and Task 1 only exposes Issue operations. Define Project binding/validation and idempotent item/status projection, or explicitly document owner-created Project setup and unsupported synchronization. Acceptance must prove two independently owned Projects and avoid suggesting a URL alone provides Project integration.

2. **Concurrency is not a complete durable queue contract.** Distributed execution specifies one Issue concurrency group, but not lost dispatch reconciliation, pending-run behavior, or shared durable attempt ownership. GitHub defaults to replacing an existing pending run; queue:max now allows up to 100 pending runs, with overflow still canceled. Specify whether duplicate Issue dispatches are intentionally coalesced; persist work intent independently and reconcile canceled/unknown dispatches. All supported consumers must use the same trusted serialization boundary. Test active + multiple pending deliveries, cancellation, unknown dispatch response and recovery on a different runner. Source: [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency), checked 2026-11-01.

3. **Cross-machine evidence and acceptance authority need a concrete contract.** “Persisted review” has no authoritative remote location or binding schema in Task 2. Define repository/Issue/attempt, exact candidate and merge SHA, reviewer identity distinct from executor, trusted policy version, required check names and source, decision and publication marker. Load these from a trusted durable source on another machine; reject issue-author-edited acceptance, omitted checks, wrong repository/SHA and reused attempt evidence. A runner-local file cannot satisfy durable cross-machine publication recovery. Prove publication retry on runner B without repeating the model review completed by runner A.

4. **Trusted execution/bootstrap boundary remains underspecified.** A trusted workflow plus trusted local commands is a sound direction, but the plan does not freeze the workflow/bootstrap ref or establish who may authorize dispatch/recovery. Define default-branch/pinned trusted bootstrap loading, numeric Issue validation, no command interpolation, narrowly scoped credentials, and a trusted recovery operation that first proves the old attempt terminated. Credentials removed from subprocess environment do not prevent access to inherited credential stores; document that a worktree is not isolation, and restrict execution to trusted project operators/runners. Tests should reject untrusted workflow refs, edited Issue command fields and unprivileged recovery; no broader sandbox claim is warranted.

5. **Existing architectural gates must survive the new adapter.** The architecture requires repository-wide merge serialization until prior postmerge acceptance, and Superpowers evidence tied to accepted inputs. The new plan mentions only per-Issue concurrency and final acceptance. Explicitly retain the existing merge barrier and stage gates, or state remote worker cannot merge and only consumes independently produced merge evidence. Test two Issues in the same repo: first failed/unavailable postmerge prevents the next automated merge; independent projects remain runnable. Require current spec/plan/premerge review evidence before execution/publication rather than allowing an Issue metadata state to bypass the process.

## Nonblocking refinements

- Declare the private installation config default path and whether an explicitly supplied tracked path is rejected; examples must contain placeholders only.
- Define Issue body conflict handling so metadata publication preserves concurrently edited user prose; read-modify-write needs conflict detection/reconciliation.
- Spell out library tree truncation/size bounds, commit-pinned links, and stale/partial project UI states. The planned tests already cover the main namespace, escaping, pagination and import hazards.
- Attach observed GitHub smoke identity/permissions and timestamp to evidence; a read-only API smoke proves connectivity, not installed workflows, a registered second physical runner or an end-to-end durable run.

No code changes, commits, pushes, runner registration, or rollout claims were made by this review.

## Resolution recorded

Parent authorized specification/plan amendments after this review. Added concrete Project projection, durable intent/evidence, trust, recovery, Superpowers and merge-scope requirements to both implementation documents. Specification is accepted as amended for implementation; capability acceptance remains pending independent code/test evidence. No board auto-creation or physical runner rollout is claimed.
