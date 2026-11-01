"""Private legacy provenance. Active cards and historical hashes are never edited.

Cooperating local migrations serialize through SQLite. Identity/hash rechecks and
CAS publication detect observed filesystem races; they are not a hostile OS
filesystem sandbox or a distributed first-creation lock.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from .creation_journal import CreationJournal
from .github_tasks import GitHubTasks
from .project_connections import safe_config_path

MAX_CARD = 1024 * 1024
MAX_REGISTRY = 8 * 1024 * 1024


def registry_path(connection):
    return connection.checkout / '.task-tower' / 'capture-migrations.json'


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink)


def _read_source(path, limit=MAX_CARD):
    path=safe_config_path(path)
    before=path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError('Unsafe migration input')
    with path.open('rb') as stream:
        if _signature(os.fstat(stream.fileno())) != _signature(before): raise ValueError('Migration input changed')
        raw=stream.read(limit+1)
        after=os.fstat(stream.fileno())
    safe_config_path(path)
    if len(raw)>limit or _signature(before)!=_signature(after) or _signature(after)!=_signature(path.stat()):
        raise ValueError('Migration input changed or exceeds limit')
    return raw,_signature(after)


def _recheck(path, expected):
    if _read_source(path) != expected: raise ValueError('Migration source changed; inspect existing Issue')


def _registry(path):
    safe_config_path(path)
    if not path.exists(): return None, None, {'version':1,'records':[]}
    raw,identity=_read_source(path,MAX_REGISTRY)
    value=json.loads(raw.decode('utf-8'))
    if not isinstance(value,dict) or set(value)!={'version','records'} or value['version']!=1 or not isinstance(value['records'],list):
        raise ValueError('Invalid migration registry; preserve it')
    required={'repository','repository_id','legacy_id','source_path','source_sha256','issue_url','number','at'}
    for row in value['records']:
        if not isinstance(row,dict) or set(row)!=required: raise ValueError('Invalid migration registry')
        if not all(isinstance(row[k],str) for k in ('repository','repository_id','legacy_id','source_path','source_sha256','at')):
            raise ValueError('Invalid migration registry')
        import re
        if not re.fullmatch('[a-f0-9]{64}',row['source_sha256']): raise ValueError('Invalid migration registry')
        if row['number'] is None:
            if row['issue_url'] is not None: raise ValueError('Invalid migration registry')
        elif type(row['number']) is not int or row['number']<1 or row['issue_url']!=f"https://github.com/{row['repository']}/issues/{row['number']}":
            raise ValueError('Invalid migration registry')
    return raw,identity,value


def _publish(path,value,expected,source=None):
    path=safe_config_path(path)
    if _registry(path)[:2] != expected: raise ValueError('Migration registry changed')
    descriptor,temporary=tempfile.mkstemp(dir=path.parent,prefix='.migration-registry-')
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(json.dumps(value,ensure_ascii=True,sort_keys=True).encode('utf-8'))
            stream.flush(); os.fsync(stream.fileno())
        safe_config_path(path)
        if _registry(path)[:2] != expected: raise ValueError('Migration registry changed')
        if source is not None: _recheck(*source)
        if expected[0] is None: os.link(temporary,path)
        else: os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _result(row,status,error=None):
    result=dict(status=status,number=row['number'],issue_url=row['issue_url'],source_errors=[])
    if error: result['source_errors'].append(error)
    return result


def _protected(connection,path):
    private=connection.checkout/'.task-tower'
    # Runtime state, lock/journal sidecars and temporary snapshots are never cards.
    if path.is_relative_to(private): raise ValueError('Migration input aliases private state')


def migrate_card(connection,path:Path,*,store=None):
    path=safe_config_path(path); _protected(connection,path)
    original=_read_source(path)
    raw=json.loads(original[0].decode('utf-8'))
    if not isinstance(raw,dict) or not isinstance(raw.get('id'),str) or not raw['id'].strip() or len(raw['id'])>1024 or '\x00' in raw['id']:
        raise ValueError('Invalid legacy identity')
    _recheck(path,original)
    target=registry_path(connection)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Validate ancestors before opening either the registry lock or publication.
    safe_config_path(target)
    lock=CreationJournal(target.with_name(target.name+'.lock.sqlite3'))
    with lock.transaction():
        before,identity,registry=_registry(target)
        digest=hashlib.sha256(original[0]).hexdigest()
        matches=[r for r in registry['records'] if r['repository'].casefold()==connection.repository.casefold() and (r['legacy_id']==raw['id'] or r['source_path']==str(path))]
        for row in matches:
            if row['legacy_id']!=raw['id'] or row['source_sha256']!=digest:
                return _result(row,'needs_input','Legacy source drift or identity conflict; inspect canonical Issue')
        row=next((r for r in matches if r['source_path']==str(path)),None)
        existing=bool(row and row['number'] is not None)
        store=store or GitHubTasks(connection)
        from .project_onboarding import preflight
        repository=preflight(connection,store)
        if any(r['repository_id']!=str(repository['id']) for r in matches): raise ValueError('Repository identity changed')
        _recheck(path,original)
        if row is None:
            row=dict(repository=connection.repository,repository_id=str(repository['id']),legacy_id=raw['id'],source_path=str(path),source_sha256=digest,issue_url=None,number=None,at=datetime.now(timezone.utc).isoformat())
            registry['records'].append(row)
            _publish(target,registry,(before,identity),(path,original))
        expected=_registry(target)[:2]
        descriptor,temporary=tempfile.mkstemp(dir=target.parent,prefix='.migration-input-',suffix='.json')
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(original[0]); stream.flush(); os.fsync(stream.fileno())
            snapshot=Path(temporary)
            snapshot_expected=_read_source(snapshot)
            _recheck(path,original)
            _recheck(snapshot,snapshot_expected)
            issue=store.import_card(snapshot)
            number=issue.get('number')
            if type(number) is not int or number<1: raise ValueError('Migration outcome uncertain; retain journal')
            if row['number'] is not None and row['number']!=number:
                return _result(row,'needs_input','Canonical Issue identity changed; inspect without replacing provenance')
            row.update(number=number,issue_url=f'https://github.com/{connection.repository}/issues/{number}')
            try:
                _recheck(path,original)
                _publish(target,registry,expected,(path,original))
            except (ValueError,OSError):
                return _result(row,'needs_input','Canonical Issue retained; source or registry changed. Restore original input and retry; never delete creation intents')
            sync=issue.get('project_sync',{})
            return _result(row,('existing' if existing else 'migrated') if sync.get('status')=='synced' else 'needs_input',None if sync.get('status')=='synced' else 'Canonical Issue retained; retry migration to repair Project membership')
        finally:
            Path(temporary).unlink(missing_ok=True)


def migration_state(connection,path:Path):
    path=safe_config_path(path)
    _,_,registry=_registry(registry_path(connection))
    rows=[r for r in registry['records'] if r['repository'].casefold()==connection.repository.casefold() and r['source_path']==str(path)]
    if len(rows)>1: raise ValueError('Ambiguous migration registry')
    if not rows: return dict(status='unmapped')
    row=rows[0]
    try: current=hashlib.sha256(_read_source(path)[0]).hexdigest()==row['source_sha256']
    except (ValueError,OSError): current=False
    return _result(row,'stale' if not current else ('current' if row['number'] else 'pending'))


def book_migrations(connection):
    """Public projection deliberately excludes installation paths and card contents."""
    _,_,registry=_registry(registry_path(connection))
    result=[]
    for row in registry['records']:
        if row['repository'].casefold()!=connection.repository.casefold(): continue
        state=migration_state(connection,Path(row['source_path']))
        result.append(dict(number=row['number'],source_sha256=row['source_sha256'],status=state['status'],issue_url=row['issue_url']))
    return result

