"""Installation-owned project connections; credentials never belong here."""
from dataclasses import dataclass
from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

REPOSITORY = r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*'


@dataclass(frozen=True)
class ProjectConnection:
    id: str
    repository: str
    checkout: Path
    runner_label: str
    project_url: str | None = None
    board: dict | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', self.id):
            raise ValueError('Invalid project ID')
        if not isinstance(self.repository, str) or not re.fullmatch(REPOSITORY, self.repository):
            raise ValueError('Invalid repository')
        if not isinstance(self.runner_label, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', self.runner_label):
            raise ValueError('Invalid runner label')
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
        path = args.config.resolve()
        if args.command == 'init':
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as stream:
                json.dump(dict(version=1, projects=[]), stream, indent=2)
            return 0
        connections = load_connections(path)
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
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.connections-')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(dict(version=1, projects=[dict(asdict(c), checkout=str(c.checkout)) for c in connections]), stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return 0
    except (ValueError, OSError):
        print('task-tower: invalid connections operation; existing configuration preserved', file=sys.stderr)
        return 2
