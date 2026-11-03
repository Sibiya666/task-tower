"""Installation-owned OpenCode policy. Registration is never native authority."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .opencode_files import read_bound, safe_path, validate_identity

VERSION='2.2.5'
SOURCE_REVISION='9bbb8ce18c80f099e0e448775f59d965ead40a21'
SURFACE_ID='opencode-v2.2.5-discovery-v1'
COLLECTOR_REVISION='opencode-v2.2.5-discovery-v1'
MAX_BYTES=1048576
POLICY_KEYS={'version','source_revision','executable_sha256','policy_id','config_scope','config_discovery_sha256','policy_evidence_path','policy_evidence_sha256','native_launch_authorized'}
EVIDENCE_KEYS={'version','policy_id','native_version','source_revision','executable_sha256','collector_revision','source_audit_sha256','reviewer_id','reviewed_at','scope','inventory','environment','qualification'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def discovery_digest(inventory,environment):
    return hashlib.sha256(canonical(dict(inventory=inventory,environment=environment))).hexdigest()


def _sha(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value): raise ValueError('invalid_digest')


def _pairs(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError('duplicate_key')
        result[key]=value
    return result


def _json(data):
    return json.loads(data.decode('utf-8',errors='strict'),object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid_number')))


def _keys(value,keys):
    if not isinstance(value,dict) or set(value)!=keys: raise ValueError('invalid_schema')


def _name(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',value): raise ValueError('invalid_identity_name')


def _scope(scope):
    _keys(scope,{'platform','home','global_config','system_config','runs_root','source_sha','worktree_template'})
    if scope['platform'] not in ('windows','linux','macos'): raise ValueError('invalid_platform')
    for name in ('home','global_config','system_config','runs_root'): safe_path(scope[name])
    if not isinstance(scope['source_sha'],str) or not re.fullmatch('[a-f0-9]{40}',scope['source_sha']): raise ValueError('invalid_source')
    if scope['worktree_template']!='{runs_root}/{run_id}/{attempt_id}/worktree': raise ValueError('invalid_worktree_template')


def _component(value):
    if (not isinstance(value,str) or not value or value in ('.','..') or value.endswith(('.', ' '))
            or any(ord(c)<32 or c in '/\\:<>"|?*' for c in value)):
        raise ValueError('invalid_component')


def validate_inventory(value,*,scope=None):
    if not isinstance(value,list) or len(value)>4096: raise ValueError('invalid_inventory')
    seen=set();total=0;templates=[];count=len(value)
    for row in value:
        if not isinstance(row,dict): raise ValueError('invalid_inventory')
        kind=row.get('kind')
        if kind=='worktree_template':
            if scope is None:raise ValueError('template_is_not_observation')
            from .opencode_templates import validate_template
            additional,size=validate_template(row,scope);count+=additional;total+=size;templates.append(row)
            continue
        path=safe_path(row.get('path'))
        key=str(path).casefold()
        if key in seen: raise ValueError('duplicate_inventory_path')
        seen.add(key);_name(row.get('role'))
        if kind=='missing':
            _keys(row,{'kind','path','role','parent_identity'})
            parent=row['parent_identity'];_keys(parent,{'path','identity','missing_components'})
            root=safe_path(parent['path']);validate_identity(parent['identity'],kind='directory')
            parts=parent['missing_components']
            if not isinstance(parts,list) or not parts or len(parts)>64: raise ValueError('invalid_missing_chain')
            for part in parts: _component(part)
            if root.joinpath(*parts)!=path: raise ValueError('invalid_missing_chain')
        elif kind=='file':
            _keys(row,{'kind','path','role','identity','bytes','sha256'})
            validate_identity(row['identity'],kind='file');_sha(row['sha256'])
            if type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_BYTES: raise ValueError('invalid_file_size')
            total+=row['bytes']
        elif kind=='directory':
            _keys(row,{'kind','path','role','identity','members'});validate_identity(row['identity'],kind='directory')
            members=row['members']
            if not isinstance(members,list) or len(members)>256: raise ValueError('invalid_membership')
            names=[]
            for member in members:
                _keys(member,{'name','kind','identity'});_component(member['name'])
                validate_identity(member['identity'],kind=member['kind'])
                names.append(member['name'])
            if names!=sorted(names) or len(set(n.casefold() for n in names))!=len(names): raise ValueError('invalid_membership')
        else: raise ValueError('invalid_inventory_kind')
    if total>8388608 or count>4096: raise ValueError('inventory_byte_limit')
    if scope is not None:
        if len(templates)!=1:raise ValueError('exactly_one_template_required')
        from .opencode_templates import validate_anchors
        validate_anchors(value,scope)


def _environment(value,platform):
    _keys(value,{'names','presence_sha256','values_sha256'})
    names=value['names']
    if not isinstance(names,list) or len(names)>4096 or any(not isinstance(name,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,199}',name) for name in names) or names!=sorted(set(names)):
        raise ValueError('invalid_environment')
    _sha(value['presence_sha256']);_sha(value['values_sha256'])
    if platform=='windows' and len({name.casefold() for name in names})!=len(names): raise ValueError('invalid_environment')


def _load_policy(raw,checkouts,*,run_roots=()):
    _keys(raw,POLICY_KEYS)
    if raw['version']!=VERSION or raw['source_revision']!=SOURCE_REVISION or raw['config_scope']!='existing-user-approved': raise ValueError('unsupported_policy')
    for key in ('executable_sha256','config_discovery_sha256','policy_evidence_sha256'): _sha(raw[key])
    _name(raw['policy_id'])
    if type(raw['native_launch_authorized']) is not bool: raise ValueError('invalid_permission')
    policy_path=safe_path(raw['policy_evidence_path'])
    data=read_bound(str(policy_path),limit=MAX_BYTES,expected=raw['policy_evidence_sha256'],private_roots=[*checkouts,*run_roots],utf8=True)
    evidence=_json(data);_keys(evidence,EVIDENCE_KEYS)
    if type(evidence['version']) is not int or evidence['version']!=1 or evidence['native_version']!=VERSION or evidence['source_revision']!=SOURCE_REVISION or evidence['collector_revision']!=COLLECTOR_REVISION:
        raise ValueError('unsupported_evidence')
    for key in ('policy_id','executable_sha256'):
        if evidence[key]!=raw[key]: raise ValueError('evidence_binding_mismatch')
    _name(evidence['reviewer_id'])
    stamp=evidence['reviewed_at']
    if not isinstance(stamp,str): raise ValueError('invalid_review_date')
    parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
    if parsed.utcoffset() is None: raise ValueError('invalid_review_date')
    _scope(evidence['scope']);validate_inventory(evidence['inventory'],scope=evidence['scope']);_environment(evidence['environment'],evidence['scope']['platform'])
    from .opencode_templates import validate_anchors
    from .opencode_files import identity
    anchor=validate_anchors(evidence['inventory'],evidence['scope'])
    if identity(safe_path(evidence['scope']['runs_root']).lstat())!=anchor:raise ValueError('output_root_identity_changed')
    if discovery_digest(evidence['inventory'],evidence['environment'])!=raw['config_discovery_sha256']: raise ValueError('discovery_binding_mismatch')
    roots=[*checkouts,*run_roots,evidence['scope']['runs_root']]
    if any(policy_path.is_relative_to(safe_path(str(root))) for root in roots): raise ValueError('private_artifact_collision')
    q=evidence['qualification']
    _keys(q,{'source_audit','fixture_report','supported_surface_id','native_probe_authorized','native_run_authorized','tool_policy'})
    if q['supported_surface_id']!=SURFACE_ID: raise ValueError('unsupported_surface')
    for key in ('native_probe_authorized','native_run_authorized'):
        if type(q[key]) is not bool: raise ValueError('invalid_permission')
    if q['native_run_authorized'] and not q['native_probe_authorized']: raise ValueError('invalid_permission')
    paths={policy_path}
    for key in ('source_audit','fixture_report','tool_policy'):
        ref=q[key];_keys(ref,{'path','sha256'});_sha(ref['sha256']);path=safe_path(ref['path'])
        if path in paths: raise ValueError('artifact_alias')
        paths.add(path)
        read_bound(str(path),limit=MAX_BYTES,expected=ref['sha256'],private_roots=roots,utf8=True)
    if evidence['source_audit_sha256']!=q['source_audit']['sha256']: raise ValueError('source_audit_binding_mismatch')
    return evidence


def validate_opencode_policy(raw:dict, *, checkouts:list[Path])->dict:
    try:
        _load_policy(raw,checkouts)
        return dict(raw)
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,OverflowError):
        raise ValueError('Invalid OpenCode policy') from None


def verify_opencode_preflight(profile:dict, *, attempt:dict, environ:dict[str,str])->dict:
    """Verify a pre-PROBE observation; allowed is never native-run authority.

    The owning future foreground branch must separately enforce run permission,
    bound actual successful version evidence, and fresh preflight before launch.
    This function neither invokes a probe nor sets any capability true.
    """
    def denied(reason):return dict(allowed=False,no_child_created=True,reasons=[reason])
    from .executor_profiles import profile_fingerprint,_pins
    from .opencode_files import digest_executable
    from .opencode_discovery import opencode_environment,environment_reasons,_collect,compare_opencode_discovery
    import os
    import uuid
    try:
        if not isinstance(profile,dict) or profile.get('kind')!='opencode':return denied('unsupported_kind')
        if attempt.get('profile_fingerprint')!=profile_fingerprint(profile):return denied('profile_binding_mismatch')
        try:evidence=_load_policy(profile['opencode'],[Path(profile['checkout'])],run_roots=[Path(profile['runs_dir'])])
        except (OSError,ValueError,TypeError,KeyError,UnicodeError):return denied('invalid_policy_evidence')
        policy=profile['opencode'];q=evidence['qualification'];scope=evidence['scope']
        if policy['native_launch_authorized'] is not True:return denied('native_launch_not_authorized')
        if q['native_probe_authorized'] is not True:return denied('native_probe_not_authorized')
        if scope['platform']!='windows' or os.name!='nt':return denied('unsupported_platform')
        for key in ('run_id','attempt_id'):
            if not isinstance(attempt.get(key),str) or str(uuid.UUID(attempt[key]))!=attempt[key]:return denied('invalid_attempt_binding')
        worktree=safe_path(attempt['worktree'])
        expected=Path(scope['runs_root'])/attempt['run_id']/attempt['attempt_id']/'worktree'
        if worktree!=expected or Path(profile['runs_dir'])!=Path(scope['runs_root']):return denied('worktree_binding_mismatch')
        if attempt.get('source_sha')!=scope['source_sha']:return denied('source_binding_mismatch')
        child=opencode_environment(environ,str(worktree))
        if environment_reasons(child,scope['platform']):return denied('unsupported_environment')
        try:_pins(profile['superpowers'])
        except (OSError,ValueError,TypeError,KeyError,UnicodeError):return denied('instruction_drift')
        if not isinstance(profile['argv'],list) or len(profile['argv'])!=1:return denied('unsupported_executable_wrapper')
        try:digest_executable(profile['argv'][0],policy['executable_sha256'])
        except (OSError,ValueError,TypeError):return denied('executable_drift')
        from .executor_worker import _git
        if (_git(worktree,'rev-parse','HEAD')!=scope['source_sha'] or
                _git(profile['checkout'],'rev-parse','--verify',profile['source_ref']+'^{commit}')!=scope['source_sha'] or
                Path(_git(worktree,'rev-parse','--show-toplevel'))!=worktree or _git(worktree,'status','--porcelain')):
            return denied('source_binding_mismatch')
        # File grants are derived only from the SAME pinned, safely opened and
        # validated evidence, never caller inventory or an approval callback.
        from .opencode_templates import file_grants
        grants=file_grants(evidence['inventory'],scope,worktree)
        observed=_collect(scope,worktree=str(worktree),environ=child,_grants=grants)
        if 'discovery_changed' in observed['reasons']:
            observed=_collect(scope,worktree=str(worktree),environ=child,_grants=grants)
        reasons=compare_opencode_discovery(evidence,observed)
        if reasons:return dict(allowed=False,no_child_created=True,reasons=reasons)
        return dict(allowed=True,worktree=str(worktree),environment=child,
                    observation_sha256=discovery_digest(observed['inventory'],observed['environment']),
                    policy_evidence_sha256=policy['policy_evidence_sha256'])
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,AttributeError):
        return denied('preflight_unavailable')
