# Pipeline implementation rulings

These coordinator rulings fix inter-module names within the accepted design. They do not grant authority to task data, change the private JSON schema or replace independent review. Task reviewers must inspect them alongside the specification.

## Ruling 1 — normalized policy and journal admission

Normalized task rows preserve the exact thirteen specification keys; components remains components. A trusted adapter derives journal.submit policy with exactly profile_id, profile_fingerprint, policy_sha256, component_keys and limits. Limits contains task_timeout_seconds, max_reworks, max_processes, role_timeout_seconds and log_max_bytes from validated private configuration. Initial Issue ID, criteria, source/base, branch/worktree/checkpoint and admission remain null until fresh preparation; delivery data cannot select them.

The journal persists admission evidence once without conflicting value/type replacement. Its exact keys are version (1), repository (casefolded), issue, issue_id, task_id, runner_label, criteria, criteria_sha256, policy_sha256, profile_id, profile_fingerprint, source_sha and base_sha. Policy creates it only after genuine initial readiness, dependency verification and authoritative current-main/source-ref agreement. Mutable status and model flags are not evidence.

## Ruling 2 — private continuation authority

Host runtime supplies _authority_check, _journal and _owner_id as internal objects/values, never accepted JSON keys. The authority hook is required for admission and continuation and rechecks saved connections, pipeline and executor-config bytes. Validated profile fingerprint and instruction pins are also rechecked.

Continuation reads actual journal.status(run_id) and compares immutable run/delivery/repository/Issue/task/runner/profile/policy/admission bindings and exact owner against the host owner ID and supplied run. The state must remain owned and nonterminal. It then validates fresh Issue criteria, private policy, lifecycle revocation/foreign ownership and real dependency receipts. A task cannot mint ownership by copying UUIDs or an admission dictionary into metadata.

Initial admission continues to call select_ready unchanged. Continuation may use a local exact dependency resolver following its validated qualified-reference/task-ID reconciliation, fresh dependency get and unchanged verified_done. It must not forge store.metadata or lifecycle status to trick initial readiness.

## Ruling 3 — scope and schema interpretation

ci_substitution is a required task-row key with an exact object; its disabled default describes the default value rather than permission to omit a required key. Existing executor allowlist membership is required and is not itself duplicate execution ownership. CLI/watch validates saved dispatcher backend/journal scope because load_pipeline_config does not receive those paths. No claim of arbitrary cross-database or cross-host mutual exclusion is permitted.

Checkpoint/journal interfaces may add private host-bound git_dir, branch and worktree evidence under the accepted immutable preparation rules. No value may be supplied by model output. Tests and independent Task1/Task2 reviews must verify these seams and record any further ruling before integration.

## Ruling 4 — local proof versus external freshness

The journal constructor has no network hook. It enforces exact persisted owner/input/generation, immutable host manifests, actual attempt launch/result/exit/cleanup, reviewer independence and history gates. Task4 apply_verdict must revalidate external policy, Issue/dependencies/current main and actual product/checkpoint immediately before persistence. Valid old-input verdicts with genuine historical process proof remain immutable superseded history, returning superseded=true; they never satisfy a current acceptance gate. Invalid forged process evidence is rejected.

## Ruling 5 — output generations and configured host checks

An executor consumes generation N and its normal output can create reviewer generation N+1 without spending rework. A completed checkpoint effect explicitly links contributing_executor_attempt_id. The current reviewer must bind the exact output checkpoint and latest eligible completed same-stage executor, with no intervening reject/reset/later contributor. A changed previously accepted input follows the bounded stale/rework rules.

Configured checks use host-only attempt role host_check in test/checking, not a seventh model role. Its binding additionally requires check_id and canonical configured check_sha256. Existing six model role schemas remain unchanged. The host writes private request/result/process artifacts, counts and persists launch before invoking the existing runner, and binds actual cleanup/exit and source unchanged proof. A model result cannot supply this evidence. History gates require current nonsuperseded receipts and actual completed publication observations, never an arbitrary status transition.

## Ruling 6 — final host evidence seam

A publisher may pass an ephemeral task-policy copy with _host_evidence mapping exact safe Markdown paths to canonical hashes. This is never an installed JSON key or model-provided authority. Ordinary role input validation rejects evidence changes. The publishing freeze only accepts the exact host-attested BOM-free <=1MiB files under the configured evidence directory and includes them in its private index while preserving the accepted product digest. All stage/history/owner gates still apply.

The private projection manifest is canonical JSON {version:1,run_id,task_id,product_sha256,files:[{path,scheme,sha256}]}, with sorted public Markdown entries; it excludes itself and cards. Its digest binds final freeze. The private JSON is not published. Task5 derives actual evidence from journal-accepted receipts rather than accepting model prose or mutating the normalized policy.
