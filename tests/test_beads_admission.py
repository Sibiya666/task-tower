"""Synthetic admission fixtures; no installed Beads or private settings are read."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HEAD = 'a' * 40
TREE = 'b' * 40
ROW = dict(id='tt-fixture.1', status='open', issue_type='task', title='PRIVATE_PROSE')


def facts(**changes):
    value = dict(status='passed', exit_code=0, pid=123, cleanup_confirmed=True,
                 duration_seconds=.01, stdout_bytes=10, stderr_bytes=0,
                 stdout_tail_unknown=False, stderr_tail_unknown=False,
                 stdout_truncated=False, stderr_truncated=False)
    value.update(changes)
    return value


class OptionalRunnerCancellationTests(unittest.TestCase):
    def test_exact_stopped_event_prevents_child_and_corrupt_flag_never_calls_truthiness(self):
        from task_tower.beads_admission import _production_runner
        event=threading.Event();event.set()
        data,receipt=_production_runner('git_surrogate',[sys.executable,'-c','raise SystemExit(99)'],Path.cwd(),1,
            os.environ.copy(),cancel_requested=event)
        self.assertFalse(receipt['started']);self.assertEqual(receipt['status'],'cancelled')
        self.assertTrue(receipt['cleanup_confirmed'])
        class Flag:
            def __bool__(self):raise AssertionError('unsafe truthiness')
        event._flag=Flag()
        data,receipt=_production_runner('git_surrogate',[sys.executable,'-c','raise SystemExit(99)'],Path.cwd(),1,
            os.environ.copy(),cancel_requested=event)
        self.assertFalse(receipt['started']);self.assertEqual(receipt['status'],'unknown')
        with self.assertRaises(ValueError):
            _production_runner('git_surrogate',[],Path.cwd(),1,{},cancel_requested=lambda:False)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / '.git').mkdir()
        self.database = self.root / 'embedded'
        (self.database / '.beads').mkdir(parents=True)
        (self.database / '.beads/metadata.json').write_text(
            '{"backend":"dolt","dolt_mode":"embedded"}', encoding='utf-8')
        self.exe = self.root / 'bd.exe'
        self.exe.write_bytes(b'fixture only, never launched')
        self.config = self.root / 'operator.json'
        self.policy = dict(version=1, executable=str(self.exe), projects=[dict(
            id='fixture', repository='Sibiya666/task-tower', directory=str(self.database),
            source=str(self.source), expected_head=HEAD, allowed_beads=['tt-fixture.1'])])
        self.write_config()
        self.calls = []
        self.values = {'git_config': '', 'git_toplevel': str(self.source),
                       'git_metadata': str(self.source / '.git'), 'git_index': '',
                       'git_head': HEAD, 'git_tree': TREE, 'git_status': '',
                       'beads_ready': [dict(ROW)], 'beads_show': [dict(ROW)]}
        self.process_changes = {}

    def write_config(self):
        self.config.write_text(json.dumps(self.policy), encoding='utf-8')

    def runner(self, operation, argv, cwd, timeout, env):
        self.calls.append((operation, argv, cwd, timeout, env))
        value = self.values[operation]
        if callable(value):
            value = value()
        return value, facts(**self.process_changes)

    def observe(self, **kwargs):
        from task_tower.beads_admission import observe
        with patch('task_tower.beads_admission.sys.platform', 'win32'):
            return observe(self.config, 'fixture', 'tt-fixture.1', runner=self.runner, **kwargs)

    def test_official_omitted_assignee_is_observation_only_and_private_free(self):
        packet = self.observe()
        self.assertEqual(packet['outcome'], 'eligible_observation')
        self.assertEqual(packet['identity'], 'Sibiya666/task-tower:beads:fixture:tt-fixture.1')
        self.assertEqual(packet['source'], dict(head=HEAD, tree=TREE))
        self.assertNotEqual(packet['run_id'], packet['attempt_id'])
        serialized = json.dumps(packet)
        for private in ('PRIVATE_PROSE', str(self.root), 'argv', 'environment', 'accepted', 'owned'):
            self.assertNotIn(private, serialized)
        self.assertLess(len(serialized.encode()), 65536)
        bead_calls = [c for c in self.calls if c[0].startswith('beads_')]
        self.assertEqual([c[1][1:] for c in bead_calls], [
            ['--readonly', '--sandbox', '--json', 'ready', '--limit', '1001'],
            ['--readonly', '--sandbox', '--json', 'show', 'tt-fixture.1']])

    def test_non_windows_never_opens_configuration(self):
        from task_tower.beads_admission import observe
        with patch('task_tower.beads_admission.sys.platform', 'linux'):
            packet = observe(self.root / 'missing', 'fixture', 'tt-fixture.1', runner=self.runner)
        self.assertEqual(packet['outcome'], 'refused')
        self.assertFalse(self.calls)

    def test_strict_config_rejects_malformed_duplicates_aliases_and_limits(self):
        from task_tower.beads_admission import load_config
        original = json.loads(json.dumps(self.policy))
        variants = [dict(original, version=True), dict(original, unknown='PRIVATE'),
                    dict(original, projects=original['projects'] * 33)]
        for key, value in [('repository', 'Other/repo'), ('expected_head', 'A'*40),
                           ('allowed_beads', ['tt-fixture.1']*2),
                           ('allowed_beads', ['tt-'+str(i) for i in range(1001)]),
                           ('source', 'relative'), ('directory', None)]:
            variant = json.loads(json.dumps(original))
            variant['projects'][0][key] = value
            variants.append(variant)
        for value in variants:
            self.config.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_config(self.config)
        self.config.write_text('{"version":1,"version":1}', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_config(self.config)

    def test_oversized_and_nonfinite_configuration_is_refused_without_commands(self):
        for raw in (' ' * 65537, '{"version":NaN}', '{"version":Infinity}'):
            self.config.write_text(raw, encoding='utf-8')
            self.assertEqual(self.observe()['outcome'], 'refused')
        self.assertFalse(self.calls)

    def test_decoder_recursion_refuses_config_and_retains_actual_process_facts(self):
        from task_tower.beads_admission import _production_runner
        # Decoder recursion thresholds vary across supported Python versions.
        # Force that failure at the decoder boundary, preserving a real process.
        with patch('task_tower.beads_admission.json.loads', side_effect=RecursionError):
            self.assertEqual(self.observe()['outcome'], 'refused')
            data, receipt = _production_runner('beads_ready', [sys.executable, '-c',
                "print('[]')"], self.root, 10, dict(os.environ))
        self.assertIsNone(data)
        self.assertEqual(receipt['status'], 'passed')
        self.assertTrue(receipt['cleanup_confirmed'])
        self.assertFalse(receipt['stdout_tail_unknown'])

    def test_unsafe_metadata_and_source_links_are_refused(self):
        (self.database / '.beads/metadata.json').write_text(
            '{"backend":"dolt","dolt_mode":"server"}', encoding='utf-8')
        self.assertEqual(self.observe()['outcome'], 'refused')
        self.assertFalse(any(c[0].startswith('beads_') for c in self.calls))

    def test_common_budget_reserves_supervisor_cleanup_and_stops_after_elapsed_reads(self):
        current = [0.0]
        def runner(operation, argv, cwd, timeout, env):
            current[0] += 9
            return self.runner(operation, argv, cwd, timeout, env)
        from task_tower.beads_admission import observe
        with patch('task_tower.beads_admission.sys.platform','win32'):
            packet = observe(self.config,'fixture','tt-fixture.1', runner=runner, clock=lambda:current[0])
        self.assertEqual(packet['outcome'], 'unknown')
        self.assertEqual(len(self.calls),3)
        self.assertFalse(any(c[0].startswith('beads_') for c in self.calls))

    def test_unauthorized_bead_stops_before_any_subprocess(self):
        self.policy['projects'][0]['allowed_beads'] = ['tt-other']
        self.write_config()
        self.assertEqual(self.observe()['outcome'], 'refused')
        self.assertFalse(self.calls)

    def test_missing_duplicate_overflow_claimed_container_and_inconsistent_rows_refuse(self):
        variants = [[], [ROW, ROW], [dict(ROW, id='tt-'+str(i)) for i in range(1001)],
                    [dict(ROW, assignee='worker')], [dict(ROW, status='deferred')],
                    [dict(ROW, issue_type='epic')], [dict(ROW, issue_type=None)],
                    [dict(ROW, assignee=7)], [dict(ROW, status=None)]]
        for rows in variants:
            self.values['beads_ready'] = rows
            with self.subTest(rows=rows[:2]):
                self.assertEqual(self.observe()['outcome'], 'refused')
        self.values['beads_ready'] = [ROW]
        self.values['beads_show'] = [dict(ROW, issue_type='bug')]
        self.assertEqual(self.observe()['outcome'], 'refused')

    def test_null_and_empty_assignees_normalize_and_prose_does_not_change_digest(self):
        first = self.observe()
        self.values['beads_show'] = [dict(ROW, assignee=None, title='different private prose')]
        self.values['beads_ready'] = [dict(ROW, assignee='')]
        second = self.observe()
        self.assertEqual(second['outcome'], 'eligible_observation')
        self.assertEqual(first['input_digest'], second['input_digest'])

    def test_unsafe_git_configuration_refuses_before_beads_or_object_reads(self):
        for setting in ('filter.evil.clean\nPRIVATE_COMMAND\0', 'core.fsmonitor\nPRIVATE_COMMAND\0',
                        'remote.origin.promisor\ntrue\0', 'extensions.partialclone\norigin\0',
                        'core.sparsecheckout\ntrue\0', 'include.path\nPRIVATE_PATH\0'):
            self.calls.clear()
            self.values['git_config'] = setting
            self.assertEqual(self.observe()['outcome'], 'refused')
            self.assertEqual([c[0] for c in self.calls], ['git_config'])

    def test_source_pin_dirty_gitlink_and_observed_mutation_refuse(self):
        for operation, value in [('git_head', 'c'*40), ('git_tree', 'bad'),
                                 ('git_status', '?? private.txt\n'),
                                 ('git_index', '160000 '+HEAD+' 0\tsub\0'),
                                 ('git_toplevel', str(self.root))]:
            old = self.values[operation]
            self.values[operation] = value
            self.assertEqual(self.observe()['outcome'], 'refused')
            self.values[operation] = old
        heads = iter([HEAD, 'c'*40])
        self.values['git_head'] = lambda: next(heads)
        self.assertEqual(self.observe()['outcome'], 'refused')

    def test_unknown_cleanup_eof_capture_and_deadline_never_eligible(self):
        for change in ({'cleanup_confirmed': False}, {'stdout_tail_unknown': True},
                       {'stderr_truncated': True}, {'status': 'timeout'}, {'duration_seconds': float('nan')}):
            self.process_changes = change
            self.assertEqual(self.observe()['outcome'], 'unknown')
        self.process_changes = {}
        ticks = iter([0, 31])
        self.assertEqual(self.observe(clock=lambda: next(ticks))['outcome'], 'unknown')

    def test_environment_and_git_arguments_prevent_effects(self):
        with patch.dict(os.environ, {'gH_tOkEn':'PRIVATE', 'BD_X':'PRIVATE', 'GIT_CONFIG':'PRIVATE',
                                     'DOLT_X':'PRIVATE', 'BEADS_X':'PRIVATE'}):
            self.observe()
        for operation, argv, cwd, timeout, env in self.calls:
            self.assertLessEqual(timeout, 10 if operation.startswith('git_') else 30)
            self.assertNotIn('PRIVATE', json.dumps(env))
            if operation.startswith('git_'):
                self.assertIn('--no-optional-locks', argv)
                self.assertIn('core.fsmonitor=false', argv)
                self.assertEqual(env['GIT_NO_LAZY_FETCH'], '1')
                self.assertEqual(env['GIT_CONFIG_GLOBAL'], 'NUL')

    def test_exceptions_and_cli_exit_codes_do_not_leak_private_text(self):
        from task_tower.beads_admission import main
        for outcome, code in [('eligible_observation', 0), ('refused', 2), ('unknown', 3)]:
            output = io.StringIO()
            with patch('task_tower.beads_admission.observe', return_value={'outcome':outcome}), contextlib.redirect_stdout(output):
                self.assertEqual(main(['--config', str(self.config), '--project','fixture','--bead','tt-fixture.1']), code)
            self.assertEqual(json.loads(output.getvalue())['outcome'], outcome)
        self.values['git_config'] = lambda: (_ for _ in ()).throw(OSError('PRIVATE_PATH_TOKEN'))
        self.assertNotIn('PRIVATE', json.dumps(self.observe()))

    def test_cli_parse_errors_are_fixed_and_never_echo_private_arguments(self):
        from task_tower.beads_admission import main
        for args in (['--config','PRIVATE_PATH','--project','fixture','--bead','tt-fixture.1','--PRIVATE_PROSE'],
                     ['--config','PRIVATE_PATH']):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    code = main(args)
                except SystemExit as error:
                    code = error.code
            self.assertEqual(code, 2)
            self.assertNotIn('PRIVATE', stdout.getvalue()+stderr.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())['reason'], 'invalid_arguments')

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_real_git_filters_fsmonitor_and_promisor_are_refused_without_marker_effect(self):
        from task_tower.beads_admission import observe
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.source, env=env, capture_output=True, timeout=10, check=True).stdout.decode('utf-8').strip()
        git('init')
        git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','fixture')
        self.policy['projects'][0]['expected_head'] = git('rev-parse','HEAD')
        self.write_config()
        marker = self.root/'marker'
        command = 'echo PRIVATE > "'+str(marker)+'"'
        for key, value in [('filter.evil.clean',command), ('core.fsmonitor',command), ('remote.origin.promisor','true')]:
            git('config', '--local', key, value)
            with patch('task_tower.beads_admission.sys.platform','win32'):
                packet = observe(self.config,'fixture','tt-fixture.1')
            self.assertEqual(packet['outcome'],'refused')
            self.assertFalse(marker.exists())
            self.assertFalse(any(p['operation'].startswith('beads_') for p in packet['processes']))
            git('config','--local','--unset',key)

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_real_safe_git_snapshot_with_fixture_beads_and_dirty_recheck(self):
        from task_tower.beads_admission import _production_runner, observe
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.source, env=env, capture_output=True, timeout=10, check=True).stdout.decode('utf-8').strip()
        git('init')
        git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','fixture')
        self.policy['projects'][0]['expected_head'] = git('rev-parse','HEAD')
        self.write_config()
        mutate = [False]
        def runner(operation, argv, cwd, timeout, env):
            if operation.startswith('git_'):
                return _production_runner(operation, argv, cwd, timeout, env)
            if operation == 'beads_show' and mutate[0]:
                (self.source/'untracked.txt').write_text('fixture',encoding='utf-8')
            return self.runner(operation, argv, cwd, timeout, env)
        with patch('task_tower.beads_admission.sys.platform','win32'):
            clean = observe(self.config,'fixture','tt-fixture.1',runner=runner)
            self.assertEqual(clean['outcome'],'eligible_observation')
            self.assertTrue(all(p['cleanup_confirmed'] and p['eof_confirmed'] for p in clean['processes']))
            mutate[0] = True
            dirty = observe(self.config,'fixture','tt-fixture.1',runner=runner)
        self.assertEqual(dirty['outcome'],'refused')

    def _assert_hidden_index_modification_refused(self, flag):
        from task_tower.beads_admission import _production_runner, observe
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.source, env=env,
                                  capture_output=True, timeout=10, check=True).stdout.decode('utf-8').strip()
        git('init')
        tracked = self.source / 'tracked.txt'
        tracked.write_text('committed fixture\n', encoding='utf-8')
        git('add', '--', 'tracked.txt')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-m', 'synthetic tracked fixture')
        self.policy['projects'][0]['expected_head'] = git('rev-parse', 'HEAD')
        self.write_config()
        def runner(operation, argv, cwd, timeout, env):
            if operation.startswith('git_'):
                return _production_runner(operation, argv, cwd, timeout, env)
            return self.runner(operation, argv, cwd, timeout, env)
        with patch('task_tower.beads_admission.sys.platform', 'win32'):
            clean = observe(self.config, 'fixture', 'tt-fixture.1', runner=runner)
        self.assertEqual(clean['outcome'], 'eligible_observation')
        self.calls.clear()
        git('update-index', flag, '--', 'tracked.txt')
        tracked.write_text('modified fixture concealed from status\n', encoding='utf-8')
        # Reproduce the reason status alone cannot prove the required clean tree.
        self.assertEqual(git('status', '--porcelain=v1', '--untracked-files=all'), '')
        with patch('task_tower.beads_admission.sys.platform', 'win32'):
            packet = observe(self.config, 'fixture', 'tt-fixture.1', runner=runner)
        self.assertEqual(packet['outcome'], 'refused')
        self.assertFalse(any(c[0].startswith('beads_') for c in self.calls))

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_assume_unchanged_modified_index_refuses_before_beads(self):
        self._assert_hidden_index_modification_refused('--assume-unchanged')

    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_skip_worktree_modified_index_refuses_before_beads(self):
        self._assert_hidden_index_modification_refused('--skip-worktree')
