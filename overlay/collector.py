"""Read-only local Codex adapter. No authentication files or message bodies are exported."""
import argparse
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
HOME = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
LABELS = {'active': 'Работает', 'idle': 'Ожидает задачи', 'stopped': 'Остановлен',
          'unknown': 'Статус неизвестен', 'stale': 'Нет свежих событий', 'error': 'Ошибка'}
LIFECYCLE = {'task_started':'active','turn_started':'active','task_complete':'idle','turn_complete':'idle',
             'turn_aborted':'stopped','task_aborted':'stopped','error':'error','turn_failed':'error'}


def earlier_lifecycle(path, end):
    """Backscan complete event lines when the current turn began before the tail."""
    with path.open('rb') as stream:
        while end > 0:
            start=max(0,end-1024*1024)
            stream.seek(start); block=stream.read(end-start)
            lines=block.split(b'\n')
            if start:
                start+=len(lines.pop(0))+1
            for line in reversed(lines):
                if b'event_msg' not in line:
                    continue
                try:
                    event=json.loads(line)
                    if event.get('type')=='event_msg' and event.get('payload',{}).get('type') in LIFECYCLE:
                        try:
                            seen=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()
                        except (KeyError,ValueError,TypeError):
                            seen=0
                        return {'status':LIFECYCLE[event['payload']['type']], 'seen':seen}
                except (ValueError,UnicodeDecodeError):
                    pass
            if start>=end:
                end=max(0,end-1024*1024)
            else:
                end=start
    return {'status':'unknown','seen':0}


class Journal:
    def __init__(self):
        self.cache = {}

    def read(self, path, now=None):
        now = time.time() if now is None else now
        path = Path(path)
        state = self.cache.setdefault(str(path), {'offset': 0, 'pending': b'', 'status': 'unknown', 'seen': 0})
        try:
            size = path.stat().st_size
            if size < state['offset']:
                state.update(offset=0, pending=b'', status='unknown', seen=0)
            with path.open('rb') as f:
                if not state['offset'] and size > 4 * 1024 * 1024:
                    f.seek(size - 4 * 1024 * 1024)
                    f.readline()
                    state.update(earlier_lifecycle(path, f.tell()))
                else:
                    f.seek(state['offset'])
                lines = (state['pending'] + f.read()).split(b'\n')
                state['pending'] = lines.pop()
                state['offset'] = f.tell()
            for line in lines:
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if event.get('type') != 'event_msg':
                    continue
                payload = event.get('payload', {})
                kind = payload.get('type')
                if kind in ('task_started', 'turn_started'):
                    state['status'] = 'active'
                elif kind in ('task_complete', 'turn_complete'):
                    state['status'] = 'idle'
                elif kind in ('turn_aborted', 'task_aborted'):
                    state['status'] = 'stopped'
                elif kind in ('error', 'turn_failed'):
                    state['status'] = 'error'
                try:
                    state['seen'] = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).timestamp()
                except (KeyError, ValueError, TypeError):
                    pass
            status = state['status']
            if status == 'active' and now - state['seen'] > 180:
                status = 'stale'
            return {'status': status, 'label': LABELS[status], 'lastEvent': state['seen']}
        except OSError:
            return {'status': 'unknown', 'label': LABELS['unknown'], 'lastEvent': 0}


def normalized(path):
    return str(path).replace('\\', '/').removeprefix('//?/').rstrip('/').casefold()


def repository_root(cwd):
    """Resolve Git worktrees using metadata only; never execute repository code."""
    try:
        directory = Path(cwd).resolve()
        for parent in (directory, *directory.parents):
            marker = parent / '.git'
            if marker.is_dir():
                return parent
            if marker.is_file():
                pointer = marker.read_text(encoding='utf-8').strip()
                if not pointer.startswith('gitdir:'):
                    return None
                gitdir = (parent / pointer.split(':', 1)[1].strip()).resolve()
                common = gitdir / 'commondir'
                if common.is_file():
                    common_dir = (gitdir / common.read_text(encoding='utf-8').strip()).resolve()
                    if common_dir.name == '.git':
                        return common_dir.parent
                return None
    except (OSError, ValueError):
        pass
    return None


def group_threads(projects, threads, parents, assignments):
    result = [dict(p, rooms=[]) for p in projects]
    by_id = {p['id']: p for p in result}
    loose = {'id': 'unassigned', 'name': 'Вне проектов', 'roots': [], 'rooms': []}
    rooms = {}
    repository_cache = {}
    valid = {t['id']: t for t in threads if not t.get('archived') and not is_guardian(t.get('source', ''))}
    owners = {}
    for tid in valid:
        owner, current, visited = tid, tid, {tid}
        while current in parents and parents[current] not in visited:
            current = parents[current]
            visited.add(current)
            if current in valid:
                owner = current
        owners[tid] = owner
    for tid, t in valid.items():
        if owners[tid] != tid:
            continue
        pid = t.get('project_id') if t.get('project_id') in by_id else assignments.get(tid)
        project = by_id.get(pid)
        if project is None:
            cwd = normalized(t.get('cwd', ''))
            matches = [(len(normalized(r)), p) for p in result for r in p.get('roots', [])
                       if cwd == normalized(r) or cwd.startswith(normalized(r) + '/')]
            if not matches:
                if cwd not in repository_cache:
                    repository_cache[cwd] = repository_root(t.get('cwd', ''))
                repo = repository_cache[cwd]
                if repo is not None:
                    matches = [(len(normalized(r)), p) for p in result for r in p.get('roots', [])
                               if normalized(repo) == normalized(Path(r).resolve())]
            project = max(matches, key=lambda item: item[0])[1] if matches else loose
        room = dict(t, agents=[])
        project['rooms'].append(room)
        rooms[tid] = room
    for tid, t in valid.items():
        owner = owners[tid]
        if owner != tid and owner in rooms:
            rooms[owner]['agents'].append(t)
    if loose['rooms']:
        result.append(loose)
    return result


def snapshot(home, journal, known_assignments=None):
    database = home / 'state_5.sqlite'
    # mode=ro includes live WAL updates; immutable=1 would silently miss them.
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
        connection.row_factory = sqlite3.Row
        projects = [dict(r, roots=[]) for r in connection.execute('SELECT id,name FROM projects ORDER BY position')]
        by_id = {p['id']: p for p in projects}
        for row in connection.execute('SELECT project_id,path FROM project_roots'):
            if row['project_id'] in by_id:
                by_id[row['project_id']]['roots'].append(row['path'])
        threads = [dict(r) for r in connection.execute(
            "SELECT id,COALESCE(NULLIF(name,''),title) AS title,cwd,project_id,rollout_path,updated_at,archived,agent_nickname,agent_role,attached_thread_parent_id,source "
            'FROM threads WHERE archived=0 ORDER BY updated_at DESC')]
        parents = {r['child_thread_id']: r['parent_thread_id'] for r in connection.execute('SELECT * FROM thread_spawn_edges')}
    threads = [t for t in threads if not is_guardian(t.get('source', ''))]
    for thread in threads:
        try:
            source = json.loads(thread.get('source', '{}'))
            spawn = source.get('subagent', {}).get('thread_spawn', {})
            if spawn.get('parent_thread_id'):
                parents.setdefault(thread['id'], spawn['parent_thread_id'])
        except (ValueError, AttributeError):
            pass
        if thread.get('attached_thread_parent_id'):
            parents.setdefault(thread['id'], thread['attached_thread_parent_id'])
        thread.update(journal.read(thread['rollout_path']))
        thread.pop('rollout_path', None)
    config_path = BASE / 'project-map.json'
    config = json.loads(config_path.read_text('utf-8')) if config_path.exists() else {}
    # Desktop and local DB project IDs differ. Match supplied names/roots, not IDs.
    assignments = dict(known_assignments or {})
    for rule in config.get('projects', []):
        target = next((p for p in projects if any(normalized(r) == normalized(rule['root']) for r in p['roots'])), None)
        if target:
            target['name'] = rule['name']
            assignments.update({tid: target['id'] for tid in rule.get('threads', [])})
    grouped = group_threads(projects, threads, parents, assignments)
    if known_assignments is not None:
        for project in grouped:
            if project['id'] == 'unassigned':
                continue
            for room in project['rooms']:
                known_assignments[room['id']] = project['id']
    return {'updatedAt': time.time(), 'error': None, 'projects': grouped}


def is_guardian(source):
    try:
        return json.loads(source).get('subagent', {}).get('other') == 'guardian'
    except (ValueError, AttributeError, TypeError):
        return False


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--home', type=Path, default=HOME)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    journal = Journal()
    target = args.output or BASE / 'runtime' / 'snapshot.json'
    target.parent.mkdir(exist_ok=True)
    assignments_path = BASE / 'runtime' / 'project-assignments.json'
    try:
        assignments = json.loads(assignments_path.read_text('utf-8'))
        if not isinstance(assignments, dict):
            assignments = {}
    except (OSError, ValueError):
        assignments = {}
    while True:
        try:
            data = snapshot(args.home, journal, assignments)
            atomic_json(assignments_path, assignments)
        except Exception as exc:
            data = {'updatedAt': time.time(), 'error': str(exc), 'projects': []}
        try:
            atomic_json(target, data)
        except OSError:
            pass  # Reader may briefly have the old snapshot open on Windows.
        if not args.watch:
            return 1 if data['error'] else 0
        time.sleep(3)


if __name__ == '__main__':
    raise SystemExit(main())
