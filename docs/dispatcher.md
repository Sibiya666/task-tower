# Foreground Issue dispatcher

The dispatcher selects explicitly allowlisted ready GitHub tasks and delivers only their identities to a trusted installation adapter. It does not run development, mark tasks complete, change GitHub, select models, install tools or register services. #24 is complete; #14 remains current through exact-main acceptance and automatic closure; #15 is next.

Run `python -m task_tower dispatcher --connections PATH --config PATH --journal PATH --once`. Omit `--once` for foreground polling (Ctrl-C exits cleanly). `--status` reads local journal state without GitHub or adapter calls. `--dry-run` reads GitHub and plans work without creating directories, journal files or adapter processes. Status and dry-run are mutually exclusive.

Keep all three paths outside connected checkouts, distinct from one another and SQLite sidecars, without symlink/junction or hard-link aliases. Example private configuration (replace paths with existing absolute installation paths):

```json
{
  "version": 1,
  "allowlist": [{"repository": "owner/repository", "issue": 42, "task_id": "TT-EXAMPLE-001"}],
  "backend": {
    "argv": ["/absolute/python", "/absolute/trusted_adapter.py", "{request}", "{result}"],
    "cwd": "/absolute/installation",
    "timeout_seconds": 60
  },
  "interval_seconds": 60
}
```

Windows installations use absolute Windows paths and JSON backslash escaping. Empty allowlist or missing backend disables delivery with exit 0 and no GitHub/adapter calls. Interval is an integer 5–3600; backend timeout is 1–300. Only trusted `{request}`, `{result}` and `{checkout}` argv placeholders are supported. Checkout substitution is the configured backend working directory, never Issue content. No shell is invoked.

The adapter receives a managed request JSON containing exactly operation (`submit` or `lookup`), delivery_id, repository, issue, task_id and runner_label. It writes result JSON with exactly version 1, matching delivery_id and status (`accepted`, `unknown`, or lookup-only `not_found`); accepted additionally requires an ASCII receipt_id token of 1–256 characters from letters, digits and `._:-`. Lookup is a trusted read-only operation and must never create work. Raw process output and receipt text are never public report data.

Preserve the private SQLite journal and use the same canonical path across local dispatcher processes. A committed unknown intent permanently forbids another submit, including crashes before launch, timeout, not_found and changed configuration. Accepted rows never invoke the adapter again. Unknown lookup requires the original allowlist identity, matching backend fingerprint and healthy current task identity; revocation prevents calls even if the task was previously ready. Operator reconciliation is outside this release. Losing or changing the journal forfeits deduplication. Separate journal copies and other machines have no shared lock.

Each tick permits up to eight new submits and eight unknown lookups. New work follows priority/repository/Issue ordering; unknown lookups use a durable round-robin cursor. These limits are per process and per tick, not execution capacity or distributed scheduling. Dependencies require fresh verified completion; closed Issues and edited body claims are insufficient. Fresh per-send revalidation checks lifecycle, metadata and dependencies again. Connections and config reload every tick and are compared before adapter calls. GitHub edits or private revocation after the final check remain a best-effort non-atomic race.

Reports contain sanitized identities and fixed reason codes. Exit 0 means a completed report (ordinary not-ready, disabled and deferred work included), 1 means source/backend/journal operational failure or unresolved outcomes, and 2 means invalid CLI/configuration. The foreground loop continues per-project source errors; invalid global configuration or journal integrity stops it. Delivery acceptance is only adapter acknowledgment, never independent development or postmerge acceptance.

Active-chat authorization continues to the next eligible task after each main/postmerge/Issue-closure cycle without another continue. Foreground polling and that chat authorization are separate from future development execution and daemon orchestration.
