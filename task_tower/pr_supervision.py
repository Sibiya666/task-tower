"""Bounded private lifecycle telemetry; never review or publication authority."""
import json
import os
import threading
import time
import uuid
from datetime import datetime,timezone
from .pr_policy import identifier,integer,text,HASH
from .executor_profiles import profile_fingerprint


def _utcnow():return datetime.now(timezone.utc)


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('Duplicate lifecycle key')
        result[key]=value
    return result


def _date(value):
    if not isinstance(value,str):raise ValueError('Invalid lifecycle date')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds()!=0:raise ValueError('Non-UTC lifecycle date')
    return result


class PRMonitor:
    """Snapshot genuine local limits once; polling only uses clocks and bytes."""
    def __init__(self):raise TypeError('Use PRMonitor.from_context')

    @classmethod
    def from_context(cls,context,*,owner_id):
        from .pr_context import PRHostContext
        if type(context) is not PRHostContext:raise ValueError('Actual private host context required')
        identifier(owner_id);loaded=context._fresh_inputs();policy=loaded['policy']
        m=object.__new__(cls)
        m.session_id=str(uuid.uuid4());m.owner_id=owner_id;m._parent_pid=os.getpid()
        m._pid=None;m._sequence=0;m._buffer=b'';m._reason=None;m._lock=threading.Lock()
        m._hello=False;m._ended=False;m._finished=False;m._phase=None;m._role=None
        m._last_action=None;m._last=None;m._wall=None;m._deadline=None;m._tasks={}
        m._stop_deadline=None;m._kill_after=None
        m._bucket=None;m._bucket_count=0;m.report=None
        m._frame_rate=max(100,policy['max_prs_per_tick']*6+32)
        m._task_timeout=policy['task_timeout_seconds'];m._action_timeout=policy['reviewer_timeout_seconds']
        m._idle_timeout=policy['interval_seconds']+5
        m._preflight_timeout=min(120,max(10,policy['request_timeout_seconds']*2));m._preflight_available=True
        m._references={(p['repository'].casefold(),t['pr_number']):frozenset((t['reviewer_profile'],t['postmerge_profile']))
            for p in policy['projects'] for t in p['tasks']}
        m._profiles={name:(profile_fingerprint(p),p['timeout_seconds']) for name,p in loaded['executor']['profiles'].items()}
        return m

    @property
    def reason(self):
        with self._lock:return self._reason

    @property
    def cleanup_deadline(self):
        with self._lock:return self._stop_deadline

    def request_stop(self):
        with self._lock:
            if self._stop_deadline is None:
                now=time.monotonic();self._stop_deadline=now+5;self._kill_after=now+.25

    def _fail(self,reason='channel_unverified'):
        if self._reason is None:self._reason=reason

    def _tick(self):
        now=time.monotonic();wall=_utcnow()
        if self._last is not None and (now<self._last or wall<self._wall):raise ValueError('Lifecycle clock reversed')
        self._last=now;self._wall=wall
        if self._deadline is not None and now>=self._deadline:raise ValueError('Lifecycle phase expired')
        if self._phase is not None:
            task=self._tasks.get(self._phase['reference'])
            if task is not None and not task.get('fenced') and wall>=task['deadline']:raise ValueError('Original UTC deadline expired')
        return now,wall

    def started(self,pid):
        with self._lock:
            try:
                if self._pid is not None or os.getpid()!=self._parent_pid:raise ValueError('Foreign lifecycle start')
                self._pid=integer(pid,1,2**63-1)
                now,_=self._tick();self._deadline=now+10
                pending=self._buffer;self._buffer=b''
                if pending:self._consume(pending)
            except Exception:self._fail()

    def feed(self,chunk):
        with self._lock:
            if self._reason is not None:return
            try:
                if os.getpid()!=self._parent_pid or type(chunk) is not bytes or not 0<len(chunk)<=65536:
                    raise ValueError('Invalid lifecycle chunk')
                if self._pid is None:
                    if len(self._buffer)+len(chunk)>65536:raise ValueError('Prestart overflow')
                    self._buffer+=chunk;return
                self._consume(chunk)
            except Exception:self._fail()

    def _consume(self,chunk):
        data=self._buffer+chunk;self._buffer=b''
        while b'\n' in data:
            line,data=data.split(b'\n',1)
            if not line or len(line)>4095:raise ValueError('Invalid lifecycle frame length')
            frame=json.loads(line.decode('utf-8'),object_pairs_hook=_pairs,
                parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Invalid JSON constant')))
            self._frame(frame)
        if len(data)>4095:raise ValueError('Unfinished lifecycle frame overflow')
        self._buffer=data

    def _frame(self,frame):
        now,wall=self._tick()
        if self._ended or self._finished or not isinstance(frame,dict):raise ValueError('Ended lifecycle')
        common={'version','session_id','owner_id','pid','sequence','event'}
        fields={'hello':set(),'idle':set(),'end':set(),'report':{'report'},
            'fence':{'repository','pr_number','input_sha256'},
            'task':{'repository','pr_number','input_sha256','admitted_utc','deadline_utc'},
            'phase_start':{'action_id','kind','repository','pr_number','input_sha256'},
            'phase_end':{'action_id'},'role_start':{'action_id','profile_id','profile_sha256'},'role_end':{'action_id'}}
        event=frame.get('event')
        if event not in fields or set(frame)!=common|fields[event]:raise ValueError('Invalid closed lifecycle frame')
        if (type(frame['version']) is not int or frame['version']!=1 or frame['session_id']!=self.session_id
                or frame['owner_id']!=self.owner_id or type(frame['pid']) is not int or frame['pid']!=self._pid
                or type(frame['sequence']) is not int or frame['sequence']!=self._sequence+1 or frame['sequence']>=2**63):
            raise ValueError('Wrong lifecycle domain/sequence')
        bucket=int(now)
        if bucket!=self._bucket:self._bucket=bucket;self._bucket_count=0
        self._bucket_count+=1
        if self._bucket_count>self._frame_rate:raise ValueError('Lifecycle rate exceeded')
        self._sequence=frame['sequence']
        if not self._hello:
            if event!='hello':raise ValueError('Missing lifecycle hello')
            self._hello=True;self._deadline=now+5;return
        if event=='hello':raise ValueError('Repeated lifecycle hello')
        if event=='report':
            if self._phase is not None:raise ValueError('Report during action')
            value=frame['report']
            allowed={'status','reason','action','repository','pr_number','issue','issue_id','task_id','head_sha','base_sha',
                'input_sha256','pr_receipt_sha256','postmerge_receipt_sha256','review_attempts','postmerge_attempts','effect_count'}
            if not isinstance(value,dict) or not {'status','reason','action'}<=set(value) or set(value)-allowed:
                raise ValueError('Invalid public host report')
            from .pr_journal import SEQUENCE,SIDE
            if value['status'] not in set(SEQUENCE)|SIDE|{'idle'}:raise ValueError('Invalid report status')
            import re
            for key in ('reason','action'):
                if value[key] is not None and (not isinstance(value[key],str) or re.fullmatch('[a-z][a-z0-9_]{0,99}',value[key]) is None):
                    raise ValueError('Invalid report code')
            for key,item in value.items():
                if key.endswith('_sha') or key.endswith('_sha256'):
                    if item is not None:text(item,HASH if key.endswith('_sha256') else '[a-f0-9]{40}')
                elif key in ('pr_number','issue','issue_id'):integer(item)
                elif key in ('review_attempts','postmerge_attempts','effect_count'):integer(item,0,2**63-1)
            if 'repository' in value and (value['repository'],value.get('pr_number')) not in self._references:
                raise ValueError('Foreign host report')
            if 'task_id' in value:
                from .pr_policy import TASK
                text(value['task_id'],TASK)
            self.report=dict(value);return
        if event=='fence':
            ref=(frame['repository'],integer(frame['pr_number']));text(frame['input_sha256'],HASH)
            if self._phase is not None or ref not in self._references:raise ValueError('Invalid task fence')
            task=self._tasks.get(ref)
            if task is not None and task['input_sha256']!=frame['input_sha256']:raise ValueError('Foreign fenced input')
            self._tasks[ref]=dict(input_sha256=frame['input_sha256'],fenced=True);return
        if event=='task':
            ref=(frame['repository'],integer(frame['pr_number']))
            if self._phase is None or self._phase['reference']!=ref or self._role is not None:
                raise ValueError('Task outside original action')
            text(frame['input_sha256'],HASH)
            admitted=_date(frame['admitted_utc']);deadline=_date(frame['deadline_utc'])
            if (admitted>wall or (deadline-admitted).total_seconds()!=self._task_timeout or deadline<=wall):
                raise ValueError('Invalid original lifecycle budget')
            original=self._tasks.get(ref)
            if original is not None and original.get('fenced'):raise ValueError('Fenced lifecycle task')
            if original is None:
                original=dict(admitted=admitted,deadline=deadline,monotonic_deadline=now+(deadline-wall).total_seconds())
                self._tasks[ref]=original
            elif (original['admitted'],original['deadline'])!=(admitted,deadline):raise ValueError('Renewed lifecycle budget')
            original['input_sha256']=frame['input_sha256'];self._phase['input_sha256']=frame['input_sha256']
            self._phase['deadline']=min(self._phase['deadline'],original['monotonic_deadline'])
            self._deadline=self._phase['deadline'];return
        if event=='phase_start':
            identifier(frame['action_id'])
            preflight=frame['kind']=='preflight';polling=frame['kind'] in ('poll','preflight')
            ref=None if polling else (frame['repository'],integer(frame['pr_number']))
            if (polling and any(frame[k] is not None for k in ('repository','pr_number','input_sha256'))
                    or self._phase is not None or not polling and ref not in self._references
                    or frame['kind'] not in ('source','poll','preflight') or frame['action_id']==self._last_action
                    or preflight and not self._preflight_available):
                raise ValueError('Invalid lifecycle action')
            self._preflight_available=False
            task=self._tasks.get(ref)
            active=task is not None and not task.get('fenced')
            if frame['input_sha256']!=(task['input_sha256'] if active else None):raise ValueError('Foreign lifecycle input')
            deadline=now+(self._preflight_timeout if preflight else self._action_timeout)
            if active:deadline=min(deadline,task['monotonic_deadline'])
            self._phase=dict(action_id=frame['action_id'],reference=ref,input_sha256=frame['input_sha256'],deadline=deadline)
            self._deadline=deadline;self._tick();return
        if event in ('phase_end','role_start','role_end'):
            if self._phase is None or frame['action_id']!=self._phase['action_id']:raise ValueError('Foreign lifecycle phase')
            if event=='role_start':
                ref=self._phase['reference'];profile=frame['profile_id']
                if (self._role is not None or ref not in self._tasks or self._tasks[ref].get('fenced') or profile not in self._references[ref]
                        or profile not in self._profiles or frame['profile_sha256']!=self._profiles[profile][0]):
                    raise ValueError('Unbound lifecycle role')
                self._role=profile;self._deadline=min(self._phase['deadline'],now+self._profiles[profile][1]);return
            if event=='role_end':
                if self._role is None:raise ValueError('Missing lifecycle role')
                self._role=None;self._deadline=self._phase['deadline'];return
            if self._role is not None:raise ValueError('Action ended during role')
            self._last_action=self._phase['action_id'];self._phase=None;self._deadline=now+5;return
        if self._phase is not None:raise ValueError('Idle/end during active action')
        if event=='idle':self._deadline=now+self._idle_timeout;return
        if event=='end':self._ended=True;self._deadline=now+5;return
        raise ValueError('Unsupported lifecycle event')

    def cancelled(self):
        with self._lock:
            try:
                if os.getpid()!=self._parent_pid:raise ValueError('Foreign monitor')
                self._tick()
                if (self._kill_after is not None and not self._ended and not self._finished
                        and time.monotonic()>=self._kill_after):self._fail('stop_requested')
            except Exception:self._fail('lifecycle_timeout_or_clock')
            return self._reason is not None

    def finished(self,exit_code,eof_confirmed=True):
        with self._lock:
            try:
                self._tick()
                if (eof_confirmed is not True or type(exit_code) is not int or exit_code!=0 or not self._hello or not self._ended
                        or self._phase is not None or self._role is not None or self._buffer):
                    raise ValueError('Unverified lifecycle EOF')
                self._finished=True;self._deadline=None
            except Exception:self._fail()


class _Wire:
    """Fixed host's noninherited writer; ordinary stdout is not this channel."""
    def __init__(self,descriptor,session_id,owner_id):
        identifier(session_id);identifier(owner_id)
        os.set_inheritable(descriptor,False)
        self.descriptor=descriptor;self.session_id=session_id;self.owner_id=owner_id;self.sequence=0

    def send(self,event,**fields):
        self.sequence+=1
        value=dict(version=1,session_id=self.session_id,owner_id=self.owner_id,pid=os.getpid(),
            sequence=self.sequence,event=event,**fields)
        raw=json.dumps(value,separators=(',',':'),ensure_ascii=True).encode()+b'\n'
        if len(raw)>4096:raise ValueError('Oversize host lifecycle frame')
        while raw:
            count=os.write(self.descriptor,raw)
            if count<=0:raise OSError('Closed lifecycle channel')
            raw=raw[count:]


class PRProgress:
    """Fixed host telemetry obtained from its actual controller, not JSON."""
    def __init__(self):raise TypeError('Use PRProgress.from_controller')

    @classmethod
    def from_controller(cls,controller,wire,stop_file):
        from .pr_worker import Controller
        if type(controller) is not Controller or type(wire) is not _Wire or wire.owner_id!=controller.owner_id:
            raise ValueError('Actual original host controller required')
        loaded=controller.context._fresh_inputs()
        result=object.__new__(cls)
        result.context=controller.context;result.journal=controller.journal;result.owner_id=controller.owner_id
        result._pid=os.getpid();result._wire=wire;result._phase=None;result._reference=None
        result._known={};result._role=False;result._profiles=loaded['executor']['profiles'];result._stop_file=stop_file
        result._references=frozenset(controller.references)
        result.interval_seconds=loaded['policy']['interval_seconds']
        result._allowed_profiles={(p['repository'].casefold(),t['pr_number']):frozenset((t['reviewer_profile'],t['postmerge_profile']))
            for p in loaded['policy']['projects'] for t in p['tasks']}
        return result

    def _scope(self):
        if self._pid!=os.getpid() or self.journal._active!=self.owner_id or self.context._closed:
            raise ValueError('Original lifecycle host retired')

    def _start(self,reference):
        self._scope()
        if self._phase is not None:raise ValueError('Nested host action')
        known=self._known.get(reference)
        if known is not None and not known.get('fenced') and _utcnow()>=_date(known['deadline_utc']):
            self._fence(reference,known['input_sha256'])
            known=self._known[reference]
        self._phase=str(uuid.uuid4());self._reference=reference
        self._wire.send('phase_start',action_id=self._phase,kind='poll' if reference is None else 'source',
            repository=None if reference is None else reference[0],pr_number=None if reference is None else reference[1],
            input_sha256=None if known is None or known.get('fenced') else known['input_sha256'])

    def poll(self):self._start(None)

    def begin(self,repository,pr_number):
        reference=(repository.casefold(),pr_number)
        if reference not in self._references:raise ValueError('Foreign lifecycle reference')
        self._start(reference)

    def admitted(self,repository,pr_number):
        self._scope();reference=(repository.casefold(),pr_number)
        if self._reference!=reference or self._phase is None or self._role:raise ValueError('Admission outside host action')
        if self._known.get(reference,{}).get('fenced'):raise ValueError('Original lifecycle task remains fenced')
        row=self.journal.get(repository,pr_number)
        if (row is None or row['owner_id']!=self.owner_id or row['owner_pid']!=os.getpid()
                or row['cancel_requested'] or _utcnow()>=_date(row['deadline_utc'])):
            raise ValueError('Original admitted lifecycle task fenced')
        values={k:row[k] for k in ('repository','pr_number','input_sha256','admitted_utc','deadline_utc')}
        values['repository']=reference[0]
        self._known[reference]=values;self._wire.send('task',**values)

    def start_role(self,profile):
        self._scope()
        if self._phase is None or self._reference is None or self._role:raise ValueError('Role outside host action')
        self.admitted(*self._reference)
        matches=[name for name,p in self._profiles.items() if name in self._allowed_profiles[self._reference]
            and profile_fingerprint(p)==profile_fingerprint(profile)]
        if not matches:raise ValueError('Unknown lifecycle role profile')
        self._wire.send('role_start',action_id=self._phase,profile_id=sorted(matches)[0],profile_sha256=profile_fingerprint(profile))
        self._role=True

    def end_role(self,process):
        self._scope()
        if not self._role or not isinstance(process,dict) or process.get('cleanup_confirmed') is not True:
            raise ValueError('Role cleanup not confirmed')
        self._wire.send('role_end',action_id=self._phase);self._role=False

    def _fence(self,reference,input_sha256):
        self._wire.send('fence',repository=reference[0],pr_number=reference[1],input_sha256=input_sha256)
        self._known[reference]=dict(input_sha256=input_sha256,fenced=True)

    def end(self):
        self._scope()
        if self._phase is None or self._role:raise ValueError('Host action cleanup not confirmed')
        reference=self._reference
        row=None if reference is None else self.journal.get(*reference)
        self._wire.send('phase_end',action_id=self._phase);self._phase=None;self._reference=None
        if row is not None and (row['owner_id']!=self.owner_id or row['cancel_requested']
                or row['state'] in ('completed','cancelled','timed_out','unknown') or _utcnow()>=_date(row['deadline_utc'])):
            self._fence(reference,row['input_sha256'])

    def cancelled(self):return self._stop_file.exists()


def lifecycle_for(context):
    progress=getattr(context,'_lifecycle',None)
    if progress is not None:
        if type(progress) is not PRProgress or progress.context is not context:raise ValueError('Foreign lifecycle context')
        progress._scope()
    return progress


def supervise(inputs,*,once,stop_requested=None):
    """One fixed persistent host process. The parent never owns PR effects."""
    import sys
    import signal
    from pathlib import Path
    from .pr_context import PRPrivateInputs,PRHostContext
    from .project_connections import safe_config_path
    from .executor_profiles import child_environment
    from .processes import run_command
    if type(inputs) is not PRPrivateInputs or type(once) is not bool:
        raise ValueError('Actual private PR launch inputs required')
    if stop_requested is not None and not callable(stop_requested):raise ValueError('Invalid supervisor stop callback')
    owner=str(uuid.uuid4())
    with PRHostContext.from_inputs(inputs) as context:
        monitor=PRMonitor.from_context(context,owner_id=owner)
        input_manifest_sha256=profile_fingerprint(context.private_input_provenance)
        directory=Path(context.private_input_provenance['artifact_namespace'])/'sessions'/monitor.session_id
        safe_config_path(directory/'.session-private-path-check')
        directory.mkdir(parents=True,exist_ok=False)
    capture=directory/'capture';capture.mkdir();stop_file=directory/'stop'
    reference=sorted(monitor._references)[0]
    argv=[str(Path(sys.executable).resolve()),'-B','-m','task_tower._pr_host',
        '--connections',str(inputs.connections_path),'--config',str(inputs.policy_path),'--journal',str(inputs.journal_path),
        '--owner-id',owner,'--session-id',monitor.session_id,'--stop-file',str(stop_file),
        '--input-manifest-sha256',input_manifest_sha256,
        '--first-repository',reference[0],'--first-pr',str(reference[1])]
    if inputs.pipeline_config_path is not None:argv+=['--pipeline-config',str(inputs.pipeline_config_path)]
    if once:argv+=['--once']
    stopped=threading.Event();handlers={}
    if threading.current_thread() is threading.main_thread():
        for name in ('SIGINT','SIGTERM'):
            signum=getattr(signal,name,None)
            if signum is not None:
                handlers[signum]=signal.getsignal(signum);signal.signal(signum,lambda *_:stopped.set())
    def cancelled():
        requested=stopped.is_set() or (stop_requested is not None and stop_requested())
        if requested and not stop_file.exists():
            with stop_file.open('xb') as stream:stream.write(b'stop\n')
        if requested:monitor.request_stop()
        return False  # The typed monitor bounds the short clean-stop grace.
    try:
        result=run_command(argv,Path(__file__).resolve().parent.parent,None,env=child_environment(os.environ),
            cancel_requested=cancelled,lifecycle_monitor=monitor,
            capture=dict(directory=capture,max_bytes_per_stream=1048576))
    finally:
        for signum,handler in handlers.items():signal.signal(signum,handler)
    healthy=(result['status']=='passed' and result['exit_code']==0 and result['started'] is True
        and result['cleanup_confirmed'] is True and monitor.reason is None
        and all(result.get(s+'_tail_unknown') is False for s in ('stdout','stderr')))
    report=monitor.report
    status=('needs_input' if not healthy or once and report is None else report['status'] if once else 'stopped')
    reason=('pr_host_unverified' if not healthy or once and report is None else report['reason'] if once else None)
    return dict(status=status,reason=reason,report=report,session_id=monitor.session_id,owner_id=owner,
        cleanup_confirmed=result['cleanup_confirmed'],owner_retired=healthy)
