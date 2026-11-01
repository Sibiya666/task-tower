# Task 6 independent specification clarification review

Verdict: **accepted within the Task 6 design boundary**, 2026-11-02. Reviewer: fresh independent `/root/pipeline_task6_spec_review`, distinct from the author. No blocking findings remain in the reviewed clarification. Builder check: nothing important left within this boundary.

## Exact reviewed bindings

Reviewed the complete working-tree document diff against HEAD `62fd437afeac079aacc0177cd4a9710558ae8c80`, repository AGENTS, original/R1 spec-review evidence, implementation ledger, Task 4 review and existing host authentication/environment/controller seams. WIP publication code is outside this review. No product source was changed or accepted here.

| File | Raw SHA256 | Canonical SHA256 |
| --- | --- | --- |
| docs/superpowers/specs/2026-11-01-stage-pipeline-design.md | 68f611b225dbb412f3f136f8da1f38b1e217378703fe25a04640580686e6a4db | 68f611b225dbb412f3f136f8da1f38b1e217378703fe25a04640580686e6a4db |
| docs/superpowers/plans/2026-11-01-stage-pipeline.md | 107b4f89406dd2c9a3ba1962294f2472d83c335579a9786c3c0a044d3f4882b2 | 107b4f89406dd2c9a3ba1962294f2472d83c335579a9786c3c0a044d3f4882b2 |

Independently recomputed with installed Python after the final correction. Canonicalization is strict UTF-8, CRLF/bare CR to LF, preserving all other bytes/content. Changing either document invalidates this scoped verdict. The earlier proposed plan `4040e12c06237ab148c053fb21f0a98afbb7f1fbd32ed041fcc199fd00fd5c6f` had a contradictory global all-children stripping sentence; the author corrected it before this final binding. It is not the accepted plan.

## Findings and preserved contracts

The host/model distinction is coherent. Existing github_source.resolve_token explicitly reads GH_TOKEN/GITHUB_TOKEN before existing credential helpers. Stripping those keys from fixed trusted host API workers breaks environment-only installations. Inheriting them intentionally exposes existing credentials to these trusted host CLI processes; this review does not hide that exposure or describe containment as a credential sandbox. The exception is limited to fixed contained host worker/dispatcher invocations, grants no scopes and stores no credentials. Model roles, custom adapters and configured checks still use case-insensitive child_environment stripping. Host workers must not forward raw environments to them. Safe Git child filtering and separate Git transport authentication remain unchanged. Credentials remain prohibited in argv, JSON, configuration, logs and artifacts.

The slow genuine dispatcher/source operation belongs in a cancellable fixed helper through the existing runner. That preserves genuine source/dependency verification while permitting the main watch loop to observe cancellation and completed workers within the existing five-second cleanup budget. Helper results remain bounded neutral identities/status/digests, without raw Issue bodies. Committed dispatcher intents remain lookup-only, never resubmitted because a helper failed or disappeared.

Journal-owned singleton claim/heartbeat/release/read-only health APIs complete the already specified controller responsibility and existing controller table. Actual owner UUID/PID and lock proof, fixed validated health values, no caller SQL or arbitrary takeover, and no unknown-run/component release preserve the private schema and fencing design. This is additive internal orchestration scope, not a private JSON configuration extension, migration, distributed lease or second process runner.

Unchanged Task 1–5 requirements still govern private authority, immutable criteria/manifests/checkpoints, fresh independent roles and receipts, durable launch/effect intents, deadlines/budgets, actual checks, publication and unknown outcomes. Their original acceptance remains content-bound to the source/dependencies actually reviewed; this clarification neither reaccepts modified code nor retroactively proves any code. Any journal/worker changes made for Task 6 require fresh focused review and integration verification against those contracts.

## Required later evidence and limits

Task 6 is not implemented or accepted by this receipt. Real subprocess tests must prove environment-only host API authentication separately from downstream model/custom/check token stripping, and assert credentials absent from arguments/results/logs/configuration/artifacts. A keyring-only or already-authenticated installed smoke does not prove environment-only mode. Required tests also cover a genuinely slow source helper cancelled within the cleanup budget, duplicate controller claims, controller exit preserving unknown locks, genuine readiness/dependency fixtures and no delivery resubmit after intent. These are requirements, not passing test claims.

No product tests were run for this document-only review. Shared AGENTS/runtime wording still contains historical blanket child-stripping language; the coordinator must reconcile it to this precise host exception under Task 7 before final integration. This is documentation follow-through, not permission to weaken role stripping. Full suites, three-OS CI, actual Task 6 implementation review, installed-runtime limitations, whole-PR exact-head/base acceptance, serialized main/postmerge acceptance and automatic closure remain required. No commit, push or external write was made by this reviewer.
