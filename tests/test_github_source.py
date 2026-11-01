import io
import json
import unittest
import zipfile
from task_tower import github_source
from task_tower.merge_events import build_merge_event

REPO = 'owner/repo'
SHA = 'a' * 40

class GitHubSourceTests(unittest.TestCase):
    def fixture(self):
        pr = {'head': {'sha': SHA}, 'merged_at': '2026-11-01T12:00:00Z', 'number': 7, 'merged': True, 'base': {'ref': 'main', 'repo': {'full_name': REPO}}, 'merge_commit_sha': SHA, 'body': 'Task-Tower: TT-ONE'}
        run = {'created_at': '2026-11-01T12:00:01Z', 'status': 'completed', 'id': 12, 'run_attempt': 2, 'event': 'pull_request', 'path': '.github/workflows/postmerge.yml', 'head_sha': SHA, 'repository': {'full_name': REPO}, 'pull_requests': [{'number': 7}]}
        event = build_merge_event({'action': 'closed', 'repository': {'full_name': REPO}, 'pull_request': pr}, REPO, 'linux', 'passed', 12, 2)
        return pr, run, event

    def source(self, change=None):
        pr, run, event = self.fixture()
        if change: change(pr, run, event)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive: archive.writestr('merge-event.json', json.dumps(event))
        self.paths = []
        def transport(url, headers, limit):
            self.paths.append(url)
            if '/zip' in url: return stream.getvalue()
            if '/pulls/' in url: result = pr
            elif '/artifacts?' in url: result = {'artifacts': [{'id': 22, 'name': 'task-tower-merge-7-linux', 'expired': False, 'workflow_run': {'id': 12, 'head_sha': SHA}}]}
            else: result = {'workflow_runs': [run]}
            return json.dumps(result).encode()
        return github_source.GitHubSource(REPO, transport=transport)

    def test_verified_zip_groups_incomplete_platforms(self):
        result = self.source().poll()
        self.assertEqual(result[0]['platforms'], {'linux': 'passed'})
        self.assertEqual(result[0]['task_ids'], ['TT-ONE'])
        self.assertEqual(result[0]['attempt'], '2')

    def test_forged_marker_rejected(self):
        with self.assertRaises(github_source.GitHubSourceError):
            self.source(lambda p, r, e: e.update(task_ids=['TT-FORGED'])).poll()

    def test_replayed_attempt_rejected(self):
        with self.assertRaises(github_source.GitHubSourceError):
            self.source(lambda p, r, e: r.update(run_attempt=3)).poll()

    def test_wrong_repository_rejected(self):
        with self.assertRaises(github_source.GitHubSourceError):
            self.source(lambda p, r, e: p['base']['repo'].update(full_name='other/repo')).poll()

    def test_failed_forwarded(self):
        result = self.source(lambda p, r, e: e.update(checks='failed')).poll()
        self.assertEqual(result[0]['platforms'], {'linux': 'failed'})



class BoundaryTests(unittest.TestCase):
    def test_pagination_reads_second_page(self):
        source = github_source.GitHubSource(REPO, transport=lambda url, headers, limit: json.dumps({'items': list(range(100)) if 'page=1&' in url else []}).encode())
        calls = []
        def transport(url, headers, limit):
            calls.append(url)
            return json.dumps({'items': list(range(100)) if url.endswith('page=1') else [101]}).encode()
        source.transport = transport
        self.assertEqual(len(list(source._pages('/example', 'items'))), 101)
        self.assertEqual(len(calls), 2)

    def test_pagination_cap_explicit(self):
        source = github_source.GitHubSource(REPO, transport=lambda *args: json.dumps({'items': [0] * 100}).encode())
        with self.assertRaisesRegex(github_source.GitHubSourceError, 'pagination'):
            list(source._pages('/example', 'items'))

    def test_expired_artifact_is_error(self):
        source = GitHubSourceTests().source()
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            if '/artifacts?' in url:
                payload = json.loads(data)
                payload['artifacts'][0]['expired'] = True
                return json.dumps(payload).encode()
            return data
        source.transport = transport
        with self.assertRaisesRegex(github_source.GitHubSourceError, 'expired'): source.poll()

    def test_oversized_zip_and_digest_rejected(self):
        source = github_source.GitHubSource(REPO, transport=lambda *args: b'x' * (github_source.MAX_BYTES + 1))
        with self.assertRaises(github_source.GitHubSourceError): source._event({'id': 1})
        source.transport = lambda *args: b'zip'
        with self.assertRaisesRegex(github_source.GitHubSourceError, 'digest'): source._event({'id': 1, 'digest': 'sha256:fake'})

    def test_zip_path_and_inflate_bounds(self):
        for name, body in [('../merge-event.json', b'{}'), ('merge-event.json', b'x' * (github_source.MAX_BYTES + 1))]:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive: archive.writestr(name, body)
            source = github_source.GitHubSource(REPO, transport=lambda *args: stream.getvalue())
            with self.assertRaises(github_source.GitHubSourceError): source._event({'id': 1})

    def test_storage_redirect_strips_authorization(self):
        import urllib.request
        request = urllib.request.Request('https://api.github.com/repos/owner/repo/actions/artifacts/1/zip', headers={'Authorization': 'Bearer SECRET'})
        redirected = github_source._Redirect().redirect_request(request, None, 302, 'found', {}, 'https://storage.example/signed')
        self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(github_source.GitHubSourceError):
            github_source._Redirect().redirect_request(request, None, 302, 'found', {}, 'http://storage.example/signed')

    def test_noauth_transport_and_sanitized_error(self):
        def transport(url, headers, limit):
            self.assertNotIn('Authorization', headers)
            raise RuntimeError('SECRET response')
        with self.assertRaises(github_source.GitHubSourceError) as error:
            github_source.GitHubSource(REPO, transport=transport).poll()
        self.assertNotIn('SECRET', str(error.exception))

    def test_incomplete_or_other_workflow_rejected(self):
        source = GitHubSourceTests().source(lambda p, r, e: r.update(status='in_progress'))
        with self.assertRaises(github_source.GitHubSourceError): source.poll()


class ClosedRunTests(unittest.TestCase):
    def test_closed_run_head_sha_and_empty_pull_requests(self):
        def closed(pr, run, event):
            pr['head'] = {'sha': 'b' * 40}
            pr['merged_at'] = '2026-11-01T12:00:00Z'
            run.update(head_sha='b' * 40, pull_requests=[], created_at='2026-11-01T12:00:01Z')
        source = GitHubSourceTests().source(closed)
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            if '/artifacts?' in url:
                payload = json.loads(data)
                payload['artifacts'][0]['workflow_run']['head_sha'] = 'b' * 40
                return json.dumps(payload).encode()
            return data
        source.transport = transport
        self.assertEqual(source.poll()[0]['merge_commit'], SHA)

    def test_run_before_merge_rejected(self):
        def old(pr, run, event):
            pr['merged_at'] = '2026-11-01T12:00:00Z'
            run['created_at'] = '2026-11-01T11:59:59Z'
        with self.assertRaises(github_source.GitHubSourceError): GitHubSourceTests().source(old).poll()


class MalformedTests(unittest.TestCase):
    def test_malformed_api_shapes_are_sanitized(self):
        for response in [[], None, {'workflow_runs': [None]}, {'workflow_runs': [{'repository': None}]}]:
            source = github_source.GitHubSource(REPO, transport=lambda *args: json.dumps(response).encode())
            with self.assertRaises(github_source.GitHubSourceError): source.poll()

class TruncationTests(unittest.TestCase):
    def test_api_declared_total_cannot_be_silently_truncated(self):
        source = github_source.GitHubSource(REPO, transport=lambda *args: json.dumps({'items': [], 'total_count': 1001}).encode())
        with self.assertRaisesRegex(github_source.GitHubSourceError, 'truncated'):
            list(source._pages('/example', 'items'))

class IsolationTests(unittest.TestCase):
    def mixed(self, malformed=False, newer=False):
        source = GitHubSourceTests().source()
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            payload = None if '/zip' in url else json.loads(data)
            if '/runs?' in url:
                old = dict(payload['workflow_runs'][0], id=13 if newer else 11)
                if malformed: old['path'] = 'other.yml'
                payload['workflow_runs'].insert(0, old)
            elif ('/runs/13/artifacts?' if newer else '/runs/11/artifacts?') in url:
                payload['artifacts'][0]['expired'] = True
            return data if payload is None else json.dumps(payload).encode()
        source.transport = transport
        return source

    def test_expired_old_run_does_not_block_valid_run(self):
        source = self.mixed()
        self.assertEqual([b['run_id'] for b in source.poll()], ['12'])
        self.assertEqual(source.errors, [{'run_id': '11', 'attempt': '2', 'head_sha': SHA, 'error': 'merge artifact expired'}])
        source.transport = GitHubSourceTests().source().transport
        source.poll()
        self.assertEqual(source.errors, [])

    def test_malformed_old_run_does_not_block_valid_run(self):
        source = self.mixed(malformed=True)
        self.assertEqual([b['run_id'] for b in source.poll()], ['12'])
        self.assertEqual(source.errors[0]['run_id'], '11')

    def test_all_expired_runs_raise_and_preserve_errors(self):
        source = self.mixed()
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            if '/artifacts?' in url:
                payload = json.loads(data)
                payload['artifacts'][0]['expired'] = True
                return json.dumps(payload).encode()
            return data
        source.transport = transport
        with self.assertRaises(github_source.GitHubSourceError): source.poll()
        self.assertEqual(len(source.errors), 2)

class NewerFailureTests(unittest.TestCase):
    def test_newer_expired_same_head_suppresses_old_pass(self):
        source = IsolationTests().mixed(newer=True)
        with self.assertRaises(github_source.GitHubSourceError): source.poll()
        self.assertEqual(source.errors[0]['head_sha'], SHA)
        self.assertEqual(source.errors[0]['attempt'], '2')

    def test_newer_expired_different_head_keeps_unrelated_pass(self):
        source = IsolationTests().mixed(newer=True)
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            if '/runs?' in url:
                payload = json.loads(data)
                payload['workflow_runs'][0]['head_sha'] = 'c' * 40
                return json.dumps(payload).encode()
            return data
        source.transport = transport
        self.assertEqual(source.poll()[0]['run_id'], '12')

    def test_unknown_failed_run_identity_blocks_all(self):
        source = IsolationTests().mixed(malformed=True)
        original = source.transport
        def transport(url, headers, limit):
            data = original(url, headers, limit)
            if '/runs?' in url:
                payload = json.loads(data)
                payload['workflow_runs'][0].pop('head_sha')
                return json.dumps(payload).encode()
            return data
        source.transport = transport
        with self.assertRaises(github_source.GitHubSourceError): source.poll()

class MissingArtifactTests(unittest.TestCase):
    def test_newer_no_artifact_suppresses_old_pass(self):
        source = IsolationTests().mixed(newer=True)
        original = source.transport
        def transport(url, headers, limit):
            if '/runs/13/artifacts?' in url: return b'{"artifacts": []}'
            return original(url, headers, limit)
        source.transport = transport
        with self.assertRaises(github_source.GitHubSourceError): source.poll()
