"""Trusted host delivery into the existing pipeline; no role/receipt importer."""
from types import SimpleNamespace
from pathlib import Path
import json
import uuid

from .project_connections import safe_config_path
from .shared_queue import _PREFIX, canonical, digest, _ref


def shared_claim(project, task, delivery_id, *, consumer=None, run_id=None, intent=None):
    """Re-read server ownership, Issue criteria and assignment before each stage."""
    if str(uuid.UUID(delivery_id)) != delivery_id:
        raise ValueError('Invalid shared delivery')
    issue = project['issues'][task['issue']]
    store = project['store']
    ref = 'refs/heads/task-tower/claims/issue-' + str(issue['id'])
    pointer = _ref(store.request('GET', '/git/ref/' + ref.removeprefix('refs/')), ref)
    commit = store.request('GET', '/git/commits/' + pointer)
    if commit.get('sha') != pointer or not commit.get('message', '').startswith(_PREFIX):
        raise ValueError('Unknown shared claim')
    from .dispatch_selection import _pairs
    body = json.loads(commit['message'][len(_PREFIX):], object_pairs_hook=_pairs)
    keys = {'version','kind','repository','issue','issue_id','task_id','criteria_sha256',
            'worker_id','worker_session','claim_id','state','base_sha','assignee'}
    if intent is None:
        keys |= {'result_sha256','handoff'}
    expected_state = 'execution_intent' if intent is not None else 'awaiting_acceptance'
    if (set(body) != keys or type(body['version']) is not int or body['version'] != 1
            or body['kind'] != 'shared-task-claim' or body['state'] != expected_state
            or body['claim_id'] != delivery_id or body['repository'] != task['repository'].casefold()
            or type(body['issue']) is not int or body['issue'] != issue['number']
            or type(body['issue_id']) is not int or body['issue_id'] != issue['id']
            or body['task_id'] != task['task_id']
            or body['criteria_sha256'] != digest({k:issue.get(k) for k in ('id','number','title','body','state')})):
        raise ValueError('Shared claim binding changed')
    for key in ('worker_id','worker_session','claim_id'):
        if str(uuid.UUID(body[key])) != body[key]:
            raise ValueError('Invalid shared owner')
    if intent is not None:
        if canonical(body) != canonical(intent):raise ValueError('Foreign shared intent')
    else:
        import re
        if not re.fullmatch('[a-f0-9]{64}', body['result_sha256']):raise ValueError('Missing durable outcome')
        if (consumer is None or run_id is None or body['handoff'] != dict(version=1,kind='pipeline',consumer_sha256=consumer,run_id=run_id)):
            raise ValueError('Foreign pipeline consumer')
    if (not isinstance(body['assignee'], str) or not body['assignee']
            or {p['login'].casefold() for p in issue.get('assignees', [])} != {body['assignee'].casefold()}):
        raise ValueError('Shared assignment changed')
    main = _ref(store.request('GET', '/git/ref/heads/main'), 'refs/heads/main')
    if body['base_sha'] != main:
        raise ValueError('Stale shared base')
    return body


def _installation(settings):
    from .pipeline import _runtime, _require_native_execution
    _require_native_execution()
    if set(settings) != {'kind','connections','config','executor_config','journal'} or settings['kind'] != 'pipeline':
        raise ValueError('Invalid pipeline handoff configuration')
    supplied = {key:Path(settings[key]) for key in ('connections','config','executor_config','journal')}
    if any(not path.is_absolute() for path in supplied.values()):
        raise ValueError('Absolute private pipeline paths required')
    paths = {key:safe_config_path(path) for key,path in supplied.items()}
    _, journal, config = _runtime(SimpleNamespace(**paths))
    return config, journal


def consumer_binding(config, journal):
    return digest(dict(journal=str(journal.path.resolve()).casefold(),policy_sha256=config['policy_sha256'],
        profiles_sha256=config['_profiles_sha256']))


def validate_installation(settings, repository, plans, allowlist):
    config, journal = _installation(settings)
    rows = [t for t in config['tasks'] if t['repository'].casefold() == repository.casefold()]
    for number, plan in plans.items():
        selected = [t for t in rows if t['issue'] == int(number)]
        authorized = [t for t in allowlist if t['repository'].casefold()==repository.casefold() and t['issue']==int(number)]
        if (len(selected) != 1 or len(authorized)!=1 or selected[0].get('shared_worker') is not True
                or selected[0]['plan_path'] != plan or selected[0]['task_id']!=authorized[0]['task_id']):
            raise ValueError('Pipeline handoff outside installed scope')
    return consumer_binding(config,journal)


def deliver(claim, settings, *, expected):
    """Submit only identity. Existing journal uniqueness, roles and checks apply.

    Caller reserves a durable fence first. Exceptions are unknown outcomes, not
    retry permission. Repeated host delivery is journal-idempotent, but workers
    never reconstruct their old executable ownership after restart.
    """
    from .pipeline import _submit
    from .pipeline_policy import admission_authorized
    from .dispatch_selection import collect_snapshot
    config, journal = _installation(settings)
    if expected!=consumer_binding(config,journal):raise ValueError('Pipeline installation changed')
    rows = [t for t in config['tasks'] if t['repository'].casefold() == claim['repository']
            and t['issue'] == claim['issue'] and t['task_id'] == claim['task_id'] and t.get('shared_worker') is True]
    if len(rows) != 1:
        raise ValueError('Shared task outside pipeline scope')
    task = rows[0]
    snapshot = collect_snapshot(config['_connections'])
    if admission_authorized(config, task, snapshot, delivery_id=claim['claim_id'], shared_intent=claim) is None:
        raise ValueError('Shared admission unavailable')
    request = dict(operation='submit', delivery_id=claim['claim_id'],
        **{k:task[k] for k in ('repository','issue','task_id','runner_label')})
    if not config['_authority_check']():raise ValueError('Pipeline policy changed')
    result = _submit(request, config, journal, task)
    if result.get('status') != 'accepted':
        raise ValueError('Shared delivery unconfirmed')
    return result
