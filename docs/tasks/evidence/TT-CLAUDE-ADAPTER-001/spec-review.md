# Independent specification acceptance — TT-CLAUDE-ADAPTER-001

Verdict: **ACCEPTED for implementation**, 2026-11-02. Reviewer: `claude_spec_acceptance`, a fresh agent distinct from the spec/plan author. This is specification acceptance only, not runtime, development, test, PR or postmerge acceptance.

## Exact reviewed inputs

- Repository: `Sibiya666/task-tower`, Issue [20](https://github.com/Sibiya666/task-tower/issues/20), read through the authenticated connector during review; dependency is Issue15.
- Actual checkout HEAD/base: `56f8ab12f21ab91030ffe54de96520fcd979dc04`, branch `feat/claude-adapter`.
- Specification: `docs/superpowers/specs/2026-11-02-claude-adapter-design.md`, canonical SHA-256 `4df7b9e772403abd16bfac311e5ebfc17ea48a7380451a5f380403337daaec74`.
- Plan: `docs/superpowers/plans/2026-11-02-claude-adapter.md`, canonical SHA-256 `9f3fe04fc489d8b30628a70387bbe0da393f9ebab5e1a037f2446e4319f01650`.
- Canonical hashing: decode UTF-8, normalize CRLF/CR to LF, hash UTF-8 bytes. Independently recomputed both hashes; both match the frozen review request. Card and review are excluded from the self-referential source binding.
- Read actual `AGENTS.md`, `docs/development-process.md`, `docs/executor.md`, `docs/bootstrap.md`, pending task card, and accepted-main `executor_profiles.py`, `executor_harness.py`, `executor_worker.py`, `executor_queue.py`, `processes.py`. Read applicable Superpowers review instructions/template; performed this review directly, without another subagent.

The coordinator supplied genuine dispatcher delivery `59b1c68b-225f-4645-a3c0-91f4485d7531` / `queue:59b1c68b-225f-4645-a3c0-91f4485d7531` and accepted dependency evidence. These remain admission provenance, not a claim that this reviewer reran admission or executed a model.

## Verification and reasoning

Independently opened current official [CLI reference](https://code.claude.com/docs/en/cli-reference), [programmatic execution](https://code.claude.com/docs/en/headless), [permissions](https://code.claude.com/docs/en/permissions), [sandboxing](https://code.claude.com/docs/en/sandboxing), and [setup](https://code.claude.com/docs/en/setup). Independently resolved installed `claude.exe` with normal PATH and ran only `--version` and `--help`: version is `2.1.302 (Claude Code)`; required flags and `manual`/`none` values are present, and `--max-turns` is absent. No auth inspection, model execution, installation, update or settings change occurred. `git diff --check` passed; untracked proposed documents were read in full rather than inferred from that check.

The fixed print/stream/schema invocation is supported by current official interfaces. Safe mode retains ordinary auth/model/permissions while disabling ordinary customizations; managed policy remains a documented boundary. Manual mode plus explicit file tools and denying unanswered requests avoids a permission bypass. The specification honestly states that file-tool policy and worktrees are not an OS security sandbox. Native Windows shell sandbox absence and unverified installed POSIX combinations are explicit. [CLI reference](https://code.claude.com/docs/en/cli-reference), [permissions](https://code.claude.com/docs/en/permissions), [sandboxing](https://code.claude.com/docs/en/sandboxing).

The protocol validates observed bytes rather than capped log prefixes, rejects denials and malformed/ambiguous terminals, binds nested results to run/attempt/source and gives cancellation or uncertain cleanup precedence. These are concrete additions to existing contained process and worker interfaces. The plan provides failing-first parser, process, profile and genuine common-backend fixture tests; preserves legacy callers and durable unknown-state fencing; and does not depend on unmerged Issue16 code. Installed execution remains a separate mandatory gate, including a distinct read-only reviewer of a committed exact pilot snapshot. Current official streaming, denial and structured-result behavior supports this approach; actual behavior still needs the required pilot. [Programmatic execution](https://code.claude.com/docs/en/headless).

No blocking specification or plan finding. Acceptance does not relax any stated gate.

## Implementation review checkpoints

- Bridge parser cap/invalid state to the runner's contained termination request while continuing to drain; a parser that silently discards forever after invalidation would not implement the specification.
- Keep public queue evidence within its existing neutral IDs/hashes/counters/booleans schema; detailed reasons and raw/model metadata stay private.
- Before model calls, concretize independent pilot identity, source, expected diff, fresh delivery and per-role installation authority. The existing single-profile-per-Issue allowlist and delivery fingerprint cannot be switched underneath an admitted run. Never replay the Issue20 dispatcher receipt or fabricate readiness/dependency proof to obtain reviewer execution.
- Treat argv-size/probe/output failures conservatively before launching a model; missing actual execution evidence cannot become verified capabilities.

These are checks against the accepted contract, not permission for new authentication/model scope or alternate queue protocols.

## Declined to judge

- Runtime correctness and actual paid/authenticated execution: no implementation or model run was part of this review; subsequent mandatory stages own that evidence.
- Unattended orchestration, publication, pool scheduling and distributed ownership: explicitly owned by other Issues; this adapter must not claim those capabilities.

Any spec/plan edit or relevant accepted-main interface change invalidates this exact source binding and requires fresh review. Root may record this verdict in the pending card through the ordinary stage loader; this reviewer did not edit the card, code, specification, plan, Git state or GitHub.
