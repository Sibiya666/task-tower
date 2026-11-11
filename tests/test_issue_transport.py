import hashlib
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from task_tower.connector.issue_transport import IssueTransport

BINDING=dict(app_id=7,installation_id=8,repository_id=9)
def event():return dict(version=1,**BINDING,delivery_id="d1",payload_sha256="a"*64,event="issues",action="opened",body=dict(issue=dict(number=12),sender=dict(type="User",id=21)))
class Remote:
    def __init__(self): self.rows=[event()];self.acks=[];self.fail_ack=False
    def take(self,limit):return self.rows
    def ack(self,key,digest):
        self.acks.append((key,digest))
        if self.fail_ack:raise TimeoutError()
        return dict(receipt_hash=digest,state="acked")
class Handler:
    def __init__(self):self.calls=0;self.result=None;self.lost=False
    def __call__(self,e,request_id):
        self.calls+=1;self.result=dict(state="published",bead_id="native-private")
        if self.lost:raise TimeoutError()
        return self.result
    def readback(self,e,request_id):return self.result
class NativeAPI:
    def __init__(self):
        self.admissions=0;self.dispatches=0;self.fail_read=False;self.lose_dispatch=False
        self.receipt=dict(state='published',bead_id='native-private',base_sha='b'*40)
        self.attempt=dict(attempt_id='attempt',phase='claimed',managed=False)
    def request(self,method,path,payload=None):
        if method=='POST' and path=='/v1/issues/admit':self.admissions+=1;return dict(issue=self.receipt)
        if method=='GET' and path.startswith('/v1/issues?'):return dict(issue=self.receipt)
        if method=='GET' and path=='/v1/attempts/attempt':
            if self.fail_read:raise TimeoutError()
            return dict(attempt=dict(self.attempt))
        raise AssertionError((method,path))
    def dispatch(self,key,base):
        self.dispatches+=1;self.attempt.update(phase='executing',managed=True)
        if self.lose_dispatch:raise TimeoutError()
class NativeConnector:
    def __init__(self,api):self.api=api;self.available=False
    def claim(self,project,bead):return dict(self.api.attempt) if self.available else None
class TransportTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:");self.addCleanup(self.db.close)
        self.store=SimpleNamespace(db=self.db,lock=threading.RLock());self.remote=Remote();self.handler=Handler()
        self.t=IssueTransport(self.store,self.remote,BINDING,self.handler)
    def native_handler(self):
        from task_tower.connector.issue_transport import IssueEventHandler
        snapshot=dict(repository='Sibiya666/task-tower',repository_id=9,issue_number=12,reporter_id=21,source_revision='a'*64)
        api=NativeAPI();connector=NativeConnector(api)
        handler=IssueEventHandler('p',SimpleNamespace(snapshot=lambda number,**kwargs:snapshot),api,connector,lambda s:self.fail('unexpected public effect'))
        self.t=IssueTransport(self.store,self.remote,BINDING,handler)
        return api,connector
    def test_duplicate_cloud_delivery_has_one_handler_effect_and_stable_ack(self):
        self.t.tick();self.t.tick()
        self.assertEqual(self.handler.calls,1);self.assertEqual(self.remote.acks[0],self.remote.acks[1])
    def test_ack_retry_uses_persisted_receipt_without_reexecution(self):
        self.remote.fail_ack=True
        with self.assertRaises(TimeoutError):self.t.tick()
        self.remote.fail_ack=False
        IssueTransport(self.store,self.remote,BINDING,self.handler).tick()
        self.assertEqual(self.handler.calls,1);self.assertEqual(len(self.remote.acks),2)
    def test_unknown_native_response_uses_readback_not_another_call(self):
        self.handler.lost=True
        with self.assertRaises(ValueError):self.t.tick()
        self.handler.lost=False;self.t.tick()
        self.assertEqual(self.handler.calls,1);self.assertEqual(len(self.remote.acks),1)
    def test_hash_conflict_and_foreign_binding_never_execute(self):
        self.t.tick();self.remote.rows[0]["payload_sha256"]="b"*64
        with self.assertRaises(ValueError):self.t.tick()
        self.remote.rows=[dict(event(),repository_id=99)]
        with self.assertRaises(ValueError):self.t.tick()
        self.assertEqual(self.handler.calls,1)
    def test_bot_and_unsupported_events_are_acknowledged_without_execution(self):
        self.remote.rows[0]["body"]["sender"]["type"]="Bot"
        self.t.tick();self.assertEqual(self.handler.calls,0);self.assertEqual(len(self.remote.acks),1)
    def test_pull_request_comments_are_acknowledged_as_ignored_without_admission(self):
        e=self.remote.rows[0];e.update(event='issue_comment',action='created')
        e['body']['issue']['pull_request']={'url':'https://api.github.com/repos/owner/repo/pulls/12'}
        self.t.tick();self.t.tick()
        self.assertEqual(self.handler.calls,0)
        self.assertEqual(len(self.remote.acks),2)
    def test_transport_ack_does_not_mean_task_acceptance(self):
        self.t.tick()
        self.assertEqual(self.handler.result["state"],"published")
        self.assertNotIn("accepted",self.remote.acks[0])
    def test_capacity_release_retries_native_claim_by_readback_before_ack(self):
        api,connector=self.native_handler()
        with self.assertRaises(ValueError):self.t.tick()
        self.assertEqual(self.remote.acks,[])
        connector.available=True;self.t.tick();self.t.tick()
        self.assertEqual((api.admissions,api.dispatches),(1,1))
        self.assertEqual(len(self.remote.acks),2)
    def test_temporary_attempt_api_failure_retries_readback_without_another_admission(self):
        api,connector=self.native_handler();connector.available=True;api.fail_read=True
        with self.assertRaises(ValueError):self.t.tick()
        self.assertEqual(self.remote.acks,[])
        api.fail_read=False;self.t.tick()
        self.assertEqual((api.admissions,api.dispatches),(1,1))
    def test_lost_dispatch_response_does_not_dispatch_managed_attempt_again(self):
        api,connector=self.native_handler();connector.available=True;api.lose_dispatch=True
        with self.assertRaises(ValueError):self.t.tick()
        self.assertEqual(self.remote.acks,[])
        self.t.tick()
        self.assertEqual((api.admissions,api.dispatches),(1,1))
        self.assertEqual(len(self.remote.acks),1)

    def test_ineligible_reporter_gets_owner_wait_message_without_native_execution(self):
        from task_tower.connector.issue_transport import IssueEventHandler
        snapshot=dict(repository="Sibiya666/task-tower",repository_id=9,issue_number=12,reporter_id=21,source_revision="a"*64)
        source=SimpleNamespace(snapshot=lambda number,**kwargs:snapshot)
        class API:
            def request(_,method,path,payload):
                self.assertEqual((method,path),("POST","/v1/issues/admit"))
                return dict(issue=dict(state="needs_input",reason="owner_admission_required"))
        messages=[]
        messenger=SimpleNamespace(ensure_comment=lambda key,number,body:messages.append(body))
        connector=SimpleNamespace(claim=lambda *a:self.fail("ineligible reporter must not start native execution"))
        handler=IssueEventHandler("p",source,API(),connector,lambda s:messenger)
        self.assertEqual(handler(event(),"request")["state"],"needs_input")
        self.assertEqual(len(messages),1)
        self.assertIn("owner",messages[0])
