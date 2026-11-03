# Independent Task1R-L implementation review

Reviewer: /root/groups18_task1rl_review, distinct from implementer. Verdict: **REJECT / BLOCKED** for the exact frozen candidate. One important blocking finding; no implementation acceptance or merge approval.

## Source binding and scope

HEAD independently read as 73186e6c58b6610eaa4f3e8745aca0437110e2f1. Foundation reviewed Task3A 3e13f54d226ae33fc89ed3144658d0c53468f5e8 on accepted main7586df4ac2e59316521463b7526089c8314024e4. Independently recomputed all14 actual candidate raw source hashes and matched every entry of source-freeze.json. Reviewed the complete14-file candidate diff including new capacity_policy.py and actual loader/runtime callsites. No candidate/source/document edits, Git mutations, live databases, private installed policy, provider/auth/native child or GitHub effects. The sole probe used disposable real JSON loader fixtures and a journal recovery sentinel.

Raw SHA256 bindings independently confirmed:

- source-freeze.json: f42ec55e46a53e22627d38521a028847b0645ed63da41e306cf285b324582584
- candidate.diff: 43b4d87f622f6b6401fde273e974bdd2e2f4b3289e2327b05d7699007b02ab36
- implementation.md: 5591460025e2df7c0a37a4c05efc573b13f6f5d6a37d1bb494fd4d3a6711eb73
- approved binding review: 8efc7e76baf3f0024fda02af7cc4a6a9c386447b64d91f20abaeb5f64bcbf1d8
- design: c7b385a65eb5ca1f463b64627334709c8ae80c20d7ebb4b367ce071ff9fb03b6
- plan: ab21fd19146701a634faf1226d8facd0c87569161600d41666f892b3c9dbf195

## Strengths

Pure loader factoring preserves v1 output shapes and historical executor duplicate semantics, while enforcing strict v2 schemas without invented max_active. Added guards cover the direct execution, role, check and publication entry seams and preserve native-platform precedence. Low-level legacy claim and migration/storage contracts remain untouched.

## Blocking finding — P1: guard the freshly reloaded watch runtime before recovery or helper creation

Location: task_tower/pipeline.py:306-313, specifically require_legacy_capacity(config) before _runtime(args), followed by only a pipeline policy_sha256 comparison and journal.recover().

A running legacy watch can observe an operator replacing executor v1 with a valid executor v2 while retaining pipeline v1. The cached config passes the guard. _runtime loads the actual v2 executor and returns fresh['_executor_config']['version']==2, but pipeline policy_sha256 excludes executor configuration/profiles and therefore remains equal. The function then calls journal.recover and can create _Host dispatch/action helpers using the old max_active. This violates the explicit current v2 refusal before recovery/helper effects, even though the helper itself later refuses execution. It also affects a cached v1 config passed directly to watch_tick after files change.

Independent reproduction used actual pipeline._runtime and both actual JSON loaders, no mocked loader or native child. From task-tower-capture run the following through the approved Python executable:

```python
import json
from types import SimpleNamespace
from tests.test_group_policy import GroupPolicyTests
from task_tower import pipeline
f=GroupPolicyTests(); f.setUp()
try:
    f.pipeline_path.write_text(json.dumps(dict(version=1,tasks=[f.task])),encoding='utf-8')
    connections=f.root/'connections.json'
    connections.write_text(json.dumps(dict(version=1,projects=[dict(
        id='r',repository='Owner/Repo',checkout=str(f.checkout),runner_label='local',
        trusted_publishers=['publisher'])])),encoding='utf-8')
    args=SimpleNamespace(connections=connections,journal=f.root/'journal.sqlite3',
        config=f.pipeline_path,executor_config=f.executor_path)
    _,_,old=pipeline._runtime(args)
    old['_watch']={}
    raw=json.loads(f.executor_path.read_text())
    raw.update(version=2,harness_resources={'local':dict(pool_id='local',
        cpu_millis=1000,memory_bytes=1048576,max_parallel=None)})
    f.executor_path.write_text(json.dumps(raw),encoding='utf-8')
    _,_,fresh=pipeline._runtime(args)
    print('old_executor',old['_executor_config']['version'],
        'fresh_executor',fresh['_executor_config']['version'],
        'policy_sha_equal',old['policy_sha256']==fresh['policy_sha256'])
    class Journal:
        def recover(self):
            raise AssertionError('RECOVERY REACHED after actual current executor changed to v2')
    try: pipeline.watch_tick(old,Journal())
    except Exception as e: print(type(e).__name__,str(e))
finally: f.doCleanups()
```

Observed fresh output, process exit0:

```
old_executor 1 fresh_executor 2 policy_sha_equal True
AssertionError RECOVERY REACHED after actual current executor changed to v2
```

Required correction: apply the capacity guard to the freshly loaded runtime before recover or any subsequent helper/source/owner effect. Add a meaningful real-file reload regression including mixed pipeline-v1/executor-v2, and assert recovery and host construction remain untouched. Freeze corrected sources and obtain fresh independent acceptance.

## Verification assessment and limits

Read preserved RED evidence:44 tests,12 failures/12 errors/1skip including unsupported-mode owner access. Read97 expanded GREEN evidence,1skip. These are implementer runs, not new reviewer reruns. Broad365 run is correctly preserved as actual exit1 with one bare-import failure and3skips; the other364 cases completed without assertion failures. Corrected PYTHONPATH=tests migration59 run ended OK/exit0. Do not label the broad invocation successful or claim full-suite acceptance. No identical suite or full suite was rerun by this reviewer; Root-owned full verification remains pending after correction/review. All14 frozen source hashes were independently verified unchanged during review.

Declined to judge: Task3B registration/protocol/schema/event enablement, Task4R resource consumers and Task5 workspace/epoch execution are explicitly later work; their absence is not a new Task1R-L finding. Original current-Windows hot recovery Issue65 remains mandatory for full18. Native POSIX61 remains deferred. No wholeIssue18, PR/main, installed capacity or unattended/night readiness verdict is granted.
