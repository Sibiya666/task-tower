"""Fixed Windows Beads port; no role execution, queue, recovery or acceptance.

Runner seam is admission's runner(operation, argv:list[str], cwd:Path,
 timeout:float, env:dict) -> (parsed_json_or_git_text, process_receipt).
Only the host injects runners. They must report actual bounded EOF/cleanup facts.
The compatibility fixture is test data, never loaded as executable authority.

Stage JSON has exactly seven keys (schema and six private fields). The loader
returns a dict subclass carrying a private source path. Copied JSON cannot
restore it, claims, fences or session authority. Every operation rereads policy.
Claim ignores caller admission packets and makes its own preclaim observation.
Claim returns public pins; subsequent methods require this same live instance.
Pins bind immutable admission base, not a mutable DEV checkpoint (roles own it).
Event input is exactly {value, reference, digest}; only fixed stages and safe
opaque references are accepted. Private inputs never appear in public results.
The coordinator owns serialized access, actor creation and the 60s renewal lane.
"""
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys
import threading
import time
from typing import TypedDict

from . import beads_admission as admission

CONTRACT_DIGEST = '7f91959cfe358ee823ea16eb0ce359e17146cebba2cc639c3fbe2a26d38b1bee'
NATIVE_DIGEST = '1cbe948667e441e80983681501b05cbaaad64eba0f5b07af861daea8fdb9ade4'
STAGES = frozenset(('claimed','spec_pending','spec_review','spec_approved','dev_tests_pending','dev_red_observed','dev_pending','dev_review',
                    'dev_approved','test_pending','test_review','candidate_for_integration',
                    'needs_input','fenced'))
TEXT_FIELDS = ('title','description','design','acceptance_criteria','notes')

class TaskInputs(TypedDict):
    title: str
    description: str
    design: str
    acceptance_criteria: str
    notes: str

class Pins(TypedDict):
    policy_digest: str
    native_contract_digest: str
    project: str
    base: dict

class ReadyTask(TypedDict):
    bead: str
    priority: int
    issue_type: str

class HostEvent(TypedDict):
    value: str
    reference: str
    digest: str

class Outcome(TypedDict):
    outcome: str
    reason: str

class _Policy(dict):
    pass


@dataclass(frozen=True)
class ProcessProof:
    operation: str
    cleanup_confirmed: bool
    eof_confirmed: bool


@dataclass(frozen=True)
class OperationProof:
    sequence: int
    processes: tuple[ProcessProof, ...]
    complete: bool


_EVENT_TYPE = threading.Event
_EVENT_IS_SET = threading.Event.is_set


def _hashfile(path,*,cancel_requested=None):
    # The qualified Windows build is 157179392 bytes. Keep a 256 MiB ceiling
    # while streaming 64 KiB chunks; oversized replacements still refuse.
    digest=hashlib.sha256()
    with admission.safe_config_path(path).open('rb') as stream:
        total=0
        while True:
            if cancel_requested is not None:
                if type(cancel_requested) is not _EVENT_TYPE: raise ValueError('exact_event_required')
                value=_EVENT_IS_SET(cancel_requested)
                if type(value) is not bool or value: raise ValueError('operation_cancelled')
            block=stream.read(65536)
            if not block: break
            total+=len(block)
            if total>256*1024*1024: raise ValueError('executable_limit')
            digest.update(block)
    return digest.hexdigest()


def load_stage_policy(path: Path) -> dict:
    """Load separate private operator policy; no Books policy or prose authority."""
    try:
        value=admission._read_json(path)
        if (not isinstance(value,dict) or set(value)!={'schema','admission_config','project',
                'role_profile','evidence_root','worktree_root','ownership'}
                or type(value['schema']) is not int or value['schema']!=1):
            raise ValueError()
        for key in ('admission_config','role_profile'):
            if not isinstance(value[key],str) or not Path(value[key]).is_absolute(): raise ValueError()
            if not admission.safe_config_path(value[key]).is_file(): raise ValueError()
        config=admission.load_config(Path(value['admission_config']))
        projects=[p for p in config['projects'] if p['id']==value['project']]
        if len(projects)!=1: raise ValueError()
        project=projects[0]
        roots=[admission._directory(value[k]).resolve() for k in ('evidence_root','worktree_root')]
        source=Path(project['source']).resolve(); database=Path(project['directory']).resolve()
        def overlap(a,b): return a==b or a in b.parents or b in a.parents
        if overlap(*roots) or any(overlap(r,s) for r in roots for s in (source,database)): raise ValueError()
        # Private configs/profile cannot live in source or evidence/worktree output.
        for key in ('admission_config','role_profile'):
            p=Path(value[key]).resolve()
            if any(p==r or r in p.parents for r in (source,*roots)): raise ValueError()
        policy_path=admission.safe_config_path(path).resolve()
        if any(policy_path==r or r in policy_path.parents for r in (source,*roots)): raise ValueError()
        ownership=value['ownership']
        if not isinstance(ownership,dict) or not ownership or not set(ownership)<=set(project['allowed_beads']): raise ValueError()
        for bead,owned in ownership.items():
            if not isinstance(owned,dict) or set(owned)!={'paths','domains'}: raise ValueError()
            paths,domains=owned['paths'],owned['domains']
            if not isinstance(paths,list) or not 1<=len(paths)<=1000: raise ValueError()
            normalized=[]
            for p in paths:
                if (not isinstance(p,str) or len(p)>512 or '\\' in p or ':' in p
                        or not p or p.endswith('/') or any(c in p for c in '\x00\r\n')
                        or PurePosixPath(p).is_absolute() or any(x in ('','.','..') for x in p.split('/'))): raise ValueError()
                normalized.append(p.casefold())
            if any(a==b or a.startswith(b+'/') or b.startswith(a+'/') for i,a in enumerate(normalized) for b in normalized[i+1:]): raise ValueError()
            if (not isinstance(domains,list) or not 1<=len(domains)<=1000
                    or any(not admission._match(d,r'[a-z][a-z0-9_.:-]{0,95}') for d in domains)
                    or len(set(domains))!=len(domains)): raise ValueError()
        result=_Policy(value); result._source_path=policy_path
        return result
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        raise ValueError('invalid_stage_policy') from None


class BeadsStagePort:
    def __init__(self,policy:dict,*,runner=None,clock=None,cancel_requested=None):
        self._cancel=None
        if cancel_requested is not None: self.bind_cancellation(cancel_requested)
        if type(policy) is not _Policy: raise ValueError('loaded_stage_policy_required')
        self._path=policy._source_path
        self._policy=load_stage_policy(self._path)
        if self._policy!=policy: raise ValueError('stage_policy_changed')
        self._digest=admission._digest(policy)
        self._config=admission.load_config(Path(policy['admission_config']))
        self._config_digest=admission._digest(self._config)
        self._project=next(p for p in self._config['projects'] if p['id']==policy['project'])
        self._exe_digest=_hashfile(self._config['executable'],cancel_requested=self._cancel)
        if runner is None and self._exe_digest!=NATIVE_DIGEST: raise ValueError('native_contract_unqualified')
        self._runner=runner
        self._sequence=0; self._proof=None; self._process_proofs=[]
        self._clock=clock or time.monotonic
        self._claims={}; self._fences=set()

    def bind_cancellation(self,event):
        if type(event) is not _EVENT_TYPE or (self._cancel is not None and self._cancel is not event):
            raise ValueError('exact_session_event_required')
        self._cancel=event

    def get_operation_proof(self):
        return self._proof

    def _cancelled(self):
        value=_EVENT_IS_SET(self._cancel) if self._cancel is not None else False
        if type(value) is not bool: raise admission._Stop('cancel_state_unknown','unknown')
        return value

    def _invoke(self,operation,argv,cwd,timeout,env):
        if self._cancelled(): raise admission._Stop('stop_requested')
        index=len(self._process_proofs)
        self._process_proofs.append(ProcessProof(operation,False,False))
        if self._runner is None:
            data,receipt=admission._production_runner(operation,argv,cwd,timeout,env,cancel_requested=self._cancel)
        else:
            data,receipt=self._runner(operation,argv,cwd,timeout,env)
        fact=admission._process_fact(operation,receipt)
        self._process_proofs[index]=ProcessProof(operation,fact['cleanup_confirmed'],fact['eof_confirmed'])
        return data,receipt

    def _context(self,bead=None,actor=None):
        if self._cancelled(): raise admission._Stop('stop_requested')
        if sys.platform!='win32': raise admission._Stop('unsupported_platform')
        if bead is not None:
            if bead in self._fences: raise admission._Stop('task_fenced','unknown')
            if bead not in self._policy['ownership']: raise admission._Stop('task_unauthorized')
        if actor is not None and not admission._match(actor,r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}'):
            raise admission._Stop('invalid_actor')
        if (admission._digest(load_stage_policy(self._path))!=self._digest
                or admission._digest(admission.load_config(Path(self._policy['admission_config'])))!=self._config_digest
                or _hashfile(self._config['executable'],cancel_requested=self._cancel)!=self._exe_digest):
            raise admission._Stop('policy_or_source_changed')
        metadata=admission._read_json(Path(self._project['directory'])/'.beads/metadata.json')
        if metadata.get('backend')!='dolt' or metadata.get('dolt_mode')!='embedded': raise admission._Stop('beads_metadata_invalid')

    def _call(self,operation,args,actor='stage-port',cwd=None):
        remaining=self._deadline-self._clock()
        if remaining<=5: raise admission._Stop('operation_deadline','unknown')
        isgit=operation.startswith('git_')
        if isgit:
            argv=['git','--no-optional-locks','-c','core.fsmonitor=false','-c','core.untrackedCache=false','-c','submodule.recurse=false']+args
        else:
            argv=[self._config['executable'],'--sandbox','--actor',actor,'--json']+args
        data,receipt=self._invoke(operation,argv,cwd or Path(self._project['directory']),min(10 if isgit else 25,remaining-5),admission._environment(Path(self._project['directory'])))
        fact=admission._process_fact(operation,receipt)
        if (self._clock()>=self._deadline or fact['status']!='passed' or fact['exit_code']!=0
                or fact['duration_seconds'] is None or not fact['cleanup_confirmed'] or not fact['eof_confirmed']
                or any(fact[s+'_bytes'] is None or fact[s+'_bytes']>admission.CAPTURE_LIMIT or receipt.get(s+'_truncated') is not False for s in ('stdout','stderr'))):
            raise admission._Stop('process_unknown','unknown')
        return data

    def _source(self):
        source=Path(self._project['source']); admission._git_metadata(source)
        def git(op,*args): return self._call('git_'+op,list(args),cwd=source)
        admission._validate_git_config(git('config','config','--null','--no-includes','--list'))
        top=git('toplevel','rev-parse','--show-toplevel'); metadata=git('metadata','rev-parse','--absolute-git-dir')
        if not isinstance(top,str) or Path(top.strip()).resolve()!=source.resolve() or not isinstance(metadata,str) or Path(metadata.strip()).resolve()!=admission._git_metadata(source): raise admission._Stop('source_identity_mismatch')
        index=git('index','ls-files','--stage','-v','-z')
        if not isinstance(index,str) or (index and not index.endswith('\0')): raise admission._Stop('source_index_invalid')
        if any(not re.match(r'H (100644|100755|120000) [0-9a-f]{40} 0\t',e) for e in index.split('\0') if e): raise admission._Stop('source_index_unsupported')
        head=git('head','rev-parse','--verify','HEAD^{commit}'); tree=git('tree','rev-parse','--verify','HEAD^{tree}')
        if not isinstance(head,str) or not isinstance(tree,str) or not admission._match(head.strip(),admission.SHA) or not admission._match(tree.strip(),admission.SHA) or head.strip()!=self._project['expected_head']: raise admission._Stop('source_pin_mismatch')
        if git('status','status','--porcelain=v1','--untracked-files=all','--ignore-submodules=all')!='': raise admission._Stop('source_dirty')
        return dict(head=head.strip(),tree=tree.strip())

    def _show(self,bead,actor):
        data=self._call('beads_show',['--readonly','show','--id='+bead,'--brief-deps'],actor)
        if not isinstance(data,list) or len(data)!=1 or admission._row(data[0])['id']!=bead: raise admission._Stop('native_row_invalid')
        return data[0]

    def _dependencies(self,bead,actor):
        data=self._call('beads_dependencies',['--readonly','dep','list',bead,'--direction','down'],actor)
        return self._edges(data)

    @staticmethod
    def _edges(data):
        if not isinstance(data,list) or len(data)>1000: raise admission._Stop('dependencies_unsupported')
        edges=[]
        for r in data:
            row=admission._row(r); kind=r.get('dependency_type')
            if kind not in ('blocks','parent-child') or row['status'] not in ('open','closed','in_progress'): raise admission._Stop('dependencies_unsupported')
            edges.append((row['id'],row['status'],row['issue_type'],kind))
        if len({e[0] for e in edges})!=len(edges): raise admission._Stop('dependencies_unsupported')
        return sorted(edges)

    def _eligible(self,bead,actor,pins):
        claim=self._claims.get(bead)
        if claim is None or actor!=claim['actor'] or pins!=claim['pins']: raise admission._Stop('live_claim_required')
        if self._clock()+30>=claim['expiry']: raise admission._Stop('lease_expired','unknown')
        if self._source()!=pins['base']: raise admission._Stop('source_changed')
        row=self._show(bead,actor)
        if row.get('status')!='in_progress' or row.get('assignee')!=actor or row.get('issue_type') not in admission.EXECUTABLE_TYPES or row.get('defer_until'): raise admission._Stop('owner_or_eligibility_changed')
        edges=self._dependencies(bead,actor)
        if self._edges(row.get('dependencies',[]))!=edges: raise admission._Stop('dependencies_inconsistent')
        parents=[]
        for ident,status,kind,dep in edges:
            if dep=='blocks':
                if status!='closed' or kind not in admission.EXECUTABLE_TYPES: raise admission._Stop('dependency_blocked')
            else:
                if kind!='epic' or status!='open': raise admission._Stop('parent_unsupported')
                parents.append(ident)
        if len(parents)>1 or row.get('parent')!=(parents[0] if parents else None): raise admission._Stop('parent_unsupported')
        if parents:
            parent=self._show(parents[0],actor)
            if parent.get('issue_type')!='epic' or parent.get('status')!='open' or parent.get('parent') or parent.get('defer_until') or parent.get('dependencies') or self._dependencies(parents[0],actor): raise admission._Stop('parent_unsupported')
        heartbeat,lease=self._lease(row)
        if heartbeat<claim['heartbeat'] or lease<claim['lease']:
            raise admission._Stop('lease_regressed','unknown')
        if self._source()!=pins['base']: raise admission._Stop('source_changed')
        return row

    @staticmethod
    def _utcnow():
        return datetime.now(timezone.utc)

    def _lease(self,row):
        try:
            heartbeat=datetime.fromisoformat(row['heartbeat_at'].replace('Z','+00:00'))
            expiry=datetime.fromisoformat(row['lease_expires_at'].replace('Z','+00:00'))
            if heartbeat.utcoffset() is None or expiry.utcoffset() is None or (expiry-heartbeat).total_seconds()!=300: raise ValueError()
            now=self._utcnow()
            if not 35<(expiry-now).total_seconds()<=305 or (heartbeat-now).total_seconds()>5: raise ValueError()
            return heartbeat,expiry
        except (ValueError,KeyError,TypeError,AttributeError): raise admission._Stop('lease_invalid','unknown') from None

    def _operation(self,body,bead=None,actor=None,task=False):
        self._sequence+=1
        self._process_proofs=[]
        self._deadline=self._clock()+30
        try:
            if task and (not admission._match(bead,admission.BEAD) or not admission._match(actor,r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}")):
                raise admission._Stop("invalid_task_identity")
            self._context(bead,actor)
            return body()
        except admission._Stop as stop:
            if isinstance(bead,str) and (stop.outcome=='unknown' or bead in self._claims): self._fences.add(bead)
            return dict(outcome=stop.outcome,reason=stop.reason)
        except Exception:
            if isinstance(bead,str): self._fences.add(bead)
            return dict(outcome='unknown',reason='operation_unavailable')
        finally:
            proofs=tuple(self._process_proofs)
            self._proof=OperationProof(self._sequence,proofs,all(p.cleanup_confirmed and p.eof_confirmed for p in proofs))

    def ready(self)->dict:
        def body():
            self._source()
            data=self._call('beads_ready',['--readonly','ready','--limit','1001'])
            if not isinstance(data,list) or len(data)>1000: raise admission._Stop('ready_overflow_or_invalid')
            tasks=[]; seen=set()
            for raw in data:
                r=admission._row(raw)
                if r['id'] in seen: raise admission._Stop('ready_rows_invalid')
                seen.add(r['id'])
                priority=raw.get('priority')
                if type(priority) is not int or not 0<=priority<=4: raise admission._Stop('ready_rows_invalid')
                if r['id'] in self._policy['ownership'] and r['status']=='open' and not r['assignee'] and r['issue_type'] in admission.EXECUTABLE_TYPES:
                    tasks.append(dict(bead=r['id'],priority=priority,issue_type=r['issue_type']))
            self._source()
            return dict(outcome='ok',reason='ready_observed',tasks=sorted(tasks,key=lambda x:(x['priority'],x['bead'])))
        result=self._operation(body); result.setdefault('tasks',[]); return result

    def claim(self,bead:str,actor:str,admission:dict)->dict:
        # Keep the documented keyword while excluding the packet from authority.
        from . import beads_admission as host_admission

        def body():
            if bead in self._claims: raise host_admission._Stop('live_claim_already_exists')
            # Share this operation's absolute budget with the original preclaim observer.
            def runner(op,argv,cwd,timeout,env):
                remaining=self._deadline-self._clock()-5
                if remaining<=0: raise host_admission._Stop('operation_deadline','unknown')
                return self._invoke(op,argv,cwd,min(timeout,remaining),env)
            packet=host_admission.observe(Path(self._policy['admission_config']),self._policy['project'],bead,runner=runner,clock=self._clock)
            if packet['outcome']!='eligible_observation': raise host_admission._Stop('preclaim_admission_refused', 'unknown' if packet['outcome']=='unknown' else 'refused')
            self._context(bead,actor)
            # Once the write is attempted any uncertainty remains fenced in memory.
            self._fences.add(bead)
            started=self._clock()
            data=self._call('beads_claim',['update',bead,'--claim'],actor)
            if not isinstance(data,list) or len(data)!=1 or data[0].get('id')!=bead or data[0].get('status')!='in_progress' or data[0].get('assignee')!=actor: raise host_admission._Stop('claim_readback_invalid','unknown')
            heartbeat,expiry=self._lease(data[0])
            pins=dict(policy_digest=self._digest,native_contract_digest=CONTRACT_DIGEST,project=self._policy['project'],base=packet['source'])
            self._claims[bead]=dict(actor=actor,pins=pins,expiry=started+min(270,(expiry-self._utcnow()).total_seconds()-30),heartbeat=heartbeat,lease=expiry)
            self._eligible(bead,actor,pins)
            self._fences.remove(bead)
            return dict(outcome='ok',reason='claim_verified',bead=bead,pins=copy.deepcopy(pins))
        return self._operation(body,bead,actor,True)

    def verify_owner_and_eligibility(self,bead:str,actor:str,pins:dict)->dict:
        def body():
            self._eligible(bead,actor,pins)
            return dict(outcome='ok',reason='owner_and_eligibility_verified',bead=bead)
        return self._operation(body,bead,actor,True)

    def read_task_inputs(self,bead:str,actor:str,pins:dict)->dict:
        def body():
            row=self._eligible(bead,actor,pins); inputs={}
            for key in TEXT_FIELDS:
                value=row.get(key)
                if value is None and key!='title': value=''
                if not isinstance(value,str) or (key=='title' and not value): raise admission._Stop('task_inputs_invalid')
                inputs[key]=value
            if sum(len(x.encode('utf-8')) for x in inputs.values())>24576: raise admission._Stop('task_inputs_limit')
            return dict(outcome='ok',reason='private_task_inputs',inputs=inputs,input_digest=admission._digest(inputs))
        result=self._operation(body,bead,actor,True)
        result.setdefault('inputs',None); result.setdefault('input_digest',None); return result

    def append_event(self,bead:str,actor:str,event:dict)->dict:
        def body():
            if (not isinstance(event,dict) or set(event)!={'value','reference','digest'} or event.get('value') not in STAGES
                    or not admission._match(event.get('reference'),r'[a-z][a-z0-9-]{0,95}') or not admission._match(event.get('digest'),r'[0-9a-f]{64}')): raise admission._Stop('event_invalid')
            self._eligible(bead,actor,self._claims.get(bead,{}).get('pins'))
            reason=event['reference']+'-sha256-'+event['digest']
            self._fences.add(bead)
            value=self._call('beads_set_state',['set-state',bead,'tower-stage='+event['value'],'--reason',reason],actor)
            if (not isinstance(value,dict) or set(value)!={'changed','dimension','event_id','issue_id','new_value','old_value','schema_version'}
                    or type(value['schema_version']) is not int or value['schema_version']!=1 or value['changed'] is not True
                    or value['dimension']!='tower-stage' or value['issue_id']!=bead or value['new_value']!=event['value']
                    or not admission._match(value['event_id'],admission.BEAD)
                    or (value['old_value'] is not None and not isinstance(value['old_value'],str))): raise admission._Stop('event_write_unknown','unknown')
            data=self._call('beads_event_read',['--readonly','show','--id='+value['event_id'],'--long'],actor)
            if not isinstance(data,list) or len(data)!=1: raise admission._Stop('event_readback_unknown','unknown')
            r=data[0]
            if (not isinstance(r,dict) or r.get('id')!=value['event_id'] or r.get('created_by')!=actor or r.get('parent')!=bead
                    or r.get('issue_type')!='event' or r.get('status')!='closed'
                    or not isinstance(r.get('description'),str) or not r['description'].endswith('\n\nReason: '+reason)
                    or not any(e[0]==bead and e[3]=='parent-child' for e in self._edges(r.get('dependencies')))):
                raise admission._Stop('event_readback_unknown','unknown')
            self._eligible(bead,actor,self._claims[bead]['pins'])
            self._fences.remove(bead)
            return dict(outcome='ok',reason='native_event_verified',event_reference=value['event_id'],event_digest=event['digest'])
        return self._operation(body,bead,actor,True)

    def heartbeat(self,bead:str,actor:str)->dict:
        def body():
            claim=self._claims.get(bead)
            self._eligible(bead,actor,claim['pins'] if claim else None)
            self._fences.add(bead); started=self._clock()
            data=self._call('beads_heartbeat',['heartbeat',bead],actor)
            if data!={'id':bead,'owner':actor,'schema_version':1,'status':'heartbeat'} or type(data.get('schema_version')) is not int: raise admission._Stop('heartbeat_unknown','unknown')
            row=self._show(bead,actor); heartbeat,expiry=self._lease(row)
            if row.get('assignee')!=actor or row.get('status')!='in_progress' or heartbeat<=claim['heartbeat'] or expiry<=claim['lease']: raise admission._Stop('heartbeat_readback_unknown','unknown')
            claim.update(expiry=started+min(270,(expiry-self._utcnow()).total_seconds()-30),heartbeat=heartbeat,lease=expiry)
            self._eligible(bead,actor,claim['pins']); self._fences.remove(bead)
            return dict(outcome='ok',reason='lease_renewed',bead=bead)
        return self._operation(body,bead,actor,True)
