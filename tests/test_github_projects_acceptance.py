"""Independent acceptance cases for project books and source ownership."""
import contextlib
import io
import json
import hashlib
import zipfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower.books import aggregate, main
from task_tower.github_tasks import GitHubTasks
from task_tower.project_connections import ProjectConnection
from task_tower.projects_board import sync_issue
from types import SimpleNamespace
from task_tower.project_worker import verified_receipt, ProjectWorker, LIFECYCLE


class BooksAcceptanceTests(unittest.TestCase):
    def connection(self, repo='owner/one'):
        return ProjectConnection(repo.split('/')[1], repo, Path.cwd(), 'tower')

    def test_malformed_issue_row_is_visible_and_other_namespace_survives(self):
        def factory(connection):
            def transport(method, url, headers, payload, limit):
                rows = [None] if connection.id == 'one' else [dict(number=7, title='valid', body='')]
                return json.dumps(rows).encode()
            return GitHubTasks(connection, transport=transport)
        report = aggregate([self.connection(), self.connection('owner/two')], factory)
        self.assertEqual([e['id'] for e in report['entries']], ['owner/two#7'])
        self.assertEqual([e['project'] for e in report['errors']], ['one'])

    def test_cli_cannot_overwrite_connection_source(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'connections.json'
            original = json.dumps(dict(version=1, projects=[]))
            config.write_text(original, encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                result = main(['--connections', str(config), '--output', str(config)])
            self.assertEqual(config.read_text(encoding='utf-8'), original)
            self.assertEqual(result, 2)

    def test_cli_does_not_clobber_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'connections.json'
            output = Path(directory) / 'existing.md'
            config.write_text(json.dumps(dict(version=1, projects=[])), encoding='utf-8')
            output.write_text('User-authored evidence', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                result = main(['--connections', str(config), '--output', str(output)])
            self.assertEqual(output.read_text(encoding='utf-8'), 'User-authored evidence')
            self.assertEqual(result, 2)

    def test_import_same_legacy_id_in_two_projects_is_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            card = Path(directory) / 'legacy.json'
            card.write_text(json.dumps(dict(id='OLD-7', status='done', evidence='keep.md')), encoding='utf-8')
            original = card.read_bytes()
            remote = {}
            def factory(connection):
                rows = remote.setdefault(connection.repository, [])
                def transport(method, url, headers, payload, limit):
                    if method == 'POST':
                        rows.append(dict(payload, number=7))
                        return json.dumps(rows[-1]).encode()
                    return json.dumps(rows).encode()
                return GitHubTasks(connection, transport=transport)
            connections = [self.connection(), self.connection('owner/two')]
            for connection in connections:
                store = factory(connection)
                self.assertEqual(store.import_card(card)['number'], 7)
                self.assertEqual(store.import_card(card)['number'], 7)
            report = aggregate(connections, factory)
            self.assertEqual([e['id'] for e in report['entries']], ['owner/one#7', 'owner/two#7'])
            self.assertEqual([e['status'] for e in report['entries']], ['needs_input', 'needs_input'])
            self.assertEqual(card.read_bytes(), original)
            self.assertEqual([len(v) for v in remote.values()], [1, 1])

    def test_truncated_library_never_publishes_partial_files(self):
        def factory(connection):
            def transport(method, url, headers, payload, limit):
                if '/issues?' in url: value = []
                elif '/commits/' in url: value = dict(sha='a' * 40)
                elif '/git/trees/' in url:
                    value = dict(truncated=True, tree=[dict(type='blob', path='partial.md')])
                else: value = dict(default_branch='main')
                return json.dumps(value).encode()
            return GitHubTasks(connection, transport=transport)
        report = aggregate([self.connection()], factory, include_library=True)
        self.assertEqual(report['entries'], [])
        self.assertEqual(report['errors'][0]['error'], 'Library unavailable or incomplete')

    def test_two_boards_equal_issue_numbers_retry_scoped_membership_and_status(self):
        items, statuses = {}, {}
        class Store:
            def __init__(self, name): self.name = name
            def get(self, number): return dict(number=number, node_id='I_' + self.name)
            def metadata(self, issue): return dict(version=1, kind='task', status='open')
            def request(self, *args): return []
        def graphql(query, variables):
            project = variables['project']
            if 'addProjectV2ItemById' in query:
                key = (project, variables['content'])
                item = items.setdefault(key, 'PVTI_' + str(len(items)))
                return {'addProjectV2ItemById': {'item': {'id': item}}}
            statuses[(project, variables['item'])] = variables['option']
            return {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': variables['item']}}}
        for name in ('one', 'two'):
            connection = SimpleNamespace(repository='owner/' + name, board=dict(
                project_id='PVT_' + name, status_field_id='FIELD_' + name,
                status_options={'open': 'OPTION_' + name}))
            for retry in range(2):
                self.assertEqual(sync_issue(connection, Store(name), 7, graphql=graphql)['status'], 'synced')
        self.assertEqual(len(items), 2)
        self.assertEqual(set(statuses.values()), {'OPTION_one', 'OPTION_two'})

    def test_receipt_cannot_omit_independent_reviewer_and_required_checks(self):
        bundle = dict(merge_commit='a' * 40, task_ids=['TT-X'], platforms={})
        receipt = dict(repository='owner/one', issue=7, run_id='41', run_attempt='1',
                       required_platforms=[], bundle=bundle,
                       review=dict(verdict='approve', commit='a' * 40, task_id='TT-X'))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('7.json', json.dumps(receipt))
        raw = stream.getvalue()
        artifact = dict(id=1, name='task-tower-review-7-1', expired=False,
                        digest='sha256:' + hashlib.sha256(raw).hexdigest(),
                        workflow_run=dict(id=41, head_sha='b' * 40))
        run = dict(status='completed', run_attempt=1, event='workflow_dispatch',
                   head_branch='main', path='.github/workflows/task-tower-project.yml',
                   repository=dict(full_name='owner/one'), head_sha='b' * 40)
        store = SimpleNamespace(request=lambda method, path: run if '/actions/runs/' in path else dict(status='ahead'))
        source = SimpleNamespace(_pages=lambda *args: [artifact], _get=lambda *args, **kwargs: raw,
                                 _id=lambda value: value, poll=lambda: [bundle])
        self.assertIsNone(verified_receipt(self.connection(), store, source, 7, dict(run_id='41')))

    def test_fresh_runner_fetches_attested_remote_receipt_without_second_review(self):
        bundle = dict(merge_commit='a' * 40, task_ids=['TT-X'], platforms=dict(windows='passed', macos='passed', linux='passed'))
        receipt = dict(repository='owner/one', issue=7, run_id='41', run_attempt='1', snapshot='stable',
                       required_platforms=['windows', 'macos', 'linux'], bundle=bundle,
                       policy=dict(reviewer='postmerge-agent', executor='dev', superpowers_sha256='c' * 64),
                       review=dict(verdict='approve', commit='a' * 40, task_id='TT-X', summary='accepted', findings=[]))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive: archive.writestr('7.json', json.dumps(receipt))
        raw = stream.getvalue()
        artifact = dict(id=1, name='task-tower-review-7-1', expired=False,
                        digest='sha256:' + hashlib.sha256(raw).hexdigest(), workflow_run=dict(id=41, head_sha='b' * 40))
        issue = dict(number=7, body='User prose preserved', state='open')
        comments = [dict(id=1, body=LIFECYCLE + json.dumps(dict(remote_attempt=dict(status='running', run_id='41'))) + '\n-->')]
        calls = []
        def request(method, path, payload=None):
            calls.append((method, path))
            if '/comments?' in path: return comments.copy()
            if path.endswith('/comments'):
                comments.append(dict(id=len(comments) + 1, **payload))
                return comments[-1]
            if '/actions/runs/' in path:
                return dict(status='completed', run_attempt=1, event='workflow_dispatch', head_branch='main',
                            path='.github/workflows/task-tower-project.yml', repository=dict(full_name='owner/one'), head_sha='b' * 40)
            return dict(status='ahead')
        def update(number, **fields): issue.update(fields)
        store = SimpleNamespace(request=request, metadata=lambda value: dict(version=1, kind='task'),
                                get=lambda number: issue.copy(), update=update)
        source = SimpleNamespace(_pages=lambda *args: [artifact], _get=lambda *args, **kwargs: raw,
                                 _id=lambda value: value, poll=lambda: [bundle])
        with tempfile.TemporaryDirectory() as directory:
            worker = ProjectWorker(self.connection(), dict(issue_tasks={'7': 'docs/tasks/TT-X.json'}, state_dir=directory),
                                   store, source, None, run_id='42')
            worker._prepare = lambda number: (dict(id='TT-X', executor='dev'), bundle, 'stable')
            worker._review = lambda *args: self.fail('runner B repeated runner A review')
            self.assertEqual(worker.consume(7)['status'], 'done')
            self.assertTrue(any('/attempts/1' in path for method, path in calls))
            self.assertEqual(issue['state'], 'closed')
            self.assertEqual(issue['body'], 'User prose preserved')

    def test_old_local_approval_cannot_override_recovered_remote_rejection(self):
        from tests.test_project_worker import Store
        with tempfile.TemporaryDirectory() as directory:
            store = Store()
            connection = SimpleNamespace(repository='a/b', checkout=Path(directory))
            config = dict(issue_tasks={'1': 'docs/tasks/TT-X.json'}, state_dir=directory)
            worker = ProjectWorker(connection, config, store, None, None, run_id='42')
            worker._prepare = lambda number: (dict(id='TT-X', executor='dev'), dict(merge_commit='a' * 40), 'same')
            worker._review = lambda *args: dict(task_id='TT-X', commit='a' * 40, verdict='approve', summary='A approved', findings=[])
            worker.consume(1)
            # Another runner explicitly recovered and rejected the same candidate.
            store.meta['remote_attempt'] = dict(status='needs_input', run_id='43', run_attempt='1', commit='a' * 40)
            store.meta['status'] = 'needs_input'
            store.issue['state'] = 'open'
            worker.run_id = '44'
            worker._review = lambda *args: self.fail('stale retry invoked reviewer')
            with self.assertRaises(ValueError): worker.consume(1)
            self.assertEqual(store.issue['state'], 'open')
            self.assertEqual(store.meta['remote_attempt']['run_id'], '43')

    def test_reviewed_attempt_can_dispatch_publication_retry(self):
        from tests.test_project_worker import Store
        with tempfile.TemporaryDirectory() as directory:
            store = Store()
            store.meta['remote_attempt'] = dict(status='reviewed', run_id='41', run_attempt='1')
            worker = ProjectWorker(SimpleNamespace(repository='a/b', checkout=Path(directory)),
                dict(issue_tasks={'1': 'docs/tasks/TT-X.json'}, state_dir=directory), store, None, None, run_id='42')
            result = worker.dispatch(1)
            self.assertTrue(result['dispatched'])
            self.assertTrue(any('/dispatches' in path for method, path, payload in store.calls))
            self.assertEqual(store.meta['remote_attempt']['run_id'], '41')
