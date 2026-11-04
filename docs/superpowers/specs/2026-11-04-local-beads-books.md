# Local Beads Books source

User decision: one Windows machine, local embedded Beads; Tasks and chronology in Task Tower Books come from it. Do not develop the old execution conveyor. No VPS, sync, migration or execution scheduling in this change.

Installation-owned TASK_TOWER_BEADS points to a private version1 config with absolute executable and a projects list (id, repository, directory). Project IDs and repository-qualified bead IDs are stable; do not manufacture GitHub Issue numbers/URLs. All commands are fixed readonly/sandbox Beads reads, bounded by time/output/count. Reject unsafe config paths, duplicate scopes and malformed responses; expose only fixed error messages. No CLI/settings/path data crosses into WebView.

The existing helper/native bridge/view accept a separately allowlisted Beads entry kind with source null and explicit bead_id. Render title, status, assignee, epic/subtask relationships, dependencies and per-card chronological events from the local journal. Preserve closed as source state, never grant verified code/main acceptance. Missing/pruned/disabled journal yields visible partial history, not an invented complete timeline. Limit historical events visibly. Failed refresh retains existing stale handling.

For repositories configured in Beads, use its tasks instead of querying duplicate GitHub Issues; other GitHub project sources remain unchanged. Local configuration is opt-in and does not change executor/dispatcher/GitHub provenance. Unrelated GitHub project books remain configured as before. This first local source supplies tasks/history only; local ideas/library scanning and local file opening are not added.

Verify projection/error/privacy/readonly tests, actual portable1.3.4 database, browser normalization/rendering and compiled native source boundary, then independent source review and Windows integration gates. Update setup README/AGENTS; configure and demonstrate the real local Books path without replacing user launch settings silently.
