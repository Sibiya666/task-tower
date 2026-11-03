import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from task_tower.executor import main, adapter
from task_tower.executor_queue import ExecutionQueue

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name).resolve()
        self.q=ExecutionQueue(self.root/'queue.db')
        self.r=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-EXECUTOR-001',runner_label='local')
        self.config=dict(profiles={'p':{'trusted':True}},allowlist=[dict(repository='Owner/Repo',issue=15,task_id='TT-EXECUTOR-001',runner_label='local',profile='p')])
    def test_adapter_commit_lookup_and_collision(self):
        first=adapter(self.r,self.config,self.q)
        self.assertEqual(first['status'],'accepted')
        self.assertEqual(first,adapter(dict(self.r,operation='lookup'),self.config,self.q))
        self.assertEqual(adapter(dict(self.r,operation='lookup',issue=16),self.config,self.q)['status'],'unknown')
        self.assertEqual(adapter(dict(self.r,operation='lookup',delivery_id=str(uuid.uuid4())),self.config,self.q)['status'],'not_found')

    def test_v2_submit_does_not_create_queue_and_known_lookup_keeps_identity(self):
        self.config['version']=2
        self.assertEqual(adapter(self.r,self.config,self.q),dict(version=1,delivery_id=self.r['delivery_id'],status='unknown'))
        self.assertFalse(self.q.path.exists())
        self.config['version']=1
        receipt=adapter(self.r,self.config,self.q);before=self.q.path.read_bytes()
        self.config['version']=2
        self.assertEqual(adapter(dict(self.r,operation='lookup'),self.config,self.q),receipt)
        self.assertEqual(self.q.path.read_bytes(),before)

    def test_v2_work_retry_cli_never_initializes_or_recovers_queue(self):
        from tests.test_executor_profiles import ExecutorProfilesTests
        fixture=ExecutorProfilesTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.v2();fixture.load()
        connections=fixture.root/'connections.json'
        connections.write_text(json.dumps(dict(version=1,projects=[dict(id='r',repository='Owner/Repo',checkout=str(fixture.checkout),runner_label='local')])),encoding='utf-8')
        queue=fixture.root/'never-created'/'queue.db'
        common=['--connections',str(connections),'--queue',str(queue),'--config',str(fixture.path)]
        for cmd,extra in [('work',['--once']),('retry',['--run-id',str(uuid.uuid4())])]:
            with contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([cmd,*common,*extra]),2)
            self.assertFalse(queue.parent.exists())
    def test_status_cancel_require_connections_but_no_profile_config(self):
        checkout=self.root/'checkout'; checkout.mkdir()
        connections=self.root/'connections.json'; connections.write_text(json.dumps(dict(version=1,projects=[dict(id='r',repository='Owner/Repo',checkout=str(checkout),runner_label='local')])))
        receipt=self.q.submit(self.r,'a'*64)
        common=['--connections',str(connections),'--queue',str(self.q.path),'--run-id',receipt['receipt_id']]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['status',*common]),0)
            self.assertEqual(main(['cancel',*common]),0)
        self.assertEqual(self.q.status(receipt['receipt_id'])['state'],'cancelled')
        connections.write_text('{}')
        with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(main(['cancel',*common]),2)
    def test_missing_connections_is_cli_error(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit): main(['status','--queue',str(self.q.path),'--run-id',str(uuid.uuid4())])
