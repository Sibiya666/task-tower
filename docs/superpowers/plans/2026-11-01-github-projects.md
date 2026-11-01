# GitHub Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect independent GitHub projects, aggregate their books and execute project tasks through a durable GitHub queue.

**Architecture:** Installation configuration owns connections. GitHub Issues own task state, repository Markdown owns artifacts, Actions owns scheduling. Existing file-backed worker remains explicit legacy mode.

**Tech Stack:** Python 3.11+, standard library, GitHub REST API and Actions.

**Spec:** docs/superpowers/specs/2026-11-01-github-projects-design.md

## Global Constraints

- No third-party dependencies or credentials in files/output.
- Each project owns Issues/Project/artifacts; user connections never enter product source.
- Preserve live worker and overlay; do not commit/push without authorization.
- Done requires verified main commit and independent acceptance.

## Review Focus

- Equal Issue numbers in different repos retain separate identities.
- API failure makes a project visibly unavailable rather than an empty success.
- Issue prose and Markdown paths cannot inject HTML or executable commands.
- Retried dispatch never repeats an already completed model run.
- Closed Issues and legacy local done records cannot forge acceptance.

### Task 1: Connections, remote store and books

Files: create task_tower/project_connections.py, github_tasks.py, books.py and tests/test_github_projects.py; modify task_tower/__main__.py. Interfaces: load_connections(path) returns validated connections; GitHubTasks exposes list/get/import; books CLI consumes connections and produces JSON/HTML.

- [x] Write failing tests for validation, namespace isolation, pagination/errors, metadata preservation/import and escaped three-entry pages.
- [x] Run focused tests and confirm failure; implement bounded GitHub transport/store and book views.
- [x] Run focused/full suite; document commands and independent task review.

### Task 2: Distributed project queue and remote acceptance

Files: create task_tower/project_worker.py, project workflow template, tests/test_project_worker.py, docs/github-projects.md. Consume Task 1 interfaces; expose trusted dispatch and one-job consumer with remote-state recheck, persisted review and explicit recovery.

- [x] Write failing tests for duplicate dispatch, interrupted run, main/evidence rejection and publication retry.
- [x] Implement workflow and consumer using trusted local runner/harness configuration; no issue-provided command execution.
- [x] Run focused/full suite and independent review; document setup and unverified physical runner limits.

### Final verification

- [x] Independently review whole diff, fix consequential findings, run full suite.
- [x] Record real read-only GitHub smoke and test evidence; leave reviewable changes, report exact rollout state.

## Independent specification review requirements

See docs/tasks/evidence/TT-GITHUB-PROJECTS-001/spec-review.md and the clarified trust contract in the spec. These requirements extend the task checklists above:

- Task 1: installation-owned pre-existing Project node ID and status mapping; GraphQL Issue membership/status projection; explicit unconfigured/permission-failure states. Board creation is out of scope. Test two owned Projects, idempotent projection and source failure isolation.
- Task 2: persist work intent, attempt identity, accepted review and pending publication in GitHub. Test pending replacement/cancellation, unknown dispatch reconciliation and runner-B publication of runner-A review without another model run. All consumers share Issue serialization and authorized recovery after proving the previous attempt terminated.
- Task 2: trusted default-branch/pinned bootstrap, numeric Issue validation, no shell interpolation, no Issue-authored acceptance authority. Bind independent acceptance to repository/Issue/attempt/exact SHA and required trusted check policy/source. Test forged/mismatched evidence, omitted checks, concurrent prose changes, untrusted refs and unauthorized recovery.
- Task 2: retain Superpowers stage gates and accepted input versions. State explicitly whether the worker only consumes externally produced merge evidence. Do not claim automated merge barrier enforcement unless implemented and tested for two Issues in the same repo.
- Final verification: report exact rollout state and limitations. Read-only API smoke proves connectivity only; no claim of installed workflows, end-to-end remote execution or a second physical runner without observed evidence. Keep installation configuration private and use placeholders in examples.
