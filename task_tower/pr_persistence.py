"""Fixed genuine intake producer; no imported authority/record promotion API."""
import hashlib
import json
import os
import re
import stat
import time
from datetime import datetime,timezone
from pathlib import Path
import uuid
from .pr_context import PRHostContext
from .pr_journal import PRJournal,BINDING
from .pr_source import PRSource,prepare_review,_git
from .pr_records import canonical_record_identity,MAX_RECORD_BYTES
from .project_connections import safe_config_path


def _write_exclusive(path,value):
    """Bounded canonical host record; partial/existing files are never replaced."""
    size,_=canonical_record_identity(value)
    if size>MAX_RECORD_BYTES:raise ValueError('Private PR record oversized')
    path=safe_config_path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    safe_config_path(path)
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    with path.open('xb') as stream:
        os.set_inheritable(stream.fileno(),False)
        for chunk in encoder.iterencode(value):
            for offset in range(0,len(chunk),65536):stream.write(chunk[offset:offset+65536].encode('utf-8'))
        stream.flush();os.fsync(stream.fileno())
    safe_config_path(path)


def prepare_admission(context,source,journal,task):
    """Current real source -> actual preparation -> admission -> private index."""
    if type(context) is not PRHostContext or type(source) is not PRSource or type(journal) is not PRJournal:
        raise ValueError('Actual PR intake objects required')
    provenance=context.private_input_provenance
    if provenance['pr_journal'] is None or provenance['pr_journal']['path']!=str(journal.path):
        raise ValueError('Foreign PR intake journal')
    with journal._db(False) as db:
        owner=None if db is None else db.execute('SELECT * FROM owners WHERE owner_id=?',(journal._active,)).fetchone()
        if owner is None or owner['status']!='active' or owner['pid']!=os.getpid():raise ValueError('Actual live intake owner required')
    fresh=context.current(source,task)
    if fresh['authority_error'] is not None or fresh['snapshot']['ready'] is not True or fresh['snapshot']['reasons']!=[]:
        raise ValueError('PR intake source/authority unavailable')
    loaded=context._fresh_inputs()
    connections=[c for c in loaded['connections'] if c.repository.casefold()==fresh['task']['repository']]
    if len(connections)!=1:raise ValueError('Foreign intake connection')
    namespace=Path(provenance['artifact_namespace'])
    directory=namespace/'preparations'/str(uuid.uuid4())
    prepared=prepare_review(connections[0],fresh['task'],fresh['snapshot'],fresh['authority'],directory,private_context=context)
    request=prepared['request'];policy=loaded['policy']
    journal.admit(dict({k:request[k] for k in BINDING},task_timeout_seconds=policy['task_timeout_seconds'],
        max_review_attempts=policy['max_review_attempts']))
    from .pr_supervision import lifecycle_for
    progress=lifecycle_for(context)
    if progress is not None:progress.admitted(request['repository'],request['pr_number'])
    actual=directory/'request.json';info=actual.stat()
    _,request_sha=canonical_record_identity(request)
    record=dict(request=request,private_input_provenance=context.private_input_provenance,
        private_artifact_identity=dict(version=1,repository=request['repository'],pr_number=request['pr_number'],
            input_sha256=request['input_sha256'],request_relative_path=actual.relative_to(namespace).as_posix(),
            request_sha256=request_sha,request_raw_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),device=info.st_dev,inode=info.st_ino))
    _write_exclusive(namespace/'prepared'/(request['input_sha256']+'.json'),record)
    context.prepared_record(request['input_sha256'])
    return prepared


def _checkout_snapshot(checkout):
    """Read hashes without following source links or executing repository config."""
    safe_config_path(checkout/'.pr-checkout-safety')
    result={}
    for root,directories,files in os.walk(checkout,followlinks=False):
        directories.sort();files.sort()
        for name in list(directories)+files:
            path=Path(root)/name;info=path.lstat();relative=path.relative_to(checkout)
            key=os.fsencode(str(relative)).hex()
            if stat.S_ISLNK(info.st_mode):
                if relative.parts[0]=='.git':raise ValueError('Linked private Git control')
                if name in directories:directories.remove(name)
                result[key]=dict(link=os.fsencode(os.readlink(path)).hex());continue
            if getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Reparse private checkout')
            if stat.S_ISDIR(info.st_mode):continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Aliased private checkout file')
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                opened=os.fstat(stream.fileno())
                if not os.path.samestat(info,opened):raise ValueError('Private checkout file replaced')
                while chunk:=stream.read(1048576):digest.update(chunk)
                end=os.fstat(stream.fileno())
            after=path.lstat()
            if (not os.path.samestat(opened,after) or (opened.st_size,opened.st_mtime_ns)!=(end.st_size,end.st_mtime_ns)
                    or (end.st_size,end.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)):raise ValueError('Private checkout changed during snapshot')
            result[key]=dict(sha256=digest.hexdigest(),mode=stat.S_IMODE(info.st_mode))
    return result


def _prepared_checkout(record,namespace):
    relative=record['private_artifact_identity']['request_relative_path']
    root=namespace.joinpath(*relative.split('/')).parent;checkout=root/'checkout'
    _checkout_snapshot(checkout)  # Reject control aliases before running Git.
    control=checkout/'.git'
    if not control.is_dir():raise ValueError('Missing private Git directory')
    for name in ('commondir','shallow','info/alternates','objects/info/alternates','info/grafts'):
        if (control/name).exists():raise ValueError('Foreign private Git source')
    raw=(control/'config').read_bytes()
    if len(raw)>16384:raise ValueError('Unexpected private Git configuration')
    section=None;values={}
    for line in raw.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith(('#',';')):continue
        if line.startswith('['):
            if line.casefold()!='[core]':raise ValueError('Unexpected private Git config section')
            section='core';continue
        match=re.fullmatch(r'([A-Za-z]+)\s*=\s*(0|true|false)',line)
        if section!='core' or match is None:raise ValueError('Unexpected private Git config value')
        key=match[1].casefold()
        if key not in {'repositoryformatversion','filemode','bare','logallrefupdates','symlinks','ignorecase','precomposeunicode','protectntfs','protecthfs'} or key in values:raise ValueError('Unsafe private Git config')
        values[key]=match[2]
    if values.get('repositoryformatversion')!='0' or values.get('bare')!='false':raise ValueError('Unexpected private Git format')
    request=record['request'];logs=root/'logs'
    if _git(checkout,['rev-parse','--verify','HEAD^{commit}'],logs,1024).decode().strip()!=request['head_sha']:
        raise ValueError('Private review head changed')
    if _git(checkout,['for-each-ref','--format=%(refname)'],logs,65536):raise ValueError('Unexpected private review refs')
    if _git(checkout,['status','--porcelain=v1','--untracked-files=all','--ignored'],logs,65536):raise ValueError('Dirty private review checkout')
    return checkout,_checkout_snapshot(checkout)


def _live_review(context,journal,owner_id,effect):
    context._fresh_inputs()
    provenance=context.private_input_provenance
    if provenance['pr_journal'] is None or provenance['pr_journal']['path']!=str(journal.path):raise ValueError('Foreign review journal')
    binding=effect['binding']
    with journal._db(True) as db:
        row=journal._get(db,binding['repository'],binding['pr_number'])
        journal._owned(db,row,owner_id);journal._tick(row)
        saved=journal._load(db,'effects','effect_id',effect['effect_id'])
        if (saved!=effect or row['state']!='reviewing' or row['cancel_requested'] or row['owner_pid']!=os.getpid()
                or effect['owner_id']!=owner_id or effect['owner_pid']!=os.getpid()
                or any(type(row[k]) is not type(binding[k]) or row[k]!=binding[k] for k in BINDING)):
            raise ValueError('Original PR review fenced')
        journal._save(db,row)
    context._fresh_inputs()
    return row


def run_review(context,source,journal,task,owner_id,*,cancel_requested=None):
    """One actual role, with its original returned envelope saved before ack."""
    from .pr_effects import PREffects
    from .pr_review import PRReviewRunner,validate_pr_review
    if type(context) is not PRHostContext or type(source) is not PRSource or type(journal) is not PRJournal:
        raise ValueError('Actual PR review objects required')
    row=journal.get(task['repository'],task['pr_number'])
    if row is None:raise ValueError('Missing genuine PR admission')
    reviews=[e for e in journal.effects(row['repository'],row['pr_number']) if e['kind']=='pr_review'
        and all(type(e['binding'][k]) is type(row[k]) and e['binding'][k]==row[k] for k in BINDING)]
    if reviews:
        if len(reviews)!=1 or reviews[0]['status'] not in ('confirmed','failed'):raise ValueError('Review intent already consumed')
        return reviews[0]  # Immutable inspection, never another role.
    retained=context.prepared_record(row['input_sha256']);request=retained['request']
    proof=PREffects(source,journal,task,owner_id,context=context)._diagnostic_proof('pending')
    namespace=Path(context.private_input_provenance['artifact_namespace'])
    checkout,before=_prepared_checkout(retained,namespace)
    for old,new in [('discovered','validating'),('validating','reviewing')]:
        if row['state']==old:
            row=journal.transition(row['repository'],row['pr_number'],owner_id,dict(state=old,input_sha256=row['input_sha256']),dict(state=new))
    effect=journal.begin_effect(row['repository'],row['pr_number'],owner_id,'pr_review',
        dict(reviewer_instance_id=request['reviewer_instance_id'],request_sha256=row['input_sha256']))
    try:
        fresh=PREffects(source,journal,task,owner_id,context=context)._diagnostic_proof('pending')
        current=_live_review(context,journal,owner_id,effect)
        profile=fresh['current']['task']['_review_profile']
        from .pr_supervision import lifecycle_for
        progress=lifecycle_for(context)
        if progress is not None:
            progress.start_role(profile)
            current=_live_review(context,journal,owner_id,effect)
        def stopped():
            if cancel_requested is not None and cancel_requested():return True
            active=journal.get(row['repository'],row['pr_number'])
            return (active['cancel_requested'] or time.monotonic()>=journal._clock_limits[(row['repository'],row['pr_number'])]
                or datetime.now(timezone.utc)>=datetime.fromisoformat(current['deadline_utc'].replace('Z','+00:00')))
        envelope=PRReviewRunner(profile).review(checkout,request,namespace/'roles'/str(uuid.uuid4()),cancel_requested=stopped)
        # Preserve what the real host returned even if a later source/private
        # check refuses promotion. This forensic copy never authorizes a role,
        # receipt, publication or retry.
        record=dict(request=request,envelope=envelope,review_effect_id=effect['effect_id'],
            private_input_provenance=retained['private_input_provenance'])
        _write_exclusive(namespace/'unverified-records'/(effect['effect_id']+'.json'),record)
        if progress is not None:progress.end_role(envelope['process'])
        if _checkout_snapshot(checkout)!=before:raise ValueError('Private review source mutated')
        _live_review(context,journal,owner_id,effect)
        receipt=validate_pr_review(envelope,request,())
        process=envelope['process']
        observation=dict(reviewer_instance_id=request['reviewer_instance_id'],
            process={k:process[k] for k in ('pid','exit_code','started','cleanup_confirmed')})
        if 'receipt_sha256' in receipt:
            record['receipt']=receipt
            _write_exclusive(namespace/'review-records'/(effect['effect_id']+'.json'),record)
            observation.update(status='confirmed',result_sha256=receipt['result_sha256'],receipt_sha256=receipt['receipt_sha256'])
        elif (process['cleanup_confirmed'] is True and process['status'] in ('passed','failed','timeout','unavailable')
                and (process['started'] is True or process['status']=='unavailable' and process['pid'] is None and process['exit_code'] is None)):
            _write_exclusive(namespace/'failure-records'/(effect['effect_id']+'.json'),record)
            observation['status']='failed'
        else:
            observation=dict(status='unknown')
        _live_review(context,journal,owner_id,effect)
        return journal.observe(effect['effect_id'],owner_id,observation)
    except BaseException as error:
        try:
            context._check_pins()
            journal.observe(effect['effect_id'],owner_id,dict(status='unknown'))
        except (ValueError,OSError):pass
        if not isinstance(error,Exception):raise
        raise ValueError('pr_review_outcome_uncertain') from None
