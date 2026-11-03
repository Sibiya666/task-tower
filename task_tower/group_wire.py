"""Pure group wire syntax, never journal/source/epoch or launch authority.

Actual consumers remain closed until resource and workspace producers prove
current epoch, resolution kind, accepted-main proof and input-specific delta.
In particular, nullable epoch0 syntax cannot establish pinned resolution.
"""
import re
import math

from .pipeline_inputs import STAGE_FIELDS, validate_stage_manifest, digest_manifest
from .executor_harness import ROLE_BINDING, role_result_schema, _validate_role_result_value
from .executor_queue import _uuid

EPOCH_FIELDS=frozenset({'base_epoch','base_epoch_sha256','scope_base_sha',
    'diff_base_sha','accepted_main_proof_sha256','task_delta_sha256'})


def validate_epoch_shape(value):
    if not isinstance(value,dict) or set(value)!=EPOCH_FIELDS:
        raise ValueError('Invalid group epoch shape')
    epoch=value['base_epoch']
    if type(epoch) is not int or not 0<=epoch<2**63:
        raise ValueError('Invalid group base epoch')
    for key in EPOCH_FIELDS-{'base_epoch'}:
        item=value[key]
        if key=='accepted_main_proof_sha256' and item is None and epoch==0: continue
        size=40 if key in ('scope_base_sha','diff_base_sha') else 64
        if not isinstance(item,str) or not re.fullmatch('[a-f0-9]{'+str(size)+'}',item):
            raise ValueError('Invalid group epoch digest')
    return value


def group_stage_shape(legacy_stage,epoch):
    """Describe stage2 syntax from a valid stage1; creates no host proof."""
    validate_stage_manifest(legacy_stage); validate_epoch_shape(epoch)
    result=dict(legacy_stage,**epoch); result['version']=2
    return validate_group_stage_shape(result)


def validate_group_stage_shape(value):
    if (not isinstance(value,dict) or set(value)!=STAGE_FIELDS|EPOCH_FIELDS
            or type(value['version']) is not int or value['version']!=2):
        raise ValueError('Invalid group stage shape')
    validate_epoch_shape({key:value[key] for key in EPOCH_FIELDS})
    legacy={key:value[key] for key in STAGE_FIELDS}; legacy['version']=1
    validate_stage_manifest(legacy)
    return value


def _role_binding_shape(binding):
    if not isinstance(binding,dict) or set(binding)!=set(ROLE_BINDING)|EPOCH_FIELDS:
        raise ValueError('Invalid group role binding shape')
    validate_epoch_shape({key:binding[key] for key in EPOCH_FIELDS})
    for key in ('run_id','attempt_id','instance_id'): _uuid(binding[key])
    if (binding['stage'] not in ('spec','development','test')
            or type(binding['generation']) is not int or binding['generation']<1):
        raise ValueError('Invalid group role stage')
    for key in ('source_sha','checkpoint_sha','input_sha256'):
        size=64 if key=='input_sha256' else 40
        if not isinstance(binding[key],str) or not re.fullmatch('[a-f0-9]{'+str(size)+'}',binding[key]):
            raise ValueError('Invalid group role digest')


def group_role_result_schema(binding,*,reviewer):
    """Role3 syntax only; this is not an attempt admission or expected epoch."""
    _role_binding_shape(binding)
    if type(reviewer) is not bool: raise ValueError('Explicit role schema required')
    legacy={key:binding[key] for key in ROLE_BINDING}
    schema=role_result_schema(legacy,reviewer=reviewer)
    schema['properties']['version']['const']=3
    for key in sorted(EPOCH_FIELDS):
        value=binding[key]
        kind='integer' if key=='base_epoch' else 'null' if value is None else 'string'
        schema['properties'][key]=dict(type=kind,const=value)
    schema['required']=list(schema['properties'])
    return schema


def validate_group_role_result_shape(value,binding,*,reviewer):
    schema=group_role_result_schema(binding,reviewer=reviewer)
    if (not isinstance(value,dict) or set(value)!=set(schema['required'])
            or type(value['version']) is not int or value['version']!=3):
        raise ValueError('Invalid group role3 shape')
    for key in EPOCH_FIELDS:
        if type(value[key]) is not type(binding[key]) or value[key]!=binding[key]:
            raise ValueError('Group role epoch/input mismatch')
    # Reuse the exact legacy finding/route/status constraints without making
    # the actual legacy file parser accept a group version or extra fields.
    legacy={key:item for key,item in value.items() if key not in EPOCH_FIELDS}
    legacy['version']=2
    try:
        _validate_role_result_value(legacy,{key:binding[key] for key in ROLE_BINDING},reviewer=reviewer)
    except (UnicodeError,TypeError,KeyError,AttributeError) as error:
        raise ValueError('Invalid group role result shape') from error
    return value


_CHECKS_FIELDS=frozenset({'version','checkpoint_sha','product_sha256','policy_sha256','execution_local','checks'})
_REQUEST_FIELDS=frozenset({'version','role','binding','manifest','worktree','instructions','host_task_policy',
    'diff_base_sha','task_data','task_data_trust','checks','host_checks','ci_substitution','obligations'})
_CHECK_ROW_FIELDS=frozenset({'id','check_sha256','status','exit_code','started','cleanup_confirmed',
    'source_unchanged','duration_seconds'}|{stream+suffix for stream in ('stdout','stderr')
        for suffix in ('_sha256','_bytes','_captured_bytes','_truncated','_tail_unknown')})


def _check_row_shape(row):
    if not isinstance(row,dict) or set(row)!=_CHECK_ROW_FIELDS:
        raise ValueError('Individual check fields remain unversioned')
    if (not isinstance(row['id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',row['id'])
            or not isinstance(row['check_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',row['check_sha256'])
            or row['status'] not in ('passed','failed','unavailable','not_started','unknown')):
        raise ValueError('Invalid individual check identity/status')
    if row['exit_code'] is not None and type(row['exit_code']) is not int:
        raise ValueError('Invalid individual check exit code')
    for key in ('started','cleanup_confirmed','source_unchanged'):
        if type(row[key]) is not bool: raise ValueError('Invalid check Boolean')
    duration=row['duration_seconds']
    try: valid_duration=type(duration) in (int,float) and math.isfinite(duration) and duration>=0
    except OverflowError: valid_duration=False
    if not valid_duration:
        raise ValueError('Invalid check duration')
    for stream in ('stdout','stderr'):
        sha=row[stream+'_sha256']
        if sha is not None and (not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha)):
            raise ValueError('Invalid check stream digest')
        total=row[stream+'_bytes']; captured=row[stream+'_captured_bytes']
        if type(total) is not int or type(captured) is not int or not 0<=captured<=total<2**63:
            raise ValueError('Invalid check capture size')
        for suffix in ('_truncated','_tail_unknown'):
            if type(row[stream+suffix]) is not bool: raise ValueError('Invalid check capture flag')
        if row[stream+'_truncated']!=(total>captured): raise ValueError('Inconsistent check capture')
    # Passing syntax is still not process provenance: actual rows/attempts and
    # configured check membership must be proven by the future host consumer.
    if row['status']=='passed' and (row['exit_code']!=0 or not all(row[key] for key in
            ('started','cleanup_confirmed','source_unchanged')) or any(row[s+'_sha256'] is None for s in ('stdout','stderr'))):
        raise ValueError('Inconsistent passing check syntax')


def validate_group_checks_shape(value):
    """Aggregate2 syntax only; actual attempts/process rows must be proven later."""
    if (not isinstance(value,dict) or set(value)!=_CHECKS_FIELDS|EPOCH_FIELDS
            or type(value['version']) is not int or value['version']!=2):
        raise ValueError('Invalid group host-check shape')
    validate_epoch_shape({key:value[key] for key in EPOCH_FIELDS})
    for key in ('checkpoint_sha','product_sha256','policy_sha256'):
        size=40 if key=='checkpoint_sha' else 64
        if not isinstance(value[key],str) or not re.fullmatch('[a-f0-9]{'+str(size)+'}',value[key]):
            raise ValueError('Invalid group check digest')
    if type(value['execution_local']) is not bool or not isinstance(value['checks'],list):
        raise ValueError('Invalid group check rows')
    for row in value['checks']:
        _check_row_shape(row)
    return value


def validate_group_role_request_shape(value):
    """Request3 data consistency; never selects an actual run or admits a role."""
    if (not isinstance(value,dict) or set(value)!=_REQUEST_FIELDS|EPOCH_FIELDS
            or type(value['version']) is not int or value['version']!=3):
        raise ValueError('Invalid group request3 shape')
    epoch={key:value[key] for key in EPOCH_FIELDS}; validate_epoch_shape(epoch)
    binding=value['binding']; _role_binding_shape(binding)
    manifest=validate_group_stage_shape(value['manifest'])
    for key in EPOCH_FIELDS:
        if any(type(item[key]) is not type(epoch[key]) or item[key]!=epoch[key] for item in (binding,manifest)):
            raise ValueError('Group request epoch/input mismatch')
    for key in ('run_id','stage','generation','source_sha','checkpoint_sha'):
        if type(binding[key]) is not type(manifest[key]) or binding[key]!=manifest[key]:
            raise ValueError('Group request stage binding mismatch')
    if binding['input_sha256']!=digest_manifest(manifest): raise ValueError('Group request immutable input mismatch')
    if value['role'] not in (binding['stage']+'_executor',binding['stage']+'_reviewer'):
        raise ValueError('Group request role mismatch')
    if not isinstance(value['worktree'],str) or not value['worktree'] or '\x00' in value['worktree']:
        raise ValueError('Invalid group request worktree syntax')
    if not isinstance(value['instructions'],dict) or not isinstance(value['task_data'],dict) or value['task_data_trust']!='untrusted':
        raise ValueError('Invalid group request data syntax')
    policy=value['host_task_policy']
    if (not isinstance(policy,dict) or set(policy)!={'spec_path','plan_path','allowed_paths','evidence_dir'}
            or not isinstance(policy['allowed_paths'],list)
            or any(not isinstance(item,str) for item in policy['allowed_paths'])
            or any(not isinstance(policy[key],str) for key in ('spec_path','plan_path','evidence_dir'))):
        raise ValueError('Invalid group request policy syntax')
    if (not isinstance(value['checks'],list) or any(not isinstance(check,dict) for check in value['checks'])
            or not isinstance(value['obligations'],list)
            or any(not isinstance(item,str) or '\x00' in item for item in value['obligations'])):
        raise ValueError('Invalid group request obligations syntax')
    ci=value['ci_substitution']
    if (not isinstance(ci,dict) or set(ci)!={'policy','evidence','unavailable_reason'}
            or not isinstance(ci['policy'],dict)
            or ci['evidence'] is not None and not isinstance(ci['evidence'],dict)
            or ci['unavailable_reason'] is not None and not isinstance(ci['unavailable_reason'],str)):
        raise ValueError('Invalid group request CI syntax')
    ci_policy=ci['policy']
    if (set(ci_policy)!={'enabled','required_platforms'} or type(ci_policy['enabled']) is not bool
            or not isinstance(ci_policy['required_platforms'],list)):
        raise ValueError('Invalid group request CI policy')
    platforms=ci_policy['required_platforms']
    if (any(platform not in ('windows','macos','linux') for platform in platforms)
            or len(set(platforms))!=len(platforms) or bool(platforms)!=ci_policy['enabled']):
        raise ValueError('Invalid group request CI platforms')
    checks=value['host_checks']
    if value['role']=='test_reviewer':
        validate_group_checks_shape(checks)
        for key in EPOCH_FIELDS|{'checkpoint_sha','product_sha256','policy_sha256'}:
            if type(checks[key]) is not type(manifest[key]) or checks[key]!=manifest[key]:
                raise ValueError('Group host checks disagree with stage')
        if digest_manifest(checks)!=manifest['checks_sha256']: raise ValueError('Group host-check aggregate hash mismatch')
    elif checks is not None:
        raise ValueError('Unexpected host-check aggregate')
    return value
