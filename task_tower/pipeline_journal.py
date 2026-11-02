"""Durable installation-local pipeline evidence; unknown work is never replayed."""
from contextlib import contextmanager, closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid
from .executor_queue import _uuid, _dead, validate_request, _private_stat
from .pipeline_inputs import canonical_json, digest_manifest, validate_stage_manifest, _relative
from .project_connections import safe_config_path, REPOSITORY

APP_ID=1414808656
STAGES=('spec','development','test')
STATES={'queued','preparing','executing','reviewing','checking','ready','publishing','ready_for_pr','awaiting_pr','needs_input','cancelled','timed_out','unknown'}
ACTIVE={'preparing','executing','reviewing','checking','ready','publishing','unknown'}
ROLES={s+'_'+r for s in STAGES for r in ('executor','reviewer')}
REASONS={None,'owner_dead','stale_input','environment_unavailable','criteria_unmet','plan_incomplete','product_defect','test_failure','evidence_missing','size_limit','rework_limit','process_limit','deadline','cancelled','policy_revoked','source_unavailable','effect_unknown','cleanup_unknown','launch_unknown','completed','blocked','conflict'}
SCHEMAS={
'runs':'CREATE TABLE runs(run_id TEXT PRIMARY KEY, delivery_id TEXT NOT NULL UNIQUE, repository TEXT NOT NULL, issue INTEGER NOT NULL, issue_id INTEGER, task_id TEXT NOT NULL, runner_label TEXT NOT NULL, profile_id TEXT NOT NULL, profile_fingerprint TEXT NOT NULL, policy_sha256 TEXT NOT NULL, criteria_sha256 TEXT, superpowers_sha256 TEXT, source_sha TEXT, base_sha TEXT, checkpoint_sha TEXT, branch TEXT NOT NULL, worktree TEXT, git_dir TEXT, admission TEXT, state TEXT NOT NULL, stage TEXT NOT NULL, generation INTEGER NOT NULL, owner_id TEXT, owner_pid INTEGER, cancel_requested INTEGER NOT NULL, created_at TEXT NOT NULL, deadline_at TEXT, updated_at TEXT NOT NULL, reworks TEXT NOT NULL, process_count INTEGER NOT NULL, component_keys TEXT NOT NULL, input_sha256 TEXT, manifest TEXT, reason TEXT, limits TEXT NOT NULL, UNIQUE(repository,issue))',
'attempts':'CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, generation INTEGER NOT NULL, stage TEXT NOT NULL, role TEXT NOT NULL, instance_id TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL, input_sha256 TEXT NOT NULL, check_id TEXT, check_sha256 TEXT, state TEXT NOT NULL, launch_intent TEXT NOT NULL, evidence TEXT, result_sha256 TEXT, artifacts TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT)',
'verdicts':'CREATE TABLE verdicts(receipt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL, generation INTEGER NOT NULL, input_sha256 TEXT NOT NULL, executor_instance_id TEXT NOT NULL, reviewer_instance_id TEXT NOT NULL, decision TEXT NOT NULL, return_stage TEXT, receipt_sha256 TEXT NOT NULL, body TEXT NOT NULL, superseded INTEGER NOT NULL)',
'effects':'CREATE TABLE effects(effect_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, kind TEXT NOT NULL, owner_id TEXT NOT NULL, intent_sha256 TEXT NOT NULL, intent TEXT NOT NULL, status TEXT NOT NULL, observation_sha256 TEXT, observation TEXT, UNIQUE(run_id,ordinal))',
'events':'CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL, reason TEXT, old_state TEXT, new_state TEXT, attempt_id TEXT, effect_id TEXT, receipt_id TEXT, old_owner_id TEXT, new_owner_id TEXT, target_stage TEXT, generation_floor INTEGER, timestamp TEXT NOT NULL)',
'controller':'CREATE TABLE controller(singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner_id TEXT NOT NULL, owner_pid INTEGER, started_at TEXT NOT NULL, last_tick_at TEXT NOT NULL, policy_sha256 TEXT NOT NULL, health TEXT NOT NULL)'}

def _now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def _dump(value): return canonical_json(value).decode('ascii')
def _sha(value,size=64,nullable=False):
    if nullable and value is None: return
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{'+str(size)+'}',value): raise ValueError('Invalid pipeline digest')
def _integer(value,low,high):
    if type(value) is not int or not low<=value<=high: raise ValueError('Invalid pipeline integer')
    return value
def _json(text):
    value=json.loads(text)
    if _dump(value)!=text or len(text.encode())>16*1024*1024: raise ValueError('Invalid canonical pipeline JSON')
    return value

def _neutral(value):
    if not isinstance(value,dict) or len(value)>64 or len(canonical_json(value))>65536: raise ValueError('Invalid neutral evidence')
    strings=STATES|{'completed','failed','passed','approve','reject','not_started','running','launch_intent'}|set(STAGES)|{r for r in REASONS if r}
    def walk(item):
        if item is None or type(item) in (bool,int): return
        if type(item) is float and item>=0: return
        if isinstance(item,str) and (item in strings or re.fullmatch('[a-f0-9]{40}|[a-f0-9]{64}|[0-9a-f-]{36}',item)): return
        if isinstance(item,list) and len(item)<=100:
            for child in item: walk(child)
            return
        if isinstance(item,dict) and len(item)<=64:
            for key,child in item.items():
                if not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}',key): raise ValueError('Unsafe evidence key')
                if key.endswith('_sha256'): _sha(child,nullable=key=='result_sha256')
                elif key.endswith('_sha'): _sha(child,40)
                elif key in {'run_id','attempt_id','instance_id','owner_id','executor_instance_id','reviewer_instance_id','reviewer_attempt_id','effect_id','receipt_id'}: _uuid(child)
                elif key in {'generation','issue_id','owner_pid','pid'}: _integer(child,1,2**63-1)
                elif key.endswith(('_count','_bytes')): _integer(child,0,2**63-1)
                elif key=='exit_code' and child is not None:
                    if type(child) is not int: raise ValueError('Invalid process exit code')
                elif key in {'started','cleanup_confirmed','source_unchanged','cancel_requested'} or key.endswith('_truncated'):
                    if type(child) is not bool: raise ValueError('Invalid Boolean evidence')
                elif key in {'duration','duration_seconds','elapsed_seconds'}:
                    if type(child) not in (int,float) or child<0: raise ValueError('Invalid duration evidence')
                if key=='check_id' and isinstance(child,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',child): continue
                walk(child)
            return
        raise ValueError('Unsafe pipeline evidence')
    walk(value)

class PipelineJournal:
    def __init__(self,path:Path,*,checkouts=(),forbidden_paths=()):
        self.path=safe_config_path(path); self.checkouts=tuple(Path(p).resolve() for p in checkouts)
        self.forbidden_paths=tuple(Path(p) for p in forbidden_paths); self._owners=set(); self._safe()
    @contextmanager
    def operation_deadline(self,deadline):
        """One host monotonic budget across DB operations, never a renewed lease."""
        if type(deadline) not in (int,float):raise ValueError('Invalid journal deadline')
        previous=getattr(self,'_operation_deadline',None)
        self._operation_deadline=min(previous,deadline) if previous is not None else deadline
        try:yield
        finally:self._operation_deadline=previous
    def _wait_seconds(self):
        deadline=getattr(self,'_operation_deadline',None)
        remaining=5 if deadline is None else min(5,deadline-time.monotonic())
        if remaining<=0:raise ValueError('Pipeline journal operation deadline exhausted')
        return remaining
    @contextmanager
    def _existing_database(self,identity):
        previous=getattr(self,'_existing_database_identity',None)
        self._existing_database_identity=identity
        try:
            self._assert_existing()
            yield
        finally:self._existing_database_identity=previous
    def _assert_existing(self):
        self._wait_seconds();self._safe()
        identity=getattr(self,'_existing_database_identity',None)
        if identity is None or not os.path.samestat(identity,_private_stat(self.path)):
            raise ValueError('Existing pipeline database missing or replaced')
        self._wait_seconds()
    def _safe(self):
        for path in [self.path,*(Path(str(self.path)+s) for s in ('-journal','-wal','-shm'))]:
            safe_config_path(path)
            try:_private_stat(path,transient=path!=self.path)
            except FileNotFoundError:pass
            if any(path.resolve().is_relative_to(c) for c in self.checkouts): raise ValueError('Private pipeline state inside checkout')
            for other in self.forbidden_paths:
                safe_config_path(other)
                if other.exists():_private_stat(other)
                for alias in [other,*(Path(str(other)+s) for s in ('-journal','-wal','-shm'))]:
                    if str(path.resolve()).casefold()==str(alias.resolve()).casefold():raise ValueError('Pipeline private path collision')
                    try:same=path.exists() and alias.exists() and os.path.samefile(path,alias)
                    except FileNotFoundError:same=False  # SQLite removed its transient sidecar.
                    if same:raise ValueError('Pipeline private path collision')
    @contextmanager
    def _db(self,write=False,*,initialize=True):
        self._wait_seconds()
        self._safe()
        existing=getattr(self,'_existing_database_identity',None) is not None
        if existing:
            initialize=False
            self._assert_existing()
        if not self.path.exists() and not write:
            if existing:raise ValueError('Existing pipeline database missing')
            yield None; return
        if write:
            if initialize:self.path.parent.mkdir(parents=True,exist_ok=True)
            self._safe()
        if any(Path(str(self.path)+s).exists() for s in ('-wal','-shm')): raise ValueError('Unsupported pipeline WAL')
        if self.path.exists():
            with self.path.open('rb') as stream: header=stream.read(100)
            if header[:16]==b'SQLite format 3\0' and header[18:20]!=b'\1\1': raise ValueError('Unsupported pipeline WAL')
        try:
            uri=not write or not initialize
            target=self.path.resolve().as_uri()+('?mode=rw' if write else '?mode=ro') if uri else self.path
            with closing(sqlite3.connect(target,uri=uri,timeout=self._wait_seconds())) as db:
                db.row_factory=sqlite3.Row; db.execute('PRAGMA busy_timeout='+str(max(0,int(self._wait_seconds()*1000)))); db.execute('PRAGMA synchronous=FULL')
                db.execute('PRAGMA busy_timeout='+str(max(0,int(self._wait_seconds()*1000))))
                if write: db.execute('BEGIN IMMEDIATE')
                else:
                    db.execute('PRAGMA query_only=ON')
                    if getattr(self,'_operation_deadline',None) is not None:db.execute('BEGIN')
                app=db.execute('PRAGMA application_id').fetchone()[0]; version=db.execute('PRAGMA user_version').fetchone()[0]
                objects={(r[0],r[1],r[2]) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
                if write and initialize and app==0 and version==0 and not objects:
                    db.execute('PRAGMA application_id='+str(APP_ID)); db.execute('PRAGMA user_version=1')
                    for schema in SCHEMAS.values(): db.execute(schema)
                elif app!=APP_ID or version!=1 or objects!={('table',n,s) for n,s in SCHEMAS.items()}: raise ValueError('Unrecognized pipeline schema')
                if db.execute('PRAGMA journal_mode').fetchone()[0]!='delete' or db.execute('PRAGMA synchronous').fetchone()[0]!=2: raise ValueError('Unsafe pipeline durability mode')
                self._validate_db(db)
                try:
                    yield db
                    if write:
                        if existing:self._assert_existing()
                        remaining=self._wait_seconds()
                        # Shutdown must not enter a fresh lock wait at COMMIT.
                        # A conflicting reader makes this bounded transaction
                        # roll back, retaining uncertain ownership.
                        wait=0 if getattr(self,'_operation_deadline',None) is not None else int(remaining*1000)
                        db.execute('PRAGMA busy_timeout='+str(wait))
                        db.commit()
                except BaseException:
                    if write: db.rollback()
                    raise
        except sqlite3.Error as error: raise ValueError('Pipeline journal unavailable') from error
    @staticmethod
    def _host_directory(value):
        if not isinstance(value,str) or not value or '\x00' in value or not Path(value).is_absolute():
            raise ValueError('Invalid host directory')
        path=Path(value)
        if path!=Path(os.path.abspath(value)) or any(part in ('.','..') or part.endswith((' ','.')) for part in path.parts[1:]):
            raise ValueError('Unsafe host directory alias')
        for part in path.parts[1:]:
            if any(ord(c)<32 or ord(c)==127 or c in '<>"|?*:' for c in part) or re.fullmatch(r'(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])',part.split('.')[0]):
                raise ValueError('Nonportable host directory')
        if any(p.exists() and not p.is_dir() for p in (path,*path.parents)): raise ValueError('Host directory is not a directory')
        safe_config_path(path/'.pipeline-directory-check')
        return value

    @staticmethod
    def _components(value):
        if not isinstance(value,list) or not value or len(value)>100 or any(not isinstance(v,str) or not re.fullmatch(r'\*|[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',v) for v in value) or len(set(value))!=len(value) or '*' in value and len(value)!=1: raise ValueError('Invalid components')
        return value
    @staticmethod
    def _limits(value):
        bounds={'task_timeout_seconds':(1,86400),'max_processes':(6,100),'max_reworks':(0,5),'role_timeout_seconds':(1,3600),'log_max_bytes':(1,67108864)}
        if not isinstance(value,dict) or set(value)!=set(bounds): raise ValueError('Invalid run limits')
        for key,bound in bounds.items(): _integer(value[key],*bound)
        return value
    @staticmethod
    def _artifacts(value):
        if not isinstance(value,dict) or set(value)-{'request','result','stdout','stderr'} or len(set(value.values()))!=len(value): raise ValueError('Invalid attempt artifacts')
        for path in value.values(): _relative(path)
    @staticmethod
    def _admission(value):
        keys={'version','repository','issue','issue_id','task_id','runner_label','criteria','criteria_sha256','policy_sha256','profile_id','profile_fingerprint','source_sha','base_sha'}
        if not isinstance(value,dict) or set(value)!=keys or type(value['version']) is not int or value['version']!=1 or not isinstance(value['criteria'],dict): raise ValueError('Invalid immutable admission')
        if digest_manifest(value['criteria'])!=value['criteria_sha256']: raise ValueError('Criteria digest mismatch')
        for key in ('criteria_sha256','policy_sha256','profile_fingerprint'): _sha(value[key])
        for key in ('source_sha','base_sha'): _sha(value[key],40)
        _integer(value['issue_id'],1,2**63-1)
        return value
    def _validate_db(self,db):
        runs={r['run_id']:dict(r) for r in db.execute('SELECT * FROM runs')}
        for row in runs.values():
            _uuid(row['run_id']); _uuid(row['delivery_id'])
            validate_request(dict(operation='submit',**{k:row[k] for k in ('delivery_id','repository','issue','task_id','runner_label')}))
            if row['repository']!=row['repository'].casefold() or row['state'] not in STATES or row['stage'] not in STAGES or row['reason'] not in REASONS: raise ValueError('Invalid pipeline state')
            _integer(row['generation'],1,1000); _integer(row['process_count'],0,100); _integer(row['cancel_requested'],0,1)
            for key in ('profile_fingerprint','policy_sha256'): _sha(row[key])
            if row['issue_id'] is not None: _integer(row['issue_id'],1,2**63-1)
            for key in ('worktree','git_dir'):
                if row[key] is not None: self._host_directory(row[key])
            for key in ('source_sha','base_sha','checkpoint_sha'): _sha(row[key],40,True)
            for key in ('criteria_sha256','input_sha256','superpowers_sha256'): _sha(row[key],nullable=True)
            if row['owner_id'] is not None: _uuid(row['owner_id'])
            if row['owner_pid'] is not None: _integer(row['owner_pid'],1,2**63-1)
            if row['owner_id'] is None and row['owner_pid'] is not None or row['state'] in ACTIVE and row['owner_id'] is None: raise ValueError('Invalid pipeline ownership')
            if row['branch']!='pipeline/'+row['run_id']: raise ValueError('Invalid pipeline branch')
            self._components(_json(row['component_keys'])); self._limits(_json(row['limits']))
            reworks=_json(row['reworks'])
            if set(reworks)!=set(STAGES): raise ValueError('Invalid rework counters')
            for number in reworks.values(): _integer(number,0,6)
            for key in ('created_at','updated_at','deadline_at'):
                if row[key] is not None and datetime.datetime.fromisoformat(row[key]).tzinfo is None: raise ValueError('Naive pipeline time')
            if row['admission'] is not None:
                admission=self._admission(_json(row['admission']))
                for key in ('repository','issue','issue_id','task_id','runner_label','criteria_sha256','policy_sha256','profile_id','profile_fingerprint','source_sha','base_sha'):
                    if type(row[key]) is not type(admission[key]) or row[key]!=admission[key]: raise ValueError('Admission identity mismatch')
            if row['manifest'] is not None:
                manifest=validate_stage_manifest(_json(row['manifest']))
                if digest_manifest(manifest)!=row['input_sha256'] or any(manifest[k]!=row[k] for k in ('run_id','stage','generation')): raise ValueError('Invalid current manifest')
        for table,key in [('attempts','attempt_id'),('verdicts','receipt_id'),('effects','effect_id')]:
            for saved in db.execute('SELECT * FROM '+table):
                row=dict(saved); _uuid(row[key])
                if row['run_id'] not in runs: raise ValueError('Orphan history')
                if table=='attempts':
                    _uuid(row['instance_id']); _uuid(row['owner_id']); _sha(row['input_sha256']); _integer(row['generation'],1,1000)
                    if row['stage'] not in STAGES or row['role'] not in ROLES|{'host_check'} or (row['role']!='host_check' and row['role'].split('_')[0]!=row['stage']) or (row['role']=='host_check' and row['stage']!='test') or row['state'] not in {'launch_intent','completed','failed','needs_input','unknown'}: raise ValueError('Invalid attempt')
                    if row['role']=='host_check':
                        if not isinstance(row['check_id'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',row['check_id']): raise ValueError('Invalid check ID')
                        _sha(row['check_sha256'])
                    elif row['check_id'] is not None or row['check_sha256'] is not None: raise ValueError('Model role cannot carry check policy')
                    validate_stage_manifest(_json(row['launch_intent'])); self._artifacts(_json(row['artifacts']))
                    if row['evidence'] is not None: _neutral(_json(row['evidence']))
                    _sha(row['result_sha256'],nullable=True)
                elif table=='effects':
                    _uuid(row['owner_id']); _integer(row['ordinal'],1,1000)
                    intent=_json(row['intent']); self._intent(intent)
                    if row['kind']!=intent['kind'] or digest_manifest(intent)!=row['intent_sha256'] or row['status'] not in {'intent','completed','unknown','failed'}: raise ValueError('Invalid effect')
                    if intent['kind']=='pr_create' and intent['marker']!='<!-- task-tower:pipeline:v1 '+row['run_id']+' '+row['effect_id']+' -->':raise ValueError('PR effect identity mismatch')
                    if intent['kind']=='pr_create':
                        host=db.execute('SELECT * FROM runs WHERE run_id=?',(row['run_id'],)).fetchone()
                        if host is None or any(intent[k]!=host[k] for k in ('repository','issue','issue_id','task_id','run_id','base_sha','branch')) or intent['head_sha']!=host['checkpoint_sha']:
                            raise ValueError('PR effect host binding mismatch')
                    if row['observation'] is not None:
                        observation=_json(row['observation']); self._effect_observation(row,intent,observation)
                        if observation.get('status')!=row['status']:raise ValueError('Effect observation status mismatch')
                        if digest_manifest(observation)!=row['observation_sha256']: raise ValueError('Invalid observation digest')
                else:
                    _uuid(row['executor_instance_id']); _uuid(row['reviewer_instance_id']); _sha(row['input_sha256']); body=_json(row['body']); self._receipt_body(body)
                    if row['decision'] not in {'approve','reject','needs_input'} or row['superseded'] not in (0,1) or digest_manifest(body)!=row['receipt_sha256']: raise ValueError('Invalid verdict')
        for row in db.execute('SELECT * FROM events'):
            if row['run_id'] not in runs or row['kind'] not in {'submitted','claimed','transition','attempt_started','attempt_finished','verdict','effect_started','effect_finished','cancel_requested','recovered','handoff','rework_applied'} or row['reason'] not in REASONS: raise ValueError('Invalid pipeline event')
            for key in ('attempt_id','effect_id','receipt_id','old_owner_id','new_owner_id'):
                if row[key] is not None: _uuid(row[key])
            if row['kind']=='handoff' and (row['old_owner_id'] is None or row['new_owner_id'] is None or row['old_owner_id']==row['new_owner_id']): raise ValueError('Invalid owner handoff')
            if row['kind']=='rework_applied':
                if row['target_stage'] not in STAGES: raise ValueError('Invalid rework target')
                _integer(row['generation_floor'],2,1001)
            elif row['target_stage'] is not None or row['generation_floor'] is not None: raise ValueError('Unexpected rework boundary')
            for key in ('old_state','new_state'):
                if row[key] is not None and row[key] not in STATES: raise ValueError('Invalid event state')
        for row in db.execute('SELECT * FROM controller'):
            _uuid(row['owner_id']); _sha(row['policy_sha256']); self._health(_json(row['health']))
            _integer(row['owner_pid'],1,2**63-1)
            for key in ('started_at','last_tick_at'):
                if datetime.datetime.fromisoformat(row[key]).tzinfo is None:raise ValueError('Invalid controller time')
            if row['singleton']!=1: raise ValueError('Invalid controller')
    @staticmethod
    def _event(db,run_id,kind,old=None,new=None,reason=None,**links):
        db.execute('INSERT INTO events(run_id,kind,reason,old_state,new_state,attempt_id,effect_id,receipt_id,old_owner_id,new_owner_id,target_stage,generation_floor,timestamp) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,kind,reason,old,new,links.get('attempt_id'),links.get('effect_id'),links.get('receipt_id'),links.get('old_owner_id'),links.get('new_owner_id'),links.get('target_stage'),links.get('generation_floor'),_now()))
    @staticmethod
    def _receipt(row): return dict(version=1,delivery_id=row['delivery_id'],status='accepted',receipt_id=row['run_id'])
    @staticmethod
    def _run(row):
        result=dict(row)
        for key in ('component_keys','reworks','limits','manifest','admission'):
            if result[key] is not None: result[key]=_json(result[key])
        return result
    def submit(self,request:dict,policy:dict)->dict:
        req=validate_request(request)
        if req['operation']!='submit' or not isinstance(policy,dict) or set(policy)!={'profile_id','profile_fingerprint','policy_sha256','component_keys','limits'}: raise ValueError('Invalid pipeline admission')
        profile_id=policy['profile_id']
        if not isinstance(profile_id,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',profile_id): raise ValueError('Invalid profile ID')
        for key in ('profile_fingerprint','policy_sha256'): _sha(policy[key])
        components=self._components(policy['component_keys']); limits=self._limits(policy['limits'])
        with self._db(True) as db:
            row=db.execute('SELECT * FROM runs WHERE delivery_id=?',(req['delivery_id'],)).fetchone()
            if row is not None:
                if any(row[k]!=req[k] for k in ('repository','issue','task_id','runner_label')) or row['profile_id']!=profile_id or any(row[k]!=policy[k] for k in ('profile_fingerprint','policy_sha256')) or _json(row['component_keys'])!=components or _json(row['limits'])!=limits: raise ValueError('Delivery identity collision')
                return self._receipt(row)
            if db.execute('SELECT 1 FROM runs WHERE repository=? AND issue=?',(req['repository'],req['issue'])).fetchone(): raise ValueError('Issue already admitted')
            run_id=str(uuid.uuid4()); now=_now()
            values=dict(run_id=run_id,delivery_id=req['delivery_id'],repository=req['repository'],issue=req['issue'],issue_id=None,task_id=req['task_id'],runner_label=req['runner_label'],profile_id=profile_id,profile_fingerprint=policy['profile_fingerprint'],policy_sha256=policy['policy_sha256'],criteria_sha256=None,superpowers_sha256=None,source_sha=None,base_sha=None,checkpoint_sha=None,branch='pipeline/'+run_id,worktree=None,git_dir=None,admission=None,state='queued',stage='spec',generation=1,owner_id=None,owner_pid=None,cancel_requested=0,created_at=now,deadline_at=None,updated_at=now,reworks=_dump(dict.fromkeys(STAGES,0)),process_count=0,component_keys=_dump(components),input_sha256=None,manifest=None,reason=None,limits=_dump(limits))
            db.execute('INSERT INTO runs('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()))
            self._validate_db(db); self._event(db,run_id,'submitted',None,'queued')
            return self._receipt(values)
    def lookup(self,delivery_id:str)->dict|None:
        _uuid(delivery_id)
        with self._db() as db:
            row=None if db is None else db.execute('SELECT * FROM runs WHERE delivery_id=?',(delivery_id,)).fetchone()
            return None if row is None else self._receipt(row)
    def status(self,run_id:str|None=None)->dict:
        if run_id is not None: _uuid(run_id)
        with self._db() as db:
            if run_id is not None:
                row=None if db is None else db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
                if row is None: raise ValueError('Pipeline run not found')
                return self._run(row)
            rows=[] if db is None else [self._run(r) for r in db.execute('SELECT * FROM runs ORDER BY repository,issue')]
            return dict(runs=rows,active=sum(r['state'] in ACTIVE for r in rows),queued=sum(r['state']=='queued' for r in rows),unknown=sum(r['state']=='unknown' for r in rows))
    def history(self,run_id):
        _uuid(run_id)
        with self._db() as db:
            if db is None or not db.execute('SELECT 1 FROM runs WHERE run_id=?',(run_id,)).fetchone(): raise ValueError('Pipeline run not found')
            result={}
            for table in ('attempts','verdicts','effects','events'):
                result[table]=[]; order='sequence' if table=='events' else 'ordinal' if table=='effects' else 'rowid'
                for saved in db.execute('SELECT * FROM '+table+' WHERE run_id=? ORDER BY '+order,(run_id,)):
                    row=dict(saved)
                    for key in ('launch_intent','evidence','artifacts','body','intent','observation'):
                        if key in row and row[key] is not None: row[key]=_json(row[key])
                    result[table].append(row)
            return result
    @contextmanager
    def owner(self,owner_id):
        _uuid(owner_id)
        if owner_id in self._owners: raise ValueError('Owner already registered')
        self._owners.add(owner_id)
        try: yield owner_id
        finally: self._owners.remove(owner_id)
    def deny_queued(self,expected:dict)->dict|None:
        """Host denial only: an exact unstarted queue snapshot gains no owner."""
        if not isinstance(expected,dict):raise ValueError('Invalid queued denial')
        _uuid(expected.get('run_id'))
        if not self.path.exists():return None
        with self._db(True) as db:
            saved=db.execute('SELECT * FROM runs WHERE run_id=?',(expected['run_id'],)).fetchone()
            if saved is None:return None
            row=self._run(saved)
            if set(expected)!=set(row):raise ValueError('Invalid queued denial binding')
            if any(type(expected[k]) is not type(row[k]) or expected[k]!=row[k] for k in row):return None
            empty=('owner_id','owner_pid','deadline_at','admission','manifest','input_sha256','worktree','git_dir','source_sha','base_sha','checkpoint_sha','criteria_sha256','superpowers_sha256')
            if row['state']!='queued' or row['process_count'] or row['cancel_requested'] or any(row[k] is not None for k in empty) or any(row['reworks'].values()):return None
            if any(db.execute('SELECT 1 FROM '+table+' WHERE run_id=? LIMIT 1',(row['run_id'],)).fetchone() for table in ('attempts','effects','verdicts')):return None
            now=_now()
            if datetime.datetime.fromisoformat(now)<datetime.datetime.fromisoformat(row['updated_at']):raise ValueError('deadline')
            changed=db.execute("UPDATE runs SET state='needs_input',reason='policy_revoked',updated_at=? WHERE run_id=? AND delivery_id=? AND repository=? AND issue=? AND task_id=? AND state='queued' AND owner_id IS NULL AND owner_pid IS NULL AND process_count=0 AND generation=? AND input_sha256 IS ? AND updated_at=?",(now,row['run_id'],row['delivery_id'],row['repository'],row['issue'],row['task_id'],row['generation'],row['input_sha256'],row['updated_at'])).rowcount
            if changed!=1:raise ValueError('Queued denial changed')
            self._event(db,row['run_id'],'transition','queued','needs_input','policy_revoked')
            self._validate_db(db)
            return self._run(db.execute('SELECT * FROM runs WHERE run_id=?',(row['run_id'],)).fetchone())

    def claim(self,owner_id:str,max_active:int,*,queued_order=None)->dict|None:
        _uuid(owner_id); _integer(max_active,1,2)
        priorities=None
        if queued_order is not None:
            if not isinstance(queued_order,list) or len(queued_order)>10000:raise ValueError('Invalid queued ordering')
            priorities={}
            for item in queued_order:
                if not isinstance(item,dict) or set(item)!={'repository','issue','priority'}:raise ValueError('Invalid queued ordering')
                repository=item['repository'];priority=item['priority']
                if not isinstance(repository,str) or not re.fullmatch(REPOSITORY,repository) or repository!=repository.casefold():raise ValueError('Invalid queued repository')
                issue=_integer(item['issue'],1,2**63-1)
                if not isinstance(priority,str) or priority not in ('P0','P1','P2','P3') or (repository,issue) in priorities:raise ValueError('Invalid queued priority')
                priorities[repository,issue]=int(priority[1])
        with self._db(True) as db:
            active=[self._run(r) for r in db.execute('SELECT * FROM runs') if r['state'] in ACTIVE]
            if owner_id in self._owners:
                for saved in db.execute("SELECT * FROM runs WHERE state='ready' ORDER BY repository,issue"):
                    row=dict(saved)
                    if self._repository_busy(db,row):continue
                    own=row['owner_id']==owner_id and row['owner_pid']==os.getpid()
                    dead=_dead(row['owner_pid'])
                    if not (own or dead) or not self._safe_ready(db,row): continue
                    if own: return self._run(row)
                    now=_now()
                    if datetime.datetime.fromisoformat(now)<datetime.datetime.fromisoformat(row['updated_at']):raise ValueError('deadline')
                    changed=db.execute("UPDATE runs SET owner_id=?,owner_pid=?,updated_at=? WHERE run_id=? AND state='ready' AND owner_id=? AND owner_pid=? AND generation=? AND input_sha256 IS ?",(owner_id,os.getpid(),now,row['run_id'],row['owner_id'],row['owner_pid'],row['generation'],row['input_sha256'])).rowcount
                    if changed!=1: raise ValueError('Ready handoff changed')
                    self._event(db,row['run_id'],'handoff','ready','ready',old_owner_id=row['owner_id'],new_owner_id=owner_id)
                    return self._run(db.execute('SELECT * FROM runs WHERE run_id=?',(row['run_id'],)).fetchone())
            if len(active)>=max_active: return None
            queued=[self._run(saved) for saved in db.execute("SELECT * FROM runs WHERE state='queued' AND cancel_requested=0 ORDER BY repository,issue")]
            if priorities is not None:
                queued=[row for row in queued if (row['repository'],row['issue']) in priorities]
                queued.sort(key=lambda row:(priorities[row['repository'],row['issue']],row['repository'],row['issue']))
            for row in queued:
                if self._repository_busy(db,row):continue
                if any(r['repository']==row['repository'] and ('*' in r['component_keys'] or '*' in row['component_keys'] or set(r['component_keys'])&set(row['component_keys'])) for r in active): continue
                now=_now(); deadline=(datetime.datetime.fromisoformat(now)+datetime.timedelta(seconds=row['limits']['task_timeout_seconds'])).isoformat()
                changed=db.execute("UPDATE runs SET state='preparing',owner_id=?,owner_pid=?,deadline_at=?,updated_at=? WHERE run_id=? AND state='queued' AND owner_id IS NULL AND generation=? AND input_sha256 IS ?",(owner_id,os.getpid() if owner_id in self._owners else None,deadline,now,row['run_id'],row['generation'],row['input_sha256'])).rowcount
                if changed!=1: raise ValueError('Pipeline claim changed')
                self._event(db,row['run_id'],'claimed','queued','preparing')
                return self._run(db.execute('SELECT * FROM runs WHERE run_id=?',(row['run_id'],)).fetchone())
            return None
    @staticmethod
    def _repository_busy(db,row):
        """Global ref checks require serialized actions within one repository.

        A live ready owner may still be freezing a checkpoint or returning its
        result. Only positive death releases that action reservation; its durable
        task/component slot is retained separately.
        """
        for other in db.execute('SELECT run_id,state,owner_pid FROM runs WHERE repository=? AND run_id<>?',(row['repository'],row['run_id'])):
            if other['state'] in ACTIVE-{'ready'} or (other['state']=='ready' and not _dead(other['owner_pid'])):return True
        return False
    @staticmethod
    def _owned(db,run_id,owner_id):
        _uuid(run_id); _uuid(owner_id)
        row=db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
        if row is None or row['owner_id']!=owner_id or row['state']=='unknown': raise ValueError('Pipeline owner/state mismatch')
        return dict(row)
    @staticmethod
    def _unresolved(db,run_id):
        return bool(db.execute("SELECT 1 FROM effects WHERE run_id=? AND status IN ('intent','unknown') UNION ALL SELECT 1 FROM attempts WHERE run_id=? AND state IN ('launch_intent','unknown') LIMIT 1",(run_id,run_id)).fetchone())
    @staticmethod
    def _safe_ready(db,row):
        if row['state']!='ready' or row['manifest'] is None or PipelineJournal._unresolved(db,row['run_id']): return False
        attempts=list(db.execute('SELECT state,evidence FROM attempts WHERE run_id=?',(row['run_id'],)))
        for attempt in attempts:
            if attempt['state'] not in {'completed','failed','needs_input'} or attempt['evidence'] is None or _json(attempt['evidence']).get('cleanup_confirmed') is not True: return False
        effects=list(db.execute('SELECT status FROM effects WHERE run_id=?',(row['run_id'],)))
        if any(effect['status']!='completed' for effect in effects): return False
        return bool(attempts or effects)

    def record(self,run_id:str,owner_id:str,expected:dict,transition:dict)->dict:
        if not isinstance(expected,dict) or set(expected)!={'state','stage','generation','input_sha256'}: raise ValueError('Invalid pipeline CAS')
        allowed={'state','stage','generation','manifest','reason','evidence','admission','issue_id','criteria_sha256','source_sha','base_sha','worktree','git_dir','superpowers_sha256'}
        if not isinstance(transition,dict) or set(transition)-allowed or 'state' not in transition: raise ValueError('Invalid transition')
        state=transition['state']; reason=transition.get('reason')
        if state not in STATES or reason not in REASONS: raise ValueError('Invalid status/reason')
        if 'evidence' in transition: _neutral(transition['evidence'])
        if 'issue_id' in transition: _integer(transition['issue_id'],1,2**63-1)
        for key in ('source_sha','base_sha'):
            if key in transition: _sha(transition[key],40)
        for key in ('criteria_sha256','superpowers_sha256'):
            if key in transition: _sha(transition[key])
        for key in ('worktree','git_dir'):
            if key in transition: self._host_directory(transition[key])
        with self._db(True) as db:
            row=self._owned(db,run_id,owner_id)
            if state in {'preparing','executing','reviewing','checking','publishing','ready'} and self._repository_busy(db,row):raise ValueError('Repository action already owned')
            if any(type(row[k]) is not type(v) or row[k]!=v for k,v in expected.items()): raise ValueError('Stale pipeline CAS')
            edges={'preparing':{'preparing','executing','ready','needs_input','cancelled','timed_out','unknown'},'executing':{'ready','needs_input','cancelled','timed_out','unknown'},'reviewing':{'ready','needs_input','cancelled','timed_out','unknown'},'checking':{'ready','needs_input','cancelled','timed_out','unknown'},'ready':{'executing','reviewing','checking','publishing','ready_for_pr','needs_input','cancelled','timed_out','unknown','ready'},'publishing':{'ready','awaiting_pr','ready_for_pr','needs_input','unknown','cancelled','timed_out'}}
            if state not in edges.get(row['state'],set()): raise ValueError('Illegal state transition')
            if state!='unknown' and self._unresolved(db,run_id): raise ValueError('Unresolved pipeline intent')
            if state in {'needs_input','cancelled','timed_out','ready_for_pr','awaiting_pr'} and transition.get('evidence',{}).get('cleanup_confirmed') is not True: raise ValueError('Release requires positive cleanup')
            stage=transition.get('stage',row['stage']); generation=transition.get('generation',row['generation'])
            if stage not in STAGES: raise ValueError('Invalid transition stage')
            _integer(generation,row['generation'],row['generation']+1)
            values={k:v for k,v in transition.items() if k not in {'evidence','manifest','admission'}}
            if 'manifest' in transition:
                manifest=validate_stage_manifest(transition['manifest'])
                if manifest['run_id']!=run_id or manifest['stage']!=stage or manifest['generation']!=generation: raise ValueError('Manifest transition mismatch')
                if row['manifest'] is not None and _json(row['manifest'])!=manifest and generation!=row['generation']+1: raise ValueError('New input needs new generation')
                for key in ('repository','issue','issue_id','task_id','source_sha','base_sha','policy_sha256','criteria_sha256','superpowers_sha256'):
                    if manifest[key]!=values.get(key,row[key]): raise ValueError('Manifest identity mismatch')
                values.update(manifest=_dump(manifest),input_sha256=digest_manifest(manifest))
            elif stage!=row['stage'] or generation!=row['generation']: raise ValueError('Stage change requires manifest')
            immutable=('issue_id','criteria_sha256','source_sha','base_sha','worktree','git_dir','superpowers_sha256')
            for key in immutable:
                if key in values and row[key] is not None and (type(row[key]) is not type(values[key]) or row[key]!=values[key]): raise ValueError('Immutable pipeline identity')
            if 'admission' in transition:
                admission=self._admission(transition['admission'])
                if row['state']!='preparing' or row['admission'] is not None and _json(row['admission'])!=admission: raise ValueError('Immutable admission')
                for key in ('repository','issue','issue_id','task_id','runner_label','criteria_sha256','policy_sha256','profile_id','profile_fingerprint','source_sha','base_sha'):
                    if admission[key]!=values.get(key,row[key]): raise ValueError('Admission does not bind run')
                values['admission']=_dump(admission)
            if row['cancel_requested'] and state in {'executing','reviewing','checking','publishing'}: raise ValueError('Cancelled before action')
            if state in {'executing','reviewing','checking','publishing'} and (values.get('manifest',row['manifest']) is None or values.get('admission',row['admission']) is None): raise ValueError('Action requires manifest and admission')
            rework=self._rework_transition(db,row,state,transition)
            self._history_gate(db,row,state,transition,rework=rework)
            if reason=='stale_input':
                if transition.get('evidence',{}).get('cleanup_confirmed') is not True or 'manifest' not in transition or generation!=row['generation']+1:
                    raise ValueError('Stale rework requires frozen input and cleanup')
                reworks=_json(row['reworks']); reworks[stage]+=1
                affected=STAGES[STAGES.index(stage):]
                db.execute('UPDATE verdicts SET superseded=1 WHERE run_id=? AND stage IN ('+','.join('?' for _ in affected)+')',(run_id,*affected))
                values['reworks']=_dump(reworks)
                self._event(db,run_id,'rework_applied',row['state'],state,'stale_input',target_stage=stage,generation_floor=generation)
                if reworks[stage]>_json(row['limits'])['max_reworks']:
                    values['state']='needs_input'; values['reason']='rework_limit'
            values['updated_at']=_now()
            db.execute('UPDATE runs SET '+','.join(k+'=?' for k in values)+' WHERE run_id=? AND owner_id=?',(*values.values(),run_id,owner_id))
            self._validate_db(db); self._event(db,run_id,'transition',row['state'],state,reason)
            return self._run(db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone())
    @staticmethod
    def _history_gate(db,row,state,transition,*,rework=False):
        def finished(role):
            attempt=db.execute("SELECT * FROM attempts WHERE run_id=? AND generation<=? AND role=? ORDER BY rowid DESC LIMIT 1",(row['run_id'],row['generation'],role)).fetchone()
            if attempt is None or attempt['state']!='completed': return False
            try: PipelineJournal._contribution_floor(db,row,attempt)
            except ValueError: return False
            return True
        def accepted(stage):
            return db.execute("SELECT 1 FROM verdicts WHERE run_id=? AND stage=? AND decision='approve' AND superseded=0",(row['run_id'],stage)).fetchone() is not None
        stage=transition.get('stage',row['stage'])
        if state=='ready' and row['state']=='executing' and not rework and not finished(row['stage']+'_executor'): raise ValueError('Executor completion proof missing')
        if state=='ready' and row['state']=='reviewing' and transition.get('reason')!='stale_input' and not db.execute('SELECT 1 FROM verdicts WHERE run_id=? AND stage=? AND generation=?',(row['run_id'],row['stage'],row['generation'])).fetchone(): raise ValueError('Reviewer receipt missing')
        if state=='ready' and row['state']=='preparing':
            binding=transition.get('manifest')
            checkpoint=None if binding is None else binding['checkpoint_sha']
            completed_commit=any(_json(e['observation']).get('commit_sha')==checkpoint==row['checkpoint_sha'] for e in db.execute("SELECT observation FROM effects WHERE run_id=? AND kind='commit' AND status='completed'",(row['run_id'],)))
            if not completed_commit and not PipelineJournal._initial_ready(db,row,transition): raise ValueError('Checkpoint completion proof missing')
        if state=='reviewing' and not finished(stage+'_executor'): raise ValueError('Reviewer needs completed executor')
        if state=='executing' and row['state']=='ready':
            executor=db.execute('SELECT * FROM attempts WHERE run_id=? AND role=? ORDER BY rowid DESC LIMIT 1',(row['run_id'],stage+'_executor')).fetchone()
            if executor is not None:
                try: PipelineJournal._contribution_floor(db,row,executor)
                except ValueError: pass  # a recorded return/reset requires new work
                else: raise ValueError('Completed stage action cannot replay')
        if state=='executing':
            for prior in STAGES[:STAGES.index(stage)]:
                if not accepted(prior): raise ValueError('Prior accepted stage missing')
        if state=='checking' and (stage!='test' or not finished('test_executor') or not all(accepted(s) for s in ('spec','development'))): raise ValueError('Host checks prerequisites missing')
        if state=='ready' and row['state']=='checking' and not rework:
            checks=list(db.execute("SELECT state,evidence FROM attempts WHERE run_id=? AND role='host_check' AND generation=?",(row['run_id'],row['generation'])))
            if not checks or any(c['state']!='completed' or _json(c['evidence']).get('source_unchanged') is not True for c in checks): raise ValueError('Completed unchanged host checks missing')
        if state=='ready' and row['state']=='checking' and not rework and not (transition.get('evidence',{}).get('cleanup_confirmed') is True and transition.get('evidence',{}).get('checks_sha256')): raise ValueError('Host checks proof missing')
        if state=='ready' and row['state']=='publishing':
            effect=db.execute('SELECT * FROM effects WHERE run_id=? ORDER BY ordinal DESC LIMIT 1',(row['run_id'],)).fetchone()
            if effect is None or effect['status']!='completed' or effect['owner_id']!=row['owner_id'] or transition.get('evidence',{}).get('publication_effect_id')!=effect['effect_id'] or transition.get('evidence',{}).get('cleanup_confirmed') is not True:raise ValueError('Publication action completion missing')
            intent=_json(effect['intent'])
            if effect['kind']!='push' and not (effect['kind']=='commit' and intent.get('evidence_manifest_sha256') and intent.get('contributing_executor_attempt_id') is None):raise ValueError('Publication action proof missing')
        if (state in {'publishing','ready_for_pr','awaiting_pr'} or state=='ready' and row['state']=='publishing') and not all(accepted(s) for s in STAGES): raise ValueError('Publication requires three accepted stages')
        if state in {'publishing','ready_for_pr','awaiting_pr'} or state=='ready' and row['state']=='publishing':
            verdict=db.execute("SELECT input_sha256,generation FROM verdicts WHERE run_id=? AND stage='test' AND decision='approve' AND superseded=0 ORDER BY rowid DESC LIMIT 1",(row['run_id'],)).fetchone()
            if row['stage']!='test' or verdict is None or verdict['input_sha256']!=row['input_sha256'] or verdict['generation']!=row['generation']: raise ValueError('Current test acceptance missing')
        if state=='awaiting_pr' and not db.execute("SELECT 1 FROM effects WHERE run_id=? AND kind='pr_create' AND status='completed'",(row['run_id'],)).fetchone(): raise ValueError('PR observation missing')

    def begin_attempt(self,run_id:str,owner_id:str,binding:dict)->dict:
        if not isinstance(binding,dict): raise ValueError('Invalid attempt binding')
        host_check=binding.get('role')=='host_check'
        keys={'role','manifest','artifact_names'}|({'check_id','check_sha256'} if host_check else set())
        if set(binding)!=keys or binding['role'] not in ROLES|{'host_check'}: raise ValueError('Invalid attempt binding')
        if host_check:
            if not isinstance(binding['check_id'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',binding['check_id']): raise ValueError('Invalid check ID')
            _sha(binding['check_sha256'])
        manifest=validate_stage_manifest(binding['manifest']); self._artifacts(binding['artifact_names'])
        with self._db(True) as db:
            row=self._owned(db,run_id,owner_id); role=binding['role']; digest=digest_manifest(manifest)
            if self._repository_busy(db,row):raise ValueError('Repository action already owned')
            if row['state'] not in ({'checking'} if host_check else {'executing','reviewing'}) or row['cancel_requested'] or manifest['run_id']!=run_id or manifest['stage']!=row['stage'] or (row['stage']!='test' if host_check else role!=row['stage']+('_reviewer' if row['state']=='reviewing' else '_executor')) or row['input_sha256']!=digest or _json(row['manifest'])!=manifest: raise ValueError('Attempt is not current action')
            if self._unresolved(db,run_id): raise ValueError('Unresolved attempt/effect')
            if db.execute('SELECT 1 FROM attempts WHERE run_id=? AND generation=? AND role=? AND check_id IS ?',(run_id,row['generation'],role,binding.get('check_id'))).fetchone(): raise ValueError('Attempt already launched')
            if row['process_count']>=_json(row['limits'])['max_processes']: raise ValueError('process_limit')
            if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(row['deadline_at']): raise ValueError('deadline')
            attempt_id=str(uuid.uuid4()); instance_id=str(uuid.uuid4()); now=_now()
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(attempt_id,run_id,row['generation'],row['stage'],role,instance_id,owner_id,digest,binding.get('check_id'),binding.get('check_sha256'),'launch_intent',_dump(manifest),None,None,_dump(binding['artifact_names']),now,None))
            db.execute('UPDATE runs SET process_count=process_count+1,updated_at=? WHERE run_id=?',(now,run_id))
            self._event(db,run_id,'attempt_started',row['state'],row['state'],attempt_id=attempt_id)
            return dict(attempt_id=attempt_id,instance_id=instance_id,run_id=run_id,role=role,stage=row['stage'],generation=row['generation'],source_sha=manifest['source_sha'],checkpoint_sha=manifest['checkpoint_sha'],input_sha256=digest,manifest=manifest,state='launch_intent',artifact_names=dict(binding['artifact_names']),**({'check_id':binding['check_id'],'check_sha256':binding['check_sha256']} if host_check else {}))
    def finish_attempt(self,attempt_id:str,owner_id:str,evidence:dict)->dict:
        _uuid(attempt_id); _uuid(owner_id); _neutral(evidence)
        required={'status','started','cleanup_confirmed','exit_code','result_sha256'}
        if not required<=set(evidence) or evidence['status'] not in {'completed','failed','needs_input','unknown'}: raise ValueError('Invalid attempt outcome')
        _sha(evidence['result_sha256'],nullable=True)
        if type(evidence['started']) is not bool or type(evidence['cleanup_confirmed']) is not bool or evidence['exit_code'] is not None and type(evidence['exit_code']) is not int: raise ValueError('Invalid process proof')
        with self._db(True) as db:
            attempt=db.execute('SELECT * FROM attempts WHERE attempt_id=?',(attempt_id,)).fetchone()
            if attempt is None or attempt['owner_id']!=owner_id or attempt['state']!='launch_intent': raise ValueError('Attempt already finished or foreign')
            row=self._owned(db,attempt['run_id'],owner_id); status=evidence['status']
            if attempt['role']=='host_check':
                if evidence.get('check_id')!=attempt['check_id'] or evidence.get('check_sha256')!=attempt['check_sha256'] or type(evidence.get('source_unchanged')) is not bool: raise ValueError('Host check proof mismatch')
                if status=='completed' and evidence['source_unchanged'] is not True: raise ValueError('Host check changed source')
            if not evidence['cleanup_confirmed'] or status=='unknown': status='unknown'
            if status=='completed' and (evidence['started'] is not True or evidence['exit_code']!=0 or evidence['result_sha256'] is None): raise ValueError('Completion requires process/result proof')
            db.execute('UPDATE attempts SET state=?,evidence=?,result_sha256=?,finished_at=? WHERE attempt_id=?',(status,_dump(evidence),evidence['result_sha256'],_now(),attempt_id))
            if status=='unknown': db.execute("UPDATE runs SET state='unknown',reason='cleanup_unknown',updated_at=? WHERE run_id=?",(_now(),row['run_id']))
            self._event(db,row['run_id'],'attempt_finished',row['state'],'unknown' if status=='unknown' else row['state'],attempt_id=attempt_id)
            return dict(attempt_id=attempt_id,state=status,evidence=dict(evidence))
    @staticmethod
    def _receipt_body(body):
        required={'manifest','input_sha256','stage','generation','executor_instance_id','reviewer_instance_id','reviewer_attempt_id','superpowers_sha256','policy_sha256','result_sha256','process','decision','return_stage'}
        if not isinstance(body,dict) or set(body)!=required: raise ValueError('Invalid receipt body')
        manifest=validate_stage_manifest(body['manifest'])
        if digest_manifest(manifest)!=body['input_sha256'] or body['stage']!=manifest['stage'] or body['generation']!=manifest['generation'] or body['policy_sha256']!=manifest['policy_sha256'] or body['superpowers_sha256']!=manifest['superpowers_sha256']: raise ValueError('Receipt manifest mismatch')
        for key in ('executor_instance_id','reviewer_instance_id','reviewer_attempt_id'): _uuid(body[key])
        _sha(body['result_sha256']); _neutral(body['process'])
        if body['decision'] not in {'approve','reject','needs_input'}: raise ValueError('Invalid decision')
        if body['decision']=='reject':
            if body['return_stage'] not in STAGES or STAGES.index(body['return_stage'])>STAGES.index(body['stage']): raise ValueError('Invalid return stage')
        elif body['return_stage'] is not None: raise ValueError('Unexpected return stage')
    def save_verdict(self,run_id:str,owner_id:str,receipt:dict)->dict:
        # The controller must freshly revalidate external policy/criteria/main and
        # checkpoint content immediately before this local attestation boundary.
        self._receipt_body(receipt)
        with self._db(True) as db:
            row=self._owned(db,run_id,owner_id)
            stale=(row['state']!='reviewing' or row['input_sha256']!=receipt['input_sha256'] or row['manifest'] is None or _json(row['manifest'])!=receipt['manifest'])
            attempt=db.execute('SELECT * FROM attempts WHERE attempt_id=?',(receipt['reviewer_attempt_id'],)).fetchone()
            if attempt is None or attempt['run_id']!=run_id or attempt['owner_id']!=owner_id or attempt['state']!='completed' or attempt['role']!=receipt['stage']+'_reviewer' or attempt['instance_id']!=receipt['reviewer_instance_id'] or attempt['input_sha256']!=receipt['input_sha256'] or attempt['result_sha256']!=receipt['result_sha256'] or _json(attempt['evidence'])!=receipt['process']: raise ValueError('Missing host reviewer proof')
            executor=db.execute("SELECT * FROM attempts WHERE run_id=? AND instance_id=? AND role=? AND state='completed'",(run_id,receipt['executor_instance_id'],receipt['stage']+'_executor')).fetchone()
            if executor is None or executor['generation']>receipt['generation']: raise ValueError('Missing host executor proof')
            checkpoint_effect=None
            for saved in db.execute("SELECT * FROM effects WHERE run_id=? AND kind='commit' AND status='completed' ORDER BY ordinal DESC",(run_id,)):
                if _json(saved['observation']).get('commit_sha')==receipt['manifest']['checkpoint_sha']:
                    checkpoint_effect=dict(saved); break
            if checkpoint_effect is None or _json(checkpoint_effect['intent'])['contributing_executor_attempt_id']!=executor['attempt_id']:
                raise ValueError('Receipt checkpoint contribution missing')
            latest=db.execute('SELECT attempt_id FROM attempts WHERE run_id=? AND role=? AND generation<=? ORDER BY rowid DESC LIMIT 1',(run_id,receipt['stage']+'_executor',receipt['generation'])).fetchone()
            if latest is None or latest['attempt_id']!=executor['attempt_id']: raise ValueError('Superseded executor contribution')
            if not stale: self._contribution_floor(db,row,executor)
            if receipt['reviewer_instance_id']==receipt['executor_instance_id'] or db.execute('SELECT 1 FROM verdicts WHERE reviewer_instance_id=?',(receipt['reviewer_instance_id'],)).fetchone(): raise ValueError('Reviewer is not fresh')
            if db.execute('SELECT 1 FROM verdicts WHERE run_id=? AND stage=? AND generation=? AND superseded=0',(run_id,receipt['stage'],receipt['generation'])).fetchone(): raise ValueError('Verdict already recorded')
            receipt_id=str(uuid.uuid4()); digest=digest_manifest(receipt)
            db.execute('INSERT INTO verdicts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(receipt_id,run_id,receipt['stage'],receipt['generation'],receipt['input_sha256'],receipt['executor_instance_id'],receipt['reviewer_instance_id'],receipt['decision'],receipt['return_stage'],digest,_dump(receipt),int(stale)))
            if receipt['decision']=='reject' and not stale:
                target=receipt['return_stage']; reworks=_json(row['reworks']); reworks[target]+=1; affected=STAGES[STAGES.index(target):]
                db.execute('UPDATE verdicts SET superseded=1 WHERE run_id=? AND stage IN ('+','.join('?' for _ in affected)+')',(run_id,*affected))
                db.execute('UPDATE runs SET reworks=? WHERE run_id=?',(_dump(reworks),run_id))
                self._event(db,run_id,'rework_applied',row['state'],row['state'],'criteria_unmet',receipt_id=receipt_id,target_stage=target,generation_floor=row['generation']+1)
                if reworks[target]>_json(row['limits'])['max_reworks']: db.execute("UPDATE runs SET state='needs_input',reason='rework_limit' WHERE run_id=?",(run_id,))
            self._event(db,run_id,'verdict',row['state'],row['state'],'stale_input' if stale else None,receipt_id=receipt_id)
            return dict(receipt_id=receipt_id,receipt_sha256=digest,body=receipt,superseded=stale)
    @staticmethod
    def _contribution_floor(db,row,executor):
        # A return/reset forbids recycling any earlier executor as new work.
        for applied in db.execute("SELECT target_stage,generation_floor FROM events WHERE run_id=? AND kind='rework_applied'",(row['run_id'],)):
            if STAGES.index(applied['target_stage'])<=STAGES.index(executor['stage']) and executor['generation']<applied['generation_floor']:
                raise ValueError('Executor precedes applied rework')

    @staticmethod
    def _initial_ready(db,row,transition):
        manifest=transition.get('manifest')
        if (row['stage']!='spec' or row['generation']!=1 or row['admission'] is None
                or row['worktree'] is None or row['git_dir'] is None
                or transition.get('stage','spec')!='spec' or transition.get('generation',1)!=1
                or manifest is None or manifest['checkpoint_sha']!=row['source_sha']
                or manifest['source_sha']!=row['source_sha'] or manifest['base_sha']!=row['base_sha']
                or manifest['prior_verdict_sha256'] is not None or manifest['checks_sha256'] is not None
                or db.execute('SELECT 1 FROM attempts WHERE run_id=?',(row['run_id'],)).fetchone()
                or db.execute('SELECT 1 FROM verdicts WHERE run_id=?',(row['run_id'],)).fetchone()
                or PipelineJournal._unresolved(db,row['run_id'])):
            return False
        for effect in db.execute("SELECT * FROM effects WHERE run_id=? AND kind='worktree_create' AND status='completed' ORDER BY ordinal DESC",(row['run_id'],)):
            intent=_json(effect['intent']); observation=_json(effect['observation'])
            if (effect['owner_id']==row['owner_id'] and observation.get('source_sha')==row['source_sha']
                    and all(intent[key]==row[key] for key in ('source_sha','branch','worktree','git_dir'))): return True
        return False

    @staticmethod
    def _failed_mutation(db,row,attempt_id):
        _uuid(attempt_id)
        roles={'executing':row['stage']+'_executor','reviewing':row['stage']+'_reviewer','checking':'host_check'}
        attempt=db.execute('SELECT * FROM attempts WHERE attempt_id=?',(attempt_id,)).fetchone()
        if (row['state'] not in roles or attempt is None or attempt['run_id']!=row['run_id']
                or attempt['owner_id']!=row['owner_id'] or attempt['role']!=roles[row['state']]
                or attempt['stage']!=row['stage'] or attempt['generation']!=row['generation']
                or attempt['input_sha256']!=row['input_sha256'] or attempt['state']!='failed'
                or attempt['evidence'] is None):
            raise ValueError('Rework requires current failed mutation proof')
        evidence=_json(attempt['evidence'])
        if evidence.get('cleanup_confirmed') is not True or evidence.get('source_unchanged') is not False or evidence.get('started') is not True:
            raise ValueError('Rework requires positively cleaned actual mutation')
        return dict(attempt)

    def _rework_proof(self,run_id,owner_id,attempt_id):
        with self._db() as db:
            if db is None: raise ValueError('Pipeline run not found')
            row=self._owned(db,run_id,owner_id)
            if self._unresolved(db,run_id): raise ValueError('Unresolved pipeline intent')
            return self._failed_mutation(db,row,attempt_id)

    @staticmethod
    def _rework_transition(db,row,state,transition):
        if state!='ready' or row['state'] not in {'executing','checking','reviewing'}: return False
        failed=db.execute("SELECT * FROM attempts WHERE run_id=? AND owner_id=? AND input_sha256=? AND generation=? AND state='failed' ORDER BY rowid DESC LIMIT 1",(row['run_id'],row['owner_id'],row['input_sha256'],row['generation'])).fetchone()
        if failed is None: return False
        PipelineJournal._failed_mutation(db,row,failed['attempt_id'])
        manifest=transition.get('manifest')
        target='development' if row['stage']=='test' else row['stage']
        if (transition.get('reason')!='stale_input' or transition.get('evidence',{}).get('cleanup_confirmed') is not True
                or transition.get('stage',row['stage'])!=target or transition.get('generation')!=row['generation']+1
                or manifest is None or manifest['checkpoint_sha']!=row['checkpoint_sha'] or manifest['checks_sha256'] is not None):
            raise ValueError('Failed mutation requires frozen bounded rework')
        effect=db.execute("SELECT * FROM effects WHERE run_id=? AND kind='rework_commit' AND status='completed' ORDER BY ordinal DESC LIMIT 1",(row['run_id'],)).fetchone()
        if (effect is None or effect['owner_id']!=row['owner_id'] or _json(effect['intent'])['failed_attempt_id']!=failed['attempt_id']
                or _json(effect['observation']).get('commit_sha')!=manifest['checkpoint_sha']):
            raise ValueError('Completed linked rework checkpoint missing')
        return True

    @staticmethod
    def _intent(intent):
        if not isinstance(intent,dict) or len(canonical_json(intent))>65536: raise ValueError('Invalid effect intent')
        schemas={'commit':{'kind','parent','tree','message','branch','contributing_executor_attempt_id','evidence_manifest_sha256'},'worktree_create':{'kind','source_sha','branch','worktree','git_dir'},'push':{'kind','repository','head_sha','base_sha','remote','branch'},'pr_create':{'kind','repository','issue','issue_id','task_id','run_id','head_sha','base_sha','branch','title_sha256','body_sha256','marker','publisher_account'}}
        schemas['rework_commit']=schemas['commit']|{'failed_attempt_id'}
        kind=intent.get('kind')
        if kind not in schemas or set(intent)!=schemas[kind]: raise ValueError('Invalid effect schema')
        if kind=='worktree_create':
            for key in ('worktree','git_dir'): PipelineJournal._host_directory(intent[key])
        if kind in {'commit','rework_commit'}:
            _sha(intent['parent'],40); _sha(intent['tree'],40)
            if intent['contributing_executor_attempt_id'] is not None: _uuid(intent['contributing_executor_attempt_id'])
            if kind=='rework_commit':
                _uuid(intent['failed_attempt_id'])
                if intent['contributing_executor_attempt_id'] is not None or intent['evidence_manifest_sha256'] is not None: raise ValueError('Rework is not accepted contribution/publication')
            if intent['message']!='Task Tower checkpoint' and not re.fullmatch(r'Task Tower (checkpoint|publication) [0-9a-f-]{36}',intent['message']): raise ValueError('Non-host commit message')
        for key,value in intent.items():
            if key.endswith('_sha'): _sha(value,40)
            if key.endswith('_sha256'): _sha(value,nullable=key=='evidence_manifest_sha256')
            if isinstance(value,str) and ('\0' in value or len(value.encode())>4096): raise ValueError('Invalid effect field')
        if 'branch' in intent:
            if not isinstance(intent['branch'],str) or not intent['branch'].startswith('pipeline/'): raise ValueError('Invalid effect branch')
            _uuid(intent['branch'][9:])
        if kind=='pr_create':
            from .pipeline_publish import _body
            _uuid(intent['run_id'])
            _integer(intent['issue'],1,2**63-1);_integer(intent['issue_id'],1,2**63-1)
            if not isinstance(intent['repository'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9_][a-z0-9_.-]*',intent['repository']):raise ValueError('Invalid PR repository')
            if not isinstance(intent['task_id'],str) or not re.fullmatch(r'TT-[A-Z0-9-]+',intent['task_id']):raise ValueError('Invalid PR task')
            if not isinstance(intent['publisher_account'],str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?',intent['publisher_account']) or '--' in intent['publisher_account']:raise ValueError('Invalid PR publisher')
            marker=re.fullmatch(r'<!-- task-tower:pipeline:v1 ([0-9a-f-]{36}) ([0-9a-f-]{36}) -->',intent['marker'])
            if marker is None or marker[1]!=intent['run_id']:raise ValueError('Invalid PR marker')
            _uuid(marker[2])
            if intent['title_sha256']!=hashlib.sha256(('Task Tower '+intent['task_id']).encode()).hexdigest() or intent['body_sha256']!=hashlib.sha256(_body(intent,intent['marker']).encode()).hexdigest():raise ValueError('Noncanonical PR payload')
        return intent
    def begin_pr_effect(self,run_id:str,owner_id:str,publisher_account:str)->dict:
        """Mint a host PR effect identity before hashing its fixed public body."""
        from .pipeline_publish import _body
        effect_id=str(uuid.uuid4()); run=self.status(run_id)
        marker='<!-- task-tower:pipeline:v1 '+run_id+' '+effect_id+' -->';title='Task Tower '+run['task_id']
        intent=dict(kind='pr_create',repository=run['repository'],issue=run['issue'],issue_id=run['issue_id'],task_id=run['task_id'],run_id=run_id,head_sha=run['checkpoint_sha'],base_sha=run['base_sha'],branch=run['branch'],title_sha256=hashlib.sha256(title.encode()).hexdigest(),body_sha256=hashlib.sha256(_body(run,marker).encode()).hexdigest(),marker=marker,publisher_account=publisher_account)
        return self._begin_effect(run_id,owner_id,intent,_effect_id=effect_id)

    def begin_effect(self,run_id:str,owner_id:str,intent:dict)->dict:
        if intent.get('kind')=='pr_create':raise ValueError('Use host PR identity mint')
        return self._begin_effect(run_id,owner_id,intent)

    def _begin_effect(self,run_id:str,owner_id:str,intent:dict,*,_effect_id=None)->dict:
        self._intent(intent)
        with self._db(True) as db:
            row=self._owned(db,run_id,owner_id)
            allowed_states={'executing','checking','reviewing'} if intent['kind']=='rework_commit' else {'preparing','executing','ready','publishing'}
            if self._repository_busy(db,row):raise ValueError('Repository action already owned')
            if row['state'] not in allowed_states or row['cancel_requested'] or self._unresolved(db,run_id): raise ValueError('Effect cannot start')
            if intent.get('branch')!=row['branch']: raise ValueError('Foreign effect branch')
            if intent['kind'] in {'push','pr_create'}:
                if row['state']!='publishing': raise ValueError('Publication effect requires publication state')
                self._history_gate(db,row,'publishing',{})
                if intent['repository']!=row['repository'] or intent['head_sha']!=row['checkpoint_sha'] or intent['base_sha']!=row['base_sha']: raise ValueError('Publication identity mismatch')
                if intent['kind']=='push' and intent['remote']!='origin': raise ValueError('Invalid publication remote')
                if intent['kind']=='pr_create' and any(intent[k]!=row[k] for k in ('run_id','issue','issue_id','task_id')): raise ValueError('PR identity mismatch')
            if intent['kind']=='worktree_create':
                if row['state']!='preparing' or any(intent[k]!=row[k] for k in ('source_sha','worktree','git_dir')): raise ValueError('Worktree effect binding mismatch')
            if intent['kind']=='commit' and row['state']=='publishing' and intent['evidence_manifest_sha256'] is None:
                raise ValueError('Publication requires host evidence manifest')
            if intent['kind']=='commit' and intent['evidence_manifest_sha256'] is not None:
                if row['state']!='publishing': raise ValueError('Evidence commit requires publication')
                if intent['contributing_executor_attempt_id'] is not None: raise ValueError('Evidence is not executor contribution')
                self._history_gate(db,row,'publishing',{})
            if intent['kind']=='rework_commit':
                self._failed_mutation(db,row,intent['failed_attempt_id'])
                for prior in db.execute("SELECT intent FROM effects WHERE run_id=? AND kind='rework_commit'",(run_id,)):
                    if _json(prior['intent'])['failed_attempt_id']==intent['failed_attempt_id']: raise ValueError('Rework checkpoint already recorded')
            if intent['kind'] in {'commit','rework_commit'} and intent['parent']!=(row['checkpoint_sha'] or row['source_sha']): raise ValueError('Unexpected commit parent')
            if intent['kind']=='commit' and row['state']=='executing' and intent['contributing_executor_attempt_id'] is None:
                raise ValueError('Executor checkpoint requires successful contribution')
            if intent['kind']=='commit' and intent['contributing_executor_attempt_id'] is not None:
                contributor=db.execute("SELECT * FROM attempts WHERE run_id=? AND role=? ORDER BY rowid DESC LIMIT 1",(run_id,row['stage']+'_executor')).fetchone()
                if contributor is None or contributor['attempt_id']!=intent['contributing_executor_attempt_id'] or contributor['state']!='completed': raise ValueError('Checkpoint contributor is not latest completed executor')
                self._contribution_floor(db,row,contributor)
            effect_id=str(uuid.uuid4()) if _effect_id is None else _effect_id
            _uuid(effect_id)
            if _effect_id is not None and intent['kind']!='pr_create':raise ValueError('Reserved PR identity')
            if intent['kind']=='pr_create' and intent['marker']!='<!-- task-tower:pipeline:v1 '+run_id+' '+effect_id+' -->':raise ValueError('PR effect marker mismatch')
            ordinal=db.execute('SELECT coalesce(max(ordinal),0)+1 FROM effects WHERE run_id=?',(run_id,)).fetchone()[0]; digest=digest_manifest(intent)
            db.execute('INSERT INTO effects VALUES(?,?,?,?,?,?,?,?,?,?)',(effect_id,run_id,ordinal,intent['kind'],owner_id,digest,_dump(intent),'intent',None,None))
            self._event(db,run_id,'effect_started',row['state'],row['state'],effect_id=effect_id)
            return dict(effect_id=effect_id,ordinal=ordinal,intent_sha256=digest,intent=dict(intent),status='intent')
    @staticmethod
    def _effect_observation(effect,intent,observation):
        """Only the typed host PR observation may carry a public URL."""
        if intent['kind']!='pr_create' or observation.get('status')!='completed':
            _neutral(observation);return
        fields={'status','repository','issue','issue_id','task_id','run_id','head_sha','base_sha','branch','number','url','author','marker'}
        if set(observation)!=fields:raise ValueError('Invalid PR observation schema')
        for key in ('repository','issue','issue_id','task_id','run_id','head_sha','base_sha','branch','marker'):
            if type(observation[key]) is not type(intent[key]) or observation[key]!=intent[key]:raise ValueError('PR observation binding mismatch')
        _integer(observation['number'],1,2**63-1)
        if observation['url']!='https://github.com/'+intent['repository']+'/pull/'+str(observation['number']):raise ValueError('Invalid PR URL')
        if observation['author']!=intent['publisher_account']:raise ValueError('PR author mismatch')
        if observation['marker']!='<!-- task-tower:pipeline:v1 '+intent['run_id']+' '+effect['effect_id']+' -->':raise ValueError('PR host effect mismatch')

    def finish_effect(self,effect_id:str,owner_id:str,observation:dict)->dict:
        _uuid(effect_id); _uuid(owner_id)
        if observation.get('status') not in {'completed','failed','unknown'}: raise ValueError('Invalid effect observation')
        with self._db(True) as db:
            effect=db.execute('SELECT * FROM effects WHERE effect_id=?',(effect_id,)).fetchone()
            if effect is None or effect['owner_id']!=owner_id or effect['status']!='intent': raise ValueError('Effect already observed or foreign')
            self._effect_observation(effect,_json(effect['intent']),observation)
            row=self._owned(db,effect['run_id'],owner_id); status=observation['status']
            if effect['kind']=='rework_commit': self._failed_mutation(db,row,_json(effect['intent'])['failed_attempt_id'])
            if effect['kind'] in {'commit','rework_commit'} and status=='completed':
                _sha(observation.get('commit_sha'),40); _sha(observation.get('tree_sha'),40)
                if observation['tree_sha']!=_json(effect['intent'])['tree']: raise ValueError('Wrong checkpoint tree')
                db.execute('UPDATE runs SET checkpoint_sha=? WHERE run_id=?',(observation['commit_sha'],row['run_id']))
            db.execute('UPDATE effects SET status=?,observation_sha256=?,observation=? WHERE effect_id=?',(status,digest_manifest(observation),_dump(observation),effect_id))
            if status=='unknown': db.execute("UPDATE runs SET state='unknown',reason='effect_unknown',updated_at=? WHERE run_id=?",(_now(),row['run_id']))
            self._event(db,row['run_id'],'effect_finished',row['state'],'unknown' if status=='unknown' else row['state'],effect_id=effect_id)
            return dict(effect_id=effect_id,status=status,observation_sha256=digest_manifest(observation),observation=dict(observation))
    def cancel(self,run_id:str)->None:
        _uuid(run_id)
        with self._db(True) as db:
            row=db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if row is None: raise ValueError('Pipeline run not found')
            state='cancelled' if row['state']=='queued' else row['state']
            db.execute('UPDATE runs SET cancel_requested=1,state=?,updated_at=? WHERE run_id=?',(state,_now(),run_id))
            self._event(db,run_id,'cancel_requested',row['state'],state,'cancelled')
            self._cancel_clean_ready(db,db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone())
    @staticmethod
    def _cancel_clean_ready(db,row):
        # No caller cleanup flag can release this reservation. Every process and
        # effect must already have positive durable evidence, and its owner must
        # be positively dead; live/null/reused/unknown ownership stays fenced.
        if row['state']!='ready' or not row['cancel_requested'] or not _dead(row['owner_pid']) or not PipelineJournal._safe_ready(db,row):return False
        db.execute("UPDATE runs SET state='cancelled',reason='cancelled',updated_at=? WHERE run_id=?",(_now(),row['run_id']))
        PipelineJournal._event(db,row['run_id'],'transition','ready','cancelled','cancelled')
        return True
    @staticmethod
    def _health(value):
        if not isinstance(value,dict) or set(value)!={'ticks','read_failures','workers','dispatcher','stopped'} or type(value['stopped']) is not bool:
            raise ValueError('Invalid controller health')
        for key,limit in (('ticks',2**63-1),('read_failures',2**63-1),('workers',2),('dispatcher',1)):
            _integer(value[key],0,limit)
        return value
    def claim_controller(self,owner_id,policy_sha256):
        """One installation-local host owner; only positively dead owners yield."""
        _uuid(owner_id);_sha(policy_sha256)
        with self._db(True) as db:
            saved=db.execute('SELECT * FROM controller WHERE singleton=1').fetchone()
            if saved is not None and not _json(saved['health'])['stopped'] and not _dead(saved['owner_pid']):
                raise ValueError('Pipeline controller already owned')
            now=_now();health=dict(ticks=0,read_failures=0,workers=0,dispatcher=0,stopped=False)
            db.execute('INSERT OR REPLACE INTO controller VALUES(1,?,?,?,?,?,?)',
                       (owner_id,os.getpid(),now,now,policy_sha256,_dump(health)))
        return self.controller_health()
    def controller_tick(self,owner_id,health):
        _uuid(owner_id)
        if not isinstance(health,dict) or 'stopped' in health:raise ValueError('Invalid controller health')
        health=self._health(dict(health,stopped=False))
        with self._db(True) as db:
            row=db.execute('SELECT health FROM controller WHERE singleton=1 AND owner_id=? AND owner_pid=?',(owner_id,os.getpid())).fetchone()
            if row is None or _json(row['health'])['stopped']:raise ValueError('Foreign or stopped pipeline controller')
            changed=db.execute('UPDATE controller SET last_tick_at=?,health=? WHERE singleton=1 AND owner_id=? AND owner_pid=?',
                               (_now(),_dump(health),owner_id,os.getpid())).rowcount
            if changed!=1:raise ValueError('Foreign pipeline controller')
    def release_controller(self,owner_id):
        _uuid(owner_id)
        with self._db(True) as db:
            row=db.execute('SELECT * FROM controller WHERE singleton=1 AND owner_id=? AND owner_pid=?',(owner_id,os.getpid())).fetchone()
            if row is None:raise ValueError('Foreign pipeline controller')
            health=_json(row['health']);health.update(stopped=True)
            db.execute('UPDATE controller SET last_tick_at=?,health=? WHERE singleton=1',(_now(),_dump(health)))
    def controller_health(self):
        with self._db() as db:
            row=None if db is None else db.execute('SELECT * FROM controller WHERE singleton=1').fetchone()
            if row is None:return None
            value=dict(row);value['health']=self._health(_json(value['health']))
            return value
    def recover(self)->list[str]:
        return self._recover(True)
    def _recover_existing(self)->list[str]:
        """Explicit shutdown recovery may roll back, never initialize/create."""
        return self._recover(False)
    def _recover(self,initialize):
        recovered=[]
        with self._db(True,initialize=initialize) as db:
            for row in db.execute('SELECT * FROM runs WHERE owner_id IS NOT NULL'):
                if self._cancel_clean_ready(db,row):
                    recovered.append(row['run_id']);continue
                if row['state']=='ready' and self._safe_ready(db,row): continue
                if row['state'] in ACTIVE-{'unknown'} and _dead(row['owner_pid']):
                    db.execute("UPDATE runs SET state='unknown',reason='owner_dead',updated_at=? WHERE run_id=? AND owner_id=? AND state=?",(_now(),row['run_id'],row['owner_id'],row['state']))
                    self._event(db,row['run_id'],'recovered',row['state'],'unknown','owner_dead'); recovered.append(row['run_id'])
        return recovered






