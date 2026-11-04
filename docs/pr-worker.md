# Private PR worker

Issue17 implementation is still undergoing integration and independent
acceptance. The commands below describe the current candidate; an installed
pilot, final full-suite/CI checks and whole-PR/main acceptance remain required.
This worker coordinates genuine new pipeline tasks. Old unproven task cards
remain deferred to Issue66.

## Inputs and startup

Complete [GitHub project setup](github-setup.md) and the existing
[pipeline setup](pipeline.md) first. Keep installation files and both journals
outside project checkouts. The PR policy uses the strict schema in
`task_tower/pr_policy.py`: actual repository/Issue ID/PR/task identity, original
pipeline run ID, reviewer/postmerge profile IDs, trusted publisher, required
check identities/platforms and the existing executor configuration. Its
`pipeline_journal` identifies the original existing pipeline database; it is
different from the PR worker's `--journal`.

Keep `merge_enabled` and `exclusive_writer.enabled` false until the actual
operator/writer boundary and current server protection are verified. A valid
configuration, green CI or a chat approval does not establish those facts.
The worker never changes branch protection or requests additional credentials.

For pipeline tasks pass the actual pipeline configuration explicitly:

```powershell
python -m task_tower pr-worker watch --connections C:/TaskTower/private/connections.json --config C:/TaskTower/private/pr.json --journal C:/TaskTower/private/pr.db --pipeline-config C:/TaskTower/private/pipeline.json
```

Paths above are examples. `watch` executes configured read-only review roles
and permitted PR actions; it is not a readiness-only command. It runs a fixed
contained host process that holds one original owner through all ticks. Its
parent only supervises time, channel integrity and process-tree cleanup.
Private inputs are checked independently before the child opens its PR writer,
then compared with the parent snapshot. No original pipeline journal recovery,
initialization or replacement is performed.

Ctrl+C requests a clean stop, followed by bounded whole-tree termination when
necessary. Uncertain roles/writes and original merge barriers remain fenced.
Restarting never steals an old task owner or replays an intent.

`work` requires `--once` and the same input flags. It performs one diagnostic
step, then retires its owner. Use `watch` for the complete multi-step cycle:
another process cannot resume a task admitted by the retired one-shot owner.
Do not delete/reset a journal or edit ownership to force continuation.

## Metadata without executable dependencies

`status`, `cancel` and `reconcile --inspect` require connections, PR config path
and PR journal path, but do not load the PR/executor/pipeline policy or roles.
The config path is still checked for private-path safety; its file may be
missing. These commands remain available after role files/pins are revoked.

```powershell
python -m task_tower pr-worker status --connections C:/TaskTower/private/connections.json --config C:/TaskTower/private/pr.json --journal C:/TaskTower/private/pr.db
python -m task_tower pr-worker cancel --connections C:/TaskTower/private/connections.json --config C:/TaskTower/private/pr.json --journal C:/TaskTower/private/pr.db --repository owner/repo --pr 44
python -m task_tower pr-worker reconcile --inspect --connections C:/TaskTower/private/connections.json --config C:/TaskTower/private/pr.json --journal C:/TaskTower/private/pr.db --repository owner/repo --pr 44
```

Cancellation reports its retained flag; it does not fabricate completed cleanup.
Inspection returns local validated identities and effect states, never retries
or clears an unknown action. Public JSON omits private paths, prompts, raw argv
and raw exceptions. Exit0 indicates successful metadata/bounded operation,
exit1 operational uncertainty and exit2 invalid arguments/configuration/state.

The local owner lock is not a distributed queue or installed service. The
worker covers allowlisted PRs, not automatic development of every GitHub Issue.
Task19 and the group pool provide separate coordination capabilities.

## Original event inspection candidate

For a journaled PR with a recorded merge, `reconcile --inspect` additionally
reads original workflow archives through the matching connected repository.
It reports run/attempt/artifact identities, original task markers, platform
checks, merge identity and a canonical event digest. `event_sha256` uses the
existing PR v1 canonical JSON fingerprint of the complete archived event.
The live marker list is separate. Editing PR prose never refreshes an old
payload. Missing/expired/mismatched archives refuse the remote inspection.
Local status and cancellation still require no executable profile/policy/pins.

`reviewed_followup_required`, `explicit_reconciliation_required` and
`fresh_acceptance_required` are diagnostic required actions, not acceptance or
recovery permission. Inspection never changes journal rows, effects, barriers,
Issue state or archives. An unmerged local row retains its local-only report.
The actual `recovery_of` baseline/follow-up execution gate is still pending;
this reader does not enable old-card admission or manufacture baseline receipts.

## Same-owner source revisions

A before-intent refusal of a reviewed/publishing/accepted input now parks that
local input as stale when no consumed unresolved effect exists. Uncertain
intents retain their existing fences. A separate confirmed negative status
precedes preparation of a changed, genuinely authorized input. An unchanged
semantic source cannot acquire another review merely through a new nonce.
The original owner/PID, first-admission deadline and consumed review budget stay.
Changing PR text can invalidate original pipeline publication provenance; that
is not automatically requalified as a new source.

Fresh inputs preserve earlier COMMENT reviews as review material. Exact durable
acknowledgments may account for earlier own statuses on the same qualified
Task/PR/head. Their IDs, author, payload and observed hash must still match;
unknown or edited statuses refuse even the next role launch. All current source,
CI, private authorization and clean server gates remain required.

This component has independent development/test acceptance and a Root-owned
17-test replay including actual review/publication revision and changed-old-status
no-launch cases; see [evidence](tasks/evidence/TT-PR-WORKER-001/task5-source-revision-acceptance.md). Recovery baseline/follow-up execution,
installed pipeline pilot and whole-feature/PR/main acceptance remain pending.
