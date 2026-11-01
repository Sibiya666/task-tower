import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import bootstrap


class BootstrapConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / 'private connections.json'
        self.args = ['--project', str(self.root), '--harness', 'codex',
                     '--github-repository', 'owner/repo', '--connection-id', 'sample',
                     '--connections', str(self.config), '--runner-label', 'sample-runner',
                     '--project-url', 'https://github.com/users/owner/projects/2']

    def test_connection_precedes_configuration_and_forwards_without_shell(self):
        events = []
        with patch.object(bootstrap, 'ensure_project_connection', create=True) as connect, \
             patch.object(bootstrap, 'prepare') as prepare, \
             contextlib.redirect_stdout(io.StringIO()):
            connect.side_effect = lambda **kw: events.append(('connect', kw))
            prepare.side_effect = lambda *a, **kw: events.append(('prepare', kw)) or {'argv': ['codex'], 'cwd': str(self.root), 'platform': 'test'}
            self.assertEqual(bootstrap.main([*self.args, '--configure-only']), 0)
        self.assertEqual([event[0] for event in events], ['connect', 'prepare'])
        self.assertEqual(events[0][1], dict(config_path=self.config, connection_id='sample',
            repository='owner/repo', checkout=self.root, runner_label='sample-runner',
            project_url='https://github.com/users/owner/projects/2'))

    def test_project_denial_prevents_persistence_and_launch(self):
        with patch.object(bootstrap, 'ensure_project_connection', create=True, side_effect=ValueError('Projects permission required')), \
             patch.object(bootstrap, 'prepare') as prepare, \
             patch.object(bootstrap.subprocess, 'run') as run, \
             contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(bootstrap.main([*self.args, '--launch']), 2)
        prepare.assert_not_called()
        run.assert_not_called()
        self.assertIn('Projects permission required', error.getvalue())

    def test_dry_run_reports_unverified_plan_without_connection_mutation(self):
        with patch.object(bootstrap, 'ensure_project_connection', create=True) as connect, \
             patch.object(bootstrap, 'prepare', return_value={'argv': ['codex']}) as prepare, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bootstrap.main([*self.args, '--dry-run']), 0)
        connect.assert_not_called()
        self.assertFalse(self.config.exists())
        self.assertFalse(prepare.call_args.kwargs['persist'])
        self.assertIn('unverified', output.getvalue())

    def test_partial_connection_flags_fail_before_prepare(self):
        with patch.object(bootstrap, 'prepare') as prepare, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(['--harness', 'codex', '--configure-only', '--github-repository', 'owner/repo']), 2)
        prepare.assert_not_called()
