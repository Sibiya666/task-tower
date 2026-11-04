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
