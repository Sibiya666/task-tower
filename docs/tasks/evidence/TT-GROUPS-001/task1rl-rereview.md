# Independent Task1R-L fix round1 re-review

Reviewer: /root/groups18_task1rl_review, original independent acceptor, distinct from implementer. Original P1 reload bypass: **ADDRESSED**. Corrected frozen Task1R-L implementation: **APPROVE** for code review. No remaining blocking finding identified within the reviewed implementation scope. Root-owned full-suite verification and later stage/integration gates remain pending; this is not PR/main or wholeIssue18 acceptance.

## Exact binding

Inherited original complete14-file review bound to HEAD73186e6c58b6610eaa4f3e8745aca0437110e2f1, reviewed Task3A3e13f54d226ae33fc89ed3144658d0c53468f5e8 and acceptedmain7586df4ac2e59316521463b7526089c8314024e4. Original rejection remains immutable at SHA256825bd566f3cdc3fd1152db11883fedbfafbc97423dcb570dd5016eab66f648f2.

Independently recomputed all15 actual source hashes against corrected freeze92b82beb89860269d0a1eaa7803235c98ad8e2f747eddd1ddffb8d0cb7a6e5d0. All match. The13 other previously reviewed files remain byte-identical; removing the unique new require_legacy_capacity(fresh) line exactly reconstructs the rejected pipeline.py hash. Read the complete two-file correction and actual watch_tick/watch/_shutdown control flow.

- Addendum: 8d4b2d5a9be92495c018183869fdb6895dd7ef7b2d797c9968cab02c5d709687
- Scoped fix diff: 7019a071e6b22d79e17e98cc044d47d9dfc70a5caf4db93cf6c4ca3b7c14cb39
- Full corrected candidate diff: dc54f88954e2f6749a39a8a2d2baf8c6fe1d2ad90834ee7bed9b4cd0b20d40d4
- Corrected task_tower/pipeline.py: e7ea181a8bda0582116f1c44baa5f51118e74e809354733771882aa4a95f0964
- tests/test_pipeline_watch.py: e251db568d3dc18052e64f4b02f7a931e275a689fae1b6bb5795b159b574663d

Approved specification/plan and independent binding remain the exact hashes recorded in the original review. No approval attaches to future changed source bytes.

## Finding disposition

The new guard at pipeline.py:310 applies to fresh _runtime output immediately after actual current file loading, before policy digest comparison, journal.recover, watch state changes or helper construction. The original mixed executor-v2/pipeline-v1 equal-policy-SHA counterexample is refused with group_runtime_unavailable. Cached v2 refusal and native-platform precedence remain intact. For v1 fresh runtime the new pure guard has no effect on return shapes, existing watch ownership or helper arguments.

The existing watch finally path still runs _shutdown after fresh-mode refusal, allowing an already-held legacy controller/helpers to stop under original cleanup semantics. This correction does not replace cleanup with a blanket skip. The genuine disposable local-controller regression verifies stopped controller state and zero workers/dispatcher, with helper construction forbidden.

## Verification

Independently ran approved Python from task-tower-capture:

`-m unittest tests.test_pipeline_watch.CapacityReloadTests -v`

Actual fresh result:2 tests1.245s,OK, both executed with no skips. Both actual JSON loaders and actual _runtime participate; equal pipeline policy SHA and executor1-to2 transition are asserted. Recovery/helper sentinels prove first-effect ordering; the second test exercises genuine existing controller shutdown/release. No native/helper/model child is launched by these two cases.

Read preserved fix RED:2 tests1.385s,FAILED2 (recovery/helper reached before fix). Read supplied covering focused result:40 tests32.145s,OK1skip, completed exit0. This latter40-case run is implementer evidence, not a new reviewer rerun. No gratuitous repeat of its broader suites or full suite performed.

Original broad365 result stays exit1 with one unchanged bare-import error and3skips; corrected migration59 run stays OK/exit0. Neither is relabelled. Root-owned full verification is still required after this code approval.

Declined to judge: later Task3B registration/schema/events, Task4R resource consumers, Task5 workspace/epoch execution, original current-Windows hot recovery65 and native POSIX61 qualification remain outside this scoped correction and retain their existing mandatory/deferred gates. No private installed files/live databases, source edits, Git mutations, remote/provider/auth/model effects or full suite were performed. Report creation is the only persistent review artifact change.
