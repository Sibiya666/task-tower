# Claude Code Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a bounded existing-auth Claude task and separate reviewer through the common backend with honest structured evidence.

**Architecture:** Add strict Claude profiles and a fixed file-only invocation. Observe stdout through the existing contained process runner, validate incremental NDJSON and source-bound structured output, and preserve durable queue fencing. Reuse accepted main APIs without unmerged stage/publication dependencies.

**Tech Stack:** Python 3.11+ standard library, existing Git/worktree/SQLite/process infrastructure, installed Claude Code 2.1.302.

**Spec:** `docs/superpowers/specs/2026-11-02-claude-adapter-design.md`.

## Global Constraints

- Use Python 3.11+ standard library only.
- Compatibility begins with exact installed release `2.1.302`.
- No auth inspection, installation, update, global setting change, model selection or permission bypass.
- Keep Codex/custom profiles and legacy process callers compatible.
- No automatic resume, ownership takeover, journal reset or unmerged #16/#17 dependency.
- `execution_completed` never means acceptance/task completion.
- Stream maximum `65536..67108864` bytes; line maximum `4096..1048576` bytes and no greater than stream cap.
- Timeout `1..86400` seconds, log cap `1..67108864` bytes per stream and existing five-second cleanup deadline remain unchanged.
- Claude budget decimal string `(0,100]`, at most two fractional digits; estimate may overshoot, no billing guarantee.

## Review Focus

- Valid-looking final output after malformed/oversized earlier bytes must fail; full observation differs from stored prefix.
- Denials and duplicate/mismatched terminal sessions must not become success even at exit zero.
- Callback failure/cancel/unknown cleanup must retain draining and durable fencing.
- Safe-mode managed policy and ordinary file access must not be described as an OS sandbox or changed model selection.
- Independent reviewer must read the exact committed pilot output rather than a new/dirty/different snapshot.

## File structure

Modify `task_tower/executor_profiles.py` for strict additive policy, `executor_harness.py` for Claude dispatch/capabilities, `executor_worker.py` for probe/observation/extraction, and `processes.py` for an optional stdout observer. Create `task_tower/claude_adapter.py` for probe validation, fixed invocation and parser only. Extend existing focused tests and add `tests/test_claude_adapter.py` plus `tests/test_claude_integration.py`. Update `docs/executor.md`, `docs/bootstrap.md` capability limits and new sanitized Issue20 evidence. Root owns shared top-level documentation and accepted stage-card updates.

### Task 1: Claude policy, probes and fixed invocation

**Files:** Modify `task_tower/executor_profiles.py`, `task_tower/executor_harness.py`; create `task_tower/claude_adapter.py`; test `tests/test_executor_profiles.py`, `tests/test_executor_harness.py`, `tests/test_claude_adapter.py`.

**Interfaces:** Consume existing `result_schema(attempt)`, `child_environment(environ)` and profile fingerprint. Produce `validate_probe(version_bytes: bytes, help_bytes: bytes, expected_version: str) -> dict`, `build_claude_invocation(attempt: dict, profile: dict) -> list[str]`, `claude_capabilities(profile: dict, evidence: dict | None = None) -> dict`. Probe returns sanitized version/required-option validation only; raw probe output stays private.

**No-update supplement:** Also produce pure `claude_child_environment(environ: dict) -> dict` in the new adapter module. Apply the common token stripping; remove case-insensitive `DISABLE_UPDATES` and `FORCE_AUTOUPDATE_PLUGINS` aliases; set canonical `DISABLE_UPDATES=1`. Preserve all remaining auth/model/telemetry variables and the original mapping. No common legacy environment change. Task3 must use this helper for every Claude probe/execution child, paired with the specification's bounded read-only preflight of known applicable local settings for only update-related env overrides and immediate fingerprint recheck; block observed conflicts/unreadable relevant local sources, otherwise retain the original managed-policy trust boundary. No model/probe invocation before current specification acceptance.

- [ ] Write failing tests for exact Claude profile keys/types/limits, non-Claude option rejection, single executable argv, forbidden approve/trust flags, missing help flags/manual/none values, wrong version, and no model/bypass/shell/turn flags.
- [ ] Write a failing child-environment test with inherited update value `0`, mixed-case duplicate aliases, forced plugin updates, GitHub tokens and representative auth/model/telemetry variables; require only canonical update-disable guard, token/force removal, exact preservation of other values and no host mutation.
- [ ] Run `python -m unittest tests.test_executor_profiles tests.test_executor_harness tests.test_claude_adapter -v`; confirm new assertions fail for the missing behavior.
- [ ] Implement strict profile and probe validation and fixed role tool lists/invocation from the specification. Add immutable MCP file/digest preparation contract without altering legacy invocation.
- [ ] Run focused tests; verify existing Codex/custom examples and capability keys remain compatible. Record evidence and request distinct Task1 review before proceeding.

### Task 2: Bounded stream observation and protocol validation

**Files:** Modify `task_tower/processes.py`; create parser in `task_tower/claude_adapter.py`; test `tests/test_executor_processes.py`, `tests/test_processes.py`, `tests/test_claude_adapter.py`.

**Interfaces:** Extend `run_command(..., *, cancel_requested=None, capture=None, stdout_observer=None)`; observer is callable `(chunk: bytes) -> None`. Produce `ClaudeEventParser(attempt: dict, stream_max_bytes: int, line_max_bytes: int)`, `.feed(chunk: bytes) -> None`, `.finish() -> dict` returning `{valid, reason, result, evidence}` with bounded data. Feed records its own invalid state and discards further content without growing memory. Observer failure propagates only as bounded runner evidence/termination request, not an uncaught drain-thread exception.

- [ ] Write failing tests splitting multibyte UTF-8/CRLF/JSON at every boundary; final no-newline; duplicate keys/init/final, wrong UUID, missing init/final, denied tools, extra event after final, unknown harmless event versus unknown terminal subtype, invalid nested binding/summary bytes, huge line/stream, malformed early bytes with later valid result.
- [ ] Write process tests proving observer sees bytes beyond stored prefix, no full-transcript retention, callback failure does not stop draining, termination request reaches the normal loop, and cleanup uncertainty cannot pass. Cover legacy callers unchanged.
- [ ] Run focused suites and confirm new failures before implementation.
- [ ] Implement bounded parser and observer; preserve shared Windows Job/POSIX containment, total digests, log caps and EOF evidence. Do not add a second process runner.
- [ ] Run focused suites and actual platform CI when available. Record fixture versus installed evidence separately; obtain independent Task2 review.

### Task 3: Foreground common-backend integration and recovery honesty

**Files:** Modify `task_tower/executor_worker.py`, `task_tower/executor_harness.py`; test `tests/test_executor_worker.py`, `tests/test_executor_integration.py`, new `tests/test_claude_integration.py`.

**Interfaces:** Consume Task1 invocation/probe and Task2 parser/observer. Preserve `execute_one(config, queue, *, owner_id=None)` and six-field adapter protocol. Worker writes exclusive private `claude-events.json` and existing `result.json` only after valid observation. `validate_result(path, attempt, max_bytes)` remains the final exact local binding check. No new queue schema or alternate admission route.

- [ ] Write failing integration tests using a clearly labeled executable fixture and existing adapter/queue/work flow for completed, denied->needs_input, nonzero, timeout, cancel, missing/malformed final, source mismatch, changed authority/pins/probe/version, observer failure and unknown cleanup.
- [ ] Test prior committed deliveries remain deduplicated; started/unknown Claude attempts cannot retry/resume; revoked profile still permits status/cancel; probes remove token variables; no raw output enters public evidence.
- [ ] Run `python -m unittest tests.test_executor_worker tests.test_executor_integration tests.test_claude_integration -v`; confirm new tests fail for missing Claude integration.
- [ ] Implement prelaunch contained probes, generated inline pinned request/instructions, immutable MCP config, observer hookup, strict result extraction and capability evidence. Preserve repeated authority/source checks and precedence of process/cleanup outcomes.
- [ ] Run focused suites then `python -m unittest discover -s tests -v`. Record sanitized test evidence; request separate Task3 review. Fixtures do not satisfy installed pilot.

### Task 4: Actual implementer/reviewer pilot and final capability documentation

**Files:** Modify `docs/executor.md`, `docs/bootstrap.md`; create `docs/tasks/evidence/TT-CLAUDE-ADAPTER-001/installed-claude-pilot.md`, `platform-matrix.md`, `test-review-inputs.md`. Root updates shared README/AGENTS/roadmap and acceptance stages.

**Interfaces:** Existing executor adapter/work/status/cancel and installation-owned source_ref/profile/allowlist; separate run/attempt UUIDs and role profiles; actual authorized task identity. Reviewer reads a new exact committed local pilot source snapshot and expected diff digest, through a fresh worktree/common backend. No direct CLI shortcut substitutes for worker execution.

- [ ] Prepare a concrete file-only pilot request, exact source/file/expected diff, existing-auth model scope/cost budget and independent reviewer request for coordinator authorization. No model invocation before accepted specification and concrete pilot authorization.
- [ ] Run genuine current-source admission/dependency verification through existing backend; retain receipt and sanitized bindings. Never reset old journal deliveries or use a dependency verification stub.
- [ ] Run installed 2.1.302 implementer via common worker; inspect exact changed files/diff and strict stream/process/result evidence. Commit only intended local pilot snapshot for review; do not push as part of pilot.
- [ ] Run a distinct read-only Claude reviewer process/session through common backend against that exact committed source and diff digest. Record independent verdict and coordinator test results; unsupported auth/network/policy failure remains a real blocker.
- [ ] Exercise installed cancellation and observed bounds under coordinator-approved small scope; report what was actually observed. Approximate budget behavior is not a hard billing assertion. Resume remains unsupported; record no invocation and unchanged fenced unknown-state behavior.
- [ ] Run full suite and actual Windows/macOS/Ubuntu CI. Publish capability matrix distinguishing fixture process tests from installed authenticated evidence; native Windows shell sandbox remains unsupported and shell tools disabled.
- [ ] Obtain fresh whole-diff development and test acceptance. Root completes exact-head/base PR acceptance, serialized merge, exact-main CI/independent postmerge acceptance and automatic Issue closure. Do not mark Issue done after pilot alone.

## Evidence freeze and handoff

- [ ] Run `git diff --check`; compute SHA-256 of UTF-8 decoded text normalized to LF for spec and plan (exclude card/reviews from self-reference).
- [ ] Fresh specification acceptor reads full documents, actual main APIs, Issue20 and current AGENTS, then records exact canonical source manifest; pending card remains pending until root records acceptance.
- [ ] Any subsequent specification/plan change invalidates that binding. Update waiting implementation against accepted main after serialized prior integration and rerun affected checks.
