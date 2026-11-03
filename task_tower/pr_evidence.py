"""Host-only read-only stage authority and private postmerge compatibility.

Public evidence is checked against retained host history; it never grants
authority. Source journals retain their existing schemas and ownership.
"""
import base64
from dataclasses import dataclass, asdict
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .pipeline_inputs import (canonical_artifact, canonical_text, digest_manifest,
    _relative, _is_card, ARTIFACT_LIMIT, BLOB_LIMIT)
from .pipeline_publish import project_evidence, _accepted
from .pr_policy import policy_fingerprint, strict_json, identifier


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _git(root,*args):
    # Existing Task2 runner isolates Git configuration/replace objects, disables
    # hooks/fsmonitor and requires complete bounded capture with child cleanup.
    from .pr_source import _git as read_git
    with tempfile.TemporaryDirectory(prefix='pr-evidence-git-') as directory:
        # The OS may spell its temp root through an alias (macOS /var).
        # Canonicalize only this exclusively host-created directory; caller
        # paths and the downstream capture/reparse checks stay unchanged.
        return read_git(Path(root),list(args),Path(directory).resolve(strict=True))


def _retained_artifact(profile,attempt,key):
    from .pipeline_inputs import _ordinary
    path=Path(profile['runs_dir'])/_relative(attempt['artifacts'][key])
    _ordinary(path)
    if path.stat().st_size>1024*1024: raise ValueError('Private artifact limit')
    return path,path.read_bytes()


def _role_artifacts(profile,attempt):
    from .executor_harness import ROLE_BINDING,validate_role_result
    from .pipeline_roles import _instruction_snapshot_unchanged
    path,raw=_retained_artifact(profile,attempt,'result')
    if _sha(raw)!=attempt['result_sha256'] or attempt['evidence']['result_sha256']!=attempt['result_sha256']:
        raise ValueError('Changed retained role result')
    binding={k:attempt[k] if k not in ('source_sha','checkpoint_sha') else attempt['launch_intent'][k] for k in ROLE_BINDING}
    reviewer=attempt['role'].endswith('_reviewer')
    value=validate_role_result(path,binding,reviewer=reviewer)
    _,request_raw=_retained_artifact(profile,attempt,'request')
    if _sha(request_raw)!=attempt['evidence'].get('request_sha256'): raise ValueError('Changed retained role request')
    request=strict_json(request_raw)
    if request['binding']!=binding or request['manifest']!=attempt['launch_intent'] or request['role']!=attempt['role']:
        raise ValueError('Retained request identity mismatch')
    instructions=request['instructions']
    if (instructions['manifest_sha256']!=attempt['launch_intent']['superpowers_sha256'] or
            digest_manifest(instructions['manifest'])!=instructions['manifest_sha256']):
        raise ValueError('Changed retained instruction binding')
    _instruction_snapshot_unchanged(instructions)
    if reviewer:
        if value['verdict']!='approve' or attempt['evidence'].get('source_unchanged') is not True:
            raise ValueError('Unapproved retained reviewer')
    elif value['status']!='completed': raise ValueError('Uncompleted retained executor')
    return request,value


def _host_check_proof(run,manifest,history,task,profile):
    checks=[]
    for check in task['checks']:
        eligible=[a for a in history['attempts'] if a['role']=='host_check' and a['check_id']==check['id'] and a['generation']<=manifest['generation']]
        if not eligible: raise ValueError('Missing host check')
        attempt=eligible[-1]; proof=attempt['evidence']; launch=attempt['launch_intent']
        if (attempt['state']!='completed' or attempt['check_sha256']!=digest_manifest(check) or
                any(launch[k]!=manifest[k] for k in ('checkpoint_sha','product_sha256','policy_sha256'))):
            raise ValueError('Stale host check')
        _,raw=_retained_artifact(profile,attempt,'result')
        if _sha(raw)!=attempt['result_sha256']: raise ValueError('Changed host check result')
        result=strict_json(raw)
        if result['id']!=check['id'] or result['check_sha256']!=attempt['check_sha256'] or result['status']!='passed':
            raise ValueError('Unpassed host check')
        for key in ('started','cleanup_confirmed','exit_code','source_unchanged'):
            if type(result[key]) is not type(proof[key]) or result[key]!=proof[key]: raise ValueError('Host check proof mismatch')
        if result['started'] is not True or result['cleanup_confirmed'] is not True or result['source_unchanged'] is not True or result['exit_code']!=0:
            raise ValueError('Unconfirmed host check')
        for key,value in result.items():
            if key.startswith(('stdout_','stderr_')) or key=='duration_seconds':
                if proof.get(key)!=value: raise ValueError('Host check capture mismatch')
        checks.append(result)
    result=dict(version=1,checkpoint_sha=manifest['checkpoint_sha'],product_sha256=manifest['product_sha256'],policy_sha256=manifest['policy_sha256'],execution_local=True,checks=checks)
    if digest_manifest(result)!=manifest['checks_sha256']: raise ValueError('Changed host check manifest')
    return result


def _persist_envelope(path,envelope):
    """Publish a fully written private file without replacing an old identity."""
    from .project_connections import safe_config_path
    from .pr_policy import canonical
    path=safe_config_path(path); path.parent.mkdir(parents=True,exist_ok=True); safe_config_path(path)
    fd,name=tempfile.mkstemp(prefix='.envelope-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(canonical(envelope).encode('utf-8')); stream.flush(); os.fsync(stream.fileno())
        os.link(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass(frozen=True)
class StageAuthorityContext:
    pipeline_journal: object
    pipeline_config: dict | None
    git_mirror: Path
    criteria_sha256: str
    superpowers_sha256: str
    profile_sha256: str
    legacy_provenance: dict | None = None


@dataclass(frozen=True)
class PostmergeReviewBinding:
    pr_binding: dict
    merge_commit: str
    bundle_sha256: str
    snapshot_sha256: str
    request_sha256: str
    effect_id: str
    reviewer_instance_id: str
    excluded_instances: tuple
    profile_sha256: str
    instructions_sha256: str

    def request(self,task,bundle,config):
        from . import tasks
        from .pr_journal import _binding
        from .executor_profiles import _pins,profile_fingerprint
        _binding(self.pr_binding)
        for value in (self.effect_id,self.reviewer_instance_id,*self.excluded_instances): identifier(value)
        if (self.reviewer_instance_id in self.excluded_instances or
                self.pr_binding['task_id']!=task['id'] or bundle.get('repository')!=self.pr_binding['repository'] or
                task['id'] not in bundle.get('task_ids',[]) or self.merge_commit!=bundle.get('merge_commit') or
                self.bundle_sha256!=policy_fingerprint(bundle) or self.snapshot_sha256!=tasks.task_snapshot(task) or
                self.profile_sha256!=profile_fingerprint(config) or self.instructions_sha256!=profile_fingerprint(_pins(config['superpowers']))):
            raise ValueError('Postmerge launch binding mismatch')
        binding=asdict(self); binding['excluded_instances']=list(self.excluded_instances)
        request=dict(binding=binding,task=task,bundle=bundle)
        material=dict(request,binding={k:v for k,v in binding.items() if k not in ('request_sha256','effect_id')})
        if policy_fingerprint(material)!=self.request_sha256: raise ValueError('Changed postmerge request')
        return request


@dataclass(frozen=True)
class PublicationContext:
    connection: object
    source: object
    binding: dict
    main_reader: object
    pr_receipt: dict
    postmerge_review: dict

    def validate(self,receipt):
        from .pr_journal import BINDING, _binding
        from .pr_policy import exact
        exact(self.binding,BINDING|{'merge_commit'})
        _binding({k:self.binding[k] for k in BINDING})
        if (self.connection.repository.casefold()!=self.binding['repository'] or
                any(receipt[k]!=self.binding[k] for k in ('repository','issue','issue_id','task_id')) or
                receipt['commit']!=self.binding['merge_commit'] or self.main_reader()!=self.binding['merge_commit']):
            raise ValueError('Publication context or exact main changed')
        pr=self.pr_receipt; post=self.postmerge_review
        if (any(pr.get(k)!=self.binding[k] for k in BINDING) or pr.get('verdict')!='approve' or
                pr.get('whole_diff_reviewed') is not True or any(f.get('blocking') is not False for f in pr.get('findings',[])) or
                pr.get('receipt_sha256')!=policy_fingerprint({k:v for k,v in pr.items() if k!='receipt_sha256'})):
            raise ValueError('Invalid retained PR receipt')
        _validate_bound_envelope(post)
        bound=post['request']['binding']
        if (bound['pr_binding']!={k:self.binding[k] for k in BINDING} or bound['merge_commit']!=receipt['commit'] or
                bound['bundle_sha256']!=policy_fingerprint(receipt['bundle']) or
                bound['snapshot_sha256']!=receipt['input_snapshot'] or post['result']['verdict']!='approve' or
                post['reviewer_instance_id']==pr['reviewer_instance_id'] or
                pr['reviewer_instance_id'] not in bound['excluded_instances']):
            raise ValueError('Postmerge receipt binding mismatch')
        bundles=self.source.poll()
        relevant=[b for b in bundles if receipt['task_id'] in b.get('task_ids',[])]
        if not relevant: raise ValueError('Missing genuine latest main CI')
        latest=max((int(b['run_id']),int(b['attempt'])) for b in relevant)
        if any(b!=receipt['bundle'] for b in relevant if (int(b['run_id']),int(b['attempt']))==latest):
            raise ValueError('Superseded publication source')


def _validate_bound_envelope(envelope):
    from .pr_policy import exact
    exact(envelope,{'request','result','process','result_sha256','reviewer_instance_id','receipt_sha256'})
    if (envelope['receipt_sha256']!=policy_fingerprint({k:v for k,v in envelope.items() if k!='receipt_sha256'}) or
            envelope['result_sha256']!=policy_fingerprint(envelope['result'])):
        raise ValueError('Changed host review envelope')
    process=envelope['process']; exact(process,{'pid','exit_code','started','cleanup_confirmed'})
    if type(process['pid']) is not int or process['pid']<1 or type(process['exit_code']) is not int or process['exit_code']!=0 or process['started'] is not True or process['cleanup_confirmed'] is not True:
        raise ValueError('Unconfirmed host process')
    binding=envelope['request']['binding']; identifier(envelope['reviewer_instance_id']); identifier(binding['effect_id'])
    if envelope['reviewer_instance_id']!=binding['reviewer_instance_id'] or envelope['reviewer_instance_id'] in binding['excluded_instances']:
        raise ValueError('Nonindependent host process')
    material=dict(envelope['request'],binding={k:v for k,v in binding.items() if k not in ('request_sha256','effect_id')})
    if policy_fingerprint(material)!=binding['request_sha256']: raise ValueError('Changed bound request')
    result=envelope['result']; request=envelope['request']
    if result['task_id']!=request['task']['id'] or result['commit']!=request['bundle']['merge_commit']:
        raise ValueError('Changed bound result identity')


def publication_completion_proof(context,publication,issue,*,store):
    """Genuine closure proof; does not depend on already-published state."""
    from .project_worker import verified_done
    receipt=publication['receipt']; context.validate(receipt)
    if any(publication['binding'][k]!=context.binding[k] for k in publication['binding']):
        raise ValueError('Foreign publication binding')
    if (issue.get('id')!=receipt['issue_id'] or issue.get('number')!=receipt['issue'] or
            issue.get('state')!='closed' or issue.get('state_reason')!='completed' or
            not verified_done(context.connection,store,context.source,issue)):
        raise ValueError('Genuine completed closure unavailable')
    return dict(repository=context.binding['repository'],pr_number=context.binding['pr_number'],
        issue=receipt['issue'],issue_id=receipt['issue_id'],task_id=receipt['task_id'],head_sha=context.binding['head_sha'],
        base_sha=context.binding['base_sha'],merge_commit=receipt['commit'],main_sha=receipt['commit'],
        bundle_sha256=policy_fingerprint(receipt['bundle']),pr_receipt_sha256=context.pr_receipt['receipt_sha256'],
        postmerge_receipt_sha256=context.postmerge_review['receipt_sha256'],publication_id=publication['publication_id'],
        verified_done=True,issue_state='closed',state_reason='completed')


def read_pipeline_authority(context: StageAuthorityContext, run_id: str) -> dict:
    """Collect an existing, pinned, validated source in ONE read transaction."""
    identifier(run_id)
    journal=context.pipeline_journal
    from .pipeline_journal import PipelineJournal, APP_ID, SCHEMAS
    if type(journal) is not PipelineJournal:
        raise ValueError('Genuine configured pipeline journal required')
    with journal._pinned_database() as identity:
        if identity is None: raise ValueError('Missing pipeline source')
        with journal._existing_database(identity),journal._db(False,initialize=False) as db:
            if not db.in_transaction: db.execute('BEGIN')
            objects={(r[0],r[1],r[2]) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if (db.execute('PRAGMA application_id').fetchone()[0]!=APP_ID or
                    db.execute('PRAGMA user_version').fetchone()[0]!=1 or
                    objects!={('table',name,sql) for name,sql in SCHEMAS.items()}):
                raise ValueError('Changed pipeline schema')
            journal._validate_db(db)
            row=db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if row is None: raise ValueError('Missing pipeline run')
            run=journal._run(row); history={}
            for table in ('attempts','verdicts','effects','events'):
                order='sequence' if table=='events' else 'ordinal' if table=='effects' else 'rowid'
                rows=[]
                for saved in db.execute('SELECT * FROM '+table+' WHERE run_id=? ORDER BY '+order,(run_id,)):
                    item=dict(saved)
                    for key in ('launch_intent','evidence','artifacts','body','intent','observation'):
                        if key in item and item[key] is not None: item[key]=strict_json(item[key])
                    rows.append(item)
                history[table]=rows
            journal._assert_existing()
            return dict(run=run,history=history)


def _blob(root,sha,name):
    _relative(name)
    size=int(_git(root,'cat-file','-s',sha+':'+name))
    if size>BLOB_LIMIT: raise ValueError('Blob limit')
    raw=_git(root,'cat-file','blob',sha+':'+name)
    if len(raw)!=size: raise ValueError('Changed object')
    return raw


def _tree_product(root,sha,task):
    files=[]; seen=set()
    designated={task[k] for k in ('spec_path','plan_path','criteria_path') if task.get(k)}
    rows=_git(root,'ls-tree','-r','-z',sha).split(b'\0')
    if len(rows)>100001: raise ValueError('Tree size limit')
    for entry in rows:
        if not entry: continue
        header,name=entry.split(b'\t',1); mode,kind,_=header.decode('ascii').split(); name=name.decode('utf-8')
        _relative(name)
        if name.casefold() in seen or mode not in ('100644','100755') or kind!='blob':
            raise ValueError('Unsafe product entry')
        seen.add(name.casefold())
        if _is_card(name) or name.startswith(task['evidence_dir']): continue
        raw=_blob(root,sha,name)
        try:
            text=raw.decode('utf-8')
            is_text=not any(ord(c)<32 and c not in '\t\r\n' or ord(c)==127 for c in text)
        except UnicodeDecodeError: is_text=False
        if name in designated:
            if len(raw)>ARTIFACT_LIMIT or not is_text: raise ValueError('Invalid designated artifact')
            content=canonical_artifact(raw); scheme='sha256-utf8-lf-v2'
        elif is_text: content=canonical_text(raw); scheme='sha256-utf8-lf-v2'
        else: content=raw; scheme='sha256-bytes-v1'
        files.append(dict(path=name,mode=mode,scheme=scheme,sha256=_sha(content)))
    return dict(version=1,files=sorted(files,key=lambda f:f['path']))


def _one(rows,condition):
    selected=[r for r in rows if condition(r)]
    if len(selected)!=1: raise ValueError('Missing or ambiguous host proof')
    return selected[0]


def _commit_object(root,effect,sha):
    """Reconcile each retained host commit intent with its actual object."""
    intent=effect['intent']; observation=effect['observation']
    if (effect['status']!='completed' or digest_manifest(intent)!=effect['intent_sha256'] or
            digest_manifest(observation)!=effect['observation_sha256'] or observation.get('commit_sha')!=sha or
            observation.get('tree_sha')!=intent['tree']):
        raise ValueError('Changed host commit observation')
    if _git(root,'rev-list','--parents','-n','1',sha).decode().split()!=[sha,intent['parent']]:
        raise ValueError('Changed host commit parents')
    if _git(root,'rev-parse',sha+'^{tree}').decode().strip()!=intent['tree']:
        raise ValueError('Changed host commit tree')
    if not 1<=int(_git(root,'cat-file','-s',sha))<=65536: raise ValueError('Host commit size limit')
    if _git(root,'cat-file','commit',sha).split(b'\n\n',1)[-1]!=(intent['message']+'\n').encode('utf-8'):
        raise ValueError('Changed host commit message')


def validate_pipeline_publication(context,run,history,snapshot):
    config=context.pipeline_config
    from .pipeline_policy import _current
    if not isinstance(config,dict) or not _current(config): raise ValueError('Current installed pipeline policy required')
    task=_one(config['tasks'],lambda t:t['repository'].casefold()==run['repository'] and t['issue']==run['issue'] and t['task_id']==run['task_id'])
    if (run['state']!='awaiting_pr' or run['cancel_requested'] or
            run['policy_sha256']!=config['policy_sha256'] or
            run['criteria_sha256']!=context.criteria_sha256 or
            run['superpowers_sha256']!=context.superpowers_sha256 or
            run['profile_fingerprint']!=context.profile_sha256):
        raise ValueError('Stale stage authority')
    for key in ('repository','issue','issue_id','task_id','base_sha'):
        if snapshot.get(key)!=run[key]: raise ValueError('Foreign stage binding')
    if snapshot.get('head_sha')!=run['checkpoint_sha']: raise ValueError('Changed published head')
    receipts=_accepted(run,history)
    profile=config['profiles'][run['profile_id']]
    if digest_manifest(profile)!=run['profile_fingerprint'] or profile['superpowers']['manifest_sha256']!=run['superpowers_sha256']:
        raise ValueError('Changed configured pipeline profile or pins')
    attempts=history['attempts']; effects=history['effects']
    if any(a['state'] not in ('completed','failed','needs_input') or not a['evidence'] or a['evidence'].get('cleanup_confirmed') is not True for a in attempts):
        raise ValueError('Unresolved process')
    if any(e['status'] in ('intent','unknown') for e in effects): raise ValueError('Unresolved effect')
    for verdict in receipts:
        body=verdict['body']; manifest=body['manifest']
        reviewer=_one(attempts,lambda a:a['attempt_id']==body['reviewer_attempt_id'])
        executor=_one(attempts,lambda a:a['instance_id']==verdict['executor_instance_id'])
        if (reviewer['role']!=verdict['stage']+'_reviewer' or reviewer['instance_id']!=verdict['reviewer_instance_id'] or
                reviewer['state']!='completed' or reviewer['input_sha256']!=verdict['input_sha256'] or
                reviewer['result_sha256']!=body['result_sha256'] or reviewer['evidence']!=body['process'] or
                reviewer['launch_intent']!=manifest or executor['state']!='completed' or
                executor['role']!=verdict['stage']+'_executor' or executor['generation']>verdict['generation'] or
                body['executor_instance_id']!=executor['instance_id'] or body['reviewer_instance_id']!=reviewer['instance_id']):
            raise ValueError('Missing host role provenance')
        for process in (reviewer['evidence'],executor['evidence']):
            if process.get('started') is not True or process.get('cleanup_confirmed') is not True or process.get('exit_code')!=0:
                raise ValueError('Unclean accepted role')
        _role_artifacts(profile,executor)
        request,value=_role_artifacts(profile,reviewer)
        if value['verdict']!=body['decision'] or value['return_stage']!=body['return_stage']:
            raise ValueError('Retained result differs from verdict')
        if verdict['stage']=='test':
            checks=_host_check_proof(run,manifest,history,task,profile)
            if request['host_checks']!=checks: raise ValueError('Changed reviewed host checks')
            if reviewer['evidence'].get('execution_local') is False:
                from .pipeline_roles import _ci_evidence
                current_ci=_ci_evidence(config,dict(run,manifest=manifest),task)
                if current_ci is None or digest_manifest(current_ci)!=reviewer['evidence'].get('ci_evidence_sha256'):
                    raise ValueError('Changed accepted CI substitution')
        contributors=[a for a in attempts if a['role']==executor['role'] and a['generation']<=verdict['generation']]
        if contributors[-1]['attempt_id']!=executor['attempt_id']: raise ValueError('Superseded contribution')
        for event in history['events']:
            if event['kind']=='rework_applied' and ('spec','development','test').index(event['target_stage'])<=('spec','development','test').index(executor['stage']) and executor['generation']<event['generation_floor']:
                raise ValueError('Contribution precedes rework')
        contribution=_one(effects,lambda e:e['kind']=='commit' and e['status']=='completed' and
            e['observation'].get('commit_sha')==manifest['checkpoint_sha'] and
            e['intent']['contributing_executor_attempt_id']==executor['attempt_id'])
        if contribution['intent']['parent']!=executor['launch_intent']['checkpoint_sha']:
            raise ValueError('Changed executor contribution parent')
        _commit_object(context.git_mirror,contribution,manifest['checkpoint_sha'])
        if digest_manifest(_tree_product(context.git_mirror,manifest['checkpoint_sha'],task))!=manifest['product_sha256']:
            raise ValueError('Accepted product object mismatch')
    executors=[v['executor_instance_id'] for v in receipts]; reviewers=[v['reviewer_instance_id'] for v in receipts]
    if set(executors)&set(reviewers) or len(set(reviewers))!=3: raise ValueError('Nonindependent stage instances')
    projection=project_evidence(run,history,task)
    final=_one(effects,lambda e:e['kind']=='commit' and e['intent']['evidence_manifest_sha256'] is not None)
    intent=final['intent']; head=run['checkpoint_sha']; root=context.git_mirror
    if (final['status']!='completed' or final['observation'].get('commit_sha')!=head or
            intent['parent']!=run['manifest']['checkpoint_sha'] or intent['contributing_executor_attempt_id'] is not None or
            intent['evidence_manifest_sha256']!=projection['manifest_sha256'] or intent['branch']!=run['branch'] or
            intent['message']!='Task Tower publication '+run['run_id']): raise ValueError('Invalid final host commit')
    _commit_object(root,final,head)
    changed=set(filter(None,_git(root,'diff','--no-ext-diff','--no-textconv','--name-only','-z',intent['parent'],head,'--').decode().split('\0')))
    if changed!=set(projection['files']): raise ValueError('Host commit changed product')
    for name,data in projection['files'].items():
        if _blob(root,head,name)!=data: raise ValueError('Changed host evidence')
    push=_one(effects,lambda e:e['kind']=='push')
    pr=_one(effects,lambda e:e['kind']=='pr_create')
    for effect in (push,pr):
        if effect['status']!='completed' or digest_manifest(effect['intent'])!=effect['intent_sha256'] or digest_manifest(effect['observation'])!=effect['observation_sha256']:
            raise ValueError('Invalid publication effect')
        for key,value in dict(repository=run['repository'],head_sha=head,base_sha=run['base_sha'],branch=run['branch']).items():
            if effect['intent'][key]!=value: raise ValueError('Foreign publication effect')
    from .pipeline_journal import PipelineJournal
    PipelineJournal._effect_observation(pr,pr['intent'],pr['observation'])
    if push['observation'].get('head_sha')!=head or pr['observation']['number']!=snapshot['pr_number']:
        raise ValueError('Foreign observed publication')
    return dict(receipts=receipts,projection=projection,task_policy=task)


def load_stage_authority(task,snapshot,*,context:StageAuthorityContext):
    if type(context) is not StageAuthorityContext: raise ValueError('Host authority context required')
    for key in ('repository','issue','issue_id','task_id','pr_number'):
        if task.get(key)!=snapshot.get(key): raise ValueError('Foreign task binding')
    if task.get('source')!='pipeline': raise ValueError('stage_authority_unverified')
    collected=read_pipeline_authority(context,task['pipeline_run_id'])
    run=collected['run']
    proof=validate_pipeline_publication(context,run,collected['history'],snapshot)
    receipts=proof['receipts']; projection=proof['projection']
    result=dict(source='pipeline',run_id=run['run_id'],criteria_sha256=run['criteria_sha256'],
        head_sha=run['checkpoint_sha'],base_sha=run['base_sha'],receipts=receipts,
        artifacts=[dict(path=name,content_base64=base64.b64encode(raw).decode('ascii'),raw_sha256=_sha(raw),
            sha256=projection['hashes'][name],scheme='sha256-utf8-lf-v2') for name,raw in projection['files'].items()],
        executor_instances=sorted({r['executor_instance_id'] for r in receipts}),
        reviewer_instances=sorted({r['reviewer_instance_id'] for r in receipts}))
    result['authority_sha256']=policy_fingerprint(result)
    return result


def project_postmerge_card(authority,merge_proof,mirror):
    """Project retained authority only into an untracked private mirror card."""
    from . import tasks
    from .pipeline_inputs import _ordinary
    root=Path(mirror).resolve()
    if authority['authority_sha256']!=policy_fingerprint({k:v for k,v in authority.items() if k!='authority_sha256'}):
        raise ValueError('Changed stage authority')
    if authority['source']!='pipeline': raise ValueError('Original legacy provenance required')
    head=authority['head_sha']; base=authority['base_sha']; merge=merge_proof['merge_commit']
    if (merge_proof['head_sha']!=head or merge_proof['base_sha']!=base or merge_proof['main_sha']!=merge or
            merge_proof['parents']!=[base,head] or
            Path(_git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()!=root or
            _git(root,'rev-parse','HEAD').decode().strip()!=merge or
            _git(root,'rev-list','--parents','-n','1',merge).decode().split()!=[merge,base,head] or
            _git(root,'rev-parse',merge+'^{tree}').strip()!=_git(root,'rev-parse',head+'^{tree}').strip()):
        raise ValueError('Exact private main mirror proof required')
    receipts=authority['receipts']
    if [v['stage'] for v in receipts]!=['spec','development','test']: raise ValueError('Missing accepted stages')
    for receipt in receipts:
        manifest=receipt['body']['manifest']
        if receipt['receipt_sha256']!=digest_manifest(receipt['body']) or receipt['superseded'] or receipt['decision']!='approve':
            raise ValueError('Changed stage receipt')
        for key in ('repository','issue','issue_id','task_id'):
            if manifest[key]!=merge_proof[key]: raise ValueError('Foreign private card')
    task_id=merge_proof['task_id']; path=tasks._safe_path(root/'docs/tasks'/(task_id+'.json'))
    relative=path.relative_to(root).as_posix()
    if _git(root,'ls-files','--',relative): raise ValueError('Tracked card overwrite forbidden')
    artifacts=authority['artifacts']
    if len(artifacts)!=1: raise ValueError('Expected actual single host evidence projection')
    artifact=artifacts[0]; name=_relative(artifact['path'])
    raw=base64.b64decode(artifact['content_base64'],validate=True)
    if (artifact['scheme']!='sha256-utf8-lf-v2' or _sha(canonical_artifact(raw))!=artifact['sha256'] or
            _sha(raw)!=artifact['raw_sha256'] or _blob(root,merge,name)!=raw):
        raise ValueError('Host evidence bytes mismatch')
    local=tasks._safe_path(root/name); _ordinary(local)
    if local.read_bytes()!=raw: raise ValueError('Changed private mirror evidence')
    digest=_sha(raw.decode('utf-8').replace('\r\n','\n').encode('utf-8'))
    executor=receipts[1]['executor_instance_id']
    card=dict(version=1,id=task_id,project_root='../..',executor=executor,status='awaiting_merge',
        stages={v['stage']:dict(status='accepted',reviewer=v['reviewer_instance_id'],
            evidence=Path(os.path.relpath(local,path.parent)).as_posix(),sha256=digest,hash_scheme='sha256-utf8-lf-v1') for v in receipts})
    card['stages']['postmerge']={'status':'pending'}
    if path.exists():
        _ordinary(path); existing=tasks.load_task(path)
        stable={k:v for k,v in existing.items() if k not in ('status','postmerge_state','stages')}
        if (stable!={k:v for k,v in card.items() if k not in ('status','stages')} or
                any(existing['stages'].get(s)!=card['stages'][s] for s in ('spec','development','test'))):
            raise ValueError('Divergent private card')
        return path
    _persist_envelope(path,card)
    tasks.load_task(path)
    return path
