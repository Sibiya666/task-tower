import copy
import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from tests.test_service_beads import NativeFixture, Beads
from task_tower.service.store import Store, encoded
from task_tower.issue_intake import INITIAL_POLICY
from task_tower.service.issue_admission import IssueBinding
from task_tower.service.beads import ServiceError

BODY="## Reproduction\nRead example.\n## Expected behavior\nCorrect text.\n## Acceptance criteria\nReadable example.\n## Files\ndocs/example.md"
class Source:
    def __init__(self): self.body=BODY; self.authorized=True
    def snapshot(self,number):
        s=dict(repository="Sibiya666/task-tower",repository_id=9,issue_number=number,reporter_id=21,owner_id=21 if self.authorized else 22,reporter_type="User",push_collaborator=False,verified_at=time.time(),state="open",body=self.body,existing_regular_paths=["docs/example.md"],runtime_scope_verified=True,base_sha="a"*40)
        s["source_revision"]=hashlib.sha256(encoded([number,self.body]).encode()).hexdigest()
        return s
class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.native=NativeFixture();self.beads=Beads(Path(self.tmp.name)/"bd",{"p":Path(self.tmp.name)},runner=self.native)
        self.source=Source();p=copy.deepcopy(INITIAL_POLICY);p["initially_enabled"]=True
        self.binding=IssueBinding(p,self.source,"c1",repository_id=9)
        self.path=Path(self.tmp.name)/"journal"
        self.store=Store(self.path,self.beads,issue_bindings={"p":self.binding});self.addCleanup(lambda:self.store.close())
    def admit(self,number=12):
        s=self.source.snapshot(number)
        return self.store.admit_issue("request-"+str(number),"p",number,s["source_revision"],"c1")
    def test_policy_route_publishes_one_native_task_without_adding_digest_allowlist(self):
        receipt=self.admit();self.assertEqual(receipt["state"],"published")
        self.assertEqual(len(self.native.rows),1);self.assertEqual(self.store.approved_plans,{})
        self.assertEqual(self.admit(),receipt)
        self.assertEqual(len(self.native.rows),1)
        self.assertEqual([x["id"] for x in self.store.ready("p")],[receipt["bead_id"]])
        a=self.store.claim_request("claim","p",receipt["bead_id"],"c1")
        self.assertEqual(a["phase"],"claimed");self.assertEqual(a["source_issue"]["issue_number"],12)
        self.store.validate_execution(a["attempt_id"],"c1")
    def test_missing_details_and_legacy_issue_have_no_native_effect(self):
        self.source.body="not enough detail"
        self.assertEqual(self.admit()["state"],"clarify");self.assertEqual(self.native.rows,{})
        self.source.body=BODY
        self.assertEqual(self.admit(121)["state"],"needs_input");self.assertEqual(self.native.rows,{})
    def test_changed_revision_foreign_connector_and_revoked_access_block_effects(self):
        with self.assertRaises(ServiceError):self.store.admit_issue("x","p",12,"b"*64,"c1")
        with self.assertRaises(ServiceError):self.store.admit_issue("x","p",12,self.source.snapshot(12)["source_revision"],"c2")
        self.source.authorized=False
        self.assertEqual(self.admit()["state"],"needs_input");self.assertEqual(self.native.rows,{})
    def test_native_unknown_is_fenced_and_not_replayed_after_restart(self):
        self.native.fail_at="create"
        receipt=self.admit();self.assertEqual(receipt["state"],"needs_reconciliation")
        count=len(self.native.calls);self.store.close()
        self.store=Store(self.path,self.beads,issue_bindings={"p":self.binding})
        self.assertEqual(self.admit(),receipt);self.assertEqual(len(self.native.calls),count)
    def test_reserved_admission_counts_against_one_author_limit(self):
        self.admit();self.assertEqual(self.admit(13)["state"],"needs_input")
        self.assertEqual(len(self.native.rows),1)
    def test_source_change_after_admission_blocks_claim_without_rewriting_task(self):
        receipt=self.admit();self.source.body=BODY.replace("Correct text.","Different task.")
        a=self.store.claim_request("claim","p",receipt["bead_id"],"c1")
        self.assertEqual(a["phase"],"needs_reconciliation")
        self.assertIsNone(self.native.rows[receipt["bead_id"]].get("assignee"))
