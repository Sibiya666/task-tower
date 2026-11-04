# Parallel Windows CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce Windows CI wall time without dropping any unittest identity or weakening process tests.

**Architecture:** Deterministically partition the full discovered suite across four isolated Windows jobs; retain stable aggregate checks and the existing exact-main event publisher.

**Tech Stack:** Python3.11 standard-library unittest; GitHub Actions Windows matrix.

**Spec:** `docs/superpowers/specs/2026-11-05-windows-ci-shards.md`.

## Global Constraints

- Four Windows shards, no third-party dependency or credential/permission changes.
- Full unique test inventory exactly once; fail closed on discovery error or malformed inventory.
- No existing test/assertion/timeout/process containment changes.
- Stable final PR/postmerge check names and genuine merge-event contract.

## Review Focus

- Failed discovery must not disappear into a different shard.
- Class/module setup and cleanup must retain normal unittest semantics.
- Matrix failure/skipping/cancellation must fail the stable aggregate.
- Postmerge publishes runtime passed only after all exact-merge shards pass.
- Runner queuing/imbalanced test cost must not be described as a measured speedup before actual CI.

## Task1: Deterministic runner and fail-closed execution

**Files:** Create `task_tower/ci_unittest.py`, `tests/test_ci_unittest.py`.

- [ ] Write meaningful partition/discovery/fixture/result/CLI regressions and confirm RED because the runner does not exist.
- [ ] Implement validated discovery, unique sorted partitioning, inventory mode and normal unittest execution/exit behavior.
- [ ] Run the new tests GREEN, then inventory the actual source to prove four disjoint selections cover every discovered test identity. Do not repeat a serial full suite for this structural inventory proof.

## Task2: Isolated Actions matrix and aggregate gates

**Files:** Modify `.github/workflows/cli.yml`, `.github/workflows/postmerge.yml`, README.md, AGENTS.md.

- [ ] Use four Windows shard jobs on the existing PR trigger and preserve the old stable check as fail-closed aggregate.
- [ ] Use four exact-merge Windows shard jobs in postmerge; dependent publisher preserves artifact identity and emits pass only for successful matrix result.
- [ ] Update entry docs with real coverage/queue/cost limits, validate diff and obtain independent whole-diff review at frozen head/base.
- [ ] Publish PR; observe actual four-shard Windows checks and final aggregate; fix real failures before merge.
- [ ] Serialize merge behind accepted previous main. Verify actual exact-main shards/artifact and independent source acceptance, record measured timing, then close `tt-qrk.3` as coordinator.
