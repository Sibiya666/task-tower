import os
from pathlib import Path
import sys
import tempfile
import unittest

from task_tower.processes import run_command


class ActualProcessIdentityTests(unittest.TestCase):
    def test_started_pid_matches_the_actual_child(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = str(Path(directory).resolve())
            result = run_command(
                [sys.executable, '-c', 'import os; print(os.getpid(), flush=True)'],
                directory, 5, capture={'directory': directory, 'max_bytes_per_stream': 100})
            self.assertEqual(result['status'], 'passed')
            self.assertTrue(result['cleanup_confirmed'])
            self.assertIn('pid', result)
            self.assertIs(type(result['pid']), int)
            self.assertGreater(result['pid'], 0)
            self.assertNotEqual(result['pid'], os.getpid())
            self.assertEqual(result['pid'], int((Path(directory)/'stdout.log').read_text(encoding='utf-8').strip()))

    def test_cancelled_before_launch_has_no_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_command([sys.executable, '-c', 'raise AssertionError()'], directory, 5,
                                 cancel_requested=lambda: True)
            self.assertEqual(result['status'], 'cancelled')
            self.assertFalse(result['started'])
            self.assertIn('pid', result)
            self.assertIsNone(result['pid'])

    def test_timeout_retains_the_launched_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_command([sys.executable, '-c', 'import time; time.sleep(5)'], directory, .1,
                                 cancel_requested=lambda: False)
            self.assertEqual(result['status'], 'timeout')
            self.assertTrue(result['started'])
            self.assertTrue(result['cleanup_confirmed'])
            self.assertIn('pid', result)
            self.assertIs(type(result['pid']), int)
            self.assertGreater(result['pid'], 0)

    def test_legacy_default_result_shape_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_command([sys.executable, '-c', 'pass'], directory, 5)
            self.assertEqual(result['status'], 'passed')
            self.assertNotIn('pid', result)


if __name__ == '__main__':
    unittest.main()
