# Task 3 independent review — first frozen implementation

Date: 2026-11-02. Verdict: **REJECT — one Important (P2) finding**. This is Task 3 review, not whole-Issue acceptance, PR acceptance, test-stage acceptance or main acceptance. Reviewer is distinct from the implementer. No product edits, commits, pushes or remote writes were performed by this reviewer.

## Scope and identity

Read repository AGENTS.md, the complete `docs/superpowers/specs/2026-11-01-stage-pipeline-design.md`, complete `docs/superpowers/plans/2026-11-01-stage-pipeline.md` and implementation ledger rulings 1–11. Applied Superpowers requesting-code-review and verification-before-completion guidance. Reviewed the entire actual additive harness diff plus complete new role runner, role tests and subprocess fixture, with the accepted policy/journal/input and existing process-runner seams. Starting HEAD: `f1f4f265f2c5d82e20569a78b181e2ea739ee747` (Task 2 accepted; Task 1 `1bc1aa4`). The four Task 3 files below are uncommitted review inputs; this verdict binds their content, not a prospective commit.

Raw SHA-256 and `sha256-utf8-lf-v2` canonical SHA-256 were independently recomputed after inspection:

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| `task_tower/executor_harness.py` | `d8c885c0287958459eda6e2eab98964e30b99e56d9a0b151326c2d544c806682` | `d8c885c0287958459eda6e2eab98964e30b99e56d9a0b151326c2d544c806682` |
| `task_tower/pipeline_roles.py` | `225749eaa63c7d889b77eaef86dca8475e0100f36dd465affe87302a8ea610a7` | `225749eaa63c7d889b77eaef86dca8475e0100f36dd465affe87302a8ea610a7` |
| `tests/test_pipeline_roles.py` | `ec4c2ef75b755fafa8afa139a8ea51c9c8dd4ab5ac414fd8f391997a9e93cddd` | `edf0996fc0121e69f0fb0fb977d9eb4b6fad04a1d9e6e96a32322073526b5ecb` |
| `tests/fixtures/pipeline_role.py` | `c43d39cd4e04f33114083001880c0acb83cd1e539d45267a396da677793d4ba2` | `c43d39cd4e04f33114083001880c0acb83cd1e539d45267a396da677793d4ba2` |

## Important finding

**P2 — Supply trusted task paths and real stage-specific obligations to each fresh role (`pipeline_roles.py`, request construction around lines 202–210).** The request contains binding, manifest, worktree, instructions, untrusted task_data, checks, host_checks and CI policy/evidence, but never the installed `spec_path`, `plan_path`, `allowed_paths` or `evidence_dir`. Its spec/development executor instruction is identical: “Implement only the accepted stage within installed allowed paths.” Those installed paths are unavailable to the child. In particular, the initial spec executor has no accepted stage yet and is not instructed to create the specification and implementation plan at the configured destinations. The reviewer obligation only says to examine the whole actual diff; it does not distinguish specification/design/plan completeness from development implementation of the accepted plan, or identify the initial source as the development diff base. This misses the specification's stage-specific request contract and Task 3 plan requirement.

Concrete reproduction: instantiated `RoleProcessTests`, ran its real `invoke()` subprocess and read the resulting host-authored request through the returned artifact name. Invocation completed, but request keys were exactly `binding, checks, ci_substitution, host_checks, instructions, manifest, obligations, role, task_data, task_data_trust, version, worktree`; all four configured path keys were absent. The fixture merely echoes completed and therefore cannot expose a real agent's inability to determine the configured output targets. The coordinator confirmed no downstream trusted task_data contract supplies these fields. Host allowed-path enforcement is useful, but rejecting a guessed destination after execution does not provide the missing task instructions.

Required correction: add a clearly host-owned task-policy projection containing configured safe artifact/scope paths; provide role-specific obligations for spec executor (create spec and plan), spec reviewer (design and plan completeness), development executor (implement accepted plan), development reviewer (whole actual diff from immutable initial source plus accepted requirements/plan), test executor (coverage/evidence only) and test reviewer (actual host checks, independent coverage and CI limitations). Identify the accepted artifact paths and immutable diff base explicitly. Keep Issue prose labeled untrusted and keep these fields derived from validated policy. Add request-contract assertions for all six roles using nondefault configured paths, then obtain fresh review of the changed freeze.

## Fresh verification

Runtime: `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; Windows host. Independently executed:

- `-m unittest tests.test_pipeline_roles tests.test_executor_harness -v`: 32 tests, 95.874 seconds, OK.
- `-m unittest tests.test_executor_processes tests.test_reviewer -v`: 18 tests, 4.918 seconds, OK with one skip (`test_alias_capture_directory_rejected`: symlink privilege unavailable).

Combined: **49 passed, 1 skipped, 0 failures/errors**. These are reviewer executions, not the author's results. The genuine six-model-role flow uses the real journal, checkpoint generation, actual child processes, host check and receipt bindings; the focused suite exercises that flow. It substitutes source collection transport in the fixture, not journal acceptance. The targeted host-check tests additionally isolate authority/state seams and should not be mistaken for complete controller integration.

Additional independent hostile probe: wrapped `_process` to revoke `_authority_check` only after the real child returned successfully. Observed `needs_input`, reason `policy_revoked`, actual `started=True`, `cleanup_confirmed=True`; no completion accepted. A second independent real-process probe above recorded the missing request fields. Neither probe changed the frozen product files.

Inspected and/or exercised strict v2 result provenance/types/extra/duplicate/linked/oversize rejection; unchanged legacy six-key protocol; fresh process IDs and read-only Codex invocation; failed/missing/tampered result/request; capped token-stripped subprocess capture; actual source mutation even after child failure; read-only reviewer/test mutations; detached checkpoint preparation with uncertain preparation fenced; backward clock and unknown runner outcomes; replay prevention; required instruction pins; host check argv-policy binding, failed checks, mutation halting with retained not_started rows and unwritable-temp classification. Existing process tests cover cancellation, timeout/descendants and cleanup uncertainty. No second process containment implementation was introduced.

CI evidence calls the unchanged authoritative `GitHubSource` through the existing source factory, requires its verified merged bundle at the exact checkpoint and configured platforms, and rechecks returned evidence after the child. The CI test uses the real GitHubSource fixture, including rejected forged task IDs/failed checks/wrong checkpoint/platform. No invented CI validator grants success. An unpublished checkpoint normally cannot satisfy this source. This review makes no live GitHub CI claim.

## Later integration seams and limits

Task 4 must freshly validate authority, source/checkpoint/artifacts, prior receipt and check manifest before receipt persistence; route actual product/test mutations through bounded development rework; distinguish failed process, timeout, cancellation, environment-unavailable and unknown cleanup; retain all first/stale rejections; and never convert a neutral reviewer needs_input into approval. The run_role completed transport outcome is not a stage decision. Task 4 must preserve dead-owner/intent fencing and persisted budgets across steps. Task 5 publication and Task 6 watch/dispatcher integration are future work and were not demanded as Task 3 functionality.

No full-suite, three-OS CI, installed-Codex pilot, production publication, unattended execution or PR/main acceptance is claimed by this scoped review. Existing unrelated runtime files were preserved. Any change to the four frozen inputs invalidates this review and requires a new content-bound review; preserve this rejected verdict in history.

## R1 independent re-review — current Task 3 verdict

Date: 2026-11-02. **ACCEPT Task 3 R1 at the exact file bindings below; no outstanding blocking findings in this scoped review.** The original rejection above remains historical evidence and is not rewritten. HEAD remains `f1f4f265f2c5d82e20569a78b181e2ea739ee747`; these are the actual uncommitted frozen Task 3 inputs, not PR/main acceptance. Same independent reviewer, with no product edits, commit, push or remote write.

Independently recomputed raw and `sha256-utf8-lf-v2` canonical hashes:

| File | Raw SHA-256 | Canonical SHA-256 |
| --- | --- | --- |
| `task_tower/executor_harness.py` | `d8c885c0287958459eda6e2eab98964e30b99e56d9a0b151326c2d544c806682` | `d8c885c0287958459eda6e2eab98964e30b99e56d9a0b151326c2d544c806682` |
| `task_tower/pipeline_roles.py` | `48b32dcb1ec09b70d09ec7d5e77ffb4dae0b7c5048450cd9bb178fa63e8ba5a6` | `48b32dcb1ec09b70d09ec7d5e77ffb4dae0b7c5048450cd9bb178fa63e8ba5a6` |
| `tests/test_pipeline_roles.py` | `41ae1b010100e6e3b7317a0fb6a394b392298789604709a525cb5553ba372c66` | `0d622655c7bcd6b4e0bc26ef600bfc43f0de478ae804bd0dbf76e7eb6786c50d` |
| `tests/fixtures/pipeline_role.py` | `15c51d838c0bd8bfa97f2bc73dc3bf1d25c708fc0c63eabfbb846a012a323d24` | `15c51d838c0bd8bfa97f2bc73dc3bf1d25c708fc0c63eabfbb846a012a323d24` |

Re-read the full current role runner and fixture, new request/negative/real-flow test changes, unchanged full harness diff, and confirmed applicable ledger rulings remain 1–11. The P2 is resolved: every request now contains a host-authored `host_task_policy` with exactly `spec_path`, `plan_path`, `allowed_paths`, `evidence_dir`; its allowed-path list is copied from validated installation policy. `diff_base_sha` is the immutable run source SHA. Untrusted Issue data remains nested and explicitly labeled; it cannot overwrite the top-level projection, obligations or diff base. Host request hashing detects a child changing the projection. Existing fresh saved-policy authority checks remain in place.

The six obligations now separately require creating/revising configured spec and plan, reviewing their design/plan completeness, implementing accepted artifacts, reviewing the complete actual development diff from immutable initial source against accepted criteria/spec/plan, auditing configured coverage with private evidence only, and independently reviewing actual checkpoint-bound host checks and coverage with explicit CI limitations. The original report's Task 4–6 seams and limitations still apply; this change does not delegate acceptance to model prose or add publishing authority.

Fresh reviewer command, using the same absolute Python runtime noted above:

`-m unittest tests.test_pipeline_roles tests.test_executor_harness tests.test_executor_processes tests.test_reviewer -v`

Actual result: **53 tests in 86.938 seconds, OK (skipped=1): 52 passed, one skip, zero failures/errors.** The skip remains symlink privilege unavailable. This reviewer run includes the genuine six-role/real-journal/host-check/receipt flow with nondefault configured paths (`docs/architecture/design-a.md`, `docs/implementation/plan-b.md`, `docs/host-proof/`) and assertions on every serialized role request, role-specific obligations and source base. It also includes new real-process request-projection tampering and Issue-data spoofing regressions, plus saved private path-policy byte drift rejecting before launch with process_count zero. Legacy protocol, process containment and existing reviewer compatibility checks passed in this same fresh invocation. No historical author full-suite output was counted as this evidence.

Additional reviewer mutation check, without editing source: intercepted the serializer to omit `host_task_policy` and `diff_base_sha` from the role request, then called the real six-role regression. After the first actual child, the regression failed with the expected `KeyError('host_task_policy')`; the probe asserted that failure and exited zero. This proves the added request assertions detect the original missing-contract defect. The normal unmodified six-role regression passed in the full fresh command above.

This is Task 3 acceptance only, bound to the four R1 hashes. No full-suite/three-OS CI/installed-Codex pilot/PR/main acceptance claim is made. Any subsequent implementation-content change requires fresh review; retain both this R1 verdict and the original rejection.
