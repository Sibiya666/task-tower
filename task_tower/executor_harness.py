"""Fixed installation-policy invocation and locally validated result protocol."""
import json
from pathlib import Path
from .project_connections import safe_config_path

def build_invocation(attempt, profile):
    if profile['kind']=='claude':
        from .claude_adapter import build_claude_invocation
        return build_claude_invocation(attempt,profile)
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
    if profile.get('kind')=='claude':
        from .claude_adapter import claude_capabilities
        return claude_capabilities(profile)
    return dict(configured=True,executable=Path(profile['argv'][0]).is_file(),probed=False,verified=False,events=False,resume=False)
