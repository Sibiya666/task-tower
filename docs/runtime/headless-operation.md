# Headless execution and trusted delivery

The service and host connector implement fixed executor/reviewer commands and
opt-in trusted GitHub delivery through exact-main verification and native owner
closure. The Linux deployment is an explicit opt-in. Container smoke and fixture results
are separate from acceptance of the real autonomous pilot. Model
completion and `awaiting_merge` do not mean accepted delivery. No UI is required
or verified. Implementation and fixture checks do not claim a delivered pilot.

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
children receive no GH_TOKEN/GITHUB_TOKEN regardless of case; only fixed trusted
host GitHub operations may use existing host authentication.

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
Reactivating a stopped existing worker also requires a local slot. Queued model
commands reserve capacity before consumption; respond/quiesce remain available
for existing attempts when the limit is full or has been lowered.

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

### Inspect ready work and import an approved plan

Use the existing private connector config (an empty `assignments` list is valid)
and its authenticated API client; no manual HTTP request is needed:

```console
python -m task_tower.connector.cli ready --project-id <approved-project-id> --config <private-connector-config>
python -m task_tower.connector.cli plan import --project-id <approved-project-id> --request-id <stable-import-request-id> --digest <approved-sha256> --plan-file <approved-plan.json> --config <private-connector-config>
```

Replace angle-bracket placeholders with actual values and quote paths containing
spaces. `ready` prints a JSON array of that project's published, native-ready
tasks. Both the connector config and the service's connector permissions must
allow the project. These commands do not start Codex, create connector journals
or worktrees, claim work, or perform GitHub delivery.

The plan file is strict UTF-8 JSON without a BOM, duplicate keys, nonfinite
constants or trailing content, at most 65,536 bytes. It contains the existing
`tasks` array, with each task's `id`, `title`, `description` and `depends_on`.
The HTTP request, including its envelope and JSON escaping, must also fit the
existing 65,536-byte API body limit. Responses retain the client's 1 MiB bound.

The service operator must first review the exact immutable plan and explicitly
allow its digest for the project in the private service `approved_plans`
configuration before starting the service. The lowercase SHA256 is calculated
over canonical JSON, using the existing helper
`task_tower.service.store.plan_digest(plan)`: sorted keys, compact separators,
ASCII escaping, UTF-8 bytes. It is **not** a hash of the pretty-printed file.
Changing task text or dependencies requires a newly reviewed digest. Supplying
`--digest` only checks that the local file matches the expected plan; it grants
no approval and cannot modify the service allowlist.

`plan import` prints the canonical batch object (`request_id`, `project_id`,
`digest`, `state`). Success means `state: "published"`, with exit status 0.
Repeat the same request ID and unchanged plan/digest after a lost response to
retrieve the same batch without creating duplicate tasks. Rejection or
unavailability returns nonzero; a returned `needs_reconciliation` batch is
printed with nonzero status and retains its native effect fence. Resolve that
state through the established operator procedure; do not change request IDs to
replay unknown effects. Publishing a batch or completing a model turn does not
mean accepted pilot delivery.

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
model result to its actual command/thread/turn. Without explicit delivery
configuration, work remains at awaiting_merge. Model processes never publish
GitHub status, merge or close native tasks.

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

## Trusted delivery (Stage 5)

Both private service and connector configurations may explicitly include
`delivery_projects: {project_id: "owner/repository"}`. Omit it to retain the
review boundary. Each project must already exist in the respective trusted
configuration. This mapping grants no new credential scope and cannot come
from a task, model result, HTTP-supplied path or display configuration. Existing
host credentials are resolved only by the fixed host adapter. The legacy single
assignment `run` command remains an execution-only path.

Independent approval queues a durable `deliver` command. The connector verifies
its service assignment and reserves the repository before consuming it. Service
and connector journals both retain repository ownership through merge and main
acceptance, including uncertain outcomes. Other repositories can continue; a
busy repository's unstarted command stays queued. No background deployment or
second task scheduler is created.

The fixed host operations validate all origin fetch/push URLs against the
allowlist using the same effective global/system Git configuration, environment
and command configuration as authenticated push, including URL rewrites and
existing credential routing. They recheck all destinations immediately before
pushing only the owned deterministic branch, and create/reuse its PR to main. They require the actual H/B, independent recorded reviewer, all current CI
and protection. Only the complete expected docs shard matrix may skip. The
adapter publishes a real `task-tower/pr-acceptance` status bound to the independent
verdict, verifies its actual creator/id/description, and re-reads H/B and
mergeability before expected-head protected merge. No native human approval is
invented, and no protection setting is modified.

A changed base invalidates review, consumes one of the existing three correction
cycles and returns to the same author thread. A bounded fresh fetch prepares a
merge in the owned worktree; the executor resolves conflicts and commits it.
Even a clean upstream merge is left for that executor to commit. Other dirty
worktrees and unknown update intents remain fenced. New actual source requires
new CI and a fresh reviewer. A fourth correction requires input and known
quiescence, as in the execution lifecycle.

Merge intent is committed before the merge request. A lost response causes GET
readback, never another merge request. Verified merge facts emit one durable
`merged` event and move the service attempt to `postmerge` while CI is pending.
No branch/main push check is inferred: the existing PR and postmerge workflows
are the applicable routes. A postmerge failure leaves Beads open and cannot
cause re-merge.

Main verification starts with a successful fresh origin/main fetch (60 seconds)
and local exact SHA/two-parent checks (10 seconds). Failed fetch stops before
source polling, discovery, a reviewer or acceptance publication. The adapter
checks actual run/repository/PR chronology, latest run attempt, complete job
outcomes, artifact provenance and GitHub ZIP digests. Runtime acceptance requires
all four exact-M manifests, complete execution counts, prescribed exact-once
selections and fresh checkout discovery through the source-bound verifier, plus
the complete authentic runtime merge-event. A docs artifact instead requires
fresh bounded source validation and skipped runtime shards; its typed receipt
retains `documentation.validation` and `runtime_tests:not_run`.

A fresh owned postmerge app-server reviews the complete actual main diff and
original criteria in a separate immutable checkout. Its thread must differ from
all author/premerge threads. Unknown starts, changes requested, source drift,
unsupported callbacks or approval requests stop for reconciliation; they are
never automatically approved or converted into acceptance. This bounded MVP
adds no automatic recovery of such a postmerge review. Existing execution-stage
structured decisions and explicit CLI responses remain available.

`POST /v1/attempts/<id>/accept` is an authenticated fixed-connector route with
`{version:1,request_id,merge,evidence}`. The service validates the owned phase,
repository, H/B/M and typed receipt, then durably saves accepted evidence and a
close intent before native owner-close. Acceptance requires readback of the
closed task, preserved owner and the exact native history event carrying the
receipt reason. Lost close/HTTP responses read back the existing result first;
an ambiguous outcome retains reconciliation and cannot repeat native close.
Only confirmed canonical closure releases the acceptance lease and marks the
attempt accepted. The worker then closes its retained owned author transports
and confirms cleanup before freeing local capacity. Unknown cleanup retains the
app, occupancy and durable reconciliation fence. Admission unions live attempts
with journaled unresolved cleanup reservations, counting an attempt once. These
reservations survive a journal reopen/new connector and remain until verified
owned cleanup or explicit cleanup reconciliation; a closed Bead or restart
cannot release them. Before remote acceptance can free a service slot, the
connector durably records the cleanup reservation and its owned resource IDs.
The resource identity stays with the actual retained transport across same-author
corrections. Lost accept/readback responses and confirmation-write failure retain
the fence. Delivery, known-live quiesce and controlled shutdown may confirm only
resource IDs whose owned transports actually closed; empty or unmatched evidence
cannot clear an old reservation. Confirmation appends a timestamped local receipt
without changing the unknown command outcome or replaying delivery. Unbound
controls cannot acknowledge unknown old-process cleanup. Known existing controls
remain available when limits are full or lowered. A premerge supersession keeps
the same author app for revision. No GitHub Issue is created as a duplicate of
Beads.

## Verification

```console
python -m unittest tests.test_headless_delivery tests.test_headless_acceptance tests.test_service_lifecycle -v
python -m unittest tests.test_service_beads tests.test_service_store tests.test_service_api tests.test_connector_rpc tests.test_connector_worktrees tests.test_connector_recovery -v
python -m unittest discover -s tests -v
```

Contract fixtures exercise real Git checkouts, SQLite transactions, HTTP and
stdio subprocesses. They substitute only model behavior/native test boundaries;
they do not establish autonomous release acceptance. Authentic bounded app-server
and native-data evidence must be reported with its actual limits. UI/manual
window checks remain deferred; applicable automated/security/CI and independent
PR/main gates remain mandatory.

## Linux Docker deployment (Stage 6)

Build and launch only this Compose project explicitly; no host installation,
autostart, canonical migration or backlog import is performed:

```console
docker compose -p task-tower-headless -f deployment/headless/compose.yaml build
python deployment/headless/smoke.py --image task-tower-headless:stage6 --receipt <outside-source-receipt.json>
```

The image pins the Task 1 Debian amd64 manifest and Beads 1.3.4 archive/binary
checksums. Python 3.13.5, Git, libc and CA packages come from the immutable signed
Debian snapshot `20261104T212339Z`; embedded Dolt ships in that pinned bd binary.
The Docker frontend is digest-pinned too. The Dockerfile-specific default-deny
ignore permits only Python source and the build definition; Git metadata,
installation configuration, runtime, DBs, logs and executor repositories are
excluded. Build downloads these pinned public dependencies; runtime does not
download tools. No `latest`, model authorization or Docker socket is used.

The smoke creates two new UUID-named volumes, provisions one private random API
token through stdin, initializes a fresh native database, imports only its approved
fixture, claims through authenticated HTTP, checks native owner/history and
restarts its own idle service to verify persistent attempt identity. It then stops
its container and retains the container/volumes plus a sanitized JSON receipt.
It never mounts host directories or touches a canonical database. A failed smoke
is a failure, and its retained volumes are not a replacement production database.
The smoke is also one bounded PR CI job; it does not replace the four complete
Windows unittest shards or change the exact-main Windows artifact identity.

For an operator-approved pilot, provision **new dedicated** Compose volumes before
`up`. Use an ephemeral provisioning container from the built image with only those
two named volumes and network disabled. Initialize bd only in a new empty project
under `/data/beads`; use `bd init --prefix <approved-prefix> --non-interactive
--skip-agents --skip-hooks`. Do not run init against an existing database. Create
`/data/runtime/service.json` and a private alphanumeric token file of 32–256 bytes
(mode 0600, owned by the service user); pass secrets through stdin/private files,
never argv, environment, source or public receipts. The configuration must contain
only approved project paths and immutable plan digests. Example shape (replace the
digest and token with private operator-provisioned values):

```json
{
  "version": 1,
  "executable": "/usr/local/bin/bd",
  "projects": {"pilot": "/data/beads/pilot"},
  "journal": "/data/runtime/service.sqlite3",
  "connectors": {"host1": {"token_file": "/data/runtime/token", "projects": ["pilot"]}},
  "approved_plans": {"pilot": ["<approved-plan-sha256>"]},
  "delivery_projects": {"pilot": "Sibiya666/task-tower"},
  "port": 8765,
  "poll_seconds": 2,
  "max_active_tasks": 2
}
```

HOME is `/data/runtime/home`: embedded Dolt needs writable user state even for
native ready/show. Keep that directory in the runtime volume. Compose mounts only
`/data/beads` and `/data/runtime`, keeps the image filesystem read-only, bounds PIDs,
drops all capabilities and sets no-new-privileges. It publishes exclusively
`127.0.0.1:${TASK_TOWER_PORT:-8765}`. Inside the separate Linux network namespace,
`--container-network` explicitly binds 0.0.0.0 so Docker bridge forwarding can reach
the API; that option rejects non-Linux/non-Docker hosts. Ordinary host service
invocation still binds only 127.0.0.1. Do not publish another host interface, use
host networking or attach untrusted containers to this API network.

```console
docker compose -p task-tower-headless -f deployment/headless/compose.yaml up -d --no-build
python -m task_tower.connector.cli work --config <private-host-connector-config>
docker compose -p task-tower-headless -f deployment/headless/compose.yaml stop
```

Configure the host connector with `http://127.0.0.1:<published-port>`, the matching
private token and only the approved pilot assignment. Repositories, worktrees,
Codex authorization and trusted GitHub credentials stay on the host. Neither
model processes nor Docker receive the trusted helper's GitHub tokens. The
connector creates the real author, each fresh reviewer and postmerge reviewer;
manual verdict transfer or merge cannot count as the autonomous pilot. Preserve
actual bead/attempt/thread/turn/PR/H/B/M/CI/closure identities in the acceptance
receipt. Do not mark the release delivered from this configuration or a fake E2E.

The canonical backlog remains unchanged. Any later native backup/restore and
single-writer switch requires its own explicit authorization and proof that no
other writer or live claim is affected. Never copy the active canonical database,
mount it simultaneously on host/container, or clear an unknown-effect fence.


Transport control queues remain bounded. Command output display deltas are not
lifecycle evidence and are excluded before that queue; RPC responses, callbacks
and turn completions are preserved. Oversize/malformed messages and control-queue
overflow still fail closed. A fixed, payload-free transport failure reason is
retained in the connector command journal with its reconciliation fence. This
never authorizes replay of an unknown turn, merge or close.
