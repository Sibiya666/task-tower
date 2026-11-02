"""Read-only installation policy for groups; never execution/acceptance authority.

executor_config is the normalized result of load_executor_config. pipeline_config
is a normalized private task policy, not Issue/model data. This module deliberately
imports no pipeline runtime: bindings need fresh host admission and journal gates.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import uuid

from .dispatch_selection import _pairs, TASK_ID
from .executor_profiles import _path, _pins, _private, profile_fingerprint
from .project_connections import REPOSITORY


NAME = r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}'
ROLES = tuple(stage + '_' + kind for stage in ('spec', 'development', 'test')
              for kind in ('executor', 'reviewer'))
TASK_FIELDS = {'repository', 'issue', 'task_id', 'runner_label', 'executor_profile',
               'components', 'allowed_paths', 'spec_path', 'plan_path', 'evidence_dir',
               'checks', 'ci_substitution', 'publish'}
LIMITS = {'max_active': (2, 1, 2), 'task_timeout_seconds': (7200, 1, 86400),
          'role_timeout_seconds': (900, 1, 3600), 'max_reworks': (2, 0, 5),
          'max_processes': (36, 6, 100), 'log_max_bytes': (1048576, 1, 67108864)}


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid group integer')
    return value



def _cap(value):
    return None if value is None else _integer(value, 1, 2**63 - 1)


def _minimum(*values):
    present = [v for v in values if v is not None]
    return min(present) if present else None


def _counts(config):
    version = config.get('version')
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Invalid capacity policy version')
    if version == 1:
        return dict(max_executors=_integer(config.get('max_active', 2), 1, 2), max_inflight=None)
    if 'max_active' in config:
        raise ValueError('Legacy capacity in version2')
    value = config.get('capacity', dict(max_executors=None, max_inflight=None))
    if not isinstance(value, dict) or set(value) != {'max_executors', 'max_inflight'}:
        raise ValueError('Invalid capacity counts')
    return {k: _cap(v) for k, v in value.items()}


def _capacity(value):
    default = dict(mode='auto', max_executors=None, max_inflight=None,
                   max_cpu_millis=None, max_memory_bytes=None, fallback=None)
    if value is None or not isinstance(value, dict) or set(value) != set(default) or value['mode'] != 'auto':
        raise ValueError('Invalid automatic capacity')
    result = dict(mode='auto', **{k: _cap(value[k]) for k in
        ('max_executors', 'max_inflight', 'max_cpu_millis', 'max_memory_bytes')})
    fallback = value['fallback']
    if fallback is not None:
        if not isinstance(fallback, dict) or set(fallback) != {'cpu_millis', 'memory_bytes', 'max_executors'}:
            raise ValueError('Invalid fallback grant')
        fallback = {k: _integer(v, 1, 2**63 - 1) for k, v in fallback.items()}
    return dict(result, fallback=fallback)


def _resources(executor, projects):
    resources = executor.get('harness_resources')
    if not isinstance(resources, dict) or not resources:
        raise ValueError('Missing harness resource grants')
    normalized, aliases = {}, {}
    for profile_id, raw in resources.items():
        profile = executor['profiles'][_name(profile_id)]
        if not isinstance(raw, dict) or set(raw) != {'pool_id', 'cpu_millis', 'memory_bytes', 'max_parallel'}:
            raise ValueError('Invalid harness resource grant')
        row = dict(pool_id=_name(raw['pool_id']),
            cpu_millis=_integer(raw['cpu_millis'], 1, 2**63 - 1),
            memory_bytes=_integer(raw['memory_bytes'], 1, 2**63 - 1), max_parallel=_cap(raw['max_parallel']))
        authority = tuple(profile['argv'])
        if authority in aliases and aliases[authority] != row['pool_id']:
            raise ValueError('Harness alias splits pool')
        aliases[authority] = row['pool_id']
        normalized[profile_id] = row
    for project in projects:
        for group in project['groups']:
            if any(p not in normalized for p in group['role_profiles'].values()):
                raise ValueError('Missing selected harness grant')
    return normalized

def _name(value, pattern=NAME):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid group identity')
    return value


def _components(value):
    if not isinstance(value, list) or not value or any(
            not isinstance(c, str) or c != '*' and not re.fullmatch(NAME, c) for c in value):
        raise ValueError('Invalid group components')
    if len(set(value)) != len(value) or '*' in value and value != ['*']:
        raise ValueError('Ambiguous group components')
    return sorted(value)


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or value.startswith('/') or any(p in ('', '.', '..') or p.casefold() == '.git'
                for p in value.rstrip('/').split('/'))):
        raise ValueError('Invalid group task path')
    for part in value.rstrip('/').split('/'):
        if (part.endswith(('.', ' ')) or any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in part)
                or re.fullmatch(r'(?i:con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])', part.split('.')[0])):
            raise ValueError('Nonportable group task path')
    return value


def _contains(prefix, name):
    return name == prefix or prefix.endswith('/') and name.startswith(prefix)


def _identity(row):
    return (row['repository'].casefold(), row['issue'], row['task_id'])


def _paths(path, journal, checkouts, pipeline):
    """Check private paths and their SQLite sidecars without creating anything."""
    inputs = [path]
    if '_policy_path' in pipeline:
        inputs.append(_path(str(pipeline['_policy_path'])))
    families = [[_path(str(p) + suffix) for suffix in ('', '-journal', '-wal', '-shm')]
                for p in [*inputs, journal]]
    for family in families:
        for candidate in family:
            _private(candidate, checkouts)
    all_paths = [p for family in families for p in family]
    if len({str(p.resolve()).casefold() for p in all_paths}) != len(all_paths):
        raise ValueError('Group private path collision')


def _profile(profile_id, profiles, connections):
    _name(profile_id)
    profile = profiles[profile_id]
    connection = connections[profile['repository'].casefold()]
    checkout = _path(profile['checkout'], directory=True)
    if (not checkout.is_dir() or checkout != connection.checkout or profile['runner_label'] != connection.runner_label
            or profile['repository'].casefold() != connection.repository.casefold()):
        raise ValueError('Group profile scope mismatch')
    _pins(profile['superpowers'])
    return profile


def _task_rows(pipeline, executor, connections):
    if type(pipeline.get('version')) is not int or pipeline['version'] not in (1, 2) or not isinstance(pipeline.get('tasks'), list):
        raise ValueError('Invalid private pipeline task policy')
    limits = {key: _integer(pipeline.get(key, default), low, high)
              for key, (default, low, high) in LIMITS.items() if key != 'max_active' or pipeline['version'] == 1}
    _counts(pipeline)
    profiles = executor['profiles']
    rows, aliases = {}, set()
    for value in pipeline['tasks']:
        if not isinstance(value, dict) or set(value) != TASK_FIELDS:
            raise ValueError('Invalid private pipeline task')
        row = copy.deepcopy(value)
        repository = _name(row['repository'], REPOSITORY).casefold()
        connection = connections[repository]
        row['repository'] = connection.repository.casefold()
        _integer(row['issue'], 1, 2**63 - 1)
        _name(row['task_id'], TASK_ID)
        _name(row['runner_label'])
        profile = _profile(row['executor_profile'], profiles, connections)
        auth = [a for a in executor['allowlist'] if a['repository'].casefold() == repository
                and all(a[k] == row[k] for k in ('issue', 'task_id', 'runner_label'))
                and a['profile'] == row['executor_profile']]
        if (len(auth) != 1 or profile['repository'].casefold() != repository
                or profile['runner_label'] != row['runner_label']):
            raise ValueError('Task lacks existing executor authority')
        alias = (repository, row['task_id'])
        if (repository, row['issue']) in rows or alias in aliases:
            raise ValueError('Duplicate private task identity')
        aliases.add(alias)
        row['components'] = _components(row['components'])
        paths = row['allowed_paths']
        if not isinstance(paths, list) or not paths:
            raise ValueError('Missing task paths')
        for name in paths:
            _relative(name)
        for i, name in enumerate(paths):
            if any(_contains(name.casefold(), other.casefold()) or _contains(other.casefold(), name.casefold())
                   for other in paths[i + 1:]):
                raise ValueError('Overlapping task paths')
        for key in ('spec_path', 'plan_path', 'evidence_dir'):
            _relative(row[key])
            if not any(_contains(p, row[key]) for p in paths):
                raise ValueError('Artifact outside authorized paths')
        if (row['spec_path'].endswith('/') or row['plan_path'].endswith('/')
                or row['spec_path'].casefold() == row['plan_path'].casefold()
                or not row['evidence_dir'].endswith('/')
                or any(_contains(row['evidence_dir'].casefold(), row[k].casefold())
                       or row['evidence_dir'].casefold().startswith(row[k].casefold() + '/')
                       for k in ('spec_path', 'plan_path'))):
            raise ValueError('Overlapping task artifacts')
        checks = row['checks']
        seen = set()
        if not isinstance(checks, list) or not checks:
            raise ValueError('Missing installed task checks')
        for check in checks:
            if not isinstance(check, dict) or set(check) != {'id', 'argv', 'timeout_seconds'}:
                raise ValueError('Invalid task check')
            _name(check['id'])
            if check['id'] in seen:
                raise ValueError('Duplicate task check')
            seen.add(check['id'])
            argv = check['argv']
            if not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or '\x00' in a for a in argv):
                raise ValueError('Invalid installed check argv')
            executable = _path(argv[0])
            if not executable.is_file() or executable.suffix.casefold() in ('.bat', '.cmd'):
                raise ValueError('Invalid check executable')
            _integer(check['timeout_seconds'], 1, 3600)
        ci = row['ci_substitution']
        if (not isinstance(ci, dict) or set(ci) != {'enabled', 'required_platforms'}
                or type(ci['enabled']) is not bool or not isinstance(ci['required_platforms'], list)
                or any(not isinstance(p, str) or p not in ('windows', 'macos', 'linux') for p in ci['required_platforms'])
                or len(set(ci['required_platforms'])) != len(ci['required_platforms'])
                or bool(ci['required_platforms']) != ci['enabled']):
            raise ValueError('Invalid installed CI policy')
        publish = row['publish']
        if (not isinstance(publish, dict) or set(publish) != {'enabled', 'remote', 'base_ref', 'publisher_account'}
                or type(publish['enabled']) is not bool or publish['remote'] != 'origin'
                or publish['base_ref'] != 'refs/heads/main' or not isinstance(publish['publisher_account'], str)
                or publish['publisher_account'].casefold() not in [p.casefold() for p in connection.trusted_publishers]):
            raise ValueError('Invalid installed publication policy')
        rows[(repository, row['issue'])] = row
    return rows, limits


def _project(value, tasks, profiles, connections, maximum, version=1):
    required = {'repository', 'groups', 'routes', 'aggregates'}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {'base_update', 'accepted_main_sources'}:
        raise ValueError('Invalid group project')
    repository = _name(value['repository'], REPOSITORY).casefold()
    if repository not in connections or any(not isinstance(value[k], list) for k in ('groups', 'routes', 'aggregates')):
        raise ValueError('Unknown group project')
    groups = {}
    for raw in value['groups']:
        if not isinstance(raw, dict) or not {'id', 'components', 'role_profiles'} <= set(raw) or set(raw) - ({'id', 'capacity', 'components', 'role_profiles'} | ({'max_inflight'} if version == 2 else set())):
            raise ValueError('Invalid group')
        name = _name(raw['id'])
        if name in groups:
            raise ValueError('Duplicate group')
        roles = raw['role_profiles']
        if not isinstance(roles, dict) or set(roles) != set(ROLES):
            raise ValueError('Missing explicit group roles')
        for profile_id in roles.values():
            profile = _profile(profile_id, profiles, connections)
            if profile['repository'].casefold() != repository:
                raise ValueError('Foreign group role profile')
        groups[name] = dict(id=name, capacity=(_integer(raw.get('capacity', 1), 1, maximum) if version == 1 else _cap(raw.get('capacity'))),
                            components=_components(raw['components']), role_profiles=copy.deepcopy(roles))
        if version == 2:
            groups[name]['max_inflight'] = _cap(raw.get('max_inflight'))
    routes = []
    for raw in value['routes']:
        if not isinstance(raw, dict) or set(raw) != {'issue', 'task_id', 'group'}:
            raise ValueError('Invalid explicit route')
        _integer(raw['issue'], 1, 2**63 - 1)
        _name(raw['task_id'], TASK_ID)
        task = tasks[(repository, raw['issue'])]
        group = groups[_name(raw['group'])]
        if task['task_id'] != raw['task_id'] or any(p != task['executor_profile'] for p in group['role_profiles'].values()):
            raise ValueError('Route widens task profile authority')
        if group['components'] != ['*'] and not set(task['components']) <= set(group['components']):
            raise ValueError('Route exceeds group component ownership')
        routes.append(copy.deepcopy(raw))
    aggregates, seen = [], set()
    for raw in value['aggregates']:
        if not isinstance(raw, dict) or set(raw) != {'issue', 'task_id', 'required_children'}:
            raise ValueError('Invalid aggregate policy')
        _integer(raw['issue'], 1, 2**63 - 1)
        _name(raw['task_id'], TASK_ID)
        if raw['issue'] in seen or not any(r['issue'] == raw['issue'] and r['task_id'] == raw['task_id'] for r in routes):
            raise ValueError('Aggregate lacks its own route')
        seen.add(raw['issue'])
        children = raw['required_children']
        if not isinstance(children, list) or not children:
            raise ValueError('Missing required children')
        children = [_name(c, REPOSITORY + r'#[1-9][0-9]*').casefold() for c in children]
        if len(set(children)) != len(children):
            raise ValueError('Duplicate required child')
        aggregates.append(dict(issue=raw['issue'], task_id=raw['task_id'], required_children=sorted(children)))
    update = value.get('base_update', dict(enabled=False, max_updates=0))
    if not isinstance(update, dict) or set(update) != {'enabled', 'max_updates'} or type(update['enabled']) is not bool:
        raise ValueError('Invalid base update grant')
    count = _integer(update['max_updates'], 0, 2)
    if bool(count) != update['enabled']:
        raise ValueError('Invalid base update allowance')
    grants, seen = [], set()
    if not isinstance(value.get('accepted_main_sources', []), list):
        raise ValueError('Invalid initial source grants')
    for raw in value.get('accepted_main_sources', []):
        if not isinstance(raw, dict) or set(raw) != {'executor_profile', 'profile_sha256', 'anchor_sha'}:
            raise ValueError('Invalid accepted-main source grant')
        profile_id = _name(raw['executor_profile'])
        profile = _profile(profile_id, profiles, connections)
        if (profile_id in seen or profile['repository'].casefold() != repository
                or _name(raw['profile_sha256'], '[a-f0-9]{64}') != profile_fingerprint(profile)):
            raise ValueError('Source grant lacks exact profile authority')
        _name(raw['anchor_sha'], '[a-f0-9]{40}')
        seen.add(profile_id)
        grants.append(copy.deepcopy(raw))
    return dict(repository=repository, groups=list(groups.values()), routes=routes,
                aggregates=aggregates, base_update=copy.deepcopy(update), accepted_main_sources=grants)


def load_group_config(path: Path, connections: list, executor_config: dict, pipeline_config: dict) -> dict:
    """Validate only private policy; do not claim, create, migrate or prove work.

    Returned private provenance must not be emitted as public status. UUID/path
    data prepares later journal binding; this function cannot enforce DB ownership.
    """
    try:
        path = _path(str(path))
        raw = path.read_bytes()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
        if (not isinstance(value, dict) or not {'version', 'installation_id', 'canonical_journal', 'projects'} <= set(value)
                or type(value['version']) is not int or value['version'] not in (1, 2)
                or set(value) - ({'version', 'installation_id', 'canonical_journal', 'projects'} |
                    ({'max_active'} if value['version'] == 1 else {'capacity'}))):
            raise ValueError('Invalid group policy schema')
        installation = value['installation_id']
        if not isinstance(installation, str) or str(uuid.UUID(installation)) != installation:
            raise ValueError('Invalid installation UUID')
        index = {c.repository.casefold(): c for c in connections}
        if len(index) != len(connections):
            raise ValueError('Duplicate project connections')
        journal = _path(value['canonical_journal'])
        _paths(path, journal, [c.checkout for c in connections], pipeline_config)
        tasks, limits = _task_rows(pipeline_config, executor_config, index)
        version = value['version']
        maximum = _integer(value.get('max_active', 2), 1, 2) if version == 1 else None
        if not isinstance(value['projects'], list):
            raise ValueError('Invalid group projects')
        projects = [_project(v, tasks, executor_config['profiles'], index, maximum, version) for v in value['projects']]
        if len({p['repository'] for p in projects}) != len(projects):
            raise ValueError('Duplicate group project')
        result = dict(version=version, installation_id=installation, canonical_journal=str(journal),
                      max_active=maximum, effective_max_active=_minimum(maximum, _counts(pipeline_config)['max_executors']), projects=projects)
        if version == 2:
            result.pop('max_active')
            result.pop('effective_max_active')
            result['capacity'] = _capacity(value.get('capacity', dict(mode='auto', max_executors=None,
                max_inflight=None, max_cpu_millis=None, max_memory_bytes=None, fallback=None)))
            result['harness_resources'] = _resources(executor_config, projects)
            result['effective_capacity'] = dict(result['capacity'])
            for key in ('max_executors', 'max_inflight'):
                result['effective_capacity'][key] = _minimum(result['capacity'][key],
                    _counts(executor_config)[key], _counts(pipeline_config)[key])
        authority = copy.deepcopy(result)
        if version == 1:
            del authority['max_active'], authority['effective_max_active']
        else:
            del authority['capacity'], authority['effective_capacity']
            for resource in authority['harness_resources'].values():
                del resource['max_parallel']
        for project in authority['projects']:
            for group in project['groups']:
                del group['capacity']
                group.pop('max_inflight', None)
        authority.update(config_path=str(path), tasks=list(tasks.values()),
            profiles={k: profile_fingerprint(v) for k, v in executor_config['profiles'].items()},
            limits={k: v for k, v in limits.items() if k != 'max_active'},
            connections=[dict(repository=c.repository.casefold(), checkout=str(c.checkout),
                              runner_label=c.runner_label, trusted_publishers=list(c.trusted_publishers)) for c in connections])
        capacity = dict(max_active=maximum, pipeline_max_active=limits.get('max_active'),
                        groups=[dict(repository=p['repository'], id=g['id'], capacity=g['capacity'])
                                for p in projects for g in p['groups']])
        if version == 2:
            capacity = dict(capacity=result['capacity'], effective_capacity=result['effective_capacity'],
                executor_capacity=_counts(executor_config), pipeline_capacity=_counts(pipeline_config),
                harness_caps={k: v['max_parallel'] for k, v in result['harness_resources'].items()},
                groups=[dict(repository=p['repository'], id=g['id'], capacity=g['capacity'],
                    max_inflight=g['max_inflight']) for p in projects for g in p['groups']])
        result.update(policy_sha256=hashlib.sha256(raw).hexdigest(),
            authorization_sha256=profile_fingerprint(authority), capacity_sha256=profile_fingerprint(capacity),
            _policy_path=path, _policy_bytes=raw, _tasks=tasks, _limits=limits,
            _connections=copy.deepcopy(connections), _executor_config=copy.deepcopy(executor_config),
            _pipeline_config=copy.deepcopy(pipeline_config))
        if path.read_bytes() != raw:
            raise ValueError('Group policy changed during read')
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise ValueError('Invalid group configuration') from None


def resolve_route(policy: dict, repository: str, issue: int, task_id: str) -> dict:
    """Return explicit routing data; labels/prose/path guesses never participate."""
    _name(repository, REPOSITORY)
    _integer(issue, 1, 2**63 - 1)
    _name(task_id, TASK_ID)
    rows = [(p, r) for p in policy['projects'] if p['repository'] == repository.casefold()
            for r in p['routes'] if r['issue'] == issue and r['task_id'] == task_id]
    if len(rows) != 1:
        return dict(status='needs_input', reason='routing_missing' if not rows else 'routing_ambiguous',
                    group_id=None, role_profiles=None, components=None, capacity=None)
    project, route = rows[0]
    group = next(g for g in project['groups'] if g['id'] == route['group'])
    task = policy['_tasks'][(repository.casefold(), issue)]
    return dict(status='ready', reason=None, group_id=group['id'], role_profiles=copy.deepcopy(group['role_profiles']),
                components=list(task['components']), capacity=(min(group['capacity'], policy['effective_max_active']) if policy['version'] == 1 else
                    dict(policy['effective_capacity'], max_executors=_minimum(group['capacity'],
                        policy['effective_capacity']['max_executors']), max_inflight=_minimum(group['max_inflight'],
                        policy['effective_capacity']['max_inflight']))))


def group_binding(policy: dict, task: dict) -> dict:
    """Freeze fresh private route/scope/limits/pins, never acceptance or a claim."""
    try:
        fresh = load_group_config(policy['_policy_path'], policy['_connections'],
                                  policy['_executor_config'], policy['_pipeline_config'])
        if (fresh['_policy_bytes'] != policy['_policy_bytes']
                or fresh['authorization_sha256'] != policy['authorization_sha256']
                or fresh['capacity_sha256'] != policy['capacity_sha256']):
            raise ValueError('Stale group policy')
        key = (task['repository'].casefold(), task['issue'])
        installed = fresh['_tasks'].get(key)
        supplied = copy.deepcopy(task)
        supplied['repository'] = supplied['repository'].casefold()
        supplied['components'] = _components(supplied['components'])
        if supplied != installed:
            raise ValueError('Task differs from private policy')
        route = resolve_route(fresh, *_identity(installed))
        if route['status'] != 'ready':
            return route
        profile = fresh['_executor_config']['profiles'][installed['executor_profile']]
        project = next(p for p in fresh['projects'] if p['repository'] == key[0])
        limits = fresh['_limits']
        budgets = dict(task_timeout_seconds=min(limits['task_timeout_seconds'], profile['timeout_seconds']),
            role_timeout_seconds=min(limits['role_timeout_seconds'], profile['timeout_seconds']),
            max_reworks=limits['max_reworks'], max_processes=limits['max_processes'],
            log_max_bytes=min(limits['log_max_bytes'], profile['log_max_bytes']))
        resources = fresh.get('harness_resources', {})
        resource_binding = {}
        if fresh['version'] == 2:
            pools = {}
            for resource in resources.values():
                pool = pools.setdefault(resource['pool_id'], dict(max_parallel=None))
                pool['max_parallel'] = _minimum(pool['max_parallel'], resource['max_parallel'])
            resource_binding = dict(harness_resources=copy.deepcopy(resources), harness_pools=pools)
        return dict(route, **resource_binding, version=fresh['version'], installation_id=fresh['installation_id'],
            canonical_journal=fresh['canonical_journal'], repository=key[0], issue=installed['issue'],
            task_id=installed['task_id'], runner_label=installed['runner_label'],
            executor_profile=installed['executor_profile'], profile_sha256=profile_fingerprint(profile),
            role_pins={r: profile['superpowers']['manifest_sha256'] for r in ROLES}, budgets=budgets,
            task_policy=copy.deepcopy(installed), base_update=copy.deepcopy(project['base_update']),
            accepted_main_source=next((copy.deepcopy(g) for g in project['accepted_main_sources']
                                      if g['executor_profile'] == installed['executor_profile']), None),
            authorization_sha256=fresh['authorization_sha256'], capacity_sha256=fresh['capacity_sha256'])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('Invalid or stale group binding') from None
