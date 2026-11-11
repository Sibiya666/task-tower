import unittest
from task_tower.issue_source import GitHubIssueSource
from tests.test_issue_policy import BODY
class Host:
    def __init__(self):self.comments=[];self.push=True;self.login="original";self.mismatch=False
    def _request(self,r,m,p,payload=None):
        if p=="/":return dict(id=99 if self.mismatch else 9,owner=dict(id=21))
        if p=="/issues/12":return dict(number=12,body=BODY,state="open",user=dict(id=22,login=self.login,type="User"))
        if p.startswith("/collaborators/"):return dict(user=dict(id=22,permissions=dict(push=self.push)))
        raise AssertionError(p)
    def _pages(self,r,p):return self.comments
class SourceTests(unittest.TestCase):
    def setUp(self):self.h=Host();self.s=GitHubIssueSource(self.h,"Sibiya666/task-tower",9,lambda paths:dict(regular_paths=list(paths),runtime_scope_verified=True,base_sha="a"*40))
    def test_source_uses_current_numeric_identity_and_permission(self):
        a=self.s.snapshot(12);self.assertTrue(a["push_collaborator"])
        self.h.push=False;self.assertFalse(self.s.snapshot(12)["push_collaborator"])
    def test_only_original_reporter_can_supply_clarification_fields(self):
        self.h.comments=[dict(id=1,body="## Reproduction\nattacker",user=dict(id=23,type="User"))]
        self.assertNotIn("attacker",self.s.snapshot(12)["body"])
        self.h.comments[0]["user"]["id"]=22
        self.assertIn("attacker",self.s.snapshot(12)["body"])
    def test_verification_and_bot_comments_do_not_change_admitted_revision(self):
        a=self.s.snapshot(12)
        self.h.comments=[dict(id=1,body="/task-tower verified "+"b"*40,user=dict(id=22,type="User"))]
        self.assertEqual(self.s.snapshot(12)["source_revision"],a["source_revision"])
    def test_foreign_repository_has_no_scope_inspection(self):
        self.h.mismatch=True
        with self.assertRaises(ValueError):self.s.snapshot(12)
