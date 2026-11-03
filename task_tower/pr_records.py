"""Bounded private PR-record encoding; hashes alone never grant process proof.

Record reading never grants publication or effect authority.
"""
import hashlib
import json
import os
from pathlib import Path

from .pr_review import MAX_RESULT_BYTES, _request, validate_pr_review
from .pr_policy import exact, text, HASH, identifier, authorized_task, canonical, strict_json
from .pr_journal import BINDING
from .pipeline_journal import _open_database_pin, _pin_identity
from .project_connections import safe_config_path
from .executor_profiles import profile_fingerprint

MAX_RECORD_BYTES=536870912


def canonical_record_identity(value,limit=None):
    """Count/hash existing canonical UTF-8 without a second complete JSON copy."""
    if limit is None: limit=MAX_RECORD_BYTES
    if type(limit) is not int or not 0<limit<=MAX_RECORD_BYTES:
        raise ValueError('Invalid private PR record limit')
    encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    count=0; digest=hashlib.sha256()
    try:
        for chunk in encoder.iterencode(value):
            # JSONEncoder may yield one large string token. Bound each UTF-8
            # conversion, including non-BMP characters, without changing bytes.
            for start in range(0,len(chunk),65536):
                raw=chunk[start:start+65536].encode('utf-8')
                count+=len(raw)
                if count>limit: raise ValueError('Private PR record limit exceeded')
                digest.update(raw)
    except (TypeError,OverflowError,RecursionError,UnicodeError):
        raise ValueError('Invalid private PR record encoding') from None
    return count,digest.hexdigest()


def check_review_record_budget(request,provenance):
    """Reserve before admission/launch; actual records still need own bounds."""
    size,_=canonical_record_identity(request)
    provenance_size,_=canonical_record_identity(provenance)
    reserve=2*size+provenance_size+2*MAX_RESULT_BYTES+65536
    if reserve>MAX_RECORD_BYTES: raise ValueError('Private PR review record budget exceeded')
    return reserve


def _file(path):
    """Read one bounded regular host file through an identity-pinned handle."""
    path=safe_config_path(path)
    before=_pin_identity(path.stat()); descriptor=_open_database_pin(path)
    try:
        opened=_pin_identity(os.fstat(descriptor))
        identity=(opened.st_dev,opened.st_ino)
        if identity!=(before.st_dev,before.st_ino) or opened.st_size>MAX_RECORD_BYTES:
            raise ValueError('Private PR record unavailable or oversized')
        with os.fdopen(os.dup(descriptor),'rb') as stream: raw=stream.read(opened.st_size+1)
        after=_pin_identity(path.stat())
        if (len(raw)>MAX_RECORD_BYTES or identity!=(after.st_dev,after.st_ino)
                or len(raw)!=opened.st_size or after.st_size!=opened.st_size
                or after.st_mtime_ns!=opened.st_mtime_ns):
            raise ValueError('Private PR record changed during read')
        safe_config_path(path)
        return strict_json(raw.decode('utf-8')),hashlib.sha256(raw).hexdigest(),identity
    finally: os.close(descriptor)


def read_prepared_record(context,input_sha256):
    """Resolve immutable material only against genuine current admission."""
    from .pr_context import PRHostContext
    if type(context) is not PRHostContext: raise ValueError('Typed private PR context required')
    text(input_sha256,HASH)
    try:
        loaded=context._fresh_inputs(); provenance=context.private_input_provenance
        namespace=Path(provenance['artifact_namespace'])
        record,_,_=_file(namespace/'prepared'/(input_sha256+'.json'))
        exact(record,{'request','private_artifact_identity','private_input_provenance'})
        request=record['request']; _request(request)
        if request['input_sha256']!=input_sha256: raise ValueError('Prepared input mismatch')
        if canonical(record['private_input_provenance'])!=canonical(provenance):
            raise ValueError('Prepared provenance changed')
        material=request['input']
        if (canonical(material.get('private_input_provenance'))!=canonical(provenance)
                or material.get('private_inputs_sha256')!=context.private_inputs_sha256):
            raise ValueError('Prepared input lacks private provenance')
        artifact=record['private_artifact_identity']
        exact(artifact,{'version','repository','pr_number','input_sha256','request_relative_path',
            'request_sha256','request_raw_sha256','device','inode'})
        if type(artifact['version']) is not int or artifact['version']!=1:
            raise ValueError('Invalid private artifact version')
        for key in ('repository','pr_number','input_sha256'):
            if type(artifact[key]) is not type(request[key]) or artifact[key]!=request[key]:
                raise ValueError('Private artifact binding mismatch')
        relative=artifact['request_relative_path']
        if not isinstance(relative,str): raise ValueError('Invalid private request location')
        parts=relative.split('/')
        if len(parts)!=3 or parts[0]!='preparations' or parts[2]!='request.json':
            raise ValueError('Invalid private request location')
        identifier(parts[1])
        if material.get('private_artifact_location')!=relative: raise ValueError('Unbound private request location')
        for key in ('request_sha256','request_raw_sha256'): text(artifact[key],HASH)
        for key in ('device','inode'):
            if type(artifact[key]) is not int or artifact[key]<(1 if key=='inode' else 0):
                raise ValueError('Invalid private request identity')
        actual,raw_sha,identity=_file(namespace.joinpath(*parts))
        _,request_sha=canonical_record_identity(request)
        if (canonical(actual)!=canonical(request) or request_sha!=artifact['request_sha256']
                or raw_sha!=artifact['request_raw_sha256'] or identity!=(artifact['device'],artifact['inode'])):
            raise ValueError('Prepared request replaced or changed')
        check_review_record_budget(request,provenance)
        task=authorized_task(loaded['policy'],request['repository'],request['pr_number'])
        for key in ('issue','issue_id','task_id'):
            if type(task[key]) is not type(request[key]) or task[key]!=request[key]:
                raise ValueError('Prepared task outside current policy')
        if request['policy_sha256']!=provenance['policy_sha256']: raise ValueError('Prepared policy changed')
        profile=loaded['executor']['profiles'][task['reviewer_profile']]
        instructions_sha=profile_fingerprint(profile['superpowers'])
        if (material.get('profile_sha256')!=profile_fingerprint(profile)
                or material.get('instructions_sha256')!=instructions_sha
                or material.get('pins')!={'instructions_sha256':instructions_sha}):
            raise ValueError('Prepared reviewer profile or instructions mismatch')
        with context._pr_snapshot() as db:
            matches=[strict_json(row['body']) for row in db.execute('SELECT body FROM prs')
                if strict_json(row['body'])['input_sha256']==input_sha256]
            if len(matches)!=1 or any(matches[0][key]!=request[key] for key in BINDING):
                raise ValueError('Prepared request lacks genuine current admission')
        context._fresh_inputs()
        return record
    except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError,RecursionError,OverflowError):
        raise ValueError('Private prepared PR record unavailable or unverified') from None


def read_review_record(context,input_sha256):
    """Resolve only the genuine confirmed host role, never an imported pointer."""
    prepared=read_prepared_record(context,input_sha256)
    request=prepared['request']; provenance=context.private_input_provenance
    try:
        with context._pr_snapshot() as db:
            rows=[strict_json(row['body']) for row in db.execute('SELECT body FROM prs')]
            current=[row for row in rows if row['input_sha256']==input_sha256]
            if len(current)!=1 or any(current[0][key]!=request[key] for key in BINDING):
                raise ValueError('Review admission changed')
            row=current[0]
            effects=[strict_json(item['body']) for item in db.execute('SELECT body FROM effects')]
            reviews=[effect for effect in effects if effect['kind']=='pr_review'
                and all(effect['binding'][key]==request[key] for key in BINDING)]
            if len(reviews)!=1 or reviews[0]['status']!='confirmed':
                raise ValueError('No unique confirmed PR review')
            effect=reviews[0]
            if (effect['owner_id']!=row['owner_id'] or effect['owner_pid']!=row['owner_pid']
                    or effect['payload']['reviewer_instance_id']!=request['reviewer_instance_id']
                    or effect['payload']['request_sha256']!=input_sha256):
                raise ValueError('Review owner or request mismatch')
            excluded=[item['payload']['reviewer_instance_id'] for item in effects
                if item['effect_id']!=effect['effect_id'] and 'reviewer_instance_id' in item['payload']]
            namespace=Path(provenance['artifact_namespace'])
            record,_,_=_file(namespace/'review-records'/(effect['effect_id']+'.json'))
            exact(record,{'request','envelope','receipt','review_effect_id','private_input_provenance'})
            if (record['review_effect_id']!=effect['effect_id']
                    or canonical(record['request'])!=canonical(request)
                    or canonical(record['private_input_provenance'])!=canonical(provenance)):
                raise ValueError('Verified PR record binding mismatch')
            receipt=validate_pr_review(record['envelope'],request,excluded)
            if ('receipt_sha256' not in receipt or canonical(receipt)!=canonical(record['receipt'])):
                raise ValueError('Unverified retained PR receipt')
            observation=effect['observation']; process=record['envelope']['process']
            for key in ('result_sha256','receipt_sha256','reviewer_instance_id'):
                if type(observation[key]) is not type(receipt[key]) or observation[key]!=receipt[key]:
                    raise ValueError('Unconfirmed PR review receipt')
            for key in ('pid','exit_code','started','cleanup_confirmed'):
                if type(observation['process'][key]) is not type(process[key]) or observation['process'][key]!=process[key]:
                    raise ValueError('Unconfirmed PR role process')
            if receipt['request_sha256']!=prepared['private_artifact_identity']['request_sha256']:
                raise ValueError('Full request receipt mismatch')
        context._fresh_inputs()
        return record
    except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError,RecursionError,OverflowError):
        raise ValueError('Private verified PR record unavailable or unverified') from None
