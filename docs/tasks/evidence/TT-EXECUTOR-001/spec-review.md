# Independent specification acceptance — TT-EXECUTOR-001

Verdict: **accepted** for implementation against the stable inputs below. Reviewer: independent `executor_spec_acceptance` instance; implementer/coordinator is a different instance. Review date: 2026-11-01. Base: `9ba02c2f207c4f2664331774ad39314ab0d51b3e`.

Reviewed full design and plan against repository instructions and continuous/parallel process. No remaining specification blocker. This accepts the specification/plan only; implementation, tests, exact-head/base PR acceptance and exact-main postmerge acceptance remain separate gates.

Two routine clarity corrections were made before acceptance: delayed jobs revalidate current authority, lifecycle, identity and verified dependencies before preparation/launch; local recovery excludes concurrent claim and cannot fence positively live owners. Claims enforce a fixed approved active bound (default two), conservatively counting unknown ownership. This guard is not the future pool scheduler. Approved checkout/ref policy determines source; Issue text cannot choose executable or authority.

Coverage reviewed:

- Immutable six-field dispatcher protocol, durable transaction-before-ack admission, UUID collision rejection, read-only lookup, owner-bound claims, restart uncertainty and no blind retry.
- Isolated exact-source worktrees; installation-owned profiles/private paths; pinned Superpowers content; host-token resolution fix without weakening verified_done; child/probe token stripping and explicit trusted custom-process boundary.
- Existing process API compatibility, Windows Job/POSIX group cleanup, bounded cancellation polling, bounded private logs and honest cleanup uncertainty.
- Strict run/attempt/source-bound output validation, no completion from exit code alone, explicit bounded retry only after proved no-child failure.
- Installed Codex safe invocation and optional saved auto-review, capability claims tied to actual evidence, opaque events and unsupported resume absent verified round trip.
- Issue #16/#18/#19 scheduling/stages/distributed ownership and #17 publication remain outside this implementation; no execution result marks a task done.
- Separate #22 ownership, serialized integration, fresh exact-head/base acceptance, exact-main CI/independent acceptance/automatic closure preserved.

No product code or remote state changed by this review. No test run is claimed for implementation that does not yet exist. `git diff --check` passed after review edits. Runtime dependency #14 evidence is an operator/coordinator prerequisite, not newly established by this documentation review; its signed/head-bound verification remains mandatory.

Canonical source manifest: SHA-256 over decoded UTF-8 text with LF newlines (BOM excluded). Stable process/spec/plan only; mutable task cards and this evidence document are excluded to prevent self-reference. Any change to a listed source invalidates this acceptance until independently re-reviewed.

```json
{
  "docs/development-process.md": "d13da41354b40b706d14cdc44c57569c8914500e5f8ba870c7aeadaac3c2bcf0",
  "docs/superpowers/plans/2026-11-01-noninteractive-executor.md": "58f07c73799d58b4b750ba5c0860aab396287cbcea2717c8bc2bc811a322ecf4",
  "docs/superpowers/specs/2026-11-01-noninteractive-executor-design.md": "164ecd8a3c9ec73fab45cf30d4e7ae240eca12cb6d05104d7907f67ab53d4440"
}
```

## Superseding CLI-contract review (2026-11-01)

Verdict remains **accepted** after independently reviewing the required private connections input. Adapter/work require `--connections`, `--config`, and `--queue`; status/cancel require `--connections`, `--queue`, and `--run-id`, without executable profile/pin prerequisites. Existing connections supply repository identity and trusted publishers for verified dependency checks. Revoking an execution profile cannot prevent cancellation. This is reuse of existing authorization, without new scopes or profile-schema keys.

This current manifest supersedes the initial spec/plan bindings (spec `ccabf4f38bd410b1ffa8bf8d43c90a5a521b6564e0b9d17c089cc9797bdb21a1`, plan `a80c5f6f4b5f110b662fd6190625718fc35772ab5b51a801f050149f91fc6875`). The earlier accepted review remains historical evidence, not acceptance of subsequently changed content.

`AGENTS.md` was read as a historical policy-context snapshot with canonical digest `2def3a2d24f1c38a384a266bdc29c9fd0f712b0976a7e1ef98478ddd06b12410`; it is deliberately excluded from the current stable source manifest because integration updates its capability notes. Its continuous/parallel authorization and independent acceptance requirements remain applicable. A substantive policy change requires review; ordinary current-capability documentation updates do not pretend to match that historical digest. Final implementation/PR review must inspect the actual current instructions.
