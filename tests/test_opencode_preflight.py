"""Pre-probe metadata gates; no test provisions or invokes a native harness."""
import copy
import hashlib
import os
from pathlib import Path
import unittest
import uuid
from contextlib import nullcontext
from unittest.mock import Mock
from unittest.mock import patch

from task_tower import executor_harness, executor_profiles, executor_worker
from task_tower import opencode_adapter as adapter
from tests import test_opencode_registration as registration_fixture
from tests import test_opencode_templates as template_fixture
from task_tower import opencode_discovery as discovery


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.f=registration_fixture.OpenCodeRegistrationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.profile=self.f.legacy.load()['profiles']['local']
        run,attempt=str(uuid.uuid4()),str(uuid.uuid4())
        self.attempt=dict(run_id=run,attempt_id=attempt,source_sha='a'*40,
            worktree=str(Path(self.profile['runs_dir'])/run/attempt/'worktree'),
            profile_fingerprint=executor_profiles.profile_fingerprint(self.profile))

    def test_false_native_permission_stops_before_git_or_runner(self):
        with patch.object(executor_worker,'_git',side_effect=AssertionError('Git preparation reached')), \
             patch.object(executor_worker,'run_command',side_effect=AssertionError('native child reached')):
            result=adapter.verify_opencode_preflight(self.profile,attempt=self.attempt,environ={})
        self.assertFalse(result['allowed'])
        self.assertTrue(result['no_child_created'])
        self.assertIn('native_launch_not_authorized',result['reasons'])

    def test_probe_permission_is_separate_and_false_denies(self):
        self.f.policy.policy['native_launch_authorized']=True
        self.f.policy.validate()
        self.profile=self.f.legacy.load()['profiles']['local']
        self.attempt['profile_fingerprint']=executor_profiles.profile_fingerprint(self.profile)
        with patch.object(executor_worker,'_git',side_effect=AssertionError('Git reached')):
            result=adapter.verify_opencode_preflight(self.profile,attempt=self.attempt,environ={})
        self.assertIn('native_probe_not_authorized',result['reasons'])

    def test_profile_or_policy_drift_does_not_reach_probe(self):
        drift=copy.deepcopy(self.profile);drift['argv']=['changed']
        with patch.object(executor_worker,'run_command',side_effect=AssertionError('native child reached')):
            result=adapter.verify_opencode_preflight(drift,attempt=self.attempt,environ={})
        self.assertIn('profile_binding_mismatch',result['reasons'])
        self.f.policy.evidence_path.write_bytes(self.f.policy.evidence_path.read_bytes()+b' ')
        result=adapter.verify_opencode_preflight(self.profile,attempt=self.attempt,environ={})
        self.assertIn('invalid_policy_evidence',result['reasons'])

    def test_registered_version_is_not_observed_version_or_run_authority(self):
        self.assertEqual(self.profile['opencode']['version'],'2.2.5')
        capabilities=executor_harness.capabilities(self.profile)
        self.assertFalse(capabilities['probed'])
        self.assertFalse(capabilities['verified'])
        self.assertFalse(capabilities['events'])
        self.assertFalse(capabilities['resume'])

    @unittest.skipUnless(os.name=='nt','current native pre-probe gate is Windows-only')
    def test_probe_only_metadata_success_does_not_grant_a_native_run(self):
        # Source/system discovery is isolated as a synthetic contract fixture.
        # Git source, fresh worktree, IDs, pins, bytes and policy reads are real.
        d=template_fixture.ActualTemplateObservationTests();d.setUp();self.addCleanup(d.doCleanups)
        root=d.f
        checkout=Path(self.f.legacy.profile['checkout'])
        git=executor_worker._git
        git(checkout,'init','-b','main')
        git(checkout,'config','core.autocrlf','false')
        (checkout/'AGENTS.md').write_bytes(d.data)
        git(checkout,'add','AGENTS.md')
        git(checkout,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','source fixture')
        source=git(checkout,'rev-parse','HEAD')
        tree=root.runs/str(uuid.uuid4())/str(uuid.uuid4())/'worktree'
        tree.parent.mkdir(parents=True)
        git(checkout,'worktree','add','--detach',str(tree),source)
        self.addCleanup(lambda:git(checkout,'worktree','remove','--force',str(tree)))
        observed=d.collect(tree)
        self.assertTrue(observed['complete'],observed['reasons'])
        expected=d.expected(observed)
        expected['scope']['source_sha']=source
        next(row for row in expected['inventory'] if row['kind']=='worktree_template')['source_sha']=source
        child=discovery.opencode_environment(root.env,str(tree))
        expected['environment']=discovery.environment_binding(child,'windows')
        p=self.f.policy
        p.evidence.update(scope=expected['scope'],inventory=expected['inventory'],environment=expected['environment'])
        p.evidence['qualification'].update(native_probe_authorized=True,native_run_authorized=False)
        p.policy['native_launch_authorized']=True;p.validate()
        self.f.legacy.profile['runs_dir']=str(root.runs)
        profile=self.f.legacy.load()['profiles']['local']
        attempt=dict(run_id=tree.parent.parent.name,attempt_id=tree.parent.name,worktree=str(tree),source_sha=source,
                     profile_fingerprint=executor_profiles.profile_fingerprint(profile))
        parents=lambda current:[current,*[parent for parent in current.parents if parent.is_relative_to(root.root)]]
        with patch.object(discovery,'_roots',return_value=d.roots),patch.object(discovery,'_ancestors',side_effect=parents), \
             patch.object(executor_worker,'run_command',side_effect=AssertionError('native child reached')):
            result=adapter.verify_opencode_preflight(profile,attempt=attempt,environ=root.env)
        self.assertTrue(result['allowed'],result.get('reasons'))
        self.assertEqual(result['environment']['PWD'],str(tree))
        self.assertFalse(p.evidence['qualification']['native_run_authorized'])
        self.assertFalse(executor_harness.capabilities(profile)['probed'])
        queue=Mock();queue.owner.return_value=nullcontext();queue.claim.return_value=dict(run_id=attempt['run_id'],profile_id='local')
        with patch.object(executor_worker,'run_command',side_effect=AssertionError('metadata became native run')):
            self.assertEqual(executor_worker.execute_one(dict(profiles={'local':profile}),queue)['status'],'needs_input')
        self.assertTrue(queue.record.call_args.args[3]['no_child_created'])
