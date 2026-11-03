"""Confirmation revalidates original gates after its actual write lock."""
from contextlib import contextmanager
from datetime import datetime,timedelta
from unittest.mock import patch
import unittest
import test_pr_journal as fixture

class MergeTransactionTests(unittest.TestCase):
    setUp=fixture.JournalTests.setUp
    ready=fixture.JournalTests.ready

    def check_fault(self,kind):
        with self.j.owner(self.owner):
            self.ready(); row=self.j.get('owner/repo',44)
            from task_tower.pr_journal import BINDING
            self.j.acquire_barrier('owner/repo',44,self.owner,{k:row[k] for k in BINDING})
            effect=self.j.begin_effect('owner/repo',44,self.owner,'merge',dict(sha=row['head_sha'],merge_method='merge',merge_action='direct_merge',bypass_rules=False))
            real=self.j._db
            @contextmanager
            def acquired(write=False):
                with real(write) as db:
                    if write:
                        if kind=='cancel':
                            current=self.j._get(db,'owner/repo',44);current['cancel_requested']=True;self.j._save(db,current)
                        expired=datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))+timedelta(seconds=1)
                        if kind=='deadline':
                            with patch('task_tower.pr_journal._now',return_value=expired):yield db
                        else:yield db
                    else:yield db
            with patch.object(self.j,'_db',side_effect=acquired),self.assertRaises(ValueError):
                self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',merge_commit='e'*40,main_sha='e'*40,parents=[row['base_sha'],row['head_sha']],result='merged'))
            self.assertNotEqual(self.j.get('owner/repo',44)['state'],'awaiting_main')
            self.assertEqual(self.j.effects('owner/repo',44)[-1]['status'],'intent')
            self.assertFalse(self.j.barrier('owner/repo')['completed'])

    def test_deadline_after_confirmation_transaction_acquisition(self):self.check_fault('deadline')
    def test_cancel_after_confirmation_transaction_acquisition(self):self.check_fault('cancel')
