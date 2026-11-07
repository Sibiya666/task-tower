"""UI-independent explicit assignment runner.

Usage: python -m task_tower.connector.cli run --config <private-file>
No install/autostart/service, role scheduling, merge or close. Configuration is
host-trusted: version, connector_id, endpoint, token_file, journal, app_server,
projects {project_id: {repository, worktree_root}}, assignment
{project_id, bead_id, base_sha, input: {text}}. Journals persist across restarts;
pending commands are fenced. New effects require a fresh explicit assignment.
"""
import argparse
import hashlib
import re
from pathlib import Path
import sys
import time
from .store import ConnectorStore
from .worktrees import Worktrees
from .app_server import AppServer,DecisionRequired
from .client import APIClient,Connector
from ..service.beads import strict_json,identity,bead_id
from ..service.cli import read_token,_absolute
from ..service.store import encoded

def load_config(path):
    path=_absolute(str(path))
    with path.open('rb') as f:raw=f.read(65537)
    if len(raw)>65536:raise ValueError('configuration_limit')
    value=strict_json(raw.decode('utf-8'))
    required={'version','connector_id','endpoint','token_file','journal','app_server','projects','assignment'}
    if not isinstance(value,dict) or set(value)!=required or type(value['version']) is not int or value['version']!=1:raise ValueError('invalid_configuration')
    identity(value['connector_id'])
    for k in ('token_file','journal','app_server'):value[k]=_absolute(value[k])
    if len({value[k] for k in ('token_file','journal','app_server')})!=3:raise ValueError('private_file_collision')
    if not isinstance(value['projects'],dict) or not 1<=len(value['projects'])<=32:raise ValueError('invalid_projects')
    a=value['assignment']
    if not isinstance(a,dict) or set(a)!={'project_id','bead_id','base_sha','input'}:raise ValueError('invalid_assignment')
    identity(a['project_id']);bead_id(a['bead_id'])
    if not isinstance(a['base_sha'],str) or re.fullmatch('[0-9a-f]{40}',a['base_sha']) is None:raise ValueError('exact_sha_required')
    if not isinstance(a['input'],dict) or set(a['input'])!={'text'} or not isinstance(a['input']['text'],str) or not 1<=len(a['input']['text'])<=32768:raise ValueError('invalid_input')
    if a['project_id'] not in value['projects']:raise ValueError('project_forbidden')
    return value

def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit host connector assignment; merge disabled')
    sub=parser.add_subparsers(dest='action',required=True);run=sub.add_parser('run');run.add_argument('--config',required=True)
    store=app=None;command=None
    try:
        args=parser.parse_args(argv);cfg=load_config(args.config)
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

if __name__=='__main__':raise SystemExit(main())
