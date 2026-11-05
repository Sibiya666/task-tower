# Beads admission implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply a bounded Windows readiness observation and public evidence vocabulary without duplicating Beads ownership or executing agents.

**Architecture:** A standalone admission module owns strict private authorization parsing, safe fixed readonly subprocesses and sanitized public output. It uses the existing process supervisor and filesystem predicates without changing Books behavior. Beads owns dependency readiness and future claims.

**Tech Stack:** Python 3.11+, standard library, installed Windows bd.exe and Git.

**Spec:** [Admission design](../specs/2026-11-05-beads-admission-design.md).

## Global constraints

- Windows only; no server, VPS, POSIX, migration, network, harness launch, claim/close, new queue or stage journal.
- One monotonic 30-second operation budget; Git at most 10 seconds each; capture at most 8 MiB per stream; config at most 64 KiB; public packet at most 64 KiB.
- Explicit separate admission authorization, project limit 32, allowed IDs limit 1000; only Sibiya666/task-tower.
- Every original path/security predicate, operation timeout and existing test remains intact.
- eligible_observation is not execution authority; closure follows actual accepted main, not model JSON.

## Review focus

- Sparse/promisor/submodule/filter/fsmonitor configuration cannot trigger network or command effects.
- Official omitted assignee differs from malformed id/status/type; real unassigned schema must work.
- Two nontransactional Beads reads or later source changes cannot become ownership authority.
- Captured errors and malformed source data must not leak paths, prose, environment or credentials.
- Unknown EOF/cleanup, exhausted budget and output truncation never produce eligibility.

### Task 1: Readonly admission implementation and meaningful tests

**Files:** Create task_tower/beads_admission.py; create tests/test_beads_admission.py. No changes to Books, old pipeline runtime or workflows.

**Interfaces:** `load_config(path: Path) -> dict`; `observe(config_path: Path, project: str, bead: str, *, runner=None, clock=None) -> dict`; `main(argv=None) -> int`. A test-only injected runner follows the module's documented fixed-operation interface and returns parsed data plus actual supervisor facts; production always uses run_command. Public packet schema and exit codes follow the spec. Internal organization is the implementer's decision; keep private config separate from packet data.

- [ ] Write failing unittest cases before product code. At minimum cover eligible official ready/show fixture with omitted assignee; non-Windows; malformed/duplicate config; foreign/unauthorized task; container/deferred/claimed/missing task; inconsistent source rows; 1001-row overflow; source mismatch/dirty/mutation; malicious Git configuration; unknown cleanup/truncation/deadline; environment stripping and privacy sentinels; stdout and return codes. Assert no mutating command is requested and packet never says accepted/done/owned.
- [ ] Run new tests and retain genuine RED output (missing module/behavior), with bounded process receipt.
- [ ] Implement strict parsing, safe local config/metadata validation and fixed safe Git reads before any Beads read. Refuse unsupported Git features; no generic command from configuration.
- [ ] Implement normalized selected-row validation, source recheck, canonical digests/UUIDs and sanitized public process facts. Unknown completion maps to unknown; known ineligible/malformed data maps to refusal. Do not swallow BaseException or leak exception text.
- [ ] Run targeted suite and existing Books tests; retain GREEN/process/source facts. Add real local Git fixture tests proving filters/fsmonitor marker commands never run; do not add live network probes or install tools. No local full-suite duplicate when targeted checks suffice before genuine full PR CI.
- [ ] Self-review exact diff and report tests, limitations and public module API to coordinator. Do not commit, push, inspect private DB/configs or run live Beads; coordinator owns host integration.

### Task 2: Operator documentation and integration evidence

**Files:** Create docs/beads-admission.md; update README.md, AGENTS.md and docs/backlog.md; update this plan checkboxes only for actual completed steps.

**Interfaces:** Document the exact private config schema and CLI from Task1. Keep example paths generic and IDs clearly illustrative. Include the structural stage envelope and its non-authority semantics, execution_completed versus accepted/done/unknown, independent reviewer identities and exact head/base pins. Do not implement a stage controller here.

- [ ] Independently review Task1 for SPEC and DEV quality, including the five review-focus cases; resolve findings through scoped TDD fixes before freezing source.
- [ ] Update docs to show the user-authorized Windows chain active while other future scopes remain deferred. Explain task1 observation versus task2 live claim, not a claim of shipped unattended execution.
- [ ] Coordinator runs one bounded real Windows CLI negative against the explicitly configured current claimed task. It must refuse; preserve actual supervisor EOF/cleanup and unchanged task owner/state. Never unclaim/reclaim, fabricate live readiness or send database/config to reviewers. Positive official-schema coverage is labelled fixture-only, not live authority evidence.
- [ ] Independent TEST acceptance assesses source/tests and actual public host receipt with this limited positive-live coverage stated explicitly. If insufficient, establish a safe additional test without replaying old pilots or altering real ownership.
- [ ] Freeze actual changed files and source hashes; commit with routine user authorization, push to Sibiya666/task-tower and create reviewable PR. Obtain fresh whole-diff independent exact head/base acceptance and real GitHub context. Wait for all current full-code CI; fresh gates before expected-head merge.
- [ ] Fresh materialize exact main, independently accept source and verify actual full Windows postmerge artifacts/manifests. Only then coordinator closes tt-auq.1 under task-tower-beads-admission and verifies history. Take newly ready tt-auq.2 under separate gates.
