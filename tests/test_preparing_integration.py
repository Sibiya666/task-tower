"""Real disposable HTTP/Git/connector preparing bridge; no live recovery."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from task_tower import preparing_recovery as contract
from task_tower.connector.client import APIClient,LifecycleConnector
from task_tower.connector.store import ConnectorStore
from task_tower.connector.worktrees import Worktrees
from task_tower.connector.app_server import AppServer
from task_tower.service.api import make_server
from task_tower.service.preparing_recovery import command_ids
from task_tower.service.store import Store,plan_digest
from tests.test_service_beads import NativeFixture,Beads
from tests.fixtures.preparing_recovery import GitCase,receipt

PLAN={'tasks':[dict(id='pilot-task',title='Work',description='Approved fixture scope',depends_on=[])]}

class PreparingBridgeTests(GitCase):
    def setUp(self):
        super().setUp()
        self.transport=tempfile.TemporaryDirectory();self.addCleanup(self.transport.cleanup)
        root=Path(self.transport.name);self.native=NativeFixture()
        self.beads=Beads(root/'bd',{'p':self.root},runner=self.native)
        self.s=Store(root/'service',self.beads,approved_plans={'p':{plan_digest(PLAN)}})
        self.addCleanup(lambda:self.s.close())
        self.s.import_plan('import','p',plan_digest(PLAN),PLAN)
        a=self.s.claim_request('claim','p','pilot-task','host1')
        self.s.start_lifecycle(a['attempt_id'],'host1',self.head)
        self.old=self.s.lifecycle_commands('host1')[0];self.key=self.old['command_id']
        self.s.record_event(dict(version=1,event_id='old-failure',attempt_id=a['attempt_id'],connector_id='host1',lifecycle=dict(kind='failed',command_id=self.key)))
        self.before=self.s.attempt(a['attempt_id'])
        self.cs=ConnectorStore(root/'connector','host1');self.addCleanup(self.cs.close)
        self.cs.receive(self.old);self.cs.update(self.key,phase='needs_reconciliation')
        self.target=root/'trees'/a['attempt_id']
        intent=dict(project_id='p',path=str(self.target),branch='codex/headless-'+a['attempt_id'],base_sha=self.head,state='preparing',review=False)
        self.cs.save_worktree(a['attempt_id'],intent);self.git(self.root,'branch',intent['branch'],self.head)
        self.r=dict(receipt(),project_id='p',bead_id='pilot-task',attempt_id=a['attempt_id'],native_owner=a['actor'],command_id=self.key,branch=intent['branch'],base_sha=self.head,branch_sha=self.head,engine_sha=self.head,command_sha256=contract.fingerprint(self.old),worktree_sha256=contract.fingerprint(intent),cleanup_sha256=contract.fingerprint(dict(cleanup_resources=None,cleanup_confirmed=None)))
        self.operation=self.r['operation_id'];self.attempt=self.r['attempt_id']
        self.approved={'p':frozenset({contract.fingerprint(self.r)})}
        self.s.close();self.s=Store(root/'service',self.beads,approved_plans={'p':{plan_digest(PLAN)}},approved_preparing=self.approved)
        self.server=make_server(self.s,{'host1':dict(token='a'*40,projects=['p'])},port=0)
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(self.server.shutdown(),self.server.server_close(),thread.join(2)))
        self.api=APIClient('http://127.0.0.1:'+str(self.server.server_port),'host1','a'*40)
        self.trees=Worktrees({'p':dict(repository=str(self.root),worktree_root=str(root/'trees'))},self.cs)
        self.source=patch.object(contract,'__file__',str(self.module));self.source.start();self.addCleanup(self.source.stop)
        self.starts=[];self.wires=[]
        def request(method,params):
            if method=='thread/start':return {'thread':{'id':'fixture-author'}}
            if method=='turn/start':self.starts.append(params);return {'turn':{'id':'fixture-turn'}}
            raise AssertionError(method)
        def factory(cwd,request_handler=None):
            self.assertEqual(Path(cwd),self.target)
            wire=SimpleNamespace(request=request,notifications=lambda:[],close=lambda:None);self.wires.append(wire)
            return AppServer(self.cs,transport=wire,request_handler=request_handler)
        self.factory=factory
    def absent(self):
        self.assertFalse(self.target.exists());self.assertEqual(self.starts,[]);self.assertIsNone(self.outcome())
    def refused(self):
        self.absent();self.assertEqual(self.cs.pending_events()[0]['lifecycle']['kind'],'failed')
    def original(self):self.assertEqual(self.s.attempt(self.attempt),self.before)
    def quiet(self,c):return patch.object(c,'_deliver_async')
    def outcome(self):return self.cs.preparing_operation(self.operation)
    def status(self):return self.api.preparing_status(self.operation)
    def restart(self,c):
        c.close();self.cs.close();self.cs=ConnectorStore(Path(self.transport.name)/'connector','host1');self.addCleanup(self.cs.close)
        self.trees=Worktrees({'p':dict(repository=str(self.root),worktree_root=str(self.target.parent))},self.cs)
        return self.connector()
    def connector(self,approved=None):
        c=LifecycleConnector(self.cs,self.api,self.trees,self.factory,approved_preparing=self.approved if approved is None else approved)
        self.addCleanup(c.close);return c
    def admit(self):return self.api.admit_preparing(self.r)
    def control(self):
        self.s.admit_preparing(self.r,'host1');return self.s.lifecycle_commands('host1')[0]
    def test_strict_control_schema_bound_to_original_identity(self):
        command=self.control()
        self.assertEqual(self.cs.preparing_control(command),self.r)
        for key,value in [('project_id','foreign'),('attempt_id','foreign'),('base_sha','b'*40),('command_id','foreign'),('receipt',dict(self.r,connector_id='foreign'))]:
            bad=copy.deepcopy(command);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.cs.preparing_control(bad)
        self.assertEqual(len(self.cs.commands()),1);self.assertFalse(self.target.exists())
    def test_real_http_admission_and_safe_status(self):
        first=self.admit();self.assertEqual(first,self.admit())
        status=self.status()
        self.assertEqual(status,first);self.assertEqual(status['state'],'pending')
        self.assertNotIn('receipt',status);self.assertNotIn('input',json.dumps(status))
        self.original()

    def test_one_attach_then_one_normal_start_only_after_known_service_ack(self):
        self.admit();c=self.connector()
        with self.quiet(c),patch.object(self.trees,'attach_preparing',wraps=self.trees.attach_preparing) as attach:
            self.assertTrue(c.tick());self.assertEqual(attach.call_count,1)
            self.assertTrue(self.target.is_dir());self.assertEqual(self.starts,[])
            self.original()
            self.assertEqual(self.cs.command(self.key)['phase'],'needs_reconciliation')
            self.assertEqual(len(self.cs.commands()),1)
            self.assertEqual(self.status()['state'],'pending')
            self.assertTrue(c.tick());self.assertEqual(attach.call_count,1)
            self.assertTrue(c.flush())
            self.assertEqual(self.status()['state'],'prepared')
            deadline=time.monotonic()+5
            while not self.starts and time.monotonic()<deadline:c.tick();time.sleep(.01)
            self.assertEqual(len(self.starts),1);self.assertEqual(len(self.wires),1)
            self.assertEqual(self.starts[0]['input'][0]['text'],self.old['input']['text'])
            for _ in range(3):c.tick()
            self.assertEqual(attach.call_count,1);self.assertEqual(len(self.starts),1)
            self.assertEqual(self.s.active_count('host1'),1)
            self.assertEqual(self.native.rows['pilot-task']['assignee'],self.before['actor'])
            commands=self.cs.commands();self.assertEqual(len(commands),2)
            replacement=next(d['command'] for d in commands if d['command']['command_id']!=self.key)
            self.assertEqual(replacement,dict(self.old,command_id=command_ids(self.r)[1]))
    def test_unconfigured_and_foreign_controls_have_no_local_effect(self):
        self.admit();c=self.connector({})
        with self.quiet(c):c.tick()
        self.absent()
        self.assertEqual(self.cs.pending_events(),[]);self.assertEqual(len(self.cs.commands()),1)
        c.close();c=self.connector();bad=self.control();bad['project_id']='foreign'
        with self.quiet(c),patch.object(self.api,'commands',return_value=[bad]):c.tick()
        self.assertFalse(self.target.exists());self.assertEqual(self.cs.pending_events(),[])
    def test_lost_result_reply_reuses_the_same_event_and_replacement_execute(self):
        self.admit();c=self.connector()
        with self.quiet(c):
            c.tick();event=self.cs.pending_events()[0];send=self.api.send_event
            def lost(value):send(value);raise TimeoutError('synthetic lost acknowledgement')
            with patch.object(self.api,'send_event',side_effect=lost):self.assertFalse(c.flush())
            self.assertEqual(self.cs.pending_events(),[event]);self.assertEqual(self.status()['state'],'prepared')
            self.assertTrue(c.flush());self.assertEqual(self.cs.pending_events(),[])
            queued=self.s.lifecycle_commands('host1');self.assertEqual(len(queued),1)
            self.assertEqual(queued[0]['command_id'],command_ids(self.r)[1])
            self.assertEqual(self.admit()['state'],'prepared')
            self.assertEqual(self.s.lifecycle_commands('host1'),queued)
    def test_native_drift_refuses_before_attach_without_consuming_control(self):
        self.admit();c=self.connector();self.native.rows['pilot-task']['assignee']='foreign-owner'
        with self.quiet(c):c.tick()
        self.absent();self.assertEqual(self.cs.pending_events(),[])
        self.original()
    def test_partial_git_failure_is_unknown_and_never_retried(self):
        self.admit();c=self.connector()
        with self.quiet(c),patch.object(self.trees,'attach_preparing',side_effect=TimeoutError('synthetic private path')) as attach:
            c.tick();self.assertEqual(attach.call_count,1)
            self.assertEqual(self.outcome()['state'],'unknown')
            event=self.cs.pending_events()[0]
            self.assertEqual(event['lifecycle'],dict(kind='failed',command_id=command_ids(self.r)[0]))
            c.tick();self.assertEqual(attach.call_count,1);self.assertEqual(self.cs.pending_events(),[event])
            self.assertNotIn('synthetic private path',json.dumps(event));self.assertTrue(c.flush())
            self.assertEqual(self.status()['state'],'unknown')
            self.original();self.assertEqual(self.starts,[])
    def test_unknown_cleanup_never_attaches_or_starts(self):
        self.admit();c=self.connector()
        self.cs.update(self.key,cleanup_confirmed=False)
        with self.quiet(c),patch.object(self.trees,'attach_preparing',side_effect=AssertionError('must not attach')):
            c.tick();self.refused()

    def test_restart_before_result_delivery_reads_known_outcome_without_attach(self):
        self.admit();c=self.connector()
        with self.quiet(c):c.tick()
        event=self.cs.pending_events()[0];restarted=self.restart(c)
        with self.quiet(restarted),patch.object(self.trees,'attach_preparing',side_effect=AssertionError('Git replay')):
            restarted.tick();self.assertEqual(self.cs.pending_events(),[event])
            self.assertEqual(self.starts,[]);self.assertTrue(restarted.flush())
            self.assertEqual(self.status()['state'],'prepared')
    def test_changed_git_branch_or_executing_source_refuses_before_attach(self):
        self.admit();c=self.connector()
        other=self.git(self.root,'commit-tree',self.git(self.root,'rev-parse','HEAD^{tree}'),'-p',self.head,'-m','other fixture commit')
        self.git(self.root,'update-ref','refs/heads/'+self.r['branch'],other)
        with self.quiet(c),patch.object(self.trees,'attach_preparing',side_effect=AssertionError('Git replay')):
            c.tick();self.refused()
    def test_changed_engine_worktree_refuses_before_intent(self):
        self.admit();c=self.connector();self.module.write_text('# changed fixture engine\n',encoding='utf-8')
        with self.quiet(c):
            c.tick();self.refused()
        self.module.write_text('# disposable source\n',encoding='utf-8')
        control=self.s.lifecycle_commands('host1')[0];validate=self.api.validate_command
        def deliver_during_validation(key):
            value=validate(key);c.flush();return value
        with self.quiet(c),patch.object(self.api,'validate_command',side_effect=deliver_during_validation) as validation:
            c.tick();self.absent();validation.assert_not_called()
            self.assertTrue(c.flush())
        restarted=self.restart(c)
        with self.quiet(restarted),patch.object(self.api,'commands',return_value=[control]),patch.object(self.api,'validate_command') as validation:
            restarted.tick();self.absent();validation.assert_not_called()
            self.assertEqual(self.status()['state'],'unknown')
    def test_unexpected_status_payload_is_not_echoed(self):
        status=self.api._preparing_status(self.admit())
        for bad in (dict(status,input='synthetic-secret'),dict(status,receipt_sha256='synthetic-secret'),dict(status,state='synthetic-secret')):
            with patch.object(self.api,'request',return_value={'preparing':bad}),self.assertRaisesRegex(ValueError,'^invalid_preparing_status$'):
                self.status()
