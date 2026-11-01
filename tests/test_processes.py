import hashlib
import errno
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from types import SimpleNamespace

from task_tower.processes import run_command


class ProcessTests(unittest.TestCase):
    def simulated_posix_command(self, signals, *, platform="darwin", timed_out=True):
        process = mock.Mock(pid=12345)
        process.wait.side_effect = ([subprocess.TimeoutExpired("python", .3), -9, -9]
                                    if timed_out else [0, 0])
        elapsed = [0.0]

        def sleep(seconds):
            elapsed[0] += seconds

        fake_os = SimpleNamespace(name="posix", killpg=mock.Mock(side_effect=signals))
        with (mock.patch("task_tower.processes.os", fake_os),
              mock.patch("task_tower.processes.signal", SimpleNamespace(SIGKILL=9)),
              mock.patch("task_tower.processes.sys", SimpleNamespace(platform=platform), create=True),
              mock.patch("task_tower.processes.subprocess.Popen", return_value=process),
              mock.patch("task_tower.processes.time.monotonic", side_effect=lambda: elapsed[0]),
              mock.patch("task_tower.processes.time.sleep", side_effect=sleep)):
            result = self.run_python("pass", timeout=.3)
        self.assertLessEqual(elapsed[0], 1)
        return result

    def test_darwin_timeout_retries_transient_cleanup_permission_error(self):
        result = self.simulated_posix_command(
            [None, PermissionError(errno.EPERM, "denied"), ProcessLookupError(errno.ESRCH, "gone")])
        self.assertEqual((result["status"], result["exit_code"]), ("timeout", -9))

    def test_darwin_timeout_cleanup_permission_error_stays_fail_closed(self):
        attempts = [0]

        def signals(*args):
            attempts[0] += 1
            if attempts[0] > 1:
                raise PermissionError(errno.EPERM, "denied")

        result = self.simulated_posix_command(signals)
        self.assertEqual(result["status"], "cleanup_failed")

    def test_darwin_timeout_cleanup_can_signal_after_permission_race(self):
        result = self.simulated_posix_command(
            [None, PermissionError(errno.EPERM, "denied"), None])
        self.assertEqual((result["status"], result["exit_code"]), ("timeout", -9))

    def test_darwin_timeout_other_permission_error_stays_fail_closed(self):
        result = self.simulated_posix_command(
            [None, PermissionError(errno.EACCES, "denied"), None])
        self.assertEqual(result["status"], "cleanup_failed")

    def test_posix_cleanup_missing_group_preserves_timeout(self):
        result = self.simulated_posix_command([None, ProcessLookupError(errno.ESRCH, "gone")])
        self.assertEqual((result["status"], result["exit_code"]), ("timeout", -9))

    def test_normal_exit_permission_error_is_not_retried(self):
        result = self.simulated_posix_command(
            [PermissionError(errno.EPERM, "denied"), None], timed_out=False)
        self.assertEqual(result["status"], "cleanup_failed")

    def test_other_posix_timeout_permission_error_is_not_retried(self):
        result = self.simulated_posix_command(
            [None, PermissionError(errno.EPERM, "denied"), None], platform="linux")
        self.assertEqual(result["status"], "cleanup_failed")

    def run_python(self, source, timeout=5):
        return run_command([sys.executable, "-c", source], Path.cwd(), timeout)

    def test_success_records_output_digest_without_output_text(self):
        result = self.run_python("import sys; sys.stdout.write('private-value')")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout_bytes"], 13)
        self.assertEqual(result["stdout_sha256"], hashlib.sha256(b"private-value").hexdigest())
        self.assertNotIn("private-value", str({k: v for k, v in result.items() if k != "argv"}))

    def test_failed_command_preserves_exit_code(self):
        result = self.run_python("raise SystemExit(7)")
        self.assertEqual((result["status"], result["exit_code"]), ("failed", 7))

    def test_missing_command_is_explained(self):
        result = run_command(["nonexistent-task-tower-123"], Path.cwd(), 5)
        self.assertEqual(result["status"], "unavailable")

    def test_metacharacters_are_literal_arguments(self):
        result = run_command([sys.executable, "-c", "import sys; print(sys.argv[1])",
                              "literal & $(echo should-not-run)"], Path.cwd(), 5)
        self.assertEqual(result["stdout_sha256"], hashlib.sha256(
            ("literal & $(echo should-not-run)" + ("\r\n" if sys.platform == "win32" else "\n")).encode()).hexdigest())

    def test_timeout_stops_parent_and_child(self):
        self.assert_child_stopped(parent_sleep=30, timeout=.3, expected="timeout")

    def test_child_does_not_survive_successful_parent_exit(self):
        self.assert_child_stopped(parent_sleep=0, timeout=5, expected="passed")

    def assert_child_stopped(self, parent_sleep, timeout, expected):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "escaped-child.txt"
            child = "import time; from pathlib import Path; time.sleep(1); Path(" + repr(str(marker)) + ").write_text('escaped')"
            parent = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                      + repr(child) + "]); time.sleep(" + str(parent_sleep) + ")")
            result = self.run_python(parent, timeout)
            self.assertEqual(result["status"], expected, result)
            time.sleep(1.2)
            self.assertFalse(marker.exists(), "child escaped command lifetime")

    def test_large_output_is_spooled_and_counted(self):
        result = self.run_python("import sys; sys.stdout.write('x' * 2000000)")
        self.assertEqual(result["stdout_bytes"], 2000000)


if __name__ == "__main__":
    unittest.main()
