"""Lifecycle contracts: real journal transactions, fixed roles and bounded capacity."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from task_tower.service.beads import ServiceError
from task_tower.service.store import Store, plan_digest
from tests.test_service_beads import NativeFixture, Beads

BASE='a'*40
HEAD='b'*40
SOURCE=dict(base_sha=BASE,head_sha=HEAD,diff='diff --git a/a.txt b/a.txt\n+fixed\n')
PLAN={'tasks':[dict(id='pilot-'+str(i),title='Task '+str(i),description='Approved criteria '+str(i),depends_on=[]) for i in range(3)]}

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'service'
        self.native=NativeFixture();self.beads=Beads(self.root/'bd',{'p':self.root},runner=self.native)
        self.s=Store(self.path,self.beads,approved_plans={'p':{plan_digest(PLAN)}})
        self.addCleanup(lambda:self.s.close())
        self.s.import_plan('import','p',plan_digest(PLAN),PLAN);self.seq=0
    def claim(self,i=0):return self.s.claim_request('r'+str(i),'p','pilot-'+str(i),'host1')
    def event(self,a,kind,**payload):
        self.seq+=1
        return dict(version=1,event_id='event'+str(self.seq),attempt_id=a['attempt_id'],connector_id='host1',lifecycle=dict(kind=kind,**payload))
    def emit(self,a,kind,**payload):return self.s.record_event(self.event(a,kind,**payload))
    def commands(self,a):return [c for c in self.s.lifecycle_commands('host1') if c['attempt_id']==a['attempt_id']]
    def start(self,i=0):
        a=self.claim(i);self.s.start_lifecycle(a['attempt_id'],'host1',BASE)
        return self.s.attempt(a['attempt_id'])
    def complete(self,a,thread,output='done',source=None):
        command=self.commands(a)[-1]
        self.emit(a,'started',command_id=command['command_id'],thread_id=thread,turn_id='turn-'+command['command_id'])
        payload=dict(command_id=command['command_id'],thread_id=thread,turn_id='turn-'+command['command_id'],result=output)
        if source is not None:payload['source']=source
        return self.emit(a,'completed',**payload)
    def verdict(self,thread,verdict='changes_requested',**kw):
        return json.dumps(dict(verdict=verdict,findings=[] if verdict=='approve' else [dict(file='a.txt',line=1,message='Fix behavior')],head_sha=HEAD,base_sha=BASE,reviewer_thread_id=thread,**kw))
    def test_findings_resume_author_and_each_review_has_new_thread(self):
        a=self.start();self.complete(a,'author',source=SOURCE)
        review=self.commands(a)[-1];self.assertEqual(review['kind'],'review')
        self.complete(a,'review1',self.verdict('review1'))
        revise=self.commands(a)[-1]
        self.assertEqual((revise['kind'],revise['thread_id']),('revise','author'))
        self.complete(a,'author',source=SOURCE)
        command=self.commands(a)[-1]
        with self.assertRaises(ServiceError):self.emit(a,'started',command_id=command['command_id'],thread_id='review1',turn_id='bad')
        with self.assertRaises(ServiceError):self.emit(a,'started',command_id=command['command_id'],thread_id='author',turn_id='bad')
        self.complete(a,'review2',self.verdict('review2','approve'))
        result=self.s.attempt(a['attempt_id'])
        self.assertEqual(result['phase'],'awaiting_merge');self.assertNotEqual(result['phase'],'accepted')
        self.assertEqual(self.native.rows['pilot-0']['status'],'in_progress')
    def test_fourth_negative_pauses_without_fourth_correction(self):
        a=self.start();self.complete(a,'author',source=SOURCE)
        for i in range(4):
            result=self.complete(a,'review'+str(i),self.verdict('review'+str(i)))
            if i<3:
                self.assertEqual(result['correction_count'],i+1)
                self.assertEqual(self.commands(a)[-1]['kind'],'revise')
                self.complete(a,'author',source=SOURCE)
        self.assertEqual((result['phase'],result['correction_count']),('needs_input',3))
        self.assertFalse(result['quiescent']);self.assertEqual(self.commands(a)[-1]['kind'],'quiesce')
    def test_capacity_disconnect_limit_reduction_and_quiescent_ack(self):
        a=self.start(0);self.start(1)
        self.emit(a,'disconnected')
        with self.assertRaises(ServiceError):self.claim(2)
        self.s.max_active_tasks=1
        self.assertEqual(self.s.attempt(a['attempt_id'])['phase'],'executing')
        self.emit(a,'pause')
        with self.assertRaises(ServiceError):self.claim(2)
        stop=self.commands(a)[-1]
        self.emit(a,'quiescent',command_id=stop['command_id'])
        with self.assertRaises(ServiceError):self.claim(2)
        self.s.max_active_tasks=2;third=self.claim(2)
        self.assertEqual(third['phase'],'claimed')
        with self.assertRaises(ServiceError):self.s.resume_lifecycle(a['attempt_id'],'host1')
    def test_commands_events_and_state_roll_back_together_and_deduplicate(self):
        a=self.start();c=self.commands(a)[-1]
        self.emit(a,'started',command_id=c['command_id'],thread_id='author',turn_id='turn1')
        e=self.event(a,'completed',command_id=c['command_id'],thread_id='author',turn_id='turn1',result='done',source=SOURCE)
        self.s.db.execute("CREATE TRIGGER fail_state BEFORE UPDATE ON attempts BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.s.record_event(e)
        self.assertEqual(self.s.attempt(a['attempt_id'])['phase'],'executing')
        self.assertEqual(len(self.commands(a)),1)
        self.s.db.execute('DROP TRIGGER fail_state')
        first=self.s.record_event(e);self.assertEqual(self.s.record_event(e),first)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM lifecycle_commands').fetchone()[0],2)
        self.assertEqual(len(self.commands(a)),1)
        self.assertEqual(self.commands(a)[-1]['kind'],'review')
    def test_stale_malformed_and_forged_review_fail_closed(self):
        for change in ('stale','foreign','extra','prose','duplicate','findings'):
            with self.subTest(change=change):
                a=self.start();self.complete(a,'author',source=SOURCE)
                c=self.commands(a)[-1];self.emit(a,'started',command_id=c['command_id'],thread_id='review',turn_id='t')
                value=json.loads(self.verdict('review','approve'))
                if change=='stale':value['base_sha']='c'*40
                if change=='foreign':value['reviewer_thread_id']='invented'
                if change=='extra':value['accepted']=True
                if change=='findings':value['findings']=[dict(file='a',line=1,message='blocker')]
                text='approve' if change=='prose' else json.dumps(value)
                if change=='duplicate':text=text[:-1]+',"verdict":"approve"}'
                with self.assertRaises(ServiceError):self.emit(a,'completed',command_id=c['command_id'],thread_id='review',turn_id='t',result=text)
                self.assertEqual(self.s.attempt(a['attempt_id'])['phase'],'reviewing')
                self.s.close();self.path=self.root/('s-'+change);self.s=Store(self.path,self.beads,approved_plans={'p':{plan_digest(PLAN)}})
                self.native.rows.clear();self.s.import_plan('i','p',plan_digest(PLAN),PLAN)
    def test_restart_preserves_commands_without_reissuing_unknown_work(self):
        a=self.start();command=self.commands(a)[0]
        self.s.close();self.s=Store(self.path,self.beads,approved_plans={'p':{plan_digest(PLAN)}})
        self.assertEqual(self.commands(a),[command])
        with self.assertRaises(ServiceError):self.s.start_lifecycle(a['attempt_id'],'host1',BASE)
    def test_explicit_resume_only_after_stop_and_native_revalidation(self):
        a=self.start();self.complete(a,'author',source=SOURCE)
        self.emit(a,'pause');stop=self.commands(a)[-1]
        with self.assertRaises(ServiceError):self.s.resume_lifecycle(a['attempt_id'],'host1')
        self.emit(a,'quiescent',command_id=stop['command_id'])
        self.native.rows['pilot-0']['assignee']='foreign'
        with self.assertRaises(ServiceError):self.s.resume_lifecycle(a['attempt_id'],'host1')
        self.native.rows['pilot-0']['assignee']=a['actor']
        resumed=self.s.resume_lifecycle(a['attempt_id'],'host1')
        self.assertEqual(resumed['phase'],'revising');self.assertEqual(self.commands(a)[-1]['thread_id'],'author')
    def test_legacy_events_cannot_bypass_managed_review(self):
        a=self.start()
        with self.assertRaises(ServiceError):self.s.record_event(dict(version=1,event_id='forged',attempt_id=a['attempt_id'],connector_id='host1',phase='awaiting_merge',execution_state='completed',connection_state='connected'))
    def test_pure_advance_does_not_mutate_and_brief_contains_actual_contract(self):
        from task_tower.service.lifecycle import advance
        from task_tower.connector.briefs import build_brief
        a=dict(phase='claimed',execution_state='not_started');before=copy.deepcopy(a)
        self.assertEqual(advance(a,dict(kind='dispatch'),{} )[-1]['kind'],'execute')
        self.assertEqual(a,before)
        brief=build_brief(PLAN['tasks'][0],'reviewer',SOURCE)
        self.assertEqual(brief['source'],SOURCE);self.assertEqual(brief['criteria'],'Approved criteria 0')
        self.assertIn('Superpowers',brief['input']['text']);self.assertIn(SOURCE['diff'],brief['input']['text'])

class DecisionTransportTests(unittest.TestCase):
    setUp=LifecycleTests.setUp
    claim=LifecycleTests.claim
    event=LifecycleTests.event
    emit=LifecycleTests.emit
    commands=LifecycleTests.commands
    start=LifecycleTests.start
    # Real service API/CLI boundaries, not a second simulation of the transition table.
    def test_structured_decision_visible_and_explicit_response_only(self):
        a=self.start();c=self.commands(a)[-1]
        self.emit(a,'started',command_id=c['command_id'],thread_id='author',turn_id='t')
        self.emit(a,'approval',command_id=c['command_id'],decision_id='decision1',request=dict(method='item/commandExecution/requestApproval',request_id=99,question='Allow fixed command?'))
        self.assertEqual(self.s.attempt(a['attempt_id'])['phase'],'needs_input')
        self.assertFalse(self.s.attempt(a['attempt_id'])['quiescent'])
        self.assertEqual(self.s.decisions('host1')[0]['status'],'pending')
        self.assertFalse(any(x['kind']=='respond' for x in self.commands(a)))
        self.s.respond_decision('decision1','host1','decline')
        reply=self.commands(a)[-1]
        self.assertEqual((reply['kind'],reply['answer']),('respond','decline'))
        self.emit(a,'responded',command_id=reply['command_id'])
        self.assertEqual(self.s.attempt(a['attempt_id'])['phase'],'executing')
        self.assertEqual(self.s.decisions('host1')[0]['status'],'answered')
        with self.assertRaises(ServiceError):self.s.respond_decision('decision1','host1','approve')
    def test_actual_http_command_routes_cli_decision_and_native_preflight(self):
        import threading
        import io
        from contextlib import redirect_stdout
        from task_tower.service.api import make_server
        from task_tower.connector.client import APIClient
        from task_tower.connector.cli import main
        server=make_server(self.s,{'host1':dict(token='a'*40,projects=['p'])},port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(2)))
        api=APIClient('http://127.0.0.1:'+str(server.server_port),'host1','a'*40)
        a=self.claim();api.dispatch(a['attempt_id'],BASE)
        commands=api.commands();self.assertEqual(len(commands),1)
        self.assertEqual(api.validate_command(commands[0]['command_id'])['actor'],a['actor'])
        self.native.rows['pilot-0']['assignee']='foreign'
        with self.assertRaises(ConnectionError):api.validate_command(commands[0]['command_id'])
        self.assertEqual(api.decisions(),[])
        with self.assertRaises(ConnectionError):APIClient('http://127.0.0.1:'+str(server.server_port),'host1','b'*40).commands()

class ConnectorLifecycleTests(unittest.TestCase):
    def _cycle(self,mode='happy'):
        import subprocess
        import sys
        import threading
        import time
        from task_tower.connector.client import APIClient,LifecycleConnector
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.worktrees import Worktrees
        from task_tower.connector.app_server import AppServer
        from task_tower.service.api import make_server
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'repo';repo.mkdir()
            def git(cwd,*args):return subprocess.run(['git','-c','core.hooksPath='+__import__('os').devnull,*args],cwd=cwd,check=True,capture_output=True,encoding='utf-8',timeout=10).stdout.strip()
            git(repo,'init');git(repo,'config','core.autocrlf','false');git(repo,'config','user.name','Fixture');git(repo,'config','user.email','fixture@example.invalid')
            (repo/'a.txt').write_text('base\n',encoding='utf-8');git(repo,'add','a.txt');git(repo,'commit','-m','base');base=git(repo,'rev-parse','HEAD')
            native=NativeFixture();s=Store(root/'service',Beads(root/'bd',{'p':root},runner=native),approved_plans={'p':{plan_digest(PLAN)}})
            cs=ConnectorStore(root/'connector','lifecycle-test-host');trees=Worktrees({'p':dict(repository=str(repo),worktree_root=str(root/'trees'))},cs)
            server=make_server(s,{'lifecycle-test-host':dict(token='a'*40,projects=['p'])},port=0)
            st=threading.Thread(target=server.serve_forever,daemon=True);st.start()
            api=APIClient('http://127.0.0.1:'+str(server.server_port),'lifecycle-test-host','a'*40)
            ids=[];roles=[];wires=[]
            class Wire:
                count=0
                reviews=0
                def __init__(self,cwd):self.cwd=Path(cwd);self.pending=[];self.thread=None;self.closed=False;self.waiting=None;self.responses=[];self.response_ready=threading.Event();wires.append(self)
                def request(self,method,params):
                    if method=='thread/start':
                        Wire.count+=1;self.thread='real-thread-'+str(Wire.count);return {'thread':{'id':self.thread}}
                    if method=='turn/start':
                        if mode=='early-approval' and not ids:
                            self.request_handler(dict(id=99,method='item/commandExecution/requestApproval',params=dict(reason='Explicit fixture command?')),self.respond)
                            if not self.response_ready.wait(3):raise TimeoutError('no explicit approval response')
                        text=params['input'][0]['text'];review='Return ONLY strict JSON' in text
                        ids.append(params['threadId']);roles.append('review' if review else 'executor')
                        turn='turn-'+str(len(ids))
                        if review:
                            Wire.reviews+=1;head=git(self.cwd,'rev-parse','HEAD')
                            result=json.dumps(dict(verdict='changes_requested' if (Wire.reviews==1 or mode=='four-negative') else 'approve',findings=[dict(file='a.txt',line=1,message='Add evidence')] if (Wire.reviews==1 or mode=='four-negative') else [],head_sha=head,base_sha=base,reviewer_thread_id=self.thread))
                        else:
                            (self.cwd/'a.txt').write_text('changed '+str(len(ids))+'\n',encoding='utf-8');git(self.cwd,'add','a.txt');git(self.cwd,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','change');result='Implementation complete'
                        completion=dict(method='turn/completed',params=dict(threadId=self.thread,turn=dict(id=turn,status='completed',items=[dict(type='agentMessage',text=result)])))
                        if mode=='approval' and len(ids)==1:
                            self.waiting=completion
                            self.pending.append(dict(id=99,method='item/commandExecution/requestApproval',params=dict(threadId=self.thread,reason='Explicit fixture command?')))
                        else:self.pending.append(completion)
                        if mode=='review-edits' and review:(self.cwd/'a.txt').write_text('unauthorized review edit',encoding='utf-8')
                        return {'turn':{'id':turn}}
                    raise AssertionError(method)
                def notifications(self):pending=self.pending;self.pending=[];return pending
                def respond(self,key,result):
                    if key!=99 or result!={'decision':'decline'}:raise AssertionError('wrong approval response')
                    self.responses.append(result);self.response_ready.set()
                    if mode=='early-approval':time.sleep(.8)
                    if self.waiting:self.pending.append(self.waiting);self.waiting=None
                def close(self):self.closed=True
            def factory(cwd,request_handler=None):
                if mode=='factory-drift':native.rows['pilot-0']['assignee']='foreign'
                return AppServer(cs,transport=Wire(cwd),request_handler=request_handler)
            c=LifecycleConnector(cs,api,trees,factory)
            try:
                s.import_plan('i','p',plan_digest(PLAN),PLAN)
                a=api.claim(dict(version=1,request_id='r',project_id='p',bead_id='pilot-0',connector_id=cs.connector_id));api.dispatch(a['attempt_id'],base)
                deadline=time.monotonic()+20
                expected='needs_reconciliation' if mode in ('review-edits','factory-drift') else 'needs_input' if mode=='four-negative' else 'awaiting_merge'
                observed_decision=False
                while (s.attempt(a['attempt_id'])['phase']!=expected or (mode=='four-negative' and not s.attempt(a['attempt_id']).get('quiescent'))) and time.monotonic()<deadline:
                    c.tick();time.sleep(.01)
                    if mode in ('approval','early-approval') and not observed_decision and api.decisions():
                        observed_decision=True
                        self.assertFalse(any(w.responses for w in wires))
                        d=api.decisions()[0];self.assertEqual(d['question'],'Explicit fixture command?')
                        api.respond(d['decision_id'],'decline')
                final=s.attempt(a['attempt_id']);self.assertEqual(final['phase'],expected)
                if mode=='factory-drift':self.assertEqual(Wire.count,0);self.assertEqual(ids,[]);return
                if mode=='review-edits':return
                if mode=='four-negative':
                    self.assertTrue(final['quiescent']);self.assertEqual(final['correction_count'],3)
                    self.assertEqual(roles,['executor','review']*4)
                    self.assertEqual(len(set(ids[::2])),1);self.assertEqual(len(set(ids[1::2])),4)
                    self.assertEqual(len(wires),5);return
                if mode in ('approval','early-approval'):self.assertTrue(observed_decision)
                if mode=='early-approval':
                    kinds=[json.loads(row[0])['lifecycle']['kind'] for row in cs.db.execute('SELECT data FROM outbox ORDER BY seq')]
                    self.assertLess(kinds.index('responded'),kinds.index('started'))
                self.assertEqual(roles,['executor','review','executor','review'])
                self.assertEqual(ids[0],ids[2]);self.assertEqual(len({ids[0],ids[1],ids[3]}),3)
                self.assertEqual(final['correction_count'],1)
                self.assertEqual(native.rows['pilot-0']['status'],'in_progress')
                self.assertEqual(len([v for v in cs.commands() if v['command'].get('kind')=='execute']),1)
                self.assertTrue(all(v['phase']=='completed' for v in cs.commands()))
            finally:c.close();server.shutdown();server.server_close();st.join(2);cs.close();s.close()
            self.assertTrue(all(w.closed for w in wires))

    def test_real_http_git_execution_review_correction_same_author_and_new_reviewer(self):self._cycle()
    def test_real_three_corrections_fourth_negative_quiesces_same_author_process(self):self._cycle('four-negative')
    def test_live_structured_approval_waits_for_explicit_response(self):self._cycle('approval')
    def test_approval_before_start_ack_uses_live_response_without_replaying_start(self):self._cycle('early-approval')
    def test_native_owner_drift_during_launch_blocks_thread_creation(self):self._cycle('factory-drift')
    def test_reviewer_cannot_modify_detached_checkout_and_accept(self):self._cycle('review-edits')

class LifecycleFaultTests(unittest.TestCase):
    setUp=LifecycleTests.setUp
    claim=LifecycleTests.claim
    event=LifecycleTests.event
    emit=LifecycleTests.emit
    commands=LifecycleTests.commands
    start=LifecycleTests.start
    complete=LifecycleTests.complete
    verdict=LifecycleTests.verdict
    def test_superseded_completion_cannot_block_quiescence_delivery(self):
        a=self.start();command=self.commands(a)[-1]
        self.emit(a,'started',command_id=command['command_id'],thread_id='author',turn_id='t')
        self.emit(a,'pause');stop=self.commands(a)[-1]
        value=self.emit(a,'completed',command_id=command['command_id'],thread_id='author',turn_id='t',result='late',source=SOURCE)
        self.assertEqual(value['phase'],'needs_input')
        self.assertEqual(self.emit(a,'quiescent',command_id=stop['command_id'])['quiescent'],True)
    def test_review_thread_cannot_be_reused_by_another_attempt(self):
        a=self.start(0);self.complete(a,'author0',source=SOURCE)
        self.complete(a,'review-used',self.verdict('review-used','approve'))
        b=self.start(1);self.complete(b,'author1',source=SOURCE);command=self.commands(b)[-1]
        with self.assertRaises(ServiceError):self.emit(b,'started',command_id=command['command_id'],thread_id='review-used',turn_id='t')
    def test_cli_lists_and_responds_without_opening_model_or_journal(self):
        import io
        import threading
        from unittest.mock import patch
        from contextlib import redirect_stdout
        from task_tower.connector.cli import main
        from task_tower.service.api import make_server
        a=self.start();c=self.commands(a)[-1]
        self.emit(a,'started',command_id=c['command_id'],thread_id='author',turn_id='t')
        self.emit(a,'approval',command_id=c['command_id'],decision_id='d1',request=dict(method='item/fileChange/requestApproval',request_id=1,question='Allow patch?'))
        server=make_server(self.s,{'host1':dict(token='a'*40,projects=['p'])},port=0)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        cfg=dict(version=1,connector_id='host1',endpoint='http://127.0.0.1:'+str(server.server_port),token_file=str(self.root/'token'),journal=str(self.root/'unused-journal'),app_server=str(self.root/'codex'),projects={'p':dict(repository=str(self.root),worktree_root=str(self.root/'trees'))},assignments=[])
        config=self.root/'operator.json';config.write_text(json.dumps(cfg),encoding='utf-8')
        try:
            with patch('task_tower.connector.cli.read_token',return_value='a'*40),redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['decision','list','--config',str(config)]),0)
                self.assertIn('Allow patch?',out.getvalue())
                self.assertEqual(main(['decision','respond','d1','--answer','decline','--config',str(config)]),0)
            self.assertFalse((self.root/'unused-journal').exists())
            self.assertEqual(self.s.decisions('host1')[0]['answer'],'decline')
        finally:server.shutdown();server.server_close();t.join(2)

class ManagedTransportTests(unittest.TestCase):
    def test_real_subprocess_callback_waits_for_explicit_response_and_retains_rpc_deadline(self):
        import subprocess,sys,threading,time
        from unittest.mock import patch
        from task_tower.connector.app_server import StdioTransport
        script="""import sys,json
for line in sys.stdin:
 m=json.loads(line)
 if 'method' not in m:
  assert m=={'id':99,'result':{'decision':'decline'}}
  print(json.dumps({'id':pending,'result':{'ok':True}}),flush=True)
 elif m['method']=='initialize':print(json.dumps({'id':m['id'],'result':{}}),flush=True)
 elif m['method']=='request':
  pending=m['id'];print(json.dumps({'id':99,'method':'item/commandExecution/requestApproval','params':{'reason':'Explicit command?'}}),flush=True)
"""
        original=subprocess.Popen;requests=[]
        def launch(argv,**kwargs):return original([sys.executable,'-u','-c',script],**kwargs)
        def handle(message,reply):requests.append((message,reply))
        with tempfile.TemporaryDirectory() as temp,patch('task_tower.connector.app_server.subprocess.Popen',side_effect=launch):
            wire=StdioTransport(Path(sys.executable),Path(temp),timeout=1,request_handler=handle)
            outcome=[]
            def invoke():outcome.append(wire.request('request',{}))
            t=threading.Thread(target=invoke);t.start()
            try:
                deadline=time.monotonic()+.5
                while not requests and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(requests);self.assertEqual(outcome,[])
                requests[0][1](99,{'decision':'decline'});t.join(2)
                self.assertEqual(outcome,[{'ok':True}]);self.assertFalse(t.is_alive())
            finally:wire.close();t.join(2)

class AdditionalLifecycleFaults(unittest.TestCase):
    setUp=LifecycleTests.setUp
    claim=LifecycleTests.claim
    event=LifecycleTests.event
    emit=LifecycleTests.emit
    commands=LifecycleTests.commands
    start=LifecycleTests.start
    def test_response_unknown_is_fenced_not_resent(self):
        a=self.start();c=self.commands(a)[-1]
        self.emit(a,'started',command_id=c['command_id'],thread_id='author',turn_id='t')
        self.emit(a,'approval',command_id=c['command_id'],decision_id='d',request=dict(method='item/fileChange/requestApproval',request_id=99,question='Patch?'))
        self.s.respond_decision('d','host1','approve');reply=self.commands(a)[-1]
        outcome=self.emit(a,'failed',command_id=reply['command_id'])
        self.assertEqual(outcome['phase'],'needs_reconciliation')
        with self.assertRaises(ServiceError):self.s.respond_decision('d','host1','approve')
        self.assertEqual(self.s.active_count('host1'),1)
    def test_restart_pending_managed_commands_emit_same_durable_fence(self):
        from task_tower.connector.store import ConnectorStore
        for phase in ('queued','creating_thread','starting','executing','needs_input'):
            with self.subTest(phase=phase):
                path=self.root/('connector-'+phase)
                cs=ConnectorStore(path,'restart-'+phase)
                command=dict(version=1,kind='execute',command_id='c',attempt_id='a',project_id='p',base_sha=BASE,input={'text':'Approved'},source=dict(base_sha=BASE,head_sha=BASE,diff=''))
                cs.receive(command);cs.update('c',phase=phase);cs.close()
                cs=ConnectorStore(path,'restart-'+phase)
                try:
                    self.assertEqual(cs.receive(command)['phase'],'needs_reconciliation')
                    events=cs.pending_events();self.assertEqual(len(events),1)
                    self.assertEqual(events[0]['lifecycle'],dict(kind='failed',command_id='c'))
                    cs.close();cs=ConnectorStore(path,'restart-'+phase)
                    self.assertEqual(cs.pending_events(),events)
                finally:cs.close()
    def test_managed_attempt_cannot_create_decision_from_freeform_question(self):
        a=self.start()
        with self.assertRaises(ServiceError):self.s.decision(dict(version=1,decision_id='prose',attempt_id=a['attempt_id'],connector_id='host1',question='agent says approve'))

class RunningCommandFenceTests(unittest.TestCase):
    setUp=LifecycleTests.setUp
    claim=LifecycleTests.claim
    event=LifecycleTests.event
    emit=LifecycleTests.emit
    commands=LifecycleTests.commands
    start=LifecycleTests.start
    def test_acknowledged_start_revokes_fresh_effect_authority(self):
        a=self.start();c=self.commands(a)[-1]
        self.assertEqual(self.s.validate_lifecycle_command(c['command_id'],'host1')['execution_state'],'not_started')
        self.emit(a,'started',command_id=c['command_id'],thread_id='author',turn_id='t')
        with self.assertRaises(ServiceError):self.s.validate_lifecycle_command(c['command_id'],'host1')
        self.emit(a,'disconnected')
        with self.assertRaises(ServiceError):self.s.validate_lifecycle_command(c['command_id'],'host1')
        self.assertEqual(self.s.active_count('host1'),1)

class LocalCapacityAdmissionTests(unittest.TestCase):
    """Real service2/connector1 admission; only owned RPC workers are held at a barrier."""
    def setUp(self):
        import queue,threading,uuid
        from task_tower.connector.client import APIClient,LifecycleConnector,Connector
        from task_tower.connector.store import ConnectorStore
        from task_tower.service.api import make_server
        LifecycleTests.setUp(self)
        self.host='capacity-'+uuid.uuid4().hex
        self.cs=ConnectorStore(self.root/'local',self.host);self.addCleanup(self.cs.close)
        self.server=make_server(self.s,{self.host:dict(token='a'*40,projects=['p'])},port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(lambda:(self.server.shutdown(),self.server.server_close(),self.thread.join(2)))
        self.api=APIClient('http://127.0.0.1:'+str(self.server.server_port),self.host,'a'*40)
        self.c=LifecycleConnector(self.cs,self.api,None,None,max_active_tasks=1)
        # Existing workers are deliberately held before queue consumption: this is
        # the reservation window; no model or transport behavior is mocked here.
        self.addCleanup(lambda:Connector.close(self.c))
    def emit(self,a,kind,**payload):
        import uuid
        return self.api.send_event(dict(version=1,event_id=str(uuid.uuid4()),attempt_id=a['attempt_id'],connector_id=self.host,lifecycle=dict(kind=kind,**payload)))['attempt']
    def worker(self):
        import queue
        return dict(queue=queue.Queue(4),apps={},replies={},busy=False,reserved=0)
    def active(self,i):
        a=self.s.claim_request('capacity-r'+str(i),'p','pilot-'+str(i),self.host)
        self.api.dispatch(a['attempt_id'],BASE)
        command=next(c for c in self.api.commands() if c['attempt_id']==a['attempt_id'])
        self.cs.receive(command);self.cs.update(command['command_id'],phase='executing',thread_id='author'+str(i),turn_id='t'+str(i))
        self.emit(a,'started',command_id=command['command_id'],thread_id='author'+str(i),turn_id='t'+str(i))
        worker=self.worker();worker['apps'][command['command_id']]=object();self.c.workers[a['attempt_id']]=worker
        return a,command,worker
    def paused(self,i):
        a,command,worker=self.active(i)
        self.emit(a,'pause');stop=next(c for c in self.api.commands() if c['attempt_id']==a['attempt_id'])
        self.emit(a,'quiescent',command_id=stop['command_id'])
        worker['apps'].clear();self.cs.update(command['command_id'],phase='completed')
        return a,command,worker
    def test_service2_connector1_existing_idle_resume_waits_for_local_slot(self):
        active,active_command,aw=self.active(0);paused,_,pw=self.paused(1)
        self.api.resume(paused['attempt_id'])
        revision=next(c for c in self.api.commands() if c['attempt_id']==paused['attempt_id'])
        self.c.tick()
        self.assertTrue(aw['apps']);self.assertTrue(pw['queue'].empty())
        self.assertNotIn(revision['command_id'],self.c.seen)
        self.assertFalse(any(d['command']['command_id']==revision['command_id'] for d in self.cs.commands()))
        self.assertEqual(self.s.active_count(self.host),2)
        self.emit(active,'pause');stop=next(c for c in self.api.commands() if c['attempt_id']==active['attempt_id'])
        self.emit(active,'quiescent',command_id=stop['command_id'])
        aw['apps'].clear();self.cs.update(active_command['command_id'],phase='completed')
        self.c.tick();self.assertEqual(pw['queue'].qsize(),1)
        self.assertIn(revision['command_id'],self.c.seen)
        self.c.tick();self.assertEqual(pw['queue'].qsize(),1)
    def test_queued_activation_reserves_slot_before_existing_idle_worker_consumes(self):
        first,_,fw=self.paused(0);second,_,sw=self.paused(1)
        self.api.resume(first['attempt_id']);self.api.resume(second['attempt_id'])
        self.c.tick()
        self.assertEqual(fw['queue'].qsize()+sw['queue'].qsize(),1)
        self.assertEqual(len([d for d in self.cs.commands() if d['command']['kind']=='revise']),1)
        # Repeated polling must retain the same reservation and defer the other ID.
        self.c.tick()
        self.assertEqual(fw['queue'].qsize()+sw['queue'].qsize(),1)
        self.assertEqual(len([d for d in self.cs.commands() if d['command']['kind']=='revise']),1)
    def test_quiesce_for_existing_idle_worker_is_not_blocked_by_full_capacity(self):
        active,_,aw=self.active(0);paused,_,pw=self.paused(1)
        self.api.resume(paused['attempt_id']);self.emit(paused,'pause')
        stop=next(c for c in self.api.commands() if c['attempt_id']==paused['attempt_id'])
        self.assertEqual(stop['kind'],'quiesce');self.c.tick()
        self.assertEqual(pw['queue'].get_nowait()['command_id'],stop['command_id'])
        self.assertTrue(aw['apps']);self.assertEqual(pw['reserved'],0)
    def test_respond_after_limit_reduction_preserves_existing_active_attempts(self):
        self.c.max_active_tasks=2
        first,command,fw=self.active(0);second,_,sw=self.active(1)
        self.c.max_active_tasks=1
        request=dict(method='item/commandExecution/requestApproval',request_id=99,question='Explicit fixture?')
        self.emit(first,'approval',command_id=command['command_id'],decision_id='capacity-decision',request=request)
        self.cs.update(command['command_id'],phase='needs_input',decision=request)
        class App:
            def __init__(self):self.responses=[]
            def respond(self,request,answer):self.responses.append((request,answer))
        app=App();fw['apps'][command['command_id']]=app
        self.api.respond('capacity-decision','decline')
        reply=next(c for c in self.api.commands() if c['kind']=='respond')
        self.c.tick()
        self.assertEqual(self.cs.command(reply['command_id'])['phase'],'completed')
        self.assertEqual(app.responses,[(request,'decline')])
        self.assertTrue(fw['apps']);self.assertTrue(sw['apps'])
        self.assertTrue(self.c.flush());self.assertEqual(self.s.attempt(first['attempt_id'])['phase'],'executing')
