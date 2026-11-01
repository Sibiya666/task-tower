import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from task_tower.merge_events import build_merge_event


def fixture():
    return {"action": "closed", "repository": {"full_name": "owner/repo"},
            "pull_request": {"number": 12, "merged": True, "merge_commit_sha": "a" * 40,
                             "body": "Task-Tower: TT-42\nTask-Tower: TT-OTHER-1\nTask-Tower: TT-42",
                             "base": {"ref": "main", "repo": {"full_name": "owner/repo"}}}}


class MergeEventTests(unittest.TestCase):
    def build(self, payload=None, **changes):
        args = dict(repository="owner/repo", platform="windows", checks="passed", run_id="123", attempt="1")
        args.update(changes)
        return build_merge_event(fixture() if payload is None else payload, **args)

    def test_normalized_contract_and_explicit_deduplicated_markers(self):
        event = self.build()
        self.assertEqual(set(event), {"version", "kind", "repository", "pr_number", "merge_commit", "task_ids", "platform", "checks", "run_url", "delivery_key"})
        self.assertEqual(event["version"], 1)
        self.assertEqual(event["kind"], "pull_request.merged")
        self.assertEqual(event["task_ids"], ["TT-42", "TT-OTHER-1"])
        self.assertEqual(event["run_url"], "https://github.com/owner/repo/actions/runs/123")
        self.assertEqual(event["pr_number"], 12)

    def test_no_marker_does_not_guess_and_input_is_unchanged(self):
        payload = fixture()
        payload["pull_request"]["body"] = "fix TT-42; Task-Tower: TT-43\nTask-Tower: tt-44\nTask-Tower: TT-45, TT-46"
        before = copy.deepcopy(payload)
        self.assertEqual(self.build(payload)["task_ids"], [])
        self.assertEqual(payload, before)

    def test_delivery_identity_is_deterministic_and_retry_specific(self):
        first = self.build()
        self.assertEqual(first, self.build(run_id=123, attempt=1))
        for change in ({"attempt": "2"}, {"run_id": "124"}, {"platform": "linux"}):
            self.assertNotEqual(first["delivery_key"], self.build(**change)["delivery_key"])

    def test_rejects_invalid_event_fields(self):
        cases = [("action", "opened"), ("pull_request.merged", False), ("pull_request.merged", 1),
                 ("pull_request.number", True), ("pull_request.number", "12"), ("pull_request.number", 0),
                 ("pull_request.merge_commit_sha", "a" * 39), ("pull_request.merge_commit_sha", "g" * 40),
                 ("pull_request.base.ref", "develop"), ("repository.full_name", "fork/repo"),
                 ("pull_request.base.repo.full_name", "fork/repo"), ("pull_request", None)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                payload = fixture()
                target = payload
                parts = field.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                with self.assertRaises(ValueError):
                    self.build(payload)

    def test_rejects_invalid_metadata(self):
        for change in ({"repository": "../repo"}, {"repository": "owner/repo?evil"}, {"platform": "freebsd"},
                       {"checks": "success"}, {"run_id": True}, {"run_id": "1/evil"}, {"run_id": 0},
                       {"attempt": -1}, {"attempt": 1.5}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.build(**change)

    def test_optional_base_repository_and_null_body(self):
        payload = fixture()
        del payload["pull_request"]["base"]["repo"]
        payload["pull_request"]["body"] = None
        self.assertEqual(self.build(payload)["task_ids"], [])

    def test_cli_external_event_file_is_data_and_invalid_input_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_file, output = root / "event.json", root / "out.json"
            payload = fixture()
            sentinel = root / "executed"
            payload["pull_request"]["body"] = f"$(touch {sentinel}); `evil`\nTask-Tower: TT-42"
            event_file.write_text(json.dumps(payload), encoding="utf-8")
            args = [sys.executable, "-m", "task_tower.merge_events", "--event", str(event_file),
                    "--repository", "owner/repo", "--platform", "linux", "--checks", "failed",
                    "--run-id", "123", "--attempt", "1", "--output", str(output)]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["checks"], "failed")
            self.assertFalse(sentinel.exists())
            before = output.read_bytes()
            event_file.write_text('{invalid', encoding="utf-8")
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid", result.stderr.lower())
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["event.json", "out.json"])

    def test_cli_creates_missing_output_parent_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_file = root / "event.json"
            output = root / "missing" / "nested" / "event.json"
            args = [sys.executable, "-m", "task_tower.merge_events", "--event", str(event_file),
                    "--repository", "owner/repo", "--platform", "linux", "--checks", "passed",
                    "--run-id", "123", "--attempt", "1", "--output", str(output)]
            event_file.write_text("{}", encoding="utf-8")
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.parent.exists())
            event_file.write_text(json.dumps(fixture()), encoding="utf-8")
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["pr_number"], 12)
