"""Closed checkpoint/evidence syntax grants no producer or epoch authority."""
import copy
import unittest
from task_tower import group_wire
from task_tower.pipeline_inputs import digest_manifest


class GroupCheckpointWireTests(unittest.TestCase):
    def setUp(self):
        self.epoch=dict(base_epoch=0,base_epoch_sha256='1'*64,scope_base_sha='2'*40,
            diff_base_sha='3'*40,accepted_main_proof_sha256=None,task_delta_sha256='4'*64)
        self.manifest=dict(version=1,files=[dict(path='src/a.py',mode='100644',
            scheme='sha256-bytes-v1',sha256='5'*64)])
        self.checkpoint=dict(version=2,**self.epoch,source_sha='a'*40,base_sha='b'*40,
            checkpoint_sha='c'*40,product_sha256=digest_manifest(self.manifest),manifest=self.manifest,
            evidence_manifest_sha256=None,spec_sha256=None,plan_sha256=None)
        self.evidence=dict(version=2,**self.epoch,run_id='00000000-0000-4000-8000-000000000018',
            task_id='TT-GROUPS-001',product_sha256=self.checkpoint['product_sha256'],
            files=[dict(path='docs/evidence/spec.md',scheme='sha256-utf8-lf-v2',sha256='6'*64)])

    def validator(self,name):
        value=getattr(group_wire,name,None)
        self.assertTrue(callable(value),'Missing closed group checkpoint/evidence syntax')
        return value

    def test_actual_named_shapes_preserve_product_manifest1_and_input_bytes(self):
        before=copy.deepcopy((self.checkpoint,self.evidence))
        self.assertEqual(self.validator('validate_group_checkpoint_shape')(self.checkpoint),self.checkpoint)
        self.assertEqual(self.validator('validate_group_evidence_shape')(self.evidence),self.evidence)
        self.assertEqual(before,(self.checkpoint,self.evidence))
        self.assertEqual(self.checkpoint['manifest']['version'],1)

    def test_closed_fields_versions_epoch_and_product_hash_refuse(self):
        validate=self.validator('validate_group_checkpoint_shape')
        for key,value in (('version',True),('version',1),('base_epoch',True),
                ('accepted_main_proof_sha256','a'*40),('product_sha256','0'*64),('extra',True)):
            with self.subTest(key=key),self.assertRaises(ValueError): validate(dict(self.checkpoint,**{key:value}))
        for key in self.checkpoint:
            changed=dict(self.checkpoint); changed.pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError): validate(changed)

    def test_product_modes_schemes_paths_and_case_aliases_refuse(self):
        validate=self.validator('validate_group_checkpoint_shape')
        for field,value in (('mode','120000'),('scheme','sha256'),('path','../a'),('path','src/')):
            changed=copy.deepcopy(self.checkpoint); changed['manifest']['files'][0][field]=value
            changed['product_sha256']=digest_manifest(changed['manifest'])
            with self.subTest(field=field,value=value),self.assertRaises(ValueError): validate(changed)
        changed=copy.deepcopy(self.checkpoint)
        changed['manifest']['files'].append(dict(changed['manifest']['files'][0],path='SRC/a.py'))
        changed['product_sha256']=digest_manifest(changed['manifest'])
        with self.assertRaises(ValueError): validate(changed)

    def test_evidence_requires_actual_text_scheme_and_closed_entries(self):
        validate=self.validator('validate_group_evidence_shape')
        for field,value in (('scheme','sha256-bytes-v1'),('sha256','A'*64),('path','../x'),('extra',True)):
            changed=copy.deepcopy(self.evidence); changed['files'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): validate(changed)
        with self.assertRaises(ValueError): validate(dict(self.evidence,version=1))
        with self.assertRaises(ValueError): validate(dict(self.evidence,base_epoch=1))
