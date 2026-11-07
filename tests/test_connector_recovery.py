import tempfile
import unittest
from pathlib import Path
from task_tower.connector.store import ConnectorStore
from task_tower.connector.client import Connector

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'journal'
        self.s=ConnectorStore(self.path,'host1');self.addCleanup(lambda:self.s.close())
    def command(self):return dict(version=1,command_id='c1',attempt_id='a1',project_id='p',base_sha='a'*40,input={'text':'hi'})
    def test_restart_fences_pending_start(self):
        self.s.receive(self.command());self.s.update('c1',phase='starting',thread_id='t1');self.s.close()
        self.s=ConnectorStore(self.path,'host1');self.assertEqual(self.s.command('c1')['phase'],'needs_reconciliation')
    def test_outbox_same_identity_until_ack(self):
        event=self.s.event('a1','executing','running');self.s.close();self.s=ConnectorStore(self.path,'host1')
        self.assertEqual(self.s.pending_events(),[event]);self.s.ack(event['event_id']);self.assertEqual(self.s.pending_events(),[])
    def test_single_owner(self):
        with self.assertRaises((OSError,ValueError)):ConnectorStore(self.path,'host1')
    def test_identity_cannot_change_on_restart(self):
        self.s.close()
        with self.assertRaises(ValueError):ConnectorStore(self.path,'host2')
    def test_http_outage_keeps_current_process_and_events_no_claim(self):
        class API:
            claims=0
            def send_event(self,e):raise ConnectionError()
            def ready(self,p):raise ConnectionError()
            def claim(self,*a):self.claims+=1
        class App:
            alive=True
            def notifications(self):return []
        self.s.event('a1','executing','running');api=API();app=App()
        c=Connector(self.s,api,app,None)
        self.assertFalse(c.flush());self.assertIsNone(c.claim('p','b1'))
        self.assertEqual(api.claims,0);self.assertTrue(app.alive);self.assertEqual(len(self.s.pending_events()),1)

class NativeRevalidationTests(unittest.TestCase):
    def test_native_drift_and_cached_attempt_cannot_authorize(self):
        from tests.test_service_beads import NativeFixture,Beads
        from tests.test_service_store import PLAN,DIGEST
        from task_tower.service.store import Store
        from task_tower.service.beads import ServiceError
        for drift in ('owner','scope','dependency','fence','phase','approval'):
            with self.subTest(drift=drift),tempfile.TemporaryDirectory() as tmp:
                native=NativeFixture();beads=Beads(Path(tmp)/'bd',{'p':Path(tmp)},runner=native)
                s=Store(Path(tmp)/'server',beads,approved_plans={'p':{DIGEST}})
                try:
                    s.import_plan('i','p',DIGEST,PLAN);a=s.claim_request('r','p','pilot-a','host1')
                    self.assertEqual(s.validate_execution(a['attempt_id'],'host1')['phase'],'claimed')
                    if drift=='owner':native.rows['pilot-a']['assignee']='foreign'
                    elif drift=='scope':native.rows['pilot-a']['description']='changed'
                    elif drift=='dependency':native.rows['pilot-a']['requires']=['pilot-b']
                    elif drift=='fence':native.rows['pilot-a']['metadata']={'unknown_outcome':True}
                    elif drift=='approval':s.approved_plans={}
                    else:
                        with s.db:
                            data=s.attempt(a['attempt_id']);data['phase']='needs_reconciliation';s._save_attempt(data)
                    with self.assertRaises(ServiceError):s.validate_execution(a['attempt_id'],'host1')
                finally:s.close()

class BoundaryTests(unittest.TestCase):
    def test_owner_drift_before_turn_no_effect(self):
        from task_tower.connector.app_server import AppServer
        from tests.test_connector_rpc import Wire
        for fail_at in (1,2,3):
            with self.subTest(fail_at=fail_at),tempfile.TemporaryDirectory() as tmp:
                s=ConnectorStore(Path(tmp)/'j','host1')
                try:
                    wire=Wire();wire.store=s;app=AppServer(s,transport=wire)
                    class API:
                        calls=0
                        def validate(self,a):
                            self.calls+=1
                            if self.calls==fail_at:raise ValueError('native_owner_changed')
                            return dict(connector_id='host1',project_id='p',phase='claimed')
                    class Trees:
                        def prepare(self,*args):return {'path':tmp}
                    c=Connector(s,API(),app,Trees())
                    command=dict(version=1,command_id='cmd1',attempt_id='a1',project_id='p',base_sha='a'*40,input={'text':'hello'})
                    self.assertEqual(c.execute(command)['phase'],'needs_reconciliation')
                    self.assertFalse(any(m=='turn/start' for m,p in wire.calls))
                    self.assertEqual(c.execute(command)['phase'],'needs_reconciliation')
                finally:s.close()
    def test_cli_contract(self):
        from task_tower.connector.cli import main
        self.assertEqual(main(['run','--config','/missing/config']),2)

class RestartPendingTests(unittest.TestCase):
    def test_every_pending_command_fenced_after_restart(self):
        for phase in ('queued','preparing','creating_thread','prepared','starting','executing'):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'j';s=ConnectorStore(path,'host1')
                s.receive(dict(version=1,command_id='c',attempt_id='a',project_id='p',base_sha='a'*40,input={'text':'hi'}))
                s.update('c',phase=phase);s.close();s=ConnectorStore(path,'host1')
                try:self.assertEqual(s.command('c')['phase'],'needs_reconciliation')
                finally:s.close()

class HTTPClientTests(unittest.TestCase):
    def test_real_http_native_validation_is_connector_scoped(self):
        import threading
        from tests.test_service_beads import NativeFixture,Beads
        from tests.test_service_store import PLAN,DIGEST
        from task_tower.service.api import make_server
        from task_tower.service.store import Store
        from task_tower.connector.client import APIClient
        with tempfile.TemporaryDirectory() as tmp:
            native=NativeFixture();s=Store(Path(tmp)/'s',Beads(Path(tmp)/'bd',{'p':Path(tmp)},runner=native),approved_plans={'p':{DIGEST}})
            server=make_server(s,{'host1':{'token':'a'*40,'projects':['p']},'host2':{'token':'b'*40,'projects':['p']}},port=0)
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                s.import_plan('i','p',DIGEST,PLAN)
                client=APIClient('http://127.0.0.1:'+str(server.server_port),'host1','a'*40)
                a=client.claim(dict(version=1,request_id='r',project_id='p',bead_id='pilot-a',connector_id='host1'))
                self.assertEqual(client.validate(a['attempt_id'])['actor'],a['actor'])
                other=APIClient('http://127.0.0.1:'+str(server.server_port),'host2','b'*40)
                with self.assertRaises(ConnectionError):other.validate(a['attempt_id'])
                native.rows['pilot-a']['assignee']='foreign'
                with self.assertRaises(ConnectionError):client.validate(a['attempt_id'])
            finally:server.shutdown();server.server_close();t.join(2);s.close()
    def test_trickle_response_headers_total_deadline(self):
        import socket,threading,time
        from task_tower.connector.client import APIClient
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
        stop=threading.Event()
        def serve():
            c,_=listener.accept()
            try:
                c.recv(8192)
                for b in b'HTTP/1.0 200 OK\r\nContent-Length: 13\r\n\r\n{"version":1}':
                    if stop.wait(.03):break
                    c.sendall(bytes([b]))
            except OSError:pass
            finally:c.close()
        t=threading.Thread(target=serve,daemon=True);t.start();start=time.monotonic()
        try:
            with self.assertRaises((TimeoutError,OSError,ValueError)):APIClient('http://127.0.0.1:'+str(port),'host1','a'*40,timeout=.15).ready('p')
            self.assertLess(time.monotonic()-start,.6)
        finally:stop.set();listener.close();t.join(2)

class ResultDeliveryTests(unittest.TestCase):
    def test_result_identity_and_text_reach_actual_api_journal(self):
        from tests.test_service_beads import NativeFixture,Beads
        from tests.test_service_store import PLAN,DIGEST
        from task_tower.service.store import Store
        from task_tower.service.beads import ServiceError
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/'s',Beads(Path(tmp)/'bd',{'p':Path(tmp)},runner=NativeFixture()),approved_plans={'p':{DIGEST}})
            try:
                s.import_plan('i','p',DIGEST,PLAN);a=s.claim_request('r','p','pilot-a','host1')
                event=dict(version=1,event_id='e1',attempt_id=a['attempt_id'],connector_id='host1',phase='executing',execution_state='completed',connection_state='connected',execution=dict(command_id='c1',thread_id='t1',turn_id='u1',result='FIXTURE_OK'))
                value=s.record_event(event)
                self.assertEqual(value['thread_id'],'t1');self.assertEqual(value['execution_result'],'FIXTURE_OK')
                self.assertEqual(s.record_event(event),value)
                with self.assertRaises(ServiceError):s.record_event(dict(event,event_id='e2',execution=dict(event['execution'],thread_id='foreign')))
            finally:s.close()
