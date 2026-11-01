# Project-first Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A user can connect a repository to its Project before creating Issues, using bootstrap/CLI and self-contained documentation.

**Architecture:** A bounded GraphQL onboarding adapter discovers/links/creates the board and persists private connection metadata. Issue import preflights the board then repairs membership on retries. Bootstrap forwards trusted flags; no hidden authentication or model capability changes.

**Tech Stack:** Python 3.11+ standard library, GitHub GraphQL/REST, existing bootstrap and connection models.

**Spec:** docs/superpowers/specs/2026-11-01-project-onboarding-design.md

## Global Constraints

- No third-party dependencies, credentials in output/config or guessed permissions.
- Project before Issue creation; preserve existing Issues and boards, no silent duplication.
- Local-only/read-only uses remain explicit; autonomous execution capabilities unchanged.
- Protect private config from symlinks/reparse paths and lost concurrent edits.
- Do not modify the pinned live watcher or overlay implementation.

## Review Focus

- A failed Project operation cannot fall through to Issue POST.
- An uncertain create/membership response cannot silently create a duplicate.
- Existing options/connections/prose survive repeat setup.
- Multiple or wrong-owner boards need explicit resolution.
- A clean clone can follow documented commands without machine-specific paths or chat context.

### Task 1: Connection onboarding and import ordering

Files: create task_tower/project_onboarding.py and tests/test_project_onboarding.py; modify github_tasks.py, project_connections.py/__main__.py as needed; regression tests for import.

- [ ] Write failing tests for discover/create/reuse/link, auth failures, ambiguity and config preservation.
- [ ] Include user/org canonical identity and mismatched URL/node/owner, linked and owner pagination truncation, partial GraphQL errors, duplicate legacy matches, unknown Project/Issue POST outcomes and rerun after remote success/local persistence failure. Assert no additional create on uncertain outcomes.
- [ ] Implement a bounded onboarding adapter and `connect` CLI, with safe private connection persistence.
- [ ] Verify preservation of existing field/option IDs, unrelated items and trusted publishers/connections; incompatible fields fail closed. Exercise two competing config writers and a same-ID/different-repository conflict, including unsafe path rejection before writes.
- [ ] Add import preflight before Issue POST and membership repair after new/existing import; test partial failures and retry without duplicates.
- [ ] Ensure repair returns the original Issue identity, preserves prose/evidence and current lifecycle, and exposes the Issue URL plus failing stage on partial success. Confirm incomplete/ambiguous lookup cannot create.
- [ ] Cover existing `task_id`, `legacy_id` and legacy metadata `id` aliases, conflicting/duplicate matches, same IDs in different repositories, and `TT-PROJECT-ROLLOUT-001` resolving to existing Issue 24 with zero Issue POSTs.
- [ ] Run focused/full tests and independent review.

### Task 2: Installer forwarding, documentation and live setup

Files: bootstrap.py (package), tests/test_bootstrap.py, README.md, AGENTS.md, docs/bootstrap.md, docs/github-setup.md, docs/roadmap.md and current architecture spec.

- [ ] Test installer GitHub flags forwarding, refusal before launch on setup failure, and unchanged local-only behavior.
- [ ] Implement installer integration using Task 1's interface; no automatic scope grant or auth secret handling.
- [ ] Document auth/project-first setup, custom harness integration, supported capabilities, and roadmap Issues.
- [ ] Include an executable clean-clone sequence with installation-owned config location, selected-repository identity, explicit board selection, human-confirmed gh auth project scope, rerun/partial-failure recovery and local-only limitations. Explain that cross-host creation serialization is not provided.
- [ ] Verify live Project linkage/items/status and repeated setup, then independent PR acceptance/CI/main/postmerge and Issue 24 closure.
