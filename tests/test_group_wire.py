"""Pure closed wire shapes never establish a durable group/run authority."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from task_tower.pipeline_inputs import validate_stage_manifest, canonical_json
try:
    from task_tower.group_wire import EPOCH_FIELDS, validate_epoch_shape, group_stage_shape, validate_group_stage_shape
except ImportError:
    EPOCH_FIELDS=validate_epoch_shape=group_stage_shape=validate_group_stage_shape=None
try:
    from task_tower.group_wire import group_role_result_schema, validate_group_role_result_shape
except ImportError:
    group_role_result_schema=validate_group_role_result_shape=None
try:
    from task_tower.group_wire import validate_group_role_request_shape, validate_group_checks_shape
except ImportError:
    validate_group_role_request_shape=validate_group_checks_shape=None


class GroupStageShapeTests(unittest.TestCase):
    def setUp(self):
        self.epoch=dict(base_epoch=0,base_epoch_sha256='1'*64,scope_base_sha='2'*40,
            diff_base_sha='3'*40,accepted_main_proof_sha256=None,task_delta_sha256='4'*64)
        self.stage=dict(version=1,repository='owner/repo',issue=18,issue_id=1018,task_id='TT-GROUPS-001',
            run_id='00000000-0000-4000-8000-000000000018',stage='spec',generation=1,
            source_sha='a'*40,base_sha='b'*40,checkpoint_sha='c'*40,product_sha256='d'*64,
            criteria_sha256='e'*64,spec_sha256=None,plan_sha256=None,prior_verdict_sha256=None,
            policy_sha256='f'*64,superpowers_sha256='1'*64,checks_sha256=None)

    def available(self): self.assertIsNotNone(validate_epoch_shape,'Missing pure group wire shapes')

    def test_closed_epoch_shape_and_signed64_boundary(self):
        self.available()
        self.assertEqual(set(EPOCH_FIELDS),set(self.epoch))
        self.assertEqual(validate_epoch_shape(self.epoch),self.epoch)
        value=dict(self.epoch,base_epoch=2**63-1,accepted_main_proof_sha256='5'*64)
        self.assertEqual(validate_epoch_shape(value),value)
        for epoch in (True,False,-1,2**63,0.0,'0'):
            with self.subTest(epoch=epoch),self.assertRaises(ValueError): validate_epoch_shape(dict(value,base_epoch=epoch))

    def test_epoch_zero_nullable_is_shape_only_and_later_requires_proof(self):
        self.available()
        self.assertEqual(validate_epoch_shape(dict(self.epoch,accepted_main_proof_sha256='5'*64))['base_epoch'],0)
        with self.assertRaises(ValueError): validate_epoch_shape(dict(self.epoch,base_epoch=1))

    def test_missing_extra_and_invalid_digest_fields_refuse(self):
        self.available()
        for key in self.epoch:
            value=copy.deepcopy(self.epoch); value.pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError): validate_epoch_shape(value)
        for value in (dict(self.epoch,extra=True),dict(self.epoch,base_epoch_sha256='A'*64),
                dict(self.epoch,scope_base_sha='2'*64),dict(self.epoch,task_delta_sha256=True)):
            with self.assertRaises(ValueError): validate_epoch_shape(value)

    def test_legacy_stage_bytes_and_default_validator_stay_unchanged(self):
        self.available(); before=canonical_json(self.stage)
        self.assertEqual(validate_stage_manifest(self.stage),self.stage)
        group=group_stage_shape(self.stage,self.epoch)
        self.assertEqual(group['version'],2)
        self.assertEqual(set(group),set(self.stage)|set(self.epoch))
        self.assertEqual(canonical_json(self.stage),before)
        self.assertEqual(validate_group_stage_shape(group),group)
        with self.assertRaises(ValueError): validate_stage_manifest(group)
        with self.assertRaises(ValueError): validate_group_stage_shape(self.stage)

    def test_unknown_boolean_versions_and_mixed_shapes_refuse(self):
        self.available(); group=group_stage_shape(self.stage,self.epoch)
        for version in (True,False,0,1,3,'2',2.0):
            with self.subTest(version=version),self.assertRaises(ValueError):
                validate_group_stage_shape(dict(group,version=version))
        with self.assertRaises(ValueError): validate_group_stage_shape(dict(group,is_group=True))
        with self.assertRaises(ValueError): group_stage_shape(group,self.epoch)

    def test_later_checkpoint_can_bind_new_delta_within_same_epoch(self):
        self.available()
        first=group_stage_shape(self.stage,self.epoch)
        later=group_stage_shape(dict(self.stage,checkpoint_sha='9'*40,product_sha256='8'*64),
            dict(self.epoch,task_delta_sha256='7'*64))
        for key in set(self.epoch)-{'task_delta_sha256'}: self.assertEqual(first[key],later[key])
        self.assertNotEqual(first['task_delta_sha256'],later['task_delta_sha256'])
        self.assertEqual(validate_group_stage_shape(later),later)


class GroupRoleShapeTests(unittest.TestCase):
    def setUp(self):
        GroupStageShapeTests.setUp(self)
        self.binding=dict(run_id=self.stage['run_id'],attempt_id='00000000-0000-4000-8000-000000000001',
            instance_id='00000000-0000-4000-8000-000000000002',stage='development',generation=1,
            source_sha='a'*40,checkpoint_sha='b'*40,input_sha256='c'*64,**self.epoch)
        self.executor=dict(self.binding,version=3,status='completed',summary='Shape fixture only.')

    def available(self): self.assertIsNotNone(group_role_result_schema,'Missing explicit group role3 shape')

    def test_schema_and_result_version3_bind_every_epoch_field(self):
        self.available()
        schema=group_role_result_schema(self.binding,reviewer=False)
        self.assertEqual(schema['properties']['version']['const'],3)
        self.assertEqual(set(schema['required']),set(self.executor))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(validate_group_role_result_shape(self.executor,self.binding,reviewer=False),self.executor)
        for key in self.epoch:
            result=copy.deepcopy(self.executor); result[key]=1 if key=='base_epoch' else '0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_group_role_result_shape(result,self.binding,reviewer=False)

    def test_legacy_role2_file_parser_does_not_accept_group3(self):
        self.available()
        from task_tower.executor_harness import ROLE_BINDING, validate_role_result
        binding={key:self.binding[key] for key in ROLE_BINDING}
        legacy=dict(binding,version=2,status='completed',summary='Shape fixture only.')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'result.json'; path.write_text(json.dumps(legacy),encoding='utf-8')
            self.assertEqual(validate_role_result(path,binding,reviewer=False),legacy)
            path.write_text(json.dumps(self.executor),encoding='utf-8')
            with self.assertRaises(ValueError): validate_role_result(path,binding,reviewer=False)
        with self.assertRaises(ValueError): validate_group_role_result_shape(legacy,self.binding,reviewer=False)

    def test_reviewer_routes_findings_and_paths_keep_existing_rules(self):
        self.available()
        result=dict(self.binding,version=3,verdict='reject',summary='Shape fixture only.',return_stage='development',
            findings=[dict(code='product_defect',path='src/file.py',line=1)])
        self.assertEqual(validate_group_role_result_shape(result,self.binding,reviewer=True),result)
        for change in ('route','path','line','extra'):
            value=copy.deepcopy(result)
            if change=='route': value['return_stage']='test'
            elif change=='path': value['findings'][0]['path']='../outside'
            elif change=='line': value['findings'][0]['line']=True
            else: value['findings'][0]['extra']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_group_role_result_shape(value,self.binding,reviewer=True)

    def test_boolean_unknown_missing_and_extra_fields_refuse(self):
        self.available()
        for version in (True,2,4,'3',3.0):
            with self.subTest(version=version),self.assertRaises(ValueError):
                validate_group_role_result_shape(dict(self.executor,version=version),self.binding,reviewer=False)
        with self.assertRaises(ValueError): validate_group_role_result_shape(dict(self.executor,is_group=True),self.binding,reviewer=False)
        bad=copy.deepcopy(self.binding); bad['base_epoch']=False
        with self.assertRaises(ValueError): group_role_result_schema(bad,reviewer=False)
        bad=copy.deepcopy(self.executor); bad.pop('task_delta_sha256')
        with self.assertRaises(ValueError): validate_group_role_result_shape(bad,self.binding,reviewer=False)


class GroupRequestShapeTests(unittest.TestCase):
    def setUp(self):
        GroupRoleShapeTests.setUp(self)
        from task_tower.pipeline_inputs import digest_manifest
        self.manifest=group_stage_shape(dict(self.stage,stage='development'),self.epoch)
        self.binding.update(checkpoint_sha=self.manifest['checkpoint_sha'],input_sha256=digest_manifest(self.manifest))
        self.request=dict(version=3,role='development_executor',binding=self.binding,manifest=self.manifest,
            worktree=str(Path(tempfile.gettempdir()).resolve()/'shape-worktree'),instructions={},
            host_task_policy=dict(spec_path='docs/spec.md',plan_path='docs/plan.md',allowed_paths=['src/','docs/'],evidence_dir='docs/evidence/'),
            task_data={},task_data_trust='untrusted',checks=[],host_checks=None,
            ci_substitution=dict(policy=dict(enabled=False,required_platforms=[]),evidence=None,unavailable_reason=None),
            obligations=['Shape fixture only; no launch authority.'],**self.epoch)

    def available(self): self.assertIsNotNone(validate_group_role_request_shape,'Missing pure group request3 shape')

    def test_group_request3_closes_outer_fields_and_nested_epoch_input(self):
        self.available()
        self.assertEqual(validate_group_role_request_shape(self.request),self.request)
        for change in ('outer','binding','manifest','input','role','extra','version'):
            value=copy.deepcopy(self.request)
            if change=='outer': value['task_delta_sha256']='0'*64
            elif change=='binding': value['binding']['scope_base_sha']='0'*40
            elif change=='manifest': value['manifest']['base_epoch_sha256']='0'*64
            elif change=='input': value['binding']['input_sha256']='0'*64
            elif change=='role': value['role']='test_reviewer'
            elif change=='extra': value['is_group']=True
            else: value['version']=2
            with self.subTest(change=change),self.assertRaises(ValueError): validate_group_role_request_shape(value)

    def test_host_check_aggregate2_preserves_individual_row_without_epoch_fields(self):
        self.available(); self.assertIsNotNone(validate_group_checks_shape)
        aggregate=dict(version=2,checkpoint_sha=self.manifest['checkpoint_sha'],product_sha256=self.manifest['product_sha256'],
            policy_sha256=self.manifest['policy_sha256'],execution_local=True,checks=[],**self.epoch)
        self.assertEqual(validate_group_checks_shape(aggregate),aggregate)
        for change in ('version','epoch','extra','execution'):
            value=copy.deepcopy(aggregate)
            if change=='version': value['version']=True
            elif change=='epoch': value['base_epoch']=True
            elif change=='extra': value['unknown']=True
            else: value['execution_local']=1
            with self.subTest(change=change),self.assertRaises(ValueError): validate_group_checks_shape(value)

    def test_request_host_checks_must_match_its_exact_stage_hash_and_epoch(self):
        self.available()
        from task_tower.pipeline_inputs import digest_manifest
        value=copy.deepcopy(self.request);value['role']='test_reviewer'
        value['binding']['stage']='test';value['manifest']['stage']='test'
        checks=dict(version=2,checkpoint_sha=value['manifest']['checkpoint_sha'],product_sha256=value['manifest']['product_sha256'],
            policy_sha256=value['manifest']['policy_sha256'],execution_local=True,checks=[],**self.epoch)
        value['host_checks']=checks;value['manifest']['checks_sha256']=digest_manifest(checks)
        value['binding']['input_sha256']=digest_manifest(value['manifest'])
        self.assertEqual(validate_group_role_request_shape(value),value)
        value['host_checks']['task_delta_sha256']='0'*64
        with self.assertRaises(ValueError): validate_group_role_request_shape(value)

    def test_individual_check_rows_keep_actual_unversioned_fields(self):
        self.available()
        row=dict(id='unit',check_sha256='1'*64,status='passed',exit_code=0,started=True,
            cleanup_confirmed=True,source_unchanged=True,duration_seconds=0.5)
        for stream in ('stdout','stderr'):
            row.update({stream+'_sha256':'2'*64,stream+'_bytes':0,stream+'_captured_bytes':0,
                stream+'_truncated':False,stream+'_tail_unknown':False})
        aggregate=dict(version=2,checkpoint_sha=self.manifest['checkpoint_sha'],product_sha256=self.manifest['product_sha256'],
            policy_sha256=self.manifest['policy_sha256'],execution_local=True,checks=[row],**self.epoch)
        before=copy.deepcopy(row)
        self.assertEqual(validate_group_checks_shape(aggregate),aggregate)
        self.assertEqual(row,before)
        for change in ('version','extra','epoch','duration','duration_overflow','integer_bool','capture'):
            value=copy.deepcopy(aggregate); check=value['checks'][0]
            if change=='version': check['version']=2
            elif change=='extra': check['unknown']=True
            elif change=='epoch': check['base_epoch']=0
            elif change=='duration': check['duration_seconds']=-1
            elif change=='duration_overflow': check['duration_seconds']=10**400
            elif change=='integer_bool': check['exit_code']=False
            else: check['stdout_captured_bytes']=1
            with self.subTest(change=change),self.assertRaises(ValueError): validate_group_checks_shape(value)

    def test_ci_policy_keeps_actual_closed_config_types_and_platform_rules(self):
        self.available()
        for policy in ({'enabled':'false','required_platforms':[]},{'enabled':False,'required_platforms':[],'extra':True},
                {'enabled':True,'required_platforms':[]},{'enabled':False,'required_platforms':['windows']},
                {'enabled':True,'required_platforms':['windows','windows']},{'enabled':True,'required_platforms':['unknown']}):
            value=copy.deepcopy(self.request); value['ci_substitution']['policy']=policy
            with self.subTest(policy=policy),self.assertRaises(ValueError): validate_group_role_request_shape(value)
