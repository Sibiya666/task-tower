"""Exact opt-in preparing protocol; no new claim, capacity or resume authority."""
import copy,json,re,uuid
from .beads import ServiceError,identity
from ..preparing_recovery import parse_receipt,validate_receipt,fingerprint

def approval_registry(value,projects):
    if value is None:value={}
    if not isinstance(value,dict) or set(value)-set(projects):raise ValueError('invalid_preparing_approvals')
    result={}
    for project,ds in value.items():
        if not isinstance(ds,(list,set,frozenset)) or len(ds)>32 or any(not isinstance(d,str) or re.fullmatch('[0-9a-f]{64}',d) is None for d in ds):raise ValueError('invalid_preparing_approvals')
        result[project]=frozenset(ds)
    return result

def command_ids(r):
    digest=fingerprint(parse_receipt(r))
    return tuple(str(uuid.uuid5(uuid.NAMESPACE_URL,'task-tower:preparing:'+kind+':'+digest)) for kind in ('control','execute'))

def prepared_result(r):
    return dict(version=1,state='prepared',receipt_sha256=fingerprint(r),**{k:r[k] for k in ('operation_id','connector_id','project_id','attempt_id','command_id','engine_sha')})

class PreparingStore:
    def _preparing_approved(self,value,connector):
        try:
            r=parse_receipt(value)
            return validate_receipt(r,self.approved_preparing,connector_id=connector,source_sha=r['engine_sha'])
        except ValueError:raise ServiceError('preparing_receipt_refused',403) from None
    def _preparing_row(self,key,connector,*,control=False):
        identity(key);identity(connector)
        row=self.db.execute('SELECT * FROM preparing_recoveries WHERE '+('control_id' if control else 'operation_id')+'=? AND connector_id=?',(key,connector)).fetchone()
        if row is None:raise ServiceError('preparing_not_found',404)
        try:d=json.loads(row['data']);r=parse_receipt(d['receipt']);ids=command_ids(r)
        except (ValueError,TypeError,KeyError):raise ServiceError('preparing_journal_invalid') from None
        if (set(d)!={'receipt','receipt_sha256','snapshot_sha256','state','control_command_id','execute_command_id','outcome'} or row['operation_id']!=r['operation_id'] or row['attempt_id']!=r['attempt_id'] or row['connector_id']!=r['connector_id'] or row['control_id']!=ids[0] or d['receipt_sha256']!=fingerprint(r) or (d['control_command_id'],d['execute_command_id'])!=ids or d['state'] not in ('pending','prepared','unknown')):raise ServiceError('preparing_journal_invalid')
        outcome=d['outcome']
        if not isinstance(d['snapshot_sha256'],str) or re.fullmatch('[0-9a-f]{64}',d['snapshot_sha256']) is None:raise ServiceError('preparing_journal_invalid')
        if d['state']!='prepared' and outcome is not None:raise ServiceError('preparing_journal_invalid')
        if d['state']=='prepared' and (not isinstance(outcome,dict) or any(outcome.get(k)!=r[k] for k in ('attempt_id','project_id','connector_id','bead_id','base_sha')) or outcome.get('actor')!=r['native_owner'] or outcome.get('active_command_id')!=ids[1] or outcome.get('phase')!='executing' or outcome.get('execution_state')!='not_started' or outcome.get('managed') is not True or outcome.get('quiescent') is not False or any(outcome.get(k) is not None for k in ('author_thread_id','head_sha','thread_id','turn_id','review')) or outcome.get('review_threads') not in (None,[])):raise ServiceError('preparing_journal_invalid')
        return d
    @staticmethod
    def _preparing_status(d):
        return dict(operation_id=d['receipt']['operation_id'],project_id=d['receipt']['project_id'],attempt_id=d['receipt']['attempt_id'],receipt_sha256=d['receipt_sha256'],state=d['state'],control_command_id=d['control_command_id'],execute_command_id=d['execute_command_id'])
    def preparing_status(self,key,connector):
        with self.lock:return self._preparing_status(self._preparing_row(key,connector))
    def _preparing_eligible(self,r,control=None):
        a=self.attempt(r['attempt_id'],r['connector_id'])
        if (a['project_id']!=r['project_id'] or a['bead_id']!=r['bead_id'] or a['actor']!=r['native_owner'] or a.get('managed') is not True or a['phase']!='needs_reconciliation' or a['execution_state']!='unknown' or a.get('quiescent') is not False or a.get('base_sha')!=r['base_sha'] or a.get('active_command_id')!=r['command_id'] or any(a.get(k) is not None for k in ('author_thread_id','head_sha','thread_id','turn_id','review')) or a.get('review_threads') not in (None,[])):raise ServiceError('preparing_attempt_fenced')
        row=self.db.execute('SELECT * FROM lifecycle_commands WHERE command_id=?',(r['command_id'],)).fetchone()
        if row is None or row['attempt_id']!=r['attempt_id'] or row['connector_id']!=r['connector_id'] or row['state']!='acknowledged':raise ServiceError('preparing_original_command_fenced')
        c=json.loads(row['data'])
        if (set(c)!={'version','kind','command_id','attempt_id','project_id','base_sha','input','source'} or type(c['version']) is not int or c['version']!=1 or c['kind']!='execute' or any(c[k]!=r[k] for k in ('command_id','attempt_id','project_id','base_sha')) or fingerprint(c)!=r['command_sha256'] or c['source']!=dict(base_sha=r['base_sha'],head_sha=r['base_sha'],diff='')):raise ServiceError('preparing_original_command_changed')
        ids={v[0] for v in self.db.execute('SELECT command_id FROM lifecycle_commands WHERE attempt_id=?',(r['attempt_id'],))}
        if ids!={r['command_id']}|({control} if control else set()) or self.db.execute('SELECT 1 FROM decisions WHERE attempt_id=?',(r['attempt_id'],)).fetchone():raise ServiceError('preparing_history_changed')
        if a.get('delivery_policy')!=self.delivery_policies.get(a['project_id']):raise ServiceError('delivery_policy_changed')
        if a.get('native_profile_digest')!=self.beads.profile_fingerprint(a['project_id']):raise ServiceError('native_profile_changed')
        self._native_execution(a)
        # Transport connection changes alone do not attest execution or invalidate a known acknowledgement.
        snapshot=fingerprint(dict(attempt={k:v for k,v in a.items() if k!='connection_state'},command=dict(row)))
        return a,c,snapshot
    @staticmethod
    def _preparing_control(r):
        return dict(version=1,kind='prepare_existing',command_id=command_ids(r)[0],attempt_id=r['attempt_id'],project_id=r['project_id'],base_sha=r['base_sha'],receipt=r)
    def admit_preparing(self,value,connector):
        from .store import encoded
        with self.lock:
            r=self._preparing_approved(value,connector)
            existing=self.db.execute('SELECT 1 FROM preparing_recoveries WHERE operation_id=?',(r['operation_id'],)).fetchone()
            if existing:
                d=self._preparing_row(r['operation_id'],connector)
                if d['receipt_sha256']!=fingerprint(r):raise ServiceError('preparing_operation_conflict')
                return self._preparing_status(d)
            if self.db.execute('SELECT 1 FROM preparing_recoveries WHERE attempt_id=?',(r['attempt_id'],)).fetchone():raise ServiceError('preparing_attempt_reserved')
            a,c,snapshot=self._preparing_eligible(r);control,execute=command_ids(r)
            if self.db.execute('SELECT 1 FROM lifecycle_commands WHERE command_id IN (?,?)',(control,execute)).fetchone():raise ServiceError('preparing_command_conflict')
            d=dict(receipt=r,receipt_sha256=fingerprint(r),snapshot_sha256=snapshot,state='pending',control_command_id=control,execute_command_id=execute,outcome=None)
            with self.db:
                self.db.execute('INSERT INTO preparing_recoveries VALUES (?,?,?,?,?)',(r['operation_id'],r['attempt_id'],connector,control,encoded(d)))
                self.db.execute('INSERT INTO lifecycle_commands VALUES (?,?,?,?,?)',(control,r['attempt_id'],connector,'queued',encoded(self._preparing_control(r))))
            return self._preparing_status(d)
    def validate_preparing_command(self,key,connector):
        with self.lock:
            d=self._preparing_row(key,connector,control=True);r=self._preparing_approved(d['receipt'],connector)
            row=self.db.execute('SELECT state,data FROM lifecycle_commands WHERE command_id=?',(key,)).fetchone()
            if d['state']!='pending' or row is None or row['state']!='queued' or json.loads(row['data'])!=self._preparing_control(r):raise ServiceError('preparing_control_fenced')
            a,c,snapshot=self._preparing_eligible(r,key)
            if snapshot!=d['snapshot_sha256']:raise ServiceError('preparing_history_changed')
            return a
    def _preparing_event(self,event):
        from .store import encoded
        if not isinstance(event,dict) or set(event) not in ({'version','event_id','attempt_id','connector_id','preparing'},{'version','event_id','attempt_id','connector_id','lifecycle'}) or type(event['version']) is not int or event['version']!=1:raise ServiceError('invalid_preparing_event',400)
        for k in ('event_id','attempt_id','connector_id'):identity(event[k])
        a=self.attempt(event['attempt_id'],event['connector_id']);raw=encoded(event)
        previous=self.db.execute('SELECT fingerprint,outcome FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
        if previous and previous['fingerprint']!=raw:raise ServiceError('event_conflict')
        return a,raw,None if previous is None else json.loads(previous['outcome'])
    def record_preparing_event(self,event):
        from .store import encoded,utc
        with self.lock:
            a,raw,previous=self._preparing_event(event)
            if previous is not None:return previous
            result=event['preparing']
            if not isinstance(result,dict) or not isinstance(result.get('operation_id'),str):raise ServiceError('invalid_preparing_result',400)
            d=self._preparing_row(result['operation_id'],event['connector_id']);r=d['receipt']
            if type(result.get('version')) is not int or result!=prepared_result(r) or a['attempt_id']!=r['attempt_id']:raise ServiceError('preparing_result_changed')
            if d['state']=='unknown':raise ServiceError('preparing_outcome_unknown')
            if d['state']=='prepared':
                with self.db:self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event['event_id'],raw,a['attempt_id'],encoded(d['outcome']),utc()))
                return d['outcome']
            self.validate_preparing_command(d['control_command_id'],event['connector_id'])
            old=json.loads(self.db.execute('SELECT data FROM lifecycle_commands WHERE command_id=?',(r['command_id'],)).fetchone()[0])
            command=dict(old,command_id=d['execute_command_id']);a=copy.deepcopy(a);a.update(phase='executing',execution_state='not_started',active_command_id=command['command_id'])
            d.update(state='prepared',outcome=a)
            with self.db:
                self.db.execute('UPDATE preparing_recoveries SET data=? WHERE operation_id=?',(encoded(d),r['operation_id']))
                self.db.execute("UPDATE lifecycle_commands SET state='acknowledged' WHERE command_id=?",(d['control_command_id'],))
                self._save_attempt(a)
                self.db.execute('INSERT INTO lifecycle_commands VALUES (?,?,?,?,?)',(command['command_id'],a['attempt_id'],event['connector_id'],'queued',encoded(command)))
                self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event['event_id'],raw,a['attempt_id'],encoded(a),utc()))
            return a
    def record_preparing_failure(self,event):
        from .store import encoded,utc
        payload=event.get('lifecycle')
        if not isinstance(payload,dict) or payload.get('kind')!='failed' or not isinstance(payload.get('command_id'),str):return None
        with self.lock:
            row=self.db.execute('SELECT operation_id FROM preparing_recoveries WHERE control_id=? AND connector_id=?',(payload['command_id'],event.get('connector_id'))).fetchone()
            if row is None:return None
            a,raw,previous=self._preparing_event(event)
            if set(payload)!={'kind','command_id'}:raise ServiceError('invalid_preparing_failure',400)
            if previous is not None:return previous
            d=self._preparing_row(row[0],event['connector_id']);r=d['receipt']
            if a['attempt_id']!=r['attempt_id']:raise ServiceError('preparing_attempt_fenced')
            with self.db:
                if d['state']=='pending':
                    d['state']='unknown';self.db.execute('UPDATE preparing_recoveries SET data=? WHERE operation_id=?',(encoded(d),r['operation_id']))
                    self.db.execute("UPDATE lifecycle_commands SET state='acknowledged' WHERE command_id=?",(d['control_command_id'],))
                self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event['event_id'],raw,a['attempt_id'],encoded(a),utc()))
            return a
