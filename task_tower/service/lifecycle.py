"""Fixed MVP roles and transactional command journal, never a task/dependency queue."""
import copy
import json
import uuid
from .beads import ServiceError,identity,strict_json
from ..connector.briefs import build_brief,validate_source


def validate_review(text,source,thread):
    try:value=strict_json(text)
    except (ValueError,TypeError):raise ServiceError('invalid_review_json',400) from None
    fields={'verdict','findings','head_sha','base_sha','reviewer_thread_id'}
    if not isinstance(value,dict) or set(value)!=fields:raise ServiceError('invalid_review_fields',400)
    if (value['verdict'] not in ('approve','changes_requested') or value['head_sha']!=source['head_sha']
            or value['base_sha']!=source['base_sha'] or value['reviewer_thread_id']!=thread):
        raise ServiceError('review_identity_or_source_mismatch')
    findings=value['findings']
    if not isinstance(findings,list) or len(findings)>100:raise ServiceError('invalid_findings',400)
    for f in findings:
        if (not isinstance(f,dict) or set(f)!={'file','line','message'} or type(f['line']) is not int or f['line']<1
                or any(not isinstance(f[k],str) or not 1<=len(f[k])<=4096 or '\x00' in f[k] for k in ('file','message'))):
            raise ServiceError('invalid_findings',400)
    if (value['verdict']=='approve')!= (not findings):raise ServiceError('review_findings_conflict',400)
    return value


def advance(attempt,event,policy):
    """Pure transition proposal; caller commits event/state/commands together."""
    a=copy.deepcopy(attempt);kind=event.get('kind');commands=[]
    def issue(kind,**kw):commands.append(dict(kind=kind,**kw))
    def pause():
        a.update(phase='needs_input',quiescent=False)
        issue('quiesce')
    if kind=='dispatch':
        if a['phase']!='claimed' or a['execution_state']!='not_started' or a.get('managed'):
            raise ServiceError('dispatch_fenced')
        a.update(managed=True,phase='executing',quiescent=False,review_threads=[],correction_count=0)
        issue('execute')
    elif kind=='resume':
        if a['phase']!='needs_input' or not a.get('quiescent') or not a.get('author_thread_id'):
            raise ServiceError('resume_fenced')
        a.update(phase='revising',quiescent=False,correction_count=0,execution_state='not_started')
        issue('revise',thread_id=a['author_thread_id'])
    elif kind=='pause':
        if a['phase'] in ('needs_reconciliation','accepted','needs_input'):raise ServiceError('pause_fenced')
        pause()
    elif kind=='disconnected':a['connection_state']='disconnected'
    elif kind=='approval':
        if a['phase'] not in ('executing','revising','reviewing') or a['execution_state'] not in ('not_started','running'):raise ServiceError('approval_fenced')
        a.update(paused_phase=a['phase'],phase='needs_input',quiescent=False)
    elif kind=='responded':
        if a['phase']!='needs_input' or a.get('quiescent') or not a.get('paused_phase'):raise ServiceError('response_fenced')
        a['phase']=a.pop('paused_phase')
    elif kind=='failed':
        a.update(phase='needs_reconciliation',execution_state='unknown',quiescent=False)
    elif kind=='quiescent':
        if a['phase']!='needs_input' or a.get('quiescent'):raise ServiceError('quiescence_fenced')
        a.update(quiescent=True,execution_state='stopped')
    elif kind=='saved_result':
        from ..delivery_policy import validate_receipt
        if a['phase']!='awaiting_merge':raise ServiceError('handoff_fenced')
        try:receipt=validate_receipt(event['receipt'],a.get('delivery_policy',{}),a['head_sha'],a['base_sha'])
        except ValueError:raise ServiceError('invalid_saved_result') from None
        a.update(phase='handoff',quiescent=True,saved_result=receipt)
    elif kind=='started':
        thread=identity(event['thread_id']);turn=identity(event['turn_id'])
        if a['phase'] not in ('executing','revising','reviewing'):raise ServiceError('start_fenced')
        if a['phase']=='reviewing':
            if thread==a.get('author_thread_id') or thread in a.get('review_threads',[]):raise ServiceError('reviewer_not_independent')
            a.setdefault('review_threads',[]).append(thread)
        elif a.get('author_thread_id') not in (None,thread):raise ServiceError('author_thread_changed')
        else:a['author_thread_id']=thread
        a.update(thread_id=thread,turn_id=turn,execution_state='running',connection_state='connected')
    elif kind=='merged':
        m=event['merge']
        if a['phase']!='awaiting_merge' or not isinstance(m,dict) or set(m)!={'repository','pr_number','head_sha','base_sha','main_sha'}:raise ServiceError('merge_fenced')
        if (m['head_sha'],m['base_sha'])!=(a['head_sha'],a['base_sha']) or type(m['pr_number']) is not int or m['pr_number']<1:raise ServiceError('merge_identity_mismatch')
        validate_source(dict(head_sha=m['main_sha'],base_sha=a['base_sha'],diff=''))
        a.update(phase='postmerge',**m)
    elif kind=='delivery_changed':
        if a['phase']!='awaiting_merge':raise ServiceError('delivery_change_fenced')
        new=event['base_sha'];validate_source(dict(base_sha=new,head_sha=a['head_sha'],diff=''))
        if new==a['base_sha']:raise ServiceError('base_unchanged')
        if a.get('correction_count',0)>=3:pause()
        else:
            update=dict(old_base_sha=a['base_sha'],new_base_sha=new)
            a.update(base_sha=new,phase='revising',correction_count=a.get('correction_count',0)+1,review=None)
            issue('revise',thread_id=a['author_thread_id'],update_base=update)
    elif kind=='completed':
        if a['phase'] not in ('executing','revising','reviewing') or a.get('execution_state')!='running':raise ServiceError('completion_fenced')
        if (event['thread_id'],event['turn_id'])!=(a.get('thread_id'),a.get('turn_id')):raise ServiceError('completion_identity_mismatch')
        if not isinstance(event['result'],str) or len(event['result'].encode('utf-8'))>32768:raise ServiceError('result_limit',400)
        a['execution_state']='completed'
        if a['phase']=='reviewing':
            verdict=validate_review(event['result'],a['source'],a['thread_id']);a['review']=verdict
            if verdict['verdict']=='approve':
                a['phase']='awaiting_merge';issue('deliver')
            elif a.get('correction_count',0)>=3:pause()
            else:
                a['correction_count']=a.get('correction_count',0)+1;a['phase']='revising'
                issue('revise',thread_id=a['author_thread_id'])
        else:
            source=validate_source(event['source'])
            if source['base_sha']!=a['base_sha']:raise ServiceError('source_base_changed')
            a.update(source=source,head_sha=source['head_sha'],phase='reviewing',execution_result=event['result'])
            issue('review')
    else:raise ServiceError('invalid_lifecycle_event',400)
    return [dict(kind='state',changes=a),*commands]


class LifecycleStore:
    def active_count(self,connector):
        return sum(1 for row in self.db.execute('SELECT data FROM attempts WHERE connector_id=?',(connector,))
                   if (a:=json.loads(row[0]))['phase'] not in ('accepted','handoff')
                   and not (a['phase']=='needs_input' and a.get('quiescent') is True))

    def lifecycle_commands(self,connector):
        identity(connector)
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute(
                "SELECT data FROM lifecycle_commands WHERE connector_id=? AND state='queued' ORDER BY rowid",(connector,))]

    def _native_lifecycle(self,data):
        # Existing fresh checks cover approval digest, owner, dependencies and metadata.
        return self.validate_execution(data['attempt_id'],data['connector_id'],lifecycle=True)

    def start_lifecycle(self,attempt,connector,base_sha):
        from ..connector.briefs import validate_source
        with self.lock:
            a=self.attempt(attempt,connector);self._native_lifecycle(a)
            validate_source(dict(base_sha=base_sha,head_sha=base_sha,diff=''))
            return self.record_lifecycle_event(dict(version=1,event_id=str(uuid.uuid4()),attempt_id=attempt,
                connector_id=connector,lifecycle=dict(kind='dispatch',base_sha=base_sha)),operator=True)

    def resume_lifecycle(self,attempt,connector):
        with self.lock:
            a=self.attempt(attempt,connector)
            if self.active_count(connector)>=self.max_active_tasks:raise ServiceError('connector_capacity')
            self._native_lifecycle(a)
            return self.record_lifecycle_event(dict(version=1,event_id=str(uuid.uuid4()),attempt_id=attempt,
                connector_id=connector,lifecycle=dict(kind='resume')),operator=True)

    def validate_lifecycle_command(self,key,connector):
        identity(key)
        with self.lock:
            row=self.db.execute("SELECT * FROM lifecycle_commands WHERE command_id=? AND connector_id=? AND state='queued'",(key,connector)).fetchone()
            if row is None:raise ServiceError('command_fenced')
            a=self.attempt(row['attempt_id'],connector);c=json.loads(row['data'])
            if c['kind']=='deliver':
                if a['phase'] not in ('awaiting_merge','postmerge') or a.get('active_command_id')!=key:raise ServiceError('delivery_fenced')
            elif c['kind'] not in ('respond','quiesce') and (a.get('active_command_id')!=key or a['phase'] not in ('executing','revising','reviewing') or a['execution_state']!='not_started'):
                raise ServiceError('command_superseded')
            if c['kind']=='respond' and (a['phase']!='needs_input' or a.get('quiescent')):raise ServiceError('response_fenced')
            if c['kind']=='quiesce' and a['phase']!='needs_input':raise ServiceError('quiescence_fenced')
            if c['kind']=='deliver':
                self.validate_execution(a['attempt_id'],a['connector_id'],delivery=True);self.reserve_delivery(a)
            elif c['kind']!='quiesce':self._native_lifecycle(a)
            return a

    def respond_decision(self,key,connector,answer):
        from .store import encoded,utc
        identity(key)
        if answer not in ('approve','decline'):raise ServiceError('invalid_answer',400)
        with self.lock:
            row=self.db.execute('SELECT * FROM decisions WHERE decision_id=? AND connector_id=?',(key,connector)).fetchone()
            if row is None:raise ServiceError('decision_not_found',404)
            d=json.loads(row['data'])
            if d.get('status')!='pending':raise ServiceError('decision_already_answered')
            a=self.attempt(d['attempt_id'],connector)
            if a['phase']!='needs_input' or a.get('quiescent') or not a.get('paused_phase'):raise ServiceError('response_fenced')
            self._native_lifecycle(a)
            c=dict(version=1,kind='respond',command_id=str(uuid.uuid4()),attempt_id=a['attempt_id'],project_id=a['project_id'],
                   base_sha=a['base_sha'],decision_id=key,target_command_id=d['command_id'],request=d['request'],answer=answer)
            d.update(status='response_queued',answer=answer,response_command_id=c['command_id'])
            with self.db:
                self.db.execute('UPDATE decisions SET data=? WHERE decision_id=?',(encoded(d),key))
                self.db.execute('INSERT INTO lifecycle_commands VALUES (?,?,?,?,?)',(c['command_id'],a['attempt_id'],connector,'queued',encoded(c)))
            return d

    def record_lifecycle_event(self,event,*,operator=False):
        from .store import encoded,utc
        fields={'version','event_id','attempt_id','connector_id','lifecycle'}
        if not isinstance(event,dict) or set(event)!=fields or type(event['version']) is not int or event['version']!=1:
            raise ServiceError('invalid_event',400)
        identity(event['event_id']);identity(event['connector_id']);payload=event['lifecycle']
        if not isinstance(payload,dict):raise ServiceError('invalid_lifecycle_event',400)
        kind=payload.get('kind')
        expected={'dispatch':{'base_sha'},'resume':set(),'pause':set(),'disconnected':set(),'failed':{'command_id'},
                  'saved_result':{'command_id','receipt'},'merged':{'command_id','merge'},'delivery_changed':{'command_id','base_sha'},'quiescent':{'command_id'},'started':{'command_id','thread_id','turn_id'},
                  'completed':{'command_id','thread_id','turn_id','result'},
                  'approval':{'command_id','decision_id','request'},'responded':{'command_id'}}
        if kind not in expected or set(payload)!={'kind'}|expected[kind]|({'source'} if kind=='completed' and 'source' in payload else set()):
            raise ServiceError('invalid_lifecycle_fields',400)
        if kind in ('dispatch','resume') and not operator:raise ServiceError('operator_command_required',403)
        fingerprint=encoded(event)
        with self.lock:
            a=self.attempt(event['attempt_id'],event['connector_id'])
            previous=self.db.execute('SELECT * FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
            if previous:
                if previous['fingerprint']!=fingerprint:raise ServiceError('event_conflict')
                return json.loads(previous['outcome'])
            if kind!='dispatch' and not a.get('managed'):raise ServiceError('not_managed')
            if a.get('delivery_policy')!=self.delivery_policies.get(a['project_id']):raise ServiceError('delivery_policy_changed')
            command=None
            if 'command_id' in payload:
                row=self.db.execute('SELECT * FROM lifecycle_commands WHERE command_id=?',(identity(payload['command_id']),)).fetchone()
                if row is None or row['attempt_id']!=a['attempt_id'] or row['connector_id']!=event['connector_id']:
                    raise ServiceError('command_fenced')
                if row['state']=='superseded' and kind in ('started','completed','approval','failed'):
                    # Known cancelled command: durably acknowledge its late notification,
                    # never let it block the ordered outbox's stop acknowledgement.
                    with self.db:self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event['event_id'],fingerprint,a['attempt_id'],encoded(a),utc()))
                    return a
                if row['state']!='queued':raise ServiceError('command_fenced')
                command=json.loads(row['data'])
                if kind=='quiescent':
                    if command['kind']!='quiesce':raise ServiceError('quiescence_fenced')
                elif kind=='responded' or (kind=='failed' and command['kind']=='respond'):
                    if command['kind']!='respond':raise ServiceError('response_fenced')
                elif command['command_id']!=a.get('active_command_id'):raise ServiceError('command_superseded')
                if kind=='merged' and (command['kind']!='deliver' or not isinstance(payload['merge'],dict) or payload['merge'].get('repository')!=self.delivery_projects.get(a['project_id'])):raise ServiceError('merge_fenced')
                if kind=='delivery_changed' and command['kind']!='deliver':raise ServiceError('delivery_change_fenced')
                if kind=='saved_result' and command['kind']!='deliver':raise ServiceError('handoff_fenced')
                if kind=='started' and a.get('execution_state')=='running':raise ServiceError('already_started')
            decision=None
            if kind=='approval':
                request=payload['request'];identity(payload['decision_id'])
                if (not isinstance(request,dict) or set(request)!={'method','request_id','question'}
                        or request['method'] not in ('item/commandExecution/requestApproval','item/fileChange/requestApproval')
                        or type(request['request_id']) not in (str,int) or isinstance(request['request_id'],bool)
                        or not isinstance(request['question'],str) or not 1<=len(request['question'])<=4096):
                    raise ServiceError('unsupported_approval',400)
                if self.db.execute('SELECT 1 FROM decisions WHERE decision_id=?',(payload['decision_id'],)).fetchone():raise ServiceError('decision_conflict')
                decision=dict(version=1,decision_id=payload['decision_id'],connector_id=event['connector_id'],attempt_id=a['attempt_id'],
                              command_id=command['command_id'],request=request,question=request['question'],status='pending')
            if kind=='dispatch':a['base_sha']=payload['base_sha']
            if kind=='started' and a['phase']=='reviewing':
                for row in self.db.execute('SELECT data FROM attempts'):
                    prior=json.loads(row[0])
                    if payload['thread_id']==prior.get('author_thread_id') or payload['thread_id'] in prior.get('review_threads',[]):
                        raise ServiceError('reviewer_not_new')
            actions=advance(a,payload,{});a=actions[0]['changes']
            outgoing=[]
            for action in actions[1:]:
                action=dict(action,version=1,command_id=str(uuid.uuid4()),attempt_id=a['attempt_id'],project_id=a['project_id'],base_sha=a['base_sha'])
                if action['kind']=='deliver':
                    action['attempt']=dict(copy.deepcopy(a),approved_task=self._approved_task(a['project_id'],a['bead_id']))
                elif action['kind']!='quiesce':
                    task=self._approved_task(a['project_id'],a['bead_id'])
                    source=a.get('source',dict(base_sha=a['base_sha'],head_sha=a['base_sha'],diff=''))
                    brief=build_brief(task,'reviewer' if action['kind']=='review' else 'executor',source)
                    action['input']=brief['input'];action['source']=source
                    if action['kind']=='revise':
                        action['input']['text']+='\nAddress independent findings:\n'+encoded((a.get('review') or {}).get('findings',[]))
                        if action.get('update_base'):action['input']['text']+='\nUpstream main changed. Resolve the trusted connector prepared merge (including any conflicts) in this SAME author worktree, commit, and repeat checks. New base: '+a['base_sha']
                outgoing.append(action);a['active_command_id']=action['command_id']
                if action['kind'] not in ('quiesce','deliver'):a['execution_state']='not_started'
            with self.db:
                self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event['event_id'],fingerprint,a['attempt_id'],encoded(a),utc()))
                self._save_attempt(a)
                if command and kind in ('completed','quiescent','failed','responded','delivery_changed','saved_result'):
                    self.db.execute("UPDATE lifecycle_commands SET state='acknowledged' WHERE command_id=?",(command['command_id'],))
                if decision:self.db.execute('INSERT INTO decisions VALUES (?,?,?,?,?)',
                    (decision['decision_id'],event['connector_id'],a['attempt_id'],encoded(decision),utc()))
                if kind=='responded':
                    row=self.db.execute('SELECT data FROM decisions WHERE decision_id=?',(command['decision_id'],)).fetchone()
                    d=json.loads(row[0]);d['status']='answered'
                    self.db.execute('UPDATE decisions SET data=? WHERE decision_id=?',(encoded(d),command['decision_id']))
                if kind=='delivery_changed':self.db.execute('DELETE FROM acceptance_repository WHERE attempt_id=?',(a['attempt_id'],))
                if kind=='pause':self.db.execute("UPDATE lifecycle_commands SET state='superseded' WHERE attempt_id=? AND state='queued'",(a['attempt_id'],))
                for c in outgoing:self.db.execute('INSERT INTO lifecycle_commands VALUES (?,?,?,?,?)',
                    (c['command_id'],a['attempt_id'],event['connector_id'],'queued',encoded(c)))
            return a
