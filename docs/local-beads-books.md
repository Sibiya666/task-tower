# Local Beads in Task Tower Books (Windows)

Books can read tasks and chronological changes from one local embedded Beads database. This is a read-only source adapter: it does not start agents, close tasks, install Beads, migrate GitHub Issues or sync databases.

Install/verify the official Windows bd.exe separately, then initialize the project with embedded `bd init`. Enable the journal **before** work you want in the chronology: `bd config set events-journal true`. Beads does not backfill earlier events. Keep its active Dolt branch stable; journal records are branch/clone-local and have retention. Missing, pruned, disabled, malformed or over-limit history is shown as partial; tasks can still be read. The reader checks journal enablement, sequence coverage, creation records and whether the latest recorded task fields match the current list snapshot. These are source-observation checks, not independent process or acceptance evidence.

Create a private JSON file outside source control:

```json
{
  "version": 1,
  "executable": "C:/Tools/beads/bd.exe",
  "projects": [
    {
      "id": "my-project",
      "repository": "owner/repository",
      "directory": "C:/Projects/my-project"
    }
  ]
}
```

Paths must be absolute, without symlinks/junctions. `repository` is the project identity namespace, not a requirement to contact GitHub. Each configured local repository appears once. The adapter verifies embedded Dolt metadata before commands and uses bounded `bd --readonly --sandbox --json list --all` and `bd --readonly --sandbox --json events export`, with a read-only `config get events-journal` availability check. JSONL exports are not used as canonical storage. No third-party Python dependency is added; Beads is an external opt-in executable.

Launch the overlay from a PowerShell session with the installation-owned config:

```powershell
$env:TASK_TOWER_BEADS = 'C:/Private/task-tower-beads.json'
& ./overlay/overlay.ps1
```

Open Books with Ctrl+B. Tasks show their original bead identity, assignee, status, epic/subtask relationships and blockers; details contain **Хронология Beads** with time, actor, operation and source state. Local entries do not fabricate GitHub URLs and expose no executable/database paths to WebView. No local file/executable open action is added. A closed bead is a source state, not independent proof of code/CI/main acceptance.

`TASK_TOWER_CONNECTIONS` can remain configured for other repositories. For repositories selected in TASK_TOWER_BEADS, Books uses Beads instead of duplicate GitHub task queries. Existing GitHub source permissions, local journals, claims and old task provenance are not migrated or modified. Other repositories retain their existing GitHub books. For a Beads-selected repository this first adapter supplies tasks and per-task chronology only; local Markdown ideas/library scanning is not added here.

Bounds: 16 configured projects, one 25-second read budget, 1000 tasks/project, 5000 journal events/project and 100 events/card, with fixed public partial/unavailable errors rather than raw backend errors. A later VPS/HTTP or multi-machine deployment needs separate configuration and qualification.

## Public result record

A Beads task can carry one deliberately public, strictly typed result block in its
canonical `notes`. Other notes remain private; there is no free-text notes export.
Use exactly these standalone marker lines (LF or CRLF):

```text
TASK_TOWER_PUBLIC_RESULT_V1_BEGIN
{"version":1,"pr":123,"main_sha":"0123456789abcdef0123456789abcdef01234567"}
TASK_TOWER_PUBLIC_RESULT_V1_END
```

The example is a format illustration, not a real delivery. `version` must be the
integer 1, `pr` an integer from 1 through 9007199254740991, and `main_sha` exactly
40 lowercase hexadecimal characters. No other keys, URLs, paths, verdicts or
arbitrary strings are accepted. The raw enclosed JSON, including its trailing
line ending, is limited to 4096 UTF-8 bytes and never truncated into validity.
Duplicate JSON keys, invalid types, nonstandard constants, malformed/multiple
marker blocks and oversize input produce **Недоступно**. Without standalone
marker lines Books shows **Не записано**; marker-like prose is not a block.

Details label the record **Сведения Beads** and explicitly say it does not confirm
acceptance. Only two links are derived: `https://github.com/OWNER/REPO/pull/PR`
and `https://github.com/OWNER/REPO/blob/MAIN_SHA/docs/beads-results/BEAD.md`.
The repository and bead come from the existing scoped identity, with the same
native/UI source validators. There is no new Actions, local file or executable
navigation. The public receipt must exist at that exact source commit; a record
does not verify the target's existence, authenticity, contents or CI by itself.

The Python public envelope, native bridge and browser policy validate the exact
nested field. Unknown keys invalidate a record rather than being silently copied.
Source `closed` and `verification: not_required` remain unchanged; a result record
does not create accepted progress. Chronology consistency compares the projected
public record in the current task and last journal snapshot. A mismatch keeps
the task and result visible but marks chronology partial. Unrelated private notes
changes that leave this projection equal do not change chronology coverage.

For a delivery, the coordinator records only the genuine PR/main identifiers after
the project's actual independent PR/main and CI gates. A receipt prepared before
merge states only facts already known at its commit. Real Books observation is
still required for product acceptance; fixtures and source reviews do not prove it.
