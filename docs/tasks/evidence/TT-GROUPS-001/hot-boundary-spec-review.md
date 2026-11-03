# Independent Issue18 hot-availability amendment review

Reviewer: /root/fetch_timeout_diagnosis

Verdict: ACCEPT the exact dated specification/plan amendment below for Task3A's limited cold-migration/hot-refusal deliverable. This is fresh specification acceptance, not acceptance of the frozen implementation, its32-test result, original-file hot recovery, full Issue18 or night readiness.

## Bound documents

| Document | Raw SHA256 | Canonical UTF-8/LF SHA256 |
| --- | --- | --- |
| task-tower-capture/docs/superpowers/specs/2026-11-02-agent-groups-design.md | 4195eb058411d3326011bd426fbcf30beb7f5423aaad43e8285d4efc97dc13a9 | 3748301bf4b13364b02bb65b223732ecf16d5fc72ed8c94a6c1f65712a998772 |
| task-tower-capture/docs/superpowers/plans/2026-11-02-agent-groups.md | f7546fcfd822541956f01d5458298400adee2238aacc0b079ca5867930daded7 | 739504836c2ae5d5a9ecea80fd9ddc05a4627223f479e93c0a8cfc34356328b1 |

Prior independent technical review: runtime/groups18-hot-recovery-design-review.md raw SHA256 fd34e05a87b85a38aa96a8bf430cd95e8e851e5d060a9dc80cd34ee11d676c24. The amendment selects its Option A; it does not approve Option B/C as original recovery.

## Assessment

The new design and plan accurately acknowledge the genuine cache_size1/spill precommit RED. They explicitly supersede the earlier unconditional cold-readonly-reopen promise with SQLite-recoverable logical v1 atomicity, without pretending the unresolved automatic recovery has passed. The old32-test failure and qualifications of prior30/135 green evidence remain required history.

The operational branch is narrow and fail-closed: only actual chained SQLITE_READONLY_ROLLBACK776 during first existing-only readonly inspection may produce exactly {status:"recovery_required",version:null}. It establishes no accepted source catalog/version/owner/cleanup. Both inspect and apply preserve original J and all sidecars without writer, backup/directory, DDL, registration, initialization, reset or release. Non776 errors remain outside this branch. Existing identity, alias, WAL/super-journal, corrupt/newer/foreign and deadline refusals remain binding. This matches the independently reproduced fact that RW/query_only can modify a foreign hot DB before host recognition.

Cold lossless migration, existing17-new-table/3-index representation, immutable original rows/sequences, typed legacy fences and postcommit complete-v2 reopening remain required. A diagnostic rollback of an isolated disposable fixture clone is evidence of that fixture's logical recoverability only; it cannot authorize original writes, hidden repair or runtime claims.

The current-version dependency is explicit, rather than a test waiver or platform deferral: [Issue65](https://github.com/Sibiya666/task-tower/issues/65) remains mandatory before full Issue18/main completion and night readiness. Independently read Issue65 via GitHub: open, milestone2, titled groups: recover interrupted migration without mutating unqualified SQLite files; its body identifies it as current Windows subtask18 and requires an independently accepted recovery boundary plus genuine hot-crash/foreign/identity/deadline/crash proofs and exact-main automatic closure. The body is consistent with the amendment; no closed/recovered status was inferred. Native hierarchy/Project membership is coordinator-owned bookkeeping and was not mutated by this review.

Copying a clone/backup over J, deleting/truncating the hot journal, generic RW fallback, operator/model attestations, immutable/nolock shortcuts and runtime _recover_existing are expressly prohibited. A later original-recovery design still needs uninterrupted pre-first-mutation physical exclusion/current source/owner proof, with no claim that a shadow hash closes TOCTOU.

## Implementation and evidence requirements

The frozen Task3A code remains unaccepted until a distinct implementation/test review. New meaningful tests must create real spilled own and foreign hot pairs, make RO inspection the first SQLite access, assert exact recovery_required/version:null and byte-for-byte source/sidecar preservation, and prove no RW/backup/DDL/claim or accepted version/owner outcome. Non776, missing/replaced/aliased files, foreign schema with Task Tower appid, corrupt/newer and unsupported sidecars remain negative cases. Keep genuine after-commit v2 and cold lossless/backup/deadline/provenance tests; do not revert to the former cold cache-only crash fixture or read RW before the assertion.

Root should record a new hashed spec-stage receipt binding these exact two documents, retaining prior accepted-main/R3/R4 and hot-failure evidence. The amendment authorizes this limited implementation/test change only. Do not close Issue65, full18, or report original hot recovery/night readiness based on refusal tests. Re-audit actual accepted main after the current63/PR64 postmerge barrier clears; this amendment does not promote an unaccepted source base.

No product code, Git state, native/auth/probe, live DB or runtime state was changed; only this review report was written.
