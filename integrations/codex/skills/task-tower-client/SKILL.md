---
name: task-tower-client
description: Use when a user asks to connect any repository or project to Task Tower, manage its tasks through Task Tower, or use its planner (таск товер, планировщик), including from a session outside the Task Tower repository.
---

# Use the Task Tower planner

The requesting session is a client/operator of the existing Task Tower service and host connector. Beads/Dolt remains its canonical task/dependency/owner/history engine. The service/connector performs admission, native claims, capacity control, author/reviewer lifecycle and configured delivery. A chat named Task Tower is not this service.

## Choose the actual role

- **User asks to connect or manage a project through Task Tower:** use this client route. Do not substitute manual Beads execution, a new coordinator chat, your own project subagents, or writing the feature yourself while calling that Task Tower scheduling.
- **Already running as a Task Tower-managed author/reviewer:** carry out the one assigned role and scope. Keep its attempt/command identities and return the requested result. Do not republish or claim your own task, create another dispatcher, or replace the connector's executor/reviewer lifecycle.
- **User explicitly requests internal maintenance/manual acceptance of Task Tower:** use `task-tower-coordinate` for that scope. This is not the default interpretation of connecting a client repository.

## Establish the connection

Read the project's supplied Task Tower binding/operator instructions and the actual Task Tower checkout's `docs/project-intake.md` and `docs/runtime/headless-operation.md`. For known source locations and their limits see [host locators](references/host-locators.md).

Resolve the actual project ID, authorized connector-config locator and supported Task Tower client source. Preserve the project's own native executable/profile, repository/base and delivery policy. A source checkout, Beads database, display entry or another chat alone establishes none of these bindings. Do not scan private configs/databases, print credentials, guess an endpoint, or install/launch another service to fill a missing binding.

Use the existing authenticated operator CLI for a read-only connection check and published ready work:

```console
python -m task_tower.connector.cli ready --project-id <registered-project> --config <private-connector-config>
```

Run from the verified Task Tower source using the already installed explicit Python interpreter appropriate to the host. Config stays private; the CLI reads its credential locally. An authenticated successful empty array means no published ready tasks, not a running executor. If the binding, registration or service is missing, identify the specific missing item and complete only authorized setup. Report unconnected/unavailable honestly; do not continue through a substitute engine or request the token in chat.

## Submit work to its planner

For new tasks, prepare the bounded immutable plan and use **`plan import`**. For existing open, unassigned native tasks, use **`plan adopt`** with their exact native snapshot; authorized read-only source inspection is allowed to prepare it. Preserve IDs/history/parents/blockers and existing ownership. Do not directly create or claim replacement Beads tasks as the client's execution path.

Follow [operator submission](references/operator-submission.md) for the actual commands and publication boundary. Use the exact operator-approved digest; a hash or model-generated approval is not authority. Reuse existing authorization instead of asking for it again. Return the actual publication `request_id`, `project_id`, `digest`, `state` and exit outcome.

Execution also needs an authorized connector assignment with exact `base_sha`. The already started connector admits published, native-ready work itself. The requesting session does not call `bd claim`, start author/reviewer subagents, invoke model turns, or build a second queue to advance it. If no connector is running, report that gap and use the documented explicit-start procedure only when authorized; never duplicate an old worker or auto-install a daemon.

Observe decisions and attempt progress through supported operator/API receipts. `decision respond` is an explicit, request-bound decision, not blanket permission. Never invent a `status`/`connect`/`register` CLI command or infer execution from `ready`/publication alone. An unavailable observation remains unknown; preserve journals and reconciliation fences.

## Report facts at the right boundary

Report connection, publication, execution and delivery separately: verified project binding/readiness; actual published batch; actual connector-owned attempt/claim if observed; saved result and delivery evidence. Chat messages, local plans, a subagent result and source `closed` do not prove scheduler execution or acceptance.

Preserve the configured policy: Task Tower protected-main gates, owner-only PR at its exact base, or reviewed local handoff. Do not merge owner-only PRs or label local/PR handoff accepted/done. Keep Superpowers and change-appropriate final Reslop verification within the actual assigned work; neither replaces Task Tower scheduling. Preserve unknown effects, active claims and user WIP rather than transferring existing work into a new attempt.
