"""Graph gates use real read-only GitHub protocols with transport-only fixtures."""
import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit, parse_qs
import zipfile

from task_tower.capture import relationship_projection
from task_tower.dispatch_selection import collect_snapshot
from task_tower.github_source import GitHubSource
from task_tower.github_tasks import GitHubTasks
from task_tower.merge_events import build_merge_event
from task_tower.project_worker import LIFECYCLE

from task_tower import group_graph


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def packed(name, value):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 11, 1, 0, 0, 0)), json.dumps(value))
    return stream.getvalue()


def issue(number, **changes):
    metadata = dict(version=1, kind='task', mode='autonomous', status='open', task_id='TT-' + str(number))
    metadata.update(changes)
    return dict(id=1000 + number, number=number, state='open', title='Task ' + str(number),
                body='Task\n<!-- task-tower:v1\n' + json.dumps(metadata) + '\n-->')


class Transport:
    """Only HTTP is substituted; source/receipt/CI/metadata code stays real."""
    def __init__(self, repository, rows):
        self.repository = repository
        self.rows = {r['number']: copy.deepcopy(r) for r in rows}
        self.comments = {}
        self.native = {}
        self.calls = []
        self.unavailable = False
        self.receipts = {}
        self.events = {}
        self.runs = {}
        self.prs = {}
        self.verification_runs = {}

    def accept(self, number, *, local=False):
        row = self.rows[number]
        task_id = GitHubTasks.metadata(row)['task_id']
        commit = format(number, '040x')
        pr_number = 100 + number
        run_id = 200 + number
        self.prs[pr_number] = dict(number=pr_number, merged=True, merged_at='2026-11-01T12:00:00Z',
            head=dict(sha=commit), base=dict(ref='main', repo=dict(full_name=self.repository)),
            merge_commit_sha=commit, body='Task-Tower: ' + task_id)
        run = dict(id=run_id, run_attempt=1, created_at='2026-11-01T12:00:01Z', status='completed',
            event='pull_request', path='.github/workflows/postmerge.yml', head_sha=commit,
            repository=dict(full_name=self.repository), pull_requests=[dict(number=pr_number)])
        self.runs[run_id] = run
        self.events[run_id] = build_merge_event(dict(action='closed', repository=dict(full_name=self.repository),
            pull_request=self.prs[pr_number]), self.repository, 'linux', 'passed', run_id, 1)
        event = self.events[run_id]
        bundle = {k: event[k] for k in ('repository', 'pr_number', 'merge_commit', 'task_ids', 'run_url')}
        key = hashlib.sha256(json.dumps([self.repository, pr_number, commit, str(run_id), '1'], separators=(',', ':')).encode()).hexdigest()
        bundle.update(run_id=str(run_id), attempt='1', platforms=dict(linux='passed'), delivery_key=key)
        review = dict(verdict='approve', commit=commit, task_id=task_id, summary='Independent accepted result', findings=[])
        if local:
            evidence = {s: dict(evidence='docs/' + s + '.md', reviewer='review-' + s, sha256='c' * 64)
                        for s in ('spec', 'development', 'test', 'postmerge')}
            receipt = dict(version=1, kind='local-postmerge', repository=self.repository, issue=number,
                issue_id=row['id'], task_id=task_id, input_snapshot='a' * 64, commit=commit,
                bundle=bundle, review=review, required_platforms=['linux'], evidence=evidence,
                evidence_digest=hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
                policy=dict(executor='dev', reviewer='review-postmerge'))
            publication = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            attempt = dict(kind='local-postmerge', status='done', commit=commit, publication_id=publication, receipt=receipt)
        else:
            verification_id = 500 + number
            self.verification_runs[verification_id] = dict(status='completed', run_attempt=1,
                event='workflow_dispatch', head_branch='main', path='.github/workflows/task-tower-project.yml',
                repository=dict(full_name=self.repository), head_sha='d' * 40)
            receipt = dict(repository=self.repository, issue=number, run_id=str(verification_id), run_attempt='1',
                bundle=bundle, review=review, required_platforms=['linux'],
                policy=dict(reviewer='postmerge-agent', executor='dev', superpowers_sha256='c' * 64))
            self.receipts[verification_id] = (number, receipt)
            attempt = dict(status='done', run_id=str(verification_id), run_attempt='1')
        self.comments[number] = [dict(id=1, user=dict(login='publisher'),
            body=LIFECYCLE + json.dumps(dict(status='done', remote_attempt=attempt)) + '\n-->')]
        row['state'] = 'closed'

    def request(self, method, url, headers, payload=None, limit=None):
        if method != 'GET':
            raise AssertionError('Graph observer attempted a write')
        self.calls.append(url)
        if self.unavailable:
            raise OSError('private network detail')
        path = urlsplit(url).path.removeprefix('/repos/' + self.repository)
        query = parse_qs(urlsplit(url).query)
        if path == '/issues':
            result = list(self.rows.values()) if query.get('page', ['1']) == ['1'] else []
        elif path.startswith('/issues/'):
            number = int(path.split('/')[2])
            if path.endswith('/comments'):
                result = self.comments.get(number, [])
            elif path.endswith('/parent'):
                result = self.native.get(number, {}).get('parent')
            elif path.endswith('/sub_issues'):
                result = self.native.get(number, {}).get('sub_issues', [])
            else:
                result = self.rows[number]
        elif path.startswith('/compare/'):
            result = dict(status='identical')
        elif path.startswith('/pulls/'):
            result = self.prs[int(path.rsplit('/', 1)[1])]
        elif path == '/actions/workflows/postmerge.yml/runs':
            result = dict(workflow_runs=list(self.runs.values()))
        elif path.startswith('/actions/runs/') and '/attempts/' in path:
            result = self.verification_runs[int(path.split('/')[3])]
        elif path.startswith('/actions/runs/') and path.endswith('/artifacts'):
            run_id = int(path.split('/')[3])
            if run_id in self.receipts:
                number, receipt = self.receipts[run_id]
                data = packed(str(number) + '.json', receipt)
                artifact = dict(id=run_id, name='task-tower-review-' + str(number) + '-1', expired=False,
                    digest='sha256:' + hashlib.sha256(data).hexdigest(), workflow_run=dict(id=run_id, head_sha='d' * 40))
            else:
                event = self.events[run_id]
                data = packed('merge-event.json', event)
                artifact = dict(id=run_id, name='task-tower-merge-' + str(event['pr_number']) + '-linux', expired=False,
                    digest='sha256:' + hashlib.sha256(data).hexdigest(), workflow_run=dict(id=run_id, head_sha=self.runs[run_id]['head_sha']))
            result = dict(artifacts=[artifact])
        elif path.startswith('/actions/artifacts/') and path.endswith('/zip'):
            artifact_id = int(path.split('/')[3])
            if artifact_id in self.receipts:
                number, receipt = self.receipts[artifact_id]
                return packed(str(number) + '.json', receipt)
            return packed('merge-event.json', self.events[artifact_id])
        else:
            raise AssertionError('Unexpected transport read: ' + path)
        return json.dumps(result).encode()

    def source_request(self, url, headers, limit):
        return self.request('GET', url, headers, limit=limit)


class GroupGraphTests(unittest.TestCase):
    def setUp(self):
        self.connections = []
        self.transports = {}
        self.stores = {}
        self.sources = {}
        self.policy = dict(projects=[])
        self.relations = {}

    def project(self, repository, rows, authorized=()):
        connection = SimpleNamespace(repository=repository, checkout=Path.cwd(), runner_label='local',
                                     trusted_publishers=['publisher'])
        transport = Transport(repository, rows)
        self.connections.append(connection)
        self.transports[repository.casefold()] = transport
        self.stores[repository.casefold()] = GitHubTasks(connection, transport=transport.request)
        self.sources[repository.casefold()] = GitHubSource(repository, transport=transport.source_request)
        self.policy['projects'].append(dict(repository=repository.casefold(),
            routes=[dict(issue=n, task_id='TT-' + str(n), group='core') for n in authorized], aggregates=[]))
        return transport

    def snapshot(self):
        return collect_snapshot(self.connections,
            store_factory=lambda c: self.stores[c.repository.casefold()],
            source_factory=lambda c: self.sources[c.repository.casefold()])

    def graph(self, snapshot=None):
        return group_graph.build_graph(snapshot or self.snapshot(), self.policy, self.relations)

    def evaluate(self, snapshot=None):
        snapshot = snapshot or self.snapshot()
        return group_graph.evaluate_graph(self.graph(snapshot), group_graph.observe_results(self.connections, snapshot))

    def test_parent_contains_is_not_dependency(self):
        self.project('owner/repo', [issue(1), issue(2)], authorized=(1, 2))
        self.relations['owner/repo#1'] = dict(parent=None, sub_issues=[dict(id='owner/repo#2')], milestone=None)
        self.policy['projects'][0]['aggregates'] = [dict(issue=1, task_id='TT-1', required_children=['owner/repo#2'])]
        result = self.evaluate()
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_pending')
        self.assertEqual(result['nodes']['owner/repo#2']['status'], 'ready')
        graph = self.graph()
        self.assertIn(dict(source='owner/repo#1', target='owner/repo#2', kind='contains'), graph['edges'])
        self.assertNotIn(dict(source='owner/repo#2', target='owner/repo#1', kind='requires_result'), graph['edges'])

    def test_explicit_parent_child_wait_cycle(self):
        self.project('owner/repo', [issue(1), issue(2, blocked_by=['owner/repo#1']),
            issue(3, blocked_by=['owner/repo#1']), issue(4)], authorized=(1, 2, 3, 4))
        self.relations['owner/repo#1'] = dict(sub_issues=[dict(id='owner/repo#2')], parent=None)
        self.policy['projects'][0]['aggregates'] = [dict(issue=1, task_id='TT-1', required_children=['owner/repo#2'])]
        result = self.evaluate()
        for number in (1, 2):
            self.assertEqual(result['nodes']['owner/repo#' + str(number)]['reason'], 'dependency_cycle')
        self.assertEqual(result['nodes']['owner/repo#3']['reason'], 'dependency_blocked')
        self.assertEqual(result['nodes']['owner/repo#4']['status'], 'ready')
        self.assertEqual(result['cycles'][0]['members'], ['owner/repo#1', 'owner/repo#2'])

    def test_closed_without_receipt_is_pending(self):
        transport = self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2']), issue(2)], authorized=(1,))
        transport.rows[2]['state'] = 'closed'
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['reason'], 'dependency_pending')
        transport.accept(2)
        snapshot = self.snapshot()
        observed = group_graph.observe_results(self.connections, snapshot)
        proof = observed['results']['owner/repo#2']
        self.assertEqual(proof['status'], 'accepted')
        self.assertEqual(proof['issue_id'], 1002)
        self.assertEqual(proof['commit_sha'], format(2, '040x'))
        self.assertEqual(len(proof['receipt_sha256']), 64)
        self.assertEqual(group_graph.evaluate_graph(self.graph(snapshot), observed)['nodes']['owner/repo#1']['status'], 'ready')
        with self.assertRaises(ValueError): group_graph.evaluate_graph(self.graph(snapshot), {'owner/repo#2': True})

    def test_aggregate_requires_only_declared_native_children(self):
        transport = self.project('owner/repo', [issue(1), issue(2), issue(3)], authorized=(1, 2, 3))
        transport.accept(2)
        transport.native[1] = dict(parent=None, sub_issues=[dict(number=n, html_url='https://github.com/owner/repo/issues/' + str(n)) for n in (2, 3)])
        projection, errors = relationship_projection(self.connections[0], self.stores['owner/repo'], transport.rows[1])
        self.assertEqual(errors, [])
        self.relations['owner/repo#1'] = projection
        self.policy['projects'][0]['aggregates'] = [dict(issue=1, task_id='TT-1', required_children=['owner/repo#2'])]
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['status'], 'ready')
        self.relations['owner/repo#1']['sub_issues'] = [dict(id='owner/repo#3')]
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['reason'], 'dependency_unavailable')

    def test_partial_relationships_and_duplicate_task_id_block(self):
        self.project('owner/repo', [issue(1), issue(2), issue(3, task_id='TT-2'),
            issue(4, blocked_by_task_ids=['TT-2']), issue(5)], authorized=(1, 4, 5))
        self.policy['projects'][0]['aggregates'] = [dict(issue=1, task_id='TT-1', required_children=['owner/repo#2'])]
        self.relations['owner/repo#1'] = dict(parent=None, sub_issues=dict(status='unavailable'))
        result = self.evaluate()
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_unavailable')
        self.assertEqual(result['nodes']['owner/repo#4']['reason'], 'dependency_unavailable')
        self.assertEqual(result['nodes']['owner/repo#5']['status'], 'ready')

    def test_cross_project_readable_not_executable(self):
        self.project('owner/repo', [issue(1, blocked_by=['other/repo#2']), issue(3)], authorized=(1, 3))
        other = self.project('other/repo', [issue(2)], authorized=())
        other.accept(2)
        graph = self.graph()
        self.assertFalse(graph['nodes']['other/repo#2']['authorized'])
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['status'], 'ready')
        other.unavailable = True
        result = self.evaluate()
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_unavailable')
        self.assertEqual(result['nodes']['owner/repo#3']['status'], 'ready')

    def test_graph_limit_fails_closed(self):
        self.project('owner/repo', [issue(1)], authorized=(1,))
        snapshot = self.snapshot()
        project = snapshot['owner/repo']
        for number in range(2, 1002):
            row = issue(number)
            project['issues'][number] = row
            project['metadata'][number] = GitHubTasks.metadata(row)
            project['index']['TT-' + str(number)] = [number]
        result = group_graph.evaluate_graph(group_graph.build_graph(snapshot, self.policy, {}), {})
        self.assertEqual(result['reason'], 'graph_limit')
        self.assertFalse(any(n['status'] == 'ready' for n in result['nodes'].values()))

    def test_ten_thousand_edge_limit_has_no_ready_partial_graph(self):
        self.project('owner/repo', [issue(1)], authorized=(1,))
        snapshot = self.snapshot()
        project = snapshot['owner/repo']
        for number in range(1, 102):
            row = issue(number, blocked_by=['owner/repo#' + str(other) for other in range(1, 102) if other != number])
            project['issues'][number] = row
            project['metadata'][number] = GitHubTasks.metadata(row)
            project['index']['TT-' + str(number)] = [number]
        graph = group_graph.build_graph(snapshot, self.policy, {})
        self.assertEqual(graph['reason'], 'graph_limit')
        self.assertEqual(graph['nodes'], {})
        self.assertEqual(graph['edges'], [])

    def test_dependency_overflow_cannot_be_hidden_by_later_malformed_reference(self):
        self.project('owner/repo', [issue(1, blocked_by=[
            'other/repo#' + str(n) for n in range(1, 10002)] + ['malformed'])], authorized=(1,))
        self.assertEqual(self.graph()['reason'], 'graph_limit')

    def test_one_thousand_deep_chain_needs_no_recursive_python_stack(self):
        self.project('owner/repo', [issue(1)], authorized=(1,))
        snapshot = self.snapshot()
        project = snapshot['owner/repo']
        for number in range(1, 1001):
            row = issue(number, blocked_by=[] if number == 1000 else ['owner/repo#' + str(number + 1)])
            project['issues'][number] = row
            project['metadata'][number] = GitHubTasks.metadata(row)
            project['index']['TT-' + str(number)] = [number]
        result = group_graph.evaluate_graph(group_graph.build_graph(snapshot, self.policy, {}), {})
        self.assertEqual(result['cycles'], [])
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_pending')

    def test_source_issue_change_and_foreign_observation_cannot_reuse_proof(self):
        transport = self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2']), issue(2)], authorized=(1,))
        transport.accept(2)
        snapshot = self.snapshot()
        accepted = group_graph.observe_results(self.connections, snapshot)
        bad = copy.deepcopy(accepted)
        bad['results']['owner/repo#2']['issue_id'] = 9999
        with self.assertRaises(ValueError): group_graph.evaluate_graph(self.graph(snapshot), bad)
        transport.rows[2]['title'] = 'Changed task criteria'
        self.assertEqual(group_graph.observe_results(self.connections, snapshot)['results']['owner/repo#2']['status'], 'unavailable')
        with self.assertRaises(ValueError): group_graph.evaluate_graph(self.graph(), accepted)

    def test_one_refresh_caches_verified_source_catalog(self):
        transport = self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2', 'owner/repo#3']),
            issue(2), issue(3), issue(4)], authorized=(1, 4))
        transport.accept(2)
        transport.accept(3)
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['status'], 'ready')
        self.assertEqual(sum('/actions/workflows/postmerge.yml/runs?' in call for call in transport.calls), 1)

    def test_partial_catalog_unavailable_dependency_preserves_other_accepted_result(self):
        self.assert_partial_catalog(local=False)

    def test_partial_catalog_preserves_local_receipt_error_provenance(self):
        self.assert_partial_catalog(local=True)

    def assert_partial_catalog(self, *, local):
        transport = self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2']), issue(2),
            issue(3), issue(4, blocked_by=['owner/repo#3']), issue(5)], authorized=(1, 4, 5))
        transport.accept(2, local=local)
        transport.accept(3)
        original_transport = self.sources['owner/repo'].transport
        def partial_failure(url, headers, limit):
            if urlsplit(url).path.endswith('/actions/artifacts/202/zip'):
                raise OSError('private artifact failure')
            return original_transport(url, headers, limit)
        self.sources['owner/repo'].transport = partial_failure
        snapshot = self.snapshot()
        observed = group_graph.observe_results(self.connections, snapshot)
        self.assertEqual(observed['results']['owner/repo#2']['status'], 'unavailable')
        self.assertEqual(observed['results']['owner/repo#2']['source_errors'], [dict(
            run_id='202', attempt='1', head_sha=format(2, '040x'), reason='source_unavailable')])
        self.assertEqual(observed['results']['owner/repo#3']['status'], 'accepted')
        result = group_graph.evaluate_graph(self.graph(snapshot), observed)
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_unavailable')
        self.assertEqual(result['nodes']['owner/repo#4']['status'], 'ready')
        self.assertEqual(result['nodes']['owner/repo#5']['status'], 'ready')
        self.assertEqual(sum('/actions/workflows/postmerge.yml/runs?' in call for call in transport.calls), 1)
        self.assertNotIn('private artifact failure', json.dumps(observed))

    def test_mismatched_dual_dependencies_and_self_cycle_remain_visible(self):
        self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2'], blocked_by_task_ids=[]),
            issue(2, blocked_by=['owner/repo#2']), issue(3)], authorized=(1, 2, 3))
        result = self.evaluate()
        self.assertEqual(result['nodes']['owner/repo#1']['reason'], 'dependency_unavailable')
        self.assertEqual(result['nodes']['owner/repo#2']['reason'], 'dependency_cycle')
        self.assertEqual(result['nodes']['owner/repo#3']['status'], 'ready')

    def test_rejected_or_newer_conflicting_receipt_invalidates(self):
        transport = self.project('owner/repo', [issue(1, blocked_by=['owner/repo#2']), issue(2)], authorized=(1,))
        transport.accept(2, local=True)
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['status'], 'ready')
        transport.comments[2][0]['user']['login'] = 'untrusted'
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['reason'], 'dependency_pending')
        transport.comments[2][0]['user']['login'] = 'publisher'
        transport.events[202]['checks'] = 'failed'
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['reason'], 'dependency_pending')
        transport.events[202]['checks'] = 'passed'
        transport.comments[2].append(dict(id=2, user=dict(login='publisher'),
            body=LIFECYCLE + json.dumps(dict(status='needs_input', remote_attempt=dict(status='needs_input'))) + '\n-->'))
        self.assertEqual(self.evaluate()['nodes']['owner/repo#1']['reason'], 'dependency_pending')


if __name__ == '__main__':
    unittest.main()
