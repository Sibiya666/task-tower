import unittest
from types import SimpleNamespace

from task_tower.projects_board import sync_issue


class Store:
    def request(self, method, path, payload=None):
        return []

    def get(self, number):
        return {'number': number, 'node_id': 'I_123', 'body': '', 'state': 'open'}

    def metadata(self, issue):
        return {'version': 1, 'kind': 'task', 'status': 'awaiting_merge'}


class BoardTests(unittest.TestCase):
    def connection(self, **changes):
        values = dict(id='alpha', repository='owner/alpha', board={
            'project_id': 'PVT_123', 'status_field_id': 'PVTSSF_123',
            'status_options': {'awaiting_merge': 'option123'}})
        values.update(changes)
        return SimpleNamespace(**values)

    def test_add_and_status_are_separate_operations_with_scoped_ids(self):
        calls = []
        def graphql(query, variables):
            calls.append((query, variables))
            if 'addProjectV2ItemById' in query:
                return {'addProjectV2ItemById': {'item': {'id': 'PVTI_123'}}}
            return {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'PVTI_123'}}}
        result = sync_issue(self.connection(), Store(), 12, graphql=graphql)
        self.assertEqual(result['status'], 'synced')
        self.assertEqual(result['identity'], 'owner/alpha#12')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], {'project': 'PVT_123', 'content': 'I_123'})
        self.assertEqual(calls[1][1]['option'], 'option123')

    def test_unmapped_status_fails_before_mutation(self):
        connection = self.connection()
        connection.board['status_options'] = {}
        with self.assertRaises(ValueError):
            sync_issue(connection, Store(), 12, graphql=lambda *args: self.fail('mutation'))

    def test_scope_error_is_reported_without_exception_secret(self):
        def unavailable(*args):
            raise RuntimeError('secret-token')
        result = sync_issue(self.connection(), Store(), 12, graphql=unavailable)
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('secret-token', str(result))

    def test_missing_board_is_not_claimed_synced(self):
        result = sync_issue(self.connection(board=None), Store(), 12)
        self.assertEqual(result['status'], 'not_configured')

    def test_invalid_issue_node_and_number_are_rejected(self):
        for number in (True, 0, '../other'):
            with self.assertRaises(ValueError):
                sync_issue(self.connection(), Store(), number)
        store = Store()
        store.get = lambda number: {'number': number, 'node_id': 'evil"', 'body': ''}
        with self.assertRaises(ValueError):
            sync_issue(self.connection(), store, 12)

    def test_done_metadata_cannot_project_unverified_done(self):
        store = Store()
        store.metadata = lambda issue: {'version': 1, 'kind': 'task', 'status': 'done'}
        connection = self.connection()
        connection.board['status_options'] = {'needs_input': 'review-option'}
        calls = []
        def graphql(query, variables):
            calls.append(variables)
            return ({'addProjectV2ItemById': {'item': {'id': 'PVTI_123'}}}
                    if len(calls) == 1 else {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'PVTI_123'}}})
        sync_issue(connection, store, 12, graphql=graphql)
        self.assertEqual(calls[1]['option'], 'review-option')

    def test_verified_done_projects_done(self):
        store = Store()
        store.metadata = lambda issue: {'version': 1, 'kind': 'task', 'status': 'done'}
        connection = self.connection()
        connection.board['status_options'] = {'done': 'done-option'}
        calls = []
        def graphql(query, variables):
            calls.append(variables)
            return ({'addProjectV2ItemById': {'item': {'id': 'PVTI_123'}}}
                    if len(calls) == 1 else {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'PVTI_123'}}})
        result = sync_issue(connection, store, 12, graphql=graphql, verified_status=lambda issue: 'done')
        self.assertEqual(result['issue_status'], 'done')
        self.assertEqual(calls[1]['option'], 'done-option')

    def test_cli_connects_remote_attestation_to_projection(self):
        from unittest.mock import patch
        from task_tower.projects_board import main
        connection = self.connection()
        store = Store()
        store.metadata = lambda issue: {'version': 1, 'kind': 'task', 'status': 'done'}
        def sync(connection, store, number, **kwargs):
            self.assertEqual(kwargs['verified_status'](store.get(number)), 'done')
            return {'status': 'synced'}
        with patch('task_tower.projects_board.load_connections', return_value=[connection]), \
             patch('task_tower.projects_board.GitHubTasks', return_value=store), \
             patch('task_tower.projects_board.sync_issue', side_effect=sync), \
             patch('task_tower.project_worker.verified_done', return_value=True), \
             patch('task_tower.github_source.resolve_token', return_value=None):
            self.assertEqual(main(['--config', 'private.json', '--project', 'alpha', '--issue', '12']), 0)
