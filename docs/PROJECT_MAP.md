# Task Tower: connector and diagnostic map

Verified 2026-11-10 against the working changes on
`codex/preparing-bridge-20261110`, based on accepted
`068ced56537226a3bdc891a2dfbefaeac9f337f5`. This is a source map, not a claim
that the changed code is deployed or that a historical failure is resolved.

| Boundary | Source and responsibility |
| --- | --- |
| Operator entry | [connector CLI](../task_tower/connector/cli.py): explicit ready/import/adopt/decision commands and read-only inspect |
| Managed execution | [client](../task_tower/connector/client.py): fixed lifecycle commands and stage-bound failure recording |
| Git source | [worktrees](../task_tower/connector/worktrees.py): exact-source/clean-worktree checks and bounded Git operations |
| Transport state | [store](../task_tower/connector/store.py): owned journal, ordered events and unknown-effect fences; typed preparing intent and atomic result/worktree/ack storage |
| Safe inspection | [diagnostics](../task_tower/connector/diagnostics.py): typed receipts, private raw evidence and read-only snapshots |
| Preparing contract | [receipt/source](../task_tower/preparing_recovery.py): exact operator-digest binding and fixed clean engine identity, rejecting index flags that hide source changes. This library component enables no recovery route. |
| Preparing preflight | [worktrees](../task_tower/connector/worktrees.py): read-only command, preparing intent and bounded Git observations; no attach, resume or fence release. |
| Preparing attach | [runner](../task_tower/connector/preparing_recovery.py) and [worktrees](../task_tower/connector/worktrees.py): exact approved source, intent before contained existing-branch attach, clean identity readback and atomic known result; unknown outcomes stay fenced. No public recovery route. |
| Preparing native admission | [service contract](../task_tower/service/preparing_recovery.py): default-empty registry, fresh native eligibility, one durable deterministic control and safe status. Check: `python -m unittest tests.test_service_preparing_admission -v`. |
| Preparing acknowledgement | [service contract](../task_tower/service/preparing_recovery.py): atomic known result/control ACK/original execute/event; failed controls stay unknown and known duplicates never requeue. Check: `python -m unittest tests.test_service_preparing_recovery -v`. |
| Preparing local API | [HTTP](../task_tower/service/api.py) and [service config](../task_tower/service/cli.py): authenticated project/attempt-scoped admission/status, typed ACK events and startup-only exact receipt approvals; no live recovery authority. Check: `python -m unittest tests.test_service_preparing_api -v`. |
| Preparing connector bridge | [CLI](../task_tower/connector/cli.py), typed journal/ACK. Check: `python -m unittest tests.test_preparing_integration tests.test_connector_cli -v`. |


The operator command and its limits are in
[connector diagnostics](runtime/connector-diagnostics.md). Core verification:
`python -m unittest discover -s tests -v`; focused diagnostic contracts:
`python -m unittest tests.test_connector_diagnostics -v`. Run final checks through
Reslop as required by the working agreements and retain raw evidence locally.
Real disposable Git attach checks: `python -m unittest tests.test_preparing_attach -v`.
Typed journal checks: `python -m unittest tests.test_preparing_operations -v`.
Preparing contract/preflight checks: `python -m unittest tests.test_preparing_recovery tests.test_preparing_preflight -v`.

Beads remains the canonical task/owner/dependency/history engine. See
[current direction](current-direction.md) and [project intake](project-intake.md).
Inspection neither launches a worker nor authorizes recovery or delivery.

## Signed webhook transport

Source verified 2026-11-11: working changes based on `1e6b6d2cf388dd1543bf508854055bd987ca6828`.
[Receiver](../integrations/github_webhook/receiver.py),
[HTTP entry](../integrations/github_webhook/api/index.py) and
[inbox](../integrations/github_webhook/inbox.py): transport only.
Check: `python -m unittest tests.test_issue_webhook_transport -v` (stdlib).
Backend: Python 3.12+, operator-applied schema/dependencies. Optional disposable-DB check:
`python -m integrations.github_webhook.inbox --check-postgres`, with operator-provided
`WEBHOOK_TEST_DATABASE_URL`; not run. SQL fault/concurrency, deployment, independent
review and PR/main gates remain. Operator must schedule `Inbox.prune(now)` for
retention with offline consumers. Replay reads receipts; no requeue/native execution.
