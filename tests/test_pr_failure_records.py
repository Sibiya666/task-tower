"""Real prepared admission and actual OS no-launch outcome, not an imported PID."""
import copy
import json
import faulthandler
import sys
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
import test_pr_retained_records as fixtures
from task_tower.pr_policy import canonical
from task_tower.pr_review import PRReviewRunner,validate_pr_review


class FailureRecordTests(unittest.TestCase):
    with_review=False
    source=fixtures.PreparedRecordTests.source
    current=fixtures.PreparedRecordTests.current
    identity=fixtures.PreparedRecordTests.identity
    fetch_transport=fixtures.PreparedRecordTests.fetch_transport

    def context(self):
        value=json.loads(self.policy.read_text());value['projects'][0]['tasks'][0]['reviewer_profile']='bad-binary'
        self.policy.write_text(json.dumps(value),encoding='utf-8')
        return fixtures.PreparedRecordTests.context(self)

    @classmethod
    def setUpClass(cls):
        faulthandler.dump_traceback_later(90)
        current=fixtures.preparation_fixture.current_fixture;real=current.installed_load
        def install(f):
            binary=f.root/'invalid-review.exe';binary.write_bytes(b'Not an executable image.\n')
            profile=copy.deepcopy(f.profile);profile['argv']=[str(binary)];profile['runs_dir']=str(f.root/'failed-pr-runs');profile['max_attempts']=1
            if getattr(cls,'mode',None) in ('incomplete','reject'):
                script="import argparse,json,pathlib;p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args();r=json.loads(pathlib.Path(a.request).read_text());v={k:r[k] for k in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')};v.update(verdict='approve',summary='Actual incomplete review fixture.',findings=[],whole_diff_reviewed=False);pathlib.Path(a.result).write_text(json.dumps(v))"
                if cls.mode=='reject':script=script.replace("verdict='approve'","verdict='reject'").replace('whole_diff_reviewed=False','whole_diff_reviewed=True')
                profile['argv']=[str(Path(sys.executable).resolve()),'-c',script]
            f.executor['profiles']['bad-binary']=profile
            return real(f)
        with patch.object(current,'installed_load',side_effect=install):
            fixtures.PreparedRecordTests.setUpClass.__func__(cls)
        try:
            cls.owner_id=str(uuid.uuid4());cls.owner=cls.pr.owner(cls.owner_id);cls.owner.__enter__()
            for old,new in [('discovered','validating'),('validating','reviewing')]:
                cls.pr.transition(cls.request['repository'],cls.request['pr_number'],cls.owner_id,
                    dict(state=old,input_sha256=cls.input_sha),dict(state=new))
            cls.effect=cls.pr.begin_effect(cls.request['repository'],cls.request['pr_number'],cls.owner_id,'pr_review',
                dict(reviewer_instance_id=cls.request['reviewer_instance_id'],request_sha256=cls.input_sha))
            profile=cls.ctx._fresh_inputs()['executor']['profiles']['bad-binary']
            cls.envelope=PRReviewRunner(profile).review(Path(cls.prepared['checkout']),cls.request,cls.namespace/'roles'/str(uuid.uuid4()))
            process=cls.envelope['process']
            expected_started=getattr(cls,'mode',None) in ('incomplete','reject')
            if process['started'] is not expected_started or process['cleanup_confirmed'] is not True or not expected_started and process['pid'] is not None:
                raise AssertionError(process)
            cls.record=dict(request=cls.request,envelope=cls.envelope,review_effect_id=cls.effect['effect_id'],
                private_input_provenance=cls.ctx.private_input_provenance)
            if getattr(cls,'mode',None)=='reject':
                cls.receipt=validate_pr_review(cls.envelope,cls.request,())
                if cls.receipt.get('verdict')!='reject' or 'receipt_sha256' not in cls.receipt:raise AssertionError(cls.receipt)
                cls.record['receipt']=cls.receipt
                cls.review_path=cls.namespace/'review-records'/(cls.effect['effect_id']+'.json');cls.review_path.parent.mkdir()
                cls.review_path.write_bytes(canonical(cls.record).encode())
                cls.pr.observe(cls.effect['effect_id'],cls.owner_id,dict(status='confirmed',reviewer_instance_id=cls.request['reviewer_instance_id'],
                    result_sha256=cls.receipt['result_sha256'],receipt_sha256=cls.receipt['receipt_sha256'],
                    process={k:process[k] for k in ('pid','exit_code','started','cleanup_confirmed')}))
                cls.pr.transition(cls.request['repository'],cls.request['pr_number'],cls.owner_id,dict(state='reviewing',input_sha256=cls.input_sha),
                    dict(state='reviewed',pr_receipt_sha256=cls.receipt['receipt_sha256'],reviewer_instance_id=cls.request['reviewer_instance_id']))
                cls.pr.transition(cls.request['repository'],cls.request['pr_number'],cls.owner_id,dict(state='reviewed',input_sha256=cls.input_sha),dict(state='publishing_acceptance'))
                faulthandler.cancel_dump_traceback_later()
                return
            cls.failed_path=cls.namespace/'failure-records'/(cls.effect['effect_id']+'.json');cls.failed_path.parent.mkdir()
            cls.original=canonical(cls.record).encode();cls.failed_path.write_bytes(cls.original)
            cls.pr.observe(cls.effect['effect_id'],cls.owner_id,dict(status='failed',
                reviewer_instance_id=cls.request['reviewer_instance_id'],process={k:process[k] for k in ('pid','exit_code','started','cleanup_confirmed')}))
        except BaseException:
            if hasattr(cls,'owner'):cls.owner.__exit__(None,None,None)
            fixtures.PreparedRecordTests.tearDownClass.__func__(cls)
            faulthandler.cancel_dump_traceback_later()
            raise
        faulthandler.cancel_dump_traceback_later()

    @classmethod
    def tearDownClass(cls):
        cls.owner.__exit__(None,None,None)
        fixtures.PreparedRecordTests.tearDownClass.__func__(cls)

    def test_actual_failed_host_record_is_readonly_and_never_a_receipt(self):
        self.assertTrue(callable(getattr(self.ctx,'failure_record',None)),'Missing genuine failure reader')
        before=self.journal.read_bytes()
        self.assertEqual(self.ctx.failure_record(self.input_sha),self.record)
        self.assertEqual(self.journal.read_bytes(),before)
        with self.assertRaises(ValueError):self.ctx.review_record(self.input_sha)
        changed=copy.deepcopy(self.record);changed['envelope']['process']['pid']=123
        try:
            self.failed_path.write_bytes(canonical(changed).encode())
            with self.assertRaises(ValueError):self.ctx.failure_record(self.input_sha)
        finally:self.failed_path.write_bytes(self.original)

    def test_genuine_failed_host_publishes_only_input_bound_failure_status(self):
        from test_pr_diagnostic_effects import diagnostic
        from task_tower.pr_effects import PREffects
        self.assertTrue(callable(getattr(PREffects,'publish_failure',None)),'Missing genuine failure diagnostic')
        effects,store=diagnostic(self,self.owner_id)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            first=effects.publish_failure();second=effects.publish_failure()
        self.assertEqual(first['status'],'confirmed');self.assertEqual(first['effect_id'],second['effect_id'])
        self.assertEqual(first['payload']['receipt_sha256'],self.input_sha)
        self.assertEqual(store['posts'][0][1]['state'],'failure');self.assertEqual(len(store['posts']),1)


class IncompleteReviewFailureTests(FailureRecordTests):
    mode='incomplete'


class NegativeReviewEffectsTests(FailureRecordTests):
    mode='reject'

    def test_actual_failed_host_record_is_readonly_and_never_a_receipt(self):
        self.assertEqual(self.ctx.review_record(self.input_sha)['receipt']['verdict'],'reject')
        with self.assertRaises(ValueError):self.ctx.failure_record(self.input_sha)

    def test_genuine_failed_host_publishes_only_input_bound_failure_status(self):
        from test_pr_diagnostic_effects import diagnostic
        effects,store=diagnostic(self,self.owner_id)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            report=effects.publish_failure();status=effects.publish_failure();repeat=effects.publish_failure()
        self.assertEqual(report['kind'],'acceptance_review');self.assertEqual(report['payload']['event'],'COMMENT')
        self.assertIn('Verdict: reject',report['payload']['body'])
        self.assertEqual(status['payload']['state'],'failure');self.assertEqual(status['payload']['receipt_sha256'],self.receipt['receipt_sha256'])
        self.assertEqual(status['effect_id'],repeat['effect_id']);self.assertEqual(len(store['posts']),2)
