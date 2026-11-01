# Independent specification acceptance — TT-DISPATCH-001

Verdict: ACCEPTED for implementation. Reviewer: dispatcher_spec_acceptance, distinct from the specification author and future implementers. Scope: design and implementation plan only; this is not development/test/PR/postmerge acceptance.

Reviewed against repository AGENTS.md, GitHubTasks metadata/list/get contracts, project_worker.issue_lifecycle and verified_done, and the authorized Issue 14 boundary. Managed request/result files reuse the existing subprocess lifecycle; no stdin or process-group changes are required. No production files changed.

Resolved before acceptance: canonical owner/repository#N dependencies match existing backlog; malformed source blocks its project while malformed individual metadata excludes only that task; separate bounded submit/lookup workloads and durable lookup fairness; config/journal path aliases; final pre-send revalidation and remaining GitHub race; untrusted receipt sanitation; reconciliation requires current allowlist, healthy identity source and unchanged backend even when readiness changes.

Authority remains private allowlist plus autonomous task metadata. Fresh dependency proofs, atomic committed unknown intent, permanent no-resubmit recovery and read-only lookup remain explicit. Dry-run/status cannot write or execute; dispatcher cannot mutate GitHub or claim to implement Issue 15 development execution. No unresolved specification blockers.

Canonical manifest scheme: sha256-utf8-lf-v1. Decode UTF-8, normalize CRLF and CR to LF, encode UTF-8 without BOM, SHA-256 bytes. Only the following stable source documents are bound; mutable task cards and evidence (including this file) are excluded to avoid self-reference.

- docs/superpowers/specs/2026-11-01-issue-dispatcher-design.md: 25650b8545c364d5aa80fa2732e44ea3b6285151e540c9dd0315c6c396d0e36b
- docs/superpowers/plans/2026-11-01-issue-dispatcher.md: fb18a98a61898cd6e0d0c314167e98170783a3d06e06bddaf2ac55faf2538d2c
