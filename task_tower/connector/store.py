"""Durable connector inbox/outbox. Unknown effects are fenced, never replayed."""
import json
import os
from pathlib import Path
import sqlite3
import threading
import tempfile
import hashlib
import uuid
from ..project_connections import safe_config_path
from ..service.beads import identity
from ..service.store import encoded,utc

class ConnectorStore:
    def __init__(self,path,connector_id):
        identity(connector_id)
        self.connector_id=connector_id;self.lock=threading.RLock();self.db=None;self.guards=[]
        self.path=safe_config_path(Path(path).absolute())
        try:
            for path in [Path(str(self.path)+'.lock'),Path(tempfile.gettempdir())/('task-tower-connector-'+hashlib.sha256(connector_id.encode('utf-8')).hexdigest()+'.lock')]:
                f=open(safe_config_path(path),'a+b');self.guards.append(f)
                if os.name=='nt':
                    import msvcrt
                    f.seek(0);f.write(b'0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not self.path.exists():
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            self.db=sqlite3.connect(self.path,check_same_thread=False);self.db.row_factory=sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            self.db.executescript("""
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inbox (command_id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,data TEXT NOT NULL,acked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS worktrees (attempt_id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (key TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS preparing_operations (operation_id TEXT PRIMARY KEY,attempt_id TEXT UNIQUE NOT NULL,data TEXT NOT NULL);
""")
            with self.db:
                row=self.db.execute("SELECT value FROM metadata WHERE key='connector_id'").fetchone()
                if row and row[0]!=connector_id:raise ValueError('connector_identity_mismatch')
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('connector_id',?)",(connector_id,))
                for row in self.db.execute('SELECT data FROM inbox').fetchall():
                    data=json.loads(row[0])
                    if data['phase'] in ('queued','preparing','creating_thread','prepared','starting','executing') or (data['command'].get('kind') and data['phase']=='needs_input'):
                        data['phase']='needs_reconciliation';self._save(data)
                        if data['command'].get('kind')=='main_review':pass
                        elif data['command'].get('kind'):self.lifecycle_event(data['command']['attempt_id'],'failed',command_id=data['command']['command_id'])
                        else:self.event(data['command']['attempt_id'],'needs_reconciliation','unknown')
        except BaseException:self.close();raise
    def close(self):
        with self.lock:
            if self.db is not None:self.db.close();self.db=None
            for f in self.guards:f.close()
            self.guards=[]
    def preparing_control(self,command):
        from ..preparing_recovery import parse_receipt
        from ..service.preparing_recovery import command_ids
        fields={'version','kind','command_id','attempt_id','project_id','base_sha','receipt'}
        if not isinstance(command,dict) or set(command)!=fields or type(command['version']) is not int or command['version']!=1 or command['kind']!='prepare_existing':raise ValueError('invalid_preparing_control')
        r=parse_receipt(command['receipt'])
        if r['connector_id']!=self.connector_id or any(command[k]!=r[k] for k in ('attempt_id','project_id','base_sha')) or command['command_id']!=command_ids(r)[0]:raise ValueError('preparing_control_mismatch')
        return r
    def preparing_failed(self,key):
        with self.lock:
            event=str(uuid.uuid5(uuid.NAMESPACE_URL,'task-tower:preparing:failed:'+identity(key)))
            return self.db.execute('SELECT 1 FROM outbox WHERE event_id=?',(event,)).fetchone() is not None
    def fail_preparing_control(self,command):
        r=self.preparing_control(command)
        with self.lock,self.db:
            prior=self.preparing_operation(r['operation_id'])
            if prior is not None and prior['state']=='prepared':return
            event=dict(version=1,event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'task-tower:preparing:failed:'+command['command_id'])),attempt_id=r['attempt_id'],connector_id=self.connector_id,lifecycle=dict(kind='failed',command_id=command['command_id']))
            raw=encoded(event);previous=self.db.execute('SELECT data FROM outbox WHERE event_id=?',(event['event_id'],)).fetchone()
            if previous is not None:
                if previous[0]!=raw:raise ValueError('preparing_failure_conflict')
                return
            self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],raw))

    def receive(self,command):
        fields={'version','command_id','attempt_id','project_id','base_sha','input'}
        managed=isinstance(command,dict) and command.get('kind') in ('execute','review','revise','quiesce','respond','deliver','main_review')
        if managed:
            fields={'version','kind','command_id','attempt_id','project_id','base_sha'}
            if command['kind'] in ('execute','review','revise','main_review'):fields|={'input','source'}
            if command['kind'] in ('execute','review','revise','main_review') and 'issue_scope' in command:
                from ..issue_runtime import validate_scope
                validate_scope(command['issue_scope']);fields.add('issue_scope')
            if command['kind']=='deliver':fields.add('attempt')
            if command['kind']=='revise':
                fields.add('thread_id')
                if 'update_base' in command:fields.add('update_base')
            if command['kind']=='respond':fields|={'decision_id','target_command_id','request','answer'}
        if not isinstance(command,dict) or set(command)!=fields or type(command['version']) is not int or command['version']!=1:raise ValueError('invalid_command')
        for k in ('command_id','attempt_id','project_id'):identity(command[k])
        import re
        if not isinstance(command['base_sha'],str) or not re.fullmatch('[0-9a-f]{40}',command['base_sha']):raise ValueError('invalid_sha')
        value=command.get('input',{'text':'control'})
        if not isinstance(value,dict) or set(value)!={'text'} or not isinstance(value['text'],str) or not 1<=len(value['text'])<=32768:raise ValueError('invalid_input')
        fingerprint=encoded(command)
        with self.lock:
            row=self.db.execute('SELECT * FROM inbox WHERE command_id=?',(command['command_id'],)).fetchone()
            if row:
                if row['fingerprint']!=fingerprint:raise ValueError('command_conflict')
                return json.loads(row['data'])
            if not managed and any(json.loads(x[0])['command']['attempt_id']==command['attempt_id'] for x in self.db.execute('SELECT data FROM inbox')):raise ValueError('attempt_already_assigned')
            if managed:
                from .briefs import validate_source
                if 'source' in command:validate_source(command['source'])
                if command['kind']=='revise':identity(command['thread_id'])
                if command['kind']=='respond' and command['answer'] not in ('approve','decline'):raise ValueError('invalid_answer')
            data=dict(command=command,phase='queued',thread_id=None,turn_id=None)
            with self.db:self.db.execute('INSERT INTO inbox VALUES (?,?,?)',(command['command_id'],fingerprint,encoded(data)))
            return data
    def _save(self,data):self.db.execute('UPDATE inbox SET data=? WHERE command_id=?',(encoded(data),data['command']['command_id']))
    def command(self,key):
        with self.lock:
            row=self.db.execute('SELECT data FROM inbox WHERE command_id=?',(key,)).fetchone()
            if not row:raise ValueError('unknown_command')
            return json.loads(row[0])
    def update(self,key,**changes):
        with self.lock,self.db:
            data=self.command(key);data.update(changes);self._save(data);return data
    def commands(self):
        with self.lock:return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM inbox ORDER BY rowid')]
    def confirm_cleanup(self,attempt,closed_resources):
        # Caller supplies ONLY resources whose retained owned transport close()
        # succeeded. No handle discovery, packet ordering, or phase inference.
        identity(attempt);closed=set(closed_resources)
        for key in closed:identity(key)
        if not closed:return set()
        confirmed=set()
        with self.lock,self.db:
            for row in self.db.execute('SELECT data FROM inbox').fetchall():
                data=json.loads(row[0]);binding=data.get('cleanup_resources')
                if (data['command']['attempt_id']!=attempt or data.get('cleanup_confirmed') is not False
                        or not isinstance(binding,list) or not binding or not all(isinstance(r,str) and r in closed for r in binding)):continue
                data['cleanup_confirmed']=True
                data.setdefault('cleanup_history',[]).append(dict(kind='owned_transport_cleanup',resource_ids=list(binding),confirmed_at=utc()))
                self._save(data);confirmed.add(data['command']['command_id'])
        return confirmed

    def cleanup_reservations(self):
        # False is a durable unknown/pending cleanup fence, never inferred away
        # from process restart, a completed command, or a closed native task.
        with self.lock:
            return {data['command']['attempt_id'] for row in self.db.execute('SELECT data FROM inbox')
                    if (data:=json.loads(row[0])).get('cleanup_confirmed') is False}

    def event(self,attempt,phase,state):
        identity(attempt)
        event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=attempt,connector_id=self.connector_id,phase=phase,execution_state=state,connection_state='connected')
        with self.lock,self.db:self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
        return event
    def pending_events(self):
        with self.lock:return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM outbox WHERE acked=0 ORDER BY seq')]
    def ack(self,key):
        with self.lock,self.db:self.db.execute('UPDATE outbox SET acked=1 WHERE event_id=?',(key,))
    def worktree(self,key):
        with self.lock:
            row=self.db.execute('SELECT data FROM worktrees WHERE attempt_id=?',(key,)).fetchone()
            return json.loads(row[0]) if row else None
    def save_worktree(self,key,data):
        with self.lock,self.db:self.db.execute('INSERT INTO worktrees VALUES (?,?) ON CONFLICT(attempt_id) DO UPDATE SET data=excluded.data',(key,encoded(data)))
    def claim_intent(self,project,bead):
        key=encoded([project,bead])
        with self.lock,self.db:
            row=self.db.execute('SELECT data FROM claims WHERE key=?',(key,)).fetchone()
            if row:return json.loads(row[0])
            data=dict(request_id=str(uuid.uuid4()),project_id=project,bead_id=bead,connector_id=self.connector_id,version=1)
            self.db.execute('INSERT INTO claims VALUES (?,?)',(key,encoded(data)));return data

    def transition(self,key,phase,state,*,execution=None,**changes):
        """Command outcome and delivery event commit together."""
        with self.lock,self.db:
            data=self.command(key);data.update(changes,phase=phase);self._save(data)
            event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=data['command']['attempt_id'],connector_id=self.connector_id,phase='executing' if phase in ('executing','completed') else phase,execution_state=state,connection_state='connected')
            if execution is not None:event['execution']=execution
            if len(encoded(event).encode('utf-8'))>65536:raise ValueError('event_body_limit')
            self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
            return data
    def existing_claim(self,project,bead):
        with self.lock:
            row=self.db.execute('SELECT data FROM claims WHERE key=?',(encoded([project,bead]),)).fetchone()
            return json.loads(row[0]) if row else None

    def lifecycle_event(self,attempt,kind,**payload):
        identity(attempt)
        event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=attempt,connector_id=self.connector_id,lifecycle=dict(kind=kind,**payload))
        if len(encoded(event).encode('utf-8'))>65536:raise ValueError('event_body_limit')
        with self.lock,self.db:self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
        return event

    def lifecycle_transition(self,key,phase,kind,*,failure_receipt=None,**payload):
        with self.lock,self.db:
            data=self.command(key)
            if failure_receipt is not None:
                from .diagnostics import validate_receipt
                if kind!='failed':raise ValueError('failure_event_required')
                data['failure_receipt']=validate_receipt(failure_receipt)
            data['phase']=phase;self._save(data)
            event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=data['command']['attempt_id'],connector_id=self.connector_id,lifecycle=dict(kind=kind,command_id=key,**payload))
            if len(encoded(event).encode('utf-8'))>65536:raise ValueError('event_body_limit')
            self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
            return data

    def preparing_operation(self,key):
        from ..preparing_recovery import parse_receipt,fingerprint
        identity(key)
        with self.lock:
            row=self.db.execute('SELECT data FROM preparing_operations WHERE operation_id=?',(key,)).fetchone()
            if row is None:return None
            data=json.loads(row[0]);r=parse_receipt(data['receipt'])
            if (set(data)!={'receipt','receipt_sha256','snapshot_sha256','state','result'}
                    or r['operation_id']!=key or fingerprint(r)!=data['receipt_sha256']
                    or data['state'] not in ('intent','unknown','prepared')
                    or (data['state']!='prepared' and data['result'] is not None)):
                raise ValueError('preparing_operation_invalid')
            if data['state']=='prepared' and data['result']!=self._preparing_result(r):raise ValueError('preparing_operation_invalid')
            return data

    @staticmethod
    def _preparing_result(r):
        from ..preparing_recovery import fingerprint
        return dict(version=1,state='prepared',receipt_sha256=fingerprint(r),**{k:r[k] for k in
            ('operation_id','connector_id','project_id','attempt_id','command_id','engine_sha')})

    def _preparing_snapshot(self,r):
        from ..preparing_recovery import fingerprint
        return fingerprint(dict(command=self.command(r['command_id']),worktree=self.worktree(r['attempt_id']),
            commands=sorted(d['command']['command_id'] for d in self.commands() if d['command']['attempt_id']==r['attempt_id']),
            events=sorted(e['event_id'] for e in self.pending_events() if e['attempt_id']==r['attempt_id'])))

    def begin_preparing(self,r):
        from ..preparing_recovery import parse_receipt,fingerprint
        r=parse_receipt(r)
        if r['connector_id']!=self.connector_id:raise ValueError('preparing_connector_mismatch')
        with self.lock,self.db:
            if self.db.execute('SELECT 1 FROM preparing_operations WHERE attempt_id=? OR operation_id=?',(r['attempt_id'],r['operation_id'])).fetchone():
                raise ValueError('preparing_attempt_reserved')
            original=self.command(r['command_id']);tree=self.worktree(r['attempt_id'])
            command=None if original is None else original['command']
            if (command is None or command['attempt_id']!=r['attempt_id'] or command['project_id']!=r['project_id']
                    or fingerprint(command)!=r['command_sha256'] or fingerprint(tree)!=r['worktree_sha256']
                    or fingerprint({k:original.get(k) for k in ('cleanup_resources','cleanup_confirmed')})!=r['cleanup_sha256']):
                raise ValueError('preparing_baseline_changed')
            data=dict(receipt=r,receipt_sha256=fingerprint(r),snapshot_sha256=self._preparing_snapshot(r),state='intent',result=None)
            self.db.execute('INSERT INTO preparing_operations VALUES (?,?,?)',(r['operation_id'],r['attempt_id'],encoded(data)))
            return data

    def complete_preparing(self,r,tree):
        from ..preparing_recovery import fingerprint
        with self.lock,self.db:
            data=self.preparing_operation(r['operation_id'])
            if data is None or data['receipt_sha256']!=fingerprint(r) or data['state']!='intent':raise ValueError('preparing_operation_changed')
            if data['snapshot_sha256']!=self._preparing_snapshot(r):raise ValueError('preparing_history_changed')
            if tree!=dict(self.worktree(r['attempt_id']),state='ready'):raise ValueError('preparing_worktree_changed')
            result=self._preparing_result(r);data.update(state='prepared',result=result)
            event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=r['attempt_id'],connector_id=self.connector_id,preparing=result)
            if len(encoded(event).encode('utf-8'))>65536:raise ValueError('event_body_limit')
            self.db.execute('UPDATE preparing_operations SET data=? WHERE operation_id=?',(encoded(data),r['operation_id']))
            self.db.execute('UPDATE worktrees SET data=? WHERE attempt_id=?',(encoded(tree),r['attempt_id']))
            self.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
            return result

    def unknown_preparing(self,r):
        from ..preparing_recovery import fingerprint
        with self.lock,self.db:
            data=self.preparing_operation(r['operation_id'])
            if data is None or data['receipt_sha256']!=fingerprint(r):raise ValueError('preparing_operation_changed')
            if data['state']=='intent':
                data['state']='unknown'
                self.db.execute('UPDATE preparing_operations SET data=? WHERE operation_id=?',(encoded(data),r['operation_id']))
