# Headless operation through the review boundary

Stage 4 adds fixed executor/reviewer lifecycle commands to the accepted Beads
service and host connector. GitHub delivery, accepted main, task closure,
deployment and an autonomous pilot belong to later stages. Model completion and
`awaiting_merge` do not mean accepted delivery. No UI is required or verified.

## Authority and persistence

Native Beads/Dolt owns tasks, dependency readiness, actors and history. The
service accepts only a published, operator-approved immutable plan digest. It
checks actual task text, dependencies, owner and metadata again before effects.
SQLite stores attempts, command inbox/outbox, events and decisions, never a
second task queue. A third task remains in Beads when both connector slots are
occupied. Nothing imports old backlog or starts an old worker.

The existing explicit-assignment `connector ... run` path remains available.
The managed path below is explicitly started in the foreground. It neither
installs a service nor registers autostart. Use the already installed Python and
Codex executable; no model, account, approval policy or sandbox override is sent.
Keep all configuration, tokens and journals outside source. Model/custom/check
children receive no GH_TOKEN/GITHUB_TOKEN regardless of case; only later fixed
trusted host helpers may use host GitHub authentication.

## Configuration and invocation

Start the existing service with its private configuration:

```console
python -m task_tower.service.cli --config <private-service-config>
```

Its existing keys are `version`, `executable`, `projects`, `journal`,
`connectors`, `approved_plans`, `port`, `poll_seconds`. Optional
`max_active_tasks` defaults to 2 (integer 1 through 32), applied separately to
each connector. Lowering it prevents new claims/resumes; it does not interrupt
existing attempts. The service remains bound to 127.0.0.1 with connector-scoped
bearer authentication and bounded JSON requests. Private token-file checks
remain mandatory.

A managed connector config retains `version`, `connector_id`, `endpoint`,
`token_file`, `journal`, `app_server` and `projects` from Stage 3, replacing the
single `assignment` with `assignments`: an explicit list of up to 32 approved
host assignments. Each entry has `project_id`, `bead_id`, exact 40-character
`base_sha`, and `input: {text: ...}`. The managed model brief is built from the
published approved task, not from arbitrary assignment prose. An empty list is
valid for an operator CLI config. `projects` retains trusted host mappings
`{project_id: {repository, worktree_root}}`; no path comes from the HTTP API.
An optional connector `max_active_tasks` defaults to 2 and bounds local workers.

```console
python -m task_tower.connector.cli work --config <private-connector-config>
python -m task_tower.connector.cli decision list --config <private-connector-config>
python -m task_tower.connector.cli decision respond <decision_id> --answer decline --config <private-connector-config>
python -m task_tower.connector.cli decision respond <decision_id> --answer approve --config <private-connector-config>
python -m task_tower.connector.cli resume <attempt_id> --config <private-connector-config>
```

`work` polls every 0.1 seconds locally, admits only configured native-ready
assignments at 2-second intervals, and respects both slot limits. Ctrl+C stops
only its owned processes; interrupted or ambiguous effects retain their fences.
Command/decision/resume actions are explicit operator effects using the private
API credentials. Decision CLI actions do not open an app-server or connector
journal. New tasks and scope expansions require a separately approved plan;
model prose never authorizes them.

## Lifecycle and wire contract

`GET /v1/commands` returns durable commands for the authenticated connector's
allowed projects. `POST /v1/commands/<id>/validate` performs fresh native
preflight. An acknowledged running command no longer grants fresh start authority,
even after a disconnect. `POST /v1/attempts/<id>/dispatch` has `{version:1,base_sha}`;
`POST /v1/attempts/<id>/resume` has `{version:1}`. Dispatch is allowed once from
claimed/not_started. Resume is allowed only after known stopped needs_input and
fresh native checks, with spare capacity. It resumes the existing author thread;
unknown or interrupted starts cannot be resumed through this command.

Managed `POST /v1/events` has exactly version=1, event_id, attempt_id,
connector_id and a typed `lifecycle` object. Its event, attempt state and resulting
commands commit in one SQLite transaction. Duplicate IDs return the committed
outcome; a different payload with the same ID fails. Legacy phase events cannot
advance a managed attempt. Durable command IDs are not JSON-RPC idempotency keys.
The connector saves intent before launch, thread identity before turn/start,
and command outcome plus outbox event together. A repeated command returns the
stored outcome, never a second turn or approval reply.

Executor completion supplies the actual committed Git head, immutable base and
full binary-capable Git diff. Dirty, foreign, non-ancestor or changed worktrees
fail closed. Each reviewer has a new actual app-server thread and a separate
detached checkout at head. The reviewer receives approved criteria, full actual
diff, exact H/B, actual reviewer thread ID and relevant Superpowers instructions.
Reviewer checkout changes invalidate the result. Independent findings return to
the same author thread and owned app-server. Three correction cycles are allowed;
the fourth changes_requested yields needs_input and a quiesce command.

The only accepted review result is strict JSON with exactly `verdict`
(`approve` or `changes_requested`), `findings`, `head_sha`, `base_sha`,
`reviewer_thread_id`. Each finding has `file`, positive integer `line`, `message`.
Approval requires no findings; changes_requested requires findings. Duplicate
JSON keys, extra fields, stale SHA, reused/self/invented reviewer identities and
prose approvals are rejected. Only the authenticated trusted connector binds the
model result to its actual command/thread/turn. Task 4 stops at awaiting_merge;
it cannot publish GitHub status, merge or close native tasks.

## Decisions, outages and stops

Only structured app-server command/file-change approval requests create managed
decisions. Arbitrary model prose is not scanned for questions. A pending request
holds its slot while its app-server is live. GET /v1/decisions lists pending and
answered records; POST /v1/decisions/<id>/respond has `{version:1,answer}` with
`approve` or `decline`. It creates a durable one-shot response command, never an
automatic permission grant. Response and following RPC ACK notifications retain
journal order. Unsupported callbacks or an expired/ambiguous RPC require
reconciliation. The original bounded RPC deadlines are unchanged: an operator
response after that boundary cannot revive an unknown request.

HTTP control polling/delivery use separate threads from each live attempt's RPC
consumer. An HTTP outage does not stop current model work or free a slot; events
remain durable and retry with the same event IDs. New claims require connectivity.
A lost turn/start answer, lost approval-send outcome, worker restart with pending
work, unknown cleanup or native drift leads to needs_reconciliation, with no
automatic replay. Existing worktrees and ownership remain intact.

needs_input frees capacity only after all owned activity has stopped and the
connector's quiescent acknowledgement is committed. Merely requesting a stop,
model completion, disconnection or an unknown outcome does not free a slot.
Explicit CLI resume is required; no automatic priority/resume policy is added.

The MVP bounds results to 32768 UTF-8 bytes, full diffs to 24576 bytes, briefs to
32768 bytes and HTTP event bodies to 65536 encoded bytes. Oversize/unsupported
results fail closed without truncating the reviewed diff. Inspect retained
private journals and reconcile; do not replay a fenced command or clear another
actor's native claim. Transport receipts are not PR/main acceptance receipts.

## Verification

```console
python -m unittest tests.test_service_lifecycle -v
python -m unittest tests.test_service_beads tests.test_service_store tests.test_service_api tests.test_connector_rpc tests.test_connector_worktrees tests.test_connector_recovery -v
python -m unittest discover -s tests -v
```

Contract fixtures exercise real Git checkouts, SQLite transactions, HTTP and
stdio subprocesses. They substitute only model behavior/native test boundaries;
they do not establish autonomous release acceptance. Authentic bounded app-server
and native-data evidence must be reported with its actual limits. UI/manual
window checks remain deferred; applicable automated/security/CI and independent
PR/main gates remain mandatory.
