import copy
import unittest
from task_tower.issue_intake import evaluate_issue, parse_request, validate_changes, INITIAL_POLICY

NOW=1893456000
BODY="## Reproduction\nOpen example.\n## Expected behavior\nShow correct text.\n## Acceptance criteria\nThe example is readable.\n## Files\ndocs/example.md"
def snapshot(): return dict(repository="Sibiya666/task-tower",repository_id=9,issue_number=12,reporter_id=21,owner_id=21,reporter_type="User",push_collaborator=False,verified_at=NOW,state="open",body=BODY,existing_regular_paths=["docs/example.md"],runtime_scope_verified=True)
class PolicyTests(unittest.TestCase):
    def setUp(self): self.policy=copy.deepcopy(INITIAL_POLICY); self.policy["initially_enabled"]=True
    def evaluate(self,s=None,c=None): return evaluate_issue(s or snapshot(),self.policy,c or dict(active_authors=0,admissions_today=0),NOW)
    def test_complete_owner_request_compiles_a_bounded_scope(self):
        d=self.evaluate(); self.assertEqual(d.state,"admit"); self.assertEqual(d.paths,("docs/example.md",))
    def test_missing_details_require_clarification(self):
        s=snapshot(); s["body"]="Please fix this"
        self.assertEqual(self.evaluate(s).state,"clarify")
        self.assertEqual(parse_request(BODY)["reproduction"],"Open example.")
    def test_disabled_policy_stale_permissions_foreign_repo_and_bots_do_not_admit(self):
        self.policy["initially_enabled"]=False; self.assertEqual(self.evaluate().state,"needs_input"); self.policy["initially_enabled"]=True
        for key,value in [("verified_at",NOW-61),("reporter_id",22),("reporter_type","Bot"),("repository","foreign/repo"),("runtime_scope_verified",False),("state","closed")]:
            s=snapshot(); s[key]=value
            with self.subTest(key=key): self.assertNotEqual(self.evaluate(s).state,"admit")
    def test_capacity_and_daily_limit_fail_closed(self):
        for c in [dict(active_authors=1,admissions_today=0),dict(active_authors=0,admissions_today=2)]: self.assertEqual(self.evaluate(c=c).state,"needs_input")
    def test_sensitive_hidden_traversal_and_missing_paths_are_never_authorized(self):
        for path in ["../README.md","docs/.private/a.md",".github/workflows/x.yml","task_tower/service/store.py","task_tower/connector/github_app.py","task_tower/issue_intake.py","task_tower/windows_job.py","task_tower/github_source.py","docs/new.md","docs/example.md;whoami"]:
            s=snapshot(); s["body"]=BODY.replace("docs/example.md",path)
            if path!="docs/new.md": s["existing_regular_paths"]=[path]
            with self.subTest(path=path): self.assertEqual(self.evaluate(s).state,"needs_input")
    def test_collaborator_permission_must_be_freshly_observed(self):
        s=snapshot(); s["reporter_id"]=22; s["push_collaborator"]=True
        self.assertEqual(self.evaluate(s).state,"admit")
    def test_postdiff_rejects_scope_mode_delete_symlink_and_line_overflow(self):
        good=[dict(path="docs/example.md",status="M",old_mode="100644",new_mode="100644",added=2,deleted=1)]
        validate_changes(good,("docs/example.md",),self.policy)
        for field,value in [("path","README.md"),("status","D"),("new_mode","120000"),("added",1001)]:
            rows=copy.deepcopy(good); rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): validate_changes(rows,("docs/example.md",),self.policy)

    def test_empty_issue_template_comments_trigger_clarification(self):
        s=snapshot();s["body"]="## Reproduction\n<!-- Fill this -->\n## Expected behavior\n<!-- Fill this -->\n## Acceptance criteria\n<!-- Fill this -->\n## Files\n<!-- Existing files only -->"
        self.assertEqual(self.evaluate(s).state,"clarify")
