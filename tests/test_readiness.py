import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from task_tower.readiness import audit, load_manifest


def manifest():
    return {
        "version": 1, "project": "fixture",
        "required_paths": ["AGENTS.md"],
        "superpowers_skill": "skills/using-superpowers/SKILL.md",
        "tools": [{"name": "python", "argv": [sys.executable, "--version"]}],
        "checks": [{"name": "baseline", "argv": [sys.executable, "-c", "pass"],
                    "timeout_seconds": 5}],
    }


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS temp paths may use /var -> /private/var; create fixtures at
        # their canonical location without weakening production link checks.
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-b", "main")
        (self.root / "AGENTS.md").write_text("Use Superpowers", encoding="utf-8")
        skill = self.root / "skills/using-superpowers/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("fixture skill", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-m", "baseline")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()


class AuditTests(ProjectFixture):
    def test_clean_project_records_revision_and_skill_digest(self):
        result = audit(self.root, manifest())
        self.assertEqual(result["status"], "awaiting_baseline")
        self.assertEqual(result["revision"], self.git("rev-parse", "HEAD"))
        self.assertEqual(result["blockers"], [])
        self.assertEqual(len(result["environment"]["superpowers_sha256"]), 64)
        self.assertFalse(result["night_ready"])

    def test_dirty_project_is_blocked(self):
        (self.root / "AGENTS.md").write_text("changed", encoding="utf-8")
        self.assertIn("dirty_repository", audit(self.root, manifest())["blockers"])

    def test_subdirectory_is_not_accepted_as_project_root(self):
        nested = self.root / "nested"
        nested.mkdir()
        self.assertIn("not_repository_root", audit(nested, manifest())["blockers"])

    def test_missing_required_file_and_skill_are_explained(self):
        (self.root / "AGENTS.md").unlink()
        (self.root / "skills/using-superpowers/SKILL.md").unlink()
        blockers = audit(self.root, manifest())["blockers"]
        self.assertIn("missing_path:AGENTS.md", blockers)
        self.assertIn("missing_superpowers", blockers)

    def test_missing_tool_is_blocker(self):
        config = manifest()
        config["tools"][0]["argv"] = ["task-tower-nonexistent-tool-123"]
        self.assertIn("tool_failed:python", audit(self.root, config)["blockers"])

    def test_non_repository_returns_blocker_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("git_unavailable_or_not_repository", audit(Path(directory), manifest())["blockers"])


class ManifestTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_manifest(path)

    def test_valid_manifest_loads(self):
        self.assertEqual(self.load(manifest())["project"], "fixture")

    def test_rejects_malformed_manifests(self):
        for key, value in [("version", 2), ("project", ""), ("required_paths", []),
                           ("superpowers_skill", "../outside"), ("checks", []),
                           ("tools", "python")]:
            with self.subTest(key=key):
                config = copy.deepcopy(manifest())
                config[key] = value
                with self.assertRaises(ValueError):
                    self.load(config)

    def test_rejects_shell_strings_invalid_timeouts_and_duplicate_names(self):
        for change in ["shell", "zero", "boolean", "nan", "duplicate", "absolute"]:
            with self.subTest(change=change):
                config = manifest()
                if change == "shell":
                    config["checks"][0]["argv"] = "echo hello"
                elif change == "duplicate":
                    config["checks"] *= 2
                elif change == "absolute":
                    config["required_paths"] = ["C:\\outside"]
                else:
                    config["checks"][0]["timeout_seconds"] = {
                        "zero": 0, "boolean": True, "nan": float("nan")}[change]
                with self.assertRaises(ValueError):
                    self.load(config)


if __name__ == "__main__":
    unittest.main()
