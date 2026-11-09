"""Trusted project delivery scope; never supplied by model output or task prose."""
import copy
import re

REPOSITORY=re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*\Z')


def policies(projects,legacy,configured=None):
    result={p:dict(mode='task_tower',repository=r,base='main') for p,r in legacy.items()}
    if configured is not None:
        if not isinstance(configured,dict):raise ValueError('invalid_delivery_policy')
        for p,value in configured.items():
            if p in result:raise ValueError('duplicate_delivery_policy')
            result[p]=copy.deepcopy(value)
    if set(result)-set(projects):raise ValueError('delivery_project_forbidden')
    for value in result.values():
        if not isinstance(value,dict):raise ValueError('invalid_delivery_policy')
        mode=value.get('mode')
        if mode=='local':
            if set(value)!={'mode'}:raise ValueError('local_delivery_scope')
            continue
        if mode not in ('task_tower','owner_pr') or set(value)!={'mode','repository','base'}:
            raise ValueError('invalid_delivery_policy')
        if not isinstance(value['repository'],str) or not REPOSITORY.fullmatch(value['repository']):
            raise ValueError('invalid_repository')
        base=value['base']
        if (not isinstance(base,str) or not 1<=len(base)<=200 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*',base)
                or '..' in base or '//' in base or base.startswith('refs/')
                or any(part.startswith('.') or part.endswith(('.','.lock')) for part in base.split('/'))
                or base.endswith('/')):raise ValueError('invalid_base_branch')
        if mode=='task_tower' and base!='main':raise ValueError('task_tower_main_required')
    return result


def validate_receipt(receipt,policy,head,base):
    fields={'kind','policy','head_sha','base_sha'}|({'pr_number'} if policy.get('mode')=='owner_pr' else set())
    if (policy.get('mode') not in ('local','owner_pr') or not isinstance(receipt,dict) or set(receipt)!=fields
            or receipt.get('policy')!=policy or receipt.get('head_sha')!=head or receipt.get('base_sha')!=base
            or receipt.get('kind')!=('reviewed.pr' if policy['mode']=='owner_pr' else 'reviewed.local')
            or (policy['mode']=='owner_pr' and (type(receipt['pr_number']) is not int or receipt['pr_number']<1))):
        raise ValueError('invalid_saved_result')
    return copy.deepcopy(receipt)
