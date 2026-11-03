"""A confirmed no-launch failure is distinct from uncertain process cleanup."""
import copy
import unittest
import uuid
import test_pr_journal as fixture


class FailedObservationTests(unittest.TestCase):
    setUp=fixture.JournalTests.setUp

    def test_exact_no_launch_failure_consumes_original_review_without_a_fake_pid(self):
        with self.j.owner(self.owner):
            self.j.admit(fixture.binding())
            for old,new in [('discovered','validating'),('validating','reviewing')]:
                self.j.transition('owner/repo',44,self.owner,dict(state=old,input_sha256='c'*64),dict(state=new))
            effect=self.j.begin_effect('owner/repo',44,self.owner,'pr_review',dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='c'*64))
            no_launch=dict(pid=None,exit_code=None,started=False,cleanup_confirmed=True)
            for mutation in [dict(no_launch,cleanup_confirmed=False),dict(no_launch,pid=123),dict(no_launch,exit_code=0)]:
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    self.j.observe(effect['effect_id'],self.owner,dict(status='failed',process=mutation))
            saved=self.j.observe(effect['effect_id'],self.owner,dict(status='failed',process=no_launch))
            self.assertEqual(saved['observation']['process'],no_launch)
            self.assertEqual(self.j.get('owner/repo',44)['review_attempts'],1)
            with self.assertRaises(ValueError):
                self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',process=no_launch))
