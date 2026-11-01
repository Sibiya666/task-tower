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
    supplied = sys.argv[1:] if argv is None else argv
    if supplied and supplied[0] == 'connect':
        from .project_onboarding import main as connect_main
        return connect_main(supplied[1:])
    if supplied and supplied[0] == "connections":
        from .project_connections import main as connections_main
        return connections_main(supplied[1:])
    if supplied and supplied[0] == "books":
        from .books import main as books_main
        return books_main(supplied[1:])
    if supplied and supplied[0] == "bootstrap":
        from .bootstrap import main as bootstrap_main
        return bootstrap_main(supplied[1:])
    if supplied and supplied[0] == "executor":
        from .executor import main as executor_main
        return executor_main(supplied[1:])
    if supplied and supplied[0] == "dispatcher":
        from .dispatcher import main as dispatcher_main
        return dispatcher_main(supplied[1:])
    if supplied and supplied[0] == "worker":
        from .postmerge_worker import main as worker_main
        return worker_main(supplied[1:])
    parser = argparse.ArgumentParser(description="Task Tower project readiness")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("audit", help="Inspect a project environment")
    command.add_argument("--project", type=Path, required=True)
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--run-checks", action="store_true",
                         help="Execute trusted manifest tool probes and baseline commands")
    command.add_argument("--output", type=Path, help="UTF-8 JSON report outside the project")
    task_parser = commands.add_parser("task", help="File-backed pilot task records")
    task_commands = task_parser.add_subparsers(dest="task_command", required=True)
    show = task_commands.add_parser("show")
    show.add_argument("path", type=Path)
    accept = task_commands.add_parser("accept")
    accept.add_argument("path", type=Path)
    accept.add_argument("--stage", choices=("spec", "development", "test", "postmerge"), required=True)
    accept.add_argument("--reviewer", required=True)
    accept.add_argument("--evidence", type=Path, required=True)
    accept.add_argument("--commit")
    args = parser.parse_args(argv)
    try:
        if args.command == "task":
            from .tasks import load_task, accept_task
            card = load_task(args.path) if args.task_command == "show" else accept_task(
                args.path, args.stage, args.reviewer, args.evidence, args.commit)
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(card, ensure_ascii=False, indent=2))
            return 0
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
