import http.client
import json
import socket
import tempfile
import threading
import time
from unittest.mock import patch
from task_tower.service import api
import unittest
from pathlib import Path
from tests.test_service_store import PLAN,DIGEST
from tests.test_service_beads import NativeFixture,Beads
from task_tower.service.api import make_server
from task_tower.service.store import Store


def private_token(path,text):
    """Provision only a new disposable file, with a private DACL at creation."""
    import os
    if os.name!='nt':
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
        return
    import subprocess,sys
    env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
    env.update(TOWER_TEST_TOKEN_PATH=str(path),TOWER_TEST_TOKEN_TEXT=text)
    subprocess.run([sys.executable,'-I','-S','-B',str(Path(__file__).parent/'fixtures/private_token.py')],env=env,check=True,
        capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.native=NativeFixture()
        beads=Beads(Path(self.tmp.name)/'bd',{'p':Path(self.tmp.name)},runner=self.native)
        self.store=Store(Path(self.tmp.name)/'journal',beads,approved_plans={'p':{DIGEST}})
        self.addCleanup(self.store.close)
        self.server=make_server(self.store,{'c1':{'token':'a'*40,'projects':['p']},
                                             'c2':{'token':'b'*40,'projects':['p']}},port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def stop():self.server.shutdown();self.server.server_close();self.thread.join(2)
        self.addCleanup(stop)

    def request(self,method,path,body=None,token='a'*40,connector='c1'):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        raw=None if body is None else json.dumps(body)
        try:
            c.request(method,path,raw,{'Authorization':'Bearer '+token,'X-Connector-ID':connector,
                                    'Content-Type':'application/json'})
            r=c.getresponse();data=json.loads(r.read());return r.status,data
        finally:c.close()

    def import_plan(self):
        status,data=self.request('POST','/v1/plans/import',dict(version=1,request_id='import-1',
            project_id='p',digest=DIGEST,plan=PLAN))
        self.assertEqual(status,200,data)

    def claim(self):return dict(version=1,request_id='r1',project_id='p',bead_id='pilot-a',connector_id='c1')

    def test_wrong_token_project_connector_rejected_before_effect(self):
        for body,token,connector in [(self.claim(),'wrong','c1'),
                (dict(self.claim(),project_id='other'),'a'*40,'c1'),
                (dict(self.claim(),connector_id='c2'),'a'*40,'c1'),
                (self.claim(),'a'*40,'unknown')]:
            status,data=self.request('POST','/v1/claims',body,token,connector)
            self.assertIn(status,(400,401,403));self.assertIn('code',data['error'])
        self.assertEqual(self.native.calls,[])

    def test_claim_lost_http_response_retries_same_attempt(self):
        self.import_plan()
        raw=json.dumps(self.claim()).encode()
        s=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3)
        s.sendall(b'POST /v1/claims HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+b'a'*40+
                  b'\r\nX-Connector-ID: c1\r\nContent-Type: application/json\r\nContent-Length: '+
                  str(len(raw)).encode()+b'\r\n\r\n'+raw)
        s.shutdown(socket.SHUT_WR)
        # The first response is deliberately discarded after the native claim.
        while s.recv(4096):pass
        s.close()
        status,a=self.request('POST','/v1/claims',self.claim())
        self.assertEqual(status,200,a)
        status,b=self.request('POST','/v1/claims',self.claim())
        self.assertEqual(a,b)
        self.assertEqual(a['attempt']['phase'],'claimed')
        self.assertEqual(sum('--claim' in c for c in self.native.calls),1)

    def test_assignment_and_events_are_bound_to_connector(self):
        self.import_plan();_,data=self.request('POST','/v1/claims',self.claim());a=data['attempt']
        status,_=self.request('GET','/v1/attempts/'+a['attempt_id'],token='b'*40,connector='c2')
        self.assertEqual(status,403)
        event=dict(version=1,event_id='e1',attempt_id=a['attempt_id'],connector_id='c1',
                   phase='executing',execution_state='running',connection_state='connected')
        status,one=self.request('POST','/v1/events',event);self.assertEqual(status,200)
        self.assertEqual(self.request('POST','/v1/events',event),(status,one))

    def test_poll_and_decision_roundtrip_have_version_and_identity(self):
        self.import_plan()
        status,data=self.request('GET','/v1/ready?project_id=p')
        self.assertEqual(status,200);self.assertEqual(data['version'],1)
        self.assertEqual(data['poll_seconds'],2)
        self.assertEqual([r['id'] for r in data['ready']],['pilot-a'])
        _,a=self.request('POST','/v1/claims',self.claim())
        body=dict(version=1,decision_id='d1',attempt_id=a['attempt']['attempt_id'],
                  connector_id='c1',question='Need scope decision')
        self.assertEqual(self.request('POST','/v1/decisions',body)[0],200)
        status,data=self.request('GET','/v1/decisions');self.assertEqual(status,200)
        self.assertEqual(data['decisions'][0]['decision_id'],'d1')

    def test_body_limit_unknown_fields_and_shell_paths_refused(self):
        self.import_plan()
        for body in [dict(self.claim(),shell='echo unsafe'),dict(self.claim(),path='/tmp'),
                     dict(self.claim(),version=2)]:
            self.assertEqual(self.request('POST','/v1/claims',body)[0],400)
        self.assertFalse(any('--claim' in c for c in self.native.calls))
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        c.request('POST','/v1/claims',b'x'*70000,{'Authorization':'Bearer '+'a'*40,
                  'X-Connector-ID':'c1','Content-Type':'application/json'})
        r=c.getresponse();self.assertEqual(r.status,413);r.read();c.close()

    def test_public_bind_is_refused(self):
        with self.assertRaises(ValueError):make_server(self.store,{},host='0.0.0.0',port=0)

    def test_private_token_file_and_cli_configuration(self):
        from task_tower.service.cli import load_config, read_token
        token=Path(self.tmp.name)/'token'
        private_token(token,'z'*40)
        self.assertEqual(read_token(token),'z'*40)
        config=Path(self.tmp.name)/'config.json'
        config.write_text(json.dumps(dict(version=1,executable=str(Path(self.tmp.name)/'bd'),
            projects={'p':self.tmp.name},journal=str(Path(self.tmp.name)/'cli-journal'),
            connectors={'c1':dict(token_file=str(token),projects=['p'])},
            approved_plans={'p':[DIGEST]},port=0,poll_seconds=3)),encoding='utf-8')
        settings=load_config(config)
        self.assertEqual(settings['poll_seconds'],3)
        self.assertEqual(settings['connectors']['c1']['token'],'z'*40)
        token.write_text('short',encoding='utf-8')
        with self.assertRaises(ValueError):read_token(token)

    @unittest.skipIf(__import__('os').name=='nt','POSIX permission bits')
    def test_public_token_file_is_rejected(self):
        from task_tower.service.cli import read_token
        token=Path(self.tmp.name)/'public';token.write_text('z'*40,encoding='utf-8');token.chmod(0o644)
        with self.assertRaises(ValueError):read_token(token)

    def test_duplicate_json_and_chunked_framing_cannot_claim(self):
        self.import_plan()
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        raw=b'{"version":1,"version":1}'
        c.request('POST','/v1/claims',raw,{'Authorization':'Bearer '+'a'*40,
                  'X-Connector-ID':'c1','Content-Type':'application/json'})
        r=c.getresponse();self.assertEqual(r.status,400);r.read();c.close()
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        c.request('POST','/v1/claims',b'0\r\n\r\n',{'Authorization':'Bearer '+'a'*40,
                  'X-Connector-ID':'c1','Content-Type':'application/json','Transfer-Encoding':'chunked'})
        r=c.getresponse();self.assertEqual(r.status,400);r.read();c.close()
        self.assertFalse(any('--claim' in c for c in self.native.calls))

    def test_config_cannot_alias_journal_to_token_or_accept_unknown_commands(self):
        from task_tower.service.cli import load_config
        token=Path(self.tmp.name)/'private-token';private_token(token,'z'*40)
        config=Path(self.tmp.name)/'config.json'
        value=dict(version=1,executable=str(Path(self.tmp.name)/'bd'),projects={'p':self.tmp.name},
            journal=str(token),connectors={'c1':dict(token_file=str(token),projects=['p'])},
            approved_plans={'p':[DIGEST]},port=0,poll_seconds=2)
        config.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ValueError):load_config(config)
        value['journal']=str(Path(self.tmp.name)/'safe-journal');value['shell']='echo unsafe'
        config.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ValueError):load_config(config)

    def test_rejected_body_receives_json_response_without_tcp_reset(self):
        for index in range(40):
            status,data=self.request('POST','/v1/claims',self.claim(),token='wrong')
            self.assertEqual(status,401)
            self.assertEqual(data['error']['code'],'unauthorized')
        self.assertEqual(self.native.calls,[])

    def test_trickling_headers_body_and_rejected_drain_do_not_block_connector(self):
        # Lower only the configured read budget; exercise real socket/HTTP/store code.
        with patch.object(api,'READ_TIMEOUT',.3,create=True):
            for phase in ('headers','body','rejected_drain'):
                with self.subTest(phase=phase):
                    slow=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
                    if phase=='headers':
                        prefix=b'GET /v1/ready?project_id=p HTTP/1.1\r\nX-Slow: '
                    else:
                        token=b'a'*40 if phase=='body' else b'wrong'
                        prefix=(b'POST /v1/claims HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+token+
                            b'\r\nX-Connector-ID: c1\r\nContent-Type: application/json\r\nContent-Length: 4096\r\n\r\n{')
                    slow.sendall(prefix)
                    stop=threading.Event()
                    def trickle():
                        while not stop.wait(.03):
                            try:slow.sendall(b' ')
                            except OSError:break
                    sender=threading.Thread(target=trickle,daemon=True);sender.start()
                    try:
                        try:status,data=self.request('GET','/v1/ready?project_id=p')
                        except OSError:status,data='timeout',None
                        self.assertEqual(status,200,'trickling '+phase+' blocked an authorized connector')
                        self.assertEqual(data['ready'],[])
                    finally:
                        stop.set();slow.close();sender.join(2)
            self.assertFalse(any('--claim' in c for c in self.native.calls))

    def test_read_deadline_does_not_cancel_a_valid_native_claim(self):
        self.import_plan()
        self.native.before_claim=lambda:time.sleep(.2)
        with patch.object(api,'READ_TIMEOUT',.1,create=True):
            status,data=self.request('POST','/v1/claims',self.claim())
        self.assertEqual(status,200,data)
        self.assertEqual(data['attempt']['phase'],'claimed')
        self.assertEqual(sum('--claim' in c for c in self.native.calls),1)
