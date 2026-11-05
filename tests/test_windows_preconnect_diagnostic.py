import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import uuid

from tools import windows_preconnect_diagnostic as diagnostic


class DiagnosticTests(unittest.TestCase):
    def test_observation_preserves_return_and_same_exception(self):
        observer = diagnostic.PreconnectObservation()
        host = SimpleNamespace(owner=str(uuid.uuid4()), journal=SimpleNamespace())
        marker = object()
        self.assertIs(observer.callback(lambda unused: marker, host), marker)
        error = ValueError('PRIVATE prose and C:/private/file')
        def fail(unused):
            raise error
        with self.assertRaises(ValueError) as caught:
            observer.callback(fail, host)
        self.assertIs(caught.exception, error)
        report = observer.report()
        self.assertEqual([r['sequence'] for r in report['records']], [1, 2])
        self.assertTrue(report['records'][1]['failed'])
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_safe_and_outside_safe_preconnect_are_attributed(self):
        observer = diagnostic.PreconnectObservation()
        journal = SimpleNamespace(_operation_deadline=time.monotonic() + 1)
        host = SimpleNamespace(owner=str(uuid.uuid4()), journal=journal)
        with tempfile.TemporaryDirectory() as directory:
            leaf = Path(directory) / 'leaf'
            leaf.touch()
            def callback(unused):
                with observer.installed():
                    def safe(unused):
                        leaf.lstat()
                        time.sleep(.02)
                    observer.safe(safe, journal)
                    time.sleep(.03)
                    observer.preconnect(journal)
                return False
            self.assertFalse(observer.callback(callback, host))
        record = observer.report()['records'][0]
        self.assertEqual(record['safe_count'], 1)
        self.assertEqual(record['lstat_count'], 1)
        self.assertGreater(record['preconnect_wall'], record['safe_wall'] + .005)
        self.assertGreater(record['outside_safe_preconnect_wall'], .005)
        self.assertGreater(record['remaining_before_safe'], record['remaining_after_safe'])
        self.assertGreater(record['remaining_after_safe'], record['remaining_preconnect'])

    def test_record_cap_keeps_slowest_and_failure_without_private_values(self):
        observer = diagnostic.PreconnectObservation()
        host = SimpleNamespace(owner='not-a-uuid PRIVATE', journal=SimpleNamespace())
        for index in range(100):
            def callback(unused):
                if index == 0:
                    time.sleep(.01)
                if index == 1:
                    raise RuntimeError('PRIVATE')
            try:
                observer.callback(callback, host)
            except RuntimeError:
                pass
        report = observer.report()
        self.assertEqual(len(report['records']), 64)
        self.assertEqual(report['omitted_records'], 36)
        self.assertIn(1, [r['sequence'] for r in report['records']])
        self.assertIn(2, [r['sequence'] for r in report['records']])
        encoded = diagnostic.encode_report(report)
        self.assertLessEqual(len(encoded), 65536)
        self.assertNotIn(b'PRIVATE', encoded)

    def test_receipt_fails_closed_for_missing_skipped_failed_or_uncontained(self):
        process = dict(status='passed', exit_code=0, started=True,
                       cleanup_confirmed=True, stdout_tail_unknown=False,
                       stderr_tail_unknown=False)
        child = dict(case=diagnostic.CASE, tests_run=1, failures=0, errors=0,
                     skipped=0, unexpected_successes=0, observation=diagnostic.PreconnectObservation().report())
        # No callback evidence is not an executed native diagnostic.
        self.assertFalse(diagnostic.receipt_passed(process, child))
        observer = diagnostic.PreconnectObservation()
        journal = SimpleNamespace()
        def measured(unused):
            observer.preconnect(journal)
            return False
        observer.callback(measured, SimpleNamespace(owner=str(uuid.uuid4()), journal=journal))
        child['observation'] = observer.report()
        self.assertTrue(diagnostic.receipt_passed(process, child))
        self.assertFalse(diagnostic.receipt_passed(process, None))
        for key, value in [('status', 'timeout'), ('cleanup_confirmed', False),
                           ('stdout_tail_unknown', True), ('stderr_tail_unknown', True),
                           ('exit_code', 1), ('started', False)]:
            self.assertFalse(diagnostic.receipt_passed(dict(process, **{key: value}), child))
        for key in ('skipped', 'failures', 'errors', 'unexpected_successes'):
            self.assertFalse(diagnostic.receipt_passed(process, dict(child, **{key: 1})))
        self.assertFalse(diagnostic.receipt_passed(process, dict(child, tests_run=0)))
        self.assertFalse(diagnostic.receipt_passed(process, dict(child, private='PRIVATE')))

    def test_native_result_never_formats_traceback_or_skip_prose(self):
        result = diagnostic.ScalarResult()
        case = unittest.FunctionTestCase(lambda: None)
        error = RuntimeError('PRIVATE task/environment/path')
        result.startTest(case)
        result.addError(case, (RuntimeError, error, None))
        result.addSkip(case, 'PRIVATE skip reason')
        report = result.scalars()
        self.assertEqual(report['errors'], 1)
        self.assertEqual(report['skipped'], 1)
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertEqual(result.errors, [])

    def test_installed_wrappers_preserve_original_wait_failure_and_restore(self):
        from task_tower import pipeline_journal
        original_safe = pipeline_journal.PipelineJournal._safe
        original_wait = pipeline_journal.PipelineJournal._wait_seconds
        with tempfile.TemporaryDirectory() as directory:
            journal = pipeline_journal.PipelineJournal(Path(directory) / 'synthetic.db')
            observer = diagnostic.PreconnectObservation(directory)
            host = SimpleNamespace(owner=str(uuid.uuid4()), journal=journal)
            with observer.installed():
                with journal.operation_deadline(time.monotonic() - 1):
                    with self.assertRaisesRegex(ValueError, 'operation deadline exhausted'):
                        observer.callback(lambda unused: journal._wait_seconds(), host)
        record = observer.report()['records'][0]
        self.assertTrue(record['failed'])
        self.assertTrue(record['wait_failed_before_connect'])
        self.assertFalse(record['connected'])
        self.assertLess(record['remaining_preconnect'], 0)
        self.assertIs(pipeline_journal.PipelineJournal._safe, original_safe)
        self.assertIs(pipeline_journal.PipelineJournal._wait_seconds, original_wait)

    def test_child_mode_refuses_direct_execution_without_parent(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'child.json'
            with patch.dict(diagnostic.os.environ, {'RUNNER_TEMP': directory}, clear=True), \
                    patch.object(diagnostic, '_child', side_effect=AssertionError('native must not run')) as child:
                self.assertEqual(diagnostic.main(['--child', '--output', str(output)]), 1)
                child.assert_not_called()
            self.assertFalse(output.exists())

    def test_parent_publishes_only_validated_report_and_requires_real_process_receipt(self):
        from unittest.mock import patch
        journal = SimpleNamespace()
        observer = diagnostic.PreconnectObservation()
        observer.callback(lambda unused: observer.preconnect(journal),
                          SimpleNamespace(owner=str(uuid.uuid4()), journal=journal))
        native = dict(case=diagnostic.CASE, tests_run=1, failures=0, errors=0,
                      skipped=0, unexpected_successes=0, observation=observer.report())
        facts = dict(status='passed', exit_code=0, started=True, cleanup_confirmed=True,
                     stdout_tail_unknown=False, stderr_tail_unknown=False,
                     stdout_bytes=0, stderr_bytes=0, duration_seconds=.1, argv=['PRIVATE'])
        def run(command, cwd, timeout, env, **kwargs):
            self.assertEqual(timeout, 240)
            self.assertIn('--child', command)
            self.assertFalse(any(k.upper() in ('GH_TOKEN', 'GITHUB_TOKEN') for k in env))
            self.assertEqual(env['_TT_PRECONNECT_PARENT_PID'], str(diagnostic.os.getpid()))
            self.assertFalse(kwargs['cancel_requested']())
            Path(command[-1]).write_bytes(diagnostic.encode_report(native))
            return facts
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            with patch.dict(diagnostic.os.environ, {'RUNNER_TEMP': directory, 'gH_tOkEn': 'PRIVATE'}), \
                    patch.object(diagnostic, '_source_sha', return_value='a' * 40), \
                    patch.object(diagnostic.processes, 'run_command', side_effect=run):
                self.assertEqual(diagnostic.main(['--output', str(output)]), 0)
            report = json.loads(output.read_bytes())
            self.assertEqual(report['source_sha'], 'a' * 40)
            self.assertTrue(report['passed'])
            self.assertNotIn('PRIVATE', json.dumps(report))
            self.assertLessEqual(output.stat().st_size, 65536)

    def test_parent_rejects_private_or_missing_child_reports_and_preserves_sanitized_failure(self):
        from unittest.mock import patch
        facts = dict(status='passed', exit_code=0, started=True, cleanup_confirmed=True,
                     stdout_tail_unknown=False, stderr_tail_unknown=False)
        for mode in ('missing', 'private', 'exception'):
            def run(command, *args, **kwargs):
                if mode == 'private':
                    Path(command[-1]).write_text('{"secret":"PRIVATE"}', encoding='utf-8')
                if mode == 'exception':
                    raise OSError('PRIVATE path and environment')
                return facts
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'report.json'
                with patch.dict(diagnostic.os.environ, {'RUNNER_TEMP': directory}), \
                        patch.object(diagnostic, '_source_sha', return_value='a' * 40), \
                        patch.object(diagnostic.processes, 'run_command', side_effect=run):
                    self.assertEqual(diagnostic.main(['--output', str(output)]), 1)
                self.assertTrue(output.exists(), 'supervisor exceptions must preserve sanitized failure evidence')
                report = json.loads(output.read_bytes())
                self.assertFalse(report['passed'])
                self.assertIsNone(report['child'])
                self.assertNotIn('PRIVATE', json.dumps(report))

    def test_original_safe_exception_and_lstat_error_are_not_replaced(self):
        observer = diagnostic.PreconnectObservation()
        journal = SimpleNamespace()
        host = SimpleNamespace(owner=str(uuid.uuid4()), journal=journal)
        error = PermissionError('PRIVATE')
        def safe(unused):
            raise error
        def callback(unused):
            return observer.safe(safe, journal)
        with self.assertRaises(PermissionError) as caught:
            observer.callback(callback, host)
        self.assertIs(caught.exception, error)
        with tempfile.TemporaryDirectory() as directory, observer.installed():
            missing = Path(directory) / 'missing'
            with self.assertRaises(FileNotFoundError):
                observer.callback(lambda unused: missing.lstat(), host)
        report = observer.report()
        self.assertTrue(all(r['failed'] for r in report['records']))
        self.assertEqual(report['records'][1]['lstat_count'], 1)
        self.assertNotIn('PRIVATE', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
