"""Task4a: real private factories, lifetime source identity and fail-closed drift."""
import hashlib
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower.executor_profiles import profile_fingerprint
from task_tower.pipeline_journal import PipelineJournal
from task_tower.pr_policy import policy_fingerprint

try:
    from task_tower.pr_context import PRHostContext, PRPrivateInputs
except ImportError:
    PRHostContext = PRPrivateInputs = None


class ContextFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.checkout = self.root / 'checkout'; self.checkout.mkdir()
        self.pins = self.root / 'pins'; self.pins.mkdir()
        (self.pins / 'SKILL.md').write_bytes(b'rules')
        manifest = {'SKILL.md': hashlib.sha256(b'rules').hexdigest()}
        self.profile = dict(kind='custom', trusted=True, repository='owner/repo',
            checkout=str(self.checkout), runner_label='local', argv=[str(Path(os.sys.executable).resolve())],
            source_ref='refs/heads/main', timeout_seconds=60, log_max_bytes=4096, max_attempts=1,
            runs_dir=str(self.root/'runs'), superpowers=dict(root=str(self.pins), revision='a'*40,
                manifest=manifest, manifest_sha256=profile_fingerprint(manifest)))
        self.connections = self.root/'connections.json'; self.executor = self.root/'executor.json'
        self.policy = self.root/'pr.json'; self.pipeline = self.root/'pipeline.json'
        self.source = self.root/'pipeline.db'; self.journal = self.root/'pr.db'
        self.write(self.connections, dict(version=1, projects=[dict(id='project', repository='owner/repo',
            checkout=str(self.checkout), runner_label='local', trusted_publishers=['operator'])]))
        self.write(self.executor, dict(version=1, profiles={'local':self.profile}, allowlist=[dict(
            repository='owner/repo', issue=17, task_id='TT-PR-001', runner_label='local', profile='local')]))
        self.pipeline_row = dict(repository='owner/repo', issue=17, task_id='TT-PR-001',
            runner_label='local', executor_profile='local', components=['core'], allowed_paths=['src/','docs/'],
            spec_path='docs/spec.md', plan_path='docs/plan.md', evidence_dir='docs/evidence/',
            checks=[dict(id='unit', argv=[str(Path(os.sys.executable).resolve()),'-m','unittest'], timeout_seconds=60)],
            ci_substitution=dict(enabled=False, required_platforms=[]),
            publish=dict(enabled=True, remote='origin', base_ref='refs/heads/main', publisher_account='operator'))
        self.write(self.pipeline, dict(version=1, tasks=[self.pipeline_row]))
        self.raw = dict(version=1, executor_config=str(self.executor), pipeline_journal=str(self.source),
            legacy_provenance=None, projects=[dict(repository='owner/repo', base_ref='refs/heads/main',
                publisher_account='operator', merge_enabled=False,
                exclusive_writer=dict(enabled=False,boundary_id='fixture',asserted_by='operator'),
                tasks=[dict(issue=17,issue_id=1017,task_id='TT-PR-001',pr_number=44,source='pipeline',
                    pipeline_run_id='00000000-0000-4000-8000-000000000001',legacy_card=None,
                    reviewer_profile='local',postmerge_profile='local',
                    required_checks=[dict(context='unit',app_id=15368)],required_platforms=['windows'])])])
        self.write(self.policy,self.raw)
        # Only fixture setup initializes this scratch source; the factory may not.
        with PipelineJournal(self.source)._db(True): pass

    @staticmethod
    def write(path,value): path.write_text(json.dumps(value),encoding='utf-8')

    def make(self, **overrides):
        self.assertIsNotNone(PRHostContext, 'Real private PR host factory is missing')
        fields=dict(connections_path=self.connections,policy_path=self.policy,journal_path=self.journal,
                    pipeline_config_path=self.pipeline); fields.update(overrides)
        result=PRHostContext.from_inputs(PRPrivateInputs(**fields)); self.addCleanup(result.close)
        return result

    def inventory(self):
        return {p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def test_failed_context_entry_closes_retained_source_descriptors(self):
        context=self.make(); descriptors=[row[0] for row in context._pins.values()]
        original=self.policy.read_bytes()
        self.policy.rename(self.root/'retained-policy.json')
        self.policy.write_bytes(original)
        with self.assertRaises(ValueError):
            with context:
                self.fail('Replaced policy entered context')
        self.assertTrue(context._closed)
        for descriptor in descriptors:
            with self.assertRaises(OSError): os.fstat(descriptor)

    def test_close_failure_still_attempts_every_retained_descriptor(self):
        context=self.make(); descriptors=[row[0] for row in context._pins.values()]
        real_close=os.close; calls=[]
        def close(descriptor):
            calls.append(descriptor); real_close(descriptor)
            if descriptor==descriptors[0]: raise OSError('injected post-close failure')
        try:
            with patch('task_tower.pr_context.os.close',side_effect=close):
                with self.assertRaisesRegex(OSError,'injected post-close failure'): context.close()
            self.assertEqual(calls,descriptors)
            for descriptor in descriptors:
                with self.assertRaises(OSError): os.fstat(descriptor)
        finally:
            for descriptor in descriptors:
                try: real_close(descriptor)
                except OSError: pass

    def test_failed_entry_keeps_primary_error_when_cleanup_also_fails(self):
        context=self.make(); descriptors=[row[0] for row in context._pins.values()]
        original=self.policy.read_bytes()
        self.policy.rename(self.root/'retained-policy.json'); self.policy.write_bytes(original)
        real_close=os.close
        def close(descriptor):
            real_close(descriptor)
            if descriptor==descriptors[0]: raise OSError('injected entry cleanup failure')
        try:
            with patch('task_tower.pr_context.os.close',side_effect=close):
                with self.assertRaises(ValueError) as failure:
                    with context: self.fail('Replaced policy entered context')
            self.assertIsInstance(failure.exception.__cause__,OSError)
            for descriptor in descriptors:
                with self.assertRaises(OSError): os.fstat(descriptor)
        finally:
            context.close()

    def test_real_factory_and_reload_do_not_write_or_initialize_journals(self):
        before=self.inventory(); context=self.make(); fresh=context._fresh_inputs()
        self.assertEqual(fresh['policy']['projects'][0]['tasks'][0]['pr_number'],44)
        self.assertEqual(fresh['pipeline_config']['tasks'][0]['task_id'],'TT-PR-001')
        self.assertTrue(fresh['pipeline_config']['_authority_check']())
        self.assertEqual(context.private_inputs_sha256,policy_fingerprint(context.private_input_provenance))
        self.assertFalse(self.journal.exists()); self.assertEqual(before,self.inventory())
        self.assertFalse(Path(str(self.journal)+'.private').exists())

    def test_explicit_locator_required_without_extending_v1_policy(self):
        before=self.inventory()
        with self.assertRaises(ValueError): self.make(pipeline_config_path=None)
        self.raw['pipeline_config']=str(self.pipeline); self.write(self.policy,self.raw)
        with self.assertRaises(ValueError): self.make()
        self.assertFalse(self.journal.exists()); self.assertFalse(Path(str(self.journal)+'.private').exists())
        self.assertEqual(before[self.source.name],self.source.read_bytes())

    def test_unicode_locator_preserves_actual_pr_policy_fingerprint(self):
        executor=self.root/'executor-\u043f\u0440.json'; self.executor.rename(executor)
        self.raw['executor_config']=str(executor); self.write(self.policy,self.raw)
        context=self.make(); loaded=context._fresh_inputs()
        self.assertEqual(context.private_input_provenance['policy_sha256'],policy_fingerprint(loaded['policy']))

    def test_each_real_private_file_byte_drift_is_refused(self):
        for path in (self.connections,self.executor,self.policy,self.pipeline):
            with self.subTest(path=path.name):
                original=path.read_bytes(); context=self.make(); path.write_bytes(original+b' ')
                with self.assertRaises(ValueError): context._fresh_inputs()
                context.close(); path.write_bytes(original)

    def test_same_bytes_replacement_source_and_config_are_refused(self):
        for path in (self.source,self.policy):
            with self.subTest(path=path.name):
                context=self.make(); replacement=self.root/'replacement'
                replacement.write_bytes(path.read_bytes())
                # Windows cannot overwrite this open file directly, although
                # share-delete permits renaming it and installing a new inode.
                old=self.root/'retained-old'; path.rename(old); replacement.rename(path)
                with self.assertRaises(ValueError): context._fresh_inputs()
                context.close(); old.unlink()

    def test_current_instruction_and_policy_mutation_cannot_authorize(self):
        context=self.make(); (self.pins/'SKILL.md').write_bytes(b'changed')
        with self.assertRaises(ValueError): context._fresh_inputs()
        (self.pins/'SKILL.md').write_bytes(b'rules')
        # Returned loader state is never the lifetime factory's accepted state.
        fresh=context._fresh_inputs(); fresh['policy']['projects'][0]['merge_enabled']=True
        self.assertFalse(context._fresh_inputs()['policy']['projects'][0]['merge_enabled'])

    def test_missing_foreign_or_hot_source_is_not_repaired(self):
        original=self.source.read_bytes()
        for mode in ('missing','foreign','wal'):
            with self.subTest(mode=mode):
                self.source.write_bytes(original)
                if mode=='missing': self.source.unlink()
                elif mode=='foreign': self.source.write_bytes(b'foreign')
                else: Path(str(self.source)+'-wal').write_bytes(b'not recovered')
                before=self.inventory()
                with self.assertRaises(ValueError): self.make()
                self.assertEqual(before,self.inventory())
                Path(str(self.source)+'-wal').unlink(missing_ok=True); self.source.write_bytes(original)

    def test_namespace_and_sidecar_collisions_are_rejected(self):
        for path in (Path(str(self.source)+'-wal'), self.source, self.checkout/'pr.db'):
            with self.subTest(path=str(path)):
                with self.assertRaises(ValueError): self.make(journal_path=path)
        namespace=Path(str(self.journal)+'.private'); namespace.mkdir()
        moved=namespace/'pipeline.json'; moved.write_bytes(self.pipeline.read_bytes())
        with self.assertRaises(ValueError): self.make(pipeline_config_path=moved)

    def test_lifetime_pins_are_noninheritable_and_close_is_terminal(self):
        context=self.make(); descriptors=[pin[0] for pin in context._pins.values()]
        self.assertTrue(descriptors)
        self.assertTrue(all(not os.get_inheritable(fd) for fd in descriptors))
        context.close(); context.close()
        for fd in descriptors:
            with self.assertRaises(OSError): os.fstat(fd)
        with self.assertRaises(ValueError): context._fresh_inputs()

    def test_actual_loader_source_journal_under_executor_runs_is_refused(self):
        runs=self.root/'runs'; runs.mkdir()
        target=runs/'pipeline.db'; self.source.rename(target); self.source=target
        self.raw['pipeline_journal']=str(target); self.write(self.policy,self.raw)
        before=self.inventory(); source_bytes=target.read_bytes()
        with self.assertRaises(ValueError): self.make()
        self.assertEqual(before,self.inventory()); self.assertEqual(source_bytes,target.read_bytes())

    def test_actual_loader_pr_policy_under_instruction_root_is_refused(self):
        target=self.pins/'pr.json'; self.policy.rename(target); self.policy=target
        before=target.read_bytes()
        with self.assertRaises(ValueError): self.make()
        self.assertEqual(before,target.read_bytes()); self.assertFalse(self.journal.exists())

    def test_actual_loader_private_journal_equal_or_ancestor_of_runs_is_refused(self):
        executor=json.loads(self.executor.read_text(encoding='utf-8'))
        for mode in ('equal','ancestor'):
            with self.subTest(mode=mode):
                journal=self.root/'private-state'
                runs=journal if mode=='equal' else journal/'roles'
                executor['profiles']['local']['runs_dir']=str(runs); self.write(self.executor,executor)
                with self.assertRaises(ValueError): self.make(journal_path=journal)
                self.assertFalse(journal.exists()); self.assertFalse(runs.exists())

    def test_actual_loader_checks_private_inputs_against_other_profile_roots(self):
        other=self.root/'other-runs'; other.mkdir()
        target=other/'pipeline.json'; self.pipeline.rename(target); self.pipeline=target
        executor=json.loads(self.executor.read_text(encoding='utf-8'))
        profile=copy.deepcopy(executor['profiles']['local']); profile['runs_dir']=str(other)
        executor['profiles']['other']=profile; self.write(self.executor,executor)
        before=self.inventory()
        with self.assertRaises(ValueError): self.make()
        self.assertEqual(before,self.inventory())

    def test_actual_loader_hardlinked_source_alias_in_runs_is_refused(self):
        runs=self.root/'runs'; runs.mkdir(); alias=runs/'source-alias.db'
        try: os.link(self.source,alias)
        except (OSError,NotImplementedError): self.skipTest('Hardlinks unavailable')
        original=self.source.read_bytes()
        self.raw['pipeline_journal']=str(alias); self.write(self.policy,self.raw)
        with self.assertRaises(ValueError): self.make()
        self.assertEqual(original,self.source.read_bytes()); self.assertEqual(original,alias.read_bytes())

    def test_actual_loader_source_sidecar_equal_to_output_root_is_refused(self):
        executor=json.loads(self.executor.read_text(encoding='utf-8'))
        executor['profiles']['local']['runs_dir']=str(self.source)+'-wal'
        self.write(self.executor,executor)
        with self.assertRaises(ValueError): self.make()
        self.assertFalse(Path(str(self.source)+'-wal').exists())

    def test_actual_loader_legacy_private_file_under_instructions_is_refused(self):
        legacy=self.pins/'legacy.json'; self.write(legacy,{})
        task=self.raw['projects'][0]['tasks'][0]
        task.update(source='legacy',pipeline_run_id=None,legacy_card='docs/tasks/TT-PR-001.json')
        self.raw.update(pipeline_journal=None,legacy_provenance=str(legacy)); self.write(self.policy,self.raw)
        with self.assertRaises(ValueError): self.make(pipeline_config_path=None)
        self.assertEqual('{}',legacy.read_text(encoding='utf-8')); self.assertFalse(self.journal.exists())

