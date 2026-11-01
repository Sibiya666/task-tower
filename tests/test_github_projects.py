import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
import io
from unittest.mock import patch

from task_tower.project_connections import load_connections, ProjectConnection
from task_tower.github_tasks import GitHubTasks, replace_metadata, parse_metadata, task_status
from task_tower.books import aggregate, render_html, main as books_main
from task_tower.project_connections import main as connections_main


class ProjectsTests(unittest.TestCase):
    def test_books_explicit_refresh_protects_hardlinked_input_and_project_sources(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config, output = root / 'config.json', root / 'report.html'
            config.write_text(json.dumps(dict(version=1, projects=[])), encoding='utf-8')
            output.write_text('old', encoding='utf-8')
            self.assertEqual(books_main(['--connections', str(config), '--output', str(output), '--overwrite']), 0)
            self.assertIn('fetched_at', output.read_text(encoding='utf-8'))
            alias = root / 'alias.json'
            os.link(config, alias)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(books_main(['--connections', str(config), '--output', str(alias), '--overwrite']), 2)
            self.assertEqual(json.loads(config.read_text())['version'], 1)
            config.write_text(json.dumps(dict(version=1, projects=[dict(id='p', repository='owner/p', checkout=str(root), runner_label='tower')])), encoding='utf-8')
            with redirect_stderr(io.StringIO()):
                self.assertEqual(books_main(['--connections', str(config), '--output', str(root / 'source.md')]), 2)
            self.assertFalse((root / 'source.md').exists())

    def test_books_reads_lifecycle_comments_without_changing_body(self):
        from task_tower.project_worker import LIFECYCLE
        body = replace_metadata('Keep prose', dict(version=1, kind='task', status='open'))
        def transport(method, url, headers, payload, limit):
            if '/comments?' in url:
                return json.dumps([dict(id=10, body=LIFECYCLE + json.dumps(dict(status='in_progress')) + '\n-->')]).encode()
            return json.dumps([dict(number=1, body=body, title='Task')]).encode()
        report = aggregate([self.connection()], lambda c: GitHubTasks(c, transport=transport))
        self.assertEqual(report['entries'][0]['status'], 'in_progress')
        self.assertEqual(report['errors'], [])
    def test_connections_cli_add_remove_and_no_overwrite_init(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config = root / 'connections.json'
            args = ['--config', str(config)]
            self.assertEqual(connections_main(args + ['init']), 0)
            self.assertEqual(connections_main(args + ['add', '--id', 'one', '--repository', 'owner/one', '--checkout', str(root), '--runner-label', 'tower']), 0)
            self.assertEqual(len(load_connections(config)), 1)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(connections_main(args + ['init']), 2)
            self.assertEqual(len(load_connections(config)), 1)
            self.assertEqual(connections_main(args + ['remove', 'one']), 0)
            self.assertEqual(load_connections(config), [])
    def connection(self, repo='owner/one'):
        return ProjectConnection(repo.split('/')[1], repo, Path('.').resolve(), 'tower')

    def test_connections_reject_duplicates_urls_and_relative_checkouts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'connections.json'
            row = dict(id='one', repository='owner/one', checkout=str(Path(directory).resolve()), runner_label='tower')
            path.write_text(json.dumps(dict(version=1, projects=[row])), encoding='utf-8')
            self.assertEqual(load_connections(path)[0].repository, 'owner/one')
            for bad in [dict(row, checkout='../escape'), dict(row, project_url='https://evil.test/users/o/projects/1')]:
                path.write_text(json.dumps(dict(version=1, projects=[bad])), encoding='utf-8')
                with self.assertRaises(ValueError): load_connections(path)
            path.write_text(json.dumps(dict(version=1, projects=[row, dict(row, id='two')])), encoding='utf-8')
            with self.assertRaises(ValueError): load_connections(path)

    def test_metadata_preserves_prose_and_cannot_forge_done(self):
        body = 'User prose <script>\n'
        value = dict(version=1, kind='task', status='done', executor='a', stages={})
        updated = replace_metadata(body, value)
        self.assertTrue(updated.startswith(body))
        self.assertEqual(parse_metadata(updated), value)
        self.assertEqual(task_status(value), 'needs_input')
        self.assertEqual(replace_metadata(updated, value), updated)
        with self.assertRaises(ValueError): parse_metadata(updated + updated)

    def test_paginated_namespaces_pr_exclusion_and_failure_isolation(self):
        def transport(method, url, headers, payload, limit):
            if '/two/' in url: raise OSError('secret token')
            if '&page=1' in url:
                rows = [dict(number=n, title='task', body='', state='closed') for n in range(1, 101)]
            else: rows = [dict(number=101, title='PR', pull_request={}, body='')]
            return json.dumps(rows).encode()
        report = aggregate([self.connection(), self.connection('owner/two')], lambda c: GitHubTasks(c, transport=transport))
        self.assertEqual(len(report['entries']), 100)
        self.assertEqual(report['entries'][0]['id'], 'owner/one#1')
        self.assertNotEqual(report['entries'][0]['status'], 'done')
        self.assertTrue(report['errors'])
        self.assertNotIn('secret token', json.dumps(report))

    def test_html_escapes_three_per_page_and_filters(self):
        entries = [dict(id=str(n), project='p', book='tasks', title='<script>alert(1)</script>', source='javascript:alert(1)', status='open') for n in range(4)]
        html = render_html(dict(entries=entries, errors=[dict(project='p', error='<bad>')]))
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('&lt;bad&gt;', html)
        self.assertIn('slice(page*3,page*3+3)', html)
        self.assertIn('id="project"', html)

    def test_invalid_stages_do_not_become_work(self):
        for stages in ([], {'postmerge': 'accepted'}, {'test': {'status': 'accepted', 'reviewer': 'same'}}):
            with self.assertRaises(ValueError):
                parse_metadata(replace_metadata('', dict(version=1, kind='task', executor='same', stages=stages)))

    def test_import_is_idempotent_and_preserves_unverified_evidence(self):
        from tests.test_project_onboarding import API
        from task_tower.project_onboarding import ensure_project_connection
        api=API('owner/one')
        issues = []
        def transport(method, url, headers, payload, limit):
            if url.endswith('/graphql'): return api.transport(method,url,headers,payload,limit)
            if '/comments?' in url: return b'[]'
            if method == 'POST':
                issues.append(dict(payload, number=1))
                return json.dumps(issues[-1]).encode()
            return json.dumps(issues).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            card = root / 'card.json'
            card.write_text(json.dumps(dict(version=1, id='OLD-1', status='done', stages={}, description='Preserved prose', evidence='old.md')), encoding='utf-8')
            connection=ensure_project_connection(root/'connections.json','one','owner/one',root,'tower',transport=api.transport)
            store = GitHubTasks(connection, transport=transport)
            self.assertEqual(store.import_card(card)['number'], 1)
            self.assertEqual(store.import_card(card)['number'], 1)
            self.assertEqual(len(issues), 1)
            metadata = parse_metadata(issues[0]['body'])
            self.assertEqual(metadata['status'], 'needs_input')
            self.assertEqual(metadata['legacy_card']['evidence'], 'old.md')
            self.assertIn('Preserved prose', issues[0]['body'])

    def test_library_pins_commit_and_rejects_truncated_tree(self):
        sha = 'a' * 40
        truncated = [False]
        def transport(method, url, headers, payload, limit):
            if url.endswith('/owner/one'): data = dict(default_branch='main')
            elif '/commits/' in url: data = dict(sha=sha)
            else: data = dict(truncated=truncated[0], tree=[dict(type='blob', path='docs/<x>.md')])
            return json.dumps(data).encode()
        store = GitHubTasks(self.connection(), transport=transport)
        self.assertEqual(store.library()[0]['source'], 'https://github.com/owner/one/blob/' + sha + '/docs/%3Cx%3E.md')
        truncated[0] = True
        with self.assertRaises(Exception): store.library()

    def test_equal_numbers_keep_repository_identity_and_pagination_is_bounded(self):
        def transport(method, url, headers, payload, limit):
            return json.dumps([dict(number=1, title='same', body='')]).encode()
        report = aggregate([self.connection(), self.connection('other/two')], lambda c: GitHubTasks(c, transport=transport))
        self.assertEqual([e['id'] for e in report['entries']], ['owner/one#1', 'other/two#1'])
        calls = []
        def endless(method, url, headers, payload, limit):
            calls.append(url)
            return json.dumps([dict(number=n + 1) for n in range(100)]).encode()
        with self.assertRaises(Exception): GitHubTasks(self.connection(), transport=endless).list_issues()
        self.assertEqual(len(calls), 20)

    def test_done_requires_fresh_remote_verification(self):
        metadata = dict(version=1, kind='task', status='done')
        def transport(method, url, headers, payload, limit):
            if '/comments?' in url: return b'[]'
            return json.dumps([dict(number=1, title='done', body=replace_metadata('', metadata))]).encode()
        store = lambda c: GitHubTasks(c, transport=transport)
        with patch('task_tower.project_worker.verified_done', return_value=True):
            self.assertEqual(aggregate([self.connection()], store)['entries'][0]['status'], 'done')
        with patch('task_tower.project_worker.verified_done', side_effect=OSError('credential')):
            report = aggregate([self.connection()], store)
            self.assertEqual(report['entries'][0]['status'], 'needs_input')
            self.assertTrue(report['errors'])


if __name__ == '__main__': unittest.main()
