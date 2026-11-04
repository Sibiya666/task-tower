"""Current main CI reads; a selected bundle is metadata, never acceptance."""
import copy
import json
import os
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
from .github_source import GitHubSource
from .pr_source import PRSource
from .pr_policy import text,SHA,integer,canonical
from .pr_source import _git,_fetch


class MainPreparation:
    """Factory-created private main mirror; JSON cannot recreate this object."""
    def __init__(self):raise TypeError('Use prepare_main')


def _live_main(context,journal,owner_id,row,effect,*,states=('awaiting_main',)):
    from .pr_journal import BINDING
    context._fresh_inputs()
    provenance=context.private_input_provenance
    if provenance['pr_journal'] is None or provenance['pr_journal']['path']!=str(journal.path):
        raise ValueError('Foreign main journal')
    with journal._db(False) as db:
        current=journal._get(db,row['repository'],row['pr_number'])
        journal._owned(db,current,owner_id)
        barrier=journal._load(db,'barriers','repository',row['repository'])
        if (current['state'] not in states or current['cancel_requested'] or current['owner_pid']!=os.getpid()
                or current['owner_id']!=owner_id or current['merge_commit']!=row['merge_commit']
                or any(type(current[k]) is not type(row[k]) or current[k]!=row[k] for k in BINDING)
                or journal._load(db,'effects','effect_id',effect['effect_id'])!=effect
                or effect['status']!='confirmed' or effect['kind']!='merge'
                or effect['owner_id']!=owner_id or effect['owner_pid']!=os.getpid()
                or effect['observation']['merge_commit']!=row['merge_commit']
                or barrier is None or barrier['completed'] is not False or barrier['owner_id']!=owner_id
                or any(barrier[k]!=row[k] for k in BINDING)):
            raise ValueError('Original main owner/barrier fenced')
    deadline=journal._clock_limits.get((row['repository'],row['pr_number']))
    if (deadline is None or time.monotonic()>=deadline or
            datetime.now(timezone.utc)>=datetime.fromisoformat(current['deadline_utc'].replace('Z','+00:00'))):
        raise ValueError('Original main deadline exceeded')


def prepare_main(context,source,github,journal,task,owner_id):
    """Retained real merge + current CI -> exclusive private compatibility card.

    No review intent, remote write, Issue closure or barrier release occurs.
    A partially prepared mirror/record is never imported as execution proof.
    """
    from .pr_context import PRHostContext
    from .pr_journal import PRJournal,BINDING
    from .pr_effects import PREffects
    from .pr_evidence import project_postmerge_card
    from .pr_persistence import _write_exclusive
    from .project_connections import safe_config_path
    if type(context) is not PRHostContext or type(journal) is not PRJournal or type(source) is not PRSource or type(github) is not GitHubSource:
        raise ValueError('Actual installed main context required')
    row=journal.get(task['repository'],task['pr_number'])
    if row is None:raise ValueError('Original merged PR required')
    effects=PREffects(source,journal,task,owner_id,context=context)
    actual,effect=effects._merge_effect()
    if effect is None or any(actual[k]!=row[k] for k in BINDING):raise ValueError('Missing original merge effect')
    _live_main(context,journal,owner_id,row,effect)
    configured,retained=effects._fact_scope(effect)
    # The supplied convenience task cannot reduce private CI/profile policy.
    bundle=select_main_bundle(source,github,configured,row['merge_commit'])
    if bundle is None:return None
    proof=source.merge_observation(row['pr_number'])
    if (proof['status']!='confirmed' or proof['merge_commit']!=row['merge_commit']
            or proof['parents']!=[row['base_sha'],row['head_sha']]
            or proof['actor'].casefold()!=configured['publisher_account'].casefold()):
        raise ValueError('Exact main merge proof changed')
    effects._match_merged_pr(source._get('/pulls/'+str(row['pr_number'])),proof,configured,retained['request'])
    _live_main(context,journal,owner_id,row,effect)
    provenance=context.private_input_provenance
    namespace=Path(provenance['artifact_namespace'])
    directory=safe_config_path(namespace/'main-preparations'/str(uuid.uuid4()))
    directory.mkdir(parents=True,exist_ok=False)
    logs=directory/'logs';logs.mkdir()
    mirror=directory/'mirror';mirror.mkdir()
    _git(mirror,['init','--template='],logs)
    url='https://github.com/'+row['repository']+'.git'
    _fetch(mirror,url,row['base_sha'],row['merge_commit'],logs)
    _git(mirror,['remote','add','origin',url],logs)
    _git(mirror,['-c','core.autocrlf=false','checkout','--detach',row['merge_commit']],logs)
    _git(mirror,['update-ref','refs/remotes/origin/main',row['merge_commit']],logs)
    merge_proof=dict({k:row[k] for k in ('repository','issue','issue_id','task_id','head_sha','base_sha','merge_commit')},
        main_sha=row['merge_commit'],parents=proof['parents'])
    card=project_postmerge_card(retained['request']['input']['authority'],merge_proof,mirror)
    if canonical(select_main_bundle(source,github,configured,row['merge_commit']))!=canonical(bundle):
        raise ValueError('Main CI changed during projection')
    _live_main(context,journal,owner_id,row,effect)
    record=dict(version=1,binding={k:row[k] for k in BINDING},merge_commit=row['merge_commit'],
        merge_effect_id=effect['effect_id'],bundle=bundle,mirror_relative_path=mirror.relative_to(namespace).as_posix(),
        card_relative_path=card.relative_to(mirror).as_posix(),private_input_provenance=provenance)
    record_path=namespace/'main-records'/(row['input_sha256']+'.json')
    _write_exclusive(record_path,record)
    prepared=object.__new__(MainPreparation)
    prepared.context=context;prepared.journal=journal;prepared.source=source;prepared.github=github
    prepared.owner_id=owner_id;prepared.pid=os.getpid();prepared.effect=effect;prepared.record=record
    prepared.record_path=record_path;prepared.mirror=mirror;prepared.card=card;prepared.bundle=copy.deepcopy(bundle)
    prepared._record_raw=canonical(record)
    prepared._mirror_identity=(mirror.stat().st_dev,mirror.stat().st_ino)
    return prepared


def _prepared_current(prepared,*,state):
    from .pr_records import _file
    from .pr_journal import BINDING
    from .pr_effects import PREffects
    from .project_connections import safe_config_path
    if type(prepared) is not MainPreparation or prepared.pid!=os.getpid():
        raise ValueError('Actual same-process main preparation required')
    context=prepared.context;journal=prepared.journal
    original=json.loads(prepared._record_raw)
    namespace=Path(context.private_input_provenance['artifact_namespace'])
    path=namespace/'main-records'/(original['binding']['input_sha256']+'.json')
    record,_,_=_file(path)
    if canonical(record)!=prepared._record_raw or record['private_input_provenance']!=context.private_input_provenance:
        raise ValueError('Original main preparation changed')
    binding=record['binding'];row=journal.get(binding['repository'],binding['pr_number'])
    if row is None or any(row[k]!=binding[k] for k in BINDING):raise ValueError('Original main admission changed')
    effect=journal.effect(record['merge_effect_id'])
    _live_main(context,journal,prepared.owner_id,row,effect,states=(state,))
    effects=PREffects(prepared.source,journal,binding,prepared.owner_id,context=context)
    task,retained=effects._fact_scope(effect)
    if canonical(select_main_bundle(prepared.source,prepared.github,task,row['merge_commit']))!=canonical(record['bundle']):
        raise ValueError('Original main CI changed')
    mirror=namespace/record['mirror_relative_path']
    safe_config_path(mirror/'.main-private-path-check')
    if (mirror.stat().st_dev,mirror.stat().st_ino)!=prepared._mirror_identity:
        raise ValueError('Original main directory replaced')
    card=safe_config_path(mirror/record['card_relative_path'])
    if card!=mirror/'docs/tasks'/(row['task_id']+'.json'):raise ValueError('Foreign main card')
    if (_git(mirror,['rev-parse','HEAD'],mirror.parent/'logs').decode().strip()!=row['merge_commit'] or
            _git(mirror,['rev-parse','refs/remotes/origin/main'],mirror.parent/'logs').decode().strip()!=row['merge_commit']):
        raise ValueError('Original main checkout changed')
    return row,task,retained,record,mirror,card


def authorize_review_launch(prepared,binding):
    """Original installed authority at the actual last process boundary.

    The host object stays local; no field is added to the review wire body.
    """
    from .pr_evidence import PostmergeReviewBinding
    if type(binding) is not PostmergeReviewBinding:raise ValueError('Actual postmerge binding required')
    row,task,_,record,_,_=_prepared_current(prepared,state='awaiting_postmerge')
    if binding.pr_binding!=record['binding'] or binding.merge_commit!=row['merge_commit']:
        raise ValueError('Foreign postmerge launch preparation')
    journal=prepared.journal
    effect=journal.effect(binding.effect_id)
    if (effect['kind']!='postmerge_review' or effect['status']!='intent'
            or effect['owner_id']!=prepared.owner_id or effect['owner_pid']!=os.getpid()
            or effect['binding']!=record['binding'] or effect['payload']!=dict(
                reviewer_instance_id=binding.reviewer_instance_id,
                request_sha256=binding.request_sha256,merge_commit=binding.merge_commit)):
        raise ValueError('Original postmerge launch intent changed')
    limits=prepared.context._fresh_inputs()['policy']
    merge=journal.effect(record['merge_effect_id'])
    _live_main(prepared.context,journal,prepared.owner_id,row,merge,states=('awaiting_postmerge',))
    remaining=min(journal._clock_limits[(row['repository'],row['pr_number'])]-time.monotonic(),
        (datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds())
    if remaining<=0:raise ValueError('Original postmerge launch deadline exceeded')
    return dict(timeout_seconds=min(remaining,limits['reviewer_timeout_seconds']),log_max_bytes=limits['log_max_bytes'])


def review_main(prepared):
    """One actual bound Worker.review_one role, persisted before PR ack."""
    from . import tasks
    from .executor_profiles import profile_fingerprint,_pins
    from .pr_evidence import PostmergeReviewBinding
    from .pr_policy import policy_fingerprint
    from .pr_journal import BINDING
    from .pr_persistence import _write_exclusive
    from .postmerge_worker import Worker
    from .reviewer import ReviewRunner
    row,task,retained,record,mirror,card=_prepared_current(prepared,state='awaiting_postmerge')
    journal=prepared.journal;context=prepared.context;owner=prepared.owner_id
    if any(e['kind']=='postmerge_review' and e['binding']==record['binding'] for e in journal.effects(row['repository'],row['pr_number'])):
        raise ValueError('Original postmerge intent already consumed')
    loaded=context._fresh_inputs()
    profile=loaded['executor']['profiles'][task['postmerge_profile']]
    authority=retained['request']['input']['authority']
    excluded=tuple(sorted(set([*authority['executor_instances'],*authority['reviewer_instances'],retained['receipt']['reviewer_instance_id']])))
    values=dict(pr_binding={k:row[k] for k in BINDING},merge_commit=row['merge_commit'],
        bundle_sha256=policy_fingerprint(record['bundle']),snapshot_sha256=tasks.task_snapshot(tasks.load_task(card)),
        reviewer_instance_id=str(uuid.uuid4()),excluded_instances=excluded,
        profile_sha256=profile_fingerprint(profile),instructions_sha256=profile_fingerprint(_pins(profile['superpowers'])))
    material=dict(values,excluded_instances=list(excluded))
    request_sha=policy_fingerprint(dict(binding=material,task=tasks.load_task(card),bundle=record['bundle']))
    worker=Worker(dict(project=str(mirror),repository=record['bundle']['repository'],required_platforms=task['required_platforms']),
        prepared.github,ReviewRunner(profile),task_provider=lambda task_id,bundle:card)
    _prepared_current(prepared,state='awaiting_postmerge')
    effect=journal.begin_effect(row['repository'],row['pr_number'],owner,'postmerge_review',
        dict(reviewer_instance_id=values['reviewer_instance_id'],request_sha256=request_sha,merge_commit=row['merge_commit']))
    try:
        _prepared_current(prepared,state='awaiting_postmerge')
        binding=PostmergeReviewBinding(**values,request_sha256=request_sha,effect_id=effect['effect_id'])
        result=worker.review_one(row['task_id'],record['bundle'],review_binding=binding,main_preparation=prepared)
        envelope=result['host_review']
        namespace=Path(context.private_input_provenance['artifact_namespace'])
        post_record=dict(version=1,binding=record['binding'],merge_commit=row['merge_commit'],
            review_effect_id=effect['effect_id'],host_review=envelope,private_input_provenance=record['private_input_provenance'])
        _write_exclusive(namespace/'postmerge-records'/(effect['effect_id']+'.json'),post_record)
        _prepared_current(prepared,state='awaiting_postmerge')
        observed=journal.observe(effect['effect_id'],owner,dict(status='confirmed',result_sha256=envelope['result_sha256'],
            receipt_sha256=envelope['receipt_sha256'],reviewer_instance_id=envelope['reviewer_instance_id'],process=envelope['process']))
        prepared._post_record_raw=canonical(post_record)
        prepared._worker=worker;prepared._post_result=result;prepared._post_effect_id=effect['effect_id']
        return observed,result
    except BaseException as error:
        try:
            context._check_pins()
            journal.observe(effect['effect_id'],owner,dict(status='unknown'))
        except (ValueError,OSError):pass
        if not isinstance(error,Exception):raise
        raise ValueError('postmerge_review_outcome_uncertain') from None


def publish_main(prepared):
    """Genuine retained postmerge -> existing single-action publication path."""
    from .pr_records import _file
    from .pr_evidence import PublicationContext,_validate_bound_envelope
    from .postmerge_worker import Worker
    from .reviewer import ReviewRunner
    from .github_tasks import GitHubTasks
    from .github_publication import GitHubPublisher
    row,task,retained,record,mirror,card=_prepared_current(prepared,state='awaiting_closure')
    journal=prepared.journal;context=prepared.context
    reviews=[e for e in journal.effects(row['repository'],row['pr_number'])
        if e['kind']=='postmerge_review' and e['binding']==record['binding']]
    if len(reviews)!=1 or reviews[0]['status']!='confirmed':raise ValueError('Missing genuine postmerge confirmation')
    effect=reviews[0]
    namespace=Path(context.private_input_provenance['artifact_namespace'])
    post,_,_=_file(namespace/'postmerge-records'/(effect['effect_id']+'.json'))
    if (canonical(post)!=prepared._post_record_raw or post['review_effect_id']!=effect['effect_id']
            or post['binding']!=record['binding'] or post['merge_commit']!=row['merge_commit']
            or post['private_input_provenance']!=record['private_input_provenance']):
        raise ValueError('Changed original postmerge record')
    envelope=post['host_review'];_validate_bound_envelope(envelope)
    if (envelope['receipt_sha256']!=row['postmerge_receipt_sha256'] or
            any(effect['observation'][k]!=envelope[k] for k in ('result_sha256','receipt_sha256','reviewer_instance_id','process'))):
        raise ValueError('Postmerge record lacks original process acknowledgment')
    loaded=context._fresh_inputs()
    connections=[c for c in loaded['connections'] if c.repository.casefold()==row['repository']]
    if len(connections)!=1:raise ValueError('Changed publication connection')
    worker=Worker(dict(project=str(mirror),repository=record['bundle']['repository'],required_platforms=task['required_platforms']),
        prepared.github,ReviewRunner(loaded['executor']['profiles'][task['postmerge_profile']]))
    post_row=worker.journal.get(row['task_id'],row['merge_commit'])
    if (post_row is None or post_row['status']!='done' or post_row['result']!=envelope['result']
            or post_row['snapshot']!=envelope['request']['binding']['snapshot_sha256']):
        raise ValueError('Actual local acceptance changed')
    publication_context=PublicationContext(connection=connections[0],source=prepared.github,
        binding=dict(record['binding'],merge_commit=row['merge_commit']),main_reader=prepared.source.main_sha,
        pr_receipt=retained['receipt'],postmerge_review=envelope,
        criteria_sha256=retained['request']['input']['authority']['criteria_sha256'],main_preparation=prepared)
    publisher=GitHubPublisher(record['bundle']['repository'],dict(issue_tasks={row['task_id']:row['issue']},
        publisher_account=task['publisher_account']),store=GitHubTasks(connections[0]),
        verify_source=prepared.github.poll,publication_context=publication_context)
    _prepared_current(prepared,state='awaiting_closure')
    result=publisher.publish_step(card,record['bundle'],post_row,task['required_platforms'],
        effect_store=journal,owner_id=prepared.owner_id)
    _prepared_current(prepared,state='awaiting_closure')
    publication=None if result['publication_id'] is None else journal.publication(result['publication_id'])
    return result,publication


def select_main_bundle(pr_source,source,task,merge_commit):
    if type(pr_source) is not PRSource or type(source) is not GitHubSource:
        raise ValueError('Actual configured main sources required')
    text(merge_commit,SHA)
    repository=task['repository'].casefold()
    if repository!=pr_source.repository or repository!=source.repository.casefold():
        raise ValueError('Foreign main source')
    if pr_source.main_sha()!=merge_commit:raise ValueError('Exact current main changed')
    bundles=source.poll()
    if source.errors:raise ValueError('Latest main source unavailable')
    relevant=[b for b in bundles if task['task_id'] in b.get('task_ids',[])]
    if not relevant:return None
    latest=max((integer(int(b['run_id'])),integer(int(b['attempt']))) for b in relevant)
    selected=[b for b in relevant if (int(b['run_id']),int(b['attempt']))==latest]
    bundle=selected[0]
    if (any(canonical(b)!=canonical(bundle) for b in selected)
            or bundle['repository'].casefold()!=repository or bundle['pr_number']!=task['pr_number']):
        raise ValueError('Ambiguous or foreign main bundle')
    if pr_source.main_sha()!=merge_commit:raise ValueError('Exact current main changed during poll')
    if bundle['merge_commit']!=merge_commit:return None
    if any(bundle['platforms'].get(platform)!='passed' for platform in task['required_platforms']):return None
    return copy.deepcopy(bundle)
