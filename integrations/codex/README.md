# Task Tower instructions for Codex sessions

This package teaches existing and new Codex sessions to use the Task Tower planner when the user selects it. It contains instructions and two personal skills; installing them does not register a project, publish tasks or start a service/worker.

## Contents

- [AGENTS.md](AGENTS.md): reusable session rules, including the user-selected Task Tower route and final verification through Reslop.
- [task-tower-client](skills/task-tower-client/SKILL.md): the normal route for connecting any repository or managing its tasks through the existing service/connector.
- [task-tower-coordinate](skills/task-tower-coordinate/SKILL.md): explicitly requested Task Tower internal maintenance and independent protected PR/main acceptance.

## Install on the actual host

After the user asks to apply this package:

1. Read this package at the intended branch/commit. Keep the current project checkout and its WIP intact; do not merge the package branch or change another project's branch merely to read it.
2. Locate the current Codex profile (`CODEX_HOME`, or the default `~/.codex`). Compare existing instructions and skill directories before changing them. Preserve unrelated rules, approvals, credentials and local adaptations.
3. Copy the two exact directories under `skills/` into that profile's personal `skills/` directory. If a same-named skill already exists, review and merge its relevant differences; do not silently replace unrelated local changes. Keep each skill's `agents/` and `references/` files with it.
4. Merge the rules in this package's `AGENTS.md` into the effective global instructions file. Preserve existing rules and account for an existing `AGENTS.override.md`; do not create a new override to hide other instructions. Ensure there is one clear client route rather than competing duplicate sections.
5. New sessions load the updated guidance when they start. For an already open session, explicitly ask it to reread the effective global instructions and the installed `task-tower-client/SKILL.md`. If its skill catalog is older, it can read that file directly. Do not restart or transfer active task workers just to refresh instructions.

The files are host-neutral. No private endpoint, native database, token, account setting or developer checkout path is bundled. Actual source/config locators must come from the authorized operator on the receiving host.

## What correct use looks like

The requesting session prepares/submits work through the supported authenticated operator CLI. Task Tower owns admission, native claim/readback, capacity and author/reviewer lifecycle; Beads/Dolt remains its canonical engine. A Task Tower chat, direct Beads claims or the session's own project subagents do not demonstrate planner use.

Validate the supplied binding with actual `ready` output. For new tasks use `plan import`; for eligible existing native tasks use `plan adopt`, with the exact operator-approved digest and a stable request ID. Execution also needs the authorized connector assignment; publication alone does not start a model. See [project intake](../../docs/project-intake.md) and [operation](../../docs/runtime/headless-operation.md).

Preserve each project's delivery policy: protected-main Task Tower delivery, an owner-only PR at its configured base, or local reviewed handoff. Do not replace a managed worker's assigned role with another dispatcher. Missing service/binding means a concrete connection gap, not permission to fall back to manual project execution or create another worker.

## Prompt for an already open session

> Read `integrations/codex/README.md` and its linked instructions/skills from the branch I supplied. Apply the package to your actual Codex profile while preserving existing rules and local changes. For this project's Task Tower work, use the real service/connector operator route. Report actual connection evidence and any published batch/connector-owned attempt; do not use a Task Tower chat, direct Beads claims or your own project agents as a substitute. Keep existing processes/claims/WIP intact and report missing binding/access precisely. Do not merge the package branch or start services merely to apply instructions.

An acknowledgment proves only that the instructions were read. Verification of planner use requires actual authenticated command outcomes, published batch identities and connector-owned attempt/claim evidence when execution is authorized. If execution is unobserved, report it as unconfirmed. Never expose tokens/full private configs or claim accepted delivery from source `closed`, a local result, or model completion alone.
