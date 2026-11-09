"""Typed local failure facts. Never serialize exception text, argv or private paths."""
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import shutil
import tempfile
import time
import uuid
from ..project_connections import safe_config_path
from ..service.beads import identity,strict_json

STAGES=frozenset({'validate','prepare','thread_create','thread_attach','turn_start',
                  'notifications','source_capture','review_validate','delivery','quiesce','respond'})
REASONS=frozenset({'unclassified','git_disk_full','git_permission_denied','git_branch_exists',
    'git_capture_not_private','git_capture_unavailable','git_capture_cleanup_unknown',
    'git_operation_unknown','git_cleanup_unconfirmed','dirty_worktree','unowned_worktree',
    'foreign_worktree','foreign_repository','unknown_sha','worktree_unknown_or_conflict',
    'source_changed_during_review','turn_not_completed','turn_start_unknown',
    'rpc_read_queue_full','rpc_line_limit','rpc_invalid_utf8','rpc_invalid_message',
    'rpc_stdout_read_failed','rpc_stdout_eof','owned_app_interrupted'})
OPERATIONS=frozenset({'read','worktree_add','fetch','merge','other'})
STATUSES=frozenset({'passed','failed','unavailable','unknown','timeout','cleanup_failed','cancelled'})

class GitFailure(ValueError):
    def __init__(self,receipt):
        super().__init__('git_operation_unknown')
        self.receipt=receipt

def private_directory(path):
    try:
        if os.name=='nt':
            from ..service.cli import _windows_private
            _windows_private(path)
        else:
            info=path.stat()
            if info.st_uid!=os.getuid() or info.st_mode&0o077:return False
        return True
    except Exception:return False

def create_private_directory(path):
    """Create exclusively; existing directories/ACLs are never modified."""
    path=Path(path);safe_config_path(path/'.guard')
    if os.name!='nt':path.mkdir(mode=0o700);return
    import ctypes
    from ctypes import wintypes as w
    adv=ctypes.WinDLL('advapi32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    adv.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];adv.OpenProcessToken.restype=w.BOOL
    adv.GetTokenInformation.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)];adv.GetTokenInformation.restype=w.BOOL
    adv.ConvertSidToStringSidW.argtypes=[w.LPVOID,ctypes.POINTER(w.LPWSTR)];adv.ConvertSidToStringSidW.restype=w.BOOL
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[w.LPCWSTR,w.DWORD,ctypes.POINTER(w.LPVOID),ctypes.POINTER(w.DWORD)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype=w.BOOL
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    kernel.LocalFree.argtypes=[w.LPVOID];kernel.LocalFree.restype=w.LPVOID
    class Attributes(ctypes.Structure):
        _fields_=[('length',w.DWORD),('descriptor',w.LPVOID),('inherit',w.BOOL)]
    kernel.CreateDirectoryW.argtypes=[w.LPCWSTR,ctypes.POINTER(Attributes)];kernel.CreateDirectoryW.restype=w.BOOL
    token=w.HANDLE();sid_text=w.LPWSTR();descriptor=w.LPVOID()
    try:
        if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(token)):raise ctypes.WinError(ctypes.get_last_error())
        size=w.DWORD();adv.GetTokenInformation(token,1,None,0,ctypes.byref(size))
        if not 0<size.value<=65536:raise OSError('token_identity_unavailable')
        buffer=ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,1,buffer,size,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
        sid=ctypes.cast(buffer,ctypes.POINTER(w.LPVOID))[0]
        if not adv.ConvertSidToStringSidW(sid,ctypes.byref(sid_text)):raise ctypes.WinError(ctypes.get_last_error())
        sddl='O:'+sid_text.value+'D:P(A;OICI;FA;;;'+sid_text.value+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,ctypes.byref(descriptor),None):raise ctypes.WinError(ctypes.get_last_error())
        attributes=Attributes(ctypes.sizeof(Attributes),descriptor,False)
        if not kernel.CreateDirectoryW(str(path),ctypes.byref(attributes)):raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if descriptor:kernel.LocalFree(descriptor)
        if sid_text:kernel.LocalFree(ctypes.cast(sid_text,w.LPVOID))
        if token:kernel.CloseHandle(token)

@contextmanager
def capture_directory():
    parent=Path(tempfile.gettempdir()).absolute()
    path=parent/('tower-connector-git-'+uuid.uuid4().hex)
    try:create_private_directory(path)
    except OSError:raise ValueError('git_capture_unavailable') from None
    before=path.stat()
    try:yield path
    finally:
        try:
            safe_config_path(path/'.guard');after=path.stat()
            if ((before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino)
                    or path.resolve().parent!=parent.resolve()):raise ValueError('capture_identity_changed')
            shutil.rmtree(path)
        except (OSError,ValueError):raise ValueError('git_capture_cleanup_unknown') from None

def git_receipt(args,result,directory):
    operation='worktree_add' if tuple(args[:2])==('worktree','add') else args[0] if args and args[0] in ('fetch','merge') else 'read'
    captured={}
    for stream in ('stdout','stderr'):
        try:
            with (Path(directory)/(stream+'.log')).open('rb') as source:raw=source.read(1048577)
            if len(raw)>1048576:raise ValueError('capture_limit')
            captured[stream]=raw
        except (OSError,ValueError):pass
    stderr=captured.get('stderr',b'').lower()
    reason='git_operation_unknown'
    if result.get('cleanup_confirmed') is not True:reason='git_cleanup_unconfirmed'
    elif result.get('exit_code') not in (0,None):
        if b'no space left on device' in stderr:reason='git_disk_full'
        elif b'permission denied' in stderr:reason='git_permission_denied'
        elif b'already exists' in stderr and b'branch' in stderr:reason='git_branch_exists'
    artifact=dict(retained=False,id=None,stdout_capture_sha256=None,stderr_capture_sha256=None)
    for stream,raw in captured.items():artifact[stream+'_capture_sha256']=hashlib.sha256(raw).hexdigest()
    if len(captured)==2:
        name='task-tower-git-failure-'+uuid.uuid4().hex
        target=Path(tempfile.gettempdir())/name
        try:
            create_private_directory(target)
            if not private_directory(target):raise ValueError('artifact_not_private')
            for stream,raw in captured.items():
                with safe_config_path(target/(stream+'.log')).open('xb') as out:out.write(raw)
            artifact.update(retained=True,id=name)
        except (OSError,ValueError):pass  # Failure to retain raw is explicitly visible.
    process={k:result.get(k) if type(result.get(k)) is bool else None for k in
        ('cleanup_confirmed','stdout_tail_unknown','stderr_tail_unknown','stdout_truncated','stderr_truncated')}
    process['exit_code']=result.get('exit_code') if type(result.get('exit_code')) is int else None
    process['status']=result.get('status') if isinstance(result.get('status'),str) and result['status'] in STATUSES else 'unknown'
    return dict(reason=reason,operation=operation,process=process,artifact=artifact)

def failure_receipt(stage,error):
    reason='unclassified';git=None
    if isinstance(error,GitFailure):
        git=error.receipt;reason=git['reason']
    elif len(error.args)==1 and type(error.args[0]) is str and error.args[0] in REASONS:
        reason=error.args[0]
    value=dict(version=1,stage=stage,reason=reason,git=git)
    validate_receipt(value)
    return value

def validate_receipt(value):
    if (not isinstance(value,dict) or set(value)!={'version','stage','reason','git'}
            or type(value['version']) is not int or value['version']!=1
            or not isinstance(value['stage'],str) or value['stage'] not in STAGES
            or not isinstance(value['reason'],str) or value['reason'] not in REASONS):raise ValueError('invalid_failure_receipt')
    git=value['git']
    if git is not None:
        if (not isinstance(git,dict) or set(git)!={'reason','operation','process','artifact'}
                or git['reason']!=value['reason'] or not isinstance(git['operation'],str) or git['operation'] not in OPERATIONS):raise ValueError('invalid_failure_receipt')
        p=git['process'];a=git['artifact']
        flags={'cleanup_confirmed','stdout_tail_unknown','stderr_tail_unknown','stdout_truncated','stderr_truncated'}
        if (not isinstance(p,dict) or set(p)!=flags|{'exit_code','status'} or not isinstance(p['status'],str) or p['status'] not in STATUSES
                or (p['exit_code'] is not None and type(p['exit_code']) is not int)
                or any(p[k] is not None and type(p[k]) is not bool for k in flags)):raise ValueError('invalid_failure_receipt')
        if (not isinstance(a,dict) or set(a)!={'retained','id','stdout_capture_sha256','stderr_capture_sha256'}
                or type(a['retained']) is not bool
                or (a['retained'] and (not isinstance(a['id'],str) or re.fullmatch(r'task-tower-git-failure-[a-f0-9]{32}',a['id']) is None))
                or (not a['retained'] and a['id'] is not None)
                or any(a[k] is not None and (not isinstance(a[k],str) or re.fullmatch('[a-f0-9]{64}',a[k]) is None)
                       for k in ('stdout_capture_sha256','stderr_capture_sha256'))):raise ValueError('invalid_failure_receipt')
    return value

def inspect_attempt(path,connector,attempt,projects):
    """Bounded snapshot of one owned transport attempt, with no constructor/recovery."""
    identity(connector);identity(attempt)
    path=safe_config_path(Path(path).absolute())
    db=None
    try:
        before=path.stat()
        if not path.is_file() or before.st_nlink!=1:raise ValueError('inspection_unavailable')
        deadline=time.monotonic()+2
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)
        db.set_progress_handler(lambda:time.monotonic()>=deadline,100)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,1048576)
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        expected={'metadata':{'key','value'},'inbox':{'command_id','fingerprint','data'},
                  'outbox':{'seq','event_id','data','acked'},'worktrees':{'attempt_id','data'}}
        for table,columns in expected.items():
            if {r[1] for r in db.execute('PRAGMA table_info('+table+')')}!=columns:raise ValueError('inspection_unavailable')
        if db.execute("SELECT value FROM metadata WHERE key='connector_id'").fetchone()!=(connector,):raise ValueError('inspection_unavailable')
        rows=db.execute("SELECT data FROM inbox WHERE json_extract(data,'$.command.attempt_id')=? LIMIT 33",(attempt,)).fetchall()
        if not rows or len(rows)>32 or sum(len(r[0].encode('utf-8')) for r in rows)>1048576:raise ValueError('inspection_unavailable')
        commands=[];scopes=set()
        phases={'queued','preparing','creating_thread','prepared','starting','executing','needs_input','completed','needs_reconciliation','stopped'}
        kinds={'execute','review','revise','quiesce','respond','deliver','main_review',None}
        for (raw,) in rows:
            data=strict_json(raw);command=data['command'];project=command['project_id'];scopes.add(project)
            if project not in projects or command['attempt_id']!=attempt or data['phase'] not in phases or command.get('kind') not in kinds:
                raise ValueError('inspection_unavailable')
            receipt=data.get('failure_receipt')
            if receipt is not None:validate_receipt(receipt)
            commands.append(dict(kind=command.get('kind'),phase=data['phase'],
                thread_registered=bool(data.get('thread_id')),turn_registered=bool(data.get('turn_id')),
                resource_registered=bool(data.get('resource_id')),failure_receipt=receipt))
        row=db.execute('SELECT data FROM worktrees WHERE attempt_id=?',(attempt,)).fetchone()
        worktree=None
        if row:
            data=strict_json(row[0])
            if (data['project_id'] not in scopes or data['state'] not in ('ready','preparing','merge_pending','base_update_intent')
                    or not isinstance(data['base_sha'],str) or re.fullmatch('[a-f0-9]{40}',data['base_sha']) is None):raise ValueError('inspection_unavailable')
            worktree=dict(state=data['state'],base_sha=data['base_sha'])
        count=db.execute("SELECT COUNT(*) FROM outbox WHERE acked=0 AND json_extract(data,'$.attempt_id')=? AND json_extract(data,'$.connector_id')=?",(attempt,connector)).fetchone()[0]
        after=path.stat()
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):raise ValueError('inspection_unavailable')
        return dict(version=1,commands=commands,worktree=worktree,pending_outbox_count=count)
    except (OSError,sqlite3.Error,KeyError,TypeError,ValueError,RecursionError):
        raise ValueError('inspection_unavailable') from None
    finally:
        if db is not None:db.close()
