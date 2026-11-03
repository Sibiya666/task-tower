# Independent Task3A frozen candidate review — 2026-11-03

Reviewer: /root/groups18_task3a_acceptor, distinct from implementer. Verdict: **REJECT / fixes required** for bounded Task3A storage acceptance. No source or Git state changed.

## Identity and scope

Checkout task-tower-capture, feat/agent-groups, four uncommitted candidate files. Accepted Issue16 foundation is main4875381be68282a7ad77ab7b1c5a3898cbc09304; its closure receipt is https://github.com/Sibiya666/task-tower/issues/16#issuecomment-6595253516. Later7586df4 is not admitted by this review; coordinator must complete exact-main acceptance and affected-interface re-audit first.

Frozen raw SHA256s independently recomputed and matched:

- task_tower/pipeline_journal.py: 149a892251990e26d7ca18abdcf7cf4cea4b2f1561cf9afe29b16e9a6fe5cf88
- task_tower/pipeline.py: 2c431e5bfa7d090fd0b373539965227da938f785c1942b3ff9e33f57b83d8f82
- task_tower/group_storage.py: f804699f00acd8bb6cb63620deb31497d7f4ac2972430f9e6a19d26c5a71d58b
- tests/test_group_migration.py: 12f63af8f20c392dfb1132996ef2267f2b7277cabb009bb9ba50d999cd743e7e

Read repository AGENTS and applicable review/verification/debugging skills; inspected actual tracked diff, the new storage/test files, relevant surrounding legacy claim/shutdown/CLI code, full representation and R3/OptionA requirements. The accepted hot-boundary spec review f361b60786c69be334e49a82994b26e1d2b6652d61e136bcde1d9db066c92fbf qualifies only cold lossless migration, complete cold v2 reopening and untouched-original hot refusal. Issue65 remains mandatory current Windows recovery work. No whole18/PR/main/native resource pilot/night acceptance is granted.

## Strengths and independent verification

Using actual Python C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe with PYTHONPATH=tests, ran `-m unittest test_group_migration -v`: **45 tests,16.190s,OK**, exit0. Root owns the separate full-suite run; no result from it is inferred here.

Independently extracted the spec's SQL block, executed it and implementation DDL in separate in-memory SQLite databases and compared exact sqlite_master type/name/sql sets: equal. Original six-table SCHEMAS digest is unchanged5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6; target catalog digest1e1e250b953b7166b481f9b52d9fa9a4ed1c6fa9454cd279600f51502315c96a, with17 additive tables and3 indexes.

Additional reviewer fixture checks passed: manually raise old events sqlite_sequence to777, then migrate and compare the entire semantic legacy dump including sequence (exactly preserved); inject _make_fence ValueError during a genuine preG legacy claim and verify actual transaction rollback restores all original rows and leaves zero reservations/actions/leases. No real user journal was used.

The genuine cache_size1/spilled hot tests run first RO access, instrument refusal of writer/backup/runtime recovery/claim, and verify exact neutral report plus unchanged bytes/directory. Cold backup, no-clobber, writer/commit contention, physical replacement/noncreation, alias and unsupported sidecar tests pass. There is no RW/query_only fallback in the new migration path; migration guards are separate from generic legacy status behavior. Existing shutdown4.8s code is outside the actual diff. Registered-G/execution tables are deliberately refused until later consumers exist; SQL constraint fixtures do not authorize runtime registration.

## Blocking finding [P2]: migration provenance is self-consistent but not bound to its authoritative saved boundary

Location: task_tower/group_storage.py:492,515,537-543 (validate_v2), with _preserved_history at327.

The validator retains and validates the migration event's immutable legacy_snapshot, but then independently validates each origin observation against current immutable identity/history. It never compares an origin of kind migration to the exact run row and per-run ordered history in that saved migration snapshot. Mutable historical run fields, including original owner/PID/state/input, therefore have no independent anchor. The expected origin is reconstructed from the same possibly altered boundary body. observation_kind is copied from origin itself and merely checked for membership in three strings, permitting an actual later legacy claim to masquerade as a migration observation and vice versa.

Concrete reproducible fixture results are preserved in runtime/groups18-task3a-independent-counterexamples.py and .log. Run from workspace root with the exact Python above. It changes only disposable fixture databases, preserving original runs rows and migration event/snapshot. Four current outputs:

```
migration_owner_mismatch UNEXPECTEDLY_ACCEPTED
postmigration_claim_mislabeled_migration UNEXPECTEDLY_ACCEPTED
migration_mislabeled_legacy_claim UNEXPECTEDLY_ACCEPTED
invalid_origin_timestamp UNEXPECTEDLY_ACCEPTED
```

The first creates a genuine dead_unknown migration, increments only observation.run_row.owner_pid by100000, updates action.origin.original_owner_pid and original_run_row_sha256, and recomputes the affected origin/observation hashes. status() still accepts although saved migration snapshot and actual original runs preserve the different real PID. An earlier independent run specifically accepted194140->294140. The second starts queued, migrates, makes a genuine legacy claim, then changes just its origin kind to migration and recomputes linked hashes. The third relabels actual migration origin as legacy_claim. These are inconsistent retained evidence, rather than a hypothetical fully forged database with every anchor changed. R3 explicitly requires recognized migration/reconciliation provenance and digests of genuine original run/history at that boundary; self-consistent hashes are insufficient.

Required correction: retain the independently validated migration snapshot and derive a run_id-keyed original run row plus ordered per-run history from it; bind every initial migration origin to exact equality with that authoritative boundary and metadata-derived migration_id. Derive expected migration-held cases from original saved state/cleanup, so deleting/relabeling a required initial origin cannot evade the comparison; forbid a new/postmigration run or later claim snapshot from calling itself migration. Keep later legacy_claim/reconcile legitimate transitions separate and tied to their actual claim/reconciliation boundary, preserving immutable history and atomic claim behavior. Add RED tests using the preserved counterexamples before fixing. Do not compare later evolving mutable runs directly to old snapshots as a substitute: legitimate legacy progress must remain possible.

Related typed-time defect: action.started_at and origin.observed_at may both be set to literal `not-a-time`, hashes recomputed, and reopen accepts while observation event.recorded_at remains a different valid timestamp. Require actual host UTC timestamp validation and equality of the origin/action/observation timestamp describing the same boundary. Treat this as part of the same strict provenance correction; it grants no immediate executable owner but violates the retained host observation contract.

No direct launch/capacity bypass was demonstrated: executable owner/epoch remain NULL and unknown held lease remains. Severity is P2 correctness of immutable audit provenance and future adoption inputs, not a claimed credential or executable-authority exploit. It blocks the explicitly requested strict representation acceptance.

## Declined to judge / pending gates

- G adoption, capacity collector/scheduler, group protocols/clones/base refresh and installed >=3 pilot: later Task3B/4+ behavior; Task3A explicitly rejects registered mode, so this review does not approve those interfaces.
- Original hot recovery: accepted OptionA expressly leaves it mandatory under current Issue65; refusal tests never satisfy that requirement.
- Current full-suite outcome, three-platform CI and exact PR/main acceptance: coordinator-owned external gates, pending independently of this candidate finding.
- Later main7586df4 acceptance/source re-audit: not established by this frozen487 review.

No other blocker was established within the reviewed Task3A candidate. A corrected source invalidates this freeze and requires fresh hashes, tests and distinct review; this rejection must remain historical.
