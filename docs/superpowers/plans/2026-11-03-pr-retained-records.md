# PR retained records implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Preserve fresh independent reviews.

**Goal:** Resolve prepared and verified PR-review records through genuine private host evidence.

**Architecture:** Pin the private PR journal independently of its mutable contents. Bind preparation provenance inside immutable input, then resolve host-owned records against a single read-only journal snapshot. Reading a record never grants effect authority.

**Tech Stack:** Python 3.11+, standard library SQLite/unittest and existing contained role runner.

**Spec:** ../specs/2026-11-02-pr-worker-design.md and ../specs/2026-11-03-pr-retained-records-contract.md.

## Global constraints

Preserve public v1 request/envelope/receipt and PRJournal schemas. Default Task2 preparation remains unchanged. No live private state migration, role launch, remote effects or legacy acceptance in the reader. Task3L, effects4c, CLI5 and operator/server gates remain required later.

## Review focus

- Same-byte physical replacement invalidates old context, while normal journal updates remain usable.
- Missing/foreign/hot or invalid journals are refused without creation or repair.
- Canonical UTF-8 size boundaries refuse before admission or launch, with no truncation.
- Orphan, unknown and cross-owner effects cannot become genuine process proof.
- Current reviewer remains distinguishable from excluded original/prior instances.

## Task4b2: producer contract and strict readers

**Files:** Modify task_tower/pr_context.py and task_tower/pr_source.py; create task_tower/pr_records.py and tests/test_pr_records.py; extend tests/test_pr_context_journal.py and preparation tests.

**Interfaces:** Retain actual prepare_review API with opt-in typed private_context; add PRHostContext.prepared_record(input_sha256) and review_record(input_sha256). Exact closed shapes, paths and limits are in the contract. Task5 owns persistence and journal lifecycle; no accepting generic import API.

- [x] Obtain independent affected-contract approval before implementation.
- [x] Write and run failing own-journal identity/schema/appearance regressions against actual factories.
- [ ] Pin/validate present own journal, including one read-only transaction, physical identity and schema; keep absent journal explicit null.
- [ ] Run journal/context regressions, including actual writes and corrupt existing rows. Close all test SQLite connections explicitly.
- [ ] Add failing preparation/provenance/limit regressions, then implement opt-in provenance and bounded canonical record utilities.
- [ ] Add genuine producer/runner/journal positive fixtures and adversarial record tests, then implement strict readers.
- [ ] Run focused tests and independent implementation acceptance; resolve findings before integration.
- [ ] Run required full checks and preserve exact-source evidence. No whole Issue completion claim from this bounded task.
