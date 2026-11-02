"""Durable installation-local admission and conservative ownership fencing."""
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from .project_connections import safe_config_path, REPOSITORY

APP_ID=1414808657
STATES={'queued','claimed','running','execution_completed','failed','cancelled','timed_out','needs_input','unknown'}
SCHEMA="CREATE TABLE jobs(delivery_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, repository TEXT NOT NULL, issue INTEGER NOT NULL, task_id TEXT NOT NULL, runner_label TEXT NOT NULL, profile_id TEXT NOT NULL, profile_fingerprint TEXT NOT NULL, state TEXT NOT NULL, owner_id TEXT, owner_pid INTEGER, attempt INTEGER NOT NULL, attempt_id TEXT, cancel_requested INTEGER NOT NULL, evidence TEXT NOT NULL)"
HISTORY_SCHEMA="CREATE TABLE attempt_history(run_id TEXT NOT NULL, attempt INTEGER NOT NULL, attempt_id TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL, owner_pid INTEGER, evidence TEXT NOT NULL, PRIMARY KEY(run_id,attempt))"
COLUMNS='delivery_id,run_id,repository,issue,task_id,runner_label,profile_id,profile_fingerprint,state,owner_id,owner_pid,attempt,attempt_id,cancel_requested,evidence'


class ExecutorCancellationFence(ValueError):
    """A committed cancellation prevents launch or a known terminal outcome."""


def _uuid(value):
    try:
        if not isinstance(value,str) or str(uuid.UUID(value))!=value: raise ValueError()
    except (ValueError,AttributeError): raise ValueError('Invalid executor UUID') from None
    return value

def validate_request(value):
    if not isinstance(value,dict) or set(value)!={'operation','delivery_id','repository','issue','task_id','runner_label'} or value['operation'] not in {'submit','lookup'}: raise ValueError('Invalid executor request')
    _uuid(value['delivery_id'])
    if (not isinstance(value['repository'],str) or not re.fullmatch(REPOSITORY,value['repository']) or type(value['issue']) is not int or value['issue']<1 or not isinstance(value['task_id'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,199}',value['task_id']) or not isinstance(value['runner_label'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',value['runner_label'])): raise ValueError('Invalid executor identity')
    return dict(value,repository=value['repository'].casefold())

def _dead(pid):
    if type(pid) is not int or pid<=0: return False
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle: return ctypes.get_last_error()==87
        try:
            code=ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code))) and code.value!=259
        finally: kernel.CloseHandle(ctypes.c_void_p(handle))
    try: os.kill(pid,0)
    except ProcessLookupError: return True
    except PermissionError: pass
    return False

class ExecutionQueue:
    def __init__(self,path,*,checkouts=(),forbidden_paths=()):
        self.path=safe_config_path(path); self.checkouts=tuple(Path(p).resolve() for p in checkouts); self.forbidden_paths=tuple(Path(p) for p in forbidden_paths); self._owners=set(); self._safe()
    def _safe(self):
        for path in [self.path,*(Path(str(self.path)+s) for s in ('-journal','-wal','-shm'))]:
            safe_config_path(path)
            if path.exists() and path.stat().st_nlink!=1: raise ValueError('Unsafe executor queue')
            if any(path.resolve().is_relative_to(c) for c in self.checkouts): raise ValueError('Private queue inside checkout')
            for other in self.forbidden_paths:
                safe_config_path(other)
                if other.exists() and other.stat().st_nlink!=1: raise ValueError('Unsafe executor input')
                if str(path.resolve()).casefold()==str(other.resolve()).casefold() or (path.exists() and other.exists() and os.path.samefile(path,other)): raise ValueError('Executor path collision')
    @contextmanager
    def _db(self,write=False):
        self._safe()
        if not write and not self.path.exists(): yield None; return
        if write: self.path.parent.mkdir(parents=True,exist_ok=True); self._safe()
        if self.path.exists():
            with self.path.open('rb') as stream: header=stream.read(100)
            if (header[:16]==b'SQLite format 3\x00' and header[18:20]!=b'\x01\x01') or any(Path(str(self.path)+s).exists() for s in ('-wal','-shm')): raise ValueError('Unsupported WAL queue')
        try:
            with closing(sqlite3.connect(self.path if write else self.path.resolve().as_uri()+'?mode=ro',uri=not write,timeout=5)) as db:
                db.row_factory=sqlite3.Row
                if write: db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
                else: db.execute('PRAGMA query_only=ON')
                app=db.execute('PRAGMA application_id').fetchone()[0]; version=db.execute('PRAGMA user_version').fetchone()[0]
                objects=list(db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
                if write and app==0 and version==0 and not objects:
                    db.execute('PRAGMA application_id='+str(APP_ID)); db.execute('PRAGMA user_version=2'); db.execute(SCHEMA); db.execute(HISTORY_SCHEMA)
                elif app!=APP_ID or version!=2 or {(r['type'],r['name'],r['sql']) for r in objects}!={('table','jobs',SCHEMA),('table','attempt_history',HISTORY_SCHEMA)}: raise ValueError('Unrecognized executor queue')
                jobs={row['run_id']:dict(row) for row in db.execute('SELECT '+COLUMNS+' FROM jobs')}
                for row in jobs.values(): self._validate(row)
                self._validate_history(db,jobs)
                try:
                    yield db
                    if write: db.commit()
                except BaseException:
                    if write: db.rollback()
                    raise
        except sqlite3.Error: raise ValueError('Executor queue unavailable') from None
    def _validate(self,row):
        validate_request(dict(operation='submit',**{k:row[k] for k in ('delivery_id','repository','issue','task_id','runner_label')}))
        _uuid(row['run_id'])
        if row['repository']!=row['repository'].casefold() or row['state'] not in STATES or not re.fullmatch('[a-f0-9]{64}',row['profile_fingerprint']) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',row['profile_id']) or type(row['attempt']) is not int or row['attempt']<0 or row['cancel_requested'] not in (0,1): raise ValueError('Invalid executor row')
        if row['owner_id'] is not None: _uuid(row['owner_id']); _uuid(row['attempt_id'])
        if (row['owner_id'] is None and row['attempt_id'] is not None) or (row['attempt']==0 and row['owner_id'] is not None) or (row['owner_id'] is None and row['owner_pid'] is not None) or (row['owner_pid'] is not None and (type(row['owner_pid']) is not int or row['owner_pid']<=0)): raise ValueError('Invalid executor ownership')
        if row['state'] in {'claimed','running','unknown','execution_completed','timed_out'} and row['owner_id'] is None: raise ValueError('Invalid executor state ownership')
        if row['state']=='queued' and (row['owner_id'] is not None or row['cancel_requested']): raise ValueError('Invalid queued ownership')
        evidence=json.loads(row['evidence'])
        self._evidence(evidence)
    def _validate_history(self,db,jobs):
        ordinals={run_id:[] for run_id in jobs}
        for saved in db.execute('SELECT * FROM attempt_history ORDER BY run_id,attempt'):
            row=dict(saved)
            _uuid(row['run_id']); _uuid(row['attempt_id']); _uuid(row['owner_id'])
            if (row['run_id'] not in jobs or type(row['attempt']) is not int or not 1<=row['attempt']<=10
                    or (row['owner_pid'] is not None and (type(row['owner_pid']) is not int or row['owner_pid']<=0))):
                raise ValueError('Invalid executor attempt history')
            evidence=json.loads(row['evidence']); self._evidence(evidence)
            if not self._retry_proof(evidence): raise ValueError('Invalid executor retry history')
            ordinals[row['run_id']].append(row['attempt'])
        for run_id,row in jobs.items():
            archived=row['attempt']-(row['owner_id'] is not None)
            if row['attempt']>10 or ordinals[run_id]!=list(range(1,archived+1)):
                raise ValueError('Invalid executor attempt sequence')
            if row['owner_id'] is None and row['evidence']!='{}':
                raise ValueError('Unowned executor evidence')
    @staticmethod
    def _retry_proof(evidence):
        return (evidence.get('started') is False and evidence.get('cleanup_confirmed') is True
                and evidence.get('prelaunch_failure') is True)
    @staticmethod
    def _evidence(value):
        # Only neutral IDs, hashes, numeric counters and booleans. Raw source/logs
        # or arbitrary prose never enter this journal.
        if not isinstance(value,dict) or len(value)>64: raise ValueError('Invalid executor evidence')
        for key,item in value.items():
            if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}',key): raise ValueError('Invalid executor evidence')
            if type(item) in (int,bool) or item is None: continue
            if isinstance(item,str) and (re.fullmatch('[a-f0-9]{40}|[a-f0-9]{64}',item) or re.fullmatch('[0-9a-f-]{36}',item)): continue
            raise ValueError('Unsafe executor evidence')
    @staticmethod
    def _receipt(row): return dict(version=1,delivery_id=row['delivery_id'],status='accepted',receipt_id=row['run_id'])
    def submit(self,request,profile_fingerprint,*,profile_id='default'):
        r=validate_request(request)
        if r['operation']!='submit' or not isinstance(profile_fingerprint,str) or not re.fullmatch('[a-f0-9]{64}',profile_fingerprint) or not isinstance(profile_id,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',profile_id): raise ValueError('Invalid admission')
        with self._db(True) as db:
            row=db.execute('SELECT * FROM jobs WHERE delivery_id=?',(r['delivery_id'],)).fetchone()
            if row is None:
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(r['delivery_id'],str(uuid.uuid4()),r['repository'],r['issue'],r['task_id'],r['runner_label'],profile_id,profile_fingerprint,'queued',None,None,0,None,0,'{}'))
                row=db.execute('SELECT * FROM jobs WHERE delivery_id=?',(r['delivery_id'],)).fetchone()
            if any(row[k]!=r[k] for k in ('repository','issue','task_id','runner_label')) or row['profile_id']!=profile_id or row['profile_fingerprint']!=profile_fingerprint: raise ValueError('Delivery identity collision')
            result=self._receipt(row)
        return result
    def lookup(self,delivery_id):
        _uuid(delivery_id)
        with self._db() as db:
            row=None if db is None else db.execute('SELECT * FROM jobs WHERE delivery_id=?',(delivery_id,)).fetchone()
            return None if row is None else self._receipt(row)
    def status(self,run_id):
        _uuid(run_id)
        with self._db() as db:
            row=None if db is None else db.execute('SELECT * FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if row is None: raise ValueError('Executor run not found')
            result=dict(row); result['evidence']=json.loads(result['evidence']); return result
    @contextmanager
    def owner(self,owner_id):
        # Lifetime registration: claims made without this guard have no death
        # proof and recovery cannot change them. No timeout can transfer ownership.
        _uuid(owner_id)
        if owner_id in self._owners: raise ValueError('Owner already registered')
        self._owners.add(owner_id)
        try: yield owner_id
        finally: self._owners.remove(owner_id)
    def claim(self,owner_id,*,max_active=2):
        _uuid(owner_id)
        if type(max_active) is not int or not 1<=max_active<=2: raise ValueError('Invalid active bound')
        with self._db(True) as db:
            if db.execute("SELECT count(*) FROM jobs WHERE state IN ('claimed','running','unknown')").fetchone()[0]>=max_active: return None
            row=db.execute("SELECT * FROM jobs WHERE state='queued' AND cancel_requested=0 ORDER BY rowid LIMIT 1").fetchone()
            if row is None: return None
            db.execute("UPDATE jobs SET state='claimed',owner_id=?,owner_pid=?,attempt=attempt+1,attempt_id=? WHERE run_id=? AND state='queued'",(owner_id,os.getpid() if owner_id in self._owners else None,str(uuid.uuid4()),row['run_id']))
            result=dict(db.execute('SELECT * FROM jobs WHERE run_id=?',(row['run_id'],)).fetchone()); result['evidence']=json.loads(result['evidence'])
        return result
    def record(self,run_id,owner_id,state,evidence):
        _uuid(run_id); _uuid(owner_id); self._evidence(evidence)
        allowed={'claimed':{'claimed','running','failed','cancelled','needs_input','unknown'},'running':{'running','execution_completed','failed','cancelled','timed_out','needs_input','unknown'}}
        with self._db(True) as db:
            row=db.execute('SELECT * FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if row is None or row['owner_id']!=owner_id or state not in allowed.get(row['state'],set()): raise ValueError('Invalid executor transition')
            # BEGIN IMMEDIATE serializes this check with public cancel(). No
            # slow worker/probe/model work occurs inside this transaction.
            # Unknown cleanup/control remains stronger than cancellation.
            if row['cancel_requested'] and state in ('running','execution_completed','failed','needs_input','timed_out'):
                raise ExecutorCancellationFence('Executor cancellation committed')
            saved=json.loads(row['evidence'])
            if any(key in saved and (type(saved[key]) is not type(value) or saved[key]!=value) for key,value in evidence.items()):
                raise ValueError('Conflicting executor evidence')
            saved.update(evidence)
            db.execute('UPDATE jobs SET state=?,evidence=? WHERE run_id=? AND owner_id=? AND state=?',(state,json.dumps(saved,sort_keys=True),run_id,owner_id,row['state']))
    def cancel(self,run_id):
        _uuid(run_id)
        with self._db(True) as db:
            row=db.execute('SELECT state FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if row is None: raise ValueError('Executor run not found')
            db.execute("UPDATE jobs SET cancel_requested=1,state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END WHERE run_id=?",(run_id,))
    def history(self,run_id):
        """Return immutable neutral evidence for explicitly retried attempts."""
        _uuid(run_id)
        with self._db() as db:
            if db is None or db.execute('SELECT 1 FROM jobs WHERE run_id=?',(run_id,)).fetchone() is None:
                raise ValueError('Executor run not found')
            result=[]
            for saved in db.execute('SELECT * FROM attempt_history WHERE run_id=? ORDER BY attempt',(run_id,)):
                row=dict(saved); row['evidence']=json.loads(row['evidence']); result.append(row)
            return result
    def retry_prelaunch(self,run_id,*,profile_fingerprint,max_attempts):
        """Explicit retry only after positive no-child proof; never recover work.

        Version 2 archives the complete attempt before clearing its current fields.
        Existing version 1 queues are rejected rather than silently migrated.
        """
        _uuid(run_id)
        if (not isinstance(profile_fingerprint,str) or not re.fullmatch('[a-f0-9]{64}',profile_fingerprint)
                or type(max_attempts) is not int or not 1<=max_attempts<=10):
            raise ValueError('Invalid executor retry policy')
        with self._db(True) as db:
            saved=db.execute('SELECT * FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if (saved is None or saved['state']!='failed' or saved['cancel_requested']
                    or saved['profile_fingerprint']!=profile_fingerprint or saved['owner_id'] is None
                    or not 1<=saved['attempt']<max_attempts or not self._retry_proof(json.loads(saved['evidence']))):
                raise ValueError('Executor retry not authorized')
            db.execute('INSERT INTO attempt_history VALUES(?,?,?,?,?,?)',tuple(saved[key] for key in
                ('run_id','attempt','attempt_id','owner_id','owner_pid','evidence')))
            changed=db.execute("UPDATE jobs SET state='queued',owner_id=NULL,owner_pid=NULL,attempt_id=NULL,evidence='{}' WHERE run_id=? AND state='failed' AND owner_id=? AND attempt_id=? AND attempt=? AND cancel_requested=0 AND profile_fingerprint=?",
                (run_id,saved['owner_id'],saved['attempt_id'],saved['attempt'],profile_fingerprint)).rowcount
            if changed!=1: raise ValueError('Executor retry state changed')
            row=dict(db.execute('SELECT * FROM jobs WHERE run_id=?',(run_id,)).fetchone())
            row['evidence']=json.loads(row['evidence'])
        return row
    def recover(self):
        recovered=[]
        # BEGIN IMMEDIATE excludes all concurrent claims and transitions while
        # positive local death is checked. Live/PID-reused/unprovable owners stay.
        with self._db(True) as db:
            for row in db.execute("SELECT * FROM jobs WHERE state IN ('claimed','running')"):
                if _dead(row['owner_pid']):
                    db.execute("UPDATE jobs SET state='unknown' WHERE run_id=? AND owner_id=? AND state=?",(row['run_id'],row['owner_id'],row['state'])); recovered.append(row['run_id'])
        return recovered
