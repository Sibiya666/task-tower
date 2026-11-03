"""Installation-owned pipeline limits and fresh, private continuation authority."""
import copy
import hashlib
import json
from pathlib import Path
import re
from .executor_profiles import _path, _private, _pins, profile_fingerprint
from .github_tasks import START, END, parse_metadata
from .dispatch_selection import _pairs, _identity, identity_matches, select_ready
from .project_worker import issue_lifecycle, verified_done

LIMITS=dict(max_active=(2,1,2),interval_seconds=(5,1,60),task_timeout_seconds=(7200,1,86400),role_timeout_seconds=(900,1,3600),max_reworks=(2,0,5),max_processes=(36,6,100),log_max_bytes=(1048576,1,67108864))
NAME=r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}'
FIELDS={'repository','issue','task_id','runner_label','executor_profile','components','allowed_paths','spec_path','plan_path','evidence_dir','checks','ci_substitution','publish'}

def _relative(value):
    if (not isinstance(value,str) or not value or '\\' in value or ':' in value or '\x00' in value or value.startswith('/') or value.endswith('//') or any(p in ('','.','..') or p.casefold()=='.git' for p in value.rstrip('/').split('/'))): raise ValueError('Invalid pipeline path')
    for component in value.rstrip('/').split('/'):
        if component.endswith(('.', ' ')) or any(ord(c)<32 or c in '<>"|?*' for c in component):
            raise ValueError('Platform-ambiguous pipeline path')
        stem=component.split('.',1)[0].casefold()
        if stem in {'con','prn','aux','nul','conin$','conout$'} or re.fullmatch(r'(com|lpt)[1-9¹²³]',stem):
            raise ValueError('Reserved pipeline path')
    return value

def _contains(prefix,path): return path==prefix or (prefix.endswith('/') and path.startswith(prefix))

def load_pipeline_config(path,connections,executor_config):
    """Load strict private JSON; runtime authority retains exact installed bytes."""
    try:
        path=_path(str(path)); _private(path,[c.checkout for c in connections])
        raw=path.read_bytes(); value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs)
        if not isinstance(value,dict) or set(value)-{'version','tasks',*LIMITS} or type(value.get('version')) is not int or value['version']!=1 or not isinstance(value.get('tasks'),list): raise ValueError()
        result=dict(version=1,tasks=[])
        for key,(default,low,high) in LIMITS.items():
            limit=value.get(key,default)
            if type(limit) is not int or not low<=limit<=high: raise ValueError()
            result[key]=limit
        seen=set(); aliases=set()
        for original in value['tasks']:
            if not isinstance(original,dict) or set(original)!=FIELDS: raise ValueError()
            row=copy.deepcopy(original)
            if not isinstance(row['repository'],str) or type(row['issue']) is not int or row['issue']<1: raise ValueError()
            matches=[c for c in connections if c.repository.casefold()==row['repository'].casefold()]
            if len(matches)!=1: raise ValueError()
            connection=matches[0]; row['repository']=connection.repository
            profile=executor_config['profiles'].get(row['executor_profile'])
            if not isinstance(profile,dict) or profile.get('kind') not in ('codex','custom'): raise ValueError('unsupported_kind')
            auth=[r for r in executor_config['allowlist'] if r['repository'].casefold()==row['repository'].casefold() and all(r[k]==row[k] for k in ('issue','task_id','runner_label')) and r['profile']==row['executor_profile']]
            if len(auth)!=1 or profile is None or profile['repository'].casefold()!=row['repository'].casefold() or profile['runner_label']!=row['runner_label'] or Path(profile['checkout'])!=connection.checkout or connection.runner_label!=row['runner_label']: raise ValueError()
            _pins(profile['superpowers'])
            identity=(row['repository'].casefold(),row['issue']); alias=(identity[0],row['task_id'])
            if identity in seen or alias in aliases: raise ValueError()
            seen.add(identity); aliases.add(alias)
            components=row['components']
            if not isinstance(components,list) or not components or any(not isinstance(c,str) or (c!='*' and not re.fullmatch(NAME,c)) for c in components) or len(set(components))!=len(components) or ('*' in components and len(components)!=1): raise ValueError()
            paths=row['allowed_paths']
            if not isinstance(paths,list) or not paths: raise ValueError()
            for p in paths: _relative(p)
            for i,p in enumerate(paths):
                if any(_contains(p.casefold(),q.casefold()) or _contains(q.casefold(),p.casefold()) for q in paths[i+1:]): raise ValueError()
            for key in ('spec_path','plan_path','evidence_dir'):
                _relative(row[key])
                if not any(_contains(p,row[key]) for p in paths): raise ValueError()
            if row['spec_path'].endswith('/') or row['plan_path'].endswith('/') or row['spec_path'].casefold()==row['plan_path'].casefold() or any(row['evidence_dir'].casefold().startswith(row[k].casefold()+'/') for k in ('spec_path','plan_path')) or not row['evidence_dir'].endswith('/') or any(_contains(row['evidence_dir'].casefold(),row[k].casefold()) for k in ('spec_path','plan_path')): raise ValueError()
            checks=row['checks']; ids=set()
            if not isinstance(checks,list) or not checks: raise ValueError()
            for check in checks:
                if not isinstance(check,dict) or set(check)!={'id','argv','timeout_seconds'} or not isinstance(check['id'],str) or not re.fullmatch(NAME,check['id']) or check['id'] in ids: raise ValueError()
                ids.add(check['id']); argv=check['argv']
                if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a or '\x00' in a for a in argv): raise ValueError()
                executable=_path(argv[0])
                if not executable.is_file() or executable.suffix.casefold() in ('.bat','.cmd'): raise ValueError()
                if type(check['timeout_seconds']) is not int or not 1<=check['timeout_seconds']<=3600: raise ValueError()
                check['argv'][0]=str(executable)
            ci=row['ci_substitution']
            if not isinstance(ci,dict) or set(ci)!={'enabled','required_platforms'} or type(ci['enabled']) is not bool or not isinstance(ci['required_platforms'],list): raise ValueError()
            platforms=ci['required_platforms']
            if any(p not in ('windows','macos','linux') for p in platforms) or len(set(platforms))!=len(platforms) or bool(platforms)!=ci['enabled']: raise ValueError()
            publish=row['publish']
            if not isinstance(publish,dict) or set(publish)!={'enabled','remote','base_ref','publisher_account'} or type(publish['enabled']) is not bool or publish['remote']!='origin' or publish['base_ref']!='refs/heads/main' or not isinstance(publish['publisher_account'],str) or publish['publisher_account'].casefold() not in [p.casefold() for p in connection.trusted_publishers]: raise ValueError()
            result['tasks'].append(row)
        result['profiles']=copy.deepcopy(executor_config['profiles'])
        result['policy_sha256']=profile_fingerprint({k:v for k,v in result.items() if k!='profiles'})
        result['_connections']=connections; result['_policy_path']=path; result['_policy_bytes']=raw
        result['_profiles_sha256']=profile_fingerprint(result['profiles'])
        result['_executor_config']=copy.deepcopy(executor_config)
        result['_executor_sha256']=profile_fingerprint(executor_config)
        result['_connection_sha256']=_connection_fingerprint(connections)
        return result
    except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError): raise ValueError('Invalid pipeline configuration') from None

def _text(value):
    if not isinstance(value,str) or value.startswith('\ufeff') or len(value.encode('utf-8'))>1048576: raise ValueError('Invalid criteria text')
    return value.replace('\r\n','\n').replace('\r','\n')

def criteria_snapshot(issue,metadata,repository):
    """Remove exactly one structurally validated metadata block, retaining prose."""
    body=_text(issue['body']); parsed=parse_metadata(body)
    # Reparse with duplicate-key rejection; legacy parser remains unchanged.
    if parsed is None: raise ValueError('Missing task metadata')
    start=body.index(START); end=body.index(END,start)+len(END)
    actual=json.loads(body[start+len(START):end-len(END)],object_pairs_hook=_pairs)
    if actual!=metadata or parsed!=metadata or _identity(metadata) is None: raise ValueError('Invalid task metadata binding')
    if type(issue['number']) is not int or issue['number']<1 or type(issue['id']) is not int or issue['id']<1: raise ValueError('Invalid Issue identity')
    result=dict(version=1,repository=repository.casefold(),issue=issue['number'],issue_id=issue['id'],task_id=_identity(metadata),title=_text(issue['title']),body=body[:start]+body[end:])
    for field in ('kind','mode','blocked_by','blocked_by_task_ids'):
        if field not in metadata: continue
        value=metadata[field]
        if field.startswith('blocked_by'):
            if not isinstance(value,list) or any(not isinstance(v,str) for v in value) or len(set(value))!=len(value): raise ValueError('Invalid dependencies')
            value=sorted(value)
        result[field]=value
    return result

def _connection_fingerprint(connections):
    bindings=[]
    for connection in connections:
        binding=dict(vars(connection))
        binding['checkout']=str(connection.checkout)
        bindings.append(binding)
    return profile_fingerprint(bindings)


def _current(config):
    if config['_policy_path'].read_bytes()!=config['_policy_bytes'] or profile_fingerprint(config['profiles'])!=config['_profiles_sha256']: return False
    if profile_fingerprint(config['_executor_config'])!=config['_executor_sha256'] or _connection_fingerprint(config['_connections'])!=config['_connection_sha256']: return False
    current=load_pipeline_config(config['_policy_path'],config['_connections'],config['_executor_config'])
    active={key:value for key,value in config.items() if not key.startswith('_')}
    installed={key:value for key,value in current.items() if not key.startswith('_')}
    if profile_fingerprint(active)!=profile_fingerprint(installed): return False
    if not callable(config.get('_authority_check')) or not config['_authority_check'](): return False
    return True

def admission_authorized(config,task,snapshot):
    try:
        if not _current(config): return None
        rows=[r for r in config['tasks'] if r==task]
        if len(rows)!=1: return None
        selected=select_ready(snapshot,rows,verify_done=verified_done)
        if not any(all(row[k]==task[k] for k in ('issue','task_id','runner_label')) and row['repository']==task['repository'].casefold() for row in selected['ready']): return None
        project=snapshot[task['repository'].casefold()]; issue=project['issues'][task['issue']]
        criteria=criteria_snapshot(issue,project['metadata'][task['issue']],task['repository'])
        profile=config['profiles'][rows[0]['executor_profile']]
        source,base=_source_current(project,profile)
        if not _current(config): return None
        return dict(version=1,repository=task['repository'].casefold(),issue=task['issue'],issue_id=issue['id'],task_id=task['task_id'],runner_label=task['runner_label'],criteria=criteria,criteria_sha256=profile_fingerprint(criteria),policy_sha256=config['policy_sha256'],profile_id=rows[0]['executor_profile'],profile_fingerprint=profile_fingerprint(profile),source_sha=source,base_sha=base)
    except Exception: return None

def _source_current(project,profile):
    from .executor_worker import _git
    base=project['store'].request('GET','/git/ref/heads/main')
    if not isinstance(base,dict) or not isinstance(base.get('object'),dict): raise ValueError('Missing current main')
    sha=base['object'].get('sha')
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{40}',sha): raise ValueError('Invalid current main')
    source=_git(profile['checkout'],'rev-parse','--verify',profile['source_ref']+'^{commit}')
    if source!=sha: raise ValueError('Source is not current main')
    return source,sha


def _dependencies(snapshot,repository,number,meta):
    # Same resolver and fresh proof contract as dispatch_selection.select_ready.
    from .project_connections import REPOSITORY
    from .dispatch_selection import TASK_ID
    canonical,legacy=set(),set()
    project=snapshot[repository]
    for field in ('blocked_by','blocked_by_task_ids'):
        values=meta.get(field,[])
        if not isinstance(values,list) or any(not isinstance(v,str) for v in values) or len(set(values))!=len(values): return False
        for value in values:
            if field=='blocked_by':
                match=re.fullmatch('('+REPOSITORY+r')#([1-9][0-9]*)',value)
                if not match: return False
                key=match[1].casefold(),int(match[2])
                if key in canonical: return False
                canonical.add(key)
            else:
                if not re.fullmatch(TASK_ID,value): return False
                matches=project['index'].get(value,[])
                if len(matches)!=1: return False
                legacy.add((repository,matches[0]))
    if 'blocked_by' in meta and 'blocked_by_task_ids' in meta and canonical!=legacy: return False
    dependencies=canonical|legacy
    if (repository,number) in dependencies: return False
    for repo,issue in sorted(dependencies):
        dependency=snapshot.get(repo)
        if not dependency or dependency['error'] or issue not in dependency['issues'] or dependency['metadata'].get(issue) is None: return False
        task_id=_identity(dependency['metadata'][issue])
        if not task_id or len(dependency['index'].get(task_id,[]))!=1: return False
        fresh=dependency['store'].get(issue)
        if not isinstance(fresh,dict) or type(fresh.get('number')) is not int or fresh['number']!=issue: return False
        fresh_meta=dependency['store'].metadata(fresh)
        if _identity(fresh_meta)!=task_id or fresh_meta.get('kind')!='task': return False
        if not verified_done(dependency['connection'],dependency['store'],dependency['source'],fresh): return False
    return True


def continuation_authorized(config,run,snapshot):
    """Authorize only a journal-owned run, never a claimed remote run identity."""
    try:
        from .pipeline_journal import PipelineJournal
        import uuid
        if not _current(config) or not isinstance(config.get('_journal'),PipelineJournal): return False
        owner=config['_owner_id']
        if not isinstance(owner,str) or str(uuid.UUID(owner))!=owner: return False
        saved=config['_journal'].status(run['run_id'])
        fields=('run_id','delivery_id','repository','issue','task_id','runner_label','profile_id','profile_fingerprint','policy_sha256','owner_id','admission')
        if any(saved[key]!=run[key] for key in fields) or saved['owner_id']!=owner: return False
        if saved.get('cancel_requested') or saved['state'] not in ('preparing','executing','reviewing','checking','ready','publishing'): return False
        rows=[r for r in config['tasks'] if r['repository'].casefold()==saved['repository'].casefold() and all(r[k]==saved[k] for k in ('issue','task_id','runner_label')) and r['executor_profile']==saved['profile_id']]
        if len(rows)!=1: return False
        profile=config['profiles'][saved['profile_id']]
        if saved['profile_fingerprint']!=profile_fingerprint(profile) or saved['policy_sha256']!=config['policy_sha256']: return False
        repo=saved['repository'].casefold(); project=snapshot[repo]
        if not identity_matches(snapshot,dict(repository=repo,issue=saved['issue'],task_id=saved['task_id'])): return False
        issue=project['issues'][saved['issue']]; meta=project['metadata'][saved['issue']]
        if issue['state']!='open' or meta.get('kind')!='task' or meta.get('mode')!='autonomous': return False
        lifecycle=issue_lifecycle(project['store'],issue)
        if 'remote_attempt' in lifecycle or lifecycle.get('status') not in ('open','running','in_progress'): return False
        if any('remote_attempt' in item or item.get('status','open') not in ('open','running','in_progress') for item in lifecycle.get('_lifecycle_history',[])): return False
        if not _dependencies(snapshot,repo,saved['issue'],meta): return False
        criteria=criteria_snapshot(issue,meta,repo); source,base=_source_current(project,profile)
        admission=dict(version=1,repository=repo,issue=saved['issue'],issue_id=issue['id'],task_id=saved['task_id'],runner_label=saved['runner_label'],criteria=criteria,criteria_sha256=profile_fingerprint(criteria),policy_sha256=config['policy_sha256'],profile_id=saved['profile_id'],profile_fingerprint=profile_fingerprint(profile),source_sha=source,base_sha=base)
        return saved['admission']==admission and saved['source_sha']==source and saved['base_sha']==base and _current(config)
    except Exception: return False
