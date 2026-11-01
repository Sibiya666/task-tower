import json
from pathlib import Path
import subprocess
import sys

from test_readiness import ProjectFixture


class TaskCliTests(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.card = self.root / "card.json"
        self.card.write_text(json.dumps({"version": 1, "id": "FIXTURE-1", "executor": "worker",
            "project_root": ".", "status": "in_progress", "stages": {}}), encoding="utf-8")
        self.evidence = self.root / "review.md"
        self.evidence.write_text("Accepted by independent reviewer", encoding="utf-8")

    def invoke(self, *args):
        return subprocess.run([sys.executable, "-m", "task_tower", "task", *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_show_then_accept_real_evidence(self):
        shown = self.invoke("show", str(self.card))
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["id"], "FIXTURE-1")
        accepted = self.invoke("accept", str(self.card), "--stage", "spec", "--reviewer", "reviewer",
                               "--evidence", str(self.evidence))
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["stages"]["spec"]["status"], "accepted")

    def test_cannot_skip_stage_from_cli(self):
        result = self.invoke("accept", str(self.card), "--stage", "test", "--reviewer", "reviewer",
                             "--evidence", str(self.evidence))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
