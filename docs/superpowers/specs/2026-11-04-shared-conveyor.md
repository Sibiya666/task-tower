# Shared GitHub development conveyor

User-approved outcome, 2026-11-04: independent agents obtain tasks from the same
GitHub backlog, execute through installed Superpowers, and automatically obtain
next tasks. Demonstrate two independent worker processes without duplicate task
execution. This is the priority integration path; do not replace it with another
local-only queue or a new implementation of Superpowers task execution.

## One vertical flow

Each project retains its own Issues/Project. Reuse connected project identity,
private allowlist, GitHub Issue metadata/dependency selection and installed
trusted harness configuration. Books aggregate those sources. No cross-project
registry or credentials are committed to task-tower itself.

Workers poll ready authorized Issues. Claim identity is repository plus immutable
Issue ID; include Issue number/task ID and accepted criteria digest. Acquisition
uses atomic GitHub reference creation in reserved branch namespace
refs/heads/task-tower/claims/issue-<immutable-id>. The reference points to a Git
commit whose closed JSON message records ownership/state; its tree is the
existing main tree, so metadata claims change no project code. Exactly one
create can win. Assignee, comments and local SQLite are not the lock.

Expose ownership through the Issue's native Assignees field, also visible on its
linked Project card when that field is enabled. Skip already assigned Issues.
After atomic acquisition, confirm assignment to the configured GitHub account
before launching the harness; failed assignment blocks that execution. Several
workers may use the same GitHub account, so the claim's worker/session identity
distinguishes actual executors. Removing an assignee never releases a claim or
authorizes a duplicate run. Preserve the assignee during independent acceptance.

Use a unique actual worker-process session per startup; never restore executable
ownership from a record. Before invoking any harness, append an execution_intent
commit with the exact previous claim commit as its sole parent; update reference
with force=false and verify the exact resulting ref. This fast-forward gate
prevents two clients advancing sibling intents. Any conflict, unavailable read,
lost intent response or unknown execution blocks launch for that claim. Never
expire/delete/reassign a claim automatically. A lost claim-create response may
only be reconciled in the same still-live attempt by reading its exact proposed
commit; no process restart is permission to execute again.

After confirmed intent, invoke only the private configured harness, with bounded
process/capture/cleanup, stripped publication credentials and a request bound to
one Issue/claim/worktree. Request references the pinned installed Superpowers
instructions and repository plan. Superpowers supplies its normal task brief,
implementation/review/testing loop and ledger; Tower does not invent another
inner task engine. Each execution has its own Git worktree/private repository.
Issue content never supplies a shell command, model, account or authorization.

Persist actual process/result facts before updating shared execution state.
Successful harness return means awaiting_acceptance, never task done. Failed or
uncertain outcomes retain the claim and visible needs_input/unknown state; no
second model launch. After handing off a result, an available worker takes the
next ready unclaimed Issue without a chat prompt. No fixed global two-worker cap;
the two-worker test is a scenario, actual capacity/budgets remain installation
policy. Same repository PR/main integration remains serialized and stale base
requires fresh review/checks.

Independent specification/development/test/PR/main acceptance remains required.
Only verified accepted main and actual GitHub closure complete the task. The
queue driver cannot mark done based on model JSON, Markdown or a green process.
Connect the existing PR/main acceptance consumer through an explicit trusted
adapter; unsupported provenance stays awaiting_acceptance. Do not forge legacy
or pipeline stage records to make the integration appear complete.

## Proof and scope

Run two OS processes against one shared server-side test transport: both race
for the same Issue and only one harness starts; different Issues execute in
parallel and the workers refill from the next tasks. Kill/restart and lost-write
cases never duplicate execution. Then verify atomic acquisition against real
GitHub with explicitly named pilot Issues and retain links. Fixture server and
two processes on one host do not prove two physical machines. Original Issue19
multi-machine/handoff/recovery scope stays required and is not silently waived.
Preserve original pending17/18 branches. Keep local test profiles/credentials out
of Git; update README/AGENTS/bootstrap instructions with actual installed state.
