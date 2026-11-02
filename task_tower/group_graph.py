"""Bounded dependency reports and fresh host observations, never task claims.

evaluate_graph consumes only the current refresh's observe_results data. Its
report is not an authenticated execution input; later host/journal gates must
revalidate authority and results. No pipeline engine or acceptance writer lives
here. Native relationship projections come from capture.relationship_projection.
"""
import copy
import io
import json
import re
import zipfile

from .dispatch_selection import _identity, TASK_ID
from .executor_profiles import profile_fingerprint
from .github_source import MAX_PAGES
from .project_connections import REPOSITORY
from . import project_worker


MAX_NODES = 1000
MAX_EDGES = 10000
WAIT_KINDS = {'requires_result', 'aggregate_requires'}


class _GraphLimit(Exception):
    pass


def _ref(value):
    match = re.fullmatch('(' + REPOSITORY + r')#([1-9][0-9]*)', value) if isinstance(value, str) else None
    if not match:
        raise ValueError('Invalid qualified graph identity')
    return match[1].casefold() + '#' + match[2]


def _snapshot_digest(snapshot):
    rows = {}
    for repository, project in sorted(snapshot.items()):
        rows[repository] = dict(error=project['error'], issues=[dict(
            number=number, issue_id=row.get('id'), state=row.get('state'),
            content_sha256=profile_fingerprint(dict(title=row.get('title'), body=row.get('body'))),
            metadata=project['metadata'].get(number)) for number, row in sorted(project['issues'].items())],
            index=project['index'])
    return profile_fingerprint(rows)


def _dependencies(repository, metadata, project):
    canonical, legacy = set(), set()
    for field in ('blocked_by', 'blocked_by_task_ids'):
        values = metadata.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values):
            raise ValueError('Invalid dependency declarations')
        for value in values:
            if field == 'blocked_by':
                reference = _ref(value)
                if reference in canonical:
                    raise ValueError('Duplicate dependency')
                canonical.add(reference)
            else:
                if not re.fullmatch(TASK_ID, value):
                    raise ValueError('Invalid dependency task ID')
                matches = project['index'].get(value, [])
                if len(matches) != 1:
                    raise ValueError('Unresolved dependency task ID')
                legacy.add(repository + '#' + str(matches[0]))
            if len(canonical) > MAX_EDGES or len(legacy) > MAX_EDGES:
                raise _GraphLimit()
    if len(canonical | legacy) > MAX_EDGES:
        raise _GraphLimit()
    if 'blocked_by' in metadata and 'blocked_by_task_ids' in metadata and canonical != legacy:
        raise ValueError('Mismatched dependency declarations')
    return canonical | legacy


def build_graph(snapshot: dict, policy: dict, relationships: dict) -> dict:
    """Build typed edges; unavailable native data never invents wait edges."""
    digest = _snapshot_digest(snapshot)
    try:
        return _build_graph(snapshot, policy, relationships, digest)
    except _GraphLimit:
        return dict(version=1, snapshot_sha256=digest, reason='graph_limit', nodes={}, edges=[])


def _build_graph(snapshot, policy, relationships, digest):
    count = sum(len(p['issues']) for p in snapshot.values())
    result = dict(version=1, snapshot_sha256=digest, reason=None, nodes={}, edges=[])
    if count > MAX_NODES:
        return dict(result, reason='graph_limit')
    nodes, edges = result['nodes'], set()
    routes, aggregates = {}, {}
    for project in policy['projects']:
        repository = project['repository'].casefold()
        for route in project['routes']:
            key = _ref(repository + '#' + str(route['issue']))
            routes.setdefault(key, []).append(route['task_id'])
        for aggregate in project['aggregates']:
            key = _ref(repository + '#' + str(aggregate['issue']))
            if key in aggregates:
                raise ValueError('Duplicate aggregate policy')
            aggregates[key] = aggregate

    def node(reference):
        if reference in nodes:
            return nodes[reference]
        if len(nodes) >= MAX_NODES:
            raise _GraphLimit()
        repository, number = reference.rsplit('#', 1)
        number = int(number)
        project = snapshot.get(repository)
        row = project['issues'].get(number) if project else None
        metadata = project['metadata'].get(number) if project else None
        task_id = _identity(metadata)
        available = (project is not None and not project['error'] and row is not None
            and type(row.get('id')) is int and row['id'] > 0 and metadata is not None
            and metadata.get('kind') == 'task' and task_id is not None
            and project['index'].get(task_id) == [number])
        bindings = routes.get(reference, [])
        value = dict(identity=reference, repository=repository, issue=number,
            issue_id=row.get('id') if row else None, task_id=task_id,
            authorized=len(bindings) == 1 and bindings[0] == task_id,
            lifecycle_state=row.get('state') if row else None,
            reason=None if available else 'dependency_unavailable',
            relationship_status='available' if reference in relationships else 'unavailable')
        nodes[reference] = value
        return value

    def edge(source, target, kind):
        value = (source, target, kind)
        if value not in edges and len(edges) >= MAX_EDGES:
            raise _GraphLimit()
        edges.add(value)

    for repository, project in sorted(snapshot.items()):
        for number in sorted(project['issues']):
            node(_ref(repository + '#' + str(number)))
    for reference in sorted(routes):
        node(reference)
    for reference in list(sorted(nodes)):
        value = nodes[reference]
        project = snapshot.get(value['repository'])
        if not value['reason']:
            try:
                for dependency in _dependencies(value['repository'], project['metadata'][value['issue']], project):
                    node(dependency)
                    edge(reference, dependency, 'requires_result')
            except (ValueError, TypeError, KeyError):
                value['reason'] = 'dependency_unavailable'
        relations = relationships.get(reference)
        native_children = None
        if isinstance(relations, dict):
            try:
                children = relations.get('sub_issues')
                if not isinstance(children, list):
                    raise ValueError('Unavailable children')
                native_children = {_ref(child['id']) for child in children}
                if len(native_children) != len(children):
                    raise ValueError('Duplicate native child')
                for child in native_children:
                    node(child)
                    edge(reference, child, 'contains')
                parent = relations.get('parent')
                if parent is not None:
                    parent = _ref(parent['id'])
                    node(parent)
                    edge(parent, reference, 'contains')
            except (ValueError, TypeError, KeyError):
                value['relationship_status'] = 'unavailable'
        aggregate = aggregates.get(reference)
        if aggregate is not None:
            try:
                required = [_ref(c) for c in aggregate['required_children']]
                if (aggregate['task_id'] != value['task_id'] or not value['authorized'] or not required
                        or len(set(required)) != len(required) or native_children is None
                        or not set(required) <= native_children):
                    raise ValueError('Required native relationship unavailable')
                for child in required:
                    node(child)
                    edge(reference, child, 'aggregate_requires')
            except (ValueError, TypeError, KeyError):
                value['reason'] = 'dependency_unavailable'
        if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
            return dict(result, reason='graph_limit', nodes={}, edges=[])
    result['edges'] = [dict(source=s, target=t, kind=k) for s, t, k in sorted(edges)]
    return result


def _cycles(nodes, adjacency):
    """Iterative Kosaraju avoids Python recursion depth at the 1000-node bound."""
    seen, order = set(), []
    reverse = {key: [] for key in nodes}
    for source, targets in adjacency.items():
        for target in targets:
            reverse[target].append(source)
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [(start, False)]
        while stack:
            current, finish = stack.pop()
            if finish:
                order.append(current)
            elif current not in seen:
                seen.add(current)
                stack.append((current, True))
                stack.extend((n, False) for n in reversed(sorted(adjacency[current])) if n not in seen)
    seen, cycles = set(), []
    for start in reversed(order):
        if start in seen:
            continue
        members, stack = [], [start]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            members.append(current)
            stack.extend(reverse[current])
        members.sort()
        if len(members) > 1 or start in adjacency[start]:
            cycles.append(members)
    return sorted(cycles)


def evaluate_graph(graph: dict, accepted: dict) -> dict:
    """Report dependency gates, not execution permission or a durable verdict."""
    result = dict(version=1, snapshot_sha256=graph['snapshot_sha256'], reason=graph['reason'], nodes={}, cycles=[])
    if graph['reason'] == 'graph_limit':
        return result
    if accepted and (set(accepted) != {'version', 'snapshot_sha256', 'results'}
            or type(accepted['version']) is not int or accepted['version'] != 1
            or accepted['snapshot_sha256'] != graph['snapshot_sha256'] or not isinstance(accepted['results'], dict)):
        raise ValueError('Expected current host result observations')
    observations = accepted.get('results', {})
    nodes = graph['nodes']
    adjacency = {key: set() for key in nodes}
    for edge in graph['edges']:
        if edge['kind'] in WAIT_KINDS:
            adjacency[edge['source']].add(edge['target'])
    cycles = _cycles(nodes, adjacency)
    cycle_members = {member for cycle in cycles for member in cycle}
    for members in cycles:
        result['cycles'].append(dict(members=members, edges=[copy.deepcopy(e) for e in graph['edges']
            if e['kind'] in WAIT_KINDS and e['source'] in members and e['target'] in members]))
    unavailable = {key for key, value in nodes.items() if value['reason'] == 'dependency_unavailable'}
    for key, observation in observations.items():
        if key not in nodes:
            continue
        if (not isinstance(observation, dict) or observation.get('identity') != key
                or observation.get('issue_id') != nodes[key]['issue_id']
                or observation.get('task_id') != nodes[key]['task_id']
                or observation.get('source_snapshot_sha256') != graph['snapshot_sha256']
                or observation.get('status') not in ('accepted', 'pending', 'unavailable')):
            raise ValueError('Invalid graph observation identity')
        if observation['status'] == 'unavailable':
            unavailable.add(key)
        if observation['status'] == 'accepted':
            if (not isinstance(observation.get('commit_sha'), str) or not re.fullmatch('[a-f0-9]{40}', observation['commit_sha'])
                    or not isinstance(observation.get('receipt_sha256'), str) or not re.fullmatch('[a-f0-9]{64}', observation['receipt_sha256'])
                    or not isinstance(observation.get('receipt_identity'), dict) or not observation['receipt_identity']):
                raise ValueError('Accepted result lacks host provenance')
    for key, value in sorted(nodes.items()):
        reachable, stack = set(), list(adjacency[key])
        while stack:
            dependency = stack.pop()
            if dependency in reachable:
                continue
            reachable.add(dependency)
            stack.extend(adjacency[dependency])
        blockers = []
        if key in cycle_members:
            reason = 'dependency_cycle'
            blockers = next(c for c in cycles if key in c)
        elif key in unavailable or reachable & unavailable:
            reason = 'dependency_unavailable'
            blockers = sorted(({key} if key in unavailable else set()) | reachable & unavailable)
        elif reachable & cycle_members:
            reason = 'dependency_blocked'
            blockers = sorted(reachable & cycle_members)
        else:
            blockers = sorted(d for d in adjacency[key] if observations.get(d, {}).get('status') != 'accepted')
            reason = 'dependency_pending' if blockers else None
        if reason:
            status = 'blocked'
        elif not value['authorized']:
            status, reason = 'not_authorized', 'routing_missing'
        elif value['lifecycle_state'] != 'open':
            status, reason = 'not_ready', 'not_open'
        else:
            status = 'ready'
        result['nodes'][key] = dict(status=status, reason=reason, blockers=blockers, authorized=value['authorized'])
    return result


class _StoreReads:
    """Freeze bounded reads within one verification; forbid accidental writes."""
    def __init__(self, store):
        self.store, self.cache, self.failed = store, {}, False

    def metadata(self, issue):
        key = ('metadata', profile_fingerprint(issue))
        if key not in self.cache:
            self.cache[key] = copy.deepcopy(self.store.metadata(issue))
        return copy.deepcopy(self.cache[key])

    def request(self, method, path):
        if method != 'GET':
            raise ValueError('Graph observations are read-only')
        key = (method, path)
        try:
            if key not in self.cache:
                self.cache[key] = copy.deepcopy(self.store.request(method, path))
            return copy.deepcopy(self.cache[key])
        except Exception:
            self.failed = True
            raise


class _SourceReads:
    def __init__(self, source):
        self.source, self.downloads, self.cache, self.failed = source, {}, {}, False
        self.poll_errors = []

    def _freeze_poll_errors(self):
        errors = getattr(self.source, 'errors', [])
        if not isinstance(errors, list) or len(errors) > MAX_PAGES * 100:
            raise ValueError('Unbounded source errors')
        frozen = []
        for error in errors:
            if not isinstance(error, dict):
                raise ValueError('Invalid source error')
            item = {key: error.get(key) for key in ('run_id', 'attempt', 'head_sha')}
            for key, pattern in (('run_id', '[1-9][0-9]*'), ('attempt', '[1-9][0-9]*'), ('head_sha', '[a-f0-9]{40}')):
                if item[key] is not None and (not isinstance(item[key], str) or not re.fullmatch(pattern, item[key])):
                    raise ValueError('Invalid source error identity')
            frozen.append(dict(item, reason='source_unavailable'))
        self.poll_errors = frozen

    def _call(self, name, *args, **kwargs):
        key = (name, args, tuple(sorted(kwargs.items())))
        try:
            if key not in self.cache:
                value = getattr(self.source, name)(*args, **kwargs)
                if name == 'poll':
                    self._freeze_poll_errors()
                self.cache[key] = copy.deepcopy(list(value) if name == '_pages' else value)
            return copy.deepcopy(self.cache[key])
        except Exception:
            self.failed = True
            raise

    def _pages(self, *args):
        return self._call('_pages', *args)

    def _get(self, path, **kwargs):
        value = self._call('_get', path, **kwargs)
        if kwargs.get('raw'):
            self.downloads[path] = value
        return value

    def _id(self, value):
        return self._call('_id', value)

    def poll(self):
        return self._call('poll')

    def relevant_errors(self, number, lifecycle):
        """Diagnostic candidates only: they can block, never prove acceptance."""
        attempt = lifecycle.get('remote_attempt', {})
        if not self.poll_errors or attempt.get('status') != 'done':
            return []
        if attempt.get('kind') == 'local-postmerge':
            receipts = [attempt.get('receipt', {})]
        else:
            receipts = []
            for data in self.downloads.values():
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        entries = archive.infolist()
                        if len(entries) == 1 and entries[0].filename == str(number) + '.json' and entries[0].file_size <= 2 * 1024 * 1024:
                            receipts.append(json.loads(archive.read(entries[0])))
                except (ValueError, OSError, RuntimeError, zipfile.BadZipFile):
                    continue
        matches = []
        for error in self.poll_errors:
            for receipt in receipts:
                bundle = receipt.get('bundle', {}) if isinstance(receipt, dict) else {}
                if not isinstance(bundle, dict):
                    continue
                run_matches = (error['run_id'] is not None and error['attempt'] is not None
                    and error['run_id'] == bundle.get('run_id') and error['attempt'] == bundle.get('attempt'))
                head_matches = error['head_sha'] is not None and error['head_sha'] == bundle.get('merge_commit')
                if run_matches or head_matches:
                    matches.append(copy.deepcopy(error))
                    break
        return matches


def observe_results(connections: list, snapshot: dict) -> dict:
    """Fresh real verified_done plus exact read provenance; no writer/callback."""
    digest = _snapshot_digest(snapshot)
    result = dict(version=1, snapshot_sha256=digest, results={})
    if sum(len(p['issues']) for p in snapshot.values()) > MAX_NODES:
        return result
    connected = {c.repository.casefold(): c for c in connections}
    if len(connected) != len(connections):
        raise ValueError('Duplicate connected graph project')
    for repository, project in sorted(snapshot.items()):
        store, source = _StoreReads(project['store']), _SourceReads(project['source'])
        for number, original in sorted(project['issues'].items()):
            identity = repository + '#' + str(number)
            task_id = _identity(project['metadata'].get(number))
            row = dict(identity=identity, issue_id=original.get('id'), task_id=task_id,
                source_snapshot_sha256=digest, status='pending', commit_sha=None,
                receipt_sha256=None, receipt_identity=None, source_errors=[])
            result['results'][identity] = row
            try:
                if project['error'] or repository not in connected:
                    raise ValueError('Unavailable project')
                connection = connected[repository]
                if connection != project['connection']:
                    raise ValueError('Snapshot connection changed')
                fresh = project['store'].get(number)
                metadata = project['store'].metadata(fresh)
                if (fresh != original or _identity(metadata) != task_id or task_id is None
                        or metadata.get('kind') != 'task' or type(fresh.get('id')) is not int or fresh['id'] <= 0
                        or project['index'].get(task_id) != [number]):
                    raise ValueError('Issue identity or source changed')
                store.failed = source.failed = False
                proven = project_worker.verified_done(connection, store, source, fresh)
                if not proven:
                    if store.failed or source.failed:
                        row['status'] = 'unavailable'
                    elif source.poll_errors:
                        lifecycle = project_worker.issue_lifecycle(store, fresh)
                        row['source_errors'] = source.relevant_errors(number, lifecycle)
                        row['status'] = 'unavailable' if row['source_errors'] else 'pending'
                    continue
                if fresh['state'] != 'closed':
                    continue  # publication has not completed the task lifecycle yet
                lifecycle = project_worker.issue_lifecycle(store, fresh)
                attempt = lifecycle['remote_attempt']
                if attempt.get('kind') == 'local-postmerge':
                    receipt = attempt['receipt']
                    receipt_identity = dict(kind='local-postmerge', publication_id=attempt['publication_id'])
                else:
                    candidates = []
                    for data in source.downloads.values():
                        with zipfile.ZipFile(io.BytesIO(data)) as archive:
                            if archive.namelist() == [str(number) + '.json']:
                                candidates.append(json.loads(archive.read(str(number) + '.json')))
                    if len(candidates) != 1:
                        raise ValueError('Missing verified receipt bytes')
                    receipt = candidates[0]
                    receipt_identity = dict(kind='actions', run_id=str(attempt['run_id']), run_attempt=str(attempt.get('run_attempt', '1')))
                if receipt['review']['task_id'] != task_id or receipt['issue'] != number:
                    raise ValueError('Receipt task identity mismatch')
                row.update(status='accepted', commit_sha=receipt['bundle']['merge_commit'],
                           receipt_sha256=profile_fingerprint(receipt), receipt_identity=receipt_identity)
            except Exception:
                row['status'] = 'unavailable'
    return result
