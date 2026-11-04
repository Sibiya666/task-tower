"""Original archive facts stay diagnostic even when live PR prose changes."""
import json
import tempfile
import unittest
from pathlib import Path
from tests import test_github_source as source_fixture
from tests.test_pr_journal import binding
from task_tower.pr_journal import PRJournal


class RecoveryInspectionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.journal=PRJournal(Path(self.directory.name).resolve()/'pr.db')
        self.row=self.journal.admit(dict(binding(),pr_number=7,task_id='TT-ONE'))

    def inspect(self,source):
        from task_tower.pr_recovery import inspect_recovery
        return inspect_recovery(self.row,self.journal,source)

    def test_live_marker_edit_never_refreshes_original_event_or_changes_journal(self):
        def original(pr,run,event):event['task_ids']=[]
        source=source_fixture.GitHubSourceTests().source(original)
        before=self.journal.path.read_bytes()
        result=self.inspect(source)
        self.assertEqual(result['required_action'],'reviewed_followup_required')
        self.assertEqual(result['live_task_ids'],['TT-ONE'])
        self.assertEqual(result['events'][0]['task_ids'],[])
        self.assertEqual(result['events'][0]['run_id'],'12')
        self.assertEqual(result['events'][0]['attempt'],'2')
        self.assertEqual(result['events'][0]['artifact_id'],22)
        again=self.inspect(source)
        self.assertEqual(result,again)
        self.assertEqual(before,self.journal.path.read_bytes())
        self.assertIsNone(self.journal.barrier('owner/repo'))

    def test_valid_marker_only_reports_diagnostic_facts_never_completion(self):
        result=self.inspect(source_fixture.GitHubSourceTests().source())
        self.assertEqual(result['required_action'],'fresh_acceptance_required')
        self.assertNotIn('verified_done',result)
        self.assertNotIn('receipt',result)
        self.assertEqual(result['events'][0]['task_ids'],['TT-ONE'])

    def test_conflicting_archived_mapping_is_parked(self):
        source=source_fixture.GitHubSourceTests().source(lambda p,r,e:e.update(task_ids=['TT-OTHER']))
        result=self.inspect(source)
        self.assertEqual(result['required_action'],'explicit_reconciliation_required')

    def test_wrong_source_and_mismatched_run_are_refused_without_writes(self):
        source=source_fixture.GitHubSourceTests().source(lambda p,r,e:r.update(run_attempt=3))
        before=self.journal.path.read_bytes()
        with self.assertRaises(ValueError):self.inspect(source)
        with self.assertRaises(ValueError):self.inspect({})
        self.assertEqual(before,self.journal.path.read_bytes())

    def test_expired_archive_is_never_replaced_with_live_body(self):
        source=source_fixture.GitHubSourceTests().source();original=source.transport
        def expired(url,headers,limit):
            raw=original(url,headers,limit)
            if '/artifacts?' in url:
                value=json.loads(raw);value['artifacts'][0]['expired']=True
                return json.dumps(value).encode()
            return raw
        source.transport=expired
        with self.assertRaises(ValueError):self.inspect(source)

    def test_boolean_version_does_not_equal_integer_version(self):
        source=source_fixture.GitHubSourceTests().source(lambda p,r,e:e.update(version=True))
        with self.assertRaises(ValueError):self.inspect(source)
