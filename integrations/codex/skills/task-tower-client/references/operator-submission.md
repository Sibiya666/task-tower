# Supported operator submission

Read the actual source documentation first. These are existing interfaces, not a new client API or approval mechanism. Replace placeholders with verified values and quote paths; use the host's explicit installed Python, with the verified Task Tower checkout as working directory. Keep token contents and full private configs out of prompts/output.

## New native tasks

Prepare strict UTF-8 JSON without BOM, duplicate keys or nonfinite values: a `tasks` array with `id`, `title`, `description`, `depends_on`. Existing size/body bounds apply (64 KiB maximum). Compute canonical SHA256 with `task_tower.service.store.plan_digest(plan)`, not the hash of pretty-printed bytes.

The trusted service operator reviews the exact plan and authorizes its digest in `approved_plans[project]`. Neither the plan file nor `--digest` grants this approval. Reuse an existing exact approval; if it is absent, prepare the concrete plan for the authorized operator rather than manufacturing the allowlist from model output.

```console
python -m task_tower.connector.cli plan import --project-id <project> --request-id <stable-request-id> --digest <approved-sha256> --plan-file <approved-plan.json> --config <private-connector-config>
```

## Existing native tasks

Follow `docs/project-intake.md`: exact native snapshot including `parents`, closed-external-blocker readbacks and ownership/drift fences, at most 32 intended tasks. Do not adopt existing owned/in-progress work or make parent containers executable merely by reference.

```console
python -m task_tower.connector.cli plan adopt --project-id <project> --request-id <stable-request-id> --digest <approved-sha256> --plan-file <exact-native-snapshot.json> --config <private-connector-config>
python -m task_tower.connector.cli ready --project-id <project> --config <private-connector-config>
```

Publication succeeds only with actual exit 0 and returned `state: "published"`. It does not launch a model. Reuse the same request ID and unchanged digest for a lost response; `needs_reconciliation`/unknown effects require reconciliation, not a fresh ID to replay them.

## Planner admission

Under existing operator authority, publish an append-only connector assignment with `project_id`, `bead_id`, exact 40-character `base_sha`, and `input: {"text": "<instruction>"}`. Both service and connector must already allow the project and exact delivery policy. Write only the explicitly registered private config atomically; do not discover or modify arbitrary configs. Existing approval/assignment additions reload; trusted scope/roots/executables/credentials/policy changes need the documented controlled procedure. Do not silently expand them.

An already explicitly started `task_tower.connector.cli work` owns native claim/readback and author/reviewer launch. There is no per-task manual model start. `work` is a foreground execution command, not a connection probe; `run` is a legacy execution command, not a setup shortcut. Do not start either just to inspect readiness or because the desired worker is unobserved. If authorized startup is necessary, follow the procedure once, retain its owned handle and stop/unknown boundaries; never restart solely after an observation timeout.

Use existing `decision list`, explicit request-bound `decision respond`, and authenticated attempt/command receipts from the existing operator surface. The API supports `GET /v1/attempts/<attempt_id>` for an actual known connector-owned attempt; the current CLI has no generic `status`, `connect` or `register` command. Missing access or identity is a concrete gap, not permission for journal/DB scanning or invented status.

Readiness, publication, running attempt, reviewed handoff and accepted delivery are separate results. For protected-main work retain independent exact-H/B approval, genuine required status/current CI/protected merge, exact-main CI and independent main acceptance before canonical owner closure. Apply other projects' configured owner-only/local boundaries without borrowing Task Tower's merge authority.
