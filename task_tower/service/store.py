"""Single-owner SQLite delivery journal. Native Beads remains the only task engine.

Pending external effects are fenced on restart, never automatically replayed.
Trusted typed delivery acceptance is implemented by the acceptance mixin.
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


def validate_plan(plan,*,external_closed=False):
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
        for dep in deps:bead_id(dep)
        tasks[key]=task
    visited,active=set(),set()
    def visit(key):
        if external_closed and key not in tasks:return
        if key not in tasks or key in active: raise ServiceError('invalid_dependency_graph',400)
        if key in visited:return
        active.add(key)
        for dep in tasks[key]['depends_on']:visit(dep)
        active.remove(key);visited.add(key)
    for key in tasks:visit(key)
    return tasks


from .lifecycle import LifecycleStore
from .preparing_recovery import PreparingStore,approval_registry
from .acceptance import AcceptanceStore


from .issue_admission import IssueAdmissionStore

class Store(IssueAdmissionStore,PreparingStore,LifecycleStore,AcceptanceStore):
    def __init__(self,path,beads,*,approved_plans=None,max_active_tasks=2,delivery_projects=None,delivery_policies=None,approved_preparing=None,issue_bindings=None):
        if type(max_active_tasks) is not int or not 1<=max_active_tasks<=32:raise ValueError('invalid_capacity')
        self.approved_preparing=approval_registry(approved_preparing,beads.projects)
        self.delivery_projects=dict(delivery_projects or {})
        from ..delivery_policy import policies
        self.delivery_policies=policies(beads.projects,self.delivery_projects,delivery_policies)
        if any(p not in beads.projects or not isinstance(r,str) or __import__('re').fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',r) is None for p,r in self.delivery_projects.items()):raise ValueError('invalid_delivery_scope')
        self.delivery_projects={p:v['repository'] for p,v in self.delivery_policies.items() if v['mode']=='task_tower'}
        self.max_active_tasks=max_active_tasks
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
                CREATE TABLE IF NOT EXISTS acceptance_effects (attempt_id TEXT PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,fingerprint TEXT NOT NULL,state TEXT NOT NULL,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS acceptance_repository (repository TEXT PRIMARY KEY,attempt_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preparing_recoveries (operation_id TEXT PRIMARY KEY,attempt_id TEXT UNIQUE NOT NULL,connector_id TEXT NOT NULL,control_id TEXT UNIQUE NOT NULL,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lifecycle_commands (
                  command_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, connector_id TEXT NOT NULL,
                  state TEXT NOT NULL, data TEXT NOT NULL);
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
            self._configure_issues(issue_bindings)
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
        result=self.issue_published(project)
        for row in self.db.execute("SELECT digest,data FROM plan_imports WHERE project_id=? AND state='published'",(project,)):
            if row['digest'] not in self.approved_plans.get(project,()):continue
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
            if self.active_count(connector_id)>=self.max_active_tasks:raise ServiceError('connector_capacity')
            attempt_id=str(uuid.uuid4());actor='tower-'+attempt_id
            data=dict(attempt_id=attempt_id,project_id=project_id,bead_id=bead_id_,connector_id=connector_id,
                actor=actor,phase='claim_pending',execution_state='not_started',connection_state='connected',
                correction_count=0,thread_id=None,turn_id=None,worktree_ref=None,head_sha=None,base_sha=None,
                pr_number=None,main_sha=None)
            if project_id in self.delivery_policies:
                data['delivery_policy']=dict(self.delivery_policies[project_id])
            if self.beads.profile_fingerprint(project_id) is not None:
                data['native_profile_digest']=self.beads.profile_fingerprint(project_id)
            # Commit intent before crossing the native boundary.
            with self.db:
                self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?)',
                    (attempt_id,project_id,bead_id_,connector_id,actor,data['phase'],encoded(data),utc(),utc()))
                self.db.execute('INSERT INTO commands VALUES (?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()),request_id,fingerprint,attempt_id,'claim_pending',None,utc()))
            try:
                task=self._approved_task(project_id,bead_id_)
                issue=self.issue_guard(project_id,bead_id_,connector_id)
                if issue:
                    data.update(source_issue=issue['source_issue'],issue_source_revision=issue['source_revision'],issue_policy_sha256=issue['policy_sha256'],issue_paths=issue['paths'],issue_base_sha=issue['base_sha'],issue_admitted_at=issue['admitted_at'])
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

    def adopt_plan(self,request_id,project,digest,plan):
        identity(request_id);self.beads.project(project)
        if not isinstance(plan,dict) or set(plan)!={'tasks'} or not isinstance(plan['tasks'],list):
            raise ServiceError('invalid_plan',400)
        clean={'tasks':[]}
        for task in plan['tasks']:
            if not isinstance(task,dict) or set(task)!={'id','title','description','depends_on','parents'}:
                raise ServiceError('invalid_plan',400)
            parents=task['parents']
            if (not isinstance(parents,list) or len(parents)>31 or any(not isinstance(x,str) for x in parents)
                    or len(set(parents))!=len(parents) or task['id'] in parents):
                raise ServiceError('invalid_parents',400)
            for parent in parents:bead_id(parent)
            clean['tasks'].append({k:v for k,v in task.items() if k!='parents'})
        validate_plan(clean,external_closed=True)
        if not isinstance(digest,str) or plan_digest(plan)!=digest or digest not in self.approved_plans.get(project,()):
            raise ServiceError('plan_not_approved',403)
        tasks={t['id']:t for t in plan['tasks']}
        with self.lock:
            row=self.db.execute('SELECT * FROM plan_imports WHERE request_id=?',(request_id,)).fetchone()
            if row:
                if row['project_id']!=project or row['digest']!=digest:raise ServiceError('request_conflict')
                return self._import_outcome(row)
            for row in self.db.execute('SELECT * FROM plan_imports WHERE project_id=?',(project,)):
                if row['digest']==digest:
                    with self.db:self.db.execute('INSERT INTO plan_imports VALUES (?,?,?,?,?,?,?)',
                        (request_id,project,digest,row['state'],row['data'],utc(),utc()))
                    return self._import_outcome(row)
                if set(tasks)&{t['id'] for t in json.loads(row['data'])['plan']['tasks']}:
                    raise ServiceError('import_task_conflict')
            data=dict(plan=plan,request_id=request_id,project_id=project,digest=digest,adopted=True)
            with self.db:self.db.execute('INSERT INTO plan_imports VALUES (?,?,?,?,?,?,?)',
                (request_id,project,digest,'importing',encoded(data),utc(),utc()))
            state='needs_reconciliation';deadline=time.monotonic()+60
            try:
                self._verify_import(project,tasks,'open',deadline)
                self._verify_import(project,tasks,'open',deadline)
                state='published'
            except Exception:pass
            with self.db:self.db.execute('UPDATE plan_imports SET state=?,updated_at=? WHERE request_id=?',(state,utc(),request_id))
            return dict(request_id=request_id,project_id=project,digest=digest,state=state)

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
        issue=self.issue_task(project,bead)
        if issue is not None:return issue
        raise ServiceError('unpublished_task',403)

    def _verify_import(self,project,tasks,status,deadline):
        for task in tasks.values():
            row=self.beads.show(project,task['id'],deadline=deadline)
            self._verify_row(task,row,status)
            if 'parents' in task:
                for dependency in task['depends_on']:
                    if dependency not in tasks:
                        dep=self.beads.show(project,dependency,deadline=deadline)
                        if dep.get('status')!='closed':raise ServiceError('adoption_dependency_not_closed')

    def _verify_row(self,task,row,status,owner=None):
        deps=row.get('dependencies',[])
        if not isinstance(deps,list) or any(not isinstance(d,dict) for d in deps):
            raise ServiceError('import_readback_mismatch')
        actual=[d.get('id') for d in deps if d.get('dependency_type')=='blocks']
        parents=[d.get('id') for d in deps if d.get('dependency_type')=='parent-child']
        hierarchy_ok=(sorted(parents)==sorted(task['parents']) and len(actual)+len(parents)==len(deps)) if 'parents' in task else len(actual)==len(deps)
        if (row.get('status')!=status or (row.get('assignee') or None)!=owner
                or row.get('title')!=task['title'] or row.get('description')!=task['description']
                or any(not isinstance(d,str) for d in actual)
                or sorted(actual)!=sorted(task['depends_on']) or not hierarchy_ok
                or ('parents' in task and row.get('metadata'))
                or (status=='deferred' and not row.get('defer_until'))
                or (status!='deferred' and row.get('defer_until'))):
            raise ServiceError('import_readback_mismatch')

    def validate_execution(self,attempt_id,connector_id,*,lifecycle=False,delivery=False):
        """Fresh native read-only boundary; cached attempt is never executable authority."""
        with self.lock:
            data=self.attempt(attempt_id,connector_id)
            if data.get('delivery_policy')!=self.delivery_policies.get(data['project_id']):raise ServiceError('delivery_policy_changed')
            if data.get('native_profile_digest')!=self.beads.profile_fingerprint(data['project_id']):raise ServiceError('native_profile_changed')
            allowed={'awaiting_merge','postmerge'} if delivery else {'claimed','executing','reviewing','revising','needs_input'} if lifecycle else {'claimed'}
            if data['phase'] not in allowed or (not lifecycle and not delivery and data['execution_state']!='not_started'):
                raise ServiceError('execution_fenced')
            return self._native_execution(data)

    def _native_execution(self,data):
        """Shared read-only native checks under the same store RLock."""
        with self.lock:
            deadline=time.monotonic()+30
            task=self._approved_task(data['project_id'],data['bead_id'])
            issue=self.issue_guard(data['project_id'],data['bead_id'],data['connector_id'])
            approved=issue is not None
            if issue and (data.get('source_issue')!=issue['source_issue'] or data.get('issue_policy_sha256')!=issue['policy_sha256']):raise ServiceError('issue_attempt_binding_changed')
            for batch in self.db.execute("SELECT digest,data FROM plan_imports WHERE project_id=? AND state='published'",(data['project_id'],)):
                if batch['digest'] in self.approved_plans.get(data['project_id'],()) and data['bead_id'] in {t['id'] for t in json.loads(batch['data'])['plan']['tasks']}:approved=True
            if not approved:raise ServiceError('execution_plan_not_approved')
            row=self.beads.show(data['project_id'],data['bead_id'],deadline=deadline)
            self._verify_row(task,row,'in_progress',data['actor'])
            if row.get('metadata') or row.get('defer_until'):
                raise ServiceError('native_fence_or_unknown_metadata')
            for dependency in task['depends_on']:
                dep=self.beads.show(data['project_id'],dependency,deadline=deadline)
                if dep.get('status')!='closed':raise ServiceError('execution_dependency_changed')
            return data

    def record_event(self,event):
        if isinstance(event,dict) and 'preparing' in event:return self.record_preparing_event(event)
        if isinstance(event,dict):
            failure=self.record_preparing_failure(event)
            if failure is not None:return failure
        if isinstance(event,dict) and 'lifecycle' in event:return self.record_lifecycle_event(event)
        if isinstance(event,dict) and self.attempt(event.get('attempt_id'),event.get('connector_id')).get('managed'):
            raise ServiceError('managed_event_required',403)
        required={'version','event_id','attempt_id','connector_id','phase','execution_state','connection_state'}
        if not isinstance(event,dict) or set(event) not in (required,required|{'execution'}) or type(event['version']) is not int or event['version']!=1:
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
        execution=event.get('execution')
        if execution is not None:
            if (not isinstance(execution,dict) or set(execution)!={'command_id','thread_id','turn_id','result'}
                    or event['phase']!='executing' or event['execution_state']!='completed'
                    or not isinstance(execution['result'],str) or len(execution['result'].encode('utf-8'))>32768):
                raise ServiceError('invalid_execution_result',400)
            for key in ('command_id','thread_id','turn_id'):identity(execution[key])
        fingerprint=encoded(event)
        with self.lock:
            data=self.attempt(event['attempt_id'],event['connector_id'])
            previous=self.db.execute('SELECT * FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
            if previous:
                if previous['fingerprint']!=fingerprint:raise ServiceError('event_conflict')
                return json.loads(previous['outcome'])
            if event['phase']!=data['phase'] and event['phase'] not in transitions.get(data['phase'],set()):
                raise ServiceError('invalid_transition')
            if execution is not None:
                if any(data.get(key) not in (None,execution[key]) for key in ('command_id','thread_id','turn_id')):
                    raise ServiceError('execution_identity_conflict')
                if data.get('execution_result') not in (None,execution['result']):raise ServiceError('execution_result_conflict')
                data.update({key:execution[key] for key in ('command_id','thread_id','turn_id')})
                data['execution_result']=execution['result']
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
            if self.attempt(value['attempt_id'],value['connector_id']).get('managed'):
                raise ServiceError('structured_approval_required',403)
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
