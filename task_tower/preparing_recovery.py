"""Fixed preparing-only receipt contract; this module performs no recovery.

Approval digests are supplied by trusted host configuration. Request fields
cannot approve themselves or attest the identity of the executing source.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .service.beads import ServiceError,identity,bead_id

_FIELDS={'version','action','operation_id','connector_id','project_id','attempt_id','command_id',
    'bead_id','native_owner','base_sha','branch_sha','engine_sha','prior_engine_sha','branch',
    'command_sha256','worktree_sha256','cleanup_sha256'}
_PRIOR='3d096092621b931af2618eea1fba78bad4315491'
_SHA=re.compile('[0-9a-f]{40}')
_DIGEST=re.compile('[0-9a-f]{64}')


def fingerprint(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def parse_receipt(value):
    if not isinstance(value,dict) or set(value)!=_FIELDS:
        raise ValueError('invalid_preparing_receipt')
    if type(value['version']) is not int or value['version']!=1 or any(
            not isinstance(value[k],str) for k in _FIELDS-{'version'}):
        raise ValueError('invalid_preparing_receipt')
    try:
        for field in ('operation_id','connector_id','project_id','attempt_id','command_id','native_owner'):
            identity(value[field])
        bead_id(value['bead_id'])
    except ServiceError:
        raise ValueError('invalid_preparing_receipt') from None
    if (value['action']!='attach_existing_preparing_v1'
            or value['branch']!='codex/headless-'+value['attempt_id']
            or value['branch_sha']!=value['base_sha']
            or any(_SHA.fullmatch(value[k]) is None for k in ('base_sha','branch_sha','engine_sha','prior_engine_sha'))
            or any(_DIGEST.fullmatch(value[k]) is None for k in ('command_sha256','worktree_sha256','cleanup_sha256'))):
        raise ValueError('invalid_preparing_receipt')
    if value['prior_engine_sha']!=_PRIOR:
        raise ValueError('unsupported_prepare_contract')
    return dict(value)


def validate_receipt(value,approved,*,connector_id,source_sha):
    value=parse_receipt(value)
    if value['connector_id']!=connector_id or value['engine_sha']!=source_sha:
        raise ValueError('preparing_source_or_connector_changed')
    if not isinstance(approved,dict):raise ValueError('preparing_receipt_not_approved')
    digests=approved.get(value['project_id'],())
    if (not isinstance(digests,(set,frozenset)) or len(digests)>32
            or any(not isinstance(d,str) or _DIGEST.fullmatch(d) is None for d in digests)
            or fingerprint(value) not in digests):
        raise ValueError('preparing_receipt_not_approved')
    return dict(value)


def code_source():
    """Verify only the fixed executing package root, never a request path."""
    from .connector.worktrees import Worktrees
    root=Path(__file__).resolve().parents[1];deadline=time.monotonic()+10
    def git(*args):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('preparing_source_unverified')
        return Worktrees._git(root,*args,timeout=remaining)
    try:
        if not os.path.samefile(root,git('rev-parse','--show-toplevel')):
            raise ValueError('preparing_source_unverified')
        sha=git('rev-parse','HEAD')
        if _SHA.fullmatch(sha) is None or git('status','--porcelain'):
            raise ValueError('preparing_source_unverified')
        return sha
    except (OSError,ValueError):
        raise ValueError('preparing_source_unverified') from None
