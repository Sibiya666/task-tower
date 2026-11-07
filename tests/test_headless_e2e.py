"""Release integration boundaries; external model/native/GitHub are fixtures."""
import unittest
from unittest.mock import patch
from task_tower.service.api import make_server


class ContainerNetworkTests(unittest.TestCase):
    def test_container_listener_requires_explicit_linux_namespace_opt_in(self):
        # Catches removing the opt-in or allowing a wildcard listener on the host.
        for kwargs in ({}, {'container_network': True}):
            with self.subTest(kwargs=kwargs), patch('sys.platform', 'win32'):
                with self.assertRaises((ValueError, TypeError)):
                    make_server(None, {}, host='0.0.0.0', port=0, **kwargs)

    def test_non_container_linux_and_arbitrary_binds_are_rejected(self):
        with patch('sys.platform', 'linux'), patch('pathlib.Path.is_file', return_value=False):
            with self.assertRaises(ValueError):make_server(None, {}, host='0.0.0.0', port=0, container_network=True)
        with patch('sys.platform', 'linux'), patch('pathlib.Path.is_file', return_value=True):
            with self.assertRaises(ValueError):make_server(None, {}, host='192.0.2.1', port=0, container_network=True)
            with self.assertRaises(ValueError):make_server(None, {}, port=0, container_network='yes')

    def test_linux_container_listener_retains_loopback_default_and_explicit_bridge_bind(self):
        # Catches an unreachable container API, while host publication stays loopback.
        with patch('task_tower.service.api.HTTPServer') as server:
            with patch('sys.platform', 'linux'), patch('pathlib.Path.is_file', return_value=True):
                try:
                    make_server(None, {}, host='0.0.0.0', port=0, container_network=True)
                except (TypeError, ValueError) as error:
                    self.fail('explicit container namespace bind unavailable: '+str(error))
                self.assertEqual(server.call_args.args[0], ('0.0.0.0', 0))
            make_server(None, {}, port=0)
            self.assertEqual(server.call_args.args[0], ('127.0.0.1', 0))


class HeadlessE2ETests(unittest.TestCase):
    """Real HTTP, journals, Git and app-server command handling in one fixture."""
    def setUp(self):
        import tempfile, subprocess, threading, os, json
        from pathlib import Path
        from task_tower.service.store import Store, plan_digest
        from task_tower.service.beads import Beads
        from tests.test_service_beads import NativeFixture
        from task_tower.connector.client import APIClient, LifecycleConnector
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.worktrees import Worktrees
        from task_tower.connector.app_server import AppServer
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        def git(cwd,*args):
            return subprocess.run(['git','-c','core.hooksPath='+os.devnull,*args],cwd=cwd,
                check=True,capture_output=True,encoding='utf-8',timeout=10).stdout.strip()
        self.git=git
        git(self.repo,'init');git(self.repo,'config','core.autocrlf','false')
        git(self.repo,'config','user.name','Fixture');git(self.repo,'config','user.email','fixture@example.invalid')
        (self.repo/'a.txt').write_text('base\n',encoding='utf-8')
        git(self.repo,'add','a.txt');git(self.repo,'commit','-m','base');self.base=git(self.repo,'rev-parse','HEAD')
        self.plan={'tasks':[dict(id='pilot-'+str(i),title='Useful fixture '+str(i),
            description='Commit a verified fixture change '+str(i),depends_on=[]) for i in range(3)]}
        self.digest=plan_digest(self.plan);self.close_events=[]
        native=NativeFixture();self.native=native;outer=self
        def native_run(argv,cwd,timeout,env):
            args=argv[argv.index('--actor')+2:]
            if args[0]=='history':return [e for e in outer.close_events if e['issue_id']==args[1]]
            result=native(argv,cwd,timeout,env)
            if args[0]=='close':
                outer.close_events.append(dict(id='close-'+args[1],issue_id=args[1],event_type='closed',
                    actor=argv[argv.index('--actor')+1],new_value=args[args.index('--reason')+1]))
            return result
        self.service=Store(self.root/'service',Beads(self.root/'bd',{'p':self.root},runner=native_run),
                           approved_plans={'p':{self.digest}})
        self.addCleanup(self.service.close)
        self.server=make_server(self.service,{'e2e':dict(token='A'*40,projects=['p'])},port=0)
        self.server_thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.server_thread.start()
        self.addCleanup(lambda:(self.server.shutdown(),self.server.server_close(),self.server_thread.join(2)))
        self.api=APIClient('http://127.0.0.1:'+str(self.server.server_port),'e2e','A'*40)
        self.local=ConnectorStore(self.root/'connector','e2e');self.addCleanup(lambda:self.local.close())
        self.trees=Worktrees({'p':dict(repository=str(self.repo),worktree_root=str(self.root/'trees'))},self.local)
        self.wires=[];self.hold=False;self.crash=False
        class Wire:
            def __init__(wire,cwd):
                wire.cwd=Path(cwd);wire.pending=[];wire.closed=False;wire.starts=0
                wire.thread='e2e-thread-'+str(len(outer.wires));outer.wires.append(wire)
            def request(wire,method,params):
                if method=='thread/start':return {'thread':{'id':wire.thread}}
                if method!='turn/start':raise AssertionError(method)
                wire.starts+=1
                if outer.crash:raise TimeoutError('fixture crash after turn/start send')
                review='Return ONLY strict JSON' in params['input'][0]['text']
                if review:
                    text=json.dumps(dict(verdict='approve',findings=[],head_sha=git(wire.cwd,'rev-parse','HEAD'),
                        base_sha=outer.base,reviewer_thread_id=wire.thread))
                else:
                    (wire.cwd/'a.txt').write_text('verified '+wire.thread+'\n',encoding='utf-8')
                    git(wire.cwd,'add','a.txt');git(wire.cwd,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture result')
                    text='Committed verified result'
                wire.pending.append(dict(method='turn/completed',params=dict(threadId=wire.thread,
                    turn=dict(id='turn-'+wire.thread,status='completed',items=[dict(type='agentMessage',text=text)]))))
                return {'turn':{'id':'turn-'+wire.thread}}
            def notifications(wire):
                if outer.hold:return []
                pending=wire.pending;wire.pending=[];return pending
            def close(wire):wire.closed=True
        self.factory=lambda cwd,request_handler=None:AppServer(self.local,transport=Wire(cwd),request_handler=request_handler)
        self.connector=LifecycleConnector(self.local,self.api,self.trees,self.factory)
        self.addCleanup(lambda:self.connector.close())
        batch=self.api.request('POST','/v1/plans/import',dict(version=1,request_id='import',project_id='p',digest=self.digest,plan=self.plan))
        self.assertEqual(batch['batch']['state'],'published')
        self.assertEqual(len(self.api.ready('p')),3)

    def start(self,index):
        a=self.api.claim(dict(version=1,request_id='claim-'+str(index),project_id='p',
            bead_id='pilot-'+str(index),connector_id='e2e'))
        return self.api.dispatch(a['attempt_id'],self.base)

    def until(self,predicate,seconds=15):
        import time
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            self.connector.tick()
            if predicate():return
            time.sleep(.01)
        self.fail('bounded E2E condition not reached: '+str([(d['phase'],d['command'].get('kind')) for d in self.local.commands()]))

    def test_import_to_independent_review_protected_delivery_main_and_canonical_close(self):
        from task_tower.connector.delivery import Delivery
        from tests.test_headless_delivery import Host, REPO
        from tests.test_headless_acceptance import evidence
        outer=self
        class GitHub(Host):
            def prepare_pr(host,a):
                host.pr.update(branch='codex/headless-'+a['attempt_id'],head_sha=a['head_sha'],base_sha=a['base_sha'])
                for c in host.checks:c['head_sha']=a['head_sha']
                return super().prepare_pr(a)
            def verify_main(host,a,merge):
                outer.assertEqual(outer.service.attempt(a['attempt_id'])['phase'],'postmerge')
                proof=evidence(a);proof['postmerge_review']['base_sha']=a['base_sha'];return proof
        host=GitHub();self.service.delivery_projects={'p':REPO}
        self.connector.delivery=Delivery(host,self.local,{'p':REPO})
        a=self.start(0)
        self.until(lambda:self.service.attempt(a['attempt_id'])['phase']=='accepted' and
                   any(d['command'].get('kind')=='deliver' and d['phase']=='completed' for d in self.local.commands()))
        final=self.service.attempt(a['attempt_id'])
        self.assertEqual(self.native.rows['pilot-0']['status'],'closed')
        self.assertEqual(final['canonical_close']['event_id'],'close-pilot-0')
        self.assertNotEqual(final['author_thread_id'],final['review']['reviewer_thread_id'])
        self.assertNotIn(final['accepted_evidence']['postmerge_review']['reviewer_thread_id'],
                         [final['author_thread_id'],*final['review_threads']])
        self.assertEqual(host.calls.count('merge'),1)
        self.assertTrue(all(w.closed for w in self.wires))
        self.assertEqual(self.local.cleanup_reservations(),set())
        self.assertEqual(sum('close' in c for c in self.native.calls),1)

    def test_two_live_worktrees_third_waits_in_native_beads(self):
        self.hold=True;a=self.start(0);b=self.start(1)
        self.until(lambda:len(self.wires)==2 and all(w.starts==1 for w in self.wires))
        with self.assertRaises(ConnectionError):self.start(2)
        self.assertEqual(self.native.rows['pilot-2']['status'],'open')
        self.assertEqual(len({w.cwd for w in self.wires}),2)
        self.assertFalse(any(w.closed for w in self.wires))
        self.hold=False
        self.until(lambda:all(self.service.attempt(v['attempt_id'])['phase']=='awaiting_merge' for v in (a,b)))
        self.assertEqual(len(self.wires),4)

    def test_http_outage_keeps_owned_turn_and_replays_durable_outbox(self):
        from unittest.mock import patch
        self.hold=True;a=self.start(0)
        self.until(lambda:len(self.wires)==1 and self.wires[0].starts==1)
        # Only HTTP transport fails; the owned RPC worker keeps draining.
        with patch.object(self.api,'request',side_effect=ConnectionError('HTTP unavailable')):
            self.hold=False
            self.until(lambda:any(d['phase']=='completed' for d in self.local.commands()))
            self.assertTrue(self.local.pending_events())
            ids=[e['event_id'] for e in self.local.pending_events()]
            self.assertFalse(self.wires[0].closed)
            self.assertEqual(len(self.wires),1)
        self.until(lambda:self.service.attempt(a['attempt_id'])['phase']=='awaiting_merge' and not self.local.pending_events())
        recorded={r[0] for r in self.service.db.execute('SELECT event_id FROM events')}
        self.assertTrue(set(ids)<=recorded)
        self.assertEqual(self.wires[0].starts,1)

    def test_crash_start_and_reopen_never_repeat_unknown_launch(self):
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.client import LifecycleConnector
        self.crash=True;a=self.start(0)
        self.until(lambda:any(d['phase']=='needs_reconciliation' for d in self.local.commands()))
        self.connector.close();self.local.close()
        self.local=ConnectorStore(self.root/'connector','e2e')
        self.connector=LifecycleConnector(self.local,self.api,self.trees,
            lambda *args,**kwargs:self.fail('unknown turn/start replayed after restart'))
        for _ in range(3):self.connector.tick()
        self.assertEqual(len(self.wires),1);self.assertEqual(self.wires[0].starts,1)
        self.assertEqual(self.native.rows['pilot-0']['status'],'in_progress')
        self.assertEqual(self.local.commands()[0]['phase'],'needs_reconciliation')
