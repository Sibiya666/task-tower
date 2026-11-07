import tempfile
import unittest
from pathlib import Path
from task_tower.connector.store import ConnectorStore
from task_tower.connector.app_server import AppServer

class Wire:
    def __init__(self): self.calls=[];self.fail=False;self.store=None
    def request(self,method,params):
        self.calls.append((method,params))
        if method=='thread/start': return {'thread':{'id':'thread1'}}
        if method=='turn/start':
            assert self.store.command('cmd1')['thread_id']=='thread1'
            if self.fail: raise TimeoutError()
            return {'turn':{'id':'turn1','status':'inProgress'}}
        return {'thread':{'id':'thread1','turns':[]}}

class RpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ConnectorStore(Path(self.tmp.name)/'journal','host1');self.addCleanup(self.store.close)
        self.wire=Wire();self.wire.store=self.store
        self.app=AppServer(self.store,transport=self.wire)
        self.store.receive(dict(version=1,command_id='cmd1',attempt_id='attempt1',project_id='p',base_sha='a'*40,input={'text':'hello'}))
    def start(self):
        t=self.app.create_thread(Path(self.tmp.name),command_id='cmd1')
        return self.app.start_turn(t,'cmd1',{'text':'hello'})
    def test_duplicate_command_one_turn_and_thread_saved_first(self):
        self.assertEqual(self.start()['turn_id'],'turn1')
        self.assertEqual(self.start()['turn_id'],'turn1')
        self.assertEqual([m for m,p in self.wire.calls].count('turn/start'),1)
        self.assertEqual([m for m,p in self.wire.calls].count('thread/start'),1)
    def test_lost_response_never_replays(self):
        self.wire.fail=True
        self.assertEqual(self.start()['phase'],'needs_reconciliation')
        self.wire.fail=False
        self.assertEqual(self.start()['phase'],'needs_reconciliation')
        self.assertEqual([m for m,p in self.wire.calls].count('turn/start'),1)
    def test_changed_command_rejected(self):
        c=self.store.command('cmd1')['command'];c['input']={'text':'different'}
        with self.assertRaises(ValueError):self.store.receive(c)
    def test_request_id_is_not_idempotence(self):
        self.start();self.assertEqual(self.store.command('cmd1')['phase'],'executing')
    def test_history_error_remains_partial(self):
        class Empty(Wire):
            def request(self,m,p):
                if p.get('includeTurns'):raise RuntimeError('unsupported')
                return {'thread':{'id':'thread1'}}
        app=AppServer(self.store,transport=Empty())
        self.assertEqual(app.inspect('thread1')['history_state'],'partial')

class TransportTests(unittest.TestCase):
    def test_actual_stdio_correlation_notifications_and_environment(self):
        import os,sys,subprocess
        from unittest.mock import patch
        from task_tower.connector.app_server import StdioTransport,DecisionRequired
        script="""import sys,json
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m:continue
 if m['method']=='decision':
  print(json.dumps({'id':99,'method':'item/commandExecution/requestApproval','params':{'threadId':'t1'}}),flush=True)
 else:
  print(json.dumps({'method':'test/notice','params':{}}),flush=True)
  print(json.dumps({'id':m['id'],'result':{'ok':True}}),flush=True)
"""
        original=subprocess.Popen
        def launch(argv,**kw):
            self.assertFalse(any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in kw['env']))
            self.assertFalse(any(k.upper().startswith(('BD_','BEADS_','DOLT_','TOWER_','TASK_TOWER_')) for k in kw['env']))
            self.assertEqual(argv[1:],['app-server','--listen','stdio://'])
            return original([sys.executable,'-u','-c',script],**kw)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'gH_tOkEn':'fixture','BEADS_DIR':'private-fixture','TOWER_API_TOKEN':'private-fixture'}),patch('task_tower.connector.app_server.subprocess.Popen',side_effect=launch):
            wire=StdioTransport(Path(sys.executable),Path(tmp),timeout=2)
            try:
                self.assertTrue(wire.request('test',{})['ok'])
                self.assertTrue(wire.notifications())
                with self.assertRaises(DecisionRequired):wire.request('decision',{})
                self.assertEqual(wire.notifications()[0]['id'],99)
            finally:wire.close()

    def test_stalled_stdin_does_not_hold_request_forever(self):
        import threading,time,types
        from task_tower.connector.app_server import StdioTransport
        wire=StdioTransport.__new__(StdioTransport)
        wire.timeout=.1;wire.serial=threading.RLock();wire.counter=0;wire.failed=threading.Event();wire.q=__import__('queue').Queue();wire.events=__import__('queue').Queue()
        release=threading.Event();errors=[]
        class Input:
            def write(self,raw):release.wait(2)
            def flush(self):pass
        wire.process=types.SimpleNamespace(stdin=Input())
        if hasattr(wire,'_start_writer'):wire._start_writer()
        def request():
            try:wire.request('test',{})
            except Exception as e:errors.append(type(e).__name__)
        t=threading.Thread(target=request);t.start()
        try:
            t.join(.5);self.assertFalse(t.is_alive());self.assertTrue(errors)
        finally:
            release.set();t.join(3)
            if hasattr(wire,'writer'):wire.writer.join(2)
