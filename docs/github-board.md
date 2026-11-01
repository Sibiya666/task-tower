# Project board projection

Each repository uses its own pre-existing GitHub Project. Connections belong to the installation; Task Tower does not create a shared product board for other projects. Obtain the board and Status field node IDs and single-select option IDs through GitHub's [Projects GraphQL API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).

Add an optional `board` object to the corresponding private connection:

```json
{
  "project_id": "PVT_REPLACE",
  "status_field_id": "PVTSSF_REPLACE",
  "status_options": {
    "open": "OPTION_TODO",
    "in_progress": "OPTION_ACTIVE",
    "awaiting_merge": "OPTION_REVIEW",
    "awaiting_postmerge": "OPTION_REVIEW",
    "postmerge_review": "OPTION_REVIEW",
    "postmerge_failed": "OPTION_ATTENTION",
    "needs_input": "OPTION_ATTENTION",
    "done": "OPTION_DONE"
  }
}
```

These are placeholders, not actual GitHub IDs. Configure a mapping for every lifecycle status used by the project. Board access requires existing credentials with suitable Projects permissions in addition to repository access. A URL alone does not grant permissions or configure synchronization.

```sh
python -m task_tower.projects_board --config /private/connections.json --project sample --issue 12
```

This explicit operation adds the Issue to its configured board and updates the mapped Status field. GitHub returns the existing item when membership already exists, so retrying after a partial failure is safe. Issues and the append-only workflow lifecycle are authoritative; the board is a projection. Unconfigured boards return `not_configured`, mapping failures reject the operation and API/permission failures return `unavailable` with a nonzero exit. No credentials or raw API error bodies are printed.

The CLI reads workflow lifecycle comments and verifies remote acceptance evidence before projecting Done. While the acceptance workflow is still running, or when its receipt has expired, completion remains unverified. Run synchronization again after the workflow completes. Continuous board synchronization and automatic board creation are not installed by this command.
