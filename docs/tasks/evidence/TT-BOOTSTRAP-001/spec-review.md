# TT-BOOTSTRAP-001 independent specification acceptance

Verdict: APPROVE

Reviewer: bootstrap-spec-reviewer (independent agent instance)
Date: 2026-11-01
Scope: specification and implementation plan acceptance; no implementation, runtime, CI, merge, or postmerge acceptance is implied.

Reviewed:
- `docs/superpowers/specs/2026-11-01-bootstrap-harness-design.md`
- `docs/superpowers/plans/2026-11-01-bootstrap-harness.md`
- Repository `AGENTS.md` and parent agent-development architecture for scope alignment.

The specification defines a testable after-clone flow: Python prerequisite with thin launchers, Windows/macOS/Linux detection, explicit Codex/Claude Code/OpenCode/custom selection, executable validation, persistent local selection, and deliberate reconfiguration. Interactive and noninteractive launch behavior is distinguished; dry-run and configure-only have clear side-effect boundaries. Overlay is optional and Windows-specific rather than a dependency of common bootstrap.

Superpowers delivery is concrete: a real SKILL.md, an explicit or discovered path, a pinned content hash, refusal on silent version changes, and generated initial context without overwriting project instructions. The specification correctly distinguishes delivering instructions from proving that a harness followed them. Custom adapters are explicitly selected executable configuration with argv-based execution and limited advertised capabilities.

The dogfood task is honestly scoped as a file-backed pilot adapter. Ordered independent spec/development/test/postmerge acceptance, evidence hashes and revalidation, distinct executor/reviewer IDs, and a main-ancestry requirement are specified. The task remains awaiting_merge before actual integration; no queue service, authenticated reviewer identity, automatic dispatch, automatic merge, night readiness, or completed production task-manager loop is claimed. The plan preserves these boundaries and requires actual stage evidence.

No blocking specification gap found for this bounded milestone. Implementation review must independently establish that these requirements hold; this approval does not certify their implementation.

Minor clarification recommendations (nonblocking):
- In onboarding documentation, show one exact first-run command including the required Superpowers path and explain the recoverable missing-tool/skill path.
- State explicitly that a postmerge evidence report should name the reviewed main commit and resulting checks; main ancestry alone does not demonstrate that the intended implementation was reviewed.
- Preserve the documented limit that reviewer IDs are organizational assertions and local evidence hashes are freshness checks rather than an authenticated CI gate.
