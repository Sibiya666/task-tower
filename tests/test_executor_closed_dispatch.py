"""Registration never widens the native launch matrix of existing consumers."""
import unittest
import contextlib
import io
import json
from contextlib import nullcontext
from unittest.mock import Mock, patch

from task_tower import executor_harness as harness
from task_tower import pipeline_roles, pipeline
from task_tower import pipeline_worker, executor_worker
from task_tower.pipeline_policy import load_pipeline_config
from tests import test_pipeline_policy as policy_fixture
from tests import test_opencode_registration as registration_fixture


class ClosedInvocationTests(unittest.TestCase):
    def setUp(self):
        self.attempt = dict(request_path='request', result_path='result',
                            schema_path='schema', worktree='worktree')

    def profiles(self):
        for kind in ('opencode', 'unknown', None, [], {}, 1, True):
            yield dict(kind=kind, argv=['native-marker'], trusted=True)
        yield dict(argv=['native-marker'], trusted=True)

    def test_generic_builder_rejects_opencode_and_unknown_kinds(self):
        for profile in self.profiles():
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'Unsupported executor kind'):
                harness.build_invocation(self.attempt, profile)

    def test_role_builder_independently_rejects_unsupported_kinds(self):
        for role in sorted(harness.ROLE_NAMES):
            for profile in self.profiles():
                with self.subTest(role=role, profile=profile):
                    with patch.object(harness, 'build_invocation', side_effect=AssertionError('generic builder reached')):
                        with self.assertRaisesRegex(ValueError, 'Unsupported executor kind'):
                            harness.build_role_invocation(self.attempt, profile, role=role)

    def test_supported_argv_stays_exact(self):
        custom = dict(kind='custom', trusted=True, argv=['custom', 'fixed'])
        expected = ['custom', 'fixed', '--request', 'request', '--result', 'result']
        self.assertEqual(harness.build_invocation(self.attempt, custom), expected)
        for role in harness.ROLE_NAMES:
            self.assertEqual(harness.build_role_invocation(self.attempt, custom, role=role), expected)


class PipelineKindBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = policy_fixture.PipelinePolicyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.profile['kind'] = 'codex'

    def test_actual_pipeline_policy_rejects_registered_unsupported_profiles(self):
        f = self.fixture
        f.load()
        for kind in ('opencode', 'unknown', None, [], {}, True):
            f.profile['kind'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                load_pipeline_config(f.path, f.connections, f.executor)
        f.profile.pop('kind')
        with self.assertRaises(ValueError):
            load_pipeline_config(f.path, f.connections, f.executor)

    def test_all_six_actual_roles_stop_before_preparation(self):
        for role in sorted(harness.ROLE_NAMES):
            for kind in ('opencode', 'unknown', None, [], {}, True):
                with self.subTest(role=role, kind=kind):
                    run = dict(profile_id='local', manifest={})
                    binding = dict(role=role, manifest={}, artifact_names={})
                    config = dict(profiles={'local': dict(kind=kind)})
                    journal = Mock()
                    with patch.object(pipeline_roles, '_authority', return_value=({}, dict(kind=kind))), \
                         patch.object(pipeline_roles, '_snapshot', side_effect=AssertionError('snapshot/preparation reached')), \
                         patch.object(pipeline_roles, 'run_command', side_effect=AssertionError('native child reached')):
                        with self.assertRaisesRegex(ValueError, 'unsupported_kind'):
                            pipeline_roles.run_role(config, run, binding, role, journal, 'owner')
                    journal.begin_attempt.assert_not_called()

    def test_public_pipeline_entry_rejects_registry_before_admission_or_child(self):
        f = self.fixture
        f.load()
        f.profile['kind'] = 'opencode'
        connections, executor, request, result, journal = [f.root/name for name in
            ('connections.json', 'executor.json', 'request.json', 'result.json', 'pipeline.db')]
        for path in (connections, executor, request):
            path.write_text('{}')
        argv = ['adapter', '--connections', str(connections), '--executor-config', str(executor),
                '--config', str(f.path), '--journal', str(journal), '--request', str(request), '--result', str(result)]
        # Substitute only common registration, as if it already knew the new kind.
        # The real public entry and independent pipeline policy remain in use.
        with patch.object(pipeline, 'load_connections', return_value=f.connections), \
             patch.object(pipeline, 'load_executor_config', return_value=f.executor), \
             patch.object(pipeline, 'adapter', side_effect=AssertionError('admission reached')) as admit, \
             patch.object(pipeline_roles, 'run_command', side_effect=AssertionError('child reached')), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pipeline.main(argv), 2)
        admit.assert_not_called()
        self.assertFalse(journal.exists())
        self.assertFalse(result.exists())

    def test_actual_common_registration_cannot_enable_public_pipeline(self):
        f=self.fixture
        native=registration_fixture.OpenCodeRegistrationTests();native.setUp();self.addCleanup(native.doCleanups)
        native.profile['checkout']=str(f.connections[0].checkout)
        native.legacy.config['allowlist']=f.executor['allowlist']
        native.legacy.connections=f.connections
        registered=native.legacy.load()
        self.assertEqual(registered['profiles']['local']['kind'],'opencode')
        f.path.write_text(json.dumps(f.value))
        connections=f.root/'connections.json'
        connections.write_text(json.dumps(dict(version=1,projects=[dict(id='fixture',repository='Owner/Repo',
            checkout=str(f.connections[0].checkout),runner_label='local',trusted_publishers=['owner'])])))
        request=f.root/'request.json';request.write_text('{}')
        result=f.root/'result.json';journal=f.root/'pipeline.db'
        argv=['adapter','--connections',str(connections),'--executor-config',str(native.legacy.path),
              '--config',str(f.path),'--journal',str(journal),'--request',str(request),'--result',str(result)]
        with patch.object(pipeline,'adapter',side_effect=AssertionError('unsupported admission reached')) as admit, \
             patch.object(executor_worker,'run_command',side_effect=AssertionError('native child reached')), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pipeline.main(argv),2)
        admit.assert_not_called();self.assertFalse(journal.exists());self.assertFalse(result.exists())

    def test_direct_preparation_refuses_before_any_git_or_files(self):
        for kind in ('opencode', 'unknown', None, [], {}, True):
            with self.subTest(kind=kind):
                with patch.object(pipeline_worker, '_task', return_value={}), \
                     patch.object(pipeline_worker, '_git', side_effect=AssertionError('Git preparation reached')):
                    with self.assertRaisesRegex(ValueError, 'unsupported_kind'):
                        pipeline_worker._prepare(dict(profiles={'local': dict(kind=kind)}),
                            dict(profile_id='local', admission=None), Mock(), 'owner')

    def test_unqualified_foreground_kind_never_reaches_generic_preparation(self):
        for kind in ('opencode', 'unknown', None, [], {}, True):
            with self.subTest(kind=kind):
                queue = Mock()
                queue.owner.return_value = nullcontext()
                queue.claim.return_value = dict(run_id='r', profile_id='local')
                with patch.object(executor_worker, '_authorized', return_value=True), \
                     patch.object(executor_worker, 'prepare_attempt', side_effect=AssertionError('preparation reached')), \
                     patch.object(executor_worker, 'run_command', side_effect=AssertionError('child reached')):
                    result = executor_worker.execute_one(dict(profiles={'local': dict(kind=kind)}), queue)
                self.assertEqual(result['status'], 'needs_input')
                self.assertEqual(queue.record.call_args.args[3],
                                 dict(no_child_created=True, reason='unsupported_kind'))

    def test_revoked_foreground_profile_keeps_legacy_evidence_shape(self):
        queue = Mock()
        queue.owner.return_value = nullcontext()
        queue.claim.return_value = dict(run_id='r', profile_id='revoked')
        result = executor_worker.execute_one(dict(profiles={}), queue)
        self.assertEqual(result['status'], 'needs_input')
        self.assertEqual(queue.record.call_args.args[3], dict(no_child_created=True))
