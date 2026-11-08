# Integration handoff fixes implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, one source writer
> and a fresh independent whole-branch reviewer. Preserve existing WIP and owners.

**Goal:** Deliver all five authorized integration findings through real acceptance.
**Architecture:** Extend the existing native wrapper, journalled lifecycle and
trusted connector. No second task engine or background activation.
**Tech Stack:** Python 3.11+, standard library, existing Beads/Codex/GitHub tools.
**Spec:** [integration design](../specs/2026-11-08-integration-fixes-design.md).

## Global constraints

- Preserve native identities/history/claims, credentials stripping and unknown fences.
- No other repository effects, DB migration, installs, ACL/account changes or old workers.
- Existing timeout/assertion/inventory/fixture/skip and PR/main gates remain mandatory.

## Review focus

- A changed token/config must not bypass immutable reload authority (task 1).
- Closed external blockers reopening after adoption must fence claim/execute (task 1).
- Legacy history cannot justify an invented close event (task 2).
- Restart must never expand a PR-only/local task to automatic merge (task 3).
- Failed fixture creation must not leave or overwrite a token file (task 4).

## Tasks

### 1. Exact adoption and bounded live reload — tt-uy8.1/.2

Files: service/store.py, service/cli.py, intake_reload.py, tests/test_project_intake.py.
Interfaces: `Store.adopt_plan` retains exact approved plan; fresh native show checks
external blocker closure; unchanged operator config avoids repeated token reads.
- [ ] Add RED external closed blocker/reopened blocker and unchanged reload tests.
- [ ] Run `python -m unittest tests.test_project_intake -v`; inspect expected failures.
- [ ] Implement minimal validation and reload caching without loosening import.
- [ ] Run adoption/reload/service/connector focused checks; commit source and docs.

### 2. Native profiles — tt-uy8.3

Files: service/beads.py, service/cli.py, service/acceptance.py, tests/test_service_beads.py.
Interfaces: optional per-project executable/history profile; old global default.
- [ ] RED tests: distinct binaries, fixed argv, unknown profile, legacy close refusal.
- [ ] Implement explicit profile selection and refusal before unverifiable closure.
- [ ] Run native/API/acceptance focused checks; document real1.0.2 evidence boundary.

### 3. Delivery policy — tt-uy8.4

Files: connector/delivery.py, connector/cli.py, connector/client.py,
service/lifecycle.py, service/acceptance.py and matching delivery/lifecycle tests.
Interfaces: immutable policy with exact base and task_tower/owner_pr/local modes;
saved-result handoff remains separate from accepted canonical closure.
- [ ] RED policy/base/zero-merge/local-zero-network and restart-fence tests.
- [ ] Implement routing, durable outcome and verified owned-resource cleanup.
- [ ] Verify existing Task Tower gates plus owner-only/local controls; commit.

### 4. Windows fixture — tt-uy8.5

Files: tests/test_service_api.py, tests/fixtures, native fixture security tests.
- [ ] Retain authentic failed job evidence and unchanged-base comparison.
- [ ] RED native create-once/private-ACL/failure-cleanup tests with five-second bound.
- [ ] Replace disposable provisioning dependency only, preserve read_token validation.
- [ ] Run real Windows fixture and API/CLI boundary checks; report cause uncertainty.

### 5. Real evidence and delivery — all children

- [ ] Bound a disposable native late-card pilot with existing Codex, distinct review,
  saved result and stopped owned processes; do not activate canonical backlog/services.
- [ ] Fresh whole-diff independent exact H/B review and corrections.
- [ ] Final `reslop.cmd t -- python -m unittest discover -s tests -v` with explicit
  interpreter as needed; preserve full inventory, raw logs, source identity and cleanup.
- [ ] Publish protected PR, coordinate serialized merge with manager, verify all PR
  checks/status/protection and expected H. Fresh exact-main CI/artifacts and distinct
  postmerge verdict before native owner close/readback/history. Report actual gaps.
