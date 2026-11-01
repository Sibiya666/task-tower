"""Independent acceptance checks using the production GitHub client boundary."""
import json
from types import SimpleNamespace
import unittest

from task_tower.github_tasks import GitHubTasks, START, END
from task_tower.github_publication import GitHubPublisher
import test_postmerge_worker


class RealClientAcceptance(test_postmerge_worker.WorkerTests):

    def test_real_client_publishes_preserves_body_and_retries_without_review(self):
        self.run_publication()

    def test_new_rejection_between_post_and_close_blocks_close(self):
        self.run_publication('reject')

    def test_changed_author_between_post_and_close_blocks_close(self):
        self.run_publication('author')

    def test_local_evidence_changed_after_post_blocks_close(self):
        self.run_publication('evidence')

    def run_publication(self, mutation=None):
        body = 'User prose must remain byte-for-byte.\n' + START + json.dumps(
            dict(version=1, kind='task', legacy_id='TT-WORKER-1')) + END
        issue = dict(number=9, id=1234, state='open', state_reason=None, body=body)
        comments = []
        requests = []
        def transport(method, url, headers, payload, limit):
            path = url.removeprefix('https://api.github.com/repos/owner/repo')
            requests.append((method, path, payload))
            if method == 'GET' and path == '/issues/9':
                value = issue
            elif method == 'GET' and path.startswith('/compare/'):
                value = dict(status='identical')
            elif method == 'GET' and path.startswith('/issues/9/comments?'):
                value = comments
            elif method == 'POST' and path == '/issues/9/comments':
                value = dict(id=1, body=payload['body'], user=dict(login='publisher'))
                comments.append(value)
                if mutation == 'reject':
                    comments.append(dict(id=2, body='<!-- task-tower:lifecycle:v1\n' + json.dumps(
                        dict(status='needs_input', remote_attempt=dict(status='needs_input'))) + '\n-->',
                        user=dict(login='publisher')))
                elif mutation == 'author':
                    comments[0] = dict(value, user=dict(login='attacker'))
                elif mutation == 'evidence':
                    (self.root / 'evidence.md').write_text('changed after publishing receipt')
            elif method == 'PATCH' and path == '/issues/9':
                self.assertEqual(payload, dict(state='closed', state_reason='completed'))
                issue.update(payload)
                value = issue
            else:
                self.fail('Unexpected API request: ' + method + ' ' + path)
            return json.dumps(value).encode()
        store = GitHubTasks(SimpleNamespace(repository='owner/repo'), transport=transport)
        worker = self.worker()
        worker.publisher = GitHubPublisher('owner/repo', dict(
            issue_tasks={'TT-WORKER-1': 9}, publisher_account='publisher'), store=store)
        rows = worker.once()
        if mutation:
            self.assertEqual(rows[0]['status'], 'done')
            self.assertEqual(rows[0]['publication']['status'], 'failed')
            self.assertEqual(issue['state'], 'open')
            self.assertFalse(any(method == 'PATCH' for method, _, _ in requests))
            worker.once()
            self.assertEqual(self.counter.read_text(), 'x')
            return
        self.assertEqual(rows[0]['publication']['status'], 'published')
        self.assertEqual(issue['state'], 'closed')
        self.assertEqual(issue['body'], body)
        worker.once()
        self.assertEqual(len(comments), 1)
        self.assertEqual(self.counter.read_text(), 'x')


class ClientRouteAcceptance(unittest.TestCase):
    def test_full_sha_main_comparison_is_supported(self):
        urls = []
        def transport(method, url, headers, payload, limit):
            urls.append(url)
            return b'{"status":"identical"}'
        store = GitHubTasks(SimpleNamespace(repository='owner/repo'), transport=transport)
        self.assertEqual(store.request('GET', '/compare/' + 'a' * 40 + '...main'),
                         {'status': 'identical'})
        self.assertEqual(len(urls), 1)
        with self.assertRaises(ValueError):
            store.request('GET', '/issues/../secrets')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([
        RealClientAcceptance('test_real_client_publishes_preserves_body_and_retries_without_review'),
        RealClientAcceptance('test_new_rejection_between_post_and_close_blocks_close'),
        RealClientAcceptance('test_changed_author_between_post_and_close_blocks_close'),
        RealClientAcceptance('test_local_evidence_changed_after_post_blocks_close'),
        loader.loadTestsFromTestCase(ClientRouteAcceptance),
    ])
