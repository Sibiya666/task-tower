"""Pure nested wire contracts; no durable verdict or check launch authority."""
import copy
import unittest
from task_tower import group_wire
from task_tower.pipeline_inputs import digest_manifest
from task_tower.pipeline_journal import PipelineJournal
import test_group_wire as wire_fixture


class GroupVerdictWireTests(unittest.TestCase):
    def setUp(self):
        fixture=wire_fixture.GroupStageShapeTests(); fixture.setUp()
        self.manifest=group_wire.group_stage_shape(fixture.stage,fixture.epoch)
        self.verdict=dict(version=2,**fixture.epoch,manifest=self.manifest,
            input_sha256=digest_manifest(self.manifest),stage='spec',generation=1,
            executor_instance_id='00000000-0000-4000-8000-000000000001',
            reviewer_instance_id='00000000-0000-4000-8000-000000000002',
            reviewer_attempt_id='00000000-0000-4000-8000-000000000003',
            superpowers_sha256=self.manifest['superpowers_sha256'],policy_sha256=self.manifest['policy_sha256'],
            result_sha256='9'*64,process=dict(started=True,cleanup_confirmed=True,exit_code=0),
            decision='approve',return_stage=None)
        self.check=dict(version=1,run_id=self.manifest['run_id'],
            attempt_id='00000000-0000-4000-8000-000000000004',
            instance_id='00000000-0000-4000-8000-000000000005',manifest=dict(self.manifest,stage='test'),
            check=dict(id='unit',argv=['/owned/python','-m','unittest'],timeout_seconds=60))
        self.check['check_sha256']=digest_manifest(self.check['check'])

    def validator(self,name):
        fn=getattr(group_wire,name,None); self.assertTrue(callable(fn),'Missing pure nested wire validator')
        return fn

    def test_group_verdict2_is_closed_nested_epoch_bound_and_legacy_refuses(self):
        fn=self.validator('validate_group_verdict_shape'); original=copy.deepcopy(self.verdict)
        self.assertEqual(fn(self.verdict),self.verdict); self.assertEqual(original,self.verdict)
        with self.assertRaises(ValueError): PipelineJournal._receipt_body(self.verdict)
        for field,value in (('version',True),('base_epoch',True),('generation',True),
                ('input_sha256','0'*64),('task_delta_sha256','0'*64),('extra',True)):
            with self.subTest(field=field),self.assertRaises(ValueError): fn(dict(self.verdict,**{field:value}))

    def test_verdict_reject_return_and_missing_fields_preserve_legacy_rules(self):
        fn=self.validator('validate_group_verdict_shape')
        self.assertEqual(fn(dict(self.verdict,decision='reject',return_stage='spec'))['decision'],'reject')
        for decision,stage in (('approve','spec'),('needs_input','spec'),('reject','development')):
            with self.assertRaises(ValueError): fn(dict(self.verdict,decision=decision,return_stage=stage))
        for key in self.verdict:
            value=dict(self.verdict); value.pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError): fn(value)

    def test_check_wrapper_stays_version1_with_stage2_and_original_hash(self):
        fn=self.validator('validate_group_check_request_shape'); original=copy.deepcopy(self.check)
        self.assertEqual(fn(self.check),self.check); self.assertEqual(original,self.check)
        for key,value in (('version',True),('version',2),('run_id',self.verdict['executor_instance_id']),
                ('check_sha256','0'*64),('base_epoch',0),('extra',True)):
            with self.subTest(key=key),self.assertRaises(ValueError): fn(dict(self.check,**{key:value}))
        changed=copy.deepcopy(self.check); changed['manifest']['version']=1
        with self.assertRaises(ValueError): fn(changed)
        changed=copy.deepcopy(self.check); changed['manifest']['stage']='spec'
        with self.assertRaises(ValueError): fn(changed)

    def test_check_closed_fields_argv_timeout_and_hash_refuse(self):
        fn=self.validator('validate_group_check_request_shape')
        for key,value in (('argv',[]),('argv',[True]),('timeout_seconds',True),('timeout_seconds',3601),('extra',True)):
            changed=copy.deepcopy(self.check); changed['check'][key]=value
            changed['check_sha256']=digest_manifest(changed['check'])
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): fn(changed)
