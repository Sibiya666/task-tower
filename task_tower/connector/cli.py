"""UI-independent explicit assignment runner.

Usage: python -m task_tower.connector.cli run --config <private-file>
No install/autostart/service or dynamic role scheduling. Managed work may opt
into fixed trusted delivery through explicit delivery_projects configuration. Configuration is
host-trusted: version, connector_id, endpoint, token_file, journal, app_server,
projects {project_id: {repository, worktree_root}}, assignment
{project_id, bead_id, base_sha, input: {text}}. Journals persist across restarts;
pending commands are fenced. New effects require a fresh explicit assignment.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import time
from .store import ConnectorStore
from .worktrees import Worktrees
from .app_server import AppServer,DecisionRequired
from .client import APIClient,Connector,LifecycleConnector
from ..service.beads import strict_json,identity,bead_id
from ..service.cli import read_token,_absolute
from ..service.store import encoded,plan_digest

def load_config(path,*,document=None):
    path=_absolute(str(path))
    if document is None:
        with path.open('rb') as f:raw=f.read(65537)
    else:raw=document
    if len(raw)>65536:raise ValueError('configuration_limit')
    value=strict_json(raw.decode('utf-8'))
    required={'version','connector_id','endpoint','token_file','journal','app_server','projects','assignment'}
    if (not isinstance(value,dict) or set(value)-{'max_active_tasks','delivery_projects','delivery_policies'} not in (required,required-{'assignment'}|{'assignments'})
            or type(value['version']) is not int or value['version']!=1):raise ValueError('invalid_configuration')
    identity(value['connector_id'])
    for k in ('token_file','journal','app_server'):value[k]=_absolute(value[k])
    if len({value[k] for k in ('token_file','journal','app_server')})!=3:raise ValueError('private_file_collision')
    if not isinstance(value['projects'],dict) or not 1<=len(value['projects'])<=32:raise ValueError('invalid_projects')
    assignments=[value['assignment']] if 'assignment' in value else value['assignments']
    if not isinstance(assignments,list) or len(assignments)>32:raise ValueError('invalid_assignments')
    for a in assignments:
        if not isinstance(a,dict) or set(a)!={'project_id','bead_id','base_sha','input'}:raise ValueError('invalid_assignment')
        identity(a['project_id']);bead_id(a['bead_id'])
        if not isinstance(a['base_sha'],str) or re.fullmatch('[0-9a-f]{40}',a['base_sha']) is None:raise ValueError('exact_sha_required')
        if not isinstance(a['input'],dict) or set(a['input'])!={'text'} or not isinstance(a['input']['text'],str) or not 1<=len(a['input']['text'])<=32768:raise ValueError('invalid_input')
        if a['project_id'] not in value['projects']:raise ValueError('project_forbidden')
    scope=value.get('delivery_projects',{})
    if (not isinstance(scope,dict) or set(scope)-set(value['projects']) or any(not isinstance(r,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',r) is None for r in scope.values())):raise ValueError('invalid_delivery_scope')
    value['delivery_projects']=scope
    from ..delivery_policy import policies
    policies(value['projects'],scope,value.get('delivery_policies'))
    value['delivery_policies']=value.get('delivery_policies',{})
    value['assignments']=assignments
    if type(value.get('max_active_tasks',2)) is not int or not 1<=value.get('max_active_tasks',2)<=32:raise ValueError('invalid_capacity')
    return value

def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit host connector assignments and opt-in trusted delivery')
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ('run','work','resume','inspect'):
        action=sub.add_parser(name);action.add_argument('--config',required=True)
        if name in ('resume','inspect'):action.add_argument('attempt_id')
    ready=sub.add_parser('ready')
    ready.add_argument('--project-id',required=True);ready.add_argument('--config',required=True)
    plan=sub.add_parser('plan');plans=plan.add_subparsers(dest='plan_action',required=True)
    for operation in ('import','adopt'):
        action=plans.add_parser(operation)
        for flag in ('project-id','request-id','digest','plan-file','config'):
            action.add_argument('--'+flag,required=True)
    decision=sub.add_parser('decision');ds=decision.add_subparsers(dest='decision_action',required=True)
    for name in ('list','respond'):
        action=ds.add_parser(name);action.add_argument('--config',required=True)
        if name=='respond':action.add_argument('decision_id');action.add_argument('--answer',choices=('approve','decline'),required=True)
    store=app=connector=None;command=None
    try:
        args=parser.parse_args(argv);cfg=load_config(args.config)
        if args.action=='inspect':
            from .diagnostics import inspect_attempt
            try:value=inspect_attempt(cfg['journal'],cfg['connector_id'],args.attempt_id,set(cfg['projects']))
            except ValueError:
                print(json.dumps(dict(version=1,error='inspection_unavailable')));return 4
            print(json.dumps(value,ensure_ascii=True,allow_nan=False));return 0
        if args.action in ('ready','plan'):
            identity(args.project_id)
            if args.project_id not in cfg['projects']:raise ValueError('project_forbidden')
            api=APIClient(cfg['endpoint'],cfg['connector_id'],read_token(cfg['token_file']))
            if args.action=='ready':value=api.ready(args.project_id)
            else:
                identity(args.request_id)
                if re.fullmatch('[0-9a-f]{64}',args.digest) is None:raise ValueError('invalid_digest')
                with Path(args.plan_file).open('rb') as stream:raw=stream.read(65537)
                if len(raw)>65536:raise ValueError('plan_file_limit')
                plan=strict_json(raw.decode('utf-8'))
                if plan_digest(plan)!=args.digest:raise ValueError('plan_digest_mismatch')
                value=api.request('POST','/v1/plans/'+args.plan_action,dict(version=1,project_id=args.project_id,
                    request_id=args.request_id,digest=args.digest,plan=plan))['batch']
            print(json.dumps(value,ensure_ascii=True,allow_nan=False))
            return 0 if args.action=='ready' or value.get('state')=='published' else 4
        if args.action in ('decision','resume'):
            api=APIClient(cfg['endpoint'],cfg['connector_id'],read_token(cfg['token_file']))
            if args.action=='resume':value=api.resume(args.attempt_id)
            elif args.decision_action=='list':value=api.decisions()
            else:value=api.respond(args.decision_id,args.answer)
            print(json.dumps(value,ensure_ascii=True));return 0
        if args.action=='work':return work(cfg,config_path=args.config)
        if 'assignment' not in cfg:raise ValueError('legacy_assignment_required')
        store=ConnectorStore(cfg['journal'],cfg['connector_id'])
        trees=Worktrees(cfg['projects'],store)
        api=APIClient(cfg['endpoint'],cfg['connector_id'],read_token(cfg['token_file']))
        a=cfg['assignment'];connector=Connector(store,api,None,trees)
        attempt=connector.claim(a['project_id'],a['bead_id'])
        if attempt is None:print('connector: API unavailable or assignment not ready');return 3
        command=dict(version=1,command_id=hashlib.sha256(encoded([attempt['attempt_id'],a]).encode('utf-8')).hexdigest(),attempt_id=attempt['attempt_id'],project_id=a['project_id'],base_sha=a['base_sha'],input=a['input'])
        previous=next((c for c in store.commands() if c['command']['command_id']==command['command_id']),None)
        if previous is not None:
            connector.flush();print('connector: '+previous['phase']);return 0 if previous['phase']=='completed' else 4
        # Fresh native check before even launching the owned app-server process.
        connector._validate(command)
        store.receive(command)  # Durable intent before the owned process starts.
        app=AppServer(store,executable=cfg['app_server'],cwd=Path(cfg['projects'][a['project_id']]['repository']))
        connector.app=app;data=connector.execute(command)
        while data['phase']=='executing':
            connector.poll();data=store.command(command['command_id']);time.sleep(.1)
        if data['phase']=='completed':
            store.update(command['command_id'],inspection=app.inspect(data['thread_id']))
        connector.flush()
        print('connector: '+data['phase'])
        if data.get('decision'):print('connector: explicit app-server decision required; affected action paused')
        return 0 if data['phase']=='completed' and not store.pending_events() else 4
    except DecisionRequired as error:
        if store is not None and command is not None:
            store.transition(command['command_id'],'needs_input','unknown',decision=error.decision)
        print('connector: explicit app-server decision required; affected action paused')
        return 4
    except KeyboardInterrupt:
        print('connector: interrupted; retained journal requires reconciliation');return 4
    except Exception:
        print('connector: invalid or unavailable private configuration/state',file=sys.stderr);return 2
    finally:
        cleanup=True
        if app is not None:
            try:app.close()
            except Exception:cleanup=False
        if connector is not None:
            try:connector.close()
            except Exception:cleanup=False
        if store is not None:
            try:
                if app is not None:
                    for data in store.commands():
                        if not cleanup and data['phase'] in ('executing','completed','needs_input'):
                            store.transition(data['command']['command_id'],'needs_reconciliation','unknown',cleanup_confirmed=False)
                        else:store.update(data['command']['command_id'],cleanup_confirmed=cleanup)
            finally:store.close()
        if not cleanup:
            print('connector: owned process cleanup unconfirmed; reconciliation required',file=sys.stderr)
            return 4

def work(cfg,*,config_path=None):
    """Explicit foreground run. Only configured assignments may be admitted.

    A blocked third claim waits in native Beads, never in a second task queue.
    Inherited authorization/model/approval policies remain untouched.
    """
    store=ConnectorStore(cfg['journal'],cfg['connector_id']);connector=None
    try:
        trees=Worktrees(cfg['projects'],store)
        api=APIClient(cfg['endpoint'],cfg['connector_id'],read_token(cfg['token_file']))
        connector=LifecycleConnector(store,api,trees,lambda cwd,request_handler=None:AppServer(store,executable=cfg['app_server'],cwd=Path(cwd),request_handler=request_handler),max_active_tasks=cfg.get('max_active_tasks',2))
        if cfg.get('delivery_projects') or cfg.get('delivery_policies'):
            from .delivery import Delivery,GitHubHost,MainReviewer
            from ..delivery_policy import policies
            from .handoff import HandoffDelivery
            policy=policies(cfg['projects'],cfg.get('delivery_projects',{}),cfg.get('delivery_policies'))
            remote={p:v['repository'] for p,v in policy.items() if v['mode']!='local'}
            automatic={p:v['repository'] for p,v in policy.items() if v['mode']=='task_tower'}
            main_reviewer=MainReviewer(trees,store,lambda cwd:AppServer(store,executable=cfg['app_server'],cwd=Path(cwd)),connector.stop)
            host=GitHubHost(trees,store,remote,reviewer=main_reviewer) if remote else None
            connector.delivery=HandoffDelivery(host,store,trees,policy,Delivery(host,store,automatic) if automatic else None)
        admitted=set();next_admission=0
        if config_path is not None:
            from ..intake_reload import ConfigReloader
            reload=ConfigReloader(config_path,cfg,'assignments',load_config)
        while True:
            connector.tick()
            if time.monotonic()>=next_admission:
                next_admission=time.monotonic()+2
                if config_path is not None:
                    try:cfg=reload()
                    except Exception:continue  # Live transports continue; no new admission.
                for assignment in cfg['assignments']:
                    key=(assignment['project_id'],assignment['bead_id'])
                    if key in admitted:continue
                    attempt=connector.claim(*key)
                    if attempt is None:continue
                    current=api.request('GET','/v1/attempts/'+identity(attempt['attempt_id']))['attempt']
                    if current['phase']=='claimed' and not current.get('managed'):api.dispatch(current['attempt_id'],assignment['base_sha'])
                    admitted.add(key)
            time.sleep(.1)
    except KeyboardInterrupt:return 4
    finally:
        # Keep journals open if containment cleanup is unconfirmed.
        if connector is not None:connector.close()
        store.close()


if __name__=='__main__':raise SystemExit(main())
