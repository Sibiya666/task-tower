"""Fixed installation-policy invocation and locally validated result protocol."""
import json
from pathlib import Path
from .project_connections import safe_config_path

def build_invocation(attempt, profile):
    if not isinstance(profile,dict) or profile.get('kind') not in ('codex','custom'):
        raise ValueError('Unsupported executor kind for generic launch')
    if profile['kind']=='custom':
        if not profile.get('trusted'): raise ValueError('Untrusted custom executor')
        return [*profile['argv'],'--request',str(attempt['request_path']),'--result',str(attempt['result_path'])]
    argv=[*profile['argv'],'exec','--json','--sandbox','workspace-write','--output-schema',str(attempt['schema_path']),'--output-last-message',str(attempt['result_path']),'-C',str(attempt['worktree'])]
    if profile.get('approve_for_me'): argv.append('--approve-for-me')
    return [*argv,'Read the execution request and pinned instructions at '+str(attempt['request_path'])+'. Return only the required result JSON.']

def _unique(pairs):
    value={}
    for key,item in pairs:
        if key in value: raise ValueError('Duplicate result key')
        value[key]=item
    return value

def validate_result(path, attempt, max_bytes):
    try:
        path=safe_config_path(path)
        if not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size>max_bytes: raise ValueError('Unsafe result')
        value=json.loads(path.read_bytes().decode('utf-8'),object_pairs_hook=_unique)
        if not isinstance(value,dict) or set(value)!={'version','run_id','attempt_id','source_sha','status','summary'} or type(value['version']) is not int or value['version']!=1: raise ValueError('Invalid result schema')
        if any(value[k]!=attempt[k] for k in ('run_id','attempt_id','source_sha')) or value['status'] not in ('completed','failed','needs_input') or not isinstance(value['summary'],str) or len(value['summary'].encode('utf-8'))>4096: raise ValueError('Invalid result binding')
        return value
    except (OSError,UnicodeError,TypeError,KeyError) as error: raise ValueError('Invalid execution result') from error

def result_schema(attempt):
    properties={key:dict(type='string',const=attempt[key]) for key in ('run_id','attempt_id','source_sha')}
    properties.update(version=dict(type='integer',const=1),status=dict(type='string',enum=['completed','failed','needs_input']),summary=dict(type='string',maxLength=4096))
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)

def capabilities(profile):
    return dict(configured=True,executable=Path(profile['argv'][0]).is_file(),probed=False,verified=False,events=False,resume=False)


ROLE_NAMES=frozenset(stage+'_'+kind for stage in ('spec','development','test') for kind in ('executor','reviewer'))
ROLE_BINDING=('run_id','attempt_id','instance_id','stage','generation','source_sha','checkpoint_sha','input_sha256')
FINDING_CODES=('criteria_unmet','plan_incomplete','product_defect','test_failure','evidence_missing','stale_input','environment_unavailable')


def build_role_invocation(attempt:dict, profile:dict, *, role:str) -> list[str]:
    if role not in ROLE_NAMES: raise ValueError('Unknown pipeline role')
    if not isinstance(profile,dict) or profile.get('kind') not in ('codex','custom'):
        raise ValueError('Unsupported executor kind for pipeline launch')
    if profile['kind']=='custom': return build_invocation(attempt,profile)
    argv=build_invocation(attempt,profile)
    argv[argv.index('--sandbox')+1]='workspace-write' if role in ('spec_executor','development_executor') else 'read-only'
    return argv


def role_result_schema(binding:dict, *, reviewer:bool) -> dict:
    properties={key:dict(type='integer' if key=='generation' else 'string',const=binding[key]) for key in ROLE_BINDING}
    properties.update(version=dict(type='integer',const=2),summary=dict(type='string',maxLength=4096))
    if reviewer:
        stages=['spec','development','test']; returns=stages[:stages.index(binding['stage'])+1]
        finding=dict(type='object',properties=dict(code=dict(type='string',enum=list(FINDING_CODES)),path=dict(type=['string','null']),line=dict(type=['integer','null'],minimum=1)),required=['code','path','line'],additionalProperties=False)
        properties.update(verdict=dict(type='string',enum=['approve','reject','needs_input']),return_stage=dict(type=['string','null'],enum=[None,*returns]),findings=dict(type='array',maxItems=32,items=finding))
    else: properties['status']=dict(type='string',enum=['completed','failed','needs_input'])
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)


def validate_role_result(path:Path, binding:dict, max_bytes:int=65536, *, reviewer:bool) -> dict:
    from .pipeline_inputs import _relative
    try:
        path=safe_config_path(path)
        if type(max_bytes) is not int or max_bytes<1 or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size>max_bytes: raise ValueError('Unsafe role result')
        value=json.loads(path.read_bytes().decode('utf-8'),object_pairs_hook=_unique)
        schema=role_result_schema(binding,reviewer=reviewer)
        if not isinstance(value,dict) or set(value)!=set(schema['required']) or type(value['version']) is not int or value['version']!=2: raise ValueError('Invalid role result schema')
        if type(value['generation']) is not int or any(type(value[k]) is not type(binding[k]) or value[k]!=binding[k] for k in ROLE_BINDING): raise ValueError('Invalid role result binding')
        if not isinstance(value['summary'],str) or len(value['summary'].encode('utf-8'))>4096: raise ValueError('Invalid role summary')
        if not reviewer:
            if value['status'] not in ('completed','failed','needs_input'): raise ValueError('Invalid role status')
        else:
            if value['verdict'] not in ('approve','reject','needs_input'): raise ValueError('Invalid verdict')
            if value['verdict']=='reject':
                if value['return_stage'] not in schema['properties']['return_stage']['enum'][1:]: raise ValueError('Invalid return route')
            elif value['return_stage'] is not None: raise ValueError('Unexpected return route')
            if not isinstance(value['findings'],list) or len(value['findings'])>32: raise ValueError('Invalid findings')
            for finding in value['findings']:
                if not isinstance(finding,dict) or set(finding)!={'code','path','line'} or finding['code'] not in FINDING_CODES: raise ValueError('Invalid finding')
                if finding['path'] is not None: _relative(finding['path'])
                if finding['line'] is not None and (type(finding['line']) is not int or finding['line']<1): raise ValueError('Invalid finding line')
        return value
    except (OSError,UnicodeError,TypeError,KeyError,AttributeError) as error:
        raise ValueError('Invalid role result') from error
