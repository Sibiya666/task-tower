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
class TransportTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:");self.addCleanup(self.db.close)
        self.store=SimpleNamespace(db=self.db,lock=threading.RLock());self.remote=Remote();self.handler=Handler()
        self.t=IssueTransport(self.store,self.remote,BINDING,self.handler)
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
    def test_transport_ack_does_not_mean_task_acceptance(self):
        self.t.tick()
        self.assertEqual(self.handler.result["state"],"published")
        self.assertNotIn("accepted",self.remote.acks[0])

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
