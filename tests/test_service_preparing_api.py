"""Real disposable HTTP/config contracts; no live connector or recovery."""
import copy
import http.client
import json
from pathlib import Path
import socket
import threading
import unittest
import uuid
from unittest.mock import Mock,patch

from task_tower.service.api import make_server
from task_tower.service.beads import Beads
from task_tower.service.preparing_recovery import command_ids
from tests.fixtures.service_preparing_recovery import PreparingServiceFixture
from tests.test_service_api import private_token


class PreparingAPITests(PreparingServiceFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        other=self.root/'other';other.mkdir()
        self.s.close()
        self.beads=Beads(self.root/'bd',{'p':self.root,'q':other},runner=self.native)
        self.reopen()
        self.server=self.server_for(['p'])

    def server_for(self,projects):
        server=make_server(self.s,{'host1':dict(token='a'*40,projects=projects),
                                  'host2':dict(token='b'*40,projects=['p'])},port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def stop():
            server.shutdown();server.server_close();thread.join(2)
            self.assertFalse(thread.is_alive())
        self.addCleanup(stop)
        return server

    def request(self,method,path,body=None,*,connector='host1',token='a'*40,server=None):
        connection=http.client.HTTPConnection('127.0.0.1',(server or self.server).server_port,timeout=3)
        try:
            connection.request(method,path,None if body is None else json.dumps(body),
                {'Authorization':'Bearer '+token,'X-Connector-ID':connector,'Content-Type':'application/json'})
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()

    def admit_http(self):
        status,data=self.request('POST','/v1/preparing',dict(version=1,receipt=self.r))
        self.assertEqual(status,200,data)
        return data['preparing']

    def test_admission_status_and_repeat_have_one_control_no_execution(self):
        first=self.admit_http();self.assertEqual(first['state'],'pending')
        self.assertEqual(self.admit_http(),first)
        status,data=self.request('GET','/v1/preparing/'+self.r['operation_id'])
        self.assertEqual(status,200,data);self.assertEqual(data['preparing'],first)
        self.assertEqual(set(first),{'operation_id','project_id','attempt_id','receipt_sha256',
            'state','control_command_id','execute_command_id'})
        status,data=self.request('GET','/v1/commands');self.assertEqual(status,200,data)
        self.assertEqual(len(data['commands']),1);self.assertEqual(data['commands'][0]['kind'],'prepare_existing')
        self.original()

    def test_authentication_and_foreign_connector_cannot_admit_or_observe(self):
        for connector,token,expected in [('host1','wrong',401),('host2','b'*40,403)]:
            with self.subTest(connector=connector):
                status,_=self.request('POST','/v1/preparing',dict(version=1,receipt=self.r),connector=connector,token=token)
                self.assertEqual(status,expected)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.admit_http()
        status,_=self.request('GET','/v1/preparing/'+self.r['operation_id'],connector='host2',token='b'*40)
        self.assertEqual(status,404);self.original()

    def test_project_scope_applies_before_admission_and_to_existing_status(self):
        scoped=self.server_for(['q'])
        status,_=self.request('POST','/v1/preparing',dict(version=1,receipt=self.r),server=scoped)
        self.assertEqual(status,403)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.admit_http()
        status,_=self.request('GET','/v1/preparing/'+self.r['operation_id'],server=scoped)
        self.assertEqual(status,403);self.original()

    def test_default_registry_refuses_real_http_admission(self):
        self.s.approved_preparing={}
        status,_=self.request('POST','/v1/preparing',dict(version=1,receipt=self.r))
        self.assertEqual(status,403)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.original()

    def test_receipt_identity_and_approval_cannot_be_changed_over_http(self):
        foreign=str(uuid.uuid4())
        for changes,expected in [(dict(attempt_id=foreign,branch='codex/headless-'+foreign),404),
                (dict(project_id='q'),403),(dict(connector_id='host2'),403),
                (dict(operation_id=str(uuid.uuid4())),403)]:
            status,data=self.request('POST','/v1/preparing',dict(version=1,receipt=dict(self.r,**changes)))
            self.assertEqual(status,expected,data)
        self.s.approved_preparing={}
        status,data=self.request('POST','/v1/preparing',dict(version=1,receipt=self.r,approved_preparing={'p':list(self.approved['p'])}))
        self.assertEqual(status,400,data)
        self.assertEqual(self.s.approved_preparing,{})
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.original()

    def test_overflow_rejection_never_drains_an_unbounded_declared_body(self):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            connection.request('POST','/v1/preparing',b'',{'Authorization':'Bearer '+'a'*40,
                'X-Connector-ID':'host1','Content-Type':'application/json','Content-Length':'999999'})
            response=connection.getresponse();self.assertEqual(response.status,413);response.read()
        finally:connection.close()
        self.original()

    def test_authenticated_overflow_drain_keeps_original_total_read_deadline(self):
        from task_tower.service import api
        with patch.object(api,'READ_TIMEOUT',.3):
            slow=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
            try:
                slow.sendall(b'POST /v1/preparing HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+
                    b'a'*40+b'\r\nX-Connector-ID: host1\r\nContent-Type: application/json\r\nContent-Length: 66000\r\n\r\n{')
                status,data=self.request('GET','/v1/ready?project_id=p')
                self.assertEqual(status,200,data)
            finally:slow.close()
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.original()

    def test_strict_bounded_body_and_route_cannot_create_control(self):
        cases=[('/v1/preparing',dict(version=True,receipt=self.r),400),
            ('/v1/preparing',dict(version=1,receipt=self.r,extra=True),400),
            ('/v1/preparing',dict(version=1,receipt=None),400),
            ('/v1/preparing',dict(version=1,receipt={}),400),
            ('/v1/preparing',dict(version=1,receipt={'private_path':str(self.root/'synthetic-private')}),400),
            ('/v1/preparing?project_id=p',dict(version=1,receipt=self.r),400),
            ('/v1/preparing',dict(version=1,receipt={'padding':'x'*66000}),413)]
        for path,body,expected in cases:
            with self.subTest(path=path,expected=expected):
                status,data=self.request('POST',path,body);self.assertEqual(status,expected,data)
                self.assertNotIn(str(self.root),json.dumps(data))
        status,_=self.request('GET','/v1/preparing/'+self.r['operation_id']+'?extra=1')
        self.assertEqual(status,404)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM preparing_recoveries').fetchone()[0],0)
        self.original()

    def test_existing_validate_and_ack_routes_commit_one_original_execute(self):
        operation=self.admit_http();control=operation['control_command_id']
        status,data=self.request('POST','/v1/commands/'+control+'/validate',dict(version=1))
        self.assertEqual(status,200,data);self.assertEqual(data['attempt']['attempt_id'],self.a['attempt_id'])
        event=self.ack()
        status,data=self.request('POST','/v1/events',event);self.assertEqual(status,200,data)
        self.assertEqual(data['attempt']['phase'],'executing')
        status,again=self.request('POST','/v1/events',event);self.assertEqual(status,200,again)
        self.assertEqual(again,data)
        status,state=self.request('GET','/v1/preparing/'+self.r['operation_id'])
        self.assertEqual(status,200,state);self.assertEqual(state['preparing']['state'],'prepared')
        status,commands=self.request('GET','/v1/commands');self.assertEqual(status,200,commands)
        self.assertEqual(len(commands['commands']),1)
        execute=commands['commands'][0]
        self.assertEqual(execute['command_id'],command_ids(self.r)[1])
        self.assertEqual(execute['input'],self.command['input']);self.assertEqual(execute['source'],self.command['source'])
        self.assertEqual(self.s.active_count('host1'),1)
        self.assertEqual(self.native.rows['pilot-task']['assignee'],self.a['actor'])

    def test_ack_auth_project_forgery_and_size_rejections_preserve_pending(self):
        self.admit_http();event=self.ack();scoped=self.server_for(['q'])
        for options,expected in [(dict(token='wrong'),401),(dict(connector='host2',token='b'*40),403),
                                  (dict(server=scoped),403)]:
            status,_=self.request('POST','/v1/events',event,**options);self.assertEqual(status,expected)
        forged=copy.deepcopy(event);forged['preparing']['engine_sha']='f'*40
        status,data=self.request('POST','/v1/events',forged);self.assertNotEqual(status,200,data)
        oversized=copy.deepcopy(event);oversized['preparing']['padding']='x'*66000
        status,data=self.request('POST','/v1/events',oversized);self.assertEqual(status,413,data)
        self.assertEqual(self.status()['state'],'pending');self.original()

    def test_failed_control_http_event_retains_unknown_and_refuses_late_ack(self):
        operation=self.admit_http()
        failed=dict(version=1,event_id='http-failure',attempt_id=self.a['attempt_id'],connector_id='host1',
            lifecycle=dict(kind='failed',command_id=operation['control_command_id']))
        status,data=self.request('POST','/v1/events',failed);self.assertEqual(status,200,data)
        status,data=self.request('GET','/v1/preparing/'+self.r['operation_id'])
        self.assertEqual(status,200,data);self.assertEqual(data['preparing']['state'],'unknown')
        status,data=self.request('POST','/v1/events',self.ack());self.assertNotEqual(status,200,data)
        self.assertEqual(self.s.lifecycle_commands('host1'),[]);self.original()

    def config(self):
        token=self.root/'http-config-token';private_token(token,'z'*40)
        path=self.root/'service-config.json'
        value=dict(version=1,executable=str(self.root/'bd'),projects={'p':str(self.root)},
            journal=str(self.root/'config-journal'),connectors={'host1':dict(token_file=str(token),projects=['p'])},
            approved_plans={'p':[]},port=0,poll_seconds=2)
        path.write_text(json.dumps(value),encoding='utf-8')
        return path,value

    def test_config_default_empty_and_explicit_bounded_registry(self):
        from task_tower.service.cli import load_config
        path,value=self.config();self.assertEqual(load_config(path)['approved_preparing'],{})
        value['approved_preparing']={'p':list(self.approved['p'])}
        path.write_text(json.dumps(value),encoding='utf-8')
        self.assertEqual(load_config(path)['approved_preparing'],self.approved)
        invalid=[None,[],{'q':['a'*64]},{'*':['a'*64]},{'p':'a'*64},{'p':['A'*64]},{'p':['a'*64]*33}]
        for registry in invalid:
            with self.subTest(registry_type=type(registry).__name__):
                value['approved_preparing']=registry;path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(ValueError):load_config(path)

    def test_main_wires_registry_into_real_disposable_store(self):
        from task_tower.service import cli
        path,value=self.config();value['approved_preparing']={'p':list(self.approved['p'])}
        path.write_text(json.dumps(value),encoding='utf-8');observed={}
        server=Mock();server.handle_request.side_effect=KeyboardInterrupt
        def make(store,*args,**kwargs):
            observed.update(store.approved_preparing);return server
        with patch.object(cli,'Beads',return_value=self.beads),patch.object(cli,'make_server',side_effect=make):
            self.assertEqual(cli.main(['--config',str(path)]),0)
        self.assertEqual(observed,self.approved);server.server_close.assert_called_once()

    def test_preparing_registry_is_not_hot_reloaded_with_plan_approvals(self):
        from task_tower.service.cli import load_config
        from task_tower.intake_reload import ConfigReloader
        path,value=self.config();current=load_config(path)
        reload=ConfigReloader(path,current,'approved_plans',load_config);self.assertEqual(reload(),current)
        value['approved_preparing']={'p':list(self.approved['p'])}
        path.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ValueError):reload()
        self.assertEqual(reload.current,current)
        value['approved_preparing']={};value['approved_plans']['p']=['b'*64]
        path.write_text(json.dumps(value),encoding='utf-8')
        self.assertEqual(reload()['approved_plans'],{'p':['b'*64]})


if __name__=='__main__':unittest.main()
