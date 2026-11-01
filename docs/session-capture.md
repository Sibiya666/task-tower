# Explicit session capture and legacy migration

Capture is explicitly invoked by a person or trusted custom harness against one selected connected project. First complete authenticated writable Project setup and Status mapping with `python -m task_tower connect`; see [setup](github-setup.md). A URL, capture intent, Issue body or session reference does not grant private execution authority or prove dependency readiness. This feature does not scan chats, install hooks, execute tasks or provide background capture.

## Submit and retry

Create one UTF-8 JSON envelope, no larger than 64 KiB:

```json
{
  "version": 1,
  "event_id": "6aa7d25d-a15d-418d-a513-7bbbde53dfe3",
  "kind": "idea",
  "title": "Show source links",
  "original_text": "Keep the selected original text exactly.",
  "session": {"provider": "custom-harness", "id": "session-42"},
  "intent": "record"
}
```

```powershell
python -m task_tower capture --connections C:/TaskTower/connections.json --project sample submit --input C:/TaskTower/capture.json
python -m task_tower capture --connections C:/TaskTower/connections.json --project sample promote --issue 42
python -m task_tower capture --connections C:/TaskTower/connections.json --project sample migrate --card C:/work/sample/docs/tasks/OLD-1.json
```

Use `--input -` only for deliberately supplied stdin. Original text must be nonempty and at most 32 KiB UTF-8; title is 1–256 characters, session provider/id each at most 128 characters. Optional session URLs must be HTTPS, at most 2048 characters, without userinfo, control characters or backslashes. Unknown fields, wrong types, embedded NULs and invalid UTF-8 fail before mutation. Links are inert provenance and are never fetched. Original text and session values use lossless, versioned, marker-inert metadata encoding; their contents never become lifecycle or queue instructions.

Optional `relations` accepts `parent` and `sub_issues` using `owner/repo#N`, `milestone` using `{"repository":"owner/repo","number":1}`, and a `sources` list of safe HTTPS URLs. Mutation currently requires the selected connected repository; another repository requires an explicitly authorized connected workflow. Parent/sub-issues use native GitHub relationships. A milestone is separate release/stage membership. Relationships and session links appear in books data and safe links; [Issue #23](https://github.com/Sibiya666/task-tower/issues/23) owns actual expandable hierarchy rendering.

Keep the same event UUID and exact payload for every delivery retry. Identity is scoped by immutable repository identity and provider. A changed payload for that event conflicts; identical text with a different event UUID is a separate capture. Never generate a replacement UUID to recover an unknown POST outcome. A committed private creation intent prevents blind replay. Retry can find the unique existing Issue and repair Project membership; absent, ambiguous, conflicting or deleted remote identities require inspection. Do not delete private intents to permit another creation. Serialize initial creation per project across installations: the local journal is not a distributed lock.

Promotion changes the existing Idea Issue into a task and preserves original provenance, prose and native relationships. Cooperating local promotions serialize and recheck a fresh body. External editors must serialize promotion too: the final GET/PATCH interval is not protected by server-enforced body CAS. `execute_requested` records a request only; the separate readiness and private authorization gates still apply.

## Explicit custom harness API

A user-installed trusted adapter may call the same bounded API:

```python
from task_tower.capture import capture, promote, validate_capture
from task_tower.capture_migration import migrate_card, migration_state
from task_tower.project_connections import load_connections

connection = next(c for c in load_connections(config_path) if c.id == project_id)
result = capture(connection, validate_capture(envelope))
```

The adapter supplies selected text and session context only. It preserves event IDs across retries and presents `needs_input` plus `source_errors` to the operator. Results identify canonical `issue_url` and `number` when known. No installer, permission grants, credential storage or executor callbacks are included. CLI exit status is 0 for success, 1 for recoverable `needs_input`, and 2 for invalid/unavailable operation; diagnostics omit raw input and transport exceptions.

## Legacy compatibility and private registry

`migrate_card(connection, path, *, store=None)` validates a regular UTF-8 JSON card (maximum 1 MiB) and uses a private temporary snapshot of its exact bytes with the unchanged `GitHubTasks.import_card(path)` API. It checks original descriptor/path identity and raw SHA-256 before import and before registry publication. Symlinks, junctions, hardlinks, known private state and connection-file aliases are rejected. The active card is never overwritten, archived, renamed or deleted. Old import commands remain available.

The original card remains a compatibility input/evidence artifact for active controllers, `tasks.load_task`, publishers and postmerge snapshots. Their original byte hashes and historical evidence are retained. Migration never regenerates old hashes or interprets historical acceptance as current remote completion. Books still use the existing independently verified completion proof; a closed Issue or body assertion is insufficient.

Ignored `.task-tower/capture-migrations.json` is a version-1 provenance registry. Each record contains repository and immutable repository ID, legacy ID, absolute original source path, raw source SHA-256, canonical Issue number/URL and registration timestamp. Number/URL are null while registration is pending. It contains no editable task state, card copy, tokens or session payloads. Source paths stay private and are excluded from books output. The temporary snapshot path is never submitted as original provenance. GitHub remains editable task truth.

Cooperating local processes hold a SQLite registry lock across migration. Publication uses a same-directory temporary file, byte/identity CAS rechecks and atomic replacement (no-clobber initial publication). Durable pending provenance binds the original source digest before remote import, so interrupted publication can safely retry through the existing creation journal. Detected registry replacement or source mutation after creation returns the existing Issue URL with a recoverable conflict; it never overwrites the changed target. These protections detect observed races and are not an arbitrary hostile-filesystem or cross-host sandbox.

`migration_state(connection, path)` reports `unmapped`, `pending`, `current` or `stale`. Books attach public hash/status provenance to the canonical Issue once and show stale/pending source errors. Changed source bytes or conflicting same-ID cards cannot silently re-import or overwrite GitHub. Restore and inspect the original input and existing identity before retrying; a different desired payload needs an explicitly reviewed reconciliation outside this migration command. Never delete registry/journal records to force replay.

Keep connections, creation journals, registry/locks and runtime inputs private and out of source control. A registry is not an alternate task database and should not be hand-edited to change task status. Preserve existing active-card controllers; migration adds no blanket ban on their writes, and later changes become visible source drift.

## Task completion and merge identity

For a managed implementation PR, include the exact standalone task marker (for this capture implementation, `Task-Tower: TT-CAPTURE-001`) before merge. Check it against the installation-owned Issue/task mapping and record it with head/base acceptance. Capture provenance and a green CI result do not supply this merge-event identity.

PR37 initially omitted the marker; its genuine successful Actions bundles were unbound (`task_ids: []`). A rerun retained the original payload. The same Issue22 remains open until a reviewed correctly marked follow-up emits a genuine new event and the independent postmerge publisher closes it. Preserve this refusal/reconciliation history; see [recovery process](development-process.md#missing-merge-event-identity-recovery). No manual Issue closure or fabricated receipt is a substitute.
