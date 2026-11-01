import hashlib
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from task_tower.processes import run_command


class ExecutorProcessesTests(unittest.TestCase):
    def test_cancel_before_launch(self):
        with patch('task_tower.processes.shutil.which') as lookup:
            result = run_command([sys.executable, '-c', 'raise SystemExit(1)'], '.', 3,
                                 cancel_requested=lambda: True)
        self.assertEqual(result['status'], 'cancelled')
        lookup.assert_not_called()
        self.assertFalse(result['started'])

    def test_cancel_running(self):
        start = time.monotonic()
        result = run_command([sys.executable, '-c', 'import time; time.sleep(20)'], '.', 10,
                             cancel_requested=lambda: time.monotonic() - start > .3)
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertLess(time.monotonic() - start, 3)

    def test_predicate_exception_is_unknown(self):
        def broken():
            raise RuntimeError('private text')
        result = run_command([sys.executable, '-c', 'pass'], '.', 2, cancel_requested=broken)
        self.assertEqual(result['status'], 'unknown')
        self.assertNotIn('argv', result)

    def test_overflow_caps_logs_but_hashes_complete_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_command([sys.executable, '-c', "import os; os.write(1,b'a'*200000); os.write(2,b'b'*150000)"], '.', 10,
                                 capture={'directory': directory, 'max_bytes_per_stream': 1024})
            self.assertEqual(result['status'], 'passed')
            for name, byte, size in [('stdout', b'a', 200000), ('stderr', b'b', 150000)]:
                self.assertEqual((pathlib.Path(directory) / (name + '.log')).read_bytes(), byte * 1024)
                self.assertEqual(result[name + '_bytes'], size)
                self.assertEqual(result[name + '_sha256'], hashlib.sha256(byte * size).hexdigest())
                self.assertTrue(result[name + '_truncated'])
                self.assertFalse(result[name + '_tail_unknown'])
            self.assertNotIn('argv', result)

    def test_existing_capture_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'stdout.log'
            path.write_bytes(b'keep')
            with self.assertRaises(ValueError):
                run_command([sys.executable, '-c', 'pass'], '.', 3,
                            capture={'directory': directory, 'max_bytes_per_stream': 100})
            self.assertEqual(path.read_bytes(), b'keep')

    def test_cleanup_failure_cannot_pass(self):
        if sys.platform != 'win32':
            self.skipTest('Windows Job fault injection')
        with patch('task_tower.windows_job.WindowsJobProcess.close', side_effect=OSError):
            result = run_command([sys.executable, '-c', 'pass'], '.', 3, cancel_requested=lambda: False)
        self.assertEqual(result['status'], 'cleanup_failed')
        self.assertFalse(result['cleanup_confirmed'])

    def test_timeout_and_normal_parent_exit_kill_descendants(self):
        for normal in (False, True):
            with self.subTest(normal=normal), tempfile.TemporaryDirectory() as directory:
                marker = pathlib.Path(directory) / 'escaped'
                child = "import pathlib,time;time.sleep(.8);pathlib.Path(" + repr(str(marker)) + ").write_text('escaped')"
                parent = ('import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);' + ('pass' if normal else 'time.sleep(20)'))
                result = run_command([sys.executable, '-c', parent], '.', 3 if normal else .25,
                                     cancel_requested=lambda: False)
                self.assertEqual(result['status'], 'passed' if normal else 'timeout')
                self.assertTrue(result['cleanup_confirmed'])
                time.sleep(1)
                self.assertFalse(marker.exists())

    def test_legacy_shape_and_digest_preserved(self):
        result = run_command([sys.executable, '-c', "print('hello')"], '.', 3)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(set(result), {'argv', 'status', 'exit_code', 'stdout_sha256',
                                      'stdout_bytes', 'stderr_sha256', 'stderr_bytes', 'duration_seconds'})

    def test_alias_capture_directory_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root) / 'private'
            directory.mkdir()
            alias = pathlib.Path(root) / 'alias'
            try:
                alias.symlink_to(directory, target_is_directory=True)
            except OSError:
                self.skipTest('symlink privilege unavailable')
            with self.assertRaises(ValueError):
                run_command([sys.executable, '-c', 'pass'], '.', 3,
                            capture={'directory': alias, 'max_bytes_per_stream': 100})

    @unittest.skipUnless(sys.platform == 'win32', 'Windows junction')
    def test_junction_capture_directory_rejected(self):
        import os
        import subprocess
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root) / 'private'
            directory.mkdir()
            alias = pathlib.Path(root) / 'alias'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(directory)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with self.assertRaises(ValueError):
                    run_command([sys.executable, '-c', 'pass'], '.', 3,
                                capture={'directory': alias, 'max_bytes_per_stream': 100})
            finally:
                os.rmdir(alias)
