"""Actual existing registration and same-process observations, no claims."""
import hashlib
import json
import os
import time
import sys
import uuid
from pathlib import Path
import unittest
from unittest.mock import patch
from task_tower import group_resources
from task_tower.pipeline_inputs import digest_manifest
import test_group_registration as registration_fixture


class GroupResourceObservationTests(unittest.TestCase):
    def setUp(self):
        self.f=registration_fixture.RegistrationContextTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.seed(); self.reg=self.f.load(); self.reg.__enter__(); self.addCleanup(self.reg.__exit__,None,None,None)
        self.f.j.register_groups(self.reg)

    def context(self):
        factory=getattr(group_resources,'ResourceContext',None)
        self.assertTrue(callable(factory),'Missing genuine resource host context')
        return factory.from_registration(self.reg)

    def sample(self,context):
        fn=getattr(group_resources,'observe_host',None)
        self.assertTrue(callable(fn),'Missing genuine host observation')
        return fn(context,deadline=time.monotonic()+2)

    def test_actual_native_or_unsupported_observation_is_closed_readonly_and_context_bound(self):
        context=self.context(); before=hashlib.sha256(self.f.j.path.read_bytes()).hexdigest()
        body=self.sample(context)
        self.assertEqual(set(body),{'version','observation_id','installation_id','policy_epoch','boot_id','process_id',
            'monotonic_ns','observed_at','expires_monotonic_ns','platform','cpu_millis','available_memory_bytes',
            'limitations','harness_pools','provenance','status','reason'})
        self.assertEqual(body['process_id'],os.getpid()); self.assertEqual(body['installation_id'],self.reg.policy['installation_id'])
        self.assertLessEqual(body['expires_monotonic_ns']-body['monotonic_ns'],5_000_000_000)
        self.assertEqual(body['policy_epoch'],self.f.j.registered_groups()['current_capacity_epoch'])
        self.assertIn(body['status'],('available','fallback','unavailable'))
        if os.name!='nt':
            self.assertEqual(body['status'],'unavailable'); self.assertEqual(body['reason'],'platform_unsupported')
        self.assertEqual(before,hashlib.sha256(self.f.j.path.read_bytes()).hexdigest())

    def test_imported_json_and_changed_public_dictionary_do_not_install_or_mutate_sample(self):
        context=self.context(); body=self.sample(context); original=digest_manifest(body)
        body['cpu_millis']=2**63-1
        resolve=getattr(group_resources,'_current_observation',None); self.assertTrue(callable(resolve))
        retained=resolve(context,original)
        self.assertNotEqual(retained['cpu_millis'],body['cpu_millis'])
        with self.assertRaises(ValueError): resolve(context,digest_manifest(body))
        with self.assertRaises(ValueError): resolve(context,body)
        with self.assertRaises(ValueError): group_resources.observe_host(dict(self.reg.policy),deadline=time.monotonic()+2)

    def test_foreign_process_stale_and_raw_policy_revocation_refuse_current_sample(self):
        context=self.context(); body=self.sample(context); digest=digest_manifest(body)
        with patch('task_tower.group_resources.os.getpid',return_value=os.getpid()+1000000),self.assertRaises(ValueError):
            group_resources._current_observation(context,digest)
        with patch('task_tower.group_resources.time.monotonic_ns',return_value=body['expires_monotonic_ns']),self.assertRaises(ValueError):
            group_resources._current_observation(context,digest)
        path=self.reg.groups_path; raw=path.read_bytes()
        try:
            path.write_bytes(raw+b' ')
            with self.assertRaises(ValueError): group_resources._current_observation(context,digest)
        finally: path.write_bytes(raw)

    def test_closed_context_and_non_typed_factory_input_refuse_before_probe(self):
        context=self.context()
        with self.assertRaises(ValueError): group_resources.ResourceContext.from_registration(dict(self.reg.policy))
        self.reg.close()
        with self.assertRaises(ValueError): self.sample(context)

    def test_new_actual_process_cannot_reuse_parent_sample_or_restore_it_from_journal(self):
        from task_tower.processes import run_command
        from task_tower.executor_profiles import child_environment
        context=self.context(); body=self.sample(context); before=self.f.j.path.read_bytes()
        registration=self.reg
        argv=[str(Path(sys.executable).resolve()),'-B',str(Path(__file__).parent/'fixtures/group_resource_observer.py'),
            *map(str,(registration.groups_path,registration.connections_path,registration.pipeline_path,
                registration.executor_path,self.f.j.path)),digest_manifest(body)]
        capture=self.f.f.root/'resource-child-capture'; capture.mkdir()
        env=child_environment(os.environ); env['PYTHONPATH']=str(Path(__file__).resolve().parent.parent)
        result=run_command(argv,Path(__file__).resolve().parent.parent,20,env=env,
            capture=dict(directory=capture,max_bytes_per_stream=65536))
        self.assertEqual(result['status'],'passed',result); self.assertEqual(result['exit_code'],0)
        self.assertTrue(result['started']); self.assertGreater(result['pid'],0); self.assertNotEqual(result['pid'],os.getpid())
        self.assertTrue(result['cleanup_confirmed'])
        for stream in ('stdout','stderr'):
            self.assertFalse(result[stream+'_tail_unknown']); self.assertFalse(result[stream+'_truncated'])
        self.assertEqual(json.loads((capture/'stdout.log').read_text()),dict(reused=False))
        self.assertEqual(before,self.f.j.path.read_bytes())

    def test_huge_finite_deadline_never_extends_five_second_sample_lifetime(self):
        context=self.context()
        body=group_resources.observe_host(context,deadline=1e300)
        self.assertLessEqual(body['expires_monotonic_ns']-body['monotonic_ns'],5_000_000_000)
        for value in (True,float('inf'),float('nan'),2**10000):
            with self.subTest(value=type(value).__name__),self.assertRaises(ValueError):
                group_resources.observe_host(context,deadline=value)

    def test_other_collector_lifetime_and_other_context_cannot_reuse_sample(self):
        context=self.context(); body=self.sample(context); digest=digest_manifest(body)
        with patch('task_tower.group_resources._COLLECTOR_LIFETIME',str(uuid.uuid4())),self.assertRaises(ValueError):
            group_resources._current_observation(context,digest)
        with self.assertRaises(ValueError): group_resources._current_observation(self.context(),digest)

    def test_actual_sample_registry_is_bounded_without_trusting_persisted_rows(self):
        context=self.context(); first=group_resources.observe_host(context,deadline=1e300)
        for _ in range(34): group_resources.observe_host(context,deadline=1e300)
        self.assertLessEqual(len(group_resources._SAMPLES),32)
        with self.assertRaises(ValueError): group_resources._current_observation(context,digest_manifest(first))

    def explicit_fallback(self):
        self.reg.close(); path=self.reg.groups_path
        raw=json.loads(path.read_text(encoding='utf-8'))
        raw['capacity']=dict(mode='auto',max_executors=2,max_inflight=None,max_cpu_millis=None,max_memory_bytes=None,
            fallback=dict(cpu_millis=8000,memory_bytes=8*1024**3,max_executors=3))
        path.write_text(json.dumps(raw),encoding='utf-8')
        self.reg=self.f.load(); self.reg.__enter__(); self.addCleanup(self.reg.__exit__,None,None,None)
        result=self.f.j.register_groups(self.reg)
        self.assertEqual(result['status'],'capacity_only')

    def test_owned_explicit_fallback_labels_raw_unknown_without_raising_known_memory(self):
        self.explicit_fallback(); context=self.context(); before=self.f.j.path.read_bytes()
        # Sensor fault/composition fixture only: actual private loaders,
        # registration and capacity epoch remain genuine; no claim is made.
        with patch('task_tower.group_resources.sys.platform','win32'),patch('task_tower.group_resources._windows_probe',
                return_value=(None,2*1024**3,['cpu_measurement_unavailable'],dict(memory=dict(available_physical=2*1024**3)))):
            body=self.sample(context)
        self.assertEqual(body['status'],'fallback'); self.assertIsNone(body['cpu_millis'])
        self.assertEqual(body['available_memory_bytes'],2*1024**3)
        self.assertEqual(body['provenance']['fallback_fields'],['cpu_millis'])
        budget=group_resources.resource_budget(body['cpu_millis'],body['available_memory_bytes'],self.reg.policy['capacity'])
        self.assertEqual(budget['memory_bytes'],1024**3); self.assertEqual(budget['max_executors'],2)
        self.assertEqual(before,self.f.j.path.read_bytes())

    def test_probe_deadline_never_becomes_positive_via_explicit_fallback(self):
        self.explicit_fallback(); context=self.context()
        with patch('task_tower.group_resources.sys.platform','win32'),patch('task_tower.group_resources._windows_probe',
                side_effect=group_resources._ProbeDeadline('Controlled probe expiry')):
            body=self.sample(context)
        self.assertEqual(body['status'],'unavailable'); self.assertEqual(body['reason'],'resource_unavailable')
        self.assertEqual(body['provenance']['fallback_fields'],[])
