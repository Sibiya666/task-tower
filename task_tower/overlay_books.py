"""Public-only incremental overlay books. Stdout is a bounded NDJSON protocol."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from .books import aggregate
from .project_connections import load_connections, safe_config_path

FRAME_LIMIT = 8 * 1024 * 1024
STREAM_LIMIT = 64 * 1024 * 1024
FRAME_COUNT = 32
ENTRY_LIMIT = 10000
ENTRY_FIELDS = frozenset('id repository number project book title source status remote_state verification description phase blockers blocked_by results history relationships stages remote_attempt created_at updated_at capture path commit artifact_state declaration_source issues milestone available'.split())


def _failure(message='Books source unavailable'):
    return dict(kind='books', version=1, state='unavailable', fetched_at=None,
                entries=[], errors=[dict(project='', source='', error=message)])


def _public(report):
    # Aggregate owns nested provenance validation. Only its explicit entry fields
    # cross this boundary; never serialize connections or exception objects.
    rows = report['entries']
    if not isinstance(rows, list) or len(rows) > ENTRY_LIMIT: raise ValueError()
    rows = [{key: deepcopy(value) for key, value in row.items() if key in ENTRY_FIELDS} for row in rows]
    errors = [{key: row[key] for key in ('project', 'source', 'error')} for row in report['errors']]
    if any(not isinstance(value, str) for row in errors for value in row.values()): raise ValueError()
    pending = any(row.get('verification') == 'pending' for row in rows)
    value = dict(kind='books', version=1, state='partial' if errors or pending else 'ready',
                 fetched_at=report.get('fetched_at'), entries=rows, errors=errors)
    if len(_encode(dict(value, sequence=FRAME_COUNT, final=False))) > FRAME_LIMIT: raise ValueError()
    return value


def snapshot(config_path: Path | None, *, on_update=None):
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
        value = snapshot(Path(path) if path else None, on_update=emit)
        emit(value, final=True)
    except Exception:
        value = _failure('Books stream limit exceeded')
        try: emit(value, final=True)
        except Exception: pass
        return 1
    return 0 if value['state'] in ('ready', 'unconfigured') else 1


if __name__ == '__main__': raise SystemExit(main())
