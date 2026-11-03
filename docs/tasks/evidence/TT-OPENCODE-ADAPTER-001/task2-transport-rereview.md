# Independent Task2 fix-round1 rereview

Reviewer: /root/opencode_task1_acceptor. Original P2: **ADDRESSED**. Verdict: **APPROVE Task2 frozen v2 code**. This scoped rereview covers only the original constructor cleanup finding and new breakage introduced by its fix. Original broad review and limitations remain in opencode21-task2-independent-review.md SHA256 cfac72c60519e5926727273905dae6b18b64cecc924f5a1c0ee958b916812527; the original blocked freeze remains historical.

Verified exact four supplied artifact hashes and all three actual source hashes plus ZIP bytes unchanged. HEAD binding remains64b9702f6ddadad89c76bfba5bed2ff75d87fb05. Normalized v1-to-v2 comparison confirms only processes.py cleanup/error propagation and three new transport regression tests changed; windows_job.py is byte-identical. The supplied diff has newline-noisy whole-file hunks, so I independently compared decoded original ZIP lines with actual candidate lines to examine the real focused changes.

Both POSIX and Windows storage constructors now collect independent cleanup callbacks for every retained raw descriptor/stream/native handle. Each cleanup attempt is isolated, primary construction exception is re-raised, and cleanup errors conservatively set its private stdin_cleanup_confirmed=false. Stream-conversion failure also independently closes its transferred raw descriptor. _stage_stdin carries that uncertainty into the bounded binding failure, and runner returns started=false, reason=stdin_binding_mismatch, status=cleanup_failed, cleanup_confirmed=false. Ordinary binding mismatches with confirmed cleanup retain previous unavailable result. No child is created for these paths. Existing transport success path/limits/permissions/None delegation/containment are unchanged by the fix.

Independent exact original Windows probe rerun: both genuine storage streams created; os.set_inheritable raises the primary OSError; writer.close closes its underlying writer and raises. Actual output now: `primary_preserved True cleanup_confirmed False`, `created 2 closed [True, True]`. This fixes the original [True,False] leak and preserves the failure rather than replacing it.

Independent new-test command using bundled Python: `python -m unittest tests.test_opencode_transport.TransportTests.test_storage_constructor_failure_closes_each_owner_and_preserves_failure tests.test_opencode_transport.TransportTests.test_storage_second_stream_failure_still_cleans_writer tests.test_opencode_transport.TransportTests.test_constructor_cleanup_uncertainty_is_not_reported_confirmed -v`. Actual result: **3 tests in0.019s, OK, exit0**. These check exact primary exception identity, closure of both underlying real streams/raw descriptors, removal of actual GetFinalPathNameByHandleW temporary paths, second conversion ownership seam and conservative runner cleanup result. No blocking finding remains in this scoped fix.

The supplied32-test5.104s OK/1skip result remains implementer evidence; I did not repeat the full focused or full repository suite. Root-owned full checks may follow code approval. No source edits, Git changes, native OpenCode/probe/provider/auth/install or remote effects were performed. This approval grants no native installation qualification or Tasks3-5/PR/main/wholeIssue acceptance.

## Bound fix artifacts

| Artifact | Raw SHA256 |
| --- | --- |
| opencode21-task2-fix1-review.diff | 966aaa7c6335f707488cfd2ef1923834c360994a0e32751fe1fd4c898db2392f |
| opencode21-task2-implementation-fix1.md | 3b1829a17ddfe28f1895e637ce345490ecaf5daef44a9de76b72634fb7cddc9a |
| opencode21-task2-freeze-v2.json | e750c515ce14510775c7f866de7303db9fd17f62cc3cc2a41104d33be675d950 |
| opencode21-task2-review-files-v2.zip | 82fd9d0c3cf224afb670ff2806071be390d1d000086c7ad7daa11c5ac8b393cf |

## Exact v2 source files

| File | Raw SHA256 |
| --- | --- |
| task_tower/processes.py | 01f9f1b81f6277168af74037c36010564f6a551e9a27723fe8e837ce8dcf3198 |
| task_tower/windows_job.py | fa1982c1032e20e57dcee00c27fc07bba11ef7d77000c530f46be80d13f9ad09 |
| tests/test_opencode_transport.py | 20163b65178b2491c2ed8caba8cb0d2be5c39ab9b3c3ff189a5ebe083ac6b242 |
