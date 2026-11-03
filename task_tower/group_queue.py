"""Actual private group queue producer; no execution authority or activation."""
import uuid
from .executor_queue import validate_request
from .pipeline_inputs import canonical_json,digest_manifest
from .group_registration import RegistrationContext,_insert
from .group_policy import group_binding


def submit(journal,request,*,context):
    from .pipeline_journal import _now,_dump,STAGES
    from .group_storage import _event
    if type(context) is not RegistrationContext or context.journal is not journal:
        raise ValueError('Invalid group queue context')
    req=validate_request(request)
    if req['operation']!='submit':raise ValueError('Invalid group queue request')
    context.revalidate()
    task=context.policy['_tasks'].get((req['repository'],req['issue']))
    if task is None or any(task[k]!=req[k] for k in ('task_id','runner_label')):
        raise ValueError('Missing private group task')
    binding=group_binding(context.policy,task)
    if binding['status']!='ready':raise ValueError('Private group route unavailable')
    # revalidate compares this retained loader result with freshly loaded files;
    # the public convenience copy context.pipeline is not authority.
    config=context.policy['_pipeline_config']
    limits=journal._limits({k:config[k] for k in ('task_timeout_seconds','role_timeout_seconds','max_reworks','max_processes','log_max_bytes')})
    with journal._db(True,initialize=False) as db:
        context.revalidate()
        installation=db.execute('SELECT * FROM group_installation').fetchone()
        if installation is None or any(installation[k]!=context.policy[p] for k,p in (
                ('installation_id','installation_id'),('current_policy_sha256','policy_sha256'),
                ('current_authorization_sha256','authorization_sha256'))):
            raise ValueError('Current registration unavailable')
        row=db.execute('SELECT * FROM runs WHERE delivery_id=?',(req['delivery_id'],)).fetchone()
        if row is not None:
            if any(row[k]!=req[k] for k in ('repository','issue','task_id','runner_label')):
                raise ValueError('Delivery identity collision')
            return journal._receipt(row)
        if db.execute('SELECT 1 FROM runs WHERE repository=? AND issue=?',(req['repository'],req['issue'])).fetchone():
            raise ValueError('Issue already admitted')
        run_id=str(uuid.uuid4());now=_now()
        values=dict(run_id=run_id,delivery_id=req['delivery_id'],repository=req['repository'],issue=req['issue'],issue_id=None,
            task_id=req['task_id'],runner_label=req['runner_label'],profile_id=task['executor_profile'],
            profile_fingerprint=binding['profile_sha256'],policy_sha256=config['policy_sha256'],criteria_sha256=None,
            superpowers_sha256=None,source_sha=None,base_sha=None,checkpoint_sha=None,branch='pipeline/'+run_id,
            worktree=None,git_dir=None,admission=None,state='queued',stage='spec',generation=1,owner_id=None,owner_pid=None,
            cancel_requested=0,created_at=now,deadline_at=None,updated_at=now,reworks=_dump(dict.fromkeys(STAGES,0)),
            process_count=0,component_keys=_dump(task['components']),input_sha256=None,manifest=None,reason=None,limits=_dump(limits))
        _insert(db,'runs',values)
        digest=digest_manifest(binding)
        _insert(db,'group_runs',dict(run_id=run_id,run_kind='group',group_id=binding['group_id'],binding_json=_dump(binding),
            binding_sha256=digest,authorization_sha256=binding['authorization_sha256'],isolation_kind='unprepared',
            first_eligible_sequence=None,current_base_epoch=None))
        _event(db,'binding',dict(version=1,binding_kind='queued_group',run_id=run_id,delivery_id=req['delivery_id'],
            capacity_epoch=installation['current_capacity_epoch'],binding=binding,binding_sha256=digest),run_id=run_id,when=now)
        journal._event(db,run_id,'submitted',None,'queued')
        context.revalidate()
        journal._validate_db(db)
        return journal._receipt(values)


def validate_queued(db,journal,run,row,events,registration):
    """Exhaustive stored metadata checks; never reconstruct execution permission."""
    from .group_storage import _json,_utc
    from .pipeline_journal import _sha,_integer,STAGES
    from . import group_policy as gp
    if registration is None:raise ValueError('Unregistered group queue')
    bindings=[(e,b) for e,b in events if e['kind']=='binding' and e['run_id']==run['run_id']]
    if len(bindings)!=1:raise ValueError('Missing or duplicate queued binding')
    event,body=bindings[0]
    if (set(body)!={'version','binding_kind','run_id','delivery_id','capacity_epoch','binding','binding_sha256'}
            or type(body['version']) is not int or body['version']!=1 or body['binding_kind']!='queued_group'
            or body['run_id']!=run['run_id'] or body['delivery_id']!=run['delivery_id']):
        raise ValueError('Invalid queued binding event')
    _integer(body['capacity_epoch'],1,2**63-1)
    saved=[b for e,b in events if e['run_id'] is None and e['kind'] in ('binding','capacity_epoch')
        and b['epoch']['epoch']==body['capacity_epoch']]
    if len(saved)!=1:raise ValueError('Missing queued registration epoch')
    snapshot=saved[0]['policy_snapshot'];group=snapshot['group'];authority=snapshot['authorization']
    binding=_json(row['binding_json'])
    if canonical_json(body['binding'])!=canonical_json(binding) or body['binding_sha256']!=row['binding_sha256'] or digest_manifest(binding)!=row['binding_sha256']:
        raise ValueError('Queued binding digest mismatch')
    tasks=[t for t in authority['tasks'] if (t['repository'],t['issue'])==(run['repository'],run['issue'])]
    if len(tasks)!=1:raise ValueError('Missing saved queue task')
    task=tasks[0];profile=task['executor_profile']
    # Reproduce all available saved relations; profile/pin files are never read
    # offline. Their hashes and reduced budgets remain metadata until a fresh
    # actual-context execution consumer recomputes the entire binding.
    route=gp.resolve_route(dict(group,_tasks={(t['repository'],t['issue']):t for t in authority['tasks']}),run['repository'],run['issue'],run['task_id'])
    project=next(p for p in group['projects'] if p['repository']==run['repository'])
    budgets=binding.get('budgets');pins=binding.get('role_pins')
    limits=authority['limits']
    if not isinstance(budgets,dict) or set(budgets)!=set(limits):raise ValueError('Invalid queued budgets')
    for key,value in budgets.items():
        _,low,high=gp.LIMITS[key];gp._integer(value,low,min(high,limits[key]))
        if key in ('max_reworks','max_processes') and value!=limits[key]:raise ValueError('Queued counter limits changed')
    if not isinstance(pins,dict) or set(pins)!=set(gp.ROLES):raise ValueError('Invalid queued role pins')
    for value in pins.values():_sha(value)
    if len(set(pins.values()))!=1:raise ValueError('Inconsistent queued role pins')
    pools={}
    for resource in group['harness_resources'].values():
        pool=pools.setdefault(resource['pool_id'],dict(max_parallel=None))
        pool['max_parallel']=gp._minimum(pool['max_parallel'],resource['max_parallel'])
    expected=dict(route,harness_resources=group['harness_resources'],harness_pools=pools,version=2,
        installation_id=group['installation_id'],canonical_journal=group['canonical_journal'],repository=run['repository'],
        issue=run['issue'],task_id=task['task_id'],runner_label=task['runner_label'],executor_profile=profile,
        profile_sha256=authority['profiles'][profile],role_pins=pins,budgets=budgets,task_policy=task,
        base_update=project['base_update'],accepted_main_source=next((g for g in project['accepted_main_sources'] if g['executor_profile']==profile),None),
        authorization_sha256=group['authorization_sha256'],capacity_sha256=group['capacity_sha256'])
    if canonical_json(binding)!=canonical_json(expected) or binding['status']!='ready':raise ValueError('Saved queue scope mismatch')
    if (row['group_id']!=binding['group_id'] or row['authorization_sha256']!=binding['authorization_sha256']
            or row['isolation_kind']!='unprepared' or row['first_eligible_sequence'] is not None or row['current_base_epoch'] is not None
            or run['profile_id']!=profile or run['profile_fingerprint']!=binding['profile_sha256']
            or run['runner_label']!=task['runner_label'] or _json(run['component_keys'])!=task['components']
            or _json(run['limits'])!=limits or run['stage']!='spec' or run['generation']!=1 or run['process_count']!=0
            or _json(run['reworks'])!=dict.fromkeys(STAGES,0) or run['branch']!='pipeline/'+run['run_id']):
        raise ValueError('Queued run metadata mismatch')
    empty=('issue_id','criteria_sha256','superpowers_sha256','source_sha','base_sha','checkpoint_sha','worktree','git_dir',
        'admission','owner_id','owner_pid','deadline_at','input_sha256','manifest')
    if any(run[k] is not None for k in empty):raise ValueError('Queued execution unavailable')
    if run['state']=='queued':
        if run['cancel_requested'] or run['reason'] is not None:raise ValueError('Invalid queued state')
    elif run['state']=='cancelled':
        if run['cancel_requested']!=1 or run['reason'] is not None:raise ValueError('Invalid queued cancellation')
        if not db.execute("SELECT 1 FROM events WHERE run_id=? AND kind='cancel_requested' AND old_state='queued' AND new_state='cancelled' AND reason='cancelled'",(run['run_id'],)).fetchone():
            raise ValueError('Missing queued cancellation history')
    elif run['state']=='needs_input':
        if run['reason']!='policy_revoked':raise ValueError('Invalid queued denial')
    else:raise ValueError('Group execution unavailable')
    if event['recorded_at']!=run['created_at'] or _utc(event['recorded_at'])<_utc(saved[0]['epoch']['registered_at']):raise ValueError('Queued event chronology mismatch')
    for table in ('attempts','effects','verdicts','group_actions','group_reservations','group_component_locks'):
        if db.execute('SELECT 1 FROM '+table+' WHERE run_id=?',(run['run_id'],)).fetchone():raise ValueError('Queued execution history unavailable')
