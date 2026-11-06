"""Observer safety tests; these do not qualify hosted documentation validation."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import tempfile

spec = importlib.util.spec_from_file_location('pr97_diagnostic', Path(__file__).parents[1]/'tools/ci_docs_pr97_diagnostic.py')
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class DocumentationError(ValueError):
    pass


def original_module(fail=None, calls=1):
    marker = object()
    captured = []
    class Source:
        def __init__(self):
            self.deadline = diagnostic.time.monotonic()+30
            self.prose_bytes = 12
            self.capture_bytes = 21
        def git(self, *args, **kwargs):
            if fail:
                raise fail
            return module.run_command(args, marker, 19.25, env={'PRIVATE': 'SECRET'}, capture={'max_bytes_per_stream': 64})
    def run(*args, **kwargs):
        captured.append((args, kwargs))
        return {'status': 'passed', 'exit_code': 0, 'cleanup_confirmed': True,
                'stdout_bytes': 12, 'stderr_bytes': 0, 'argv': ['PRIVATE'], 'stderr': 'SECRET'}
    def broken(source, revision):
        return source.git('cat-file', 'blob', 'PRIVATE_oid', cap=64)
    def validate(*args, **kwargs):
        source = Source()
        for unused in range(calls):
            module._broken(source, 'PRIVATE_revision')
        return {'PRIVATE': 'SECRET'}
    module=SimpleNamespace(_Source=Source, run_command=run, _broken=broken, validate=validate,
                           DocumentationError=DocumentationError, MAX_SECONDS=30,
                           MAX_CAPTURE_BYTES=64*1024*1024, MAX_PROSE_BYTES=16*1024*1024,
                           MAX_OUTPUT_BYTES=16*1024*1024)
    return module, captured, marker


class DiagnosticTests(unittest.TestCase):
    def test_delegates_exact_arguments_and_restores_originals(self):
        module, captured, marker=original_module()
        original=(module._Source.git, module.run_command, module._broken)
        report=diagnostic.observe(module, '.')
        self.assertEqual(report['outcome'], 'passed')
        self.assertEqual((module._Source.git, module.run_command, module._broken), original)
        self.assertEqual(captured[0], ((('cat-file','blob','PRIVATE_oid'),marker,19.25),
            {'env':{'PRIVATE':'SECRET'},'capture':{'max_bytes_per_stream':64}}))
        self.assertEqual(report['tail'][0]['operation'], 'blob')
        self.assertTrue(report['tail'][0]['process_called'])

    def test_unknown_private_exception_is_redacted_and_preprocess_refusal_distinct(self):
        module, unused, unused2=original_module(DocumentationError('C:/PRIVATE SECRET'))
        report=diagnostic.observe(module, '.')
        self.assertEqual(report['outcome'], 'refused')
        self.assertEqual(report['error_chain'], ['documentation:unknown'])
        self.assertFalse(report['tail'][0]['process_called'])
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertNotIn('SECRET', json.dumps(report))

    def test_original_resource_refusal_is_rethrown_by_wrapper_then_observed(self):
        error=DocumentationError('resource_limit')
        module, unused, unused2=original_module(error)
        original=module.validate
        def validate(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except DocumentationError as caught:
                self.assertIs(caught,error)
                raise
        module.validate=validate
        report=diagnostic.observe(module, '.')
        self.assertEqual(report['error_chain'], ['documentation:resource_limit'])
        self.assertEqual(report['outcome'], 'refused')

    def test_bounded_tail_omission_and_no_raw_success_output(self):
        module, unused, unused2=original_module(calls=30)
        report=diagnostic.observe(module, '.')
        self.assertEqual(report['git_calls'],30)
        self.assertEqual(len(report['tail']),8)
        self.assertEqual(report['omitted_operations'],22)
        raw=diagnostic.encode_report(report)
        self.assertLessEqual(len(raw),16384)
        self.assertNotIn(b'PRIVATE',raw)
        self.assertNotIn(b'SECRET',raw)

    def test_nested_category_chain_is_bounded_and_unknown_text_private(self):
        error=DocumentationError('documentation_validation_failed')
        error.__cause__=DocumentationError('resource_limit')
        module, unused, unused2=original_module(error)
        report=diagnostic.observe(module,'.')
        self.assertEqual(report['error_chain'],['documentation:documentation_validation_failed','documentation:resource_limit'])
        error.__cause__=error
        self.assertLessEqual(len(diagnostic.error_chain(error,module)),4)

    def test_output_limit_refuses_oversize(self):
        with self.assertRaises(ValueError):
            diagnostic.encode_report({'data':'x'*16384})

    def test_observer_fault_cannot_be_misreported_as_original_refusal_or_pass(self):
        for original_error in (None,DocumentationError('resource_limit')):
            module,captured,unused=original_module(original_error)
            original=module.validate
            def classify_like(*args,**kwargs):
                try:
                    return original(*args,**kwargs)
                except ValueError:
                    return None
            module.validate=classify_like
            with mock.patch.object(diagnostic,'operation',side_effect=ValueError('PRIVATE observer error')):
                report=diagnostic.observe(module,'.')
            self.assertEqual(report['outcome'],'observer_failed')
            self.assertNotIn('error_chain',report)
            self.assertNotIn('PRIVATE',json.dumps(report))
            if original_error is None:
                self.assertEqual(len(captured),1)

    def test_real_process_failure_has_distinct_telemetry_without_private_result(self):
        module, unused, unused2=original_module()
        def failed(*args,**kwargs):
            return {'status':'failed','exit_code':9,'cleanup_confirmed':True,
                    'stdout_bytes':0,'stderr_bytes':7,'stderr':'PRIVATE SECRET'}
        module.run_command=failed
        original_git=module._Source.git
        def git(source,*args,**kwargs):
            result=original_git(source,*args,**kwargs)
            if result['status']!='passed':
                raise DocumentationError('git_or_resource_error')
            return result
        module._Source.git=git
        report=diagnostic.observe(module,'.')
        self.assertTrue(report['tail'][0]['process_called'])
        self.assertEqual(report['tail'][0]['process_status'],'failed')
        self.assertEqual(report['error_chain'],['documentation:git_or_resource_error'])
        self.assertNotIn('PRIVATE',json.dumps(report))

    def test_entrypoint_original_refusal_and_guard_refusal_exit_nonzero(self):
        module, unused, unused2=original_module(DocumentationError('resource_limit'))
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'observation.json'
            with mock.patch.object(diagnostic,'load_target',return_value=(module,'.')), mock.patch('builtins.print'):
                self.assertEqual(diagnostic.main(['--target','.','--report',str(output)]),1)
            self.assertEqual(json.loads(output.read_text())['outcome'],'refused')
            with mock.patch.object(diagnostic,'load_target',side_effect=OSError('PRIVATE SECRET')), mock.patch('builtins.print'):
                self.assertEqual(diagnostic.main(['--target','.','--report',str(output)]),1)
            self.assertEqual(json.loads(output.read_text())['outcome'],'guard_refused')
            self.assertNotIn('PRIVATE',output.read_text())

    def test_output_failure_does_not_emit_private_exception_traceback(self):
        with mock.patch.object(diagnostic,'load_target',side_effect=ValueError('PRIVATE guard')), \
             mock.patch.object(diagnostic,'encode_report',side_effect=OSError('SECRET output')), \
             mock.patch('builtins.print') as printed:
            self.assertEqual(diagnostic.main(['--target','.','--report','unused']),2)
        printed.assert_called_once_with('diagnostic output refused')

    def test_source_guard_rejects_wrong_commit_or_module(self):
        self.assertFalse(diagnostic.valid_source('0'*40,b'PRIVATE'))
        self.assertFalse(diagnostic.valid_source(diagnostic.TARGET_SHA,b'PRIVATE'))

    def test_workflow_has_only_narrow_trigger_and_no_existing_workflow_changes(self):
        text=(Path(__file__).parents[1]/'.github/workflows/ci-docs-pr97-diagnostic.yml').read_text(encoding='utf-8')
        self.assertIn('branches: [codex/ci-docs-pr97-diagnostic]',text)
        self.assertIn('permissions:\n  contents: read',text)
        self.assertIn(diagnostic.TARGET_SHA,text)
        self.assertIn('timeout-minutes: 5',text)
        self.assertNotIn('schedule:',text)
        self.assertNotIn('workflow_dispatch:',text)
        self.assertNotIn('task-tower-docs-',text)


if __name__=='__main__':
    unittest.main()
