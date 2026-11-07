"""Single-owner SQLite delivery journal. Native Beads remains the only task engine.

Pending external effects are fenced on restart, never automatically replayed.
No method in this stage accepts delivery, closes a task, or runs a command.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .beads import ServiceError, identity, bead_id
from ..project_connections import safe_config_path


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def plan_digest(plan):
    return hashlib.sha256(encoded(plan).encode('utf-8')).hexdigest()


def utc(): return datetime.now(timezone.utc).isoformat()


def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!={'tasks'} or not isinstance(plan['tasks'],list) or not 1<=len(plan['tasks'])<=32:
        raise ServiceError('invalid_plan',400)
    tasks={}
    for task in plan['tasks']:
        if not isinstance(task,dict) or set(task)!={'id','title','description','depends_on'}:
            raise ServiceError('invalid_plan',400)
        key=bead_id(task['id'])
        if key in tasks: raise ServiceError('duplicate_plan_task',400)
        for field,maximum in [('title',256),('description',8192)]:
            text=task[field]
            if not isinstance(text,str) or not text.strip() or len(text)>maximum or '\x00' in text:
                raise ServiceError('invalid_plan_text',400)
        deps=task['depends_on']
        if not isinstance(deps,list) or len(deps)>31 or any(not isinstance(d,str) for d in deps) or len(set(deps))!=len(deps):
            raise ServiceError('invalid_dependencies',400)
        tasks[key]=task
    visited,active=set(),set()
    def visit(key):
        if key not in tasks or key in active: raise ServiceError('invalid_dependency_graph',400)
        if key in visited:return
        active.add(key)
        for dep in tasks[key]['depends_on']:visit(dep)
        active.remove(key);visited.add(key)
    for key in tasks:visit(key)
    return tasks


class Store:
    def __init__(self,path,beads,*,approved_plans=None):
        self.path=safe_config_path(Path(path).absolute())
        self.beads=beads
        self.approved_plans={p:frozenset(ds) for p,ds in (approved_plans or {}).items()}
        self.lock=threading.RLock()
        self._guard=None
        self.db=None
        guard=safe_config_path(Path(str(self.path)+'.lock'))
        self._guard=open(guard,'a+b')
        try:
            # An OS-held lease, not a PID file. Never remove the locked inode.
            if os.name=='nt':
                import msvcrt
                self._guard.seek(0);self._guard.write(b'0');self._guard.flush();self._guard.seek(0)
                msvcrt.locking(self._guard.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._guard.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not self.path.exists():
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            self.db=sqlite3.connect(self.path,timeout=5,check_same_thread=False)
            self.db.row_factory=sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS attempts (
                  attempt_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, bead_id TEXT NOT NULL,
                  connector_id TEXT NOT NULL, actor TEXT NOT NULL, phase TEXT NOT NULL,
                  data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS active_attempt ON attempts(project_id,bead_id)
                  WHERE phase != 'accepted';
                CREATE TABLE IF NOT EXISTS commands (
                  command_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                  fingerprint TEXT NOT NULL, attempt_id TEXT NOT NULL, phase TEXT NOT NULL,
                  outcome TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                  event_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                  attempt_id TEXT NOT NULL, outcome TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decisions (
                  decision_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL,
                  attempt_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plan_imports (
                  request_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                  digest TEXT NOT NULL, state TEXT NOT NULL, data TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            """)
            with self.db:
                for row in self.db.execute("SELECT * FROM attempts WHERE phase='claim_pending'").fetchall():
                    data=json.loads(row['data']);data['phase']='needs_reconciliation'
                    self._save_attempt(data)
                self.db.execute("UPDATE commands SET phase='needs_reconciliation' WHERE phase='claim_pending'")
                self.db.execute("UPDATE plan_imports SET state='needs_reconciliation',updated_at=? WHERE state='importing'",(utc(),))
        except BaseException:
            self.close();raise

    def close(self):
        with self.lock:
            if self.db is not None:self.db.close();self.db=None
            if self._guard is not None:self._guard.close();self._guard=None

    def _save_attempt(self,data):
        self.db.execute('UPDATE attempts SET phase=?,data=?,updated_at=? WHERE attempt_id=?',
                        (data['phase'],encoded(data),utc(),data['attempt_id']))

    def attempt(self,attempt_id,connector_id=None):
        identity(attempt_id)
        with self.lock:
            row=self.db.execute('SELECT data FROM attempts WHERE attempt_id=?',(attempt_id,)).fetchone()
            if row is None:raise ServiceError('attempt_not_found',404)
            data=json.loads(row['data'])
            if connector_id is not None and data['connector_id']!=connector_id:
                raise ServiceError('connector_forbidden',403)
            return data

    def _published(self,project):
        result=set()
        for row in self.db.execute("SELECT data FROM plan_imports WHERE project_id=? AND state='published'",(project,)):
            result.update(t['id'] for t in json.loads(row['data'])['plan']['tasks'])
        return result

    def ready(self,project):
        self.beads.project(project)
        with self.lock:
            allowed=self._published(project)
            busy={r[0] for r in self.db.execute("SELECT bead_id FROM attempts WHERE project_id=? AND phase!='accepted'",(project,))}
            return [{k:r[k] for k in ('id','title','status','priority','issue_type') if k in r}
                    for r in self.beads.ready(project) if r['id'] in allowed and r['id'] not in busy]

    def claim_request(self,request_id,project_id,bead_id_,connector_id):
        identity(request_id);identity(connector_id);bead_id(bead_id_);self.beads.project(project_id)
        fingerprint=encoded([project_id,bead_id_,connector_id])
        with self.lock:
            command=self.db.execute('SELECT * FROM commands WHERE request_id=?',(request_id,)).fetchone()
            if command:
                if command['fingerprint']!=fingerprint:raise ServiceError('request_conflict')
                if command['outcome'] is not None:return json.loads(command['outcome'])
                return self.attempt(command['attempt_id'],connector_id)
            if bead_id_ not in self._published(project_id):raise ServiceError('unpublished_task',403)
            row=self.db.execute("SELECT * FROM attempts WHERE project_id=? AND bead_id=? AND phase!='accepted'",
                                (project_id,bead_id_)).fetchone()
            if row:
                if row['connector_id']!=connector_id:raise ServiceError('owner_conflict')
                first=self.db.execute('SELECT outcome FROM commands WHERE attempt_id=? AND outcome IS NOT NULL ORDER BY created_at LIMIT 1',(row['attempt_id'],)).fetchone()
                data=json.loads(first[0]) if first else json.loads(row['data'])
                with self.db:self.db.execute('INSERT INTO commands VALUES (?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),request_id,fingerprint,row['attempt_id'],data['phase'],encoded(data),utc()))
                return data
            attempt_id=str(uuid.uuid4());actor='tower-'+attempt_id
            data=dict(attempt_id=attempt_id,project_id=project_id,bead_id=bead_id_,connector_id=connector_id,
                actor=actor,phase='claim_pending',execution_state='not_started',connection_state='connected',
                correction_count=0,thread_id=None,turn_id=None,worktree_ref=None,head_sha=None,base_sha=None,
                pr_number=None,main_sha=None)
            # Commit intent before crossing the native boundary.
            with self.db:
                self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?)',
                    (attempt_id,project_id,bead_id_,connector_id,actor,data['phase'],encoded(data),utc(),utc()))
                self.db.execute('INSERT INTO commands VALUES (?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),request_id,fingerprint,attempt_id,'claim_pending',None,utc()))
            try:
                task=self._approved_task(project_id,bead_id_)
                self._verify_import(project_id,{bead_id_:task},'open',time.monotonic()+30)
                row=self.beads.claim(project_id,bead_id_,actor)
                self._verify_row(task,row,'in_progress',actor)
                data['phase']='claimed'
            except Exception:
                # Even a failure response may follow a native effect. Preserve ownership/fence.
                data['phase']='needs_reconciliation'
            with self.db:
                self._save_attempt(data)
                self.db.execute('UPDATE commands SET phase=?,outcome=? WHERE request_id=?',
                                (data['phase'],encoded(data),request_id))
            return data

    def import_plan(self,request_id,project,digest,plan):
        identity(request_id);self.beads.project(project)
        tasks=validate_plan(plan)
        if not isinstance(digest,str) or plan_digest(plan)!=digest or digest not in self.approved_plans.get(project,()):
            raise ServiceError('plan_not_approved',403)
        with self.lock:
            row=self.db.execute('SELECT * FROM plan_imports WHERE request_id=?',(request_id,)).fetchone()
            if row:
                if row['project_id']!=project or row['digest']!=digest:raise ServiceError('request_conflict')
                return self._import_outcome(row)
            row=self.db.execute('SELECT * FROM plan_imports WHERE project_id=? AND digest=?',(project,digest)).fetchone()
            if row:
                with self.db:self.db.execute('INSERT INTO plan_imports VALUES (?,?,?,?,?,?,?)',
                    (request_id,project,digest,row['state'],row['data'],utc(),utc()))
                return self._import_outcome(row)
            for row in self.db.execute('SELECT data FROM plan_imports WHERE project_id=?',(project,)):
                if set(tasks)&{t['id'] for t in json.loads(row['data'])['plan']['tasks']}:
                    raise ServiceError('import_task_conflict')
            data=dict(plan=plan,request_id=request_id,project_id=project,digest=digest)
            with self.db:self.db.execute('INSERT INTO plan_imports VALUES (?,?,?,?,?,?,?)',
                (request_id,project,digest,'importing',encoded(data),utc(),utc()))
            state='needs_reconciliation';deadline=time.monotonic()+120;actor='task-tower-plan-import'
            try:
                for task in tasks.values():self.beads.create_deferred(project,task,actor,deadline)
                for task in tasks.values():
                    for dep in task['depends_on']:self.beads.add_dependency(project,task['id'],dep,actor,deadline)
                self._verify_import(project,tasks,'deferred',deadline)
                for task in tasks.values():self.beads.publish(project,task['id'],actor,deadline)
                self._verify_import(project,tasks,'open',deadline)
                state='published'
            except Exception:pass
            with self.db:self.db.execute('UPDATE plan_imports SET state=?,updated_at=? WHERE request_id=?',(state,utc(),request_id))
            return dict(request_id=request_id,project_id=project,digest=digest,state=state)

    def _import_outcome(self,row):
        return dict(request_id=json.loads(row['data'])['request_id'],project_id=row['project_id'],
                    digest=row['digest'],state=row['state'])

    def _approved_task(self,project,bead):
        for row in self.db.execute("SELECT data FROM plan_imports WHERE project_id=? AND state='published'",(project,)):
            for task in json.loads(row[0])['plan']['tasks']:
                if task['id']==bead:return task
        raise ServiceError('unpublished_task',403)

    def _verify_import(self,project,tasks,status,deadline):
        for task in tasks.values():
            row=self.beads.show(project,task['id'],deadline=deadline)
            self._verify_row(task,row,status)

    def _verify_row(self,task,row,status,owner=None):
        deps=row.get('dependencies',[])
        if not isinstance(deps,list) or any(not isinstance(d,dict) for d in deps):
            raise ServiceError('import_readback_mismatch')
        actual=[d.get('id') for d in deps if d.get('dependency_type')=='blocks']
        if (row.get('status')!=status or (row.get('assignee') or None)!=owner
                or row.get('title')!=task['title'] or row.get('description')!=task['description']
                or any(not isinstance(d,str) for d in actual)
                or sorted(actual)!=sorted(task['depends_on']) or len(actual)!=len(deps)
                or (status=='deferred' and not row.get('defer_until'))
                or (status!='deferred' and row.get('defer_until'))):
            raise ServiceError('import_readback_mismatch')

    def record_event(self,event):
        required={'version','event_id','attempt_id','connector_id','phase','execution_state','connection_state'}
        if not isinstance(event,dict) or set(event)!=required or type(event['version']) is not int or event['version']!=1:
            raise ServiceError('invalid_event',400)
        identity(event['event_id']);identity(event['connector_id'])
        transitions={
            'claimed':{'executing','needs_input','needs_reconciliation'},
            'executing':{'reviewing','needs_input','needs_reconciliation'},
            'reviewing':{'revising','awaiting_merge','needs_input','needs_reconciliation'},
            'revising':{'executing','reviewing','needs_input','needs_reconciliation'},
            'awaiting_merge':{'postmerge','needs_input','needs_reconciliation'},
            'postmerge':{'needs_input','needs_reconciliation'},
            'needs_input':{'needs_reconciliation'},'needs_reconciliation':set()}
        if event['phase'] not in {'executing','reviewing','revising','awaiting_merge','postmerge','needs_input','needs_reconciliation'}:
            raise ServiceError('phase_forbidden',403)
        if event['execution_state'] not in ('not_started','running','stopped','completed','unknown') or event['connection_state'] not in ('connected','disconnected','unknown'):
            raise ServiceError('invalid_event_state',400)
        fingerprint=encoded(event)
        with self.lock:
            data=self.attempt(event['attempt_id'],event['connector_id'])
            previous=self.db.execute('SELECT * FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
            if previous:
                if previous['fingerprint']!=fingerprint:raise ServiceError('event_conflict')
                return json.loads(previous['outcome'])
            if event['phase']!=data['phase'] and event['phase'] not in transitions.get(data['phase'],set()):
                raise ServiceError('invalid_transition')
            data.update({k:event[k] for k in ('phase','execution_state','connection_state')})
            with self.db:
                self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',
                    (event['event_id'],fingerprint,data['attempt_id'],encoded(data),utc()))
                self._save_attempt(data)
            return data

    def decision(self,value):
        fields={'version','decision_id','attempt_id','connector_id','question'}
        if not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int or value['version']!=1:
            raise ServiceError('invalid_decision',400)
        identity(value['decision_id']);identity(value['connector_id'])
        if not isinstance(value['question'],str) or not 1<=len(value['question'])<=4096:
            raise ServiceError('invalid_question',400)
        with self.lock:
            self.attempt(value['attempt_id'],value['connector_id'])
            row=self.db.execute('SELECT data FROM decisions WHERE decision_id=?',(value['decision_id'],)).fetchone()
            if row:
                if row[0]!=encoded(value):raise ServiceError('decision_conflict')
                return json.loads(row[0])
            with self.db:self.db.execute('INSERT INTO decisions VALUES (?,?,?,?,?)',
                (value['decision_id'],value['connector_id'],value['attempt_id'],encoded(value),utc()))
            return value

    def decisions(self,connector_id):
        identity(connector_id)
        with self.lock:return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM decisions WHERE connector_id=? ORDER BY created_at',(connector_id,))]
