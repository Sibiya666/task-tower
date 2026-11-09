# Explicit native profiles and legacy event history

This is an operator-registered compatibility route, not discovery or migration.
A human-authorized disposable proof on 2026-11-09 verified the pinned Beads 1.0.2
route with Dolt 1.85.0. This evidence applies to a newly initialized isolated
database; it does not establish compatibility with an existing project database.

The optional service `native_profiles` maps registered project IDs to exact
`executable`, `sha256`, `version` and `history` values. An original binary, matching
`.beads/.local_version` and unchanged profile are checked before native effects.
The default global executable route remains available. Profiles are immutable
during live approval reload and bound to existing attempts by digest.

Supported explicit history values are `events-v1` for Beads 1.3.4,
`dolt-server-events-v1` for Beads 1.0.2, and `unavailable` (which refuses native
successful closure). Commit history is never relabelled as event history.

## Legacy reader boundary

Do **not** use `bd --readonly sql` as a migration-free reader. In Beads 1.0.2,
`sql` is absent from the read-only store allowlist; normal pre-run initialization
can run schema/credential/remote setup. A matching `.local_version` only prevents
the separate version-bump hook. See upstream [CLI initialization](https://github.com/gastownhall/beads/blob/v1.0.2/cmd/bd/main.go)
and [store initialization](https://github.com/gastownhall/beads/blob/v1.0.2/internal/storage/dolt/store.go).

The remote history profile additionally requires `history_reader` with an exact
Dolt 1.85.0 executable/hash, loopback host `127.0.0.1`, explicit port, database,
user, `password_file` (or null), native `project_id` UUID and `metadata_sha256`.
The registered regular `.beads/metadata.json` must match that complete byte hash
and explicitly specify matching server mode, host/port/database/user, project UUID
and disabled TLS. Beads 1.0.2 omits its false TLS bool when saving metadata; that
documented producer shape is accepted, while true or non-bool values are refused.
Missing/defaulted identity or connection fields, redirects and `.env` overrides fail
closed. No database copy, new binary over an old DB or automatic configuration
repair is performed. Other layouts need separate explicit registration.

Only the pinned Dolt CLI connects for event reads. Explicit `--host` selects its
remote path before any local engine; failed connections cannot fall back locally.
Its working directory and `DOLT_ROOT_PATH` are new private scratch directories.
Inherited database/Git overrides and GitHub tokens are removed. A protected
password file is read only by the host helper and passed in the child environment,
never arguments, model briefs or logs. See Dolt's [remote dispatch](https://github.com/dolthub/dolt/blob/v1.85.0/go/cmd/dolt/dolt.go),
[query execution](https://github.com/dolthub/dolt/blob/v1.85.0/go/cmd/dolt/commands/sqlserver/queryist_utils.go)
and [credential handling](https://github.com/dolthub/dolt/blob/v1.85.0/go/cmd/dolt/cli/credentials.go).
Only the scratch Dolt config disables metrics/version checks, with
`DOLT_DISABLE_EVENT_FLUSH=1`; no host-global settings are changed.

One source-defined SELECT checks native database metadata `_project_id` and reads
`events` or `wisp_events` according to actual `wisps` membership in the same query.
Only a strictly validated native bead ID enters the query. SQL, table names,
ordering and limits cannot come from configuration or task text. Native UUIDs,
actors, chronology and close reasons are retained; no event is invented.
The pinned Dolt JSON writer omits SQL NULL columns. Only nullable event values
and the identity row's fixed NULL placeholders may be absent; required event and
project identity fields remain mandatory. See the upstream [JSON writer](https://github.com/dolthub/dolt/blob/v1.85.0/go/libraries/doltcore/table/typed/json/writer.go).

More than 100 events, duplicate IDs, missing project identity, malformed output or
uncertain process cleanup fails closed. See the native [event routing](https://github.com/gastownhall/beads/blob/v1.0.2/internal/storage/issueops/events.go)
and [close event](https://github.com/gastownhall/beads/blob/v1.0.2/internal/storage/issueops/close.go).

The native 1.0.2 profile disables server autostart and pins its registered endpoint.
Server-backed recognized read commands avoid schema initialization; this claim
does not extend to embedded mode. Native writes still require normal explicit
ownership and authorization. Read commands may update local bookkeeping, so this
is a database-schema boundary rather than a promise of zero filesystem writes.

## Bounded compatibility evidence

The disposable proof exercised native create/claim/close, authentic ordinary-task
and active-wisp event readback, reader restart and source-identity guards. All 50
captured operations completed successfully. Working-root hashes matched across
history reads, the event scheduler remained OFF, and the owned server stopped
gracefully. A separate read against its verified stopped endpoint returned the
actual connection refusal and failed closed without local fallback; process and
scratch cleanup completed. These checks ran through noninteractive Reslop.

The active-wisp evidence covers history routing after a native direct claim; it
does not establish service admission of wisps. No existing project database was
opened or migrated, and no real popo compatibility or PR/main acceptance is
implied. Future probes still require a newly initialized disposable database,
the pinned legacy binary and an explicitly authorized isolated backend. Stop on
incompatibility; no fallback installation is authorized.
