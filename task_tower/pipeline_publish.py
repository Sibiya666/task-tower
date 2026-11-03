"""Host-only projections and one durably fenced publication effect.

Stage receipts continue to bind the accepted test checkpoint. A final host
commit adds only reproducible Markdown; it never creates stage acceptance.
Unknown effects are observation-only and this module has no integration API.
"""

from .capacity_policy import require_legacy_capacity
import hashlib
from pathlib import Path
import re
from urllib.parse import quote

from .github_tasks import GitHubTasks
from .pipeline_inputs import (_git, _ordinary, _relative, canonical_artifact,
                              canonical_json, digest_manifest, product_manifest,
                              freeze_checkpoint)
from .pipeline_journal import STAGES
from .project_connections import safe_config_path


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _accepted(run, history):
    if run['stage'] != 'test' or run['manifest'] is None:
        raise ValueError('Missing current stage acceptance')
    selected=[]
    for stage in STAGES:
        rows=[v for v in history['verdicts'] if v['stage']==stage and not v['superseded']]
        if len(rows)!=1 or rows[0]['decision']!='approve':
            raise ValueError('Missing current stage acceptance')
        v=rows[0]; body=v['body']; manifest=body['manifest']
        if digest_manifest(body)!=v['receipt_sha256'] or digest_manifest(manifest)!=v['input_sha256']:
            raise ValueError('Invalid accepted receipt')
        if v['executor_instance_id']==v['reviewer_instance_id']:
            raise ValueError('Nonindependent receipt')
        for key in ('run_id','repository','issue','issue_id','task_id','source_sha','base_sha','policy_sha256','criteria_sha256','superpowers_sha256'):
            if manifest[key]!=run[key]: raise ValueError('Receipt identity mismatch')
        if manifest['prior_verdict_sha256']!=(selected[-1]['receipt_sha256'] if selected else None):
            raise ValueError('Broken accepted receipt chain')
        selected.append(v)
    if selected[-1]['input_sha256']!=run['input_sha256'] or selected[-1]['generation']!=run['generation']:
        raise ValueError('Stale test acceptance')
    return selected


def project_evidence(run:dict, history:dict, task_policy:dict)->dict:
    """Reproduce public facts solely from immutable accepted host history.

    The returned private projection manifest excludes itself and mutable cards.
    Callers obtain history from the live journal, never a role result.
    """
    receipts=_accepted(run,history)
    if (task_policy['repository'].casefold()!=run['repository'] or
            any(task_policy[k]!=run[k] for k in ('issue','task_id','runner_label')) or
            task_policy['executor_profile']!=run['profile_id']):
        raise ValueError('Missing private publication mapping')
    directory=_relative(task_policy['evidence_dir'])
    lines=['# Task Tower stage evidence','',
        'Repository: '+run['repository'], 'Issue: '+str(run['issue']),
        'Task: '+run['task_id'], 'Run: '+run['run_id'],'',
        'Accepted product SHA256: '+run['manifest']['product_sha256'],
        'Accepted test checkpoint: '+run['manifest']['checkpoint_sha'],'',
        'This records stage acceptance. Whole PR and main acceptance remain required.','']
    for v in receipts:
        lines.extend(['## '+v['stage'],'',
            'Generation: '+str(v['generation']), 'Input SHA256: '+v['input_sha256'],
            'Receipt SHA256: '+v['receipt_sha256'],
            'Executor instance: '+v['executor_instance_id'],
            'Reviewer instance: '+v['reviewer_instance_id'],''])
    lines.extend(['## Host checks',''])
    checks=[a for a in history['attempts'] if a['role']=='host_check' and
            a['launch_intent']['checkpoint_sha']==run['manifest']['checkpoint_sha']]
    for a in checks:
        e=a['evidence'] or {}
        lines.append('Check '+a['check_id']+': '+a['state']+
            '; exit '+str(e.get('exit_code'))+'; cleanup '+str(e.get('cleanup_confirmed'))+
            '; source unchanged '+str(e.get('source_unchanged'))+'.')
    lines.extend(['','## Superseded history',''])
    for v in history['verdicts']:
        if v['superseded']:
            lines.append(v['stage']+' generation '+str(v['generation'])+': '+v['receipt_sha256']+'.')
    lines.extend(['','Limitations: local fixtures do not establish installed runtime or remote publication readiness.',''])
    name=directory+'pipeline-'+run['run_id']+'.md'
    files={name:'\n'.join(lines).encode('utf-8')}
    hashes={p:_sha(data) for p,data in files.items()}
    manifest=dict(version=1,run_id=run['run_id'],task_id=run['task_id'],product_sha256=run['manifest']['product_sha256'],files=[dict(path=p,scheme='sha256-utf8-lf-v2',sha256=hashes[p]) for p in sorted(hashes)])
    return dict(files=files,hashes=hashes,manifest=manifest,manifest_sha256=digest_manifest(manifest))


def _final(run,history,projection):
    rows=[e for e in history['effects'] if e['kind']=='commit' and e['intent']['evidence_manifest_sha256'] is not None]
    if not rows:return None
    if len(rows)!=1:raise ValueError('Ambiguous host checkpoint')
    e=rows[0]; intent=e['intent']
    if (e['status']!='completed' or intent['parent']!=run['manifest']['checkpoint_sha'] or
            intent['contributing_executor_attempt_id'] is not None or
            intent['evidence_manifest_sha256']!=projection['manifest_sha256'] or
            e['observation']['commit_sha']!=run['checkpoint_sha']):
        raise ValueError('Invalid host checkpoint')
    if _commit_object(run,e,projection)['commit_sha']!=run['checkpoint_sha']:raise ValueError('Changed host checkpoint')
    return e


def _commit_object(run,effect,projection):
    """Observe only the current branch object, never search orphaned objects."""
    intent=effect['intent'];root=run['worktree']
    if (intent['kind']!='commit' or intent['parent']!=run['manifest']['checkpoint_sha'] or
            intent['branch']!=run['branch'] or intent['message']!='Task Tower publication '+run['run_id'] or
            intent['contributing_executor_attempt_id'] is not None or
            intent['evidence_manifest_sha256']!=projection['manifest_sha256']):
        raise ValueError('Invalid host commit intent')
    if _git(root,'symbolic-ref','--quiet','HEAD').decode().strip()!='refs/heads/'+run['branch']:raise ValueError('Changed host branch')
    head=_git(root,'rev-parse','HEAD').decode().strip()
    if _git(root,'rev-list','--parents','-n','1',head).decode().split()!=[head,intent['parent']]:raise ValueError('Host commit parent mismatch')
    if _git(root,'rev-parse',head+'^{tree}').decode().strip()!=intent['tree']:raise ValueError('Host commit tree mismatch')
    if not 1<=int(_git(root,'cat-file','-s',head))<=65536:raise ValueError('Host commit size limit')
    raw=_git(root,'cat-file','commit',head)
    if raw.split(b'\n\n',1)[-1]!=(intent['message']+'\n').encode():raise ValueError('Host commit message mismatch')
    changed=set(filter(None,_git(root,'diff','--name-only','-z',intent['parent'],head,'--').decode().split('\0')))
    if changed!=set(projection['files']):raise ValueError('Host checkpoint changes product')
    for name,data in projection['files'].items():
        if _git(root,'cat-file','blob',head+':'+name)!=data:raise ValueError('Host checkpoint evidence mismatch')
    return dict(status='completed',commit_sha=head,tree_sha=intent['tree'])


def _projection_current(run,task,journal,projection,head):
    private=safe_config_path(journal.path.parent/('projection-'+run['run_id']+'.json'))
    _ordinary(private)
    if private.read_bytes()!=canonical_json(projection['manifest']):raise ValueError('Changed private projection')
    policy=dict(task,source_sha=run['source_sha'],expected_head=head,git_dir=run['git_dir'],branch=run['branch'],_host_evidence=projection['hashes'])
    if digest_manifest(product_manifest(Path(run['worktree']),policy))!=run['manifest']['product_sha256']:raise ValueError('stale_input')
    for name,data in projection['files'].items():
        if (Path(run['worktree'])/name).read_bytes()!=data:raise ValueError('Changed host evidence')


def validate_publication_current(run,task,journal):
    """Validate actual final HEAD without replacing the immutable stage input.

    This helper is also the controller's sole final-checkpoint exception.
    It reconstructs evidence from actual journal receipts and verifies Git blobs,
    exact current files and product digest; no callback can grant acceptance.
    """
    history=journal.history(run['run_id']); projection=project_evidence(run,history,task)
    final=_final(run,history,projection)
    if final is None:raise ValueError('Missing host checkpoint')
    _projection_current(run,task,journal,projection,run['checkpoint_sha'])
    return projection


def _connection(config,run):
    rows=[c for c in config['_connections'] if c.repository.casefold()==run['repository']]
    if len(rows)!=1:raise ValueError('Missing connected repository')
    return rows[0]


def _remote(run):
    """Reject remapping/push URLs and accept only the connected GitHub identity."""
    root=run['worktree']; repository=run['repository']
    config=_git(root,'config','--list').decode()
    if any(line.casefold().startswith(('url.','remote.origin.pushurl=','remote.origin.push=','remote.origin.mirror=','remote.origin.receivepack=','remote.origin.uploadpack=','remote.origin.proxy=','remote.origin.vcs=','core.sshcommand=','core.gitproxy=','push.followtags=')) for line in config.splitlines()):
        raise ValueError('Unsafe publication remote')
    urls=_git(root,'remote','get-url','--all','origin').decode().splitlines()
    allowed={'https://github.com/'+repository,'https://github.com/'+repository+'.git',
             'git@github.com:'+repository,'git@github.com:'+repository+'.git',
             'ssh://git@github.com/'+repository,'ssh://git@github.com/'+repository+'.git'}
    if len(urls)!=1 or urls[0].casefold() not in allowed:raise ValueError('Wrong publication repository')


def _remote_head(run):
    result=_git(run['worktree'],'ls-remote','--refs','origin','refs/heads/'+run['branch']).decode().splitlines()
    if not result:return None
    if len(result)!=1 or result[0].split('\t')!=[run['checkpoint_sha'],'refs/heads/'+run['branch']]:
        raise ValueError('Changed remote branch')
    return run['checkpoint_sha']


def _body(run,marker):
    return ('Task Tower accepted stage output for Issue '+str(run['issue'])+'.\n\n'
        'Task-Tower: '+run['task_id']+'\n\n'+marker+'\n\n'
        'Stage evidence is included in the branch. Independent exact PR and main acceptance remain required.\n')


def _pr_observation(row,intent,effect_id):
    marker='<!-- task-tower:pipeline:v1 '+intent['run_id']+' '+effect_id+' -->'
    if not isinstance(row,dict):raise ValueError('Invalid PR response')
    number=row.get('number')
    if type(number) is not int or number<1:raise ValueError('Invalid PR number')
    repo=intent['repository']; body=row.get('body'); title=row.get('title')
    if (not isinstance(body,str) or not isinstance(title,str) or _sha(body.encode())!=intent['body_sha256'] or
            _sha(title.encode())!=intent['title_sha256'] or body.splitlines().count('Task-Tower: '+intent['task_id'])!=1 or
            len(re.findall(r'^Task-Tower:',body,re.M))!=1 or body.count(marker)!=1 or
            len(re.findall(r'<!-- task-tower:pipeline:',body))!=1 or intent['marker']!=marker or
            re.search(r'(?i)\b(closes|fixes|resolves)\b',body)):
        raise ValueError('PR marker mismatch')
    if row.get('state')!='open' or row.get('user',{}).get('login','').casefold()!=intent['publisher_account'].casefold():raise ValueError('PR author or state mismatch')
    for side,sha,ref in [('head',intent['head_sha'],intent['branch']),('base',intent['base_sha'],'main')]:
        actual=row.get(side,{})
        if actual.get('sha')!=sha or actual.get('ref')!=ref or actual.get('repo',{}).get('full_name','').casefold()!=repo:raise ValueError('PR repository or SHA mismatch')
    url='https://github.com/'+repo+'/pull/'+str(number)
    actual_url=row.get('html_url')
    match=re.fullmatch(r'https://github\.com/([A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*)/pull/([1-9][0-9]*)',actual_url) if isinstance(actual_url,str) else None
    if match is None or match[1].casefold()!=repo or match[2]!=str(number):raise ValueError('PR URL mismatch')
    return dict(status='completed',repository=repo,issue=intent['issue'],issue_id=intent['issue_id'],task_id=intent['task_id'],run_id=intent['run_id'],head_sha=intent['head_sha'],base_sha=intent['base_sha'],branch=intent['branch'],number=number,url=url,author=intent['publisher_account'],marker=marker)


def _lookup(store,intent,effect_id):
    owner=intent['repository'].split('/')[0]; rows=[]
    for page in range(1,11):
        batch=store.request('GET','/pulls?state=all&head='+quote(owner+':'+intent['branch'],safe='')+'&base=main&per_page=100&page='+str(page))
        if not isinstance(batch,list) or len(batch)>100 or any(not isinstance(r,dict) for r in batch):raise ValueError('Invalid PR lookup')
        rows.extend(batch)
        if len(batch)<100:break
    else:raise ValueError('PR lookup limit')
    # Exact head/base lookup is conservative: any other PR on this branch is a conflict.
    if len(rows)>1:raise ValueError('Ambiguous PR lookup')
    return None if not rows else _pr_observation(rows[0],intent,effect_id)


def _fresh(config,run,journal,owner):
    from .pipeline_worker import _authority
    task=_authority(config,run,journal,owner)
    _accepted(run,journal.history(run['run_id']))
    if run['state']!='publishing':raise ValueError('Publication requires host state')
    return task


def publish_one(config:dict,run:dict,journal,owner_id:str,*,store_factory=GitHubTasks)->dict:
    """Perform one next final commit/push/PR effect, with intent before writes."""
    require_legacy_capacity(config)
    task=_fresh(config,run,journal,owner_id); history=journal.history(run['run_id'])
    if any(e['status'] in ('intent','unknown') for e in history['effects']):raise ValueError('Unresolved effect')
    projection=project_evidence(run,history,task)
    final=_final(run,history,projection)
    if final is None:
        from .pipeline_worker import _current
        _current(run,task)
        for name,data in projection['files'].items():
            path=safe_config_path(Path(run['worktree'])/name)
            if path.exists():raise ValueError('Preexisting host evidence')
            path.parent.mkdir(parents=True,exist_ok=True);safe_config_path(path)
            with path.open('xb') as stream:stream.write(data)
        private=safe_config_path(journal.path.parent/('projection-'+run['run_id']+'.json'))
        data=canonical_json(projection['manifest'])
        if private.exists() and private.read_bytes()!=data:raise ValueError('Changed private projection')
        if not private.exists():
            with private.open('xb') as stream:stream.write(data)
        policy=dict(task,_host_evidence=projection['hashes'],_before_effect=lambda:_fresh(config,journal.status(run['run_id']),journal,owner_id))
        freeze_checkpoint(run,policy,journal,owner_id)
        current=journal.status(run['run_id']);_fresh(config,current,journal,owner_id)
        validate_publication_current(current,task,journal)
        if not task['publish']['enabled']:
            from .pipeline_worker import _record
            _record(journal,current,owner_id,state='ready_for_pr',evidence=dict(cleanup_confirmed=True))
        else:
            from .pipeline_worker import _record
            effect=journal.history(run['run_id'])['effects'][-1]
            _record(journal,current,owner_id,state='ready',evidence=dict(cleanup_confirmed=True,publication_effect_id=effect['effect_id']))
        return journal.status(run['run_id'])
    validate_publication_current(run,task,journal)
    if not task['publish']['enabled']:
        from .pipeline_worker import _record
        return _record(journal,run,owner_id,state='ready_for_pr',evidence=dict(cleanup_confirmed=True))
    connection=_connection(config,run);_remote(run)
    pushes=[e for e in history['effects'] if e['kind']=='push']
    if not pushes:
        _remote_head(run);_fresh(config,run,journal,owner_id);validate_publication_current(run,task,journal);_remote(run)
        effect=journal.begin_effect(run['run_id'],owner_id,dict(kind='push',repository=run['repository'],head_sha=run['checkpoint_sha'],base_sha=run['base_sha'],remote='origin',branch=run['branch']))
        try:
            _fresh(config,run,journal,owner_id);validate_publication_current(run,task,journal);_remote(run)
            _remote_head(run)
            hooks=journal.path.parent/('checkpoint-'+run['run_id'])/'hooks'
            safe_config_path(hooks/'.safe')
            if not hooks.is_dir() or list(hooks.iterdir()):raise ValueError('Unsafe publication hooks')
            _git(run['worktree'],'-c','core.hooksPath='+str(hooks),'-c','push.gpgSign=false','push','--porcelain','--no-follow-tags','--recurse-submodules=no','origin',run['checkpoint_sha']+':refs/heads/'+run['branch'])
            if _remote_head(run)!=run['checkpoint_sha']:raise ValueError('Push observation missing')
            journal.finish_effect(effect['effect_id'],owner_id,dict(status='completed',head_sha=run['checkpoint_sha']))
            from .pipeline_worker import _record
            _record(journal,journal.status(run['run_id']),owner_id,state='ready',evidence=dict(cleanup_confirmed=True,publication_effect_id=effect['effect_id']))
        except Exception:
            journal.finish_effect(effect['effect_id'],owner_id,dict(status='unknown'))
        return journal.status(run['run_id'])
    if len(pushes)!=1 or pushes[0]['status']!='completed' or pushes[0]['intent']['head_sha']!=run['checkpoint_sha']:raise ValueError('Invalid push history')
    _remote_head(run)
    prs=[e for e in history['effects'] if e['kind']=='pr_create']
    if prs:
        if len(prs)!=1 or prs[0]['status']!='completed':raise ValueError('Unresolved PR history')
        from .pipeline_worker import _record
        return _record(journal,run,owner_id,state='awaiting_pr',evidence=dict(cleanup_confirmed=True))
    # Reserve the effect UUID before forming its immutable identity marker.
    # The journal mints it atomically via begin_pr_effect, never from model data.
    title='Task Tower '+run['task_id']
    _fresh(config,run,journal,owner_id);validate_publication_current(run,task,journal);_remote(run)
    effect=journal.begin_pr_effect(run['run_id'],owner_id,task['publish']['publisher_account'])
    intent=effect['intent']; store=store_factory(connection)
    try:
        found=_lookup(store,intent,effect['effect_id'])
        if found is None:
            _fresh(config,run,journal,owner_id);validate_publication_current(run,task,journal);_remote(run)
            if _remote_head(run)!=run['checkpoint_sha']:raise ValueError('Missing pushed head')
            payload=dict(title=title,body=_body(run,intent['marker']),head=run['branch'],base='main')
            found=_pr_observation(store.request('POST','/pulls',payload),intent,effect['effect_id'])
        _fresh(config,run,journal,owner_id);validate_publication_current(run,task,journal)
        journal.finish_effect(effect['effect_id'],owner_id,found)
        from .pipeline_worker import _record
        return _record(journal,journal.status(run['run_id']),owner_id,state='awaiting_pr',evidence=dict(cleanup_confirmed=True))
    except Exception:
        journal.finish_effect(effect['effect_id'],owner_id,dict(status='unknown'))
        return journal.status(run['run_id'])


def inspect_effect(config:dict,effect:dict,*,store_factory=GitHubTasks)->dict:
    """Observe only; absence never authorizes replay, reset or owner takeover."""
    journal=config.get('_journal')
    if journal is None:raise ValueError('Missing host journal')
    run=journal.status(effect['run_id'])
    saved=[e for e in journal.history(run['run_id'])['effects'] if e['effect_id']==effect['effect_id']]
    if len(saved)!=1 or saved[0]!=effect:raise ValueError('Foreign effect observation')
    if effect['kind']=='pr_create':
        try:
            result=_lookup(store_factory(_connection(config,run)),effect['intent'],effect['effect_id'])
            return result or dict(status='unknown')
        except Exception:return dict(status='unknown')
    if effect['kind']=='push':
        try:
            _remote(run)
            return dict(status='completed',head_sha=run['checkpoint_sha']) if _remote_head(run)==effect['intent']['head_sha'] else dict(status='unknown')
        except Exception:return dict(status='unknown')
    if effect['kind']=='commit':
        try:
            from .pipeline_worker import _task
            task=_task(config,run)
            projection=project_evidence(run,journal.history(run['run_id']),task)
            observation=_commit_object(run,effect,projection)
            _projection_current(run,task,journal,projection,observation['commit_sha'])
            return observation
        except Exception:return dict(status='unknown')
    return dict(status='unknown')
