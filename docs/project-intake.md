# Trusted intake for existing native projects

This is an opt-in operator route, separate from `plan import`. Keep the existing
single writer and dedicated Beads executable for each approved project. Register
project roots, connector scope, model executable, credentials and delivery scope
before starting the service/foreground connector. This feature does not discover
repositories or import historical backlogs.

An already running `service.cli --config <private-service.json>` reloads additions
to `approved_plans` before its next request (idle polling interval 0.5 seconds).
An already running `connector.cli work --config <private-connector.json>` reloads
append-only `assignments` at its existing two-second admission boundary. No manual
claim, turn/start or model invocation is needed for each new approved assignment.
It still requires one explicitly started service and connector; this change does
not install a daemon. Legacy `run`, static direct callers and `plan import` remain
supported. Assignments stay bounded at 32 and projects at 32.

## Register one exact user instruction

1. Read native `show` for each intended open, unassigned task. Build an exact JSON
   snapshot with `id`, `title`, `description`, `depends_on` (blocking IDs) and
   `parents` (parent-child IDs, including parents outside this batch). Include only
   intended executable tasks. Parent containers do not become executable merely
   because their IDs are referenced. Blocking IDs must be within the approved
   batch unless an external blocker is already closed and passes both fresh native
   readbacks. External blockers are never adopted, mutated or made executable.
   Reopening one fences subsequent claim/execution. Adopt up to 32 tasks.
2. Compute the canonical SHA256 using `task_tower.service.store.plan_digest`.
   After operator review of that exact snapshot, append the digest to the trusted
   service file's `approved_plans[project]`. Write files atomically in their trusted
   directory; never take approvals or configuration from model output or HTTP.
3. Publish through the supported authenticated operator command:

   ```console
   python -m task_tower.connector.cli plan adopt --project-id <registered-project> --request-id <stable-request-id> --digest <approved-sha256> --plan-file <exact-snapshot.json> --config <private-connector.json>
   python -m task_tower.connector.cli ready --project-id <registered-project> --config <private-connector.json>
   ```

4. Append a connector assignment containing that project ID, native bead ID,
   exact approved 40-character `base_sha`, and `input: {"text": "<user instruction>"}`.
   The foreground connector admits it when published and native dependency-ready,
   with the normal claim/readback, capacity, approval callbacks and delivery gates.
   The manager registers scope and instruction; it does not launch the model.

Example snapshot (the parent itself is not admitted):

```json
{"tasks":[{"id":"pilot-a","title":"Approved change","description":"Exact native description","depends_on":[],"parents":["pilot-epic"]}]}
```

## Drift, reload and recovery

Adoption performs two complete native readbacks and journals publication intent.
It never creates, updates, reassigns or deletes a native task. Native history is
preserved. Exact title/description, open status, absent owner, blockers and parents
must match. A fresh normal claim checks the snapshot again; parent-child links
are not ready blockers. Existing owned/in-progress tasks cannot be adopted by
this route. Native metadata and unknown effects retain existing execution fences.

A repeated request/digest returns its journalled outcome. Read failures, mismatches
or interrupted adoption remain `needs_reconciliation`, including after restart;
a new request ID cannot bypass this fence or replay native effects. Do not edit
SQLite, clear ownership or remove dependencies to make a task ready. Investigate
native evidence and use established reconciliation procedures.

Live reload rejects removal or modification of existing assignments and approved
digests, duplicate assignments, scope expansion and changes to roots, credentials,
endpoint, journal, capacity, delivery settings or executable. Service retains the
last valid approval set; connector continues active work but skips new admission
when its file is invalid. Fix the operator file and retry normal polling. Revocation,
assignment retirement after the 32-entry limit, or any trusted-setting change needs
an explicit controlled restart with journals retained and active work reconciled.
Reload does not change model/account authorization or approval decisions.

After a controlled restart, only publications whose digest remains in the current
approval set can admit new claims. Revoked journal rows and existing ownership
remain recorded; restoring approval permits normal admission again. A repeated
request can read its prior outcome without restoring execution authority.

## Project-specific native and delivery authority

Optional service `native_profiles` bind per-project executable hashes, versions
and event readers. See [legacy event history](runtime/legacy-event-reader.md) for
the strict server-backed 1.0.2 route and its bounded compatibility evidence.
Never open an old database using the global newer binary to obtain history.

The optional `delivery_policies` is identical in service and connector config:

```json
{"local-project":{"mode":"local"},"remote-project":{"mode":"owner_pr","repository":"owner/project","base":"test"}}
```

`local` persists the independently reviewed source/result and performs no GitHub
operation. `owner_pr` pushes the reviewed branch and opens a PR against exactly
the configured base; only the owner decides whether to merge. Neither mode
automatically merges or closes native work as accepted. After owned transports
are verified stopped, the attempt becomes `handoff` with a saved receipt and
releases capacity. Unknown effects/cleanup remain fenced on restart.

The existing `delivery_projects` spelling retains Task Tower's automatic protected
main route. Explicit `task_tower` policies also require base `main` and all its
existing CI/independent PR/main gates. Do not reuse that acceptance contract for
unrelated repositories. A project cannot occur in both policy spellings. Policies
bind at native claim; changed service/connector/restarted authority cannot expand
an existing attempt's scope. Trusted policy changes require controlled restart
and reconciliation, never live assignment prose.
