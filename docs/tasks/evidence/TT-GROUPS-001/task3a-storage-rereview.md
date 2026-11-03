# Independent corrected Task3A re-review — 2026-11-03

Reviewer: /root/groups18_task3a_acceptor, distinct from implementer. Verdict: **APPROVE the frozen bounded Task3A implementation/schema and targeted migration behavior; complete Task3A test acceptance remains gated on the coordinator's fresh corrected full suite.** No blocking finding remains. This is not PR/head-base acceptance, exact-main acceptance, full Issue18 completion, original hot recovery or night readiness.

Historical rejection runtime/groups18-task3a-independent-review.md SHA256f1a41b43b226e3eeab96bdb93f72c8a5bb88685c83bbadd2d415920ee28acdf1 and its counterexample evidence remain unchanged. This new verdict applies only to the corrected bytes below.

## Exact candidate binding

Read-only Git inspection independently confirmed HEADdf1734c84ffd5c84bff856a33df4f3180ebc43fc after the coordinator's accepted758 merge. Independently recomputed and matched all four final freeze hashes (manifest runtime/groups18-task3a-provenance-final-source-freeze.json SHA256dd0ad087fef4059fc12af5880beb3137f2d05af116182a335816a825a5721ba8):

| File under task-tower-capture | Raw SHA256 |
| --- | --- |
| task_tower/pipeline_journal.py | 149a892251990e26d7ca18abdcf7cf4cea4b2f1561cf9afe29b16e9a6fe5cf88 |
| task_tower/pipeline.py | 2c431e5bfa7d090fd0b373539965227da938f785c1942b3ff9e33f57b83d8f82 |
| task_tower/group_storage.py | 7efc29660c1ea723f1c2472b152cf4230c17dfaa274e36c92d92c7525078a0e5 |
| tests/test_group_migration.py | f80edde0be88ff036a071e3643595df51e8d23cac4cf38bae63a7370f0276c32 |

Read runtime/accepted-main-758-contract-audit.md: coordinator records actual accepted main7586df4ac2e59316521463b7526089c8314024e4, three-platform postmerge CI41580684133, independent approve and automatic Issue63 receipt https://github.com/Sibiya666/task-tower/issues/63#issuecomment-6596295026. Affected14 modules are unchanged from accepted487; fetch timeout is outside storage semantics. This reviewer inspected that audit and merge HEAD without re-publishing/re-accepting the external main cycle. Prior accepted Issue16 foundation4875381be68282a7ad77ab7b1c5a3898cbc09304 retains its original receipt.

R3 and accepted hot-boundary OptionA reviewf361b60786c69be334e49a82994b26e1d2b6652d61e136bcde1d9db066c92fbf remain normative. Neutral host markers implement genuine provenance under existing SQL kinds; they add no execution/cleanup authority or semantic spec amendment.

## Review and fresh evidence

Inspected the complete actual tracked pipeline.py/pipeline_journal.py diff again, all corrected storage functions and added tests, surrounding migration/claim/reconciliation/cleanup/sidecar code, final handoff and accepted-main audit. Tracked pipeline files remain byte-identical to the previous reviewed candidate. No source, Git, shared docs/card or live journal was changed by reviewer.

Using actual Python C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe with PYTHONPATH=tests, independently ran -m unittest test_group_migration -v from task-tower-capture: **59 tests in20.968s,OK,exit0**. No skip in these59 migration tests. Includes real spilled hot refusal, complete postcommit cold reopening, lossless backups/sequences, contention/deadline/identity/noncreation, SQL constraints, initial provenance, future claims, own-ready continuation, reconciliation, marker corruption and rollback. Implementer's224 targeted result is handoff evidence, not substituted for this run.

Ran unchanged original reviewer counterexample script from workspace root against corrected source:

- migration_owner_mismatch: REFUSED, Migration origin contradicts authoritative legacy snapshot.
- postmigration_claim_mislabeled_migration: REFUSED, Legacy host marker identity/order/time/hash mismatch.
- migration_mislabeled_legacy_claim: REFUSED, Legacy origin provenance mismatch.
- invalid_origin_timestamp: REFUSED, Invalid isoformat string: not-a-time.

An initial script invocation mistakenly used the checkout cwd and only reported missing script, executing no counterexample. The subsequent correct workspace-root invocation supplied the verified results above.

Additional reviewer-owned disposable fixture probes passed:

- Initial migration ordinal changed to2: host refused.
- Nonnull executable owner on legacy fence: SQL refused.
- Action/origin/observation timestamps consistently rebound to valid +03:00 time with all affected hashes recomputed: host refused because UTC is required.
- sqlite3.IntegrityError injected during observation insertion AFTER marker insertion: complete actual legacy claim transaction rolled back. Exact original legacy dump remained, group_events had only its single migration event, and no new action/lease/reservation remained.

Independently extracted/executed exact spec SQL and implementation DDL in separate memory databases and compared exact sqlite_master type/name/sql sets: equal. Original SCHEMAS digest5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6 and catalog digest1e1e250b953b7166b481f9b52d9fa9a4ed1c6fa9454cd279600f51502315c96a remain unchanged:6 original tables,17 additive tables,3 indexes.

## Why the finding is resolved

Initial holdings derive from the authoritative validated immutable migration snapshot using unchanged product/positive-cleanup predicates. Required initial observations must occupy the initial observation segment, have ordinal1, exact saved run row and ordered per-run history, and independently derived migration kind. Complete initial-set equality prevents missing/relabel evasion. Historical mutable owner/PID/state/input are bound to that saved boundary without incorrectly binding later evolving current rows to old values.

Later literal host claim/reconciliation callsites append closed marker and observation in the same existing transaction. Marker kind determines expected origin kind. IDs, metadata-derived migration_id, row/history hashes, actual original-history tip, adjacency, contiguous per-run ordinals and host UTC time equality are checked. A legacy claim needs retained claimed-event/preparing semantics or genuine positive safe-ready continuation. Reconciliation needs actual product ownership, unproven cleanup and matching later retained legacy state; a fully rebound unstarted queued boundary is refused. Own-ready continuation can leave all original six tables unchanged while appending its neutral host marker.

Markers grant no executable owner, G/epoch, resource sample, stage verdict, cleanup or fairness advancement. Typed legacy_fence executable fields remain NULL; unknown held leases block new claims, component ownership remains separate and genuine cleanup is still required. Correction leaves OptionA first actual chained RO776 neutral result, byte-preserved original/sidecars, no writer/backup/DDL and migration-only guards unchanged.

## Findings and remaining gates

Critical: none established. Important/blocking: none remaining within this bounded candidate. No requested source correction remains.

Coordinator must run/inspect a fresh complete corrected full suite on these integrated bytes before declaring Task3A test-stage acceptance. Old70083 was incomplete and cannot supply that gate; no full-suite pass is claimed here. Changes invalidate these hashes and require affected re-review/checks.

Declined to judge: G adoption, resource scheduler/probes, group protocols/execution/clones/base refresh and installed>=3 pilot are later Task3B/4+ scope. Original automatic hot recovery remains mandatory current Windows Issue65; refusal tests do not qualify it. Current three-platform CI, PR exact head/base acceptance, eventual exact-main acceptance and automatic Issue closure remain separate downstream gates. No full18 completion or night readiness is granted.
