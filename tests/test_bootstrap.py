import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tower bootstrap ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "проект с пробелами"
        self.project.mkdir()
        self.skill = self.root / "SKILL.md"
        self.skill.write_text("# Using Superpowers\nFollow the process.", encoding="utf-8")
        self.output = self.root / "received.json"
        self.script = self.root / "fixture_harness.py"
        self.script.write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "Path(sys.argv[1]).write_text(json.dumps({'cwd':os.getcwd(),"
            "'context':Path(sys.argv[2]).read_text(encoding='utf-8')}),encoding='utf-8')\n"
            "raise SystemExit(7)\n", encoding="utf-8")
        self.descriptor = self.root / "adapter.json"
        self.descriptor.write_text(json.dumps({"version": 1, "id": "fixture",
            "launch_argv": [sys.executable, str(self.script), str(self.output), "{instructions}"],
            "capabilities": {"interactive_launch": True}}), encoding="utf-8")

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "bootstrap.py"),
                               "--project", str(self.project), *args], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def setup_args(self):
        return ["--harness", "custom", "--adapter", str(self.descriptor),
                "--superpowers", str(self.skill)]

    def test_dry_run_never_persists_or_launches(self):
        result = self.invoke(*self.setup_args(), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / ".task-tower").exists())
        self.assertFalse(self.output.exists())
        self.assertEqual(json.loads(result.stdout)["harness"], "custom")

    def test_configure_then_launch_reuses_choice_and_passes_context(self):
        configured = self.invoke(*self.setup_args(), "--configure-only")
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertFalse(self.output.exists())
        launched = self.invoke("--launch")
        self.assertEqual(launched.returncode, 7, launched.stderr)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(Path(result["cwd"]).resolve(), self.project.resolve())
        self.assertIn(str(self.skill.resolve()), result["context"])
        self.assertIn("Superpowers", result["context"])

    def test_noninteractive_needs_explicit_launch(self):
        result = self.invoke(*self.setup_args())
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_changed_skill_blocks_reused_launch(self):
        self.assertEqual(self.invoke(*self.setup_args(), "--configure-only").returncode, 0)
        self.skill.write_text("changed instructions", encoding="utf-8")
        result = self.invoke("--launch")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_missing_harness_reports_no_traceback(self):
        result = self.invoke("--harness", "codex", "--executable", "missing-tower-harness-123",
                             "--superpowers", str(self.skill), "--configure-only")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_conflicting_modes_rejected(self):
        result = self.invoke(*self.setup_args(), "--dry-run", "--launch")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows launcher")
    def test_windows_launcher_preserves_invalid_argument_exit_code(self):
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run(["cmd.exe", "/d", "/c", str(ROOT / "start.cmd"),
                                 "--definitely-invalid-option"], capture_output=True, env=env)
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
