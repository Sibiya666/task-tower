"""Installation-owned project connections; credentials never belong here."""
from dataclasses import dataclass, field
from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import sqlite3
import stat
from contextlib import closing

REPOSITORY = r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*'


@dataclass(frozen=True)
class ProjectConnection:
    id: str
    repository: str
    checkout: Path
    runner_label: str
    project_url: str | None = None
    board: dict | None = None
    trusted_publishers: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', self.id):
            raise ValueError('Invalid project ID')
        if not isinstance(self.repository, str) or not re.fullmatch(REPOSITORY, self.repository):
            raise ValueError('Invalid repository')
        if not isinstance(self.runner_label, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', self.runner_label):
            raise ValueError('Invalid runner label')
        accounts = self.trusted_publishers
        if (not isinstance(accounts, list) or any(not isinstance(account, str) or '--' in account or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?', account) for account in accounts)
            or len({account.casefold() for account in accounts}) != len(accounts)):
            raise ValueError('Invalid trusted publisher accounts')
        checkout = Path(self.checkout)
        if not checkout.is_absolute() or not checkout.is_dir():
            raise ValueError('Checkout must be an existing absolute directory')
        object.__setattr__(self, 'checkout', checkout.resolve())
        if self.project_url is not None and (not isinstance(self.project_url, str) or not re.fullmatch(r'https://github\.com/(users|orgs)/[A-Za-z0-9-]+/projects/[1-9][0-9]*', self.project_url)):
            raise ValueError('Invalid GitHub Project URL')
        if self.board is not None:
            board = self.board
            if not isinstance(board, dict) or set(board) != {'project_id', 'status_field_id', 'status_options'} or not isinstance(board.get('project_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', board['project_id']):
                raise ValueError('Invalid project board configuration')
            if 'status_field_id' in board and (not isinstance(board['status_field_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]+', board['status_field_id'])):
                raise ValueError('Invalid project status field')
            options = board.get('status_options', {})
            if not isinstance(options, dict) or not options or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', v) for k, v in options.items()) or not board.get('status_field_id'):
                raise ValueError('Invalid project status options')


def load_connections(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('version') != 1 or set(value) != {'version', 'projects'} or not isinstance(value['projects'], list):
            raise ValueError()
        connections = [ProjectConnection(**row) for row in value['projects']]
        if len({c.id.casefold() for c in connections}) != len(connections) or len({c.repository.casefold() for c in connections}) != len(connections):
            raise ValueError()
        return connections
    except (TypeError, OSError, ValueError, KeyError):
        raise ValueError('Invalid project connections configuration') from None


def safe_config_path(path):
    """Reject links before resolution, including Windows directory junctions."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Unsafe connections path')
        if part == path and not stat.S_ISREG(info.st_mode):
            raise ValueError('Unsafe connections path')
    return path


def connection_snapshot(path):
    path = safe_config_path(path)
    if not path.exists(): return None, []
    before = path.read_bytes()
    connections = load_connections(path)
    if path.read_bytes() != before: raise ValueError('Connections changed; rerun setup')
    return before, connections


def write_connections(path, connections, *, expected):
    """Serialize cooperating writers, then compare and atomically replace bytes."""
    path = safe_config_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = safe_config_path(path.with_name(path.name + '.lock.sqlite3'))
    with closing(sqlite3.connect(lock, timeout=10)) as database, database:
        database.execute('BEGIN IMMEDIATE')
        safe_config_path(path)
        current = path.read_bytes() if path.exists() else None
        if current != expected: raise ValueError('Connections changed; rerun setup')
        value = dict(version=1, projects=[dict(asdict(c), checkout=str(c.checkout)) for c in connections])
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.connections-')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            safe_config_path(path)
            if (path.read_bytes() if path.exists() else None) != expected:
                raise ValueError('Connections changed; rerun setup')
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Manage private installation project connections')
    parser.add_argument('--config', required=True, type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init')
    commands.add_parser('list')
    add = commands.add_parser('add')
    for name in ('id', 'repository', 'checkout', 'runner-label'):
        add.add_argument('--' + name, required=True)
    add.add_argument('--project-url')
    commands.add_parser('remove').add_argument('id')
    args = parser.parse_args(argv)
    try:
        path = safe_config_path(args.config)
        if args.command == 'init':
            write_connections(path, [], expected=None)
            return 0
        before, connections = connection_snapshot(path)
        if before is None: raise ValueError('Missing configuration')
        if args.command == 'list':
            print(json.dumps([dict(asdict(c), checkout=str(c.checkout)) for c in connections], indent=2))
            return 0
        if args.command == 'add':
            connection = ProjectConnection(args.id, args.repository, Path(args.checkout), args.runner_label, args.project_url)
            if any(c.id.casefold() == connection.id.casefold() or c.repository.casefold() == connection.repository.casefold() for c in connections):
                raise ValueError('Duplicate connection')
            connections.append(connection)
        else:
            remaining = [c for c in connections if c.id != args.id]
            if len(remaining) == len(connections): raise ValueError('Unknown project')
            connections = remaining
        write_connections(path, connections, expected=before)
        return 0
    except (ValueError, OSError):
        print('task-tower: invalid connections operation; existing configuration preserved', file=sys.stderr)
        return 2
