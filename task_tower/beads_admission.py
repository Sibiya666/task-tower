"""Bounded Windows readiness observations. Packets never grant execution authority.

Test seam: runner(operation, argv, cwd: Path, timeout: float, env: dict)
returns (data, process_facts). Git data is UTF-8 text, Beads data is parsed
JSON. Facts use processes.run_command's capture-mode receipt, including EOF,
cleanup, duration and byte counts. Production always uses that supervisor.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import uuid

from .beads_books import BEAD, PROJECT
from .processes import run_command
from .project_connections import safe_config_path

LIMIT = 65536
CAPTURE_LIMIT = 8 * 1024 * 1024
SHA = r'[0-9a-f]{40}'
REPOSITORY = 'Sibiya666/task-tower'
EXECUTABLE_TYPES = {'task', 'bug', 'feature', 'chore', 'spike', 'story'}


class _Stop(Exception):
    def __init__(self, reason, outcome='refused'):
        self.reason, self.outcome = reason, outcome


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('invalid_constant')
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    except RecursionError:
        raise ValueError('invalid_json_depth') from None


def _read_json(path):
    path = safe_config_path(path)
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('configuration_limit')
    return _json(raw.decode('utf-8'))


def _match(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _directory(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('absolute_directory_required')
    directory = Path(value)
    # The existing guard validates all ancestors, including junction/reparse bits.
    safe_config_path(directory / '.task-tower-path-guard')
    if not directory.is_dir():
        raise ValueError('directory_required')
    return directory


def _git_metadata(source):
    dotgit = source / '.git'
    if dotgit.is_dir():
        gitdir = _directory(str(dotgit))
    else:
        dotgit = safe_config_path(dotgit)
        with dotgit.open('rb') as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('git_metadata_limit')
        text = raw.decode('utf-8').strip()
        if not text.startswith('gitdir: ') or '\n' in text:
            raise ValueError('git_metadata_invalid')
        target = Path(text[8:])
        gitdir = _directory(str(source / target))
    common = gitdir
    marker = safe_config_path(gitdir / 'commondir')
    if marker.exists():
        with marker.open('rb') as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('git_metadata_limit')
        target = raw.decode('utf-8').strip()
        if not target or '\n' in target:
            raise ValueError('git_metadata_invalid')
        common = _directory(str(gitdir / target))
    for directory in (gitdir, common):
        for name in ('config', 'config.worktree', 'HEAD', 'index', 'objects/.guard'):
            safe_config_path(directory / name)
    return gitdir.resolve()


def load_config(path: Path) -> dict:
    """Load strict private observation authorization; never reuse Books settings."""
    try:
        value = _read_json(path)
        if (not isinstance(value, dict) or set(value) != {'version', 'executable', 'projects'}
                or type(value['version']) is not int or value['version'] != 1
                or not isinstance(value['projects'], list) or not 1 <= len(value['projects']) <= 32):
            raise ValueError('invalid_config')
        if not isinstance(value['executable'], str) or not Path(value['executable']).is_absolute():
            raise ValueError('invalid_executable')
        executable = safe_config_path(value['executable'])
        if not executable.is_file() or executable.suffix.lower() != '.exe':
            raise ValueError('invalid_executable')
        ids, directories, sources = set(), set(), set()
        for project in value['projects']:
            if (not isinstance(project, dict) or set(project) != {
                    'id', 'repository', 'directory', 'source', 'expected_head', 'allowed_beads'}
                    or not _match(project['id'], PROJECT) or project['repository'] != REPOSITORY
                    or not _match(project['expected_head'], SHA)):
                raise ValueError('invalid_project')
            allowed = project['allowed_beads']
            if (not isinstance(allowed, list) or not 1 <= len(allowed) <= 1000
                    or any(not _match(bead, BEAD) for bead in allowed)
                    or len(set(allowed)) != len(allowed)):
                raise ValueError('invalid_allowlist')
            directory = _directory(project['directory'])
            safe_config_path(directory / '.beads/metadata.json')
            source = _directory(project['source'])
            _git_metadata(source)
            for collection, identity in ((ids, project['id'].casefold()),
                                         (directories, str(directory.resolve()).casefold()),
                                         (sources, str(source.resolve()).casefold())):
                if identity in collection:
                    raise ValueError('duplicate_project')
                collection.add(identity)
        return value
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('invalid_configuration') from None


def _environment(directory):
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(('BD_', 'BEADS_', 'DOLT_', 'GIT_'))
           and k.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN')}
    env.update(BEADS_DIR=str(directory / '.beads'), GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL='NUL', GIT_NO_LAZY_FETCH='1',
               GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    return env


_EVENT_TYPE = threading.Event
_EVENT_IS_SET = threading.Event.is_set


def _production_runner(operation, argv, cwd, timeout, env, *, cancel_requested=None):
    if cancel_requested is not None and type(cancel_requested) is not _EVENT_TYPE:
        raise ValueError('exact_event_required')
    def cancelled():
        value = _EVENT_IS_SET(cancel_requested) if cancel_requested is not None else False
        if type(value) is not bool:
            raise ValueError('exact_event_state_required')
        return value
    with tempfile.TemporaryDirectory(prefix='task-tower-admission-') as directory:
        receipt = run_command(argv, cwd, timeout, env=env,
                              cancel_requested=cancelled if cancel_requested is not None else None,
                              capture=dict(directory=Path(directory), max_bytes_per_stream=CAPTURE_LIMIT))
        # Read only bounded captures; stderr is deliberately never parsed or exposed.
        raw = (Path(directory) / 'stdout.log').read_bytes()
        try:
            text = raw.decode('utf-8')
            data = _json(text) if operation.startswith('beads_') else text
        except (ValueError, UnicodeError):
            data = None
        return data, receipt


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _process_fact(operation, receipt):
    if not isinstance(receipt, dict):
        raise _Stop('process_unknown', 'unknown')
    def integer(name):
        value = receipt.get(name)
        return value if type(value) is int and value >= 0 else None
    duration = receipt.get('duration_seconds')
    duration = duration if type(duration) in (float, int) and math.isfinite(duration) and duration >= 0 else None
    status = receipt.get('status')
    if status not in {'passed', 'failed', 'timeout', 'unavailable', 'cancelled', 'unknown', 'cleanup_failed'}:
        status = 'unknown'
    return dict(operation=operation, pid=integer('pid'), exit_code=receipt.get('exit_code')
                if type(receipt.get('exit_code')) is int else None, status=status,
                eof_confirmed=all(receipt.get(s+'_tail_unknown') is False for s in ('stdout', 'stderr')),
                cleanup_confirmed=receipt.get('cleanup_confirmed') is True,
                duration_seconds=duration, stdout_bytes=integer('stdout_bytes'), stderr_bytes=integer('stderr_bytes'))


def _validate_git_config(raw):
    if not isinstance(raw, str) or (raw and not raw.endswith('\0')):
        raise _Stop('source_configuration_invalid')
    for entry in raw.split('\0'):
        if not entry:
            continue
        key, separator, value = entry.partition('\n')
        key, value = key.lower(), value.lower()
        if (not separator or key.startswith(('filter.', 'include.', 'includeif.'))
                or key in {'extensions.partialclone', 'extensions.worktreeconfig'}
                or (key.startswith('remote.') and key.endswith(('.promisor', '.partialclonefilter')))
                or (key == 'core.fsmonitor' and value not in {'false', '0', 'no', 'off', ''})
                or (key in {'core.sparsecheckout', 'core.sparsecheckoutcone'} and value not in {'false', '0', 'no', 'off', ''})):
            raise _Stop('source_configuration_unsupported')


def _row(value):
    if (not isinstance(value, dict) or not _match(value.get('id'), BEAD)
            or not _match(value.get('status'), r'[a-z][a-z0-9_]{0,63}')
            or not _match(value.get('issue_type'), r'[a-z][a-z0-9_]{0,63}')):
        raise _Stop('source_rows_invalid')
    assignee = value.get('assignee')
    if assignee is None:
        assignee = ''
    if not isinstance(assignee, str) or len(assignee) > 256:
        raise _Stop('source_rows_invalid')
    return dict(id=value['id'], status=value['status'], issue_type=value['issue_type'], assignee=assignee)


def _packet(reason):
    return dict(schema=1, kind='beads.admission.observation', run_id=str(uuid.uuid4()),
                attempt_id=str(uuid.uuid4()), platform='windows', outcome='refused',
                reason=reason, observed_at=datetime.now(timezone.utc).isoformat(),
                identity=None, source=None, policy_digest=None, input_digest=None, processes=[])


def observe(config_path: Path, project: str, bead: str, *, runner=None, clock=None) -> dict:
    """Observe readiness under one 30-second budget; no claim or execution follows."""
    clock = clock or time.monotonic
    deadline = clock() + 30
    packet = _packet('unsupported_platform')
    if sys.platform != 'win32':
        return packet
    runner = runner or _production_runner
    try:
        if clock() >= deadline:
            raise _Stop('operation_deadline', 'unknown')
        try:
            config = load_config(config_path)
        except ValueError:
            raise _Stop('invalid_configuration') from None
        selected = [p for p in config['projects'] if p['id'] == project]
        if len(selected) != 1 or bead not in selected[0]['allowed_beads']:
            raise _Stop('task_unauthorized')
        policy = selected[0]
        source, directory = Path(policy['source']), Path(policy['directory'])
        packet['identity'] = f'{REPOSITORY}:beads:{project}:{bead}'
        packet['policy_digest'] = _digest(dict(schema=1, project=project, repository=REPOSITORY,
            allowed_beads=sorted(policy['allowed_beads']), expected_head=policy['expected_head']))
        env = _environment(directory)

        def call(operation, args, cwd):
            remaining = deadline - clock()
            # The supervisor can spend five seconds proving cleanup. Reserve it
            # inside the common operation budget rather than granting fresh time.
            if remaining <= 5:
                raise _Stop('operation_deadline', 'unknown')
            timeout = min(10 if operation.startswith('git_') else 25, remaining - 5)
            data, receipt = runner(operation, args, cwd, timeout, dict(env))
            fact = _process_fact(operation, receipt)
            packet['processes'].append(fact)
            if (clock() >= deadline or fact['duration_seconds'] is None
                    or not fact['cleanup_confirmed'] or not fact['eof_confirmed']
                    or fact['stdout_bytes'] is None or fact['stderr_bytes'] is None
                    or any(receipt.get(s+'_truncated') is not False for s in ('stdout', 'stderr'))
                    or any(fact[s+'_bytes'] > CAPTURE_LIMIT for s in ('stdout', 'stderr'))):
                raise _Stop('process_unknown', 'unknown')
            if fact['status'] != 'passed' or fact['exit_code'] != 0:
                raise _Stop('process_unknown', 'unknown')
            return data

        git_prefix = ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                      '-c', 'core.untrackedCache=false', '-c', 'submodule.recurse=false']

        def git(operation, *args):
            return call('git_'+operation, git_prefix+list(args), source)

        def snapshot():
            _validate_git_config(git('config', 'config', '--null', '--no-includes', '--list'))
            top = git('toplevel', 'rev-parse', '--show-toplevel')
            metadata = git('metadata', 'rev-parse', '--absolute-git-dir')
            if (not isinstance(top, str) or Path(top.strip()).resolve() != source.resolve()
                    or not isinstance(metadata, str) or Path(metadata.strip()).resolve() != _git_metadata(source)):
                raise _Stop('source_identity_mismatch')
            index = git('index', 'ls-files', '--stage', '-v', '-z')
            if not isinstance(index, str) or (index and not index.endswith('\0')):
                raise _Stop('source_index_invalid')
            for entry in index.split('\0'):
                if not entry:
                    continue
                # -v prefixes cached entries with H, lowercases assume-unchanged
                # entries, and marks skip-worktree entries S. Either flag can
                # conceal modified tracked bytes from status; refuse both.
                if not re.match(r'H (100644|100755|120000) [0-9a-f]{40} 0\t', entry):
                    raise _Stop('source_index_unsupported')
            head = git('head', 'rev-parse', '--verify', 'HEAD^{commit}')
            tree = git('tree', 'rev-parse', '--verify', 'HEAD^{tree}')
            status = git('status', 'status', '--porcelain=v1', '--untracked-files=all', '--ignore-submodules=all')
            if not isinstance(head, str) or not isinstance(tree, str):
                raise _Stop('source_pin_invalid')
            head, tree = head.strip(), tree.strip()
            if not _match(head, SHA) or not _match(tree, SHA) or head != policy['expected_head']:
                raise _Stop('source_pin_mismatch')
            if status != '':
                raise _Stop('source_dirty')
            return dict(head=head, tree=tree)

        before = snapshot()
        packet['source'] = before
        try:
            metadata = _read_json(directory / '.beads/metadata.json')
            if not isinstance(metadata, dict) or metadata.get('backend') != 'dolt' or metadata.get('dolt_mode') != 'embedded':
                raise ValueError('unsupported_backend')
        except (ValueError, OSError):
            raise _Stop('beads_metadata_invalid') from None
        prefix = [config['executable'], '--readonly', '--sandbox', '--json']
        ready = call('beads_ready', prefix+['ready', '--limit', '1001'], directory)
        show = call('beads_show', prefix+['show', bead], directory)
        if not isinstance(ready, list) or len(ready) > 1000 or not isinstance(show, list) or len(show) != 1:
            raise _Stop('source_rows_invalid')
        rows = [_row(row) for row in ready]
        if len({row['id'] for row in rows}) != len(rows):
            raise _Stop('source_rows_invalid')
        chosen = [row for row in rows if row['id'] == bead]
        shown = _row(show[0])
        if len(chosen) != 1 or chosen[0] != shown or shown['id'] != bead:
            raise _Stop('readiness_inconsistent')
        if shown['status'] != 'open' or shown['assignee'] or shown['issue_type'] not in EXECUTABLE_TYPES:
            raise _Stop('task_ineligible')
        if snapshot() != before:
            raise _Stop('source_changed')
        packet['input_digest'] = _digest(dict(identity=packet['identity'], ready=chosen[0], show=shown))
        packet.update(outcome='eligible_observation', reason='ready_unclaimed_observation')
    except _Stop as stop:
        packet.update(outcome=stop.outcome, reason=stop.reason)
    except Exception:
        # OS/decoder/runner failures are intentionally non-diagnostic publicly.
        packet.update(outcome='unknown', reason='observation_unavailable')
    return packet


def main(argv=None) -> int:
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            # argparse's message can contain arbitrary private argument values.
            raise _Stop('invalid_arguments')
    parser = Parser(prog='task-tower-beads-admission', allow_abbrev=False,
                    description='Observe authorized local Beads readiness')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--bead', required=True)
    try:
        args = parser.parse_args(argv)
    except _Stop:
        packet = _packet('invalid_arguments')
    else:
        packet = observe(args.config, args.project, args.bead)
    raw = json.dumps(packet, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(raw.encode('utf-8')) > LIMIT:
        packet.update(outcome='unknown', reason='packet_limit', processes=[])
        raw = json.dumps(packet, sort_keys=True, separators=(',', ':'), allow_nan=False)
    print(raw)
    return {'eligible_observation': 0, 'refused': 2, 'unknown': 3}[packet['outcome']]


if __name__ == '__main__':
    raise SystemExit(main())
