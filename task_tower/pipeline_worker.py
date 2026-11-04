"""One deterministic, durable pipeline action; model output is never authority.

The private ``_publisher`` callable is a host integration seam, not installed
JSON policy. It receives publishing state after current stage acceptance and
freshness checks, and owns one host effect plus its durable journal transition.
It runs even with remote publication disabled so host evidence can be finalized.
Its return value is never process/effect evidence. Until linked, accepted work
remains ready with an environment_unavailable action result.
"""
from contextlib import nullcontext
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import time
from pathlib import Path
import uuid
from typing import Protocol
from .pipeline_inputs import (canonical_artifact, canonical_text, digest_manifest, product_manifest,
                              stage_manifest, freeze_checkpoint)
from .pipeline_journal import STAGES, ACTIVE
from .executor_profiles import _pins, profile_fingerprint
from .executor_worker import _git
from .project_connections import safe_config_path

_TERMINAL={'needs_input','cancelled','timed_out','ready_for_pr','awaiting_pr','unknown'}
_CAS=('state','stage','generation','input_sha256')


class Publisher(Protocol):
    def __call__(self,config:dict,run:dict,journal,owner_id:str)->dict: ...


def _unresolved(history):
    return (any(a['state'] in ('launch_intent','unknown') for a in history['attempts']) or
            any(e['status'] in ('intent','unknown') for e in history['effects']))


def _floor(history,stage):
    return max([1]+[e['generation_floor'] for e in history['events']
        if e['kind']=='rework_applied' and STAGES.index(e['target_stage'])<=STAGES.index(stage)])


def _executors(run,history):
    floor=_floor(history,run['stage'])
    return [a for a in history['attempts'] if a['role']==run['stage']+'_executor'
            and floor<=a['generation']<=run['generation']]


def _verdicts(history,stage):
    return [v for v in history['verdicts'] if v['stage']==stage and not v['superseded']]


def next_action(run:dict,history:dict)->str|None:
    """Derive the next action solely from bound, append-only host history."""
    if run['state'] in _TERMINAL:return None
    if _unresolved(history):return 'fence'
    if run['cancel_requested']:return 'cancel'
    if run['state']=='queued' or run['manifest'] is None:return 'prepare'
    stage=run['stage']
    for prior in STAGES[:STAGES.index(stage)]:
        if not any(v['decision']=='approve' for v in _verdicts(history,prior)):return 'park'
    receipts=[v for v in _verdicts(history,stage) if v['input_sha256']==run['input_sha256'] and v['generation']==run['generation']]
    if receipts:
        if receipts[-1]['decision']!='approve':return 'park'
        return 'publish' if stage=='test' else 'advance_'+STAGES[STAGES.index(stage)+1]
    executors=_executors(run,history)
    if not executors:return stage+'_executor'
    executor=executors[-1]
    if executor['state']!='completed':return 'park'
    checkpoints=[e for e in history['effects'] if e['kind']=='commit' and e['status']=='completed'
        and e['intent']['contributing_executor_attempt_id']==executor['attempt_id']]
    if not checkpoints or run['manifest']['checkpoint_sha']!=checkpoints[-1]['observation']['commit_sha']:return 'checkpoint'
    if stage=='test' and run['manifest']['checks_sha256'] is None:return 'checks'
    reviewers=[a for a in history['attempts'] if a['role']==stage+'_reviewer' and a['input_sha256']==run['input_sha256']]
    if reviewers:return 'apply_verdict' if reviewers[-1]['state']=='completed' else 'park'
    return stage+'_reviewer'


def _record(journal,run,owner,**transition):
    return journal.record(run['run_id'],owner,{k:run[k] for k in _CAS},transition)


def _public(run,*,reason=None):
    if run is None:return dict(run_id=None,status='idle',stage=None,generation=None,reason=reason,input_sha256=None,receipt_sha256=None,effect_sha256=None)
    return dict(run_id=run['run_id'],status=run['state'],stage=run['stage'],generation=run['generation'],
        reason=reason or run['reason'],input_sha256=run['input_sha256'],receipt_sha256=None,effect_sha256=None)


def _task(config,run):
    rows=[r for r in config['tasks'] if r['repository'].casefold()==run['repository'] and
        all(r[k]==run[k] for k in ('issue','task_id','runner_label')) and r['executor_profile']==run['profile_id']]
    if len(rows)!=1:raise ValueError('Missing installed task')
    return rows[0]


def _check_deadline(config,run):
    now=datetime.now(timezone.utc)
    if now<datetime.fromisoformat(run['updated_at']):raise ValueError('deadline')
    clocks=config.setdefault('_budget_clocks',{})
    clock=clocks.get(run['run_id'])
    if clock is None:
        clock=dict(run_id=run['run_id'],started=time.monotonic(),remaining=(datetime.fromisoformat(run['deadline_at'])-now).total_seconds(),last=now)
        clocks[run['run_id']]=clock
    if now<clock['last'] or now>=datetime.fromisoformat(run['deadline_at']) or time.monotonic()-clock['started']>=clock['remaining']:raise ValueError('deadline')
    clock['last']=now


def _authority(config,run,journal,owner):
    from .dispatch_selection import collect_snapshot
    from .pipeline_policy import continuation_authorized
    if config.get('_journal') is not journal or config.get('_owner_id')!=owner:raise ValueError('Missing host authority')
    current=journal.status(run['run_id'])
    if any(type(current[k]) is not type(run[k]) or current[k]!=run[k] for k in ('owner_id',*_CAS,'manifest','worktree','git_dir')):raise ValueError('Stale controller binding')
    snapshot=collect_snapshot(config['_connections'])
    if any(project.get('error') for project in snapshot.values()):config['_scheduling_source_failed']=True
    if not continuation_authorized(config,run,snapshot):raise ValueError('policy_revoked')
    config['_issue_data']=copy.deepcopy(snapshot[run['repository']]['issues'][run['issue']])
    if current['owner_pid']!=os.getpid():raise ValueError('Foreign process owner')
    _check_deadline(config,run)
    if run['manifest'] is not None:
        prior=_prior(journal.history(run['run_id']),run['stage'])
        if run['manifest']['prior_verdict_sha256']!=(prior['receipt_sha256'] if prior else None):raise ValueError('Missing current prior receipt')
    return _task(config,run)


def _checkpoint(run,task):
    policy=dict(task,source_sha=run['source_sha'],expected_head=run['checkpoint_sha'] or run['source_sha'],git_dir=run['git_dir'],branch=run['branch'])
    manifest=product_manifest(Path(run['worktree']),policy)
    value=dict(checkpoint_sha=run['checkpoint_sha'] or run['source_sha'],product_sha256=digest_manifest(manifest))
    for field in ('spec','plan'):
        p=Path(run['worktree'])/task[field+'_path']
        value[field+'_sha256']=hashlib.sha256(canonical_artifact(p.read_bytes())).hexdigest() if p.is_file() else None
    return value


def _current(run,task):
    point=_checkpoint(run,task)
    for key in ('checkpoint_sha','product_sha256','spec_sha256','plan_sha256'):
        if point[key]!=run['manifest'][key]:raise ValueError('stale_input')
    return point


def _cleanup(history):
    return not _unresolved(history) and all(a.get('evidence') and a['evidence'].get('cleanup_confirmed') is True for a in history['attempts']) and all(e['status']=='completed' for e in history['effects'])


def _park(journal,run,owner,reason,state='needs_input'):
    history=journal.history(run['run_id'])
    if run['state']=='unknown':return run
    if not _cleanup(history):return _record(journal,run,owner,state='unknown',reason='cleanup_unknown')
    return _record(journal,run,owner,state=state,reason=reason,evidence=dict(cleanup_confirmed=True))


def _prior(history,stage):
    if stage=='spec':return None
    rows=[v for v in _verdicts(history,STAGES[STAGES.index(stage)-1]) if v['decision']=='approve']
    if not rows:raise ValueError('Missing prior acceptance')
    return rows[-1]


def _prepare(config,run,journal,owner):
    from .dispatch_selection import collect_snapshot
    from .pipeline_policy import admission_authorized
    task=_task(config,run);profile=config['profiles'][run['profile_id']]
    if run['admission'] is None:
        admission=admission_authorized(dict(config,_shared_journal=journal),task,collect_snapshot(config['_connections']),delivery_id=run['delivery_id'],run_id=run['run_id'])
        if admission is None:raise ValueError('policy_revoked')
        run=_record(journal,run,owner,state='preparing',admission=admission,**{k:admission[k] for k in ('issue_id','criteria_sha256','source_sha','base_sha')})
    _authority(config,run,journal,owner)
    pins=_pins(profile['superpowers'])
    directory=Path(profile['runs_dir'])/run['run_id']; safe_config_path(directory/'.safe')
    worktree=directory/('pipeline-'+run['run_id'])
    common=Path(_git(profile['checkout'],'rev-parse','--path-format=absolute','--git-common-dir'))
    git_dir=common/'worktrees'/worktree.name
    for p in (worktree,git_dir):
        safe_config_path(p/'.safe')
        if p.exists():raise ValueError('conflict')
    if _git(profile['checkout'],'branch','--list',run['branch']):raise ValueError('conflict')
    if directory.resolve().is_relative_to(Path(profile['checkout']).resolve()):raise ValueError('Unsafe private worktree')
    run=_record(journal,run,owner,state='preparing',worktree=str(worktree),git_dir=str(git_dir),superpowers_sha256=pins['manifest_sha256'])
    directory.mkdir(parents=True,exist_ok=True); hooks=directory/'preparation-hooks';hooks.mkdir(exist_ok=False)
    _authority(config,run,journal,owner)
    effect=journal.begin_effect(run['run_id'],owner,dict(kind='worktree_create',source_sha=run['source_sha'],branch=run['branch'],worktree=str(worktree),git_dir=str(git_dir)))
    try:
        _git(profile['checkout'],'-c','core.hooksPath='+str(hooks),'worktree','add','-b',run['branch'],str(worktree),run['source_sha'])
        if Path(_git(worktree,'rev-parse','--absolute-git-dir')).resolve()!=git_dir.resolve() or _git(worktree,'rev-parse','HEAD')!=run['source_sha'] or _git(worktree,'status','--porcelain'):raise ValueError('Worktree observation mismatch')
        _authority(config,run,journal,owner)
        journal.finish_effect(effect['effect_id'],owner,dict(status='completed',source_sha=run['source_sha']))
    except (ValueError,OSError):
        journal.finish_effect(effect['effect_id'],owner,dict(status='unknown'));return journal.status(run['run_id'])
    checkpoint=_checkpoint(run,task)
    manifest=stage_manifest(run,checkpoint,stage='spec',generation=run['generation'],prior_receipt=None,checks=None)
    _authority(config,run,journal,owner)
    return _record(journal,run,owner,state='ready',manifest=manifest)


def _binding(run,role):
    return dict(role=role,manifest=run['manifest'],artifact_names={k:k+('.log' if k in ('stdout','stderr') else '.json') for k in ('request','result','stdout','stderr')})


def _validated_reviewer(config,run,binding,result,journal,owner):
    from .executor_harness import ROLE_BINDING,validate_role_result
    attempts=journal.history(run['run_id'])['attempts']
    attempt_id=binding.get('attempt_id',result.get('attempt_id'))
    selected=[a for a in attempts if a['attempt_id']==attempt_id and a['role'].endswith('_reviewer') and a['owner_id']==owner]
    if len(selected)!=1:raise ValueError('Missing host reviewer')
    attempt=selected[0]
    if attempt['state']!='completed' or not attempt['evidence'] or attempt['evidence'].get('source_unchanged') is not True:raise ValueError('Invalid reviewer process')
    from .pipeline_roles import _file_sha,_instruction_snapshot_unchanged
    root=Path(config['profiles'][run['profile_id']]['runs_dir'])
    request_path=safe_config_path(root/attempt['artifacts']['request'])
    if _file_sha(request_path)!=attempt['evidence'].get('request_sha256'):raise ValueError('Changed private request')
    request=json.loads(request_path.read_bytes().decode('utf-8'))
    if request['instructions']['manifest_sha256']!=attempt['launch_intent']['superpowers_sha256']:raise ValueError('Changed instruction binding')
    _instruction_snapshot_unchanged(request['instructions'])
    exact={key:attempt[key] if key not in ('source_sha','checkpoint_sha') else attempt['launch_intent'][key] for key in ROLE_BINDING}
    path=safe_config_path(Path(config['profiles'][run['profile_id']]['runs_dir'])/attempt['artifacts']['result'])
    value=validate_role_result(path,exact,reviewer=True)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=attempt['result_sha256']:raise ValueError('Changed reviewer result')
    if result.get('result') is not None and result['result']!=value:raise ValueError('Forged reviewer envelope')
    return attempt,value


def _current_ci(config,run,task,reviewer):
    proof=reviewer['evidence']
    if proof.get('execution_local') is not False:return
    from .pipeline_roles import _ci_evidence
    current=_ci_evidence(config,run,task)
    if reviewer['stage']!='test' or current is None or digest_manifest(current)!=proof.get('ci_evidence_sha256'):raise ValueError('environment_unavailable')


def apply_verdict(config:dict,run:dict,binding:dict,result:dict,journal,owner_id:str)->dict:
    """Revalidate actual private result/process and current external authority."""
    reviewer,value=_validated_reviewer(config,run,binding,result,journal,owner_id)
    task=_authority(config,run,journal,owner_id)
    _current(run,task)
    _current_ci(config,run,task,reviewer)
    history=journal.history(run['run_id']);executors=[a for a in history['attempts'] if a['role']==reviewer['stage']+'_executor' and a['generation']<=reviewer['generation'] and a['state']=='completed']
    if not executors:raise ValueError('Missing executor contribution')
    executor=executors[-1]
    manifest=reviewer['launch_intent']
    receipt=dict(manifest=manifest,input_sha256=reviewer['input_sha256'],stage=reviewer['stage'],generation=reviewer['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256=manifest['superpowers_sha256'],policy_sha256=manifest['policy_sha256'],result_sha256=reviewer['result_sha256'],process=reviewer['evidence'],decision=value['verdict'],return_stage=value['return_stage'])
    # Recheck after reading history, immediately before local attestation.
    _authority(config,run,journal,owner_id)
    _current(run,task)
    _current_ci(config,run,task,reviewer)
    saved=journal.save_verdict(run['run_id'],owner_id,receipt)
    current=journal.status(run['run_id'])
    if saved['superseded'] or current['state'] in _TERMINAL:return _public(current)
    if value['verdict']=='needs_input':return _public(_park(journal,current,owner_id,'environment_unavailable'))
    if value['verdict']=='reject':
        stage=value['return_stage']; checkpoint=_checkpoint(current,task)
        new=stage_manifest(current,checkpoint,stage=stage,generation=current['generation']+1,prior_receipt=_prior(journal.history(run['run_id']),stage),checks=None)
        current=_record(journal,current,owner_id,state='ready',stage=stage,generation=new['generation'],manifest=new,reason='criteria_unmet')
    else:current=_record(journal,current,owner_id,state='ready',reason=None)
    answer=_public(current);answer['receipt_sha256']=saved['receipt_sha256'];return answer


def _checkpoint_policy(config,run,journal,owner):
    """Private callable only: recheck this owner/input before checkpoint effects."""
    return dict(_authority(config,run,journal,owner),
        _before_effect=lambda:_authority(config,run,journal,owner))


def _stale(config,run,journal,owner,stage):
    # A dirty tree cannot be paired with an older checkpoint. Only an actual
    # failed source-mutating attempt can authorize a forensic rework snapshot.
    task=_checkpoint_policy(config,run,journal,owner)
    history=journal.history(run['run_id'])
    failed=[a for a in history['attempts'] if a['owner_id']==owner and
        a['input_sha256']==run['input_sha256'] and a['state']=='failed' and
        a.get('evidence',{}).get('cleanup_confirmed') is True and
        a['evidence'].get('source_unchanged') is False]
    completed=[a for a in history['attempts'] if a['owner_id']==owner and
        a['input_sha256']==run['input_sha256'] and a['state']=='completed' and
        a['role']==run['stage']+'_executor' and a.get('evidence',{}).get('source_unchanged') is False]
    if (stage=='spec' and run['stage']=='development' and completed and
            any(_checkpoint(run,task)[k]!=run['manifest'][k] for k in ('spec_sha256','plan_sha256'))):
        point=freeze_checkpoint(run,task,journal,owner)
    elif failed:
        from .pipeline_inputs import freeze_rework_checkpoint
        point=freeze_rework_checkpoint(run,task,journal,owner,failed[-1]['attempt_id'])
    else:return _park(journal,run,owner,'stale_input')
    run=journal.status(run['run_id'])
    _authority(config,run,journal,owner)
    manifest=stage_manifest(run,point,stage=stage,generation=run['generation']+1,prior_receipt=_prior(journal.history(run['run_id']),stage),checks=None)
    return _record(journal,run,owner,state='ready',stage=stage,generation=manifest['generation'],manifest=manifest,reason='stale_input',evidence=dict(cleanup_confirmed=True))


def _frozen_product(run,task,point):
    """Recover from the immutable commit, never attribute later dirt to a role."""
    from .pipeline_inputs import _git as git_bytes, _is_card
    rows=[]
    for entry in git_bytes(run['worktree'],'ls-tree','-r','-z',point['checkpoint_sha']).split(b'\0'):
        if not entry:continue
        header,name=entry.split(b'\t',1);mode,kind,oid=header.decode('ascii').split(' ');name=os.fsdecode(name)
        if _is_card(name) or name.startswith(task['evidence_dir']):continue
        if kind!='blob' or mode not in ('100644','100755'):raise ValueError('stale_input')
        data=git_bytes(run['worktree'],'cat-file','blob',oid)
        if len(data)>16777216:raise ValueError('size_limit')
        try:
            text=data.decode('utf-8')
            is_text=not any(ord(c)<32 and c not in '\t\r\n' or ord(c)==127 for c in text)
        except UnicodeDecodeError:is_text=False
        designated=name in (task['spec_path'],task['plan_path'])
        if designated:
            if not is_text:raise ValueError('stale_input')
            data=canonical_artifact(data)
        elif is_text:data=canonical_text(data)
        rows.append(dict(path=name,mode=mode,scheme='sha256-utf8-lf-v2' if is_text else 'sha256-bytes-v1',sha256=hashlib.sha256(data).hexdigest()))
    if digest_manifest(dict(version=1,files=sorted(rows,key=lambda row:row['path'])))!=point['product_sha256']:raise ValueError('stale_input')


def _checkpoint_action(config,run,journal,owner):
    task=_checkpoint_policy(config,run,journal,owner);history=journal.history(run['run_id']);executor=_executors(run,history)[-1]
    existing=[e for e in history['effects'] if e['kind']=='commit' and e['status']=='completed' and e['intent']['contributing_executor_attempt_id']==executor['attempt_id']]
    point=_checkpoint(run,task) if existing else freeze_checkpoint(run,task,journal,owner)
    if existing:_frozen_product(run,task,point)
    run=journal.status(run['run_id'])
    _authority(config,run,journal,owner)
    if run['stage']=='spec' and any(point.get(k) is None for k in ('spec_sha256','plan_sha256')):return _park(journal,run,owner,'evidence_missing')
    manifest=stage_manifest(run,point,stage=run['stage'],generation=run['generation']+1,prior_receipt=_prior(history,run['stage']),checks=None)
    return _record(journal,run,owner,state='ready',generation=manifest['generation'],manifest=manifest,reason=None)


def _queued_selection(config,journal=None,queued=()):
    """Fresh host ordering/denials, never permission to execute queued work."""
    from .dispatch_selection import collect_snapshot,select_ready
    from .project_worker import verified_done
    from .pipeline_policy import admission_authorized,_current
    denied=[]
    try:
        snapshot=collect_snapshot(config['_connections'])
        evidence_unknown=False
        # Observe the real verifier; subsequent polls can clear partial errors.
        def verify(connection,store,source,issue):
            nonlocal evidence_unknown
            try:return verified_done(connection,store,source,issue)
            finally:
                if getattr(source,'errors',()):evidence_unknown=True
        selected=select_ready(snapshot,config['tasks'],verify_done=verify)
        if len(selected['ready'])>10000:return [],True,denied
        source_unknown=any(row['status']=='unavailable' for row in selected['projects']) or evidence_unknown or any(getattr(project.get('source'),'errors',()) for project in snapshot.values())
        failed=source_unknown or any(row['reason'] in {'source_unavailable','lifecycle_unavailable','invalid_priority','invalid_dependencies','task_identity_mismatch','issue_missing'} for row in selected['excluded'])
        if journal is not None:
            try:private_current=_current(config)
            except (OSError,ValueError,TypeError,KeyError):private_current=None;failed=True
            excluded={(r['repository'],r['issue']):r['reason'] for r in selected['excluded']}
            for run in queued:
                tasks=[t for t in config['tasks'] if t['repository'].casefold()==run['repository'] and all(t[k]==run[k] for k in ('issue','task_id','runner_label')) and t['executor_profile']==run['profile_id']]
                profile=config['profiles'].get(run['profile_id'])
                mismatch=len(tasks)!=1 or profile is None or run['policy_sha256']!=config['policy_sha256'] or run['profile_fingerprint']!=profile_fingerprint(profile)
                reject=mismatch or private_current is False
                reason=excluded.get((run['repository'],run['issue']))
                project=snapshot.get(run['repository'])
                # Do not re-poll away a known unknown while classifying denial.
                if not reject and private_current is True and reason not in (None,'source_unavailable','lifecycle_unavailable') and not (reason=='dependency_unverified' and source_unknown) and project and not project['error']:
                    reject=admission_authorized(dict(config,_shared_journal=journal),tasks[0],snapshot,delivery_id=run['delivery_id'],run_id=run['run_id']) is None
                if reject:
                    result=journal.deny_queued(run)
                    if result is not None:denied.append(result)
            known={(r['repository'],r['issue']) for r in queued}
            selected['ready']=[r for r in selected['ready'] if (r['repository'],r['issue']) in known]
            # Wait for the original worker's exact consumer/run confirmation.
            # Queued identity alone and legacy outcomes never launch a model.
            ready=[]
            for row in selected['ready']:
                run=next(r for r in queued if (r['repository'],r['issue'])==(row['repository'],row['issue']))
                task=next(t for t in config['tasks'] if t['repository'].casefold()==run['repository'] and t['issue']==run['issue'])
                if task.get('shared_worker') is True and admission_authorized(dict(config,_shared_journal=journal),task,snapshot,delivery_id=run['delivery_id'],run_id=run['run_id']) is None:
                    failed=True;continue
                ready.append(row)
            selected['ready']=ready
            if private_current is not True:selected['ready']=[]
        return [{key:row[key] for key in ('repository','issue','priority')} for row in selected['ready']],failed,denied
    except (OSError,ValueError,TypeError,KeyError):return [],True,denied


def _step(config,journal,owner):
    runs=journal.status()['runs']
    matching=[r for r in runs if r['owner_id']==owner and r['state'] in ACTIVE and r['state']!='unknown']
    if len(matching)>1:raise ValueError('One action owner cannot own multiple runs')
    if matching and matching[0]['owner_pid']!=os.getpid():raise ValueError('Foreign process owner')
    run=matching[0] if matching else journal.claim(owner,config['max_active'],queued_order=[])
    denied=[]
    if run is None:
        order,failed,denied=_queued_selection(config,journal,[r for r in runs if r['state']=='queued'])
        config['_scheduling_source_failed']=failed
        run=journal.claim(owner,config['max_active'],queued_order=order)
    if run is None:return _public(denied[0] if denied and not config['_scheduling_source_failed'] else None)
    action=next_action(run,journal.history(run['run_id']))
    if action is None:return _public(run)
    if action=='fence':
        reason='effect_unknown' if any(e['status'] in ('intent','unknown') for e in journal.history(run['run_id'])['effects']) else 'launch_unknown'
        return _public(_record(journal,run,owner,state='unknown',reason=reason))
    if action=='cancel':return _public(_park(journal,run,owner,'cancelled','cancelled'))
    now=datetime.now(timezone.utc)
    if run['deadline_at'] and (now>=datetime.fromisoformat(run['deadline_at']) or now<datetime.fromisoformat(run['updated_at'])):return _public(_park(journal,run,owner,'deadline','timed_out'))
    if run['process_count']>=run['limits']['max_processes'] and action not in ('apply_verdict','park'):return _public(_park(journal,run,owner,'process_limit'))
    try:
        if action=='prepare':return _public(_prepare(config,run,journal,owner))
        task=_authority(config,run,journal,owner)
        if action not in ('checkpoint','park'):
            try:
                if action=='publish' and run['state'] in ('publishing','ready') and run['checkpoint_sha']!=run['manifest']['checkpoint_sha']:
                    from .pipeline_publish import validate_publication_current
                    validate_publication_current(run,task,journal)
                else:_current(run,task)
            except ValueError:
                target='spec' if any(_checkpoint(run,task)[k]!=run['manifest'][k] for k in ('spec_sha256','plan_sha256')) else ('development' if run['stage']=='test' else run['stage'])
                return _public(_stale(config,run,journal,owner,target))
        if action=='checkpoint':return _public(_checkpoint_action(config,run,journal,owner))
        if action=='park':return _public(_park(journal,run,owner,'evidence_missing'))
        if action.startswith('advance_'):
            stage=action[len('advance_'):];point=_current(run,task)
            manifest=stage_manifest(run,point,stage=stage,generation=run['generation']+1,prior_receipt=_prior(journal.history(run['run_id']),stage),checks=None)
            run=_record(journal,run,owner,state='ready',stage=stage,generation=manifest['generation'],manifest=manifest,reason=None)
            action=stage+'_executor'
        if action=='publish':
            publisher:Publisher|None=config.get('_publisher')
            if not callable(publisher):return _public(run,reason='environment_unavailable')
            if run['state']!='publishing':run=_record(journal,run,owner,state='publishing')
            publisher(config,run,journal,owner)
            return _public(journal.status(run['run_id']))
        if action=='checks':
            from .pipeline_roles import run_checks
            if run['state']!='checking':run=_record(journal,run,owner,state='checking')
            checks=run_checks(config,run,run['manifest'],journal,owner);run=journal.status(run['run_id'])
            if run['state']=='unknown':return _public(run)
            if run['cancel_requested']:return _public(_park(journal,run,owner,'cancelled','cancelled'))
            _check_deadline(config,run)
            if any(row['status']!='passed' for row in checks['checks']):
                if any(not row['source_unchanged'] and row['started'] for row in checks['checks']):return _public(_stale(config,run,journal,owner,'development'))
                return _public(_park(journal,run,owner,'environment_unavailable' if any(row['status']=='unavailable' for row in checks['checks']) else 'test_failure'))
            _authority(config,run,journal,owner);point=_current(run,task)
            manifest=stage_manifest(run,point,stage='test',generation=run['generation']+1,prior_receipt=_prior(journal.history(run['run_id']),'test'),checks=checks)
            run=_record(journal,run,owner,state='ready',generation=manifest['generation'],manifest=manifest,evidence=dict(cleanup_confirmed=True,checks_sha256=digest_manifest(checks)))
            return _public(run)
        if action=='apply_verdict':
            attempts=[a for a in journal.history(run['run_id'])['attempts'] if a['role']==run['stage']+'_reviewer' and a['input_sha256']==run['input_sha256']]
            return apply_verdict(config,run,dict(attempt_id=attempts[-1]['attempt_id']),{},journal,owner)
        if action.endswith(('_executor','_reviewer')):
            from .pipeline_roles import run_role
            state='reviewing' if action.endswith('_reviewer') else 'executing'
            if run['state']!=state:run=_record(journal,run,owner,state=state)
            invocation_run=dict(run,_issue_data=config['_issue_data'])
            result=run_role(config,invocation_run,_binding(run,action),action,journal,owner)
            run=journal.status(run['run_id'])
            if run['state']=='unknown':return _public(run)
            if run['cancel_requested']:return _public(_park(journal,run,owner,'cancelled','cancelled'))
            _check_deadline(config,run)
            if result['process'].get('status')=='timeout':return _public(_park(journal,run,owner,'deadline','timed_out'))
            if result['status']!='completed':
                if result.get('source_changed') and action.startswith('test_'):return _public(_stale(config,run,journal,owner,'development'))
                return _public(_park(journal,run,owner,result.get('reason') if result.get('reason') in ('policy_revoked','environment_unavailable') else 'evidence_missing'))
            if action.endswith('_reviewer'):return apply_verdict(config,run,result,result,journal,owner)
            if run['stage']=='development':
                point=_checkpoint(run,task)
                if any(point[k]!=run['manifest'][k] for k in ('spec_sha256','plan_sha256')):return _public(_stale(config,run,journal,owner,'spec'))
            _authority(config,run,journal,owner)
            return _public(_record(journal,run,owner,state='ready',reason=None))
        raise ValueError('Unknown controller action')
    except (ValueError,OSError) as error:
        run=journal.status(run['run_id'])
        if run['state']=='unknown':return _public(run)
        reason=str(error).split(':',1)[0]
        if reason=='stale_input':
            try:return _public(_stale(config,run,journal,owner,'spec' if run['stage']=='spec' else 'development'))
            except (ValueError,OSError):pass
        return _public(_park(journal,run,owner,reason if reason in ('conflict','size_limit','process_limit','policy_revoked','deadline') else 'environment_unavailable','timed_out' if reason=='deadline' else 'needs_input'))


def step(config:dict,journal,*,owner_id:str|None=None)->dict:
    """Perform at most one role, checkpoint, check batch or publication action."""
    owner=owner_id or config.get('_owner_id') or str(uuid.uuid4())
    if not hasattr(journal,'_pipeline_clocks'):journal._pipeline_clocks={}
    host=dict(config,_journal=journal,_owner_id=owner,_budget_clocks=journal._pipeline_clocks,_scheduling_source_failed=False)
    context=nullcontext() if owner in journal._owners else journal.owner(owner)
    with context:
        answer=_step(host,journal,owner)
        if host['_scheduling_source_failed'] and answer['reason'] is None:
            answer['reason']='source_unavailable'
            if answer['run_id'] is None:answer['status']='unavailable'
        if answer['run_id']:
            history=journal.history(answer['run_id'])
            current=[v for v in history['verdicts'] if not v['superseded']]
            answer['receipt_sha256']=current[-1]['receipt_sha256'] if current else None
            answer['effect_sha256']=history['effects'][-1]['intent_sha256'] if history['effects'] else None
        return answer

