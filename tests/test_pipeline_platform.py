import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import pipeline


class PlatformBoundaryTests(unittest.TestCase):
    def test_native_capability_matches_actual_host(self):
        self.assertEqual(pipeline.native_execution_supported(), os.name == 'nt')

    def test_unsupported_cli_rejects_before_private_state_or_process_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'absent'
            for command in ('work','watch','_action','_dispatch'):
                with self.subTest(command=command):
                    argv=[command]
                    keys=['connections','journal','config','executor-config']
                    if command in ('watch','_dispatch'):keys+=['dispatch-config','dispatch-journal']
                    if command in ('_action','_dispatch'):keys+=['host-result']
                    for key in keys:argv+=['--'+key,str(root/key)]
                    if command=='work':argv+=['--once']
                    if command=='_action':argv+=['--host-owner','00000000-0000-4000-8000-000000000001']
                    stderr=io.StringIO()
                    with patch.object(pipeline,'native_execution_supported',return_value=False,create=True), patch.object(pipeline,'_runtime',side_effect=AssertionError('private state touched')), patch('subprocess.Popen',side_effect=AssertionError('process launched')), contextlib.redirect_stderr(stderr):
                        self.assertEqual(pipeline.main(argv),2)
                    self.assertEqual(json.loads(stderr.getvalue()),{'error':'unsupported_platform'})
                    self.assertFalse(root.exists())

    def test_direct_native_entries_reject_before_inspecting_inputs(self):
        with patch.object(pipeline,'native_execution_supported',return_value=False,create=True), patch('subprocess.Popen',side_effect=AssertionError('process launched')):
            for entry in (pipeline.work,pipeline.watch,pipeline.watch_tick,pipeline._action,pipeline._dispatch):
                with self.subTest(entry=entry.__name__),self.assertRaisesRegex(ValueError,'^unsupported_platform$'):
                    entry(None,None)
            with self.assertRaisesRegex(ValueError,'^unsupported_platform$'):
                pipeline._Host(None,'_action',1,None)

    @unittest.skipIf(os.name=='nt','Actual unsupported host regression')
    def test_actual_unsupported_host_rejects_valid_native_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'absent'
            for command in ('work','watch','_action','_dispatch'):
                argv=[command]
                keys=['connections','journal','config','executor-config']
                if command in ('watch','_dispatch'):keys+=['dispatch-config','dispatch-journal']
                if command in ('_action','_dispatch'):keys+=['host-result']
                for key in keys:argv+=['--'+key,str(root/key)]
                if command=='work':argv+=['--once']
                if command=='_action':argv+=['--host-owner','00000000-0000-4000-8000-000000000001']
                stderr=io.StringIO()
                with self.subTest(command=command),patch.object(pipeline,'_runtime',side_effect=AssertionError('Private state touched')),patch('subprocess.Popen',side_effect=AssertionError('Process launched')),contextlib.redirect_stderr(stderr):
                    self.assertEqual(pipeline.main(argv),2)
                self.assertEqual(json.loads(stderr.getvalue()),{'error':'unsupported_platform'})
                self.assertFalse(root.exists())

    def test_portable_adapter_cli_submission_lookup_and_inspection(self):
        from tests.test_pipeline_watch import WatchTests
        import uuid
        fixture=WatchTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        request=fixture.root/'request.json';result=fixture.root/'result.json'
        payload=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=fixture.config['tasks'][0]['task_id'],runner_label='local')
        argv=['adapter','--connections',str(fixture.connections),'--journal',str(fixture.args.journal),'--config',str(fixture.source.fixture.path),'--executor-config',str(fixture.executor),'--request',str(request),'--result',str(result)]
        with patch.object(pipeline,'native_execution_supported',return_value=False),patch('subprocess.Popen',side_effect=AssertionError('Portable command launched a process')):
            request.write_text(json.dumps(payload))
            self.assertEqual(pipeline.main(argv),0)
            receipt=json.loads(result.read_text())
            payload['operation']='lookup';request.write_text(json.dumps(payload))
            self.assertEqual(pipeline.main(argv),0)
            self.assertEqual(json.loads(result.read_text()),receipt)
            common=['--connections',str(fixture.connections),'--journal',str(fixture.args.journal),'--run-id',receipt['receipt_id']]
            for command in ('status','reconcile','cancel'):
                extra=['--inspect'] if command=='reconcile' else []
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(pipeline.main([command,*common,*extra]),0)
            self.assertEqual(fixture.journal.status(receipt['receipt_id'])['state'],'cancelled')
