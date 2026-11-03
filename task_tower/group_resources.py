"""Conservative arithmetic and genuine read-only same-process observations.

No resource lease, reservation or execution authority is created here.
Registered claims remain closed until the actual transactional consumers and
workspace/current-epoch producers are independently accepted.
"""
import re
import copy
import json
import os
import sys
import time
import uuid
from datetime import datetime,timezone
from .capacity_policy import positive
from .group_policy import ROLES, _capacity
from .pipeline_inputs import canonical_json,digest_manifest

_MAX=2**63-1
_CPU_HEADROOM=1000
_MEMORY_HEADROOM=1024**3
_HELPER_CPU=100
_HELPER_MEMORY=64*1024**2
_COLLECTOR_PID=os.getpid()
_COLLECTOR_LIFETIME=str(uuid.uuid4())
_LAST_MONOTONIC=time.monotonic_ns()
_LAST_WALL=datetime.now(timezone.utc)
_SAMPLES={}


class ResourceContext:
    """Actual existing registration, not a normalized policy dictionary."""
    def __init__(self):
        raise TypeError('Use ResourceContext.from_registration')

    @classmethod
    def from_registration(cls,registration):
        from .group_registration import RegistrationContext
        if type(registration) is not RegistrationContext: raise ValueError('Actual registration context required')
        context=object.__new__(cls); context._registration=registration
        context._snapshot()
        return context

    def _snapshot(self):
        from .group_registration import RegistrationContext
        registration=self._registration
        if type(registration) is not RegistrationContext: raise ValueError('Actual registration context required')
        registration.revalidate(); policy=registration.policy
        with registration.journal._db(False,initialize=False) as db:
            installed=db.execute('SELECT * FROM group_installation').fetchone()
            if installed is None: raise ValueError('Resource policy is not registered')
            installed=dict(installed)
            epoch=db.execute('SELECT * FROM group_capacity_epochs WHERE epoch=?',
                (installed['current_capacity_epoch'],)).fetchone()
            if (epoch is None or installed['installation_id']!=policy['installation_id']
                    or installed['current_policy_sha256']!=policy['policy_sha256']
                    or installed['current_authorization_sha256']!=policy['authorization_sha256']
                    or epoch['capacity_sha256']!=policy['capacity_sha256']):
                raise ValueError('Resource policy epoch changed')
        registration.revalidate()
        pools={}
        for grant in policy.get('harness_resources',{}).values():
            pool=pools.setdefault(grant['pool_id'],dict(max_parallel=None))
            cap=grant['max_parallel']
            if cap is not None: pool['max_parallel']=cap if pool['max_parallel'] is None else min(pool['max_parallel'],cap)
        return dict(installation_id=policy['installation_id'],policy_epoch=installed['current_capacity_epoch'],
            capacity=copy.deepcopy(policy['capacity']),capacity_sha256=policy['capacity_sha256'],harness_pools=pools)


class _ProbeDeadline(ValueError):
    pass


def _probe_tick(deadline):
    if time.monotonic()>=deadline: raise _ProbeDeadline('Resource probe deadline exhausted')


def _windows_probe(deadline):
    """Only fixed read-only Windows APIs; unresolved enclosing jobs stay unknown."""
    import ctypes as c
    kernel=c.WinDLL('kernel32',use_last_error=True)
    dword=c.c_uint32; size=c.c_size_t; u64=c.c_uint64; handle=c.c_void_p
    class Memory(c.Structure):
        _fields_=[('length',dword),('load',dword)]+[(name,u64) for name in
            ('total_physical','available_physical','total_commit','available_commit','total_virtual','available_virtual','extended_virtual')]
    class BasicLimit(c.Structure):
        _fields_=[('process_time',c.c_int64),('job_time',c.c_int64),('flags',dword),
            ('minimum_working_set',size),('maximum_working_set',size),('active_process_limit',dword),
            ('affinity',size),('priority',dword),('scheduling',dword)]
    class ExtendedLimit(c.Structure):
        _fields_=[('basic',BasicLimit),('io',u64*6),('process_memory',size),('job_memory',size),
            ('peak_process_memory',size),('peak_job_memory',size)]
    class CpuRate(c.Structure):
        _fields_=[('flags',dword),('value',dword)]
    kernel.GetActiveProcessorCount.argtypes=[c.c_ushort]; kernel.GetActiveProcessorCount.restype=dword
    kernel.GetProcessAffinityMask.argtypes=[handle,c.POINTER(size),c.POINTER(size)]; kernel.GetProcessAffinityMask.restype=c.c_int
    kernel.GlobalMemoryStatusEx.argtypes=[c.POINTER(Memory)]; kernel.GlobalMemoryStatusEx.restype=c.c_int
    kernel.IsProcessInJob.argtypes=[handle,handle,c.POINTER(c.c_int)]; kernel.IsProcessInJob.restype=c.c_int
    kernel.QueryInformationJobObject.argtypes=[handle,c.c_int,handle,dword,c.POINTER(dword)]
    kernel.QueryInformationJobObject.restype=c.c_int
    provenance={}; limitations=[]; cpu=None; memory=None
    def call(function,*args):
        _probe_tick(deadline); result=function(*args); _probe_tick(deadline)
        if not result: raise OSError('Native resource query unavailable')
        return result
    try:
        active=int(call(kernel.GetActiveProcessorCount,0xffff)); process_mask=size(); system_mask=size()
        call(kernel.GetProcessAffinityMask,handle(-1),c.byref(process_mask),c.byref(system_mask))
        provenance['cpu']=dict(active=active,process_affinity=hex(process_mask.value),system_affinity=hex(system_mask.value))
        if active>c.sizeof(size)*8 or not process_mask.value or process_mask.value&~system_mask.value:
            raise OSError('Unsupported processor group or affinity')
        cpu=min(active,process_mask.value.bit_count())*1000
    except OSError: limitations.append('cpu_measurement_unavailable')
    try:
        value=Memory(); value.length=c.sizeof(Memory)
        call(kernel.GlobalMemoryStatusEx,c.byref(value))
        if any(getattr(value,'available_'+kind)>getattr(value,'total_'+kind) for kind in ('physical','commit','virtual')):
            raise OSError('Inconsistent memory observation')
        memory=_nonnegative(min(value.available_physical,value.available_commit,value.available_virtual))
        provenance['memory']=dict(available_physical=value.available_physical,available_commit=value.available_commit,
            available_virtual=value.available_virtual)
    except (OSError,ValueError): limitations.append('memory_measurement_unavailable')
    try:
        in_job=c.c_int(); call(kernel.IsProcessInJob,handle(-1),None,c.byref(in_job))
        provenance['in_job']=bool(in_job.value)
        if in_job.value:
            for number,structure,name in ((9,ExtendedLimit,'immediate_job_limits'),(15,CpuRate,'immediate_job_cpu')):
                try:
                    value=structure(); returned=dword()
                    call(kernel.QueryInformationJobObject,None,number,c.byref(value),c.sizeof(value),c.byref(returned))
                    if returned.value!=c.sizeof(value): raise OSError('Incomplete immediate job query')
                    provenance[name]=(dict(flags=value.basic.flags,process_memory=value.process_memory,job_memory=value.job_memory)
                        if number==9 else dict(flags=value.flags,value=value.value))
                except OSError: provenance[name]=None
            cpu=None; memory=None; limitations.append('enclosing_job_constraints_unresolved')
    except OSError:
        cpu=None; memory=None; limitations.append('job_membership_unavailable')
    return cpu,memory,limitations,provenance


def _collector_clock():
    global _LAST_MONOTONIC,_LAST_WALL
    if os.getpid()!=_COLLECTOR_PID: raise ValueError('Foreign resource collector process')
    mono=time.monotonic_ns(); wall=datetime.now(timezone.utc)
    if mono<_LAST_MONOTONIC or wall<_LAST_WALL: raise ValueError('Resource collector clock moved backward')
    _LAST_MONOTONIC=mono; _LAST_WALL=wall
    return mono,wall


def observe_host(context,*,deadline):
    """Genuine same-process sample only; no journal write or claim is made."""
    import math
    try: finite=type(deadline) in (int,float) and math.isfinite(deadline)
    except OverflowError: finite=False
    if type(context) is not ResourceContext or not finite:
        raise ValueError('Typed resource context and monotonic deadline required')
    start,wall=_collector_clock(); now=time.monotonic()
    if deadline<=now: raise ValueError('Resource observation deadline exhausted')
    expires=start+int(min(5.0,deadline-now)*1_000_000_000)
    if expires<=start: raise ValueError('Resource observation deadline exhausted')
    probe_deadline=min(deadline,now+2)
    scope=context._snapshot(); _probe_tick(probe_deadline)
    platform={'win32':'windows','linux':'linux','darwin':'macos'}.get(sys.platform,'unsupported')
    cpu=None; memory=None; limitations=[]; provenance=dict(capacity_sha256=scope['capacity_sha256'])
    timed_out=False
    if platform=='windows':
        try:
            cpu,memory,limitations,native=_windows_probe(probe_deadline); provenance['native']=native
        except _ProbeDeadline: timed_out=True; limitations=['probe_deadline_exhausted']
        except (OSError,ValueError,AttributeError): limitations=['native_probe_unavailable']
    else: limitations=['platform_unsupported']
    context._snapshot()
    end,_=_collector_clock()
    if time.monotonic()>=probe_deadline or end>=expires: timed_out=True
    budget=resource_budget(cpu,memory,scope['capacity'])
    status=budget['status']; reason=None
    if platform!='windows': status='unavailable'; reason='platform_unsupported'
    elif timed_out: status='unavailable'; reason='resource_unavailable'; cpu=None; memory=None
    elif status=='unavailable': reason='resource_unavailable'
    provenance['fallback_fields']=budget['limitations'] if status=='fallback' else []
    body=dict(version=1,observation_id=str(uuid.uuid4()),installation_id=scope['installation_id'],
        policy_epoch=scope['policy_epoch'],boot_id=_COLLECTOR_LIFETIME,process_id=_COLLECTOR_PID,
        monotonic_ns=start,observed_at=wall.isoformat(timespec='microseconds').replace('+00:00','Z'),
        expires_monotonic_ns=expires,platform=platform,cpu_millis=cpu,available_memory_bytes=memory,
        limitations=limitations,harness_pools=scope['harness_pools'],provenance=provenance,status=status,reason=reason)
    # Public bodies retain raw nullable measurements. Only the unchanged actual
    # capacity policy can apply fallback and its additional count cap later.
    for digest,entry in list(_SAMPLES.items()):
        if entry[2]<=end: del _SAMPLES[digest]
    if len(_SAMPLES)>=32: del _SAMPLES[next(iter(_SAMPLES))]
    digest=digest_manifest(body); _SAMPLES[digest]=(context,canonical_json(body),expires)
    return copy.deepcopy(body)


def _current_observation(context,digest):
    """Locate an actual local sample; raw SQL/public dictionaries cannot restore it."""
    if (type(context) is not ResourceContext or not isinstance(digest,str)
            or not re.fullmatch('[a-f0-9]{64}',digest) or os.getpid()!=_COLLECTOR_PID):
        raise ValueError('Resource observation unavailable')
    entry=_SAMPLES.get(digest)
    if entry is None or entry[0] is not context or time.monotonic_ns()>=entry[2]:
        raise ValueError('Resource observation unavailable')
    scope=context._snapshot(); mono,_=_collector_clock(); body=json.loads(entry[1])
    if (mono>=entry[2] or body['boot_id']!=_COLLECTOR_LIFETIME or body['process_id']!=os.getpid()
            or body['installation_id']!=scope['installation_id'] or body['policy_epoch']!=scope['policy_epoch']
            or body['provenance']['capacity_sha256']!=scope['capacity_sha256']):
        raise ValueError('Resource observation unavailable')
    return body


def _nonnegative(value):
    if type(value) is not int or not 0<=value<=_MAX:
        raise ValueError('Invalid resource measurement integer')
    return value


def _sum(values):
    result=0
    for value in values:
        result+=_nonnegative(value)
        if result>_MAX: raise ValueError('Resource arithmetic overflow')
    return result


def task_envelope(role_profiles,grants):
    """Maximum declared six-role estimate plus fixed helper overhead; pure math."""
    if not isinstance(role_profiles,dict) or set(role_profiles)!=set(ROLES) or not isinstance(grants,dict):
        raise ValueError('Six explicit role resource grants required')
    selected=[]; pools={}
    for role in ROLES:
        name=role_profiles[role]
        if not isinstance(name,str) or name not in grants: raise ValueError('Missing selected role resource grant')
        grant=grants[name]
        if (not isinstance(grant,dict) or set(grant)!={'pool_id','cpu_millis','memory_bytes','max_parallel'}
                or not isinstance(grant['pool_id'],str)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',grant['pool_id'])):
            raise ValueError('Invalid selected role resource grant')
        positive(grant['cpu_millis']); positive(grant['memory_bytes'])
        if grant['max_parallel'] is not None: positive(grant['max_parallel'])
        pools[role]=grant['pool_id']; selected.append(grant)
    return dict(cpu_millis=_sum((max(grant['cpu_millis'] for grant in selected),_HELPER_CPU)),
        memory_bytes=_sum((max(grant['memory_bytes'] for grant in selected),_HELPER_MEMORY)),role_pools=pools)


def resource_budget(cpu_millis,available_memory_bytes,capacity):
    """Arithmetic over declared measurements; does not authenticate them."""
    policy=_capacity(capacity); values=[cpu_millis,available_memory_bytes]; missing=[]
    for index,key in enumerate(('cpu_millis','memory_bytes')):
        if values[index] is None:
            missing.append(key)
            if policy['fallback'] is not None: values[index]=policy['fallback'][key]
        else: _nonnegative(values[index])
    maximum=policy['max_executors']
    if any(value is None for value in values):
        return dict(status='unavailable',cpu_millis=None,memory_bytes=None,
            max_executors=maximum,limitations=missing)
    if missing:
        limit=policy['fallback']['max_executors']
        maximum=limit if maximum is None else min(maximum,limit)
    cpu=max(0,values[0]-_CPU_HEADROOM); memory=max(0,values[1]-_MEMORY_HEADROOM)
    if policy['max_cpu_millis'] is not None: cpu=min(cpu,policy['max_cpu_millis'])
    if policy['max_memory_bytes'] is not None: memory=min(memory,policy['max_memory_bytes'])
    return dict(status='fallback' if missing else 'available',cpu_millis=cpu,memory_bytes=memory,
        max_executors=maximum,limitations=missing)


def resources_fit(budget,held,candidate):
    """Pure feasibility only; the real claim must re-read every held lease."""
    if not isinstance(budget,dict) or not isinstance(held,list): raise ValueError('Invalid resource arithmetic inputs')
    if budget.get('status') not in ('available','fallback') or any(item is None for item in held): return False
    if not isinstance(candidate,dict) or any(not isinstance(item,dict) for item in held):
        raise ValueError('Invalid held resource estimates')
    if (not {'cpu_millis','memory_bytes','max_executors'}<=set(budget)
            or any(not {'cpu_millis','memory_bytes'}<=set(item) for item in [*held,candidate])):
        raise ValueError('Incomplete resource arithmetic inputs')
    totals={key:_sum([positive(item[key]) for item in held]+[positive(candidate[key])])
        for key in ('cpu_millis','memory_bytes')}
    if any(totals[key]>_nonnegative(budget[key]) for key in totals): return False
    maximum=budget['max_executors']
    return maximum is None or len(held)+1<=positive(maximum)
