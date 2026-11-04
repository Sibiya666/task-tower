# Windows Test-Host Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development for the bounded fixture helper and integrations.

**Goal:** Capture the missing discriminator when existing Windows CI fixture hosts fail, without relaxing their gates.

**Architecture:** A test-only observation context records bounded whitelisted parent facts and creates lazy failure messages. Production controller/process/journal behavior remains unchanged.

**Tech Stack:** Python3.11 standard-library unittest/mock, existing Windows native fixture tests.

**Spec:** `docs/superpowers/specs/2026-11-05-ci-fixture-observability.md`.

## Global Constraints

- Test-only code; no archived-conveyor features, production authority/clock/timeout changes, model invocations or real task claims.
- Original return values/exceptions, assertions, measured cancellation phase and cleanup controls unchanged.
-32 host/16 error records; bounded scalar values and valid ASCII JSON report<=16KiB; no secrets/environment/database bodies.
- Keep parent bug open until actual cause/fix evidence exists.

## Review Focus

- Observation must not add a journal read inside cancellation's deadline or hold a lock across product calls.
- A false shutdown proof, callback exception or missing host result remains a failure.
- Captured rows must be those actually observed, not a later row presented as the original.
- Hook restoration must not control active fixture threads or leak patches to subsequent tests.
- Passing-path message construction must remain lazy; failure reports cannot leak arbitrary bodies or exceed caps.

## Task1: Fixture helper and meaningful tests

**Files:** Create `tests/fixtures/host_observation.py` and `tests/test_host_observation.py`.

- [ ] Independent design/buildability review before implementation.
- [ ] Write RED regressions for faithful callback/result/proof observations, unchanged exceptions/return values, caps/redaction and hook restoration.
- [ ] Implement the minimum observation-only context; run GREEN and independent task spec/quality review.

## Task2: Wire unchanged native precondition assertions

**Files:** Modify `tests/test_pipeline_watch.py` only for lazy messages/context wiring; preserve every expected state/count and deadline.

- [ ] Add preparation-only observation to the delayed-cancellation helper; publication precondition observation before the blocked-Git phase; optional observer message to the watcher precondition timeout.
- [ ] Run the affected unchanged native cases once with bounded supervisor capture and source-unchanged/EOF/cleanup proof. Do not loop the full suite to obtain green.
- [ ] Freeze full head/base diff, fresh independent PR acceptance and real complete Windows matrix; no merge on failed checks.
- [ ] Serialize integration against accepted current main; independently verify exact-main source/CI/artifact. Diagnostic delivery may finish, but parent bug remains open without cause evidence.
