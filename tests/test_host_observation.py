"""Passive fixture diagnostics: changing an original result is always a bug."""
import argparse
import contextlib
import importlib
import json
from pathlib import Path
import tempfile
import threading
import sqlite3
import types
import unittest
from unittest.mock import patch

from task_tower import pipeline


class HostObservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def observation(self):
        # Turn missing feature into an explicit RED assertion, not an import error.
        try:
            module = importlib.import_module('tests.fixtures.host_observation')
        except ModuleNotFoundError:
            self.fail('HostObservation fixture helper has not been implemented')
        return module.HostObservation(self.root)

    @contextlib.contextmanager
    def host_environment(self, runner, status=None):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(pipeline, '_require_native_execution'))
            stack.enter_context(patch.object(pipeline, '_fixed', return_value=['fixture']))
            stack.enter_context(patch.object(pipeline.processes, 'run_command', side_effect=runner))
            if status is not None:
                stack.enter_context(patch.object(pipeline.PipelineJournal, 'status', status))
            yield

    def host(self, kind='_action', root=None):
        return pipeline._Host(argparse.Namespace(journal=(root or self.root) / 'watch.db'),
                              kind, 30, threading.Event())

    def test_callback_exception_is_captured_before_runner_swallows_it(self):
        error = ValueError('private exception prose ghp_NEVER_EXPORT')
        reads = []

        def status(journal):
            reads.append(journal)
            raise error

        def runner(*args, cancel_requested, **kwargs):
            try:
                cancel_requested()
            except ValueError as caught:
                self.assertIs(caught, error)
            return dict(status='failed', cleanup_confirmed=False, exit_code=7)

        with self.host_environment(runner, status), self.observation() as observation:
            host = self.host()
            self.assertTrue(host.done.wait(2))
            self.assertEqual(host.outcome['exit_code'], 7)
            host.close()
        report = json.loads(observation.message())
        self.assertEqual(len(reads), 1)
        self.assertEqual(report['errors'][0]['type'], 'ValueError')
        self.assertGreaterEqual(report['hosts'][0]['callback_duration_seconds'], 0)
        self.assertFalse(report['hosts'][0]['outcome']['cleanup_confirmed'])
        self.assertIsNone(report['hosts'][0]['result'])
        self.assertNotIn('private', observation.message())
        self.assertNotIn('ghp_', observation.message())

    def test_original_status_row_result_and_close_are_observed_faithfully(self):
        row = dict(run_id='01234567-89ab-4cde-8fab-0123456789ab', owner_id=None,
                   deadline_at=None, updated_at='2020-01-01T00:00:00+00:00',
                   cancel_requested=False, state='executing', stage='test', generation=7,
                   reason='owner_dead', process_count=7, request='NEVER_EXPORT')
        reads = []
        result = dict(run_id=row['run_id'], status='ready', stage='test', generation=7,
                      reason=None, input_sha256=None, receipt_sha256=None, effect_sha256=None)
        outcome = dict(status='passed', cleanup_confirmed=True, exit_code=0, stdout='NEVER_EXPORT')

        def status(journal):
            reads.append(journal)
            return dict(runs=[dict(row)])

        def runner(argv, *args, cancel_requested, **kwargs):
            row['owner_id'] = argv[argv.index('--host-owner') + 1]
            self.assertFalse(cancel_requested())
            row['state'] = 'unknown'  # Report must keep original returned row.
            Path(argv[argv.index('--host-result') + 1]).write_text(json.dumps(result), encoding='utf-8')
            return outcome

        with self.host_environment(runner, status), self.observation() as observation:
            host = self.host()
            self.assertTrue(host.done.wait(2))
            self.assertIs(host.outcome, outcome)
            self.assertEqual(host.result, result)
            path = host.path
            host.close()
            self.assertFalse(path.exists())
        report = json.loads(observation.message())
        saved = report['hosts'][0]
        self.assertEqual(saved['owned_run']['state'], 'executing')
        self.assertEqual(saved['owned_run']['process_count'], 7)
        self.assertEqual(saved['result']['status'], 'ready')
        self.assertFalse(saved['stop_requested'])
        self.assertIsNone(saved['budget_deadline'])
        self.assertEqual(len(reads), 1)
        self.assertNotIn('NEVER_EXPORT', observation.message())

    def test_shutdown_false_and_exception_identity_survive(self):
        error = OSError('NEVER_EXPORT')
        with patch.object(pipeline, '_shutdown', return_value=False), self.observation() as observation:
            self.assertIs(pipeline._shutdown({}, argparse.Namespace(path=self.root / 'watch.db'), {}), False)
        self.assertIs(json.loads(observation.message())['shutdowns'][0]['result'], False)
        with patch.object(pipeline, '_shutdown', side_effect=error), self.observation() as observation:
            with self.assertRaises(OSError) as caught:
                pipeline._shutdown({}, argparse.Namespace(path=self.root / 'watch.db'), {})
        self.assertIs(caught.exception, error)
        self.assertEqual(json.loads(observation.message())['errors'][0]['type'], 'OSError')

    def test_lazy_message_reads_only_when_unittest_formats_failure(self):
        calls = []
        journal = argparse.Namespace(path=self.root / 'watch.db',
                                     status=lambda: calls.append(True) or dict(runs=[]))
        with self.observation() as observation:
            message = observation.lazy_message(journal)
            self.assertEqual('ready', 'ready', message)
            self.assertEqual(calls, [])
            with self.assertRaises(AssertionError) as caught:
                self.assertEqual('unknown', 'ready', message)
            self.assertIn('"hosts"', str(caught.exception))
            self.assertEqual(calls, [True])

    def test_caps_valid_ascii_json_and_no_private_values(self):
        def runner(*args, cancel_requested, **kwargs):
            cancel_requested()
            return dict(status='failed', cleanup_confirmed=False)

        def status(journal):
            raise ValueError('ghp_' + 'secret' * 10000 + '\u2603')

        with self.host_environment(runner, status), self.observation() as observation:
            for _ in range(45):
                host = self.host()
                self.assertTrue(host.done.wait(2))
                host.close()
        message = observation.message()
        report = json.loads(message)
        self.assertLessEqual(len(message.encode('ascii')), 16384)
        self.assertLessEqual(len(report['hosts']), 32)
        self.assertLessEqual(len(report['errors']), 16)
        self.assertGreaterEqual(report['omitted_hosts'], 13)
        self.assertGreaterEqual(report['omitted_errors'], 29)
        self.assertNotIn('secret', message)

    def test_hooks_restore_without_waiting_for_inflight_callback(self):
        entered, release = threading.Event(), threading.Event()
        originals = (pipeline._Host.__init__, pipeline._Host.run, pipeline._Host.cancelled,
                     pipeline._Host.close, pipeline.PipelineJournal.status, pipeline._shutdown)

        def status(journal):
            entered.set()
            release.wait(2)
            return dict(runs=[])

        def runner(*args, cancel_requested, **kwargs):
            self.assertFalse(cancel_requested())
            return dict(status='failed', cleanup_confirmed=True)

        with self.host_environment(runner, status):
            with self.observation() as observation:
                host = self.host()
                self.assertTrue(entered.wait(2))
            self.assertFalse(host.done.is_set())
            release.set()
            self.assertTrue(host.done.wait(2))
            host.close()
        self.assertEqual(originals, (pipeline._Host.__init__, pipeline._Host.run, pipeline._Host.cancelled,
                                    pipeline._Host.close, pipeline.PipelineJournal.status, pipeline._shutdown))

    def test_failure_message_refuses_journal_outside_synthetic_fixture(self):
        reads = []
        with tempfile.TemporaryDirectory() as outside, self.observation() as observation:
            journal = argparse.Namespace(path=Path(outside) / 'private.db',
                                         status=lambda: reads.append(True) or dict(runs=[]))
            report = json.loads(observation.message(journal))
        self.assertEqual(reads, [])
        self.assertTrue(report['failure_time_journal_refused'])

    def test_report_prunes_whole_records_and_never_formats_disallowed_values(self):
        class Unprintable:
            def __str__(self):
                raise AssertionError('must not format private values')

        row = dict(run_id='01234567-89ab-4cde-8fab-0123456789ab', owner_id='11234567-89ab-4cde-8fab-0123456789ab',
                   state='unknown', reason='owner_dead', stage='test', generation=7, process_count=7,
                   input_sha256='a' * 64, receipt_sha256='b' * 64, effect_sha256='c' * 64,
                   updated_at='2026-11-05T00:00:00.123456+00:00', deadline_at='2026-11-05T00:00:00.123456+00:00',
                   created_at='2026-11-05T00:00:00.123456+00:00', started_at='2026-11-05T00:00:00.123456+00:00',
                   finished_at='2026-11-05T00:00:00.123456+00:00', request=Unprintable(), pid=Unprintable())
        journal = argparse.Namespace(path=self.root / 'watch.db', status=lambda: dict(runs=[row] * 100))
        with self.observation() as observation:
            report_text = observation.message(journal)
        report = json.loads(report_text)
        self.assertLessEqual(len(report_text.encode('ascii')), 16384)
        self.assertTrue(report['truncated'])
        self.assertGreater(report['omitted_failure_time_runs'], 68)
        self.assertEqual(report['failure_time_runs'][0]['process_count'], 7)
        self.assertNotIn('pid', report['failure_time_runs'][0])

    def test_bookkeeping_failure_cannot_change_original_callback_return(self):
        seen = []

        def runner(*args, cancel_requested, **kwargs):
            seen.append(cancel_requested())
            return dict(status='failed', cleanup_confirmed=True)

        with self.host_environment(runner, lambda journal: dict(runs=[])):
            with self.observation() as observation:
                with patch.object(observation, '_callback', side_effect=ValueError('private')):
                    host = self.host()
                    self.assertTrue(host.done.wait(2))
                    host.close()
        self.assertEqual(seen, [False])
        self.assertEqual(host.outcome['status'], 'failed')
        self.assertGreaterEqual(json.loads(observation.message())['observation_errors'], 1)

    def test_host_outside_fixture_is_not_captured(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.host_environment(lambda *a, **k: dict(status='failed', cleanup_confirmed=True)):
                with self.observation() as observation:
                    host = self.host(root=Path(outside))
                    self.assertTrue(host.done.wait(2))
                    host.close()
        self.assertEqual(json.loads(observation.message())['hosts'], [])

    def test_missing_outcome_remains_missing_and_restores_on_body_exception(self):
        originals = (pipeline._Host.__init__, pipeline._Host.run, pipeline._Host.cancelled,
                     pipeline._Host.close, pipeline.PipelineJournal.status, pipeline._shutdown)
        error = RuntimeError('private body error')
        with self.host_environment(lambda *a, **k: (_ for _ in ()).throw(OSError('private runner error'))):
            with self.assertRaises(RuntimeError) as caught:
                with self.observation() as observation:
                    host = self.host()
                    self.assertTrue(host.done.wait(2))
                    self.assertIsNone(host.outcome)
                    self.assertIsNone(host.result)
                    host.close()
                    raise error
        self.assertIs(caught.exception, error)
        saved = json.loads(observation.message())['hosts'][0]
        self.assertIsNone(saved['outcome'])
        self.assertIsNone(saved['result'])
        self.assertEqual(originals, (pipeline._Host.__init__, pipeline._Host.run, pipeline._Host.cancelled,
                                    pipeline._Host.close, pipeline.PipelineJournal.status, pipeline._shutdown))

    def test_error_locations_use_real_raise_site_and_callback_identity(self):
        seen, errors = [], []

        def status(journal):
            if not seen:
                seen.append(True)
                return dict(runs=[])
            try:
                with journal.operation_deadline(0):
                    journal._wait_seconds()
            except ValueError as error:
                errors.append(error)
                raise

        def runner(*args, cancel_requested, **kwargs):
            self.assertFalse(cancel_requested())
            try:
                cancel_requested()
            except ValueError as error:
                self.assertIs(error, errors[0])
            return dict(status='failed', cleanup_confirmed=True)

        with self.host_environment(runner, status), self.observation() as observation:
            host = self.host()
            self.assertTrue(host.done.wait(2))
            host.close()
        report = json.loads(observation.message())
        record = report['errors'][0]
        self.assertIn('host_owner_id', record)
        self.assertEqual(record['host_owner_id'], host.owner)
        self.assertEqual(record['callback_sequence'], 2)
        self.assertEqual(record['locations'][-1]['module'], 'task_tower.pipeline_journal')
        self.assertEqual(record['locations'][-1]['function'], 'PipelineJournal._wait_seconds')
        self.assertGreater(record['locations'][-1]['line'], 0)
        self.assertEqual(report['hosts'][0]['callback_count'], 2)

    def test_explicit_causes_are_bounded_and_implicit_context_is_private(self):
        private = 'GhP_NEVER_EXPORT_\u2603'
        sqlite_error = sqlite3.OperationalError(private)
        sqlite_error.sqlite_errorcode = 5
        root = ValueError(private)
        root.__cause__ = sqlite_error
        sqlite_error.__cause__ = RuntimeError(private)
        sqlite_error.__cause__.__cause__ = OSError(private)
        sqlite_error.__cause__.__cause__.__cause__ = TypeError(private)
        root.__context__ = PermissionError(private)

        def status(journal):
            raise root

        def runner(*args, cancel_requested, **kwargs):
            try:
                cancel_requested()
            except ValueError as caught:
                self.assertIs(caught, root)
            return dict(status='failed', cleanup_confirmed=True)

        with self.host_environment(runner, status), self.observation() as observation:
            host = self.host()
            self.assertTrue(host.done.wait(2))
            host.close()
        message = observation.message()
        record = json.loads(message)['errors'][0]
        self.assertIn('causes', record)
        self.assertEqual([cause['type'] for cause in record['causes']],
                         ['sqlite3.OperationalError', 'RuntimeError', 'OSError'])
        self.assertEqual(record['causes'][0]['sqlite_errorcode'], 5)
        self.assertTrue(record['causes_truncated'])
        self.assertNotIn('PermissionError', message)
        self.assertNotIn('NEVER_EXPORT', message)
        self.assertNotIn(str(self.root), message)
        self.assertNotIn('HostObservationTests', message)
        self.assertNotIn('"status"', json.dumps(record['locations']))
        message.encode('ascii')

    def test_cyclic_error_chain_unknown_types_and_invalid_sqlite_code_are_safe(self):
        class PrivateError(Exception):
            def __str__(self):
                raise AssertionError('must not format exception')

        root = ValueError('private')
        cause = PrivateError('private')
        root.__cause__ = cause
        cause.__cause__ = root
        cause.sqlite_errorcode = 'GhP_NEVER_EXPORT'
        with self.observation() as observation:
            observation._error('cancelled', root)
        record = json.loads(observation.message())['errors'][0]
        self.assertIn('causes', record)
        self.assertEqual([child['type'] for child in record['causes']], ['Exception'])
        self.assertTrue(record['causes_truncated'])
        self.assertNotIn('sqlite_errorcode', record['causes'][0])

    def test_error_discriminator_bookkeeping_failure_preserves_exception_identity(self):
        root = ValueError('private')
        caught_errors = []

        def runner(*args, cancel_requested, **kwargs):
            try:
                cancel_requested()
            except ValueError as error:
                caught_errors.append(error)
            return dict(status='failed', cleanup_confirmed=True)

        def status(journal):
            raise root

        with self.host_environment(runner, status), self.observation() as observation:
            with patch.object(observation, '_error', side_effect=TypeError('private bookkeeping failure')):
                host = self.host()
                self.assertTrue(host.done.wait(2))
                host.close()
        self.assertEqual(caught_errors, [root])
        self.assertGreater(json.loads(observation.message())['observation_errors'], 0)

    def test_traceback_traversal_and_retained_locations_and_json_remain_bounded(self):
        journal = pipeline.PipelineJournal(self.root / 'synthetic.db')
        with journal.operation_deadline(0):
            try:
                journal._wait_seconds()
            except ValueError as caught:
                frame = caught.__traceback__.tb_next
        # Repeat a real production frame without recursion/native processes/DB I/O.
        traceback = None
        for _ in range(40):
            traceback = types.TracebackType(traceback, frame.tb_frame, frame.tb_lasti, frame.tb_lineno)
        error = ValueError('GhP_NEVER_EXPORT')
        error.__traceback__ = traceback
        cause = error
        for _ in range(3):
            child = ValueError('GhP_NEVER_EXPORT')
            child.__traceback__ = traceback
            cause.__cause__ = child
            cause = child
        with self.observation() as observation:
            observation._error('cancelled', error)
            first = json.loads(observation.message())['errors'][0]
            self.assertEqual(len(first['locations']), 8)
            self.assertEqual(first['omitted_locations'], 24)
            self.assertTrue(first['traceback_truncated'])
            for _ in range(24):
                observation._error('cancelled', error)
        message = observation.message()
        report = json.loads(message)
        self.assertLessEqual(len(message.encode('ascii')), 16384)
        self.assertTrue(report['truncated'])
        self.assertGreater(report['omitted_errors'], 9)
        self.assertNotIn('NEVER_EXPORT', message)

    def test_sqlite_error_code_excludes_bool_string_and_oversize_values(self):
        with self.observation() as observation:
            for code in (True, 'GhP_NEVER_EXPORT', 2**100):
                error = sqlite3.OperationalError('private')
                error.sqlite_errorcode = code
                observation._error('cancelled', error)
        records = json.loads(observation.message())['errors']
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertEqual(record['type'], 'sqlite3.OperationalError')
            self.assertNotIn('sqlite_errorcode', record)
