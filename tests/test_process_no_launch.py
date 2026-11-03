"""Actual prelaunch refusal has complete empty bounded-capture facts."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from task_tower.processes import run_command


class NoLaunchCaptureTests(unittest.TestCase):
    def test_missing_executable_has_empty_capture_without_invented_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            result=run_command([str(root/'missing-executable')],root,2,
                capture={'directory':root,'max_bytes_per_stream':1024})
            self.assertEqual(result['status'],'unavailable')
            self.assertIs(result['started'],False)
            self.assertIsNone(result['pid']);self.assertIsNone(result['exit_code'])
            self.assertIs(result['cleanup_confirmed'],True)
            for stream in ('stdout','stderr'):
                self.assertEqual((root/(stream+'.log')).read_bytes(),b'')
                self.assertEqual(result[stream+'_sha256'],hashlib.sha256(b'').hexdigest())
                self.assertEqual(result[stream+'_bytes'],0)
                self.assertEqual(result[stream+'_captured_bytes'],0)
                self.assertIs(result[stream+'_tail_unknown'],False)
                self.assertIs(result[stream+'_truncated'],False)
