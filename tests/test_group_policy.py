"""Pure policy boundaries: routing never supplies execution or acceptance proof."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from task_tower.executor_profiles import load_executor_config, profile_fingerprint

from task_tower import group_policy


ROLES = ('spec_executor', 'spec_reviewer', 'development_executor',
         'development_reviewer', 'test_executor', 'test_reviewer')


class GroupPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        self.pins = self.root / 'skills'
        self.pins.mkdir()
        (self.pins / 'SKILL.md').write_bytes(b'accepted instructions\r\n')
        manifest = {'SKILL.md': hashlib.sha256(b'accepted instructions\n').hexdigest()}
        raw_profile = dict(kind='custom', repository='Owner/Repo', checkout=str(self.checkout),
            runner_label='local', argv=[str(Path(sys.executable).resolve())], trusted=True,
            source_ref='refs/heads/main', timeout_seconds=60, log_max_bytes=4096,
            max_attempts=1, runs_dir=str(self.root / 'runs'), superpowers=dict(
                root=str(self.pins), revision='a' * 40, manifest=manifest,
                manifest_sha256=profile_fingerprint(manifest)))
        self.connection = SimpleNamespace(repository='Owner/Repo', checkout=self.checkout,
            runner_label='local', trusted_publishers=['publisher'])
        self.connections = [self.connection]
        self.executor_path = self.root / 'executor.json'
        self.executor_path.write_text(json.dumps(dict(version=1, profiles={'local': raw_profile},
            allowlist=[dict(repository='Owner/Repo', issue=18, task_id='TT-GROUPS-001',
                runner_label='local', profile='local')])), encoding='utf-8')
        self.executor = load_executor_config(self.executor_path, self.connections)
        self.task = dict(repository='Owner/Repo', issue=18, task_id='TT-GROUPS-001',
            runner_label='local', executor_profile='local', components=['scheduler'],
            allowed_paths=['task_tower/', 'tests/', 'docs/'],
            spec_path='docs/spec.md', plan_path='docs/plan.md', evidence_dir='docs/evidence/',
            checks=[dict(id='unit', argv=[str(Path(sys.executable).resolve()), '-m', 'unittest'],
                timeout_seconds=30)], ci_substitution=dict(enabled=False, required_platforms=[]),
            publish=dict(enabled=False, remote='origin', base_ref='refs/heads/main',
                publisher_account='publisher'))
        self.pipeline_path = self.root / 'pipeline.json'
        self.pipeline_path.write_text('{}', encoding='utf-8')
        self.pipeline = dict(version=1, max_active=2, task_timeout_seconds=7200,
            role_timeout_seconds=900, max_reworks=2, max_processes=36, log_max_bytes=1048576,
            tasks=[self.task], _policy_path=self.pipeline_path)
        self.group = dict(id='core', components=['scheduler', 'storage'],
            role_profiles={role: 'local' for role in ROLES})
        self.project = dict(repository='owner/repo', groups=[self.group],
            routes=[dict(issue=18, task_id='TT-GROUPS-001', group='core')], aggregates=[])
        self.value = dict(version=1, installation_id='00000000-0000-4000-8000-000000000001',
            canonical_journal=str(self.root / 'pipeline.sqlite3'), projects=[self.project])
        self.path = self.root / 'groups.json'

    def load(self):
        self.path.write_text(json.dumps(self.value), encoding='utf-8')
        return group_policy.load_group_config(self.path, self.connections, self.executor, self.pipeline)

    def route(self, policy=None, issue=18, task_id='TT-GROUPS-001'):
        return group_policy.resolve_route(policy or self.load(), 'OWNER/REPO', issue, task_id)

    def test_v2_actual_executor_pipeline_loaders_compose_without_count_fallback(self):
        from task_tower.pipeline_policy import load_pipeline_config
        raw=json.loads(self.executor_path.read_text())
        raw.update(version=2,capacity=dict(max_executors=3,max_inflight=None),
                   harness_resources={'local':dict(pool_id='local',cpu_millis=1000,memory_bytes=1048576,max_parallel=3)})
        self.executor_path.write_text(json.dumps(raw),encoding='utf-8')
        self.executor=load_executor_config(self.executor_path,self.connections)
        self.pipeline_path.write_text(json.dumps(dict(version=2,tasks=[self.task],capacity=dict(max_executors=1,max_inflight=None))),encoding='utf-8')
        self.pipeline=load_pipeline_config(self.pipeline_path,self.connections,self.executor)
        self.value['version']=2
        loaded=self.load()
        self.assertEqual(loaded['effective_capacity']['max_executors'],1)
        self.assertEqual(loaded['harness_resources']['local']['max_parallel'],3)
        self.assertNotIn('max_active',self.executor)
        self.assertNotIn('max_active',self.pipeline)
        # A real v1 executor does not silently supply v2 resource authority.
        raw.pop('harness_resources');raw.pop('capacity');raw['version']=1
        self.executor_path.write_text(json.dumps(raw),encoding='utf-8')
        self.executor=load_executor_config(self.executor_path,self.connections)
        with self.assertRaises(ValueError):self.load()

    def test_strict_schema_defaults_and_role_profiles(self):
        policy = self.load()
        route = self.route(policy)
        self.assertEqual(policy['max_active'], 2)
        self.assertEqual(policy['effective_max_active'], 2)
        self.assertEqual(route, dict(status='ready', reason=None, group_id='core',
            role_profiles={role: 'local' for role in ROLES}, components=['scheduler'], capacity=1))
        self.assertEqual(policy['_policy_bytes'], self.path.read_bytes())
        self.assertEqual(policy['policy_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        original = copy.deepcopy(self.value)
        for edit in (lambda: self.value.update(max_active=True),
                     lambda: self.value.update(version=True),
                     lambda: self.group.update(capacity=3),
                     lambda: self.group['role_profiles'].pop('test_reviewer'),
                     lambda: self.group['role_profiles'].update(coordinator='local'),
                     lambda: self.value.update(model='chosen')):
            with self.subTest(edit=edit):
                edit()
                with self.assertRaises(ValueError): self.load()
                self.value = copy.deepcopy(original)
                self.project = self.value['projects'][0]
                self.group = self.project['groups'][0]

    def test_no_labels_or_prose_route_authority(self):
        self.project['routes'] = []
        self.assertEqual(self.route()['reason'], 'routing_missing')
        self.project['routes'] = [dict(issue=18, task_id='TT-GROUPS-001', group='core', label='core')]
        with self.assertRaises(ValueError): self.load()
        self.project['routes'] = [dict(issue=99, task_id='TT-OTHER-001', group='core')]
        with self.assertRaises(ValueError): self.load()

    def test_missing_route_parks_one_task(self):
        policy = self.load()
        missing = self.route(policy, 19, 'TT-NEXT-001')
        self.assertEqual(missing, dict(status='needs_input', reason='routing_missing',
            group_id=None, role_profiles=None, components=None, capacity=None))
        self.assertEqual(self.route(policy)['status'], 'ready')
        self.project['routes'].append(dict(self.project['routes'][0]))
        ambiguous = self.load()
        self.assertEqual(self.route(ambiguous), dict(status='needs_input', reason='routing_ambiguous',
            group_id=None, role_profiles=None, components=None, capacity=None))
        self.assertEqual(group_policy.group_binding(ambiguous, self.task)['reason'], 'routing_ambiguous')

    def test_task_components_cannot_exceed_group(self):
        self.task['components'] = ['outside']
        with self.assertRaises(ValueError): self.load()
        self.group['components'] = ['*']
        self.assertEqual(self.route()['components'], ['outside'])
        self.task['components'] = ['*']
        self.assertEqual(self.route()['components'], ['*'])
        self.group['components'] = ['scheduler']
        with self.assertRaises(ValueError): self.load()
        for components in ([], ['*', 'scheduler'], ['scheduler', 'scheduler'], [True]):
            self.group['components'] = components
            with self.subTest(components=components), self.assertRaises(ValueError): self.load()

    def test_normalized_component_order_keeps_task_binding(self):
        self.task['components'] = ['storage', 'scheduler']
        binding = group_policy.group_binding(self.load(), self.task)
        self.assertEqual(binding['components'], ['scheduler', 'storage'])
        self.assertEqual(self.task['components'], ['storage', 'scheduler'])

    def test_profile_scope_and_pin_change_rejected(self):
        frozen = self.load()
        binding = group_policy.group_binding(frozen, self.task)
        self.assertEqual(binding['budgets'], dict(task_timeout_seconds=60, role_timeout_seconds=60,
            max_reworks=2, max_processes=36, log_max_bytes=4096))
        self.assertEqual(binding['role_pins']['test_reviewer'],
            self.executor['profiles']['local']['superpowers']['manifest_sha256'])
        task = copy.deepcopy(self.task)
        task['allowed_paths'] = ['*']
        with self.assertRaises(ValueError): group_policy.group_binding(frozen, task)
        (self.pins / 'SKILL.md').write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError): group_policy.group_binding(frozen, self.task)
        with self.assertRaises(ValueError): self.load()

    def test_profile_checkout_replacement_cannot_reuse_old_validation(self):
        loaded = self.load()
        self.checkout.rmdir()
        self.checkout.write_text('not a source directory', encoding='utf-8')
        with self.assertRaises(ValueError): group_policy.group_binding(loaded, self.task)

    def test_stale_private_bytes_and_returned_binding_mutation_do_not_grant_authority(self):
        policy = self.load()
        binding = group_policy.group_binding(policy, self.task)
        binding['task_policy']['allowed_paths'].append('outside/')
        self.assertNotIn('outside/', group_policy.group_binding(policy, self.task)['task_policy']['allowed_paths'])
        self.path.write_text(self.path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaises(ValueError): group_policy.group_binding(policy, self.task)

    def test_aggregate_policy_preserves_qualified_children_without_claiming_native_proof(self):
        self.project['aggregates'] = [dict(issue=18, task_id='TT-GROUPS-001',
            required_children=['Other/Project#2', 'Owner/Repo#1'])]
        project = self.load()['projects'][0]
        self.assertEqual(project['aggregates'][0]['required_children'], ['other/project#2', 'owner/repo#1'])
        self.assertNotIn('accepted', project['aggregates'][0])
        self.project['aggregates'][0]['required_children'].append('OWNER/REPO#1')
        with self.assertRaises(ValueError): self.load()
        self.project['aggregates'][0]['required_children'] = ['relative#1']
        with self.assertRaises(ValueError): self.load()

    def test_capacity_debt_does_not_reassign(self):
        self.group['capacity'] = 2
        first = group_policy.group_binding(self.load(), self.task)
        self.value['max_active'] = 1
        self.group['capacity'] = 1
        smaller = group_policy.group_binding(self.load(), self.task)
        self.assertEqual(smaller['capacity'], 1)
        self.assertEqual(first['authorization_sha256'], smaller['authorization_sha256'])
        self.assertNotEqual(first['capacity_sha256'], smaller['capacity_sha256'])
        self.assertEqual(smaller['group_id'], 'core')
        self.project['base_update'] = dict(enabled=True, max_updates=1)
        changed = group_policy.group_binding(self.load(), self.task)
        self.assertNotEqual(smaller['authorization_sha256'], changed['authorization_sha256'])

    def test_duplicate_keys_and_private_path_aliases_rejected(self):
        self.load()
        self.path.write_text('{"version":1,"version":1}', encoding='utf-8')
        with self.assertRaises(ValueError):
            group_policy.load_group_config(self.path, self.connections, self.executor, self.pipeline)
        alias = self.root / 'hardlinked-groups.json'
        os.link(self.path, alias)
        with self.assertRaises(ValueError):
            group_policy.load_group_config(alias, self.connections, self.executor, self.pipeline)
        alias.unlink()
        self.path = self.checkout / 'groups.json'
        with self.assertRaises(ValueError): self.load()
        self.path = self.root / 'groups.json'
        for journal in (str(self.path), str(self.path) + '-wal', str(self.pipeline_path),
                        str(self.checkout / 'journal.sqlite3')):
            self.value['canonical_journal'] = journal
            with self.subTest(journal=journal), self.assertRaises(ValueError): self.load()

    def test_pipeline_one_caps_groups_two(self):
        self.group['capacity'] = 2
        self.pipeline['max_active'] = 1
        policy = self.load()
        self.assertEqual(policy['effective_max_active'], 1)
        self.assertEqual(self.route(policy)['capacity'], 1)
        self.value['max_active'] = 1
        self.group['capacity'] = 2
        with self.assertRaises(ValueError): self.load()

    def test_role_profile_must_match_existing_task_authority(self):
        other = copy.deepcopy(self.executor['profiles']['local'])
        other['runs_dir'] = str(self.root / 'other-runs')
        self.executor['profiles']['other'] = other
        self.group['role_profiles']['spec_reviewer'] = 'other'
        with self.assertRaises(ValueError): self.load()
        self.group['role_profiles']['spec_reviewer'] = 'missing'
        with self.assertRaises(ValueError): self.load()

    def test_canonical_journal_path_and_installation_binding(self):
        before = self.load()
        binding = group_policy.group_binding(before, self.task)
        self.assertEqual(binding['installation_id'], '00000000-0000-4000-8000-000000000001')
        self.assertEqual(binding['canonical_journal'], str(self.root / 'pipeline.sqlite3'))
        self.assertFalse((self.root / 'pipeline.sqlite3').exists())
        self.value['installation_id'] = 'not-a-uuid'
        with self.assertRaises(ValueError): self.load()
        self.value['installation_id'] = '00000000-0000-4000-8000-000000000001'
        self.value['canonical_journal'] = 'relative.sqlite3'
        with self.assertRaises(ValueError): self.load()
        self.value['canonical_journal'] = str(self.root / 'different.sqlite3')
        self.assertNotEqual(before['authorization_sha256'], self.load()['authorization_sha256'])

    def test_base_update_disabled_default_and_two_intent_limit(self):
        self.assertEqual(group_policy.group_binding(self.load(), self.task)['base_update'],
            dict(enabled=False, max_updates=0))
        for value in (dict(enabled=True, max_updates=3), dict(enabled=True, max_updates=True),
                      dict(enabled=True, max_updates=0), dict(enabled=False, max_updates=1),
                      dict(enabled='yes', max_updates=1), dict(enabled=True, max_updates=1, prompt='grant')):
            self.project['base_update'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.load()
        self.project['base_update'] = dict(enabled=True, max_updates=2)
        self.assertEqual(group_policy.group_binding(self.load(), self.task)['base_update']['max_updates'], 2)

    def test_accepted_main_source_requires_exact_private_profile_anchor_grant(self):
        self.assertIsNone(group_policy.group_binding(self.load(), self.task)['accepted_main_source'])
        grant = dict(executor_profile='local',
            profile_sha256=profile_fingerprint(self.executor['profiles']['local']), anchor_sha='b' * 40)
        self.project['accepted_main_sources'] = [grant]
        binding = group_policy.group_binding(self.load(), self.task)
        self.assertEqual(binding['accepted_main_source'], grant)
        self.assertEqual(self.executor['profiles']['local']['source_ref'], 'refs/heads/main')
        for field, value in (('profile_sha256', 'c' * 64), ('anchor_sha', 'refs/heads/main'),
                             ('executor_profile', 'missing')):
            old = grant[field]
            grant[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.load()
            grant[field] = old
        self.project['accepted_main_sources'].append(dict(grant))
        with self.assertRaises(ValueError): self.load()


class GroupPolicyV2Tests(GroupPolicyTests):
    # Inherit v1 coverage on the unchanged fixture; opt in only in v2 cases.
    def upgrade(self):
        self.value['version'] = 2
        self.executor['version'] = 2
        self.executor.pop('max_active', None)
        self.executor['capacity'] = dict(max_executors=None, max_inflight=None)
        self.executor['harness_resources'] = {'local': dict(pool_id='approved', cpu_millis=1000,
            memory_bytes=1073741824, max_parallel=None)}
        self.pipeline['version'] = 2
        self.pipeline.pop('max_active', None)
        self.pipeline['capacity'] = dict(max_executors=None, max_inflight=None)

    def test_v2_auto_inherit_has_no_fixed_task_count(self):
        self.upgrade()
        policy = self.load()
        self.assertEqual(self.route(policy)['capacity'], dict(mode='auto', max_executors=None,
            max_inflight=None, max_cpu_millis=None, max_memory_bytes=None, fallback=None))
        self.assertEqual(group_policy.group_binding(policy, self.task)['version'], 2)
        self.assertIsNone(policy['projects'][0]['groups'][0]['capacity'])

    def test_v2_explicit_caps_above_two_and_legacy_minimum(self):
        self.upgrade()
        self.value['capacity'] = dict(mode='auto', max_executors=9, max_inflight=12,
            max_cpu_millis=9000, max_memory_bytes=2**40, fallback=None)
        self.group.update(capacity=5, max_inflight=8)
        self.executor['capacity']['max_executors'] = 7
        self.pipeline['capacity']['max_inflight'] = 6
        self.assertEqual(self.route()['capacity']['max_executors'], 5)
        self.assertEqual(self.route()['capacity']['max_inflight'], 6)
        self.pipeline['version'] = 1
        self.pipeline.pop('capacity')
        self.assertEqual(self.route()['capacity']['max_executors'], 2)

    def test_v2_strict_capacity_and_missing_resources(self):
        self.upgrade()
        original = copy.deepcopy(self.value)
        for bad in (True, 0, -1, 2**63, '3'):
            self.group['capacity'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): self.load()
        self.value = original
        self.group = self.value['projects'][0]['groups'][0]
        for capacity in ({}, dict(mode='auto', max_executors=None, max_inflight=None,
                max_cpu_millis=None, max_memory_bytes=None, fallback={'cpu_millis': True,
                'memory_bytes': 1, 'max_executors': 1})):
            self.value['capacity'] = capacity
            with self.subTest(capacity=capacity), self.assertRaises(ValueError): self.load()
        self.value.pop('capacity')
        self.executor['harness_resources'] = {}
        with self.assertRaises(ValueError): self.load()

    def test_v2_capacity_digest_excludes_only_capacity_authority(self):
        self.upgrade()
        before = self.load()
        self.group.update(capacity=5, max_inflight=7)
        self.executor['harness_resources']['local']['max_parallel'] = 4
        after = self.load()
        self.assertEqual(before['authorization_sha256'], after['authorization_sha256'])
        self.assertNotEqual(before['capacity_sha256'], after['capacity_sha256'])
        self.executor['harness_resources']['local']['cpu_millis'] = 2000
        changed = self.load()
        self.assertNotEqual(after['authorization_sha256'], changed['authorization_sha256'])

    def test_v2_legacy_executor_is_explicit_cap_and_cannot_infer_resources(self):
        self.value['version'] = 2
        with self.assertRaises(ValueError): self.load()
        self.executor['harness_resources'] = {'local': dict(pool_id='approved', cpu_millis=1000,
            memory_bytes=1073741824, max_parallel=5)}
        self.assertEqual(self.route()['capacity']['max_executors'], 2)

    def test_v2_binding_freezes_resources_and_pool_caps_use_minimum(self):
        self.upgrade()
        self.executor['harness_resources']['local']['max_parallel'] = 5
        other = copy.deepcopy(self.executor['profiles']['local'])
        self.executor['profiles']['alias'] = other
        self.executor['harness_resources']['alias'] = dict(pool_id='approved', cpu_millis=2000,
            memory_bytes=2000000000, max_parallel=3)
        binding = group_policy.group_binding(self.load(), self.task)
        self.assertEqual(binding['harness_resources']['local']['cpu_millis'], 1000)
        self.assertEqual(binding['harness_pools'], {'approved': {'max_parallel': 3}})
        binding['harness_resources']['local']['cpu_millis'] = 1
        self.assertEqual(group_policy.group_binding(self.load(), self.task)
                         ['harness_resources']['local']['cpu_millis'], 1000)
        self.executor['harness_resources']['alias']['pool_id'] = 'split'
        with self.assertRaises(ValueError): self.load()

    def test_v2_resource_authority_rejects_model_hints_and_bad_fallbacks(self):
        self.upgrade()
        for raw in (dict(pool_id='approved', cpu_millis=1000, memory_bytes=1,
                         max_parallel=None, model='cheap'),
                    dict(pool_id='approved', cpu_millis=True, memory_bytes=1, max_parallel=None)):
            self.executor['harness_resources']['local'] = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError): self.load()
        self.upgrade()
        self.value['capacity'] = dict(mode='auto', max_executors=None, max_inflight=None,
            max_cpu_millis=None, max_memory_bytes=None,
            fallback=dict(cpu_millis=4000, memory_bytes=2**34, max_executors=4))
        self.assertEqual(self.route()['capacity']['fallback']['max_executors'], 4)
        self.value['capacity']['model'] = 'budget'
        with self.assertRaises(ValueError): self.load()


if __name__ == '__main__':
    unittest.main()
