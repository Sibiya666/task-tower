"""Pure group wire syntax, never journal/source/epoch or launch authority.

Actual consumers remain closed until resource and workspace producers prove
current epoch, resolution kind, accepted-main proof and input-specific delta.
In particular, nullable epoch0 syntax cannot establish pinned resolution.
"""
import re

from .pipeline_inputs import STAGE_FIELDS, validate_stage_manifest
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
