# Task6 independent review — rejected frozen revision

Fresh reviewer `/root/pr_reviewer_review`, independent of implementer/coordinator; 2026-11-02. Reviewed AGENTS and current accepted R2 stage-pipeline specification/plan, entire Task6 WIP and shared journal/worker/publisher/executor delta against HEAD `35da43c`. **REJECT: P1 cancellation ordering and P2 exit/portable-test findings require correction and independent reacceptance.** This is not PR acceptance or installed-runtime readiness evidence.

## Blocking findings

1. **P1: public work interrupt may never request child cancellation while SQLite is locked.** `task_tower/pipeline.py:250` calls `journal.status()` and cancellation writes before `stop.set()`. `finally` then synchronously calls unbounded `journal.recover()`. Unlike watch's `_shutdown`, these paths have no shared monotonic shutdown deadline and do not set stop before DB access. A real exclusive SQLite lock during Ctrl-C delays termination, and a status exception skips stop.set entirely, leaving the contained helper running until its independent task timeout. Controlled probe used a real PipelineJournal/SQLite BEGIN EXCLUSIVE and replaced only the waiting host with a fixture whose wait raises KeyboardInterrupt. Actual result: `EXCEPTION ValueError SECONDS 14.89 STOP_SET False`. Request stop first, bound all public-work shutdown DB/cleanup under the same <=5-second budget and retain unknown ownership on failure. Add a real live-helper public-work interrupt+SQLite-lock regression.

2. **P2: operational uncertainty is reported with success exit status.** `pipeline.main` prints the work report then unconditionally returns 0 at line374. With actual parser/report/exit control flow and controlled `_runtime`/`work` fixtures returning unknown/cleanup_unknown, result was `UNKNOWN_WORK_EXIT 0 REPORT {"reason": "cleanup_unknown", "status": "unknown"}`. Specification requires exit1 for operational uncertainty. Classify unknown/incomplete host outcomes separately from a valid parked needs_input tick and test CLI exit codes.

3. **P2: new controller tests repeat the macOS temporary-path failure.** `tests/test_pipeline_cli.py` lines18,33,45,55,64 construct positive PipelineJournal paths using unresolved `Path(directory)` from TemporaryDirectory. macOS `/var` temporary paths have a symlink ancestor which production safe_config_path deliberately rejects. These fixtures need canonical roots before journal construction, preserving intentional negative alias arguments and the guard. This is the same diagnosed portability failure corrected in the separate Root PID-test patch. No local macOS run is claimed; remote macOS verification remains required.

## Scope and positive observations

The new fixed host helpers use the existing process runner; genuine source factories and verified_done remain unchanged. Only transport fixtures replace HTTP/Git transport. Roles/checks strip host token keys. Same-repository claim/transition/attempt/effect exclusion is transaction-bound; unknowns retain reservations. The publication ready boundaries require completed current effect proof and accepted three-stage chain; worker continuation explicitly validates final evidence checkpoint. Controller health is strict and ownership checks retain positive-death semantics. The PID portability patch is a separately accepted Root change, not author Task6 implementation.

Read-only inspect/status avoid executable pin requirements, and health reads do not create a journal. Two-repository overlap/refill and unknown retention have real-process fixture coverage. These observations do not override the findings above, full-suite/three-OS gates or installed Codex pilot requirements.

## Exact freeze

Independently recomputed freeze manifest SHA-256: `0c8e2d1108e1d4484d6c79e9408d3fa0006bdb9e0ba1c3367b928cbb77d2118c`. Every listed raw and canonical digest matched. Raw hashes:

| File | SHA-256 |
| --- | --- |
| task_tower/pipeline.py | `0f44b0dc0093fd847b52bd96c9d99e9ff26ba67dfee06cde2355a7e8f864438e` |
| task_tower/__main__.py | `3d78cca9a8ff3cc1cacca849ef0cb839987dd42be5603d9a74628e2792470440` |
| task_tower/executor.py | `13acb7a4ea0af756be6d35955778566c7ddfbe188bcffc4d675aa03d289089a8` |
| task_tower/pipeline_journal.py | `b87d016684baf7eaab4309f3168b5be53eac0ef67062cec6fcfd3b6cd6024740` |
| task_tower/pipeline_worker.py | `587ff0eecb7639e1296649ab727150d7e57321521629eb8d6ab02fbaba1b0524` |
| task_tower/pipeline_publish.py | `b2b502433e910a9dd9dcd19db37efb994446f9005bd2b9d0efb5b55096faa83f` |
| tests/test_pipeline_cli.py | `b678a29428970be902e53567c10a114753cc6452f93efe570361782f3e6a7cdd` |
| tests/test_pipeline_watch.py | `5346571c1fc0654a61f71d010c446a76c58fc3197118d0025c65c63208c01491` |
| tests/test_pipeline_journal.py | `68ed5a7d2eeab26275124932b62a934c4638d03abfc6e56b93fe618f26ab9473` |
| tests/test_pipeline_publish.py | `12c336665d227f79a5b110ef86b8e90f452e1f70a131ceb5325b9db7d119c774` |
| tests/fixtures/pipeline_watch_role.py | `540bc2ea38c445bd3fe5c25a904bc50dff42acaf8eb903c1f132f9161637f2c0` |
| tests/fixtures/pipeline_http_site/sitecustomize.py | `4ead16aadc71c640f64ada06cd76892acd54083fee961994f23d823790b58ef4` |
| task_tower/processes.py (dependency) | `e3c07d5cdff3ad123b92f188fb62d5e03f63c83d024f89ab549ef1058ace52bd` |
| task_tower/windows_job.py (dependency) | `9212e216cb52bc55e77ebf0854b86f502b851f74fc26a667b105d4c90085498a` |
| tests/test_process_pid.py (Root dependency) | `54dc23e84b47c38bca4d8bcb0f73da319faa2b7fff35962b5664c3a5a4a70a91` |

Canonical hashes differ only for __main__.py (`fe78133b6c2db935dc0918df283bd70b4eff34f6382a62b176f54ff0e57b0177`), pipeline_worker.py (`052be65111954e64c79c848abff75ab8cf961cb3bfb55d4d44559cc4b8a9ef50`), processes.py (`329bd49d2fb8a155b6eb0002bd43876d003e921081041cfa73f41a09595a890c`) and windows_job.py (`df5f7de7b6f7e5324070c78422159286222c4b0dfdba2e4ae53d85d8e9b775fe`).

## Independent verification

Used absolute `C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Started the full author-focused command independently:

```text
python.exe -m unittest tests.test_pipeline_cli tests.test_pipeline_watch.WatchTests tests.test_pipeline_journal tests.test_executor_adapter tests.test_process_pid -v
```

Independent result: **67 tests in 285.591s, OK, exit0**. The supplied tests pass but do not cover the confirmed public-work Ctrl-C/DB-lock ordering or operational exit-code defects. The two controlled probes above use actual public work interrupt/report control flow with explicit fixtures; no live external writes, source edits or commits were performed. No installation, model selection or non-Windows/full-CI success is claimed.
