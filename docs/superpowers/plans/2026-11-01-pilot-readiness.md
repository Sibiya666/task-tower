# Pilot readiness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Produce a working CLI that determines whether a project can enter the agent-development pilot and records bounded check results.

**Architecture:** A versioned JSON manifest describes the environment; a read-only audit checks Git, project instructions, Superpowers and tools. Explicitly requested baseline commands run with time limits; a JSON report records the exact revision and evidence. This milestone does not issue tasks, invoke model inference, change project files or merge code.

**Tech Stack:** Python 3.11+ standard library, Git, Windows PowerShell; unittest with real temporary repositories and child processes. No dependency installation.

**Spec:** ../specs/2026-11-01-agent-development-architecture-design.md

## Global Constraints

- Superpowers is mandatory; audit verifies the configured skill file and records its content hash.
- Existing Dialoid changes are preserved. No baseline commands run on a dirty repository.
- Readiness for a pilot does not authorize or claim readiness for nightly automerge.
- Commands use argument arrays without shell expansion; timeout stops process descendants.
- Reports contain environment/check identity and output digests, not raw command output or secrets.
- Reuse the clean task-tower checkout and feature branch; no additional worktree required.

## Review Focus

- Dirty or changing HEAD must block a valid baseline (Task 1/3 tests).
- Invalid manifests and paths escaping the project must fail closed (Task 1 tests).
- Missing executables and failed Git probes must become explained blockers (Task 1/2 tests).
- A timed-out parent must not leave a child executing (Task 2 real process test).
- Passing commands alone must not imply a safe night or bypass missing policy (Task 3 tests).

### Task 1: Manifest and read-only audit

**Files:** `task_tower/readiness.py`, `tests/test_readiness.py`, `task_tower/__init__.py`.

**Interfaces:** `load_manifest(path) -> dict`; `audit(root, manifest) -> dict` with `status`, `blockers`, `revision`, `environment`, `night_ready=False`. Validate version=1, non-empty project ID, required relative paths, Superpowers skill path, tool argument arrays, baseline commands and positive timeouts. Resolve project-relative paths and reject traversal/symlink escape. Probe actual Git root, HEAD, worktree cleanliness, tool availability, required docs and skill digest. Tool argv is executed only with --run-checks.

- [x] Write tests for clean Git repository, dirtiness, wrong root, missing instructions/skill/tool, malformed manifests and path escape.
- [x] Run `python -m unittest discover -s tests -v`; confirm failures from absent implementation.
- [x] Implement minimal loader and audit; run full suite, expect PASS.

### Task 2: Bounded check execution

**Files:** `task_tower/processes.py`, `task_tower/windows_job.py`, `tests/test_processes.py`.

**Interfaces:** `run_command(argv, cwd, timeout_seconds) -> dict` returns status (`passed`, `failed`, `timeout`, `unavailable`), exit code, duration, output size/hash and argv. Windows uses a kill-on-close Job Object: CreateProcessW suspended, assign to job, then ResumeThread; POSIX uses a new session and killpg. Descendants are also stopped on normal parent exit. Output is spooled to temporary files, not held unbounded in memory. No raw output enters the report.

- [x] Write tests for exit success/failure, missing executable, output digest, literal shell characters and timeout including a spawned child.
- [x] Run focused tests and confirm RED.
- [x] Implement bounded runner; run full suite, expect PASS.

### Task 3: CLI, manifests and real Dialoid report

**Files:** `task_tower/__main__.py`, `tests/test_cli.py`, `examples/dialoid.project.json`, `README.md`, `AGENTS.md`, `.gitignore`, `docs/reports/2026-11-01-dialoid-readiness.md`.

**Interfaces:** `python -m task_tower audit --project PATH --manifest FILE [--run-checks] [--output FILE]`. Audit always checks environment. Without `--run-checks`, status is `awaiting_baseline` if environment passes. With explicit baseline execution, require clean preflight, run commands sequentially and recheck HEAD and cleanliness. Status `ready_for_pilot` only when all checks pass and repository stays unchanged. Failure exit=1; invalid input exit=2; success exit=0. Output JSON is UTF-8 and report-writing errors are explained.

- [x] Write subprocess CLI tests for JSON, explicit baseline gate, blocked execution, failure codes and a check changing the repository.
- [x] Run focused tests and confirm RED.
- [x] Implement CLI and project example; document setup, limitations, report fields and use.
- [x] Audit real Dialoid read-only; store a redacted human-readable findings report in docs, local JSON under ignored runtime/.
- [x] Run full suite and diff checks; independent reviewer inspects implementation against plan/spec; fix substantive findings with regression tests.

## Scope after this milestone

Queue, task capture from sessions, model execution adapter, stage transitions, merge controller and book UI remain subsequent milestones. A blocked Dialoid audit must not be presented as a completed autonomous task cycle. Select a clean pilot checkout and project policies before starting real execution.
