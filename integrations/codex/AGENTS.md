# Codex working agreements

## Required Reslop verification after Superpowers

User decision, 2026-11-08: use Reslop globally for project verification after Superpowers.

- For coding tasks, complete the applicable Superpowers implementation, independent review and corrections, then perform the final change-appropriate project verification through Reslop before reporting completion or delivering the change.
- Use the project's real documented commands through `reslop t -- <program> [args]`, for example `reslop t -- python -m unittest discover -s tests -v` or `reslop t -- node --test`. Preserve the required test inventory, assertions, timeouts, fixtures, skips and exit codes. Use `reslop.cmd` if Windows PowerShell cannot execute the npm PowerShell shim.
- Plan the required final verification run through Reslop; do not repeat an already successful expensive full suite solely to change its output formatting. Intermediate TDD checks may keep their existing runners. Documentation-only changes need relevant documentation checks rather than unrelated runtime tests.
- Read the reduced report and inspect its referenced raw `.log/*.raw` output for failures, missing details or uncertainty. Retain the full output and any project-required source-bound receipts/capture. Keep generated logs local and out of commits.
- A nonzero exit, missing required evidence, skipped required execution or failed cleanup is not a pass. If Reslop itself is unavailable or broken, report that fact, preserve the required checks with the original runner, and do not claim the Reslop step passed.
- This is a noninteractive verification step. Do not implicitly start the Reslop TUI, an ACP agent, another task engine, a monitor or a background service. Preserve project task ownership, token-stripped child environments, independent review, CI and protected PR/main acceptance gates.


## User-selected Task Tower scheduling

User decision, 2026-11-09: when asked to connect a repository/project to Task Tower or manage tasks through its planner, use the existing Task Tower service and connector. Load `task-tower-client` from the personal skills directory (read its SKILL.md directly if this session's catalog predates it) before choosing execution/delegation tools. This applies from any repository, including Task Tower itself.

The requesting session prepares/submits work through the supported authenticated operator CLI. Task Tower owns admission, native claims, capacity and executor/reviewer lifecycle; Beads remains its canonical storage engine. Do not substitute a Task Tower chat, direct Beads claims, your own project subagents or manual implementation for the requested planner route. A managed worker performs only its assigned role and does not resubmit/redispatch its own task.

Verify the actual source, registered project and trusted connector binding. Missing/unavailable registration or service must be reported specifically; complete only authorized setup, without a silent fallback. Do not invent commands, scan private configs/DBs, expose tokens, or implicitly start/transfer/duplicate workers. Keep existing claims, WIP, unknown-effect fences and delivery policies. Manual internal maintenance/acceptance uses `task-tower-coordinate` only when that is the actual requested role. Existing explicitly chosen scheduler execution is not replaced by Superpowers' default subagent workflow.
