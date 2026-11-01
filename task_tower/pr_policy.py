"""Strict installation-owned authorization for the local PR worker.

Writer assertions are retained, never inferred from a process lock or chat.
Loading a policy validates its shape; it does not verify live branch protection.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .project_connections import REPOSITORY, safe_config_path

LIMITS = {
    'interval_seconds': (10, 1, 60), 'max_prs_per_tick': (10, 1, 100),
    'max_pages': (20, 1, 100), 'request_timeout_seconds': (30, 1, 120),
    'max_response_bytes': (16777216, 1, 67108864),
    'reviewer_timeout_seconds': (900, 1, 3600), 'max_review_attempts': (2, 1, 5),
    'log_max_bytes': (1048576, 1, 67108864), 'task_timeout_seconds': (86400, 60, 604800),
}
ACCOUNT = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?'
TASK = r'TT-[A-Z0-9]+(?:-[A-Z0-9]+)*'
SHA = r'[a-f0-9]{40}'
HASH = r'[a-f0-9]{64}'


def exact(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value)-set(required)-set(optional):
        raise ValueError('Invalid PR schema')


def integer(value, low=1, high=2**63-1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid PR integer')
    return value


def text(value, pattern=None):
    if not isinstance(value, str) or not value or len(value)>1024 or '\x00' in value or (pattern and not re.fullmatch(pattern,value)):
        raise ValueError('Invalid PR identity')
    return value


def identifier(value):
    text(value)
    try:
        if str(uuid.UUID(value)) != value: raise ValueError()
    except (ValueError, AttributeError): raise ValueError('Invalid PR UUID') from None
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def policy_fingerprint(policy):
    return hashlib.sha256(canonical(policy).encode('utf-8')).hexdigest()


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate PR JSON key')
        result[key]=value
    return result


def strict_json(value):
    return json.loads(value,object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def private_paths(paths, checkouts=()):
    """Validate lexical paths and every SQLite/owner sidecar before resolution."""
    expanded=[]
    for raw in paths:
        if not isinstance(raw,(str,Path)) or not Path(raw).is_absolute():
            raise ValueError('PR private paths must be absolute')
        path=safe_config_path(raw)
        group=[]
        for candidate in (path, *(Path(str(path)+suffix) for suffix in ('-journal','-wal','-shm','.owner-lock'))):
            safe_config_path(candidate)
            if candidate.exists() and candidate.stat().st_nlink!=1: raise ValueError('Hardlinked PR state')
            resolved=str(candidate.resolve()).casefold()
            for checkout in checkouts:
                root=str(Path(checkout).resolve()).casefold().rstrip('/\\')
                if resolved==root or resolved.startswith(root+os.sep): raise ValueError('Private PR state inside checkout')
            for other in expanded:
                if resolved==str(other.resolve()).casefold() or (candidate.exists() and other.exists() and os.path.samefile(candidate,other)):
                    raise ValueError('PR private path collision')
            group.append(candidate)
        expanded.extend(group)
    return tuple(safe_config_path(path) for path in paths)


def load_pr_policy(path, connections, executor_config):
    """Return normalized JSON policy; reject unknown fields and authority aliases."""
    try:
        checkouts=tuple(c.checkout for c in connections)
        private_paths((path,),checkouts)
        raw=strict_json(Path(path).read_text(encoding='utf-8'))
        required={'version','executor_config','pipeline_journal','legacy_provenance','projects'}
        exact(raw,required,LIMITS)
        if type(raw['version']) is not int or raw['version']!=1: raise ValueError('Invalid PR version')
        if not isinstance(raw['projects'],list) or not raw['projects']: raise ValueError('Missing PR projects')
        result=copy.deepcopy(raw)
        for key,(default,low,high) in LIMITS.items(): result[key]=integer(raw.get(key,default),low,high)
        profiles=executor_config['profiles']; allowlist=executor_config['allowlist']
        repositories=set(); modes=set()
        for project in result['projects']:
            exact(project,{'repository','base_ref','publisher_account','merge_enabled','exclusive_writer','tasks'})
            repository=text(project['repository'],REPOSITORY).casefold()
            matches=[c for c in connections if c.repository.casefold()==repository]
            if len(matches)!=1 or repository in repositories: raise ValueError('Foreign/duplicate PR project')
            repositories.add(repository); project['repository']=matches[0].repository
            trusted={a.casefold() for a in matches[0].trusted_publishers}
            account=text(project['publisher_account'],ACCOUNT)
            if '--' in account or account.casefold() not in trusted: raise ValueError('Untrusted PR publisher')
            if project['base_ref']!='refs/heads/main' or type(project['merge_enabled']) is not bool: raise ValueError('Invalid PR target')
            writer=project['exclusive_writer']; exact(writer,{'enabled','boundary_id','asserted_by'})
            if type(writer['enabled']) is not bool: raise ValueError('Invalid writer assertion')
            text(writer['boundary_id'],r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}')
            assertion=text(writer['asserted_by'],ACCOUNT)
            if '--' in assertion or assertion.casefold() not in trusted: raise ValueError('Unauthorized writer assertion')
            tasks=project['tasks']
            if not isinstance(tasks,list) or not tasks: raise ValueError('Missing PR tasks')
            seen=[set(),set(),set(),set()]
            for task in tasks:
                exact(task,{'issue','issue_id','task_id','pr_number','source','pipeline_run_id','legacy_card',
                    'reviewer_profile','postmerge_profile','required_checks','required_platforms'},{'recovery_of'})
                for field in ('issue','issue_id','pr_number'): integer(task[field])
                text(task['task_id'],TASK)
                for keys,field in zip(seen,('issue','issue_id','task_id','pr_number')):
                    if task[field] in keys: raise ValueError('Duplicate PR task identity')
                    keys.add(task[field])
                if not any(a['repository'].casefold()==repository and a['issue']==task['issue'] and a['task_id']==task['task_id'] for a in allowlist):
                    raise ValueError('PR task outside executor authority')
                for field in ('reviewer_profile','postmerge_profile'):
                    name=text(task[field],r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}')
                    if name not in profiles or profiles[name]['repository'].casefold()!=repository: raise ValueError('Foreign PR profile')
                mode=task['source']; modes.add(mode)
                if mode=='pipeline':
                    identifier(task['pipeline_run_id'])
                    if task['legacy_card'] is not None: raise ValueError('Ambiguous PR authority')
                elif mode=='legacy':
                    if task['pipeline_run_id'] is not None or task['legacy_card']!='docs/tasks/'+task['task_id']+'.json': raise ValueError('Invalid legacy card')
                else: raise ValueError('Invalid PR source')
                checks=task['required_checks']
                if not isinstance(checks,list) or not checks: raise ValueError('Missing required PR checks')
                contexts=set()
                for check in checks:
                    exact(check,{'context','app_id'}); context=text(check['context'])
                    if context in contexts or context=='task-tower/pr-acceptance' or any(ord(c)<32 for c in context): raise ValueError('Ambiguous PR check')
                    contexts.add(context)
                    if check['app_id'] is not None: integer(check['app_id'])
                platforms=task['required_platforms']
                if not isinstance(platforms,list) or not platforms or any(p not in ('windows','macos','linux') for p in platforms) or len(set(platforms))!=len(platforms): raise ValueError('Invalid PR platforms')
                if 'recovery_of' in task:
                    recovery=task['recovery_of']; exact(recovery,{'pr_number','merge_commit','event_sha256','baseline_receipt_sha256'})
                    integer(recovery['pr_number']); text(recovery['merge_commit'],SHA)
                    for key in ('event_sha256','baseline_receipt_sha256'): text(recovery[key],HASH)
                    if recovery['pr_number']==task['pr_number']: raise ValueError('Self recovery')
        references=[path,result['executor_config']]
        for mode,field in [('pipeline','pipeline_journal'),('legacy','legacy_provenance')]:
            if (mode in modes)!=(result[field] is not None): raise ValueError('Unused or missing PR authority')
            if result[field] is not None: references.append(result[field])
        private_paths(references,checkouts)
        for field in ('executor_config','pipeline_journal','legacy_provenance'):
            if result[field] is not None: result[field]=str(safe_config_path(result[field]))
        return result
    except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError):
        raise ValueError('Invalid PR configuration') from None


def authorized_task(policy, repository, pr_number):
    text(repository,REPOSITORY); integer(pr_number)
    matches=[dict(project,**task) for project in policy['projects']
        if project['repository'].casefold()==repository.casefold() for task in project['tasks'] if task['pr_number']==pr_number]
    if len(matches)!=1: raise ValueError('PR not uniquely authorized')
    result=copy.deepcopy(matches[0]); result.pop('tasks')
    result['readiness_reason']=('writer_boundary_required' if not result['exclusive_writer']['enabled']
        else 'merge_disabled' if not result['merge_enabled'] else None)
    return result
