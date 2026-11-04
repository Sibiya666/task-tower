"""Negative SQLite race tests; metadata fixtures grant no host authority."""
from contextlib import contextmanager
from datetime import datetime,timedelta
from unittest.mock import patch
import unittest
from tests import test_pr_journal as fixture
from task_tower.pr_policy import policy_fingerprint


class CompletionTransactionTests(unittest.TestCase):
    setUp=fixture.JournalTests.setUp
    ready=fixture.JournalTests.ready
    publication_ready=fixture.JournalTests.publication_ready
    confirm_comment=fixture.JournalTests.confirm_comment

    @contextmanager
    def fault(self,kind):
        real=self.j._db;row=self.j.get('owner/repo',44)
        @contextmanager
        def acquired(write=False):
            with real(write) as db:
                if write and kind=='cancel':
                    current=self.j._get(db,'owner/repo',44);current['cancel_requested']=True;self.j._save(db,current)
                if write and kind=='deadline':
                    expired=datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))+timedelta(seconds=1)
                    with patch('task_tower.pr_journal._now',return_value=expired):yield db
                else:yield db
        with patch.object(self.j,'_db',side_effect=acquired):yield

    def comment_fault(self,kind):
        with self.j.owner(self.owner):
            publication=self.publication_ready()
            effect=self.j.begin_effect('owner/repo',44,self.owner,'comment_post',
                dict(publication_id=publication['publication_id'],body_sha256=publication['body_sha256']))
            with self.fault(kind),self.assertRaises(ValueError):
                self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',remote_id=9,
                    body_sha256=publication['body_sha256'],author='operator'))
            self.assertEqual(self.j.effect(effect['effect_id'])['status'],'intent')
            self.assertIsNotNone(self.j.barrier('owner/repo'))

    def barrier_fault(self,kind):
        with self.j.owner(self.owner):
            publication=self.confirm_comment(self.publication_ready())
            effect=self.j.begin_effect('owner/repo',44,self.owner,'issue_close',
                dict(publication_id=publication['publication_id'],issue_id=1017,state='closed',state_reason='completed'))
            self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',issue_id=1017,state='closed',state_reason='completed'))
            self.j.record_publication(publication['publication_id'],self.owner,'close_intent',dict(phase='closure_observed'))
            row=self.j.get('owner/repo',44)
            proof=dict({k:row[k] for k in ('repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','merge_commit','pr_receipt_sha256','postmerge_receipt_sha256')},
                main_sha=row['merge_commit'],bundle_sha256=policy_fingerprint(publication['receipt']['bundle']),
                publication_id=publication['publication_id'],verified_done=True,issue_state='closed',state_reason='completed')
            self.j.record_publication(publication['publication_id'],self.owner,'closure_observed',dict(phase='published',completion_proof=proof))
            with self.fault(kind),self.assertRaises(ValueError):self.j.complete_barrier('owner/repo',self.owner,proof)
            self.assertIsNotNone(self.j.barrier('owner/repo'))
            self.assertNotEqual(self.j.get('owner/repo',44)['state'],'completed')

    def test_comment_confirmation_rechecks_deadline_after_lock(self):self.comment_fault('deadline')
    def test_comment_confirmation_rechecks_cancel_after_lock(self):self.comment_fault('cancel')
    def test_barrier_completion_rechecks_deadline_after_lock(self):self.barrier_fault('deadline')
    def test_barrier_completion_rechecks_cancel_after_lock(self):self.barrier_fault('cancel')
