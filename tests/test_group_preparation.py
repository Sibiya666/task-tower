"""Actual existing registration/runtime/source context before a resource claim."""
import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from tests import test_group_registration as registration
from tests import test_group_graph as graph_fixture
from tests.test_pipeline_journal import request


class PreparationContextTests(unittest.TestCase):
    setUp=registration.RegistrationContextTests.setUp
    load=registration.RegistrationContextTests.load
    seed=registration.RegistrationContextTests.seed

    def test_original_deadline_expiring_during_collection_refuses_further_reads(self):
        import time
        _,transport=self.actual_source();self.seed()
        from task_tower.group_preparation import PreparationContext
        with self.load() as ctx:
            self.j.register_groups(ctx)
            req=dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')
            self.j.submit_group(req,context=ctx);before=self.j.path.read_bytes()
            now=[time.monotonic()];calls=[]
            def exhausted(*args,**kwargs):
                calls.append(args)
                value=transport(*args,**kwargs)
                now[0]=ctx.deadline+1
                return value
            with patch('task_tower.source_deadline.time.monotonic',side_effect=lambda:now[0]),patch('task_tower.github_tasks._transport',side_effect=exhausted),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                with self.assertRaises(ValueError):PreparationContext.from_registration(ctx)
            self.assertEqual(len(calls),1)
            self.assertEqual(self.j.path.read_bytes(),before)

    def actual_source(self):
        def git(*args):return subprocess.check_output(['git','-C',str(self.f.checkout),*args],stderr=subprocess.DEVNULL).decode().strip()
        git('init','-b','main')
        for name in ('docs/spec.md','docs/plan.md'):
            p=self.f.checkout/name;p.parent.mkdir(exist_ok=True);p.write_text('Initial source artifact.\n')
        git('add','docs');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','initial source')
        git('remote','add','origin','https://github.com/Owner/Repo.git')
        sha=git('rev-parse','HEAD')
        http=graph_fixture.Transport('Owner/Repo',[graph_fixture.issue(18,task_id='TT-GROUPS-001')])
        def transport(method,url,headers,payload=None,limit=None):
            if url.endswith('/git/ref/heads/main'):
                if method!='GET':raise AssertionError('Source mutation')
                return json.dumps(dict(object=dict(sha=sha))).encode()
            return http.request(method,url,headers,payload,limit)
        return sha,transport

    def test_factory_uses_genuine_runtime_admission_without_claim_or_journal_mutation(self):
        sha,transport=self.actual_source();self.seed()
        self.assertIsNotNone(importlib.util.find_spec('task_tower.group_preparation'),'Missing actual preparation context')
        from task_tower.group_preparation import PreparationContext
        with self.load() as ctx:
            self.j.register_groups(ctx)
            req=dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')
            receipt=self.j.submit_group(req,context=ctx);before=self.j.path.read_bytes()
            with patch('task_tower.github_tasks._transport',side_effect=transport),patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:transport('GET',url,headers,limit=limit)),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                prepared=PreparationContext.from_registration(ctx)
                rows=prepared.candidates()
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['run_id'],receipt['receipt_id'])
            self.assertEqual(rows[0]['source_admission']['source_sha'],sha)
            self.assertEqual(rows[0]['source_admission']['base_sha'],sha)
            self.assertEqual(rows[0]['issue_id'],1018)
            self.assertEqual(rows[0]['source_policy_sha256'],ctx.policy['_pipeline_config']['policy_sha256'])
            rows[0]['source_admission']['source_sha']='f'*40
            self.assertEqual(prepared.candidates()[0]['source_admission']['source_sha'],sha)
            raw=self.f.pipeline_path.read_bytes()
            try:
                self.f.pipeline_path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError):prepared.candidates()
            finally:self.f.pipeline_path.write_bytes(raw)
            self.assertEqual(self.j.path.read_bytes(),before)
        self.assertEqual(self.j.status(receipt['receipt_id'])['state'],'queued')

    def test_arbitrary_context_never_reaches_source_or_creates_execution(self):
        self.seed()
        from task_tower.group_preparation import PreparationContext
        before=self.j.path.read_bytes()
        with patch('task_tower.github_tasks._transport',side_effect=AssertionError('Unbound source poll')):
            for value in (None,{},dict(journal=self.j,policy=self.f.value)):
                with self.assertRaises(ValueError):PreparationContext.from_registration(value)
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_fresh_source_rejects_stale_pinned_main_without_rebinding(self):
        sha,transport=self.actual_source();self.seed()
        from task_tower.group_preparation import PreparationContext
        def changed(method,url,headers,payload=None,limit=None):
            if url.endswith('/git/ref/heads/main'):return json.dumps(dict(object=dict(sha='d'*40))).encode()
            return transport(method,url,headers,payload,limit)
        with self.load() as ctx:
            self.j.register_groups(ctx)
            req=dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')
            receipt=self.j.submit_group(req,context=ctx);before=self.j.path.read_bytes()
            with patch('task_tower.github_tasks._transport',side_effect=changed),patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:changed('GET',url,headers,limit=limit)),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                self.assertEqual(PreparationContext.from_registration(ctx).candidates(),[])
            self.assertEqual(self.j.path.read_bytes(),before)
        row=self.j.status(receipt['receipt_id']);self.assertIsNone(row['source_sha']);self.assertIsNone(row['owner_id'])
        self.assertEqual(subprocess.check_output(['git','-C',str(self.f.checkout),'rev-parse','HEAD']).decode().strip(),sha)

    def test_mutable_pipeline_copy_cannot_supply_source_authority(self):
        sha,transport=self.actual_source();self.seed()
        from task_tower.group_preparation import PreparationContext
        with self.load() as ctx:
            self.j.register_groups(ctx)
            req=dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')
            self.j.submit_group(req,context=ctx);expected=ctx.policy['_pipeline_config']['policy_sha256']
            ctx.pipeline=copy.deepcopy(ctx.pipeline);ctx.pipeline['policy_sha256']='f'*64
            with patch('task_tower.github_tasks._transport',side_effect=transport),patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:transport('GET',url,headers,limit=limit)),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                candidates=PreparationContext.from_registration(ctx).candidates()
            self.assertEqual(candidates[0]['source_policy_sha256'],expected)
            self.assertEqual(candidates[0]['source_admission']['source_sha'],sha)

    def test_actual_capacity_epoch_keeps_original_binding_and_current_source_policy(self):
        sha,transport=self.actual_source();self.seed()
        from task_tower.group_preparation import PreparationContext
        with self.load() as ctx:
            self.j.register_groups(ctx)
            req=dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')
            receipt=self.j.submit_group(req,context=ctx)
            original_policy=ctx.policy['_pipeline_config']['policy_sha256']
        raw=json.loads(self.f.pipeline_path.read_text());raw['capacity']=dict(max_executors=3,max_inflight=None)
        self.f.pipeline_path.write_text(json.dumps(raw))
        with self.load() as ctx:
            self.assertEqual(self.j.register_groups(ctx)['status'],'capacity_only')
            with patch('task_tower.github_tasks._transport',side_effect=transport),patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:transport('GET',url,headers,limit=limit)),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                prepared=PreparationContext.from_registration(ctx);rows=prepared.candidates()
            self.assertEqual(len(rows),1);self.assertNotEqual(rows[0]['source_policy_sha256'],original_policy)
            self.assertEqual(rows[0]['source_admission']['policy_sha256'],rows[0]['source_policy_sha256'])
            self.assertEqual(self.j.status(receipt['receipt_id'])['policy_sha256'],original_policy)
            self.assertTrue(callable(getattr(prepared,'initial_admission',None)),'Missing actual group admission2 producer')
            admission=prepared.initial_admission(receipt['receipt_id'])
            self.assertEqual(admission['version'],2);self.assertEqual(admission['policy_sha256'],original_policy)
            self.assertEqual(admission['source_policy_sha256'],rows[0]['source_policy_sha256'])
            self.assertEqual(admission['capacity_epoch'],2)
            self.assertEqual(admission['group_binding_sha256'],rows[0]['queued_group_binding_sha256'])
            self.assertNotEqual(rows[0]['queued_group_binding_sha256'],rows[0]['current_group_binding_sha256'])

    def test_new_registration_authority_cannot_reauthorize_an_original_queue_binding(self):
        sha,transport=self.actual_source();self.seed()
        from task_tower.group_preparation import PreparationContext
        with self.load() as ctx:
            self.j.register_groups(ctx)
            self.j.submit_group(dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local'),context=ctx)
        # Real private task scope changes, followed by actual explicit stopped
        # registration, never retroactively authorize the original queued task.
        raw=json.loads(self.f.pipeline_path.read_text());raw['tasks'][0]['allowed_paths'].append('extra/')
        self.f.pipeline_path.write_text(json.dumps(raw))
        with self.load() as ctx:
            self.assertEqual(self.j.register_groups(ctx)['status'],'authorization_change')
            with patch('task_tower.github_tasks._transport',side_effect=transport),patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:transport('GET',url,headers,limit=limit)),patch('task_tower.github_source.resolve_token',return_value=None),patch('task_tower.github_tasks.resolve_token',return_value=None):
                self.assertEqual(PreparationContext.from_registration(ctx).candidates(),[])
