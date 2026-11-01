"""Interactive onboarding, deliberately separate from autonomous execution."""

import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .harness import BUILTINS, load_config, prepare


def ensure_project_connection(**kwargs):
    # Local-only bootstrap remains usable without importing the GitHub adapter.
    from .project_onboarding import ensure_project_connection as connect
    return connect(**kwargs)


def choose_harness():
    choices = (*BUILTINS, "custom")
    print("Harness: " + ", ".join(f"{i + 1}. {name}" for i, name in enumerate(choices)))
    selected = input("Choose harness: ").strip().lower()
    if selected in choices:
        return selected
    if selected in ("1", "2", "3", "4"):
        return choices[int(selected) - 1]
    raise ValueError("Choose codex, claude, opencode, or custom")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Task Tower bootstrap (Python 3.11+)")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--harness", choices=(*BUILTINS, "custom"))
    parser.add_argument("--superpowers", type=Path, help="Path to installed using-superpowers/SKILL.md")
    parser.add_argument("--adapter", type=Path, help="Trusted custom launch descriptor v1")
    parser.add_argument("--executable", help="Override installed harness executable")
    parser.add_argument("--github-repository", help="Explicit owner/repository to connect before launch")
    parser.add_argument("--connection-id")
    parser.add_argument("--connections", type=Path, help="Private installation connections JSON outside the checkout")
    parser.add_argument("--runner-label")
    parser.add_argument("--project-url", help="Explicit existing GitHub Project selection")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--configure-only", action="store_true")
    modes.add_argument("--launch", action="store_true")
    parser.add_argument("--overlay", action="store_true", help="Also start Windows Codex observer")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve()
        connection_flags = (args.github_repository, args.connection_id, args.connections,
                            args.runner_label, args.project_url)
        github_plan = None
        if any(value is not None for value in connection_flags):
            if not all((args.github_repository, args.connection_id, args.connections, args.runner_label)):
                raise ValueError("GitHub setup requires --github-repository, --connection-id, --connections and --runner-label")
            # Preserve path components so onboarding can reject symlinks/reparse points.
            github_plan = dict(config_path=args.connections.expanduser().absolute(),
                               connection_id=args.connection_id, repository=args.github_repository,
                               checkout=project, runner_label=args.runner_label,
                               project_url=args.project_url)
        saved = load_config(project) or {}
        selected = args.harness or saved.get("harness")
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if not selected:
            if not interactive:
                raise ValueError("Non-interactive setup requires --harness")
            print(f"Platform: {platform.system()}; project: {project}")
            selected = choose_harness()
        if not interactive and not (args.launch or args.configure_only or args.dry_run):
            raise ValueError("Non-interactive use requires --launch, --configure-only or --dry-run")
        if args.overlay and platform.system() != "Windows":
            raise ValueError("Native overlay currently supports Windows only; the harness does not require it")
        skill = args.superpowers
        adapter = args.adapter
        if interactive and skill is None and not saved.get("superpowers"):
            answer = input("Path to Superpowers using-superpowers/SKILL.md: ").strip()
            if answer:
                skill = Path(answer).expanduser()
        if interactive and selected == "custom" and adapter is None and not saved.get("adapter"):
            adapter = Path(input("Path to trusted custom adapter JSON: ").strip()).expanduser()
        if github_plan is not None and not args.dry_run:
            ensure_project_connection(**github_plan)
        plan = prepare(project, selected, skill, adapter, args.executable, persist=not args.dry_run)
        if github_plan is not None:
            plan["github_connection"] = {
                **{key: str(value) if isinstance(value, Path) else value for key, value in github_plan.items()},
                "status": "unverified plan; no GitHub or connection writes" if args.dry_run else "configured",
            }
        if args.dry_run or args.configure_only:
            print(json.dumps({"harness": selected, **plan}, ensure_ascii=False, indent=2))
            return 0
        if args.overlay:
            powershell = shutil.which("powershell.exe")
            overlay = Path(__file__).resolve().parents[1] / "overlay/overlay.ps1"
            if not powershell or not overlay.is_file():
                raise ValueError("Windows overlay prerequisites are unavailable")
            print("Overlay observes Codex sessions only; other harness telemetry is not connected.", flush=True)
            subprocess.Popen([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA",
                              "-File", str(overlay)], cwd=overlay.parent,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"Starting {selected} on {plan['platform']}. Authentication stays with your harness.", flush=True)
        # Interactive session and permissions are owned by the selected harness.
        # This is not the bounded autonomous process supervisor.
        return subprocess.run(plan["argv"], cwd=plan["cwd"], shell=False).returncode
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, EOFError) as error:
        print(f"task-tower bootstrap: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
