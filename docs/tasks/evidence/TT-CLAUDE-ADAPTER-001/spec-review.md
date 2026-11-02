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

## R1 — narrow child update-guard supplement review

2026-11-02, same independent reviewer. **REJECTED as currently worded; helper policy accepted in principle.** The original report above is preserved. Reviewed canonical spec `4b0df7a12990bec5e97465485a70e3df842861444cb70e5d8cbafeccc395b8f9` and plan `e157e48f704c1f226443a6e69f89259b64d0b57e1662db57d61fce3d119ea2dd`; independently recomputed both. Task1 WIP/code is excluded from this narrow specification review.

The proposed pure child helper appropriately removes GitHub tokens and case-insensitive update/force aliases, supplies canonical `DISABLE_UPDATES=1`, preserves other variables and leaves the host untouched. Removing the force variable avoids relying on invented `0` semantics. Official documentation identifies the full update-disable control and the force-plugin-update override of the weaker updater control. It also states that settings `env` commonly replaces inherited values. [Environment variables](https://code.claude.com/docs/en/env-vars).

Important finding: the new paragraph makes every actual probe/pilot depend on establishing that all loaded settings and managed policy cannot override the guard, but supplies no bounded method. Managed sources can arrive remotely and change while a session runs. Requiring universal proof converts the original accepted managed-policy boundary into an open-ended prerequisite; the task's no-install/update instruction does not require a new human attestation or proof against arbitrary trusted policy behavior. [Settings and precedence](https://code.claude.com/docs/en/settings).

Read-only current-installation spot check parsed the default user settings and reported only relevant-key presence: neither update-related key is present. Worker checkout project/local settings are absent; `C:/Program Files/ClaudeCode/managed-settings.json` is absent; no `CLAUDE_CONFIG_DIR` override is inherited. No auth/model/secret values or complete settings were output. This is a scoped check, not a claim that all managed sources or the eventual pilot checkout were examined. No Claude process, model, updater, auth operation or settings mutation was run during R1.

Required correction: replace the universal prerequisite with a bounded read-only preflight of known applicable local settings sources for only these update-related `env` keys, including the actual invocation worktree and selected config directory. Record sanitized source identities/fingerprints and relevant-key findings privately; block an observed conflicting override or an unreadable relevant local source. Recheck for each concrete probe/pilot as appropriate. If no conflict is observed, allow guarded execution under the already documented managed-policy boundary, without asserting an absolute OS/update guarantee. Newly observed conflicting managed behavior remains a real blocker; unknown hypothetical remote behavior alone does not create a new approval flow. Do not inspect credentials or mutate policy to pass preflight.

Suggested replacement intent: “The supplied mapping is a child-process safeguard. Before actual probes/pilot, inspect known applicable local settings read-only for update-related env overrides and retain sanitized fingerprints/findings. Block observed conflicts or unreadable relevant local settings; otherwise proceed with this guard and document that existing trusted managed policy may still affect runtime behavior. No claim is made that arbitrary managed hooks cannot run external commands.”

No other original design decision is reopened. A corrected frozen supplement needs fresh narrow acceptance before its runtime hookup. Pure helper tests alone do not prove effective runtime policy.

## R2 — corrected narrow supplement acceptance

2026-11-02, reviewer `claude_spec_acceptance`. **ACCEPTED for implementation.** This supersedes R1's rejection for the corrected supplement only; original report and R1 remain preserved above.

Independently recomputed canonical UTF-8/LF hashes and read the changed supplement/source entry and corresponding plan contract:

- Specification: `8d1c587b62cff7ded7906a450800d722f50bf285d835e9c0ed1e794a6080c3bd`.
- Plan: `30f8ff37c16b0ae2372151abb7ef27f87be7ad98f5b0dd2b415fb6efb230cb1f`.
- Accepted-main interface baseline remains `56f8ab12f21ab91030ffe54de96520fcd979dc04`. Current Task1 code and test claims are outside this narrow review.

R1 is resolved: known local settings sources are concretely enumerated, inspection is restricted to relevant update-control env keys, evidence remains private/sanitized, source fingerprints are checked immediately before launch, and observed conflicts/unreadable relevant local sources block. In the absence of an observed conflict the guarded mapping may proceed under the original managed-policy boundary. The text explicitly excludes universal remote/future-policy proof, new hypothetical attestation and an absolute OS/update guarantee. These requirements are practical without changing global/auth/model/telemetry settings. No additional local settings scan, Claude process, model or mutation was needed for R2.

The previously verified official environment-variable/settings sources support both the child-only update control and acknowledging later settings precedence. Removing the force override rather than assigning an assumed false value remains sound. The plan carries the helper's exact preservation/alias/token tests and binds Task3 runtime hookup to the scoped preflight. No remaining narrow specification blocker. Development review must verify this behavior and its failure paths; this verdict does not establish runtime effectiveness or pilot acceptance.
