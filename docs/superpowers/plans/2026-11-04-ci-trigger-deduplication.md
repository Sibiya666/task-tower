# Windows CI Trigger Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the unchanged full Windows suite once for a PR and once for its exact merge, rather than duplicate ordinary pushes.

**Architecture:** PR-only Portable CLI validation retains its stable check and merge-tree checkout. The unchanged postmerge workflow remains the sole full exact-main validator and merge-event producer for PR-based integration.

**Tech Stack:** GitHub Actions YAML, existing Python3.11 unittest, Windows runner.

**Spec:** `docs/superpowers/specs/2026-11-04-ci-trigger-deduplication.md`.

## Global Constraints

- Windows only; no new dependencies, permissions, model/account/auth or repository changes.
- Keep the full unittest command, stable job name and postmerge artifact contract.
- Do not claim direct-push/merge-queue support or full overlay coverage.
- Independent head/base review and applicable CI/main acceptance are mandatory for workflow changes.

## Review Focus

- Superseded PR cancellation must not cancel another PR or a main/postmerge run.
- PR checks must retain default proposed-merge checkout rather than silently switching to branch head.
- The postmerge producer must retain exact merge SHA, failure propagation and event artifact identity.
- Administrative CI exceptions for docs must not be reused for this workflow change.
- Documentation must describe absent push CI truthfully and avoid inventing speedup measurements.

## Task1: Remove duplicate triggers and document the accepted route

**Files:** Modify `.github/workflows/cli.yml`; update `README.md` and `AGENTS.md`; retain `postmerge.yml` byte-for-byte.

- [ ] Confirm independent research acceptance, create/claim canonical optimization Bead and preserve its dependency on accepted research.
- [ ] Remove the Portable CLI push trigger; add workflow/PR-scoped supersession cancellation, keeping all job steps unchanged.
- [ ] Update entry docs with the PR/full exact-main route and direct-push/merge-queue limits.
- [ ] Inspect actual YAML/steps and diff; validate no other workflow/test source changed. Do not add implementation-mirroring string assertions for a small configuration change; actual Actions execution is required validation.
- [ ] Commit and freeze full head/base diff. Obtain an independent exact-head/base whole-diff approval and genuine GitHub acceptance context.
- [ ] Open PR, verify only applicable PR workflow executes and full Windows checks succeed, then expected-head merge under existing authorization.
- [ ] Verify exact-main source, unchanged postmerge full suite and real artifact; obtain independent main acceptance and close the canonical Bead as coordinator with evidence links.
