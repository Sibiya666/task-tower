"""Fresh independent PR acceptance using existing pinned read-only role profiles.

Only the host constructs a request. Model output is untrusted data; this module
validates binding, size, process completion and cleanup before returning a receipt.
Neither requests nor raw process logs are public receipt content.
"""
import copy
import hashlib
import math
import os
from pathlib import Path

from .executor_profiles import _pins, child_environment, profile_fingerprint
from .pr_journal import BINDING, _binding
from .pr_policy import canonical, exact, identifier, integer, strict_json, text, HASH
from .processes import run_command
from .project_connections import safe_config_path

REQUEST_KEYS = BINDING | {'version', 'reviewer_instance_id', 'attempt', 'input'}
RESULT_KEYS = {'version', 'repository', 'pr_number', 'task_id', 'head_sha', 'base_sha',
    'input_sha256', 'reviewer_instance_id', 'verdict', 'summary', 'findings', 'whole_diff_reviewed'}
ENVELOPE_KEYS = {'request', 'result', 'process', 'result_sha256', 'reviewer_instance_id'}
MAX_RESULT_BYTES = 1024 * 1024


def _hash(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _request(value):
    exact(value, REQUEST_KEYS)
    _binding({k:value[k] for k in BINDING})
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid PR request version')
    identifier(value['reviewer_instance_id']); integer(value['attempt'], 1, 5)
    data=value['input']
    if not isinstance(data,dict) or _hash(data) != value['input_sha256']:
        raise ValueError('Invalid immutable PR input')
    for key in (BINDING-{'input_sha256'})|{'reviewer_instance_id','attempt'}:
        if key not in data or data[key] != value[key] or type(data[key]) is not type(value[key]):
            raise ValueError('Inconsistent PR input identity')
    if data.get('version') != 1 or type(data.get('version')) is not int:
        raise ValueError('Invalid PR input version')
    authority=data.get('authority')
    if not isinstance(authority,dict): raise ValueError('Missing PR source authority')
    for key in ('executor_instances','reviewer_instances'):
        items=authority.get(key)
        if not isinstance(items,list) or len(items)>100 or len(set(items))!=len(items):
            raise ValueError('Invalid prior PR instances')
        for item in items: identifier(item)
    if value['reviewer_instance_id'] in authority['executor_instances']+authority['reviewer_instances']:
        raise ValueError('PR reviewer is a prior stage instance')
    return value


def _summary(value):
    if not isinstance(value,str) or not value.strip() or len(value.encode('utf-8')) > 8192 or '\x00' in value:
        raise ValueError('Invalid PR review text')


def _result(value, request):
    exact(value, RESULT_KEYS)
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid PR result version')
    for key in ('repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id'):
        if type(value[key]) is not type(request[key]) or value[key] != request[key]:
            raise ValueError('Invalid PR result binding')
    if value['verdict'] not in ('approve','reject','needs_input') or type(value['whole_diff_reviewed']) is not bool:
        raise ValueError('Invalid PR result decision')
    _summary(value['summary'])
    findings=value['findings']
    if not isinstance(findings,list) or len(findings)>100: raise ValueError('Invalid PR findings')
    seen=set()
    for item in findings:
        exact(item, {'id','blocking','summary'})
        text(item['id'],r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}')
        if item['id'] in seen or type(item['blocking']) is not bool: raise ValueError('Invalid PR finding')
        seen.add(item['id']); _summary(item['summary'])
    if len(canonical(value).encode('utf-8')) > MAX_RESULT_BYTES:
        raise ValueError('Oversized PR review result')
    return value


def _schema(request):
    properties={key:dict(type='integer' if type(request[key]) is int else 'string',const=request[key])
        for key in RESULT_KEYS-{'verdict','summary','findings','whole_diff_reviewed'}}
    properties.update(verdict=dict(type='string',enum=['approve','reject','needs_input']),
        summary=dict(type='string',minLength=1,maxLength=8192),whole_diff_reviewed=dict(type='boolean'),
        findings=dict(type='array',maxItems=100,items=dict(type='object',additionalProperties=False,
            required=['id','blocking','summary'],properties=dict(id=dict(type='string'),blocking=dict(type='boolean'),summary=dict(type='string',minLength=1,maxLength=8192)))))
    return dict(type='object',additionalProperties=False,required=sorted(RESULT_KEYS),properties=properties)


def _private_directory(directory,checkout):
    directory=Path(directory).absolute(); checkout=Path(checkout).resolve()
    safe_config_path(directory/'.path-check')
    if directory.resolve().is_relative_to(checkout) or checkout.is_relative_to(directory.resolve()):
        raise ValueError('PR output overlaps checkout')
    # mkdir is exclusive: stale results and role-instance output cannot be reused.
    try: directory.mkdir(parents=True,exist_ok=False)
    except OSError: raise ValueError('PR output directory already exists or unavailable') from None
    return directory


class PRReviewRunner:
    def __init__(self,profile):
        self.profile=copy.deepcopy(profile)

    def review(self,checkout,request,output_dir,*,cancel_requested=None):
        request=copy.deepcopy(_request(request)); profile=self.profile
        pins=_pins(profile['superpowers'])
        if request['input'].get('profile_sha256')!=profile_fingerprint(profile):
            raise ValueError('PR reviewer profile binding mismatch')
        if request['input'].get('instructions_sha256')!=profile_fingerprint(pins):
            raise ValueError('PR reviewer instruction binding mismatch')
        if profile.get('repository','').casefold()!=request['repository']:
            raise ValueError('Foreign PR reviewer profile')
        timeout=profile.get('timeout_seconds')
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=3600:
            raise ValueError('Invalid PR reviewer timeout')
        limit=integer(profile.get('log_max_bytes'),1,67108864)
        argv=profile.get('argv')
        if not isinstance(argv,list) or not argv or any(not isinstance(arg,str) or not arg or '\x00' in arg for arg in argv):
            raise ValueError('Invalid PR reviewer argv')
        if profile.get('kind') not in ('codex','custom') or profile.get('approve_for_me',False):
            raise ValueError('Invalid read-only reviewer profile')
        if profile['kind']=='custom' and profile.get('trusted') is not True:
            raise ValueError('Untrusted custom PR reviewer')
        if profile['kind']=='codex' and len(argv)!=1: raise ValueError('Invalid Codex reviewer argv')
        checkout=Path(checkout).resolve()
        if not checkout.is_dir(): raise ValueError('Missing PR checkout')
        output=_private_directory(output_dir,checkout)
        if output.resolve().is_relative_to(Path(pins['root']).resolve()):
            raise ValueError('PR output overlaps pinned instructions')
        request_path=output/'request.json'; result_path=output/'result.json'; schema_path=output/'schema.json'
        instructions_path=output/'instructions.json'
        instructions_bytes=canonical(pins).encode('utf-8')
        instructions_path.write_bytes(instructions_bytes)
        request_bytes=canonical(request).encode('utf-8')
        request_path.write_bytes(request_bytes); schema_path.write_text(canonical(_schema(request)),encoding='utf-8')
        if profile['kind']=='custom':
            command=[*argv,'--request',str(request_path),'--result',str(result_path)]
        else:
            command=[*argv,'exec','--json','--sandbox','read-only','--output-schema',str(schema_path),
                '--output-last-message',str(result_path),'-C',str(checkout),
                'Read AGENTS.md, pinned Superpowers instructions identified by '+str(instructions_path)+
                ', and the immutable request at '+str(request_path)+
                '. Review the complete actual diff and binary manifest, accepted artifacts, criteria and CI. '
                'Do not implement changes. Check authorization, workflows and policy have not been weakened. '
                'Acknowledge binary/UI limitations in summary; use needs_input if criteria cannot be checked. '
                'Read only this immutable request, its bound checkout and explicitly pinned instructions. '
                'Private provenance paths are identifiers only: do not open installation configuration, '
                'journals, account settings or credential files. '
                'Return only the required PR review JSON.']
        process=run_command(command,checkout,timeout,env=child_environment(os.environ),
            cancel_requested=cancel_requested,capture=dict(directory=str(output),max_bytes_per_stream=limit))
        response=None; digest=None
        try:
            safe_config_path(result_path)
            if result_path.stat().st_nlink!=1 or result_path.stat().st_size>MAX_RESULT_BYTES:
                raise ValueError('Invalid PR result file')
            with result_path.open('rb') as stream: raw=stream.read(MAX_RESULT_BYTES+1)
            if len(raw)>MAX_RESULT_BYTES: raise ValueError('Oversized PR review result')
            response=strict_json(raw.decode('utf-8')); _result(response,request)
            # Canonical result hashes can be reproduced without publishing private raw files.
            digest=_hash(response)
            with request_path.open('rb') as stream: current_request=stream.read(len(request_bytes)+1)
            with instructions_path.open('rb') as stream: current_instructions=stream.read(len(instructions_bytes)+1)
            if (current_request!=request_bytes or current_instructions!=instructions_bytes
                    or _pins(profile['superpowers'])!=pins):
                raise ValueError('PR review input or instruction drift')
        except (OSError,ValueError,UnicodeError,TypeError,KeyError,RecursionError):
            response=None; digest=None
        return dict(request=request,result=response,process=process,result_sha256=digest,
            reviewer_instance_id=request['reviewer_instance_id'])


def validate_pr_review(envelope,request,excluded_instances):
    """Return a hash-bound receipt or a fixed needs_input decision; never a bool.

    Envelope is host-owned memory (not model JSON). Hash checks detect drift but
    are not a signature granting arbitrary imported envelopes process authority.
    """
    def unavailable(reason):
        return dict(verdict='needs_input',reason=reason)
    try:
        _request(request); exact(envelope,ENVELOPE_KEYS)
        if envelope['request']!=request or _hash(envelope['request'])!=_hash(request):
            return unavailable('review_request_mismatch')
        instance=envelope['reviewer_instance_id']; identifier(instance)
        if instance!=request['reviewer_instance_id']: return unavailable('review_instance_mismatch')
        if not isinstance(excluded_instances,(tuple,list)): raise ValueError('Invalid PR exclusions')
        for item in excluded_instances: identifier(item)
        authority=request['input']['authority']
        if instance in (*excluded_instances,*authority['executor_instances'],*authority['reviewer_instances']):
            return unavailable('reviewer_not_independent')
        process=envelope['process']
        if not isinstance(process,dict): raise ValueError('Invalid PR process')
        allowed={'status','exit_code','started','cleanup_confirmed','duration_seconds','reason','pid'}
        for stream in ('stdout','stderr'):
            allowed|={stream+suffix for suffix in ('_sha256','_bytes','_captured_bytes','_tail_unknown','_truncated')}
        exact(process, {'status','exit_code','started','cleanup_confirmed','duration_seconds'},allowed)
        if (process['status']!='passed' or type(process['exit_code']) is not int or process['exit_code']!=0
                or process['started'] is not True or process['cleanup_confirmed'] is not True):
            return unavailable('review_process_unconfirmed')
        integer(process['pid'])
        duration=process['duration_seconds']
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0:
            raise ValueError('Invalid PR process duration')
        for stream in ('stdout','stderr'):
            text(process[stream+'_sha256'],HASH)
            total=integer(process[stream+'_bytes'],0); captured=integer(process[stream+'_captured_bytes'],0,total)
            if process[stream+'_tail_unknown'] is not False or type(process[stream+'_truncated']) is not bool:
                return unavailable('review_process_unconfirmed')
            if process[stream+'_truncated'] != (total>captured): raise ValueError('Invalid PR process capture')
        result=_result(envelope['result'],request)
        if envelope['result_sha256']!=_hash(result): return unavailable('review_result_hash_mismatch')
        if result['verdict']=='approve' and not result['whole_diff_reviewed']:
            return unavailable('whole_diff_not_reviewed')
        if result['verdict']=='approve' and any(f['blocking'] for f in result['findings']):
            return unavailable('blocking_findings')
        receipt={key:request[key] for key in BINDING}
        receipt.update(version=1,verdict=result['verdict'],summary=result['summary'],findings=copy.deepcopy(result['findings']),
            whole_diff_reviewed=result['whole_diff_reviewed'],reviewer_instance_id=instance,
            request_sha256=_hash(request),result_sha256=_hash(result),process_sha256=_hash(process))
        receipt['receipt_sha256']=_hash(receipt)
        return receipt
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError):
        return unavailable('invalid_pr_review')
