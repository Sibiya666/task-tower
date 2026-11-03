"""Actual retained stage producer -> opt-in provenance-bound preparation."""
from pathlib import Path
import copy
import unittest
import uuid
from unittest.mock import patch

import test_pr_context_current as current_fixture
from task_tower.pr_journal import PRJournal
from task_tower.pr_policy import policy_fingerprint
from task_tower.pr_source import prepare_review, PRSourceError


class PreparationContextTests(unittest.TestCase):
    setUpClass=classmethod(current_fixture.CurrentAuthorityTests.setUpClass.__func__)
    tearDownClass=classmethod(current_fixture.CurrentAuthorityTests.tearDownClass.__func__)
    context=current_fixture.CurrentAuthorityTests.context
    source=current_fixture.CurrentAuthorityTests.source
    current=current_fixture.CurrentAuthorityTests.current
    identity=current_fixture.CurrentAuthorityTests.identity
    fetch_transport=current_fixture.CurrentAuthorityTests.fetch_transport

    def test_actual_preparation_binds_current_private_provenance_and_host_location(self):
        with PRJournal(self.journal)._db(True): pass
        context=self.context(); source=self.source(context); fresh=self.current(context,source)
        self.assertIsNone(fresh['authority_error'])
        directory=Path(str(self.journal)+'.private')/'preparations'/str(uuid.uuid4())
        connection=context._fresh_inputs()['connections'][0]
        with patch('task_tower.pr_source._fetch',side_effect=self.fetch_transport):
            prepared=prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                directory,private_context=context)
        request=prepared['request']; data=request['input']
        self.assertEqual(data['private_input_provenance'],context.private_input_provenance)
        self.assertEqual(data['private_inputs_sha256'],context.private_inputs_sha256)
        self.assertEqual(data['private_artifact_location'],directory.relative_to(
            Path(str(self.journal)+'.private')).as_posix()+'/request.json')
        self.assertEqual(request['input_sha256'],policy_fingerprint(data))
        # Existing callers retain the original immutable input fields.
        with patch('task_tower.pr_source._fetch',side_effect=self.fetch_transport):
            legacy=prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                self.root/('legacy-preparation-'+str(uuid.uuid4())))
        self.assertNotIn('private_input_provenance',legacy['request']['input'])

    def test_foreign_locator_or_dict_cannot_reach_git(self):
        with PRJournal(self.journal)._db(True): pass
        context=self.context(); fresh=self.current(context,self.source(context))
        connection=context._fresh_inputs()['connections'][0]
        for candidate,location in ((context,self.root/'outside'),
                (context.private_input_provenance,Path(str(self.journal)+'.private')/'preparations'/str(uuid.uuid4()))):
            with self.subTest(candidate=type(candidate).__name__),patch('task_tower.pr_source._git',
                    side_effect=AssertionError('Invalid context reached Git')),self.assertRaises(PRSourceError):
                prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                    location,private_context=candidate)
            self.assertFalse(location.exists())

    def test_private_revocation_is_refused_before_git(self):
        with PRJournal(self.journal)._db(True): pass
        context=self.context(); fresh=self.current(context,self.source(context))
        connection=context._fresh_inputs()['connections'][0]
        original=self.policy.read_bytes()
        self.addCleanup(self.policy.write_bytes,original)
        self.policy.write_bytes(original+b' ')
        location=Path(str(self.journal)+'.private')/'preparations'/str(uuid.uuid4())
        with patch('task_tower.pr_source._git',side_effect=AssertionError('Revoked inputs reached Git')),self.assertRaises(PRSourceError):
            prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                location,private_context=context)
        self.assertFalse(location.exists())

    def test_oversized_reserve_refuses_before_request_file_or_launch(self):
        with PRJournal(self.journal)._db(True): pass
        context=self.context(); fresh=self.current(context,self.source(context))
        connection=context._fresh_inputs()['connections'][0]
        location=Path(str(self.journal)+'.private')/'preparations'/str(uuid.uuid4())
        with patch('task_tower.pr_source._fetch',side_effect=self.fetch_transport),patch(
                'task_tower.pr_records.MAX_RECORD_BYTES',1024),self.assertRaises(PRSourceError):
            prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                location,private_context=context)
        self.assertFalse((location/'request.json').exists())
        self.assertFalse((location/'input.json').exists())

    def test_mutated_in_memory_reviewer_profile_is_refused_before_git(self):
        with PRJournal(self.journal)._db(True): pass
        context=self.context(); fresh=self.current(context,self.source(context))
        connection=context._fresh_inputs()['connections'][0]
        task=copy.deepcopy(fresh['task']); task['_review_profile']['timeout_seconds']+=1
        location=Path(str(self.journal)+'.private')/'preparations'/str(uuid.uuid4())
        with patch('task_tower.pr_source._git',side_effect=AssertionError('Forged profile reached Git')),self.assertRaises(PRSourceError):
            prepare_review(connection,task,fresh['snapshot'],fresh['authority'],location,private_context=context)
