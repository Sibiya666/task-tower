import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest

from task_tower.processes import run_command


class ProcessTests(unittest.TestCase):
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
