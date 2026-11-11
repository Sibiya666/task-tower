import copy
import unittest
from task_tower.reporter_verification import candidate_receipt,validate_verification,reporter_ready
S=dict(repository="owner/repo",repository_id=9,issue_number=12,reporter_id=21)
H="b"*40; B="a"*40
PR=dict(repository="owner/repo",head_repository="owner/repo",number=3,head_sha=H,base_sha=B,state="open",merged=False)
class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.c=candidate_receipt(S,PR,21,"Fetch and test commit "+H,"2030-01-01T00:00:00Z")
        self.comment=dict(id=44,body="/task-tower verified "+H,user=dict(id=21,type="User"),created_at="2030-01-01T00:01:00Z",updated_at="2030-01-01T00:01:00Z",issue_url="https://api.github.com/repos/owner/repo/issues/12")
    def test_exact_original_numeric_reporter_can_verify_exact_candidate(self):
        v=validate_verification(self.comment,self.c,PR)
        self.assertEqual(v["comment_id"],44); self.assertEqual(v["head_sha"],H)
    def test_wrong_author_bot_sha_unbound_phrase_and_edited_comment_are_rejected(self):
        for key,value in [("user",dict(id=22,type="User")),("user",dict(id=21,type="Bot")),("body","ready"),("body","/task-tower verified "+"c"*40),("updated_at","2030-01-01T00:02:00Z"),("created_at","2029-01-01T00:00:00Z"),("issue_url","https://api.github.com/repos/owner/repo/issues/13")]:
            row=copy.deepcopy(self.comment); row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): validate_verification(row,self.c,PR)
    def test_head_and_base_movement_invalidate_candidate(self):
        for key in ["head_sha","base_sha"]:
            pr=dict(PR);pr[key]="c"*40
            with self.assertRaises(ValueError):validate_verification(self.comment,self.c,pr)
    def test_fresh_readback_required_and_deleted_comment_is_not_ready(self):
        class Host:
            def read_pr(_,r,p): return dict(PR)
            def _pages(_,r,p): return []
        a=dict(source_issue=S,candidate=self.c)
        self.assertFalse(reporter_ready(a,Host()))
    def test_later_explicit_negative_report_invalidates_confirmation(self):
        rows=[self.comment,dict(self.comment,id=45,body="/task-tower changes "+H,created_at="2030-01-01T00:02:00Z",updated_at="2030-01-01T00:02:00Z")]
        class Host:
            def read_pr(_,r,p): return dict(PR)
            def _pages(_,r,p): return rows
        self.assertFalse(reporter_ready(dict(source_issue=S,candidate=self.c),Host()))
        rows.pop(); self.assertTrue(reporter_ready(dict(source_issue=S,candidate=self.c),Host()))
    def test_missing_instructions_or_reporter_substitution_is_rejected(self):
        with self.assertRaises(ValueError):candidate_receipt(S,PR,22,"test","2030-01-01T00:00:00Z")
        with self.assertRaises(ValueError):candidate_receipt(S,PR,21,"","2030-01-01T00:00:00Z")
