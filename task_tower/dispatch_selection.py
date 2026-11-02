"""Private dispatcher authority and fresh, read-only Issue selection."""
import json
from pathlib import Path
import re
import shutil
import string

from .project_connections import REPOSITORY, safe_config_path
from .project_worker import issue_lifecycle

TASK_ID = r'TT-[A-Z0-9-]+'


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Invalid dispatcher configuration')
        result[key] = value
    return result


def validate_config(value, connections):
    """Validate trusted installation settings, never remote Issue metadata."""
    if not isinstance(value, dict) or set(value) - {'version', 'allowlist', 'backend', 'interval_seconds'} or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Invalid dispatcher configuration')
    repositories = {c.repository.casefold() for c in connections}
    if len(repositories) != len(connections): raise ValueError('Invalid dispatcher configuration')
    interval = value.get('interval_seconds', 60)
    if type(interval) is not int or not 5 <= interval <= 3600: raise ValueError('Invalid dispatcher configuration')
    allowlist = value.get('allowlist', [])
    if not isinstance(allowlist, list): raise ValueError('Invalid dispatcher configuration')
    normalized, seen, task_ids = [], set(), set()
    for row in allowlist:
        if (not isinstance(row, dict) or set(row) != {'repository', 'issue', 'task_id'}
            or not isinstance(row['repository'], str) or row['repository'].casefold() not in repositories
            or type(row['issue']) is not int or row['issue'] < 1
            or not isinstance(row['task_id'], str) or not re.fullmatch(TASK_ID, row['task_id'])):
            raise ValueError('Invalid dispatcher configuration')
        key = row['repository'].casefold(), row['issue']
        if key in seen or (key[0], row['task_id']) in task_ids: raise ValueError('Invalid dispatcher configuration')
        seen.add(key)
        task_ids.add((key[0], row['task_id']))
        normalized.append(dict(row, repository=key[0]))
    backend = value.get('backend')
    if backend is not None:
        if (not isinstance(backend, dict) or set(backend) != {'argv', 'cwd', 'timeout_seconds'}
            or not isinstance(backend['argv'], list) or not backend['argv']
            or any(not isinstance(a, str) or not a or '\x00' in a for a in backend['argv'])
            or type(backend['timeout_seconds']) is not int or not 1 <= backend['timeout_seconds'] <= 300
            or not isinstance(backend['cwd'], str)):
            raise ValueError('Invalid dispatcher configuration')
        cwd = Path(backend['cwd'])
        if not cwd.is_absolute() or not cwd.is_dir(): raise ValueError('Invalid dispatcher configuration')
        try:
            for arg in backend['argv']:
                for _, field, spec, conversion in string.Formatter().parse(arg):
                    if field is not None and (field not in ('request', 'result', 'checkout') or spec or conversion): raise ValueError()
            if '{' in backend['argv'][0] or '}' in backend['argv'][0]: raise ValueError()
            executable = shutil.which(backend['argv'][0])
            if not executable or Path(executable).suffix.casefold() in ('.bat', '.cmd'): raise ValueError()
        except (ValueError, OSError): raise ValueError('Invalid dispatcher configuration') from None
        backend = dict(argv=[str(Path(executable).resolve()), *backend['argv'][1:]], cwd=str(cwd.resolve()), timeout_seconds=backend['timeout_seconds'])
    return dict(version=1, allowlist=normalized, backend=backend, interval_seconds=interval)


def load_dispatch_config(path: Path, connections: list) -> dict:
    try:
        path = safe_config_path(path).resolve()
        for connection in connections:
            if path.is_relative_to(Path(connection.checkout).resolve()): raise ValueError()
        return validate_config(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs), connections)
    except (ValueError, TypeError, OSError):
        raise ValueError('Invalid dispatcher configuration') from None


def _identity(meta):
    if not isinstance(meta, dict): return None
    ids = [meta[k] for k in ('task_id', 'legacy_id', 'id') if k in meta]
    if not ids or any(not isinstance(i, str) or not re.fullmatch(TASK_ID, i) for i in ids) or len(set(ids)) != 1: return None
    return ids[0]


def identity_matches(snapshot, candidate):
    repo = snapshot.get(candidate['repository'].casefold())
    if not repo or repo['error']: return False
    meta = repo['metadata'].get(candidate['issue'])
    task_id = _identity(meta)
    return (task_id == candidate['task_id'] and meta.get('kind') == 'task'
            and len(repo['index'].get(task_id, [])) == 1)


def collect_snapshot(connections: list, *, store_factory=None, source_factory=None) -> dict:
    # Resolve defaults only at call time: dispatcher imports this collector and
    # owns the existing authenticated GitHubSource factory. Explicit factories
    # retain their original transport seam and never trigger default auth.
    if store_factory is None:
        from .github_tasks import GitHubTasks
        store_factory = GitHubTasks
    if source_factory is None:
        from .dispatcher import _source
        source_factory = _source
    snapshot = {}
    for connection in connections:
        key = connection.repository.casefold()
        project = dict(connection=connection, store=None, source=None, issues={}, index={}, metadata={}, error=None)
        snapshot[key] = project
        try:
            store = project['store'] = store_factory(connection)
            project['source'] = source_factory(connection)
            rows = store.list_issues()
            if not isinstance(rows, list): raise ValueError()
            for row in rows:
                if (not isinstance(row, dict) or type(row.get('number')) is not int or row['number'] < 1
                    or row['number'] in project['issues'] or row.get('state') not in ('open', 'closed') or 'pull_request' in row):
                    raise ValueError()
                project['issues'][row['number']] = row
            for number, row in project['issues'].items():
                try:
                    meta = store.metadata(row)
                    if not isinstance(meta, dict): meta = None
                except Exception: meta = None
                project['metadata'][number] = meta
                task_id = _identity(meta)
                if task_id: project['index'].setdefault(task_id, []).append(number)
        except Exception:
            project.update(error='source_unavailable', issues={}, metadata={}, index={})
    return snapshot


def select_ready(snapshot: dict, allowlist: list, *, verify_done) -> dict:
    ready, excluded, proofs = [], [], {}
    projects = [dict(repository=k, status='unavailable' if p['error'] else 'available', reason=p['error']) for k,p in sorted(snapshot.items())]
    def dependency_proven(key):
        if key in proofs: return proofs[key]
        repo, number = key
        project = snapshot.get(repo)
        proofs[key] = False
        if not project or project['error'] or number not in project['issues'] or project['metadata'].get(number) is None: return False
        task_id = _identity(project['metadata'][number])
        if not task_id or len(project['index'].get(task_id, [])) != 1: return False
        try:
            fresh = project['store'].get(number)
            if not isinstance(fresh, dict) or type(fresh.get('number')) is not int or fresh['number'] != number: return False
            fresh_meta = project['store'].metadata(fresh)
            if _identity(fresh_meta) != task_id or fresh_meta.get('kind') != 'task': return False
            proofs[key] = bool(verify_done(project['connection'], project['store'], project['source'], fresh))
        except Exception: pass
        return proofs[key]
    for auth in allowlist:
        repository = auth['repository'].casefold()
        number, task_id = auth['issue'], auth['task_id']
        identity = dict(repository=repository, issue=number, task_id=task_id)
        project = snapshot.get(repository)
        reason = None
        if not project or project['error']: reason = 'source_unavailable'
        elif number not in project['issues']: reason = 'issue_missing'
        elif not identity_matches(snapshot, identity): reason = 'task_identity_mismatch'
        else:
            row, meta = project['issues'][number], project['metadata'][number]
            if row['state'] != 'open' or meta.get('kind') != 'task' or meta.get('mode') != 'autonomous' or meta.get('status') != 'open': reason = 'not_ready'
            elif meta.get('priority', 'P3') not in ('P0','P1','P2','P3'): reason = 'invalid_priority'
            else:
                try:
                    lifecycle = issue_lifecycle(project['store'], row)
                    if lifecycle.get('status') != 'open' or 'remote_attempt' in lifecycle:
                        reason = 'lifecycle_not_open'
                except Exception: reason = 'lifecycle_unavailable'
            if reason is None:
                try:
                    canonical, legacy = set(), set()
                    for field in ('blocked_by', 'blocked_by_task_ids'):
                        values = meta.get(field, [])
                        if not isinstance(values, list) or any(not isinstance(v,str) for v in values) or len(set(values)) != len(values): raise ValueError()
                        for value in values:
                            if field == 'blocked_by':
                                match = re.fullmatch('(' + REPOSITORY + r')#([1-9][0-9]*)', value)
                                if not match: raise ValueError()
                                key = match[1].casefold(), int(match[2])
                                if key in canonical: raise ValueError()
                                canonical.add(key)
                            else:
                                if not re.fullmatch(TASK_ID, value): raise ValueError()
                                matches = project['index'].get(value, [])
                                if len(matches) != 1: raise ValueError()
                                legacy.add((repository, matches[0]))
                    if 'blocked_by' in meta and 'blocked_by_task_ids' in meta and canonical != legacy: raise ValueError()
                    dependencies = canonical | legacy
                    if (repository,number) in dependencies: raise ValueError()
                    if any(not dependency_proven(key) for key in sorted(dependencies)): reason = 'dependency_unverified'
                except (TypeError, ValueError): reason = 'invalid_dependencies'
        if reason: excluded.append(dict(identity, reason=reason))
        else: ready.append(dict(identity, runner_label=project['connection'].runner_label, priority=meta.get('priority','P3')))
    ready.sort(key=lambda r:(int(r['priority'][1]),r['repository'],r['issue']))
    excluded.sort(key=lambda r:(r['repository'],r['issue']))
    return dict(ready=ready, excluded=excluded, projects=projects)
