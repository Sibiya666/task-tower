"""Validate a project contract and inspect it without running manifest commands."""

import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess


def _relative(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("project paths must be non-empty relative paths")
    windows = PureWindowsPath(value)
    if Path(value).is_absolute() or windows.drive or windows.root or ".." in windows.parts:
        raise ValueError("project paths must stay inside the project")
    return value


def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    validate_manifest(data)
    return data


def validate_manifest(data):
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("manifest version must be 1")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        raise ValueError("project must be a non-empty identifier")
    required = data.get("required_paths")
    if not isinstance(required, list) or not required:
        raise ValueError("required_paths must contain project instructions")
    for value in required:
        _relative(value)
    if "AGENTS.md" not in required:
        raise ValueError("required_paths must include AGENTS.md")
    _relative(data.get("superpowers_skill"))
    for key in ("tools", "checks"):
        items = data.get(key)
        if not isinstance(items, list) or not items:
            raise ValueError(f"{key} must be a non-empty list")
        names = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"invalid {key} entry")
            name = item.get("name")
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError(f"{key} names must be non-empty and unique")
            names.add(name)
            argv = item.get("argv")
            if not isinstance(argv, list) or not argv or any(
                    not isinstance(arg, str) or not arg or "\0" in arg for arg in argv):
                raise ValueError("argv must be a non-empty list of non-empty strings")
            if key == "checks":
                timeout = item.get("timeout_seconds")
                if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
                    raise ValueError("timeout_seconds must be positive and finite")


def _contained(root, relative):
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes project: {relative}")
    return resolved


def _git(root, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            timeout=10, env=env)
    if result.returncode:
        raise ValueError("Git probe failed")
    return result.stdout.decode("utf-8", errors="replace").strip()


def audit(root, manifest):
    validate_manifest(manifest)
    root = Path(root).resolve()
    blockers = []
    environment = {"manifest_sha256": hashlib.sha256(json.dumps(
        manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(), "tools": []}
    result = {"version": 1, "project": manifest["project"], "revision": None,
              "status": "blocked", "night_ready": False, "blockers": blockers,
              "environment": environment, "checks": []}
    try:
        actual_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        if actual_root != root:
            blockers.append("not_repository_root")
        result["revision"] = _git(root, "rev-parse", "HEAD")
        if _git(root, "status", "--porcelain", "--untracked-files=normal"):
            blockers.append("dirty_repository")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        blockers.append("git_unavailable_or_not_repository")
    for path in manifest["required_paths"]:
        if not _contained(root, path).is_file():
            blockers.append(f"missing_path:{path}")
    skill = _contained(root, manifest["superpowers_skill"])
    if not skill.is_file():
        blockers.append("missing_superpowers")
    else:
        environment["superpowers_sha256"] = hashlib.sha256(skill.read_bytes()).hexdigest()
    # Tool arguments are NOT run during audit. The manifest is trusted executable
    # configuration only when the owner explicitly requests --run-checks.
    for tool in manifest["tools"]:
        executable = shutil.which(tool["argv"][0])
        environment["tools"].append({"name": tool["name"], "available": bool(executable)})
        if not executable:
            blockers.append(f"tool_failed:{tool['name']}")
    if not blockers:
        result["status"] = "awaiting_baseline"
    return result
