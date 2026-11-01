# Overlay integration

User approved combining the working desktop overlay and Task Tower CLI in this repository. Reuse this existing checkout: it contains uncommitted work that must be preserved, and a fresh worktree would omit it.

1. Copy the existing overlay source, web assets, preparation tools, tests and licensed vendor files into `overlay/`. Keep runtime data ignored; preserve learned project assignments locally. Retain old launch paths as forwarding scripts after validation.
2. Preserve the current readiness CLI documentation in `docs/readiness.md`. Write a unified README, architecture and developer guidance; distinguish implemented monitoring/audit from planned orchestration.
3. Use the three real screenshots supplied by the user during integration. Preserve originals, label imagegen background cleanup, normalize transparent exports to a shared proportional canvas and document provenance. No additional capture mode or synthetic data is required.
4. Run CLI unittest discovery, overlay collector tests, browser tests and native smoke/capture from the new location. Inspect screenshots. Update the desktop shortcut and verify its target.
5. Document verification and repository status. Do not commit, push, or include runtime snapshots, browser profiles or session logs.
