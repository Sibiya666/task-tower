# Bootstrap harness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task.

**Goal:** Launch a chosen harness after clone and record this work as a staged Task Tower pilot task.

**Architecture:** Separate harness/configuration module, bootstrap CLI, and file-backed pilot task record. Overlay remains independent. No automatic queue/model execution/merge claims.

**Tech Stack:** Python 3.11+ stdlib, unittest, Git.

**Spec:** ../specs/2026-11-01-bootstrap-harness-design.md

## Global Constraints

No installation, auth reads, permission bypass, or global configuration edits. Preserve unrelated files. Do not commit/push without user request. Superpowers required; never mark task done before main + postmerge.

## Review Focus

Untrusted shell characters and Windows shims; symlink/hardlink writes; stale skill/evidence hashes; noninteractive accidental launch; spoofable pilot reviewer IDs explicitly documented.

### Task 1: Harness and configuration

Files: task_tower/harness.py, tests/test_harness.py. Interfaces: prepare(project: Path, harness: str, superpowers: Path|None, adapter: Path|None, executable: str|None, persist: bool) -> dict (argv, cwd, capabilities, platform, config); load_config(project) -> dict|None. Builtin discovery via shutil.which; --executable override; custom descriptor validation. Persist local config/context atomically; detect stale skills on reuse. Test RED→GREEN, independent review.

### Task 2: Pilot task card

Files: task_tower/tasks.py, tests/test_tasks.py. Interfaces: load_task(path) -> dict; accept_task(path, stage, reviewer, evidence: Path, commit: str|None=None) -> dict. Strict stages spec/development/test/postmerge, executor ID in card, hashes + relative paths for evidence, main ancestry check postmerge. Atomic saves, safe path handling, stale evidence blockers. Test RED→GREEN, independent review.

### Task 3: Bootstrap CLI and launchers

Files: task_tower/bootstrap.py, bootstrap.py, start.cmd, start.sh, task_tower/__main__.py (task subcommands), tests/test_bootstrap.py, docs/bootstrap.md, README.md, .gitignore, examples/custom-harness.json, .github/workflows/cli.yml. Expose bootstrap --project --harness --superpowers --adapter --executable --dry-run --configure-only --launch; interactive selection and existing config reuse; subprocess.run(argv,cwd, no shell) attached terminal, propagate exit/cancel. Add task show/accept CLI. Real fixture subprocess tests plus CI three OS. Review and final full suite. Save independent decisions and results to docs/tasks/evidence/TT-BOOTSTRAP-001/ and accept actual stages through CLI; leave postmerge pending until real main integration.

## Execution ledger

Spec/design describes the approved user flow; precise defaults above are implementer decisions. Separate clean task-tower checkout is reused, no extra worktree needed. Tests and independent reviewers supply stage evidence. No completed automatic task-manager loop is claimed.
