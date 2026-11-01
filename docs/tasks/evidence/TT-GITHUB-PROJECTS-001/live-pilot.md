# Live GitHub pilot

2026-11-01. Implemented CLI used with installation-owned connections at `../runtime/github-projects/connections.json`; the product repository contains no user project list or credentials.

- Existing GitHub credentials resolved at runtime. Read-only fresh library smoke returned 41 commit-pinned Markdown entries and zero source errors.
- Explicit import of `docs/tasks/TT-GITHUB-PROJECTS-001.json` created [Task Tower Issue 9](https://github.com/Sibiya666/task-tower/issues/9).
- Repeating the exact import returned Issue 9 again, without creating another Issue.
- Fresh HTML aggregation after import returned exit 0 and rendered 42 source-linked entries (one Issue and 41 Markdown files). Snapshot stored outside the product checkout at `../runtime/github-projects/books-verified.html`.
- No workflow template was enabled, no runner registered and no Project board permissions/mutation verified. Distributed receipt reuse and Project projection are fixture-tested; these are not claims of physical multi-machine execution.
- Feature is not in main; postmerge acceptance remains pending. Existing local postmerge watcher was left intact; it has not been silently switched to remote mode.
