"""File-backed pilot task acceptance; reviewer identity is organizational, not authenticated."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

STAGES = ('spec', 'development', 'test', 'postmerge')


def _safe_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = os.lstat(part)
        except FileNotFoundError:
            info = None
        reparse = (info is not None and getattr(info, 'st_file_attributes', 0)
                   & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if part.is_symlink() or reparse:
            raise ValueError('Task paths cannot traverse symlinks, junctions or reparse points')
    return path.resolve()


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                                text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('Git validation failed: ' + ' '.join(args)) from error
    return result.stdout.strip()


def _read(path: Path) -> tuple[dict, Path]:
    path = _safe_path(path)
    try:
        card = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Cannot read task card') from error
    if not isinstance(card, dict) or type(card.get('version')) is not int or card['version'] != 1:
        raise ValueError('Task card requires version 1')
    for key in ('id', 'executor', 'project_root'):
        if not isinstance(card.get(key), str) or not card[key].strip():
            raise ValueError('Task card requires ' + key)
    root_path = Path(card['project_root'])
    if root_path.is_absolute():
        raise ValueError('project_root must be relative to card directory')
    root = _safe_path(path.parent / root_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Task card must be inside project root')
    if Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise ValueError('project_root must identify the Git repository root')
    stages = card.get('stages')
    if not isinstance(stages, dict) or set(stages) - set(STAGES):
        raise ValueError('Invalid task stages')
    pending = False
    for stage in STAGES:
        record = stages.get(stage, {'status': 'pending'})
        if not isinstance(record, dict) or record.get('status') not in ('pending', 'accepted'):
            raise ValueError('Invalid stage record')
        if record['status'] == 'pending':
            pending = True
        elif pending:
            raise ValueError('Accepted stages cannot skip prior stages')
        else:
            if not isinstance(record.get('reviewer'), str) or not record['reviewer'].strip() or record['reviewer'] == card['executor']:
                raise ValueError('Acceptance requires a distinct reviewer')
            if not isinstance(record.get('evidence'), str) or not isinstance(record.get('sha256'), str):
                raise ValueError('Acceptance requires evidence and sha256')
    expected = _status(stages)
    if card.get('status') != expected:
        raise ValueError('Task status does not match accepted stages')
    return card, root


def _status(stages: dict) -> str:
    if stages.get('postmerge', {}).get('status') == 'accepted':
        return 'done'
    if stages.get('test', {}).get('status') == 'accepted':
        return 'awaiting_merge'
    return 'in_progress'


def _hash(path: Path, root: Path) -> str:
    path = path.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Evidence must be an existing file inside project root')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_evidence(card: dict, path: Path, root: Path, stages=STAGES) -> None:
    for stage in stages:
        record = card['stages'].get(stage, {})
        if record.get('status') == 'accepted':
            evidence = Path(record['evidence'])
            try:
                if evidence.is_absolute() or _hash(path.parent / evidence, root) != record['sha256']:
                    raise ValueError('hash mismatch')
            except (OSError, ValueError) as error:
                raise ValueError('stale evidence for ' + stage) from error
            if stage == 'postmerge':
                _check_commit(root, record.get('commit'))


def _check_commit(root: Path, commit: str | None) -> str:
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-fA-F]{7,40}|[0-9a-fA-F]{64}', commit):
        raise ValueError('postmerge requires an explicit Git commit hash')
    resolved = _git(root, 'rev-parse', '--verify', commit + '^{commit}')
    _git(root, 'merge-base', '--is-ancestor', resolved, 'refs/heads/main')
    return resolved


def load_task(path: Path) -> dict:
    path = _safe_path(path)
    card, root = _read(path)
    _check_evidence(card, path, root)
    return card


def accept_task(path: Path, stage: str, reviewer: str, evidence: Path,
                commit: str | None = None) -> dict:
    path = _safe_path(path)
    card, root = _read(path)
    if stage not in STAGES:
        raise ValueError('Unknown task stage')
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer == card['executor']:
        raise ValueError('Acceptance requires a reviewer distinct from executor')
    index = STAGES.index(stage)
    for previous in STAGES[:index]:
        if card['stages'].get(previous, {}).get('status') != 'accepted':
            raise ValueError('Cannot skip task stages')
    _check_evidence(card, path, root, STAGES[:index])
    evidence = Path(evidence).resolve()
    digest = _hash(evidence, root)
    record = {'status': 'accepted', 'reviewer': reviewer,
              'evidence': Path(os.path.relpath(evidence, path.parent)).as_posix(), 'sha256': digest}
    if stage == 'postmerge':
        record['commit'] = _check_commit(root, commit)
    card['stages'][stage] = record
    for downstream in STAGES[index + 1:]:
        card['stages'][downstream] = {'status': 'pending'}
    card['status'] = _status(card['stages'])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.task-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(card, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return card

