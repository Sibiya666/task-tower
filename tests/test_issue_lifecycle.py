import copy
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_service_beads import NativeFixture,Beads
from tests.test_issue_admission import Source
from task_tower.issue_intake import INITIAL_POLICY
from task_tower.service.issue_admission import IssueBinding
from task_tower.service.store import Store
from task_tower.service.beads import ServiceError
from task_tower.reporter_verification import candidate_receipt

H="b"*40;B="a"*40;REPO="Sibiya666/task-tower"
DIFF="diff --git a/docs/example.md b/docs/example.md\nindex 1234567..7654321 100644\n--- a/docs/example.md\n+++ b/docs/example.md\n@@ -1 +1 @@\n-old\n+new\n"
class CandidateHost:
    def __init__(self):self.comments=[]
    def read_pr(self,r,p):return dict(repository=REPO,head_repository=REPO,number=7,head_sha=H,base_sha=B,state="open",merged=False)
    def _pages(self,r,p):return self.comments
    def _request(self,r,m,p):return next(v for v in self.comments if v["id"]==int(p.rsplit("/",1)[1]))
class IssueLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);native=NativeFixture();beads=Beads(root/"bd",{"p":root},runner=native)
        self.source=Source();self.source.host=CandidateHost();policy=copy.deepcopy(INITIAL_POLICY);policy["initially_enabled"]=True
        self.s=Store(root/"journal",beads,delivery_projects={"p":REPO},issue_bindings={"p":IssueBinding(policy,self.source,"c1",9)})
        self.addCleanup(self.s.close);self.seq=0
        r=self.s.admit_issue("admit","p",12,self.source.snapshot(12)["source_revision"],"c1")
        self.a=self.s.claim_request("claim","p",r["bead_id"],"c1")
        self.s.start_lifecycle(self.a["attempt_id"],"c1",B)
        self.complete("author",source=dict(head_sha=H,base_sha=B,diff=DIFF))
        review=dict(verdict="approve",findings=[],head_sha=H,base_sha=B,reviewer_thread_id="review")
        self.complete("review",result=json.dumps(review))
        self.a=self.s.attempt(self.a["attempt_id"])
        self.c=candidate_receipt(self.a["source_issue"],self.source.host.read_pr(REPO,7),21,"Check commit "+H,"2030-01-01T00:00:00Z")
    def command(self):return self.s.lifecycle_commands("c1")[-1]
    def emit(self,kind,**p):
        self.seq+=1
        return self.s.record_event(dict(version=1,event_id="e"+str(self.seq),attempt_id=self.a["attempt_id"],connector_id="c1",lifecycle=dict(kind=kind,command_id=self.command()["command_id"],**p)))
    def complete(self,thread,result="done",source=None):
        self.emit("started",thread_id=thread,turn_id="t"+thread)
        p=dict(thread_id=thread,turn_id="t"+thread,result=result)
        if source:p["source"]=source
        self.emit("completed",**p)
    def test_candidate_is_persisted_without_reserving_merge_lease(self):
        a=self.emit("candidate",candidate=self.c)
        self.assertEqual(a["candidate"],self.c)
        self.s.validate_lifecycle_command(self.command()["command_id"],"c1")
        self.assertEqual(self.s.db.execute("SELECT count(*) FROM acceptance_repository").fetchone()[0],0)
    def test_forged_reporter_receipt_cannot_reserve_or_merge(self):
        self.emit("candidate",candidate=self.c)
        with self.assertRaises(ServiceError):self.emit("reporter_verified",verification=dict(comment_id=44,head_sha=H,base_sha=B,candidate_sha256=self.c["candidate_sha256"],reporter_id=21,created_at="2030-01-01T00:01:00Z"))
    def test_fresh_reporter_receipt_survives_native_history_and_reserves_only_when_ready(self):
        self.emit("candidate",candidate=self.c)
        comment=dict(id=44,body="/task-tower verified "+H,user=dict(id=21,type="User"),created_at="2030-01-01T00:01:00Z",updated_at="2030-01-01T00:01:00Z",issue_url="https://api.github.com/repos/"+REPO+"/issues/12")
        self.source.host.comments=[comment]
        from task_tower.reporter_verification import validate_verification
        receipt=validate_verification(comment,self.c,self.source.host.read_pr(REPO,7))
        a=self.emit("reporter_verified",verification=receipt)
        self.assertEqual(a["reporter_verification"],receipt)
        self.s.validate_lifecycle_command(self.command()["command_id"],"c1")
        self.assertEqual(self.s.db.execute("SELECT count(*) FROM acceptance_repository").fetchone()[0],1)
        original=self.source.host.read_pr
        self.source.host.read_pr=lambda r,p:dict(original(r,p),merged=True,state='closed')
        # Lost merge notification: existing repository ownership must permit
        # factual readback instead of demanding an already closed PR be open.
        self.s.validate_lifecycle_command(self.command()['command_id'],'c1')
    def test_base_change_invalidates_candidate_and_requires_a_new_reporter_confirmation(self):
        self.emit('candidate',candidate=self.c)
        comment=dict(id=44,body='/task-tower verified '+H,user=dict(id=21,type='User'),created_at='2030-01-01T00:01:00Z',updated_at='2030-01-01T00:01:00Z',issue_url='https://api.github.com/repos/'+REPO+'/issues/12')
        self.source.host.comments=[comment]
        from task_tower.reporter_verification import validate_verification
        self.emit('reporter_verified',verification=validate_verification(comment,self.c,self.source.host.read_pr(REPO,7)))
        a=self.emit('delivery_changed',base_sha='c'*40)
        self.assertNotIn('candidate',a)
        self.assertNotIn('reporter_verification',a)
        self.assertEqual(a['phase'],'revising')
        new_head='d'*40;new_base='c'*40
        self.complete('author',source=dict(head_sha=new_head,base_sha=new_base,diff=DIFF))
        self.complete('review2',result=json.dumps(dict(verdict='approve',findings=[],head_sha=new_head,base_sha=new_base,reviewer_thread_id='review2')))
        self.source.host.read_pr=lambda r,p:dict(repository=REPO,head_repository=REPO,number=7,head_sha=new_head,base_sha=new_base,state='open',merged=False)
        candidate=candidate_receipt(self.a['source_issue'],self.source.host.read_pr(REPO,7),21,'Check '+new_head,'2030-01-01T00:02:00Z')
        a=self.emit('candidate',candidate=candidate)
        self.assertEqual(a['candidate'],candidate)
        self.s.validate_lifecycle_command(self.command()['command_id'],'c1')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM acceptance_repository').fetchone()[0],0)
        with self.assertRaises(ServiceError):self.emit('reporter_verified',verification=validate_verification(comment,self.c,dict(repository=REPO,head_repository=REPO,number=7,head_sha=H,base_sha=B,state='open',merged=False)))
