"""Fixed remote SELECT for native Beads 1.0.2 events, without Beads initialization.

Dolt's explicit --host route cannot fall back to a local store. Never use
`bd sql`: its 1.0.2 pre-run storage path can perform schema migrations.
"""
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid
from .beads import ServiceError,bead_id,environment
from .native_profiles import verify_binary
from ..project_connections import safe_config_path

FIELDS=('id','issue_id','event_type','actor','old_value','new_value','comment','created_at')


def validate_reader(value):
    fields={'executable','sha256','version','host','port','database','user','password_file','project_id','metadata_sha256'}
    if (not isinstance(value,dict) or set(value)!=fields or value['version']!='1.85.0'
            or not isinstance(value['executable'],str) or not Path(value['executable']).is_absolute()
            or not isinstance(value['sha256'],str) or re.fullmatch('[0-9a-f]{64}',value['sha256']) is None
            or not isinstance(value['metadata_sha256'],str) or re.fullmatch('[0-9a-f]{64}',value['metadata_sha256']) is None
            or value['host']!='127.0.0.1' or type(value['port']) is not int or not 1<=value['port']<=65535
            or any(not isinstance(value[k],str) or re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_-]{0,63}',value[k]) is None for k in ('database','user'))
            or (value['password_file'] is not None and (not isinstance(value['password_file'],str) or not Path(value['password_file']).is_absolute()))):
        raise ValueError('invalid_history_reader')
    try:
        if str(uuid.UUID(value['project_id']))!=value['project_id']:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise ValueError('invalid_history_project') from None


def verify_source(project,profile):
    import hashlib
    from .beads import strict_json
    root=Path(project)/'.beads'
    for name in ('.env','redirect'):
        path=root/name
        if path.exists() or path.is_symlink():raise ServiceError('native_routing_override')
    path=safe_config_path(root/'metadata.json')
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=profile['metadata_sha256']:raise ServiceError('native_source_changed')
    metadata=strict_json(raw.decode('utf-8'))
    allowed={'database','backend','deletions_retention_days','dolt_mode','dolt_server_host','dolt_server_port',
        'dolt_server_user','dolt_database','dolt_server_tls','dolt_data_dir','dolt_remotesapi_port','project_id',
        'global_dolt_database','stale_closed_issues_days','last_bd_version'}
    expected=dict(project_id=profile['project_id'],dolt_mode='server',dolt_server_host=profile['host'],
        dolt_server_port=profile['port'],dolt_database=profile['database'],dolt_server_user=profile['user'])
    if (not isinstance(metadata,dict) or set(metadata)-allowed
            or any(type(metadata.get(k)) is not type(v) or metadata[k]!=v for k,v in expected.items())):
        raise ServiceError('native_source_mismatch')
    # Native 1.0.2 Config.Save serializes this bool with omitempty. Omission is
    # its known false value; explicit true or any non-bool remains unsupported.
    tls=metadata.get('dolt_server_tls',False)
    if type(tls) is not bool or tls:raise ServiceError('native_source_mismatch')


def password(path):
    if path is None:return ''
    from .cli import _windows_private
    path=safe_config_path(Path(path));info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>256 or info.st_nlink!=1:raise ValueError('invalid_password_file')
    if os.name=='nt':_windows_private(path)
    elif info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('password_not_private')
    with path.open('rb') as stream:raw=stream.read(257)
    value=raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
    if len(raw)>256 or any(c in value for c in '\x00\r\n'):raise ValueError('invalid_password_file')
    return value


def query(bead):
    bead_id(bead)  # Excludes quotes, whitespace and every SQL control character.
    columns=','.join(FIELDS)
    project="(SELECT value FROM metadata WHERE `key`='_project_id')"
    identity="SELECT 'identity' AS row_kind,value AS project_id,"+','.join('NULL AS '+f for f in FIELDS)+" FROM metadata WHERE `key`='_project_id'"
    event="SELECT 'event' AS row_kind,"+project+' AS project_id,'+columns
    membership="EXISTS (SELECT 1 FROM wisps WHERE id='"+bead+"')"
    return ('SELECT * FROM ('+identity+' UNION ALL '+event+" FROM events WHERE issue_id='"+bead+"' AND NOT "+membership+
            ' UNION ALL '+event+" FROM wisp_events WHERE issue_id='"+bead+"' AND "+membership+
            ') AS native_events ORDER BY row_kind DESC,created_at DESC,id DESC LIMIT 102')


def read_events(project,bead,profile,runner,timeout):
    bead_id(bead);deadline=time.monotonic()+timeout
    try:
        validate_reader(profile);verify_source(project,profile);verify_binary(profile['executable'],profile['sha256'],deadline)
        if profile['password_file'] is not None and deadline-time.monotonic()<5:raise ServiceError('native_deadline')
        secret=password(profile['password_file'])
        with tempfile.TemporaryDirectory(prefix='tower-native-events-') as temp:
            cwd=Path(temp);(cwd/'home').mkdir()
            settings=cwd/'home/.dolt';settings.mkdir()
            (settings/'config_global.json').write_text('{"metrics.disabled":"true","versioncheck.disabled":"true"}\n',encoding='utf-8')
            env=environment(cwd)
            env.update(DOLT_ROOT_PATH=str(cwd/'home'),DOLT_CLI_PASSWORD=secret,DOLT_CLI_USER=profile['user'],DOLT_DISABLE_EVENT_FLUSH='1')
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ServiceError('native_deadline')
            argv=[profile['executable'],'--host','127.0.0.1','--port',str(profile['port']),'--use-db',profile['database'],
                  '--user',profile['user'],'--no-tls','sql','--disable-auto-gc','--result-format','json','--query',query(bead)]
            result=runner(argv,cwd,remaining,env)
        if not isinstance(result,dict) or set(result)!={'rows'} or not isinstance(result['rows'],list):raise ValueError()
        rows=result['rows']
        if not 1<=len(rows)<=101:raise ValueError()
        identity=[r for r in rows if isinstance(r,dict) and r.get('row_kind')=='identity']
        if len(identity)!=1 or identity[0].get('project_id')!=profile['project_id']:raise ValueError()
        seen=set();events=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'row_kind','project_id',*FIELDS} or row['project_id']!=profile['project_id']:raise ValueError()
            if row['row_kind']=='identity':
                if any(row[k] is not None for k in FIELDS):raise ValueError()
                continue
            if (row['row_kind']!='event' or row['issue_id']!=bead or not isinstance(row['id'],str)
                    or str(uuid.UUID(row['id']))!=row['id'] or row['id'] in seen
                    or any(not isinstance(row[k],str) for k in ('event_type','actor','created_at'))
                    or any(row[k] is not None and not isinstance(row[k],str) for k in ('old_value','new_value','comment'))):raise ValueError()
            seen.add(row['id']);events.append({k:row[k] for k in FIELDS})
        return events
    except ServiceError:raise
    except Exception:raise ServiceError('native_event_history_unknown') from None
