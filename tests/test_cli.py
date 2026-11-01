import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from test_readiness import ProjectFixture, manifest


class CliTests(ProjectFixture):
    def invoke(self, config=None, *args):
        # Manifest is deliberately outside the target repository.
        config_path = self.root.parent / (self.root.name + "-manifest.json")
        self.addCleanup(lambda: config_path.unlink(missing_ok=True))
        config_path.write_text(json.dumps(config or manifest()), encoding="utf-8")
        result = subprocess.run([sys.executable, "-m", "task_tower", "audit", "--project",
                                 str(self.root), "--manifest", str(config_path), *args],
                                capture_output=True, text=True, encoding="utf-8")
        return result

    def test_audit_does_not_run_manifest_commands(self):
        config = manifest()
        config["tools"][0]["argv"] = [sys.executable, "-c", "from pathlib import Path; Path('unexpected').touch()"]
        result = self.invoke(config)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "awaiting_baseline")
        self.assertFalse((self.root / "unexpected").exists())

    def test_explicit_baseline_can_be_ready_for_pilot_but_never_night(self):
        result = self.invoke(None, "--run-checks")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ready_for_pilot")
        self.assertFalse(report["night_ready"])
        self.assertFalse(report["agent_execution_verified"])
        self.assertEqual(len(report["checks"]), 2)

    def test_dirty_project_prevents_all_manifest_execution(self):
        (self.root / "uncommitted").touch()
        result = self.invoke(None, "--run-checks")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["checks"], [])

    def test_failed_baseline_blocks_readiness(self):
        config = manifest()
        config["checks"][0]["argv"] = [sys.executable, "-c", "raise SystemExit(3)"]
        result = self.invoke(config, "--run-checks")
        self.assertEqual(result.returncode, 1)
        self.assertIn("check_failed:baseline", json.loads(result.stdout)["blockers"])

    def test_command_changing_files_invalidates_baseline(self):
        config = manifest()
        config["checks"][0]["argv"] = [sys.executable, "-c", "from pathlib import Path; Path('changed').touch()"]
        result = self.invoke(config, "--run-checks")
        self.assertEqual(result.returncode, 1)
        self.assertIn("repository_changed_during_checks", json.loads(result.stdout)["blockers"])

    def test_commit_during_baseline_invalidates_even_clean_repository(self):
        config = manifest()
        config["checks"][0]["argv"] = [sys.executable, "-c",
            "import subprocess; subprocess.run(['git','-c','user.name=Fixture',"
            "'-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','new'],check=True)"]
        result = self.invoke(config, "--run-checks")
        self.assertEqual(result.returncode, 1)
        self.assertIn("repository_changed_during_checks", json.loads(result.stdout)["blockers"])

    def test_invalid_manifest_has_explained_exit_code(self):
        config = manifest()
        config["checks"] = []
        result = self.invoke(config)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_report_cannot_overwrite_project_files(self):
        result = self.invoke(None, "--output", str(self.root / "AGENTS.md"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Use Superpowers")

    def test_report_written_as_utf8_outside_project(self):
        output = self.root.parent / (self.root.name + "-report.json")
        self.addCleanup(lambda: output.unlink(missing_ok=True))
        config = manifest()
        config["project"] = "Проект"
        result = self.invoke(config, "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["project"], "Проект")

    def test_external_report_hardlink_cannot_overwrite_project_file(self):
        output = self.root.parent / (self.root.name + "-hardlink.json")
        self.addCleanup(lambda: output.unlink(missing_ok=True))
        os.link(self.root / "AGENTS.md", output)
        result = self.invoke(None, "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Use Superpowers")
        self.assertEqual(json.loads(output.read_text())["status"], "awaiting_baseline")


if __name__ == "__main__":
    unittest.main()
