"""python -m task_tower audit ..."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

from .processes import run_command
from .readiness import audit, load_manifest


def run_baseline(root, manifest, report):
    if report["blockers"]:
        return
    commands = [("tool", item, 10) for item in manifest["tools"]]
    commands += [("check", item, item["timeout_seconds"]) for item in manifest["checks"]]
    for kind, item, timeout in commands:
        result = run_command(item["argv"], root, timeout)
        report["checks"].append({"kind": kind, "name": item["name"], **result})
        if result["status"] != "passed":
            report["blockers"].append(f"{kind}_failed:{item['name']}")
        after = audit(root, manifest)
        if after["revision"] != report["revision"] or after["blockers"] or (
                after["environment"] != report["environment"]):
            report["blockers"].append("repository_changed_during_checks")
        if report["blockers"]:
            report["status"] = "blocked"
            return
    report["status"] = "ready_for_pilot"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Task Tower project readiness")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("audit", help="Inspect a project environment")
    command.add_argument("--project", type=Path, required=True)
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--run-checks", action="store_true",
                         help="Execute trusted manifest tool probes and baseline commands")
    command.add_argument("--output", type=Path, help="UTF-8 JSON report outside the project")
    args = parser.parse_args(argv)
    try:
        root = args.project.resolve()
        if args.output:
            output = args.output.resolve()
            if output.is_relative_to(root) or output == args.manifest.resolve():
                raise ValueError("report must be outside the project and cannot overwrite the manifest")
        manifest = load_manifest(args.manifest)
        report = audit(root, manifest)
        report.update(created_at=datetime.now(timezone.utc).isoformat(),
                      host={"os": platform.system(), "python": platform.python_version()},
                      agent_execution_verified=False)
        if args.run_checks:
            run_baseline(root, manifest, report)
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output.parent.mkdir(parents=True, exist_ok=True)
            # Replace the directory entry, never truncate an existing hardlink.
            descriptor, temporary = tempfile.mkstemp(prefix=".task-tower-", dir=output.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, output)
            finally:
                Path(temporary).unlink(missing_ok=True)
        # PowerShell's legacy console codepage must not corrupt machine JSON.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
        return 1 if report["blockers"] else 0
    except (OSError, ValueError) as error:
        print(f"task-tower: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
