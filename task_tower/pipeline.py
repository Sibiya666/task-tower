"""Installation-local pipeline CLI and contained host orchestration.

Only fixed host Python invocations inherit API credentials. Roles and checks
continue to construct their own stripped environments in pipeline_roles.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
import re
import sqlite3
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
import uuid

from . import dispatcher, processes
from .dispatch_delivery import DeliveryJournal, backend_fingerprint
from .dispatch_selection import load_dispatch_config
from .executor import _paths, _unique, _write
from .executor_profiles import load_executor_config, profile_fingerprint
from .executor_queue import validate_request
from .executor_queue import _dead
from .pipeline_journal import PipelineJournal, ACTIVE, STATES, REASONS
from .pipeline_policy import load_pipeline_config
from .project_connections import load_connections

_CAP=65536
_BACKOFF=(5,10,20,40,60)


class UnsupportedPlatform(ValueError):
    """The current release has no qualified native pipeline on this host."""


def native_execution_supported():
    return os.name=='nt'


def _require_native_execution():
    if not native_execution_supported():raise UnsupportedPlatform('unsupported_platform')


def adapter(request,config,journal):
    request=validate_request(request)
    unknown=dict(version=1,delivery_id=request['delivery_id'],status='unknown')
    rows=[t for t in config['tasks'] if t['repository'].casefold()==request['repository'] and
          all(t[k]==request[k] for k in ('issue','task_id','runner_label'))]
    if len(rows)!=1 or not config['_authority_check']():return unknown
    task=rows[0];profile=config['profiles'][task['executor_profile']]
    if task.get('shared_worker') is True and request['operation']=='submit':return unknown
    if request['operation']=='lookup':
        receipt=journal.lookup(request['delivery_id'])
        if receipt is None:return dict(version=1,delivery_id=request['delivery_id'],status='not_found')
        run=journal.status(receipt['receipt_id'])
        if any(run[k]!=request[k] for k in ('repository','issue','task_id','runner_label')) or run['policy_sha256']!=config['policy_sha256'] or run['profile_fingerprint']!=profile_fingerprint(profile):return unknown
        return receipt
    return _submit(request,config,journal,task)


def _submit(request,config,journal,task):
    """Host-only identity insertion; caller supplies current admission authority."""
    profile=config['profiles'][task['executor_profile']]
    limits={k:config[k] for k in ('task_timeout_seconds','role_timeout_seconds','max_reworks','max_processes','log_max_bytes')}
    return journal.submit(request,dict(profile_id=task['executor_profile'],profile_fingerprint=profile_fingerprint(profile),
        policy_sha256=config['policy_sha256'],component_keys=task['components'],limits=limits))


def _parser():
    parser=argparse.ArgumentParser(description='Durable local stage pipeline')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('adapter','work','watch','status','cancel','reconcile','_action','_dispatch'):
        command=sub.add_parser(name)
        for key in ('connections','journal'):command.add_argument('--'+key,type=Path,required=True)
        if name in ('adapter','work','watch','_action','_dispatch'):
            for key in ('config','executor-config'):command.add_argument('--'+key,type=Path,required=True)
        if name in ('watch','_dispatch'):
            for key in ('dispatch-config','dispatch-journal'):command.add_argument('--'+key,type=Path,required=True)
        if name=='adapter':
            for key in ('request','result'):command.add_argument('--'+key,type=Path,required=True)
        if name in ('_action','_dispatch'):command.add_argument('--host-result',type=Path,required=True)
        if name=='_action':command.add_argument('--host-owner',required=True)
        if name=='work':command.add_argument('--once',action='store_true',required=True)
        if name in ('cancel','reconcile'):command.add_argument('--run-id',required=True)
        if name=='status':command.add_argument('--run-id')
        if name=='reconcile':command.add_argument('--inspect',action='store_true',required=True)
    return parser


def _runtime(args):
    inputs=[args.connections]
    connection_bytes=args.connections.read_bytes()
    connections=load_connections(args.connections)
    if args.connections.read_bytes()!=connection_bytes:raise ValueError('Connections changed')
    args._connections_bytes=connection_bytes
    for key in ('config','executor_config','dispatch_config','dispatch_journal','request','result','host_result'):
        value=getattr(args,key,None)
        if value is not None:inputs.append(value)
    journals=[args.journal]+([args.dispatch_journal] if hasattr(args,'dispatch_journal') else [])
    paths=[*inputs,args.journal]
    sidecars=[Path(str(journal)+s) for journal in journals for s in ('-journal','-wal','-shm')]
    paths.extend(sidecars)
    if any(not Path(path).is_absolute() for path in paths):raise ValueError('Private pipeline paths must be absolute')
    _paths(paths,connections,transient_paths=sidecars)
    journal=PipelineJournal(args.journal,checkouts=[c.checkout for c in connections],forbidden_paths=inputs)
    if not hasattr(args,'config'):return connections,journal,None
    saved={path:path.read_bytes() for path in (args.connections,args.config,args.executor_config)}
    executor=load_executor_config(args.executor_config,connections)
    config=load_pipeline_config(args.config,connections,executor)
    config['_shared_journal']=journal
    def authority():
        try:
            _paths(paths,connections,transient_paths=sidecars)
            return all(path.read_bytes()==value for path,value in saved.items())
        except (ValueError,OSError):return False
    config['_authority_check']=authority
    config['_cli_args']=args
    from .pipeline_publish import publish_one
    config['_publisher']=publish_one
    if hasattr(args,'dispatch_config'):
        config['_dispatch_config']=load_dispatch_config(args.dispatch_config,connections)
        config['_dispatch_bytes']=args.dispatch_config.read_bytes()
        _backend_scope(config,journal)
    return connections,journal,config


def _fixed(args,command):
    argv=[str(Path(sys.executable).resolve()),'-m','task_tower','pipeline',command]
    keys=['connections','config','executor_config','journal']
    if command=='_dispatch':keys+=['dispatch_config','dispatch_journal']
    for key in keys:argv+=['--'+key.replace('_','-'),str(getattr(args,key))]
    return argv


def _backend_scope(config,journal):
    """The installed backend selects this exact owner, never another queue."""
    args=config['_cli_args'];backend=config['_dispatch_config'].get('backend')
    expected=_fixed(args,'adapter')+['--request','{request}','--result','{result}']
    if not backend or backend['argv']!=expected or Path(backend['cwd']).resolve()!=Path(__file__).resolve().parent.parent:
        raise ValueError('Dispatcher backend must bind this pipeline installation')
    fingerprint=backend_fingerprint(backend)
    authorized={(t['repository'].casefold(),t['issue'],t['task_id']) for t in config['tasks']}
    if any((t['repository'].casefold(),t['issue'],t['task_id']) not in authorized for t in config['_dispatch_config']['allowlist']):
        raise ValueError('Dispatcher allowlist is outside pipeline policy')
    saved=DeliveryJournal(args.dispatch_journal,readonly=True,checkouts=[c.checkout for c in config['_connections']],
        forbidden_paths=(args.connections,args.config,args.executor_config,args.journal,args.dispatch_config))
    for row in saved.rows():
        if row['backend_fingerprint']!=fingerprint:raise ValueError('Committed dispatcher backend cannot change')
    return fingerprint


def _read(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>_CAP or path.is_symlink():raise ValueError('Invalid host result')
    value=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=_unique)
    if not isinstance(value,dict):raise ValueError('Invalid host result')
    return value


def _host_result(value,kind):
    if kind=='_action':
        keys={'run_id','status','stage','generation','reason','input_sha256','receipt_sha256','effect_sha256'}
        if set(value)!=keys or value['status'] not in STATES|{'idle','unavailable'} or value['reason'] not in REASONS:raise ValueError('Invalid action report')
        if value['run_id'] is None:
            if value['status'] not in ('idle','unavailable') or value['stage'] is not None or value['generation'] is not None:raise ValueError('Invalid idle report')
            if value['status']=='unavailable' and (value['reason']!='source_unavailable' or any(value[key] is not None for key in ('input_sha256','receipt_sha256','effect_sha256'))):raise ValueError('Invalid source failure report')
        else:
            if value['status']=='unavailable':raise ValueError('Unavailable action cannot own a run')
            if str(uuid.UUID(value['run_id']))!=value['run_id'] or value['stage'] not in ('spec','development','test') or type(value['generation']) is not int or value['generation']<1:raise ValueError('Invalid action binding')
        for key in ('input_sha256','receipt_sha256','effect_sha256'):
            if value[key] is not None and (not isinstance(value[key],str) or not re.fullmatch('[a-f0-9]{64}',value[key])):raise ValueError('Invalid action digest')
    else:
        if set(value)!={'version','operational_failure','read_failure','deliveries'} or type(value['version']) is not int or value['version']!=1 or any(type(value[k]) is not bool for k in ('operational_failure','read_failure')) or not isinstance(value['deliveries'],list) or len(value['deliveries'])>256:raise ValueError('Invalid dispatcher report')
        for row in value['deliveries']:
            if not isinstance(row,dict) or set(row)-{'repository','issue','task_id','state','status','reason'} or not {'repository','issue','task_id'}<=set(row):raise ValueError('Invalid delivery report')
            if not isinstance(row['repository'],str) or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',row['repository']) or type(row['issue']) is not int or row['issue']<1 or not isinstance(row['task_id'],str) or not re.fullmatch('TT-[A-Z0-9-]+',row['task_id']):raise ValueError('Invalid delivery identity')
            if any(not isinstance(v,str) or not re.fullmatch('[a-z_]{1,64}',v) for k,v in row.items() if k in ('state','status','reason')):raise ValueError('Invalid delivery status')
    return value


def _public_run(run,journal):
    history=journal.history(run['run_id']);receipts=[v for v in history['verdicts'] if not v['superseded']]
    value={k:run[k] for k in ('run_id','repository','issue','task_id','state','stage','generation','process_count','reworks','deadline_at','reason','input_sha256','cancel_requested','created_at','updated_at')}
    value['limits']={k:run['limits'][k] for k in ('max_processes','max_reworks','task_timeout_seconds')}
    value['receipt_sha256']=receipts[-1]['receipt_sha256'] if receipts else None
    value['effect_sha256']=history['effects'][-1]['intent_sha256'] if history['effects'] else None
    prs=[e['observation'] for e in history['effects'] if e['kind']=='pr_create' and e['status']=='completed']
    value['pr_url']=prs[-1]['url'] if prs else None
    value['actions']=[dict(role=a['role'],stage=a['stage'],generation=a['generation'],state=a['state'],started_at=a['created_at'],finished_at=a['finished_at'],duration_seconds=None if a['evidence'] is None else a['evidence'].get('duration_seconds')) for a in history['attempts']]
    return value


def _connected(connections,runs):
    for run in runs:
        if not any(c.repository.casefold()==run['repository'] and c.runner_label==run['runner_label'] for c in connections):raise ValueError('Pipeline run disconnected')


def _status(connections,journal,run_id=None):
    runs=[journal.status(run_id)] if run_id else journal.status()['runs'];_connected(connections,runs)
    controller=journal.controller_health()
    if controller:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(controller['last_tick_at'])).total_seconds()
        controller={k:controller[k] for k in ('started_at','last_tick_at','health')}
        controller['uncertain']=(controller['health']['stopped'] and bool(controller['health']['workers'] or controller['health']['dispatcher'])) or age<0 or (not controller['health']['stopped'] and age>65)
    return dict(runs=[_public_run(r,journal) for r in runs],controller=controller,
        active=sum(r['state'] in ACTIVE for r in runs),queued=sum(r['state']=='queued' for r in runs),
        unknown=sum(r['state']=='unknown' for r in runs),parked=sum(r['state'] in ('needs_input','cancelled','timed_out') for r in runs))


def _action(config,journal):
    _require_native_execution()
    from .pipeline_worker import step
    journal.recover()
    return step(config,journal,owner_id=config['_cli_args'].host_owner)


def _dispatch(config,journal):
    _require_native_execution()
    args=config['_cli_args'];_backend_scope(config,journal)
    if args.dispatch_config.read_bytes()!=config['_dispatch_bytes']:raise ValueError('Dispatcher policy changed')
    report=dispatcher.tick(config['_connections'],config['_dispatch_config'],args.dispatch_journal,
        authority_check=lambda:config['_authority_check']() and args.dispatch_config.read_bytes()==config['_dispatch_bytes'],
        forbidden_paths=(args.connections,args.config,args.executor_config,args.journal,args.dispatch_config))
    # Deliberately do not serialize raw source data, backend paths or prose.
    return dict(version=1,operational_failure=bool(report.get('operational_failure')),
        read_failure=any(p.get('reason')=='source_unavailable' for p in report['projects']),
        deliveries=[{k:d[k] for k in ('repository','issue','task_id','state','status','reason') if k in d} for d in report['deliveries']][:256])


class _Host:
    """A thread waits on the existing contained runner; it never launches itself."""
    def __init__(self,args,kind,timeout,stop):
        _require_native_execution()
        self.stop=stop;self.done=threading.Event();self.outcome=None;self.result=None
        self._budget_deadline=None
        self.kind=kind
        self.journal=PipelineJournal(args.journal)
        self.owner=str(uuid.uuid4()) if kind=='_action' else None
        self.directory=tempfile.TemporaryDirectory(prefix='task-tower-host-',dir=args.journal.parent)
        self.path=Path(self.directory.name)/'host-result.json'
        self.argv=_fixed(args,kind)+['--host-result',str(self.path)]
        if self.owner:self.argv+=['--host-owner',self.owner]
        self.timeout=timeout
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        try:
            self.outcome=processes.run_command(self.argv,Path(__file__).resolve().parent.parent,self.timeout,env=dict(os.environ),
                cancel_requested=self.cancelled)
            if self.outcome['status']=='passed' and self.outcome['cleanup_confirmed']:
                self.result=_host_result(_read(self.path),self.kind)
        except (OSError,ValueError,KeyError,TypeError,AttributeError):pass
        finally:self.done.set()
    def cancelled(self):
        if self.stop.is_set():return True
        if self.owner:
            with self.journal.operation_deadline(time.monotonic()+1.0):runs=self.journal.status()['runs']
            if self.stop.is_set():return True
            for run in runs:
                if run['owner_id']==self.owner:
                    now=datetime.now(timezone.utc)
                    elapsed=time.monotonic()
                    if run['deadline_at'] is not None and self._budget_deadline is None:
                        self._budget_deadline=elapsed+max(0,(datetime.fromisoformat(run['deadline_at'])-now).total_seconds())
                    return bool(run['cancel_requested']) or now<datetime.fromisoformat(run['updated_at']) or (self._budget_deadline is not None and elapsed>=self._budget_deadline)
        return False
    def close(self):
        if self.done.is_set():self.directory.cleanup()


def work(config,journal):
    _require_native_execution()
    args=config['_cli_args'];args.journal.parent.mkdir(parents=True,exist_ok=True)
    stop=threading.Event();host=_Host(args,'_action',_remaining(config,journal),stop)
    interrupted=False;confirmed=False
    try:
        while not host.done.wait(.1):pass
    except KeyboardInterrupt:
        interrupted=True
    finally:
        state=dict(owner=None,stop=stop,workers=[host],dispatcher=None,ticks=0,failures=0)
        confirmed=_shutdown(config,journal,state,cancel_runs=interrupted)
    return host.result if confirmed and host.result is not None else dict(status='unknown',reason='cleanup_unknown')


def _remaining(config,journal):
    # Preclaim ceiling only. The callback anchors the claimed owner's immutable
    # remaining UTC budget to monotonic time; another task cannot shorten it.
    return config['task_timeout_seconds']


def _watch_read_failures(state):
    return state['failures']+max(state.get('action_failures',0),int(state.get('action_warning',False)))


def watch_tick(config,journal,*,dispatch_tick=dispatcher.tick):
    """Poll contained hosts and refill; slow API operations remain off-loop."""
    _require_native_execution()
    state=config['_watch'];args=config['_cli_args']
    # Fresh private policy validation happens in every helper and here each pass.
    _,_,fresh=_runtime(args)
    if fresh['policy_sha256']!=config['policy_sha256']:raise ValueError('Pipeline watch policy changed')
    journal.recover();now=time.monotonic()
    for host in list(state['workers']):
        if host.done.is_set():
            result=host.result;host.close();state['workers'].remove(host)
            if result:
                state['action_warning']=result.get('reason')=='source_unavailable'
                if result.get('status')=='unavailable':
                    state['action_failures']=state.get('action_failures',0)+1
                    state['next_queued_action']=now+_BACKOFF[min(state['action_failures']-1,4)]
                else:state.update(action_failures=0,next_queued_action=0)
    helper=state['dispatcher']
    if helper and helper.done.is_set():
        result=helper.result;helper.close();state['dispatcher']=None
        if result and result.get('read_failure'):
            state['failures']+=1;state['next_dispatch']=now+_BACKOFF[min(state['failures']-1,4)]
        else:
            state['failures']=0;state['next_dispatch']=now+config['interval_seconds']
    if state['dispatcher'] is None and now>=state['next_dispatch']:
        state['dispatcher']=_Host(args,'_dispatch',config['task_timeout_seconds'],state['stop'])
    rows=journal.status()['runs']
    active=[r for r in rows if r['state'] in ACTIVE]
    eligible=set()
    for run in rows:
        others=[r for r in active if r['run_id']!=run['run_id'] and r['repository']==run['repository']]
        busy=any(r['state']!='ready' or not _dead(r['owner_pid']) for r in others)
        if busy or run['cancel_requested']:continue
        if run['state']=='ready' and _dead(run['owner_pid']):eligible.add(run['repository'])
        if run['state']=='queued' and now>=state.get('next_queued_action',0) and len(active)<config['max_active'] and not any('*' in r['component_keys'] or '*' in run['component_keys'] or set(r['component_keys'])&set(run['component_keys']) for r in others):eligible.add(run['repository'])
    # Atomically claimed run/component capacity remains authoritative inside children.
    if eligible:
        for _ in range(min(config['max_active']-len(state['workers']),len(eligible))):
            state['workers'].append(_Host(args,'_action',_remaining(config,journal),state['stop']))
    state['ticks']+=1
    health=dict(ticks=state['ticks'],read_failures=_watch_read_failures(state),workers=len(state['workers']),dispatcher=int(state['dispatcher'] is not None))
    journal.controller_tick(state['owner'],health)
    return health


def _shutdown(config,journal,state,*,cancel_runs=True):
    state['stop'].set()  # Always request contained termination before touching DB.
    deadline=time.monotonic()+4.8
    hosts=[*state['workers']]+([state['dispatcher']] if state['dispatcher'] else [])
    db_done=threading.Event();hosts_done=threading.Event();proof=dict(hosts=False,db=False)
    state['_shutdown_journal_done']=db_done
    def finish_journal():
        # SQLite can perform more than one internal busy wait per statement.
        # Keep that wait off the caller as well as capping every transaction by
        # the same deadline. A late transaction must roll back before commit.
        try:
            shutdown_journal=PipelineJournal(journal.path,checkouts=journal.checkouts,forbidden_paths=journal.forbidden_paths)
            with shutdown_journal.operation_deadline(deadline),ExitStack() as existing:
                identity=existing.enter_context(shutdown_journal._pinned_database())
                if identity is not None:existing.enter_context(shutdown_journal._existing_database(identity))
                fallback=False
                try:runs=shutdown_journal.status()['runs']
                except ValueError as error:
                    cause=error.__cause__
                    if not isinstance(cause,sqlite3.Error) or getattr(cause,'sqlite_errorcode',None)!=sqlite3.SQLITE_READONLY_ROLLBACK:raise
                    hosts_done.wait(max(0,deadline-time.monotonic()))
                    if not proof['hosts'] or any(not h.done.is_set() or not h.outcome or not h.outcome.get('cleanup_confirmed') for h in hosts):return
                    if identity is None:return
                    shutdown_journal._recover_existing()
                    runs=shutdown_journal.status()['runs']
                    fallback=True
                for run in runs:
                    if cancel_runs and run['owner_id'] in {h.owner for h in state['workers']} and run['state'] in (ACTIVE if fallback else ACTIVE-{'unknown'}):shutdown_journal.cancel(run['run_id'])
                hosts_done.wait(max(0,deadline-time.monotonic()))
                if not fallback:shutdown_journal.recover()
                if not proof['hosts']:return
                if state['owner'] is not None:
                    shutdown_journal.controller_tick(state['owner'],dict(ticks=state['ticks'],read_failures=_watch_read_failures(state),workers=0,dispatcher=0))
                    shutdown_journal.release_controller(state['owner'])
                if identity is not None:shutdown_journal._assert_existing()
            if time.monotonic()>=deadline:return
            proof['db']=True
        except (ValueError,OSError):pass
        finally:db_done.set()
    threading.Thread(target=finish_journal,daemon=True).start()
    confirmed=True
    for host in hosts:
        host.done.wait(max(0,deadline-time.monotonic()))
        if not host.done.is_set() or not host.outcome or not host.outcome.get('cleanup_confirmed'):confirmed=False
        host.close()
    proof['hosts']=confirmed;hosts_done.set()
    db_done.wait(max(0,deadline-time.monotonic()))
    return confirmed and db_done.is_set() and proof['db']


def watch(config,journal):
    _require_native_execution()
    owner=str(uuid.uuid4());journal.claim_controller(owner,config['policy_sha256'])
    state=dict(owner=owner,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0,next_dispatch=0)
    config['_watch']=state;exit_code=0
    try:
        while not state['stop'].is_set():
            watch_tick(config,journal)
            state['stop'].wait(.25)
    except KeyboardInterrupt:pass
    finally:
        if not _shutdown(config,journal,state):exit_code=1
    return exit_code


def main(argv=None):
    args=_parser().parse_args(argv)
    try:
        if args.command in ('work','watch','_action','_dispatch'):_require_native_execution()
        connections,journal,config=_runtime(args)
        if args.command=='adapter':
            report=adapter(_read(args.request),config,journal);_write(args.result,report);return 0
        if args.command in ('_action','_dispatch'):
            report=_action(config,journal) if args.command=='_action' else _dispatch(config,journal)
            if len(json.dumps(report).encode('utf-8'))>_CAP:raise ValueError('Oversize host report')
            _write(args.host_result,report);return 0
        if args.command=='watch':return watch(config,journal)
        if args.command=='work':report=work(config,journal)
        elif args.command=='status':report=_status(connections,journal,args.run_id)
        else:
            _status(connections,journal,args.run_id)
            if args.connections.read_bytes()!=args._connections_bytes:raise ValueError('Connections changed')
            if args.command=='cancel':journal.cancel(args.run_id);report=_status(connections,journal,args.run_id)
            else:
                history=journal.history(args.run_id)
                report=dict(run=_public_run(journal.status(args.run_id),journal),
                    effects=[dict(effect_id=e['effect_id'],kind=e['kind'],status=e['status'],intent_sha256=e['intent_sha256'],observation_sha256=e['observation_sha256'],
                        binding={k:v for k,v in e['intent'].items() if k in ('repository','issue','issue_id','task_id','run_id','head_sha','base_sha','branch','parent','tree','source_sha','evidence_manifest_sha256')},
                        observed=None if e['observation'] is None else {k:v for k,v in e['observation'].items() if k in ('status','commit_sha','tree_sha','head_sha','number','url','author','repository','issue','issue_id','task_id','run_id','base_sha','branch')}) for e in history['effects']],
                    required_action='unknown_requires_owner_reconciliation' if journal.status(args.run_id)['state']=='unknown' else None)
        if args.connections.read_bytes()!=args._connections_bytes:raise ValueError('Connections changed')
        print(json.dumps(report,sort_keys=True))
        completed={'idle','ready','needs_input','cancelled','timed_out','ready_for_pr','awaiting_pr'}
        return 1 if args.command=='work' and report.get('status') not in completed else 0
    except UnsupportedPlatform:
        print(json.dumps(dict(error='unsupported_platform')),file=sys.stderr);return 2
    except (OSError,ValueError,TypeError,KeyError):
        print(json.dumps(dict(error='invalid_or_unavailable_private_state')),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
