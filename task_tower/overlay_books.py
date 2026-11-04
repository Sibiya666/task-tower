"""Public-only incremental overlay books. Stdout is a bounded NDJSON protocol."""
from copy import deepcopy
import json
import os
import re
from pathlib import Path
import sys

from .books import aggregate
from .project_connections import load_connections, safe_config_path

FRAME_LIMIT = 8 * 1024 * 1024
STREAM_LIMIT = 64 * 1024 * 1024
FRAME_COUNT = 32
ENTRY_LIMIT = 10000
ENTRY_FIELDS = frozenset('id repository number project book title source status remote_state verification description phase blockers blocked_by results history relationships stages remote_attempt created_at updated_at capture path commit artifact_state declaration_source issues milestone available migrations source_kind bead_id assignee'.split())


def _migrations(value):
    if not isinstance(value, list) or len(value) > 100: raise ValueError()
    result = []
    for row in value:
        if not isinstance(row, dict): raise ValueError()
        public = {key: deepcopy(row[key]) for key in ('number', 'source_sha256', 'status', 'issue_url')}
        number, url = public['number'], public['issue_url']
        if number is not None and (type(number) is not int or number < 1): raise ValueError()
        if not isinstance(public['source_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', public['source_sha256']): raise ValueError()
        if public['status'] not in ('current', 'stale', 'pending'): raise ValueError()
        if number is None:
            if url is not None: raise ValueError()
        elif not isinstance(url, str) or len(url) > 8192 or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/' + str(number), url): raise ValueError()
        result.append(public)
    return result


def _failure(message='Books source unavailable'):
    return dict(kind='books', version=1, state='unavailable', fetched_at=None,
                entries=[], errors=[dict(project='', source='', error=message)])


def _public(report):
    # Aggregate owns nested provenance validation. Only its explicit entry fields
    # cross this boundary; never serialize connections or exception objects.
    rows = report['entries']
    if not isinstance(rows, list) or len(rows) > ENTRY_LIMIT: raise ValueError()
    rows = [{key: deepcopy(value) for key, value in row.items() if key in ENTRY_FIELDS} for row in rows]
    for row in rows:
        if 'migrations' in row: row['migrations'] = _migrations(row['migrations'])
    errors = [{key: row[key] for key in ('project', 'source', 'error')} for row in report['errors']]
    if any(not isinstance(value, str) for row in errors for value in row.values()): raise ValueError()
    pending = any(row.get('verification') == 'pending' for row in rows)
    value = dict(kind='books', version=1, state='partial' if errors or pending else 'ready',
                 fetched_at=report.get('fetched_at'), entries=rows, errors=errors)
    if len(_encode(dict(value, sequence=FRAME_COUNT, final=False))) > FRAME_LIMIT: raise ValueError()
    return value


def _beads_snapshot(config_path,beads_path,on_update):
    from .beads_books import read_projects
    local=dict(entries=[],errors=[],fetched_at=None,repositories=[])
    remote=dict(entries=[],errors=[],fetched_at=None)
    failures=[];latest=None
    def combined():
        return dict(entries=local['entries']+remote['entries'],errors=local['errors']+remote['errors']+failures,
                    fetched_at=remote.get('fetched_at') or local.get('fetched_at'))
    def publish():
        nonlocal latest
        latest=_public(combined());latest['state']='partial'
        if on_update is not None: on_update(deepcopy(latest))
    def local_update(value):
        nonlocal local
        local=value;publish()
    def remote_update(value):
        nonlocal remote
        remote=value;publish()
    try: local=read_projects(beads_path,on_update=local_update)
    except Exception: failures.append(dict(project='',source='',error='Local Beads source unavailable or limit exceeded'))
    try:
        connections=load_connections(safe_config_path(config_path)) if config_path else []
        connections=[c for c in connections if c.repository.casefold() not in local['repositories']]
        if connections: remote=aggregate(connections,include_library=True,on_update=remote_update)
    except Exception: failures.append(dict(project='',source='',error='GitHub Books source interrupted or unavailable'))
    try: return _public(combined())
    except Exception:
        if latest is not None:
            latest['state']='partial'
            latest['errors'].append(dict(project='',source='',error='Books source interrupted or limit exceeded'))
            if len(_encode(dict(latest,sequence=FRAME_COUNT,final=True)))<=FRAME_LIMIT:return latest
        return _failure('Books source unavailable or limit exceeded')


def snapshot(config_path: Path | None, *, on_update=None, beads_path=None):
    if beads_path is not None:
        return _beads_snapshot(config_path,beads_path,on_update)
    if config_path is None:
        return dict(kind='books', version=1, state='unconfigured', fetched_at=None, entries=[], errors=[])
    latest = None
    def update(report):
        nonlocal latest
        latest = _public(report)
        if on_update is not None: on_update(deepcopy(latest))
    try:
        connections = load_connections(safe_config_path(config_path))
        if not connections:
            return dict(kind='books', version=1, state='unconfigured', fetched_at=None, entries=[], errors=[])
        return _public(aggregate(connections, include_library=True, on_update=update))
    except Exception:
        if latest is not None:
            latest['state'] = 'partial'
            latest['errors'].append(dict(project='', source='', error='Books source interrupted or limit exceeded'))
            # Reserve diagnostic space too; otherwise use a small fixed failure.
            if len(_encode(dict(latest, sequence=FRAME_COUNT, final=True))) <= FRAME_LIMIT: return latest
        return _failure('Books source unavailable or limit exceeded')


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def main(argv=None):
    # No command-line configuration surface: only installation-owned environment.
    if argv is None: argv = sys.argv[1:]
    if argv: return 2
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='strict', newline='\n')
    count = total = 0
    def emit(value, final=False):
        nonlocal count, total
        raw = _encode(dict(value, sequence=count+1, final=final))
        if len(raw) > FRAME_LIMIT: raise ValueError()
        # Reserve one full maximum-size final frame and one frame slot.
        if not final and (count >= FRAME_COUNT-1 or total+len(raw)+FRAME_LIMIT > STREAM_LIMIT): return
        if count >= FRAME_COUNT or total+len(raw) > STREAM_LIMIT: raise ValueError()
        sys.stdout.write(raw.decode('utf-8')); sys.stdout.flush()
        count += 1; total += len(raw)
    path = os.environ.get('TASK_TOWER_CONNECTIONS')
    try:
        beads=os.environ.get('TASK_TOWER_BEADS')
        value = snapshot(Path(path) if path else None, on_update=emit, **({'beads_path':Path(beads)} if beads else {}))
        emit(value, final=True)
    except Exception:
        value = _failure('Books stream limit exceeded')
        try: emit(value, final=True)
        except Exception: pass
        return 1
    return 0 if value['state'] in ('ready', 'unconfigured') else 1


if __name__ == '__main__': raise SystemExit(main())
