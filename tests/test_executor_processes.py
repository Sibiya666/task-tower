import hashlib
import inspect
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from task_tower.processes import run_command


class ExecutorProcessesTests(unittest.TestCase):
    def observer_command(self,*args,**kwargs):
        self.assertIn('stdout_observer',inspect.signature(run_command).parameters,
                      'contained process observer missing')
        return run_command(*args,**kwargs)

    def test_observer_receives_full_stream_beyond_stored_prefix(self):
        digest=hashlib.sha256(); count=[0]
        def observe(chunk): digest.update(chunk); count[0]+=len(chunk)
        with tempfile.TemporaryDirectory() as directory:
            result=self.observer_command([sys.executable,'-c',"import os;os.write(1,b'x'*250000)"],'.',5,
                capture={'directory':pathlib.Path(directory).resolve(),'max_bytes_per_stream':32},
                stdout_observer=observe)
            self.assertEqual(result['status'],'passed')
            self.assertEqual(count[0],250000)
            self.assertEqual(digest.hexdigest(),hashlib.sha256(b'x'*250000).hexdigest())
            self.assertEqual(result['stdout_captured_bytes'],32)
            self.assertFalse(result['stdout_tail_unknown'])
            self.assertFalse(result['stdout_observer_failed'])

    def test_observer_exception_is_neutral_failure_but_drain_reaches_eof(self):
        calls=[0]
        def observe(chunk):
            calls[0]+=1
            raise RuntimeError('secret-observer-detail')
        started=time.monotonic()
        result=self.observer_command([sys.executable,'-c',
            "import os,time;os.write(1,b'x'*300000);time.sleep(20)"],'.',10,stdout_observer=observe)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['stdout_observer_failed'])
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(result['stdout_tail_unknown'])
        self.assertEqual(calls[0],1)
        self.assertLess(time.monotonic()-started,3)
        self.assertNotIn('secret-observer-detail',repr(result))

    def test_parser_invalidity_requests_contained_termination(self):
        from task_tower import claude_adapter
        self.assertTrue(hasattr(claude_adapter,'ClaudeEventParser'))
        import uuid
        parser=claude_adapter.ClaudeEventParser(dict(run_id=str(uuid.uuid4()),
            attempt_id=str(uuid.uuid4()),source_sha='a'*40),65536,4096)
        result=self.observer_command([sys.executable,'-c',
            "import os,time;os.write(1,b'x'*10000);time.sleep(20)"],'.',10,stdout_observer=parser.observe)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['cleanup_confirmed']); self.assertTrue(parser.termination_requested)
        self.assertFalse(parser.finish()['valid'])

    def test_observer_failure_cannot_override_unknown_cleanup(self):
        if sys.platform!='win32': self.skipTest('Windows Job fault injection')
        def fail(chunk): raise ValueError('private')
        with patch('task_tower.windows_job.WindowsJobProcess.close',side_effect=OSError):
            result=self.observer_command([sys.executable,'-c',"print('output')"],'.',3,stdout_observer=fail)
        self.assertEqual(result['status'],'cleanup_failed')
        self.assertFalse(result['cleanup_confirmed'])

    def test_observer_base_exception_does_not_escape_drain_thread(self):
        failures=[]
        def fail(chunk): raise SystemExit('private-detail')
        with patch('threading.excepthook',side_effect=lambda args:failures.append(args)):
            result=self.observer_command([sys.executable,'-c',"print('output')"],'.',3,stdout_observer=fail)
        self.assertEqual(failures,[])
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['stdout_observer_failed'])
        self.assertTrue(result['cleanup_confirmed'])

    def test_durable_cancel_precedes_simultaneous_observer_failure(self):
        cancel=threading.Event()
        def observe(chunk):
            cancel.set()
            raise ValueError('private')
        result=self.observer_command([sys.executable,'-c',
            "import os,time;os.write(1,b'x');time.sleep(10)"],'.',3,
            cancel_requested=cancel.is_set,stdout_observer=observe)
        self.assertEqual(result['status'],'cancelled')
        self.assertTrue(result['stdout_observer_failed'])
        self.assertTrue(result['cleanup_confirmed']); self.assertFalse(result['stdout_tail_unknown'])

    def test_cancel_predicate_uncertainty_precedes_observer_failure(self):
        emitted=threading.Event()
        def observe(chunk):
            emitted.set()
            raise ValueError('observer-private')
        def cancel():
            if emitted.is_set(): raise RuntimeError('cancel-private')
            return False
        result=self.observer_command([sys.executable,'-c',
            "import os,time;os.write(1,b'x');time.sleep(10)"],'.',3,
            cancel_requested=cancel,stdout_observer=observe)
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(result['stdout_observer_failed']); self.assertTrue(result['cleanup_confirmed'])
        self.assertNotIn('private',repr(result))

    def test_active_deadline_precedes_observer_failure(self):
        def observe(chunk): raise ValueError('private')
        result=self.observer_command([sys.executable,'-c',
            "import os,time;os.write(1,b'x');time.sleep(10)"],'.',.2,stdout_observer=observe)
        self.assertEqual(result['status'],'timeout')
        self.assertTrue(result['stdout_observer_failed']); self.assertTrue(result['cleanup_confirmed'])

    def test_late_observer_failure_after_fast_exit_is_failed_without_cleanup_timeout(self):
        def observe(chunk):
            time.sleep(.3)
            raise ValueError('private')
        result=self.observer_command([sys.executable,'-c',"print('output')"],'.',.2,stdout_observer=observe)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['stdout_observer_failed']); self.assertTrue(result['cleanup_confirmed'])

    def test_durable_cancel_during_join_precedes_late_observer_failure(self):
        cancel=threading.Event()
        def observe(chunk):
            time.sleep(.15)
            cancel.set()
            raise ValueError('private')
        result=self.observer_command([sys.executable,'-c',"print('output')"],'.',3,
            cancel_requested=cancel.is_set,stdout_observer=observe)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['status'],'cancelled')
        self.assertTrue(result['stdout_observer_failed']); self.assertTrue(result['cleanup_confirmed'])

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
            directory = pathlib.Path(directory).resolve()
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
            directory = pathlib.Path(directory).resolve()
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
                directory = pathlib.Path(directory).resolve()
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
            root = pathlib.Path(root).resolve()
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
            root = pathlib.Path(root).resolve()
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

    @unittest.skipUnless(sys.platform == 'win32', 'Windows junction')
    def test_junction_capture_rejected_without_path_is_junction(self):
        import os
        import subprocess
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw).resolve()
            directory = root / 'private'
            directory.mkdir()
            (directory / 'nested').mkdir()
            alias = root / 'alias'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(directory)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Python 3.11 lacks Path.is_junction; retain the real reparse point.
            is_junction = getattr(pathlib.Path, 'is_junction', None)
            if is_junction is not None:
                delattr(pathlib.Path, 'is_junction')
            try:
                for capture_dir in (alias, alias / 'nested'):
                    with self.subTest(directory=capture_dir):
                        with patch('task_tower.processes.shutil.which', return_value=None) as lookup:
                            with self.assertRaisesRegex(ValueError, 'unsafe_capture_directory'):
                                run_command([sys.executable, '-c', 'pass'], '.', 3,
                                            capture={'directory': capture_dir, 'max_bytes_per_stream': 100})
                            lookup.assert_not_called()
                        self.assertFalse((capture_dir / 'stdout.log').exists())
                        self.assertFalse((capture_dir / 'stderr.log').exists())
            finally:
                if is_junction is not None:
                    pathlib.Path.is_junction = is_junction
                os.rmdir(alias)
