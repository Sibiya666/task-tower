"""Validate GitHub merge facts and export portable postmerge events."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", re.ASCII)
_TASK_MARKER = re.compile(r"^[ \t]*Task-Tower:[ \t]*(TT-[A-Z0-9]+(?:-[A-Z0-9]+)*)[ \t]*$", re.MULTILINE | re.ASCII)


def _positive(value, name):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) and int(value) > 0:
        return str(int(value))
    raise ValueError(f"{name} must be a positive integer")


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def build_merge_event(payload, repository, platform, checks, run_id, attempt):
    """Return a normalized event, rejecting anything outside the merge contract."""
    if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
        raise ValueError("repository must be owner/repo")
    if platform not in ("windows", "macos", "linux"):
        raise ValueError("platform must be windows, macos or linux")
    if checks not in ("passed", "failed"):
        raise ValueError("checks must be passed or failed")
    run_id = _positive(run_id, "run_id")
    attempt = _positive(attempt, "attempt")
    payload = _object(payload, "payload")
    if payload.get("action") != "closed":
        raise ValueError("action must be closed")
    source = _object(payload.get("repository"), "repository")
    if source.get("full_name") != repository:
        raise ValueError("payload repository does not match expected repository")
    pr = _object(payload.get("pull_request"), "pull_request")
    if pr.get("merged") is not True:
        raise ValueError("pull_request.merged must be true")
    base = _object(pr.get("base"), "pull_request.base")
    if base.get("ref") != "main":
        raise ValueError("pull_request.base.ref must be main")
    if "repo" in base and _object(base["repo"], "pull_request.base.repo").get("full_name") != repository:
        raise ValueError("base repository does not match expected repository")
    number = pr.get("number")
    if type(number) is not int or number <= 0:
        raise ValueError("pull_request.number must be a positive integer")
    sha = pr.get("merge_commit_sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ValueError("merge_commit_sha must contain 40 hexadecimal characters")
    sha = sha.lower()
    body = pr.get("body")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise ValueError("pull_request.body must be text or null")
    task_ids = list(dict.fromkeys(_TASK_MARKER.findall(body.replace("\r\n", "\n"))))
    identity = [repository, number, sha, platform, run_id, attempt]
    key = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"version": 1, "kind": "pull_request.merged", "repository": repository,
            "pr_number": number, "merge_commit": sha, "task_ids": task_ids,
            "platform": platform, "checks": checks,
            "run_url": f"https://github.com/{repository}/actions/runs/{run_id}",
            "delivery_key": key}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("event", "repository", "platform", "checks", "run-id", "attempt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    temporary = None
    try:
        payload = json.loads(Path(args.event).read_text(encoding="utf-8-sig"))
        event = build_merge_event(payload, args.repository, args.platform, args.checks, args.run_id, args.attempt)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(event, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, output)
        temporary = None
    except (OSError, ValueError) as exc:
        parser.exit(2, f"invalid merge event: {exc}\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
