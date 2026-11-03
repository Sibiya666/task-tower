# Typed transient SQLite sidecar review

Independent scoped security/function review, 2026-11-02. Verdict: **ACCEPT the three-file typed transient correction within its stated scope**. This is neither whole-branch development acceptance nor testing-stage, PR, main, or postmerge acceptance.

Reviewed against HEAD `a569285d1966e53a5abe52a8b7f368d43321cc75`, base `56f8ab12f21ab91030ffe54de96520fcd979dc04`, and freeze `runtime-task7-transient-zero-freeze.json` SHA256 `5371243c87f1e0480ae831913855fcf7f2e549f1a001d7ee148179c5b26ca313`. Frozen raw/canonical hashes matched at review entry:

| File | SHA256 |
| --- | --- |
| task_tower/executor.py | 1bfda46856c3137f78052aa52779b2c634f859c0ce53df9355cec5dfbdc0d801 |
| task_tower/pipeline.py | 1cef4c7dcfc86247e396f0bab3b11199f687db275d87b63e4d2eee6b39e70a0e |
| tests/test_safe_config_race.py | ec68ffff21642f49dcb5a20fe7aa9e5889c32e8929a7993725729733149e4f69 |

Read repository AGENTS, stage-pipeline specification/plan, review-verification guidance, actual diff and both callers. `_paths` remains strict by default. Only explicit, member-bound `-journal`, `-wal`, `-shm` paths with their base present can take the exception. Both CLI callers derive these lists from their actual DB arguments; config, request, result, host-result and main DB inputs do not receive a role merely from their filename. Pipeline dispatch DB is included as a strict input and its three derived sidecars are explicitly typed. The zero-link branch requires an originally regular, non-reparse snapshot and checks the current leaf without following links; current hardlinks, directories and reparse points remain rejected. Collision and checkout containment checks remain active.

## Independent verification

Ran Python standard-library unittest with `tests.test_safe_config_race tests.test_executor_adapter tests.test_pipeline_cli tests.test_pipeline_inputs -v`: **49 tests, 35.178 seconds, OK, two platform skips** (unavailable symlink creation and POSIX executable-mode transition). No full-suite or six-role execution was used during concurrent worker/journal work.

Retained a focused rerun log for the first three modules: **29 tests, 0.925 seconds, OK, one symlink-creation skip**, private `runtime/transient-zero-independent/unit.log`, SHA256 `92ae8c2132230798c2e0a48bd34adcb5afcb220e5996fd41ef7cf8fbc8162bb3`.

Created a separate private probe at `runtime/transient-zero-independent/probe.py` outside the checkout. SHA256 `86c74f023e432caf8effa6019c4386e6fc094da1bbf036f2cdd313440a43bc86`. Result JSON SHA256 `623134d3e24a80bde27e0acdfbfd1b91e4b313162f76e965241f4b3e36aef3d6`. Its 17 assertions passed on Windows. The probe obtained actual `os.fstat` metadata from an open file after real deletion using a delete-sharing Windows handle, asserted regular-file type and zero links, and injected that unchanged snapshot only at the following-stat seam. This is a deterministic observation-seam test, not a spontaneous kernel-race reproduction.

The typed sidecar accepted this genuine removed-file snapshot; strict default rejected the same snapshot. None/bool/dict/string role containers, None/bytes role members, main-file role, unrelated role, missing base, duplicate paths, checkout containment, a current hardlink replacement, and a real Windows directory junction all remained rejected. Author tests separately cover the three sidecar suffixes, removed-directory snapshots, suffix-named strict inputs and all sidecar hardlinks.

The supplied real SQLite churn summary was inspected separately: final guard records **4,652 commits, 11,612 checks, 84 real zero-link sidecar observations and zero unsafe failures**. This is author diagnostic evidence, not an independently repeated churn experiment. Its reported old-guard comparison contains 28 unsafe failures. The deterministic independent probes above support the narrow interpretation of that result.

## Residual scope and acceptance limits

No blocking security/function finding in the frozen three-file change. Adjacent unchanged guards in `PipelineJournal._safe` and `ExecutionQueue._safe` still reject zero-link sidecar metadata. Independent probes reproduce those strict rejections using the same genuine removed-file snapshot at each stat seam; their own forbidden-input guards also retain `exists()`/`stat()` races. These are residual liveness candidates, reported to the coordinator before this verdict, not proof that real churn reached each guard or caused any recorded CI failure. Follow-up work requires its own freeze and acceptance; this review does not cover concurrently changing worker/journal files.

The original macOS early `policy_revoked` failure remains **unproven** as to cause. This review does not replace fresh exact-head CI, whole-diff independent development/testing acceptance, or serialized PR/main/postmerge barriers. It does not claim all filesystem races are fixed, descriptor-level immunity to hostile concurrent replacement, or unattended readiness.
