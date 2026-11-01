import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from task_tower import harness


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / 'project space Ю'
        self.project.mkdir()
        self.skill = Path(self.temp.name).resolve() / 'SKILL.md'
        self.skill.write_text('Use Superpowers.', encoding='utf-8')

    def prepare(self, **kwargs):
        options = dict(project=self.project, harness='codex', superpowers=self.skill,
                       adapter=None, executable=sys.executable, persist=True)
        options.update(kwargs)
        return harness.prepare(**options)

    def test_dry_run_plans_prompt_without_creating_files(self):
        result = self.prepare(persist=False)
        self.assertFalse((self.project / '.task-tower').exists())
        self.assertEqual(result['cwd'], str(self.project.resolve()))
        self.assertIn(str(self.project / '.task-tower' / 'context.md'), result['argv'][-1])

    def test_persisted_skill_pin_rejects_change_and_explicit_path_refreshes(self):
        self.prepare()
        self.assertIsNotNone(harness.load_config(self.project))
        self.skill.write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed|hash|stale'):
            self.prepare(superpowers=None)
        self.prepare()
        self.prepare(superpowers=None)

    def test_builtin_argv_delivers_context_and_opencode_project(self):
        for name in ('codex', 'claude', 'opencode'):
            result = self.prepare(harness=name)
            self.assertEqual(result['argv'][0], str(Path(sys.executable).resolve()))
            self.assertIn(str(self.skill), (self.project / '.task-tower/context.md').read_text(encoding='utf-8'))
            if name == 'opencode':
                self.assertEqual(result['argv'][1:3], [str(self.project), '--prompt'])
            self.assertTrue(result['capabilities']['interactive_launch'])

    def test_custom_snapshot_reused_without_silent_descriptor_change(self):
        adapter = Path(self.temp.name) / 'adapter.json'
        adapter.write_text(json.dumps({'version': 1, 'id': 'fixture', 'launch_argv': [sys.executable, '{project}', '{instructions}'], 'capabilities': {'interactive_launch': True}}))
        result = self.prepare(harness='custom', adapter=adapter, executable=None)
        self.assertEqual(result['argv'][1:], [str(self.project), str(self.project / '.task-tower/context.md')])
        adapter.write_text('{}')
        reused = self.prepare(harness='custom', adapter=None, executable=None, superpowers=None)
        self.assertEqual(result['argv'], reused['argv'])

    def test_rejects_malformed_descriptor_and_missing_skill_or_executable(self):
        adapter = Path(self.temp.name) / 'adapter.json'
        for changes in ({'launch_argv': ['echo', '{bad}']}, {'capabilities': {'interactive_launch': False}}, {'version': True}):
            value = {'version': 1, 'id': 'fixture', 'launch_argv': [sys.executable], 'capabilities': {'interactive_launch': True}}
            value.update(changes)
            adapter.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                self.prepare(harness='custom', adapter=adapter)
        with self.assertRaises(ValueError):
            self.prepare(superpowers=Path(self.temp.name) / 'absent')
        with self.assertRaises(ValueError):
            self.prepare(executable='not-a-real-harness-92731')

    def test_windows_shell_shim_is_rejected(self):
        shim = Path(self.temp.name) / 'harness.cmd'
        shim.write_text('@echo off')
        with patch.object(harness.platform, 'system', return_value='Windows'):
            with self.assertRaisesRegex(ValueError, 'native|shim|executable'):
                self.prepare(executable=str(shim))

    def test_atomic_write_does_not_modify_hardlinked_context_target(self):
        self.prepare()
        context = self.project / '.task-tower/context.md'
        context.unlink()
        target = Path(self.temp.name) / 'outside'
        target.write_text('untouched')
        os.link(target, context)
        self.prepare()
        self.assertEqual(target.read_text(), 'untouched')

    def test_refuses_symlink_state_directory(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        try:
            (self.project / '.task-tower').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.prepare()
        self.assertEqual(list(outside.iterdir()), [])


    def test_invalid_saved_skill_pin_is_explained(self):
        self.prepare()
        config = self.project / '.task-tower/config.json'
        value = json.loads(config.read_text(encoding='utf-8'))
        value['superpowers'] = {'path': str(self.skill)}
        config.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            self.prepare(superpowers=None)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_rejects_junction_without_new_pathlib_api(self):
        import subprocess
        outside = Path(self.temp.name) / 'junction-target'
        outside.mkdir()
        state = self.project / '.task-tower'
        created = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(state), str(outside)], capture_output=True)
        if created.returncode:
            self.skipTest('junction creation unavailable')
        try:
            with patch.object(Path, 'is_junction', return_value=False, create=True):
                with self.assertRaisesRegex(ValueError, 'symlink|junction|reparse'):
                    self.prepare()
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            os.rmdir(state)
