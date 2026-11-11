import copy
import unittest
from tests import test_headless_delivery as fixtures
from task_tower.connector.store import ConnectorStore
from task_tower.connector.delivery import Delivery
import tempfile
from pathlib import Path
attempt,REPO,H,B=fixtures.attempt,fixtures.REPO,fixtures.H,fixtures.B
from task_tower.connector.delivery import Pending
from task_tower.reporter_verification import candidate_receipt

S=dict(repository=REPO,repository_id=9,issue_number=12,reporter_id=21)
class IssueDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ConnectorStore(Path(self.tmp.name)/'journal','stage5-fixture');self.addCleanup(self.store.close)
        self.host=fixtures.Host();self.d=Delivery(self.host,self.store,{'p':REPO})
    def issue(self,verified=False):
        a=attempt();a["source_issue"]=S
        pr=dict(self.host.pr)
        c=candidate_receipt(S,pr,21,"Check "+H,"2030-01-01T00:00:00Z");a["candidate"]=c
        self.host.comments=[]
        if verified:self.host.comments=[dict(id=44,body="/task-tower verified "+H,user=dict(id=21,type="User"),created_at="2030-01-01T00:01:00Z",updated_at="2030-01-01T00:01:00Z",issue_url="https://api.github.com/repos/"+REPO+"/issues/12")]
        self.host._pages=lambda r,p:self.host.comments
        self.d.prepare_pr(a);return a
    def test_missing_reporter_confirmation_blocks_merge_without_holding_repository(self):
        self.issue()
        with self.assertRaises(Pending):self.d.merge_expected(REPO,7,H,B)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM repository_delivery").fetchone()[0],0)
        self.assertNotIn("merge",self.host.calls)
    def test_reporter_confirmation_does_not_waive_failed_ci(self):
        self.issue(True);self.host.checks[0]["conclusion"]="failure"
        with self.assertRaises(ValueError):self.d.merge_expected(REPO,7,H,B)
        self.assertNotIn("merge",self.host.calls)
    def test_confirmation_deleted_during_checks_blocks_final_merge(self):
        self.issue(True);original=self.host.read_checks
        def checks(r,h):self.host.comments=[];return original(r,h)
        self.host.read_checks=checks
        with self.assertRaises(Pending):self.d.merge_expected(REPO,7,H,B)
        self.assertNotIn("merge",self.host.calls)
    def test_current_reporter_confirmation_preserves_existing_protected_merge(self):
        self.issue(True);self.assertEqual(self.d.merge_expected(REPO,7,H,B)["head_sha"],H)
        self.assertEqual(self.host.calls.count("merge"),1)
    def test_merged_candidate_is_not_revalidated_while_postmerge_checks_are_pending(self):
        a=self.issue(True);self.d.merge_expected(REPO,7,H,B)
        self.host.comments=[]
        self.d._issue_candidate(dict(attempt=a,project_id='p'),None)
        self.assertEqual(self.host.calls.count('merge'),1)
    def test_persisted_merge_intent_reads_back_fact_without_requiring_open_pr(self):
        self.issue(True)
        d=self.d._load(REPO,7);d['phase']='merge_intent';self.d._save(d)
        self.host.merge(REPO,7,H);self.host.comments=[]
        result=self.d.merge_expected(REPO,7,H,B)
        self.assertEqual(result['main_sha'],fixtures.M)
        self.assertEqual(self.host.calls.count('merge'),1)
    def test_restart_accepts_only_persisted_dynamic_candidate_fields(self):
        a=attempt();a['source_issue']=S;self.d.prepare_pr(a)
        d=self.d._load(REPO,7)
        d['attempt']['candidate']=candidate_receipt(S,self.host.pr,21,'Check '+H,'2030-01-01T00:00:00Z')
        d['attempt']['reporter_verification']={'comment_id':44}
        self.d._save(d)
        self.assertEqual(self.d.prepare_pr(a),dict(repository=REPO,pr_number=7))
        self.assertEqual(self.host.calls.count('prepare'),1)
        changed=copy.deepcopy(a);changed['author_thread_id']='different'
        with self.assertRaisesRegex(ValueError,'delivery_source_changed'):self.d.prepare_pr(changed)
