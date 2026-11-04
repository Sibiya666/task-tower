"""Source-only host channel monitor. No claim, task or role authority exists."""
import json
import os
import threading
import time
import uuid
from .group_registration import RegistrationContext


def _uuid(value):
    if not isinstance(value,str) or str(uuid.UUID(value))!=value:raise ValueError('Invalid host UUID')
    return value


def _integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('Invalid host integer')
    return value


def _pairs(rows):
    result={}
    for key,value in rows:
        if key in result:raise ValueError('Duplicate channel key')
        result[key]=value
    return result


class GroupMonitor:
    """Actual registered parent factory; source-only until coupled claims ship."""
    def __init__(self):raise TypeError('Use GroupMonitor.from_registration')

    @classmethod
    def from_registration(cls,registration,*,owner_id):
        from .group_resources import ResourceContext
        if type(registration) is not RegistrationContext:raise ValueError('Actual registration required')
        _uuid(owner_id);registration.revalidate()
        ResourceContext.from_registration(registration)._snapshot()
        monitor=object.__new__(cls)
        monitor.session_id=str(uuid.uuid4());monitor.owner_id=owner_id
        monitor._parent_pid=os.getpid();monitor._pid=None;monitor._sequence=0
        monitor._lock=threading.Lock();monitor._buffer=b'';monitor._reason=None
        monitor._deadline=None;monitor._last=None;monitor._phase=None;monitor._phases=set()
        monitor._bucket=None;monitor._bucket_count=0;monitor._ended=False;monitor._finished=False
        monitor._policy_sha256=registration.policy['policy_sha256']
        monitor._installation_id=registration.policy['installation_id']
        monitor._source_ceiling=registration.deadline
        registration.revalidate()
        return monitor

    @property
    def reason(self):
        with self._lock:return self._reason

    def _fail(self,reason='channel_unverified'):
        if self._reason is None:self._reason=reason

    def _check_time(self,now):
        if self._last is not None and now<self._last:self._fail('clock_uncertain')
        self._last=now
        if self._deadline is not None and now>=self._deadline:self._fail('phase_timeout')

    def started(self,pid):
        with self._lock:
            if self._pid is not None or os.getpid()!=self._parent_pid:
                self._fail();return
            self._pid=_integer(pid,1,2**63-1)
            now=time.monotonic();self._last=now;self._deadline=min(now+10,self._source_ceiling)
            pending=self._buffer;self._buffer=b''
            if pending:self._consume(pending)

    def feed(self,chunk):
        with self._lock:
            if self._reason is not None:return
            try:
                if type(chunk) is not bytes or not 0<len(chunk)<=65536:raise ValueError('Invalid chunk')
                if os.getpid()!=self._parent_pid:raise ValueError('Foreign monitor process')
                if self._pid is None:
                    if len(self._buffer)+len(chunk)>4095:raise ValueError('Prestart overflow')
                    self._buffer+=chunk;return
                self._consume(chunk)
            except Exception:self._fail()

    def _consume(self,chunk):
        try:
            data=self._buffer+chunk;self._buffer=b''
            while b'\n' in data:
                line,data=data.split(b'\n',1)
                if not line or len(line)>4095:raise ValueError('Invalid frame length')
                frame=json.loads(line.decode('utf-8'),object_pairs_hook=_pairs,
                    parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Invalid JSON constant')))
                self._frame(frame)
                if self._reason is not None:return
            if len(data)>4095:raise ValueError('Unfinished frame overflow')
            self._buffer=data
        except Exception:self._fail()

    def _frame(self,frame):
        now=time.monotonic();self._check_time(now)
        if self._reason is not None:return
        common={'version','domain','session_id','owner_id','pid','sequence','event'}
        if not isinstance(frame,dict) or not common<=set(frame):raise ValueError('Missing host fields')
        if (type(frame['version']) is not int or frame['version']!=1 or frame['domain']!='groups'
                or frame['session_id']!=self.session_id or frame['owner_id']!=self.owner_id
                or _integer(frame['pid'],1,2**63-1)!=self._pid
                or _integer(frame['sequence'],1,2**63-1)!=self._sequence+1 or self._ended):
            raise ValueError('Host session mismatch')
        if self._sequence>=1000000:raise ValueError('Session frame overflow')
        bucket=int(now)
        if bucket!=self._bucket:self._bucket=bucket;self._bucket_count=0
        self._bucket_count+=1
        if self._bucket_count>100:raise ValueError('Channel rate exceeded')
        event=frame['event']
        if self._sequence==0:
            if event!='hello' or set(frame)!=common:raise ValueError('Missing hello')
            self._deadline=min(now+5,self._source_ceiling)
        elif event=='idle':
            raise ValueError('Persistent worker consumer unavailable')
        elif event in ('phase_start','phase_end'):
            fields={'phase_id','phase_kind','task_key','action_id','member','member_sha256','profile_sha256'}
            if set(frame)!=common|fields|({'requested_seconds'} if event=='phase_start' else set()):raise ValueError('Invalid phase shape')
            _uuid(frame['phase_id'])
            if (frame['phase_kind']!='source' or frame['task_key'] is not None or frame['action_id'] is not None
                    or frame['member']!='collect_source' or frame['member_sha256'] is not None or frame['profile_sha256'] is not None):
                raise ValueError('Claimed task/role consumer unavailable')
            identity={key:frame[key] for key in fields}
            if event=='phase_start':
                if self._phase is not None or frame['phase_id'] in self._phases or len(self._phases)>=65536:raise ValueError('Consumed phase')
                self._phase=identity;self._phases.add(frame['phase_id'])
                self._deadline=min(now+_integer(frame['requested_seconds'],1,60),self._source_ceiling)
            else:
                if self._phase!=identity:raise ValueError('Foreign phase end')
                self._phase=None;self._deadline=min(now+5,self._source_ceiling)
        elif event=='session_end':
            if set(frame)!=common or self._phase is not None:raise ValueError('Invalid session end')
            self._ended=True;self._deadline=min(now+5,self._source_ceiling)
        else:raise ValueError('Unsupported lifecycle event')
        self._sequence+=1

    def cancelled(self):
        with self._lock:
            if os.getpid()!=self._parent_pid:self._fail()
            if self._pid is not None and not self._finished:self._check_time(time.monotonic())
            return self._reason is not None

    def finished(self,exit_code,eof_confirmed):
        with self._lock:
            self._check_time(time.monotonic())
            if self._buffer or not self._ended or exit_code!=0 or eof_confirmed is not True:self._fail()
            self._finished=True


def observe_source(registration):
    """Run the fixed read-only collector inside its original hard budget.

    The returned observation is diagnostic only. No graph/resource cache or
    admission crosses the process boundary and no runnable claim is created.
    """
    import sys
    from pathlib import Path
    from .executor_profiles import child_environment
    from .project_connections import safe_config_path
    from .executor import _paths
    from .processes import run_command
    if type(registration) is not RegistrationContext:raise ValueError('Actual source registration required')
    registration.revalidate()
    locators=(registration.groups_path,registration.connections_path,registration.pipeline_path,registration.executor_path)
    if any(path not in registration._sources for path in locators):raise ValueError('Original private source locators required')
    monitor=GroupMonitor.from_registration(registration,owner_id=str(uuid.uuid4()))
    directory=Path(str(registration.journal.path)+'.source-probes')/monitor.session_id
    sentinel=directory/'.source-private-path-check'
    _paths([sentinel],registration.connections)
    safe_config_path(sentinel)
    directory.mkdir(parents=True,exist_ok=False)
    capture=directory/'capture';capture.mkdir()
    argv=[str(Path(sys.executable).resolve()),'-B','-m','task_tower._group_source',
        '--groups-config',str(registration.groups_path),'--connections',str(registration.connections_path),
        '--pipeline-config',str(registration.pipeline_path),'--executor-config',str(registration.executor_path),
        '--journal',str(registration.journal.path),'--owner-id',monitor.owner_id,'--session-id',monitor.session_id,
        '--deadline',repr(registration.deadline)]
    registration.revalidate()
    result=run_command(argv,Path(__file__).resolve().parent.parent,None,
        env=child_environment(os.environ),cancel_requested=lambda:False,lifecycle_monitor=monitor,
        capture=dict(directory=capture,max_bytes_per_stream=65536))
    qualified=(result['status']=='passed' and result['exit_code']==0 and result['started'] is True
        and result['cleanup_confirmed'] is True and monitor.reason is None
        and all(result.get(s+'_tail_unknown') is False and result.get(s+'_truncated') is False for s in ('stdout','stderr')))
    return dict(status='source_observed' if qualified else 'source_unverified',process=result,
        session_id=monitor.session_id,owner_id=monitor.owner_id,reason=monitor.reason)
