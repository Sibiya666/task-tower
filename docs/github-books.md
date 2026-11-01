# Project connections and books

## Target bookshelf hierarchy

The shelf keeps three books, each scoped or filtered by project:

- **Ideas** contains proposals before commitment. Promoting an idea links it to its resulting feature or task; the original idea remains traceable.
- **Tasks** contains implementation milestones, large features represented by parent Issues, and their native GitHub sub-issues. An Issue may also represent a bug, research or documentation work. A milestone groups work toward a release or stage; it is not a feature or an Issue parent. A feature may span milestones, so grouping by stage must retain its parent link rather than invent a second parent or duplicate task.
- **Project library** contains specs, research, designs, decisions and acceptance reports linked to the relevant feature, task and implementation stage. Markdown in the repository remains the content source.

Books are containers and projections of these concepts, not separate copies of GitHub records. Native Issue parent/sub-issue relationships supply the feature tree; milestone membership supplies the implementation-stage view; Project supplies the board. Retain repository-qualified identities and source links at every level. Unassigned tasks remain visible, and unavailable relationships must be shown as unavailable rather than inferred from titles or silently treated as absent.

Feature progress shows accepted child work separately from merged or merely closed Issues. A parent is not automatically accepted because its children are closed: its own acceptance criteria and exact-main postmerge acceptance still apply. Completed work and its artifacts remain accessible.

The overlay implements this hierarchy through its Books dialog. The standalone CLI/HTML renderer retains its flat snapshot with project/book filters and three entries per page. Native, browser and source-proof acceptance are separate gates; see the Issue #23 evidence before treating the feature as accepted in main.

Connections belong to the installation, outside the product checkout (or inside ignored `runtime/`). They contain no credentials. Commands require an explicit path and never save your list in the product source by default. Checkout paths must be existing absolute directories. IDs and repositories are unique; GitHub Project URLs are optional.

```powershell
python -m task_tower connections --config C:/TaskTower/connections.json init
python -m task_tower connections --config C:/TaskTower/connections.json add --id sample --repository example/sample --checkout C:/work/sample --runner-label sample-runner --project-url https://github.com/users/example/projects/1
python -m task_tower connections --config C:/TaskTower/connections.json list
python -m task_tower connections --config C:/TaskTower/connections.json remove sample
```

Use `GH_TOKEN`, `GITHUB_TOKEN`, existing `gh auth token`, or Git credential-manager authentication at runtime. Credentials are never included in books or configuration. Private repositories require suitable existing read access; import requires Issues write access. Board projection additionally requires Projects access; see [queue setup](github-projects.md).

```powershell
python -m task_tower books --connections C:/TaskTower/connections.json
python -m task_tower books --connections C:/TaskTower/connections.json --format html --output C:/TaskTower/books.html
python -m task_tower books --connections C:/TaskTower/connections.json --project sample --book tasks
python -m task_tower books --connections C:/TaskTower/connections.json --project sample --import-card C:/work/sample/docs/tasks/OLD-1.json
```

The standalone HTML opens locally, filters projects and books, and displays three entries per page. A timestamp identifies the saved snapshot; rerun the command to refresh it. JSON returns entries and visible source errors. Exit status 1 means partial/unavailable sources, 2 means invalid configuration or operation. Errors never include raw transport exceptions or credentials.

Output files are created without replacing existing files. Add `--overwrite` explicitly when refreshing a generated report. Configuration and import-source aliases (including hardlinks), symbolic links, and project source targets are always rejected. Inside connected checkouts, generated reports must live under `runtime/` or `.task-tower/`; reports elsewhere may use any filename. Writes publish atomically and do not truncate linked files.

Issues without Task Tower metadata remain ordinary tasks. An explicit `kind: idea` metadata record selects the ideas book. Pull requests are excluded. Identity includes repository and Issue number, so matching numbers in different projects never collide. The library links Markdown files at the fetched commit, and rejects truncated trees instead of presenting an incomplete tree as complete. Issue pagination is bounded at 20 pages of 100; responses are bounded at 2 MiB and requests time out after 30 seconds.

Task metadata is a versioned JSON block delimited by `<!-- task-tower:v1` and `-->`. Updating a block preserves surrounding prose. Duplicate/invalid blocks fail visibly. Imported local cards retain their legacy ID and historical evidence; repeat imports find the same Issue. Imports do not overwrite local cards or existing Issues. Unverifiable completion becomes `needs_input`. Serialize import operations per project: GitHub Issue creation has no transactional idempotency key, so simultaneous first imports are not an atomic lock.

Closed Issues never imply acceptance. Body metadata alone never proves `done`: books require fresh independently verified remote completion evidence through the project worker verifier. Unavailable or rejected evidence stays `needs_input` with an explicit source error. See [the approved architecture](superpowers/specs/2026-11-01-github-projects-design.md) for acceptance requirements.

Managed task lifecycle updates are read from bounded append-only Task Tower Issue comments. These updates preserve Issue body prose; a comment claiming completion still requires the independent remote completion proof.

For explicit, retryable GitHub Project board projection and trusted status-field mapping, see [board configuration](github-board.md).

Explicit session capture, same-Issue promotion and provenance-only legacy migration are documented in [session capture](session-capture.md). Migration retains active card bytes and historical worker evidence; GitHub remains editable task truth. Books attach migration hash/status to the canonical Issue without exposing private source paths or creating duplicate tasks. Changed local bytes are shown as stale provenance, never silently synchronized. The flat renderer exposes session/native relationship links; the overlay adds expandable hierarchy.

## Overlay setup and refresh

Create the private connections file using the commands above, then set its absolute path in the environment of the overlay launcher:

```powershell
$env:TASK_TOWER_CONNECTIONS = 'C:/TaskTower/connections.json'
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay/overlay.ps1
```

Use the scene context menu's «Книги проекта» action or Ctrl+B, including the physical B key under a Russian layout. Escape closes details before the dialog. Books share the existing window and preserve its placement and session activity. The project filter uses explicit connection identities rather than guessing a connection from a tower title.

First opening starts one refresh; explicit Refresh starts another after the previous attempt ends. There is no background Books polling. Known Issue identities and repository artifacts render before fresh completion verification. Pending verification cannot display accepted completion. A new attempt invalidates previous proof claims; successful final output and process exit are required before advancing the last-success time. The 120-second deadline retains valid partial data as interrupted/stale. Snapshots become stale after 300 seconds, and failed refreshes mark them stale immediately. Missing fields, unavailable relationships and truncated lists are visibly distinct from empty values.

Public snapshot limits are 8 MiB and 10,000 entries per frame, 64 MiB and 32 frames per attempt. Bodies are limited to 32 KiB; phase/blocker labels to 256 characters; blocker/result/history arrays to 100 items. Fixed diagnostics indicate limits without exposing private configuration, paths, credentials or transport exceptions.

Only the native host opens source links. It permits the configured GitHub repositories' Issue, PR and milestone URLs, immutable 40-hex-commit Markdown blob URLs, and each exact configured Project URL. Queries, fragments, user information, lookalike hosts, foreign repositories and arbitrary session URLs are rejected. Markdown and Issue text are displayed as text; the WebView does not fetch GitHub data or execute source content.

## Explicit artifact versions

An optional repository file `docs/task-tower-library.json` declares artifact versions. It is bounded to 256 KiB and 1,000 entries and has this schema:

```json
{"version":1,"artifacts":[{"path":"docs/specs/example.md","commit":"0123456789abcdef0123456789abcdef01234567","state":"working","issues":["example/sample#1"],"milestone":{"repository":"example/sample","number":1}}]}
```

Use only the exact schema accepted by `task_tower/book_library.py`; unavailable blobs and invalid declarations produce visible diagnostics. States `working`, `accepted` and `superseded` are explicitly labeled declared states. They do not grant task acceptance. Unindexed Markdown remains visible with unknown state. Version identity includes repository, path and immutable commit, so historical versions remain separate and traceable. Associations must refer to explicitly connected repositories; names never imply a task or milestone link.
