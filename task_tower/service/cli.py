"""Explicit foreground entry point. No install, autostart or production DB migration.

Private config keys: version, executable, projects {id: absolute directory},
journal, connectors {id: {token_file, projects}}, approved_plans {project: [sha256]},
port, poll_seconds. Approval digests are operator inputs, never client assertions.
"""
import argparse
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from .api import make_server
from .beads import Beads, identity, strict_json, environment
from .store import Store
from ..project_connections import safe_config_path


def _absolute(value):
    if not isinstance(value,str) or not Path(value).is_absolute():raise ValueError('absolute_path_required')
    return safe_config_path(Path(value))


def _windows_private(path):
    # Read-only ACL verification, no icacls mutations or policy/account changes.
    script = """$ErrorActionPreference='Stop'
$acl=[System.IO.File]::GetAccessControl($env:TOWER_TOKEN_CHECK_PATH)
$me=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
if($owner -ne $me){exit 1}
$allowed=@($me,'S-1-5-18','S-1-5-32-544')
foreach($r in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){
 if($r.AccessControlType -eq 'Allow' -and $r.IdentityReference.Value -notin $allowed){exit 1}
}
if($acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]).Count -eq 0){exit 1}
exit 0
"""
    exe=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    env=environment(path.parent);env['TOWER_TOKEN_CHECK_PATH']=str(path)
    result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-Command',script],
        env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode!=0:raise ValueError('token_not_private')


def read_token(path):
    path=_absolute(str(path));info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>256 or info.st_nlink!=1:
        raise ValueError('invalid_token_file')
    if os.name=='nt':_windows_private(path)
    elif info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('token_not_private')
    with path.open('rb') as stream:raw=stream.read(257)
    token=raw.decode('ascii').strip()
    if not 32<=len(token)<=256 or not token.isalnum():raise ValueError('invalid_token')
    return token


def load_config(path,*,document=None):
    path=_absolute(str(path))
    if document is None:
        with path.open('rb') as stream:raw=stream.read(65537)
    else:raw=document
    if len(raw)>65536:raise ValueError('config_limit')
    value=strict_json(raw.decode('utf-8'))
    required={'version','executable','projects','journal','connectors','approved_plans','port','poll_seconds'}
    if not isinstance(value,dict) or set(value)-{'max_active_tasks','delivery_projects','delivery_policies','native_profiles'} != required or type(value['version']) is not int or value['version']!=1:
        raise ValueError('invalid_configuration')
    exe=_absolute(value['executable']);journal=_absolute(value['journal'])
    if not isinstance(value['projects'],dict) or not 1<=len(value['projects'])<=32:
        raise ValueError('invalid_projects')
    projects={}
    for key,directory in value['projects'].items():
        if not isinstance(directory,str) or not Path(directory).is_absolute():raise ValueError('invalid_directory')
        path=Path(directory);safe_config_path(path/'.tower-path-guard')
        if not path.is_dir():raise ValueError('invalid_directory')
        projects[identity(key)]=path
    if len({str(p.resolve()).casefold() for p in projects.values()})!=len(projects):raise ValueError('project_alias')
    if not isinstance(value['connectors'],dict) or not 1<=len(value['connectors'])<=32:
        raise ValueError('invalid_connectors')
    connectors={}
    for key,entry in value['connectors'].items():
        identity(key)
        if not isinstance(entry,dict) or set(entry)!={'token_file','projects'}:raise ValueError('invalid_connector')
        token_path=_absolute(entry['token_file'])
        if token_path==journal or token_path==exe:raise ValueError('private_file_collision')
        connectors[key]=dict(token=read_token(token_path),projects=entry['projects'])
    approved=value['approved_plans']
    from .native_profiles import profiles
    profiles(projects,value.get('native_profiles',{}))
    from ..delivery_policy import policies
    policies(projects,value.get('delivery_projects',{}),value.get('delivery_policies'))
    if not isinstance(approved,dict) or set(approved)-set(projects):raise ValueError('invalid_approvals')
    for digests in approved.values():
        if (not isinstance(digests,list) or len(digests)>1000
                or any(not isinstance(d,str) or re.fullmatch('[0-9a-f]{64}',d) is None for d in digests)):
            raise ValueError('invalid_approvals')
    return dict(executable=exe,projects=projects,journal=journal,connectors=connectors,native_profiles=value.get('native_profiles',{}),
                approved_plans=approved,delivery_projects=value.get('delivery_projects',{}),delivery_policies=value.get('delivery_policies',{}),max_active_tasks=value.get('max_active_tasks',2),port=value['port'],poll_seconds=value['poll_seconds'])


def main(argv=None):
    parser=argparse.ArgumentParser(description='Foreground loopback Beads service')
    parser.add_argument('--config',required=True)
    parser.add_argument('--container-network',action='store_true',help='Linux Docker namespace only; host publishing must be loopback')
    try:
        args=parser.parse_args(argv)
        config=load_config(args.config)
        beads=Beads(config['executable'],config['projects'],native_profiles=config.get('native_profiles'))
        store=Store(config['journal'],beads,approved_plans=config['approved_plans'],delivery_projects=config['delivery_projects'],max_active_tasks=config['max_active_tasks'],delivery_policies=config.get('delivery_policies'))
        try:
            server=make_server(store,config['connectors'],host='0.0.0.0' if args.container_network else '127.0.0.1',
                               port=config['port'],poll_seconds=config['poll_seconds'],container_network=args.container_network)
            try:
                from ..intake_reload import ConfigReloader
                reload=ConfigReloader(args.config,config,'approved_plans',load_config)
                server.timeout=.5
                while True:
                    try:
                        current=reload()
                        with store.lock:store.approved_plans=current['approved_plans']
                        config=current
                    except Exception:pass  # Reject invalid file; retain prior operator authority.
                    server.handle_request()
            except KeyboardInterrupt:pass
            finally:server.server_close()
        finally:store.close()
        return 0
    except (Exception,):
        print('task-tower service: invalid or unavailable private configuration/state',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
