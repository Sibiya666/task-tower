import json
from pathlib import Path
import tempfile
import unittest
import os
from task_tower import executor_harness as harness

class HarnessTests(unittest.TestCase):
    def test_duplicate_oversize_and_hardlinked_output_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'result'; attempt=dict(run_id='r',attempt_id='a',source_sha='1'*40)
            path.write_text('{"version":1,"version":1}')
            with self.assertRaises(ValueError): harness.validate_result(path,attempt,4096)
            path.write_text(' '*100)
            with self.assertRaises(ValueError): harness.validate_result(path,attempt,50)
            os.link(path,Path(raw)/'alias')
            with self.assertRaises(ValueError): harness.validate_result(path,attempt,4096)
    def test_flags_and_policy(self):
        attempt=dict(schema_path='schema',result_path='result',worktree='work',request_path='request',prompt_path='prompt')
        argv=harness.build_invocation(attempt,dict(kind='codex',argv=['codex'],approve_for_me=False))
        self.assertEqual(argv,['codex','exec','--json','--sandbox','workspace-write','--output-schema','schema','--output-last-message','result','-C','work','Read the execution request and pinned instructions at request. Return only the required result JSON.'])
        self.assertFalse(harness.capabilities(dict(kind='codex',argv=['codex']))['verified'])
        enabled=harness.build_invocation(attempt,dict(kind='codex',argv=['codex'],approve_for_me=True))
        self.assertEqual(enabled.count('--approve-for-me'),1)
        self.assertNotIn('--full-auto',enabled); self.assertNotIn('--model',enabled)
        with self.assertRaises(ValueError): harness.build_invocation(attempt,dict(kind='custom',argv=['custom']))
    def test_result_binding_and_strictness(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'result.json'
            attempt=dict(run_id='r',attempt_id='a',source_sha='1'*40)
            value=dict(version=1,**attempt,status='completed',summary='ok')
            path.write_text(json.dumps(value),encoding='utf-8')
            self.assertEqual(harness.validate_result(path,attempt,4096),value)
            for update in [dict(extra=True),dict(run_id='wrong'),dict(version=True),dict(status='done'),dict(summary=2)]:
                path.write_text(json.dumps(value|update),encoding='utf-8')
                with self.assertRaises(ValueError): harness.validate_result(path,attempt,4096)
            path.write_bytes(b'\xff')
            with self.assertRaises(ValueError): harness.validate_result(path,attempt,4096)
    def test_result_status_container_is_rejected_as_value_error(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'result'; attempt=dict(run_id='r',attempt_id='a',source_sha='1'*40)
            path.write_text(json.dumps(dict(version=1,**attempt,status=[],summary='ok')))
            with self.assertRaises(ValueError): harness.validate_result(path,attempt,4096)
