# GitHub Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** The installed watcher automatically publishes a proven local acceptance and closes its mapped GitHub Issue.

**Architecture:** Add a publisher adapter and separate journal publication claims/retries. Extend the watcher after acceptance, including already-done records, and teach books to verify explicitly trusted local-publisher comments.

**Tech Stack:** Python 3.11+ standard library, SQLite, GitHub REST.

**Spec:** docs/superpowers/specs/2026-11-01-github-publication-design.md

## Global Constraints

- Preserve live journal and independent reviewer decisions; no model rerun for publication.
- Explicit per-repository mapping and trusted account configuration, never credentials in files.
- Preserve prose and independent workflow receipt mode; no physical runner installation required.
- Main+CI+accepted independent evidence are mandatory before close.

## Review Focus

- Lost HTTP response must not create duplicate receipts on restart.
- Stale approvals must not override newer rejection/lifecycle attempts.
- Untrusted comment authors and Issue-body metadata cannot forge done.
- Publication errors cannot mark the local review failed or trigger another model.
- Concurrent publishers and crash recovery retain one publication owner.

### Task 1: Publisher, durable state and watcher integration

Files: task_tower/github_publication.py, postmerge_journal.py, postmerge_worker.py; tests/test_github_publication.py and worker integration cases.

- [x] Write failing tests for close eligibility, API retry/lost response, unchanged model count and claims.
- [x] Test actual authors of new/discovered receipts, canonical persisted payload across mutable evidence, conflicting identities, pagination exhaustion, lease expiry and delayed stale owner.
- [x] Implement GitHubPublisher with explicit issue mapping/account and canonical receipt; add SQLite publication claim/save/finish helpers and optional worker config wiring.
- [x] Run focused/full tests and independent task review.

### Task 2: Trusted book verification and rollout

Files: project_connections.py, project_worker.py (receipt verification only), books/board compatibility tests, docs/github-publication.md.

- [x] Write failing tests for trusted/untrusted author, forged/stale receipt, valid done and existing workflow mode.
- [x] Test cross-mode newer rejection/running/failed attempts, reposted old approval, altered receipt, ambiguous PATCH reconciliation; document compare/close race.
- [x] Implement explicit connection trust and remote verification, document local-vs-Actions trust boundaries.
- [x] Run independent final review/full tests, replace the idle live watcher retaining state, and verify automatic closure and duplicate safety on Issue 9.
