"""Finite, read-only discovery; unsupported observations never grant execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .opencode_files import identity, read_bound, safe_path

from .executor_profiles import child_environment

AUTH_NAMES=frozenset(('OPENCODE_PASSWORD','OPENCODE_SERVER_PASSWORD','OPENCODE_CONSOLE_TOKEN'))
FIXED_NAMES=frozenset(('HOME','USERPROFILE','HOMEDRIVE','HOMEPATH','XDG_CONFIG_HOME','XDG_DATA_HOME',
    'XDG_CACHE_HOME','XDG_STATE_HOME','ProgramData','TMPDIR','TMP','TEMP','PATH','PATHEXT','COMSPEC',
    'SHELL','BASH_ENV','ENV','NODE_OPTIONS','NODE_PATH','BUN_OPTIONS','LD_PRELOAD','LD_LIBRARY_PATH',
    'DYLD_INSERT_LIBRARIES','DYLD_LIBRARY_PATH',
    'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'))
ALLOWED_OPENCODE=frozenset(('OPENCODE_CONFIG_DIR','OPENCODE_CLIENT','OPENCODE_DISABLE_AUTOUPDATE'))
INJECTION=frozenset(('BASH_ENV','ENV','NODE_OPTIONS','NODE_PATH','BUN_OPTIONS','LD_PRELOAD',
                     'LD_LIBRARY_PATH','DYLD_INSERT_LIBRARIES','DYLD_LIBRARY_PATH'))


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def opencode_environment(environ:dict[str,str],worktree:str)->dict[str,str]:
    result=child_environment(environ)
    result.update(PWD=str(worktree),OPENCODE_DISABLE_AUTOUPDATE='1')
    return result


def _environment_map(environ,platform):
    if not isinstance(environ,dict) or any(not isinstance(key,str) for key in environ): raise ValueError('invalid_environment')
    if platform=='windows':
        if len({key.casefold() for key in environ})!=len(environ): raise ValueError('environment_case_collision')
        return {key.upper():value for key,value in environ.items()}
    return environ


def environment_binding(environ:dict[str,str],platform:str)->dict:
    values=_environment_map(environ,platform)
    fixed={name.upper() for name in FIXED_NAMES} if platform=='windows' else FIXED_NAMES
    names=sorted(fixed|{name for name in values if name.startswith(('OPENCODE_','OTEL_')) and name not in AUTH_NAMES})
    if len(names)>4096: raise ValueError('environment_limit')
    present=[];bound=[]
    for name in names:
        exists=name in values
        present.append([name,exists])
        value=values[name] if exists else None
        if exists and not isinstance(value,str): raise ValueError('invalid_environment')
        bound.append([name,value])
    return dict(names=names,presence_sha256=_sha(present),values_sha256=_sha(bound))


def environment_reasons(environ:dict[str,str],platform:str)->list[str]:
    values=_environment_map(environ,platform)
    for name in values:
        if name in AUTH_NAMES: continue
        if (name in INJECTION or name.startswith(('OTEL_','LD_','DYLD_','NODE_','BUN_','JSC_'))
                or name.startswith('OPENCODE_') and name not in ALLOWED_OPENCODE):
            return ['unsupported_environment']
    return []


# Every family is version-qualified, including unsupported families. A listed
# source family is not a native authority bit. Presence can only add a blocker.
SOURCE_TABLE={
    'revision':'9bbb8ce18c80f099e0e448775f59d965ead40a21',
    'ancestors':('opencode.json','opencode.jsonc','.opencode','.agents','.claude'),
    'directories':('agent','agents','mode','modes','command','commands','skill','skills','plugin','plugins'),
    'json':('opencode.json','opencode.jsonc'),
    'agent_patterns':('{agent,agents}/**/*.md','{mode,modes}/*.md'),
    'command_patterns':('{command,commands}/**/*.md',),
    'skill_patterns':('skills/**/SKILL.md','skills/*.md'),
    'plugin_patterns':('{plugin,plugins}/*.{js,ts}','{plugin,plugins}/*/'),
    'cli':('cli.json','tui.json'),
    'instructions':('global_config/AGENTS.md','worktree-to-home-or-project/AGENTS.md'),
    'forbidden_state':('kv.json','auth.json','storage','*.db','*.db-wal','*.db-shm','*.db-journal'),
    'anchors':('core/src/config/discovery.ts','core/src/config.ts','core/src/config/variable.ts',
        'core/src/config/plugin/source.ts','core/src/plugin/source-directory.ts','core/src/plugin/module.ts',
        'core/src/config/plugin/agent.ts','core/src/config/plugin/command.ts',
        'core/src/config/plugin/compatibility.ts','core/src/config/plugin/skill-scan.ts',
        'core/src/config/plugin/instruction.ts','core/src/instruction-discovery.ts',
        'core/src/wellknown.ts','core/src/kv.ts','core/src/credential.ts','core/src/database/database.ts',
        'cli/src/index.ts','cli/src/config/config.ts','cli/src/config/migrate.ts','cli/src/database-path.ts',
        'cli/src/server-process.ts','cli/src/services/standalone.ts','cli/src/services/updater.ts',
        'util/src/global.ts','util/src/global-roots.ts','plugin/src/runtime.ts','plugin/src/runtime-modules.ts'),
}


def _supported_config(value,role):
    if not isinstance(value,dict):return False
    allowed={'$schema'} if role=='cli_json' else {'$schema','model','default_agent','permissions','update','share'}
    if set(value)-allowed:return False
    if '$schema' in value and not isinstance(value['$schema'],str):return False
    if 'default_agent' in value and (not isinstance(value['default_agent'],str) or len(value['default_agent'])>1024):return False
    if 'update' in value and value['update'] not in ('disable','notify','auto'):return False
    if 'share' in value and value['share'] not in ('manual','disabled'):return False
    if 'model' in value:
        model=value['model']
        if isinstance(model,str):
            if len(model)>1024 or not re.fullmatch(r'[^/#]+/[^#]+(?:#[^#]+)?',model):return False
        elif isinstance(model,dict):
            if not {'providerID','model'}<=set(model) or set(model)-{'providerID','model','variant'}:return False
            if any(not isinstance(item,str) or not item or len(item)>1024 for item in model.values()):return False
            if '/' in model['providerID'] or any('#' in item for item in model.values()):return False
        else:return False
    if 'permissions' in value:
        rules=value['permissions']
        if not isinstance(rules,list) or len(rules)>256:return False
        for rule in rules:
            if not isinstance(rule,dict) or set(rule)!={'action','resource','effect'} or rule['effect'] not in ('allow','deny','ask'):
                return False
            if any(not isinstance(rule[key],str) or not rule[key] or len(rule[key])>4096 for key in ('action','resource')):return False
    return True


def _roots(scope,environ):
    platform=scope['platform'];env=_environment_map(environ,platform)
    def value(name): return env.get(name.upper() if platform=='windows' else name)
    home=value('USERPROFILE' if platform=='windows' else 'HOME')
    if not home or str(safe_path(home))!=scope['home']: raise ValueError('unsupported_home_source')
    home=Path(home)
    roots={
        'data':Path(value('XDG_DATA_HOME') or home/'.local/share')/'opencode',
        'cache':Path(value('XDG_CACHE_HOME') or home/'.cache')/'opencode',
        'state':Path(value('XDG_STATE_HOME') or home/'.local/state')/'opencode',
        'config':Path(value('OPENCODE_CONFIG_DIR') or (Path(value('XDG_CONFIG_HOME') or home/'.config')/'opencode')),
    }
    temp=(value('TEMP') or value('TMP')) if platform=='windows' else value('TMPDIR') or '/tmp'
    if not temp: raise ValueError('unsupported_tmp_source')
    roots['tmp']=Path(temp)/'opencode'
    roots.update(log=roots['data']/'log',repos=roots['data']/'repos',bin=roots['cache']/'bin')
    for name,path in roots.items(): roots[name]=safe_path(str(path))
    system=Path(value('ProgramData') or 'C:\\ProgramData')/'opencode' if platform=='windows' else Path('/Library/Application Support/opencode' if platform=='macos' else '/etc/opencode')
    if str(roots['config'])!=scope['global_config'] or str(system)!=scope['system_config']:
        raise ValueError('source_root_mismatch')
    return roots


def _ancestors(path):
    rows=[path,*path.parents]
    if len(rows)>64: raise ValueError('ancestor_limit')
    return rows


def _instruction_paths(worktree,home,global_config):
    stop=home if worktree.is_relative_to(home) else worktree
    paths=[global_config/'AGENTS.md']
    for parent in _ancestors(worktree):
        paths.append(parent/'AGENTS.md')
        if parent==stop:break
    return sorted(set(paths),key=str)


class _Observation:
    def __init__(self,grants):
        self.rows={};self.reasons=set();self.diagnostics=[];self.grants=grants or {};self.total=0

    def deny(self,reason,path=None,info=None):
        self.reasons.add(reason)
        if path is not None and len(self.diagnostics)<4096:
            row=dict(path=str(path),reason=reason)
            if info is not None:
                row.update(identity=identity(info),bytes=info.st_size)
            self.diagnostics.append(row)

    def put(self,row):
        key=row['path'].casefold()
        if key not in self.rows and len(self.rows)>=4096: raise ValueError('inventory_entry_limit')
        self.rows.setdefault(key,row)

    def missing(self,path,role):
        parent=path;parts=[]
        while True:
            try: info=parent.lstat();break
            except FileNotFoundError:
                if parent==parent.parent: raise ValueError('unresolved_parent')
                parts.insert(0,parent.name);parent=parent.parent
        ident=identity(info)
        if ident['kind']!='directory' or not parts: raise ValueError('unresolved_parent')
        self.put(dict(kind='missing',path=str(path),role=role,
                      parent_identity=dict(path=str(parent),identity=ident,missing_components=parts)))

    def members(self,path):
        result=[]
        with os.scandir(path) as entries:
            for entry in entries:
                if len(result)>=256: raise ValueError('directory_member_limit')
                # Windows DirEntry.stat exposes zero file IDs. lstat performs
                # the actual platform identity query without following links.
                info=Path(entry.path).lstat();ident=identity(info)
                result.append(dict(name=entry.name,kind=ident['kind'],identity=ident))
        result.sort(key=lambda row:row['name'])
        names=[row['name'].casefold() for row in result]
        if len(set(names))!=len(names): raise ValueError('membership_case_collision')
        return result

    def directory(self,path,role,*,startup=False,credential=False,closed_files=False):
        path=safe_path(str(path))
        try: before=path.lstat()
        except FileNotFoundError:
            self.missing(path,role)
            if startup:self.deny('unsupported_startup_directory_creation')
            return False
        ident=identity(before)
        if ident['kind']!='directory':
            self.deny('unsupported_directory_kind',path,before);return False
        first=self.members(path)
        if identity(path.lstat())!=ident or self.members(path)!=first: raise ValueError('discovery_changed')
        self.put(dict(kind='directory',path=str(path),role=role,identity=ident,members=first))
        if credential:
            for entry in first:
                name=entry['name'].casefold()
                if name in ('kv.json','auth.json','storage','credentials.json','accounts.json') or re.fullmatch(r'.*\.db(?:-(?:wal|shm|journal))?',name):
                    self.deny('unsupported_credential_dependent_discovery')
        if closed_files and any(row['kind']=='file' for row in first):
            self.deny('unsupported_unqualified_startup_file')
        return True

    def file(self,path,role,*,forbidden=False,migration=False):
        path=safe_path(str(path))
        try: info=path.lstat()
        except FileNotFoundError:
            self.missing(path,role);return
        ident=identity(info)
        if ident['kind']!='file' or info.st_nlink!=1: raise ValueError('unsafe_eligible_file')
        if forbidden:
            self.deny('unsupported_credential_dependent_discovery',path,info);return
        if migration:
            self.deny('unsupported_startup_migration',path,info);return
        grant=self.grants.get(str(path))
        if not isinstance(grant,dict):
            self.deny('unsupported_unqualified_config_file',path,info);return
        if grant.get('identity')!=ident or grant.get('bytes')!=info.st_size or grant.get('role')!=role:
            self.deny('approved_file_changed');return
        if self.total+info.st_size>8388608: raise ValueError('inventory_byte_limit')
        try: data=read_bound(str(path),limit=1048576,expected=grant['sha256'],utf8=True)
        except (OSError,ValueError,UnicodeError):
            self.deny('approved_file_changed');return
        self.total+=len(data)
        self.put(dict(kind='file',path=str(path),role=role,identity=ident,bytes=len(data),sha256=grant['sha256']))
        if role=='instruction':
            if b'{env:' in data or b'{file:' in data:self.deny('unsupported_instruction_reference')
            return
        # Supported JSON is intentionally a closed non-executable subset.
        # Other existing settings stay intact and make this launch unsupported.
        from .opencode_adapter import _json
        try:
            value=_json(data)
            if b'{env:' in data or b'{file:' in data or not _supported_config(value,role):
                self.deny('unsupported_config_semantics')
        except (ValueError,UnicodeError): self.deny('unsupported_config_semantics')

    def config_directory(self,path,role):
        present=self.directory(path,role)
        if not present:return False
        for name in SOURCE_TABLE['json']:self.file(path/name,'config_json')
        for name in SOURCE_TABLE['directories']:
            target=path/name
            exists=self.directory(target,'native_config_directory')
            if exists:
                # These are known native input families, not silently ignored
                # arbitrary descendants. Their formats remain unqualified.
                self.deny('unsupported_plugin_surface' if name in ('plugin','plugins') else 'unsupported_native_config_surface')
        return present

    def stable(self):
        for row in self.rows.values():
            path=safe_path(row['path'])
            if row['kind']=='missing':
                if path.exists() or identity(Path(row['parent_identity']['path']).lstat())!=row['parent_identity']['identity']:
                    raise ValueError('discovery_changed')
            elif identity(path.lstat())!=row['identity'] or row['kind']=='directory' and self.members(path)!=row['members']:
                raise ValueError('discovery_changed')


def _collect(scope,*,worktree,environ,_grants=None):
    """Private grant composition: only verify_preflight supplies pinned inventory.

    This helper does not execute anything or create qualification authority.
    The public collector deliberately has no file-content grant parameter.
    """
    from .opencode_adapter import _scope,validate_inventory
    environment={};observation=_Observation(_grants)
    try:
        try:_scope(scope)
        except (OSError,ValueError,TypeError,KeyError):raise ValueError('invalid_scope')
        environment=environment_binding(environ,scope['platform'])
        observation.reasons.update(environment_reasons(environ,scope['platform']))
        tree=safe_path(worktree);runs=Path(scope['runs_root'])
        if identity(tree.lstat())['kind']!='directory':raise ValueError('invalid_worktree')
        relative=tree.relative_to(runs)
        import uuid
        if len(relative.parts)!=3 or relative.parts[-1]!='worktree' or any(str(uuid.UUID(value))!=value for value in relative.parts[:2]):
            raise ValueError('invalid_worktree_template')
        roots=_roots(scope,environ)
        if any(runs.is_relative_to(root) or root.is_relative_to(runs) for root in roots.values()):
            raise ValueError('unsupported_output_root_overlap')
        for name,path in roots.items():observation.directory(path,'startup_'+name,startup=True,credential=name in ('data','state','config'),closed_files=name in ('data','cache','state'))
        generated={runs,tree.parent,tree.parent.parent}
        for path in _instruction_paths(tree,Path(scope['home']),roots['config']):
            if path.parent not in generated:observation.file(path,'instruction')
        for ancestor in _ancestors(tree):
            if ancestor in generated:
                from .opencode_templates import CANDIDATES
                roles={'.agents':'compatibility_root','.claude':'compatibility_root','.opencode':'project_directory',
                       'AGENTS.md':'instruction','opencode.json':'project_config','opencode.jsonc':'project_config'}
                for name in CANDIDATES:
                    path=safe_path(str(ancestor/name))
                    try:info=path.lstat()
                    except FileNotFoundError:observation.missing(path,roles[name])
                    else:observation.deny('unsupported_run_ancestor_candidate',path,info)
                continue
            for name in SOURCE_TABLE['json']:observation.file(ancestor/name,'project_config')
            observation.config_directory(ancestor/'.opencode','project_directory')
            for name in ('.agents','.claude'):
                path=ancestor/name
                if observation.directory(path,'compatibility_root'):
                    observation.deny('unsupported_compatibility_surface')
                    observation.directory(path/'skills','compatibility_skills')
        observation.config_directory(roots['config'],'global_config')
        observation.config_directory(Path(scope['system_config']),'system_config')
        for name in ('.agents','.claude'):
            path=Path(scope['home'])/name
            if observation.directory(path,'home_compatibility_root'):
                observation.deny('unsupported_compatibility_surface')
                observation.directory(path/'skills','compatibility_skills')
        observation.file(roots['config']/'cli.json','cli_json')
        observation.file(roots['config']/'tui.json','cli_migration',migration=True)
        observation.file(roots['state']/'kv.json','native_state',forbidden=True)
        for name in ('opencode.db','auth.json'):observation.file(roots['data']/name,'native_state',forbidden=True)
        if scope['platform']=='macos':
            import pwd
            username=pwd.getpwuid(os.getuid()).pw_name
            for path in (Path('/Library/Managed Preferences')/username/'ai.opencode.managed.plist',Path('/Library/Managed Preferences/ai.opencode.managed.plist')):
                observation.file(path,'managed_preference',forbidden=True)
        observation.stable()
        validate_inventory(list(observation.rows.values()))
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
        reason=str(error) if isinstance(error,ValueError) and re.fullmatch('[a-z_]{1,80}',str(error)) else 'discovery_unavailable'
        observation.reasons.add(reason)
    return dict(complete=not observation.reasons,worktree=worktree,inventory=sorted(observation.rows.values(),key=lambda row:row['path'].casefold()),
                environment=environment,reasons=sorted(observation.reasons),diagnostics=observation.diagnostics)


def collect_opencode_discovery(scope:dict,*,worktree:str,environ:dict[str,str])->dict:
    first=_collect(scope,worktree=worktree,environ=environ)
    return _collect(scope,worktree=worktree,environ=environ) if 'discovery_changed' in first['reasons'] else first


def compare_opencode_discovery(expected:dict,observed:dict)->list[str]:
    reasons=set(observed.get('reasons',[]))
    if observed.get('complete') is not True:reasons.add('discovery_incomplete')
    try:
        if any(row.get('kind')=='worktree_template' for row in expected['inventory']):
            from .opencode_templates import inventory_matches
            same=inventory_matches(expected['inventory'],observed,expected['scope'])
        else:same=sorted(expected['inventory'],key=lambda row:row['path'].casefold())==sorted(observed['inventory'],key=lambda row:row['path'].casefold())
        if not same:reasons.add('inventory_changed')
    except (ValueError,KeyError,TypeError,AttributeError):reasons.add('inventory_changed')
    if expected.get('environment')!=observed.get('environment'):reasons.add('environment_changed')
    return sorted(reasons)
