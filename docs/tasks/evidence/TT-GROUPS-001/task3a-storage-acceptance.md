# Task3A bounded storage acceptance — 2026-11-03

Independent reviewer: /root/groups18_task3a_acceptor. Accept the exact frozen Task3A implementation and tests for cold lossless migration, complete postcommit cold v2 reopening and honest untouched-original hot refusal only. The outstanding full-suite condition in the [corrected independent review](task3a-storage-rereview.md) is now satisfied by the coordinator-owned run verified below. Whole Issue18 development/test/postmerge stages remain pending; no live migration was performed.

## Bound source and retained reviews

Accepted integration base7586df4ac2e59316521463b7526089c8314024e4 was merged into branch HEADdf1734c84ffd5c84bff856a33df4f3180ebc43fc before this run. [Exact four-file source freeze](task3a-source-freeze.json) binds pipeline.py, pipeline_journal.py, group_storage.py and test_group_migration.py; its original base487 identifies the accepted Issue16 schema foundation, not a claim that later758 was absent from verification. Original SCHEMAS digest5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6 and exact17-new-table/3-index catalog1e1e250b953b7166b481f9b52d9fa9a4ed1c6fa9454cd279600f51502315c96a remain unchanged.

The [original rejection](task3a-storage-review-rejected.md) remains byte-identical, SHA256f1a41b43b226e3eeab96bdb93f72c8a5bb88685c83bbadd2d415920ee28acdf1. The [fresh re-review](task3a-storage-rereview.md) remains byte-identical, SHA25658234b92f8b275fff70d9090aaef9c66522c56d64bf8277cc383dc9bc933d0cb. The provenance correction independently rejects all four original counterexamples and passed59 migration tests20.968s plus reviewer-owned timestamp/ordinal/authority/transaction-rollback probes. Retain rejected, RED and incomplete historical evidence; the old70083 partial full run never passed.

## Complete corrected full-suite receipt

Root ran the full dependency-free suite, python -m unittest discover -s tests -v, through the existing bounded verification runner from accepted758. Reviewer inspected completion.json, exact output hashes, before/after source manifests and final unittest result; no second full run was required for these documentation-only updates.

- 869 tests in1567.921s: OK, skipped7; child exit0, started=true, cleanup_confirmed=true.
- Verified completion: verified_success=true and source_unchanged=true. [Original completion receipt](task3a-full-suite-completion.json), raw SHA2560cffd94c865ac156dbf65decd5587592924f873ed6cc80f925a990e21ad86328.
- stderr complete134900 bytes, SHA2560b2c89a10a6527828b013837bb7bb6964805807067ef148d32f7195fe4a0bdbf; stdout complete85 bytes, SHA256fd546d01c6d2880b01d3bce9a7b1f43d0c4125bcc137c4ce97d019d3e8643e08. Neither stream truncated or has an unknown tail.
- Before/after source manifests are byte-identical, SHA256c6d90303f7e0de746abd55c2164827142709240728a2ba288659d8facab6a461; the four reviewed candidate hashes still match. Private full logs/manifests remain under runtime/verification/groups18-task3a-final-root.

## Operational limits

Migration is explicit and existing-only; inspect does not create a database/directory or load execution profiles. Cold apply requires stopped ownership, bounded60s/one FULL transaction and no-clobber diagnostic backup. Legacy rows/order/sqlite_sequence and immutable provenance survive. Typed legacy_fence records create no executable owner, G, epoch, resource estimate or accepted stage; unknown held leases fence new claims and component ownership is retained independently.

Only a genuine first existing-only read-only SQLITE_READONLY_ROLLBACK776 returns exactly {status:"recovery_required",version:null}; CLI exits1. This establishes no recognized version/schema/owner/cleanup and opens no original writer, backup or DDL. Non776, unsupported sidecars, aliases, corruption and changed physical identity remain refusals. No RW fallback, source repair, backup-over-live or replay is authorized.

Original automatic hot recovery remains mandatory current Windows [Issue65](https://github.com/Sibiya666/task-tower/issues/65) before full18 completion. G adoption/discovery, group protocols, resource collectors/scheduler, independent clones and installed concurrency remain later independently gated work. This receipt grants no whole18 completion, PR/head-base or main acceptance, automatic Issue closure or night readiness.
