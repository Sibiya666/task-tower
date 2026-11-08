# Pipeline Checkpoint Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a verified final commit usable after a transient private-index sharing violation, with actual cleanup and unchanged deadlines/fences.

**Architecture:** Specialize temporary-index directory cleanup in `pipeline_inputs`. Retry only error 32 under the existing host guard and a five-second additional cap; revalidate owned directory identity before retry. Preserve the current completed-effect chronology.

**Tech Stack:** Python 3.11+, standard library, real native Windows fixture.

**Spec:** [design](../specs/2026-11-08-pipeline-checkpoint-cleanup-design.md).

This is an implementation record. Canonical task status belongs to Beads
`tt-azn`; GitHub owns PR/CI/main acceptance. This document is not a work queue.

## Global Constraints

- Preserve checks, timeouts, authority, cancellation, privacy and effect fences.
- Historical causality of the original reason-free receipt remains unspecified.
- No best-effort cleanup success, Git replay, ACL/auth/settings or UI changes.

## Review Focus

- Permanent or non-sharing permission failures must still refuse continuation.
- A replaced directory or reparse point must never become a cleanup target.
- Guard/deadline failure must prevent another cleanup attempt.
- A body exception must survive a successful cleanup retry.
- A completed commit must remain completed and occur exactly once.

### Task 1: Regression and contained fix

**Files:**
- Modify: `task_tower/pipeline_inputs.py` (private checkpoint directory cleanup).
- Modify: `tests/test_pipeline_publish.py` (native causal regression).
- Create: `tests/fixtures/windows_file_lease.py` (scoped test-only read handle).
- Create: `tests/test_pipeline_checkpoint_cleanup.py` (refusal/budget tests).
- Modify: `tests/test_pipeline_watch.py` (existing bounded failure message).

**Interfaces:** Private temporary-directory subclass receives its parent and the existing host guard; callers retain the original checkpoint API.

- [x] Add the real Windows index-lock regression; observe RED without changing original assertions/timeouts.
- [x] Add minimal sharing-only cleanup retry, original-identity validation and existing guard checks.
- [x] Observe GREEN and run refusal/budget/body-exception tests.
- [ ] Run the original native watch test and relevant checkpoint/publication checks.
- [ ] Obtain independent whole-diff review at actual head/base and genuine full CI.
- [ ] Publish genuine approval status, verify protection, merge expected head.
- [ ] Verify fresh exact main, full runtime manifests/event and independent acceptance.
- [ ] Close the canonical task only within the demonstrated scope; retain original failed and invalid experimental receipts.
