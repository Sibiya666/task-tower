"""Bounded, read-only GitHub postmerge event receipt. No artifact code is run."""
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .merge_events import build_merge_event

MAX_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20


class GitHubSourceError(RuntimeError):
    """A receipt could not be verified; its contents are deliberately omitted."""


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or not target.hostname or target.username or target.password:
            raise GitHubSourceError('unsafe artifact redirect')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        # Storage redirects must never receive GitHub credentials (including same host).
        redirected.remove_header('Authorization')
        return redirected


def _http_get(url, headers, limit):
    from .source_deadline import remaining
    try:
        request = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.build_opener(_Redirect()).open(request, timeout=remaining(30)) as response:
            data = response.read(limit + 1)
        remaining(30)
        if len(data) > limit:
            raise GitHubSourceError('response exceeds size limit')
        return data
    except (urllib.error.URLError, OSError, ValueError):
        raise GitHubSourceError('GitHub request failed (authentication, expiry or network)') from None


def resolve_token():
    from .source_deadline import remaining
    """Use existing credentials only, without saving credentials or prompting."""
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        return token.strip()
    env = dict(os.environ, GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    for argv, request in [(['gh', 'auth', 'token', '--hostname', 'github.com'], None),
                          (['git', '-c', 'credential.interactive=false', 'credential', 'fill'], 'protocol=https\nhost=github.com\n\n')]:
        try:
            result = subprocess.run(argv, input=request, text=True, capture_output=True, timeout=remaining(10), env=env)
            remaining(10)
            if result.returncode == 0:
                if argv[0] == 'gh':
                    return result.stdout.strip() or None
                for line in result.stdout.splitlines():
                    if line.startswith('password='):
                        return line.partition('=')[2] or None
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class GitHubSource:
    def __init__(self, repository, token=None, transport=None):
        if not isinstance(repository, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*', repository):
            raise ValueError('repository must be owner/repo')
        self.errors = []
        self.repository = repository
        self.transport = transport or _http_get
        self.headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Task-Tower'}
        if token:
            self.headers['Authorization'] = 'Bearer ' + token

    def _get(self, path, raw=False):
        from .source_deadline import remaining
        try:
            remaining(30)
            data = self.transport('https://api.github.com/repos/' + self.repository + path, dict(self.headers), MAX_BYTES)
            remaining(30)
            if not isinstance(data, bytes) or len(data) > MAX_BYTES:
                raise ValueError()
            return data if raw else json.loads(data)
        except GitHubSourceError:
            raise
        except Exception:
            raise GitHubSourceError('invalid GitHub response') from None

    def _pages(self, path, key):
        received = 0
        for page in range(1, MAX_PAGES + 1):
            payload = self._get(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            rows = payload.get(key)
            if not isinstance(rows, list) or len(rows) > 100:
                raise GitHubSourceError('invalid GitHub page')
            received += len(rows)
            yield from rows
            if len(rows) < 100:
                if payload.get('total_count', received) > received:
                    raise GitHubSourceError('GitHub pagination truncated')
                return
        raise GitHubSourceError('GitHub pagination limit exceeded')

    @staticmethod
    def _id(value):
        if type(value) is not int or value <= 0:
            raise GitHubSourceError('invalid GitHub identifier')
        return value

    def _event(self, artifact):
        data = self._get('/actions/artifacts/' + str(self._id(artifact.get('id'))) + '/zip', raw=True)
        digest = artifact.get('digest')
        if digest is not None and digest != 'sha256:' + hashlib.sha256(data).hexdigest():
            raise GitHubSourceError('artifact digest mismatch')
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) != 1 or entries[0].filename != 'merge-event.json' or entries[0].file_size > MAX_BYTES or entries[0].flag_bits & 1:
                    raise ValueError()
                with archive.open(entries[0]) as stream:
                    payload = stream.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError()
                event = json.loads(payload)
                if not isinstance(event, dict):
                    raise ValueError()
                return event
        except (ValueError, OSError, zipfile.BadZipFile, RuntimeError):
            raise GitHubSourceError('invalid merge event ZIP') from None

    def poll(self):
        """Return verified bundles or a sanitized error; partial receipts never pass."""
        self.errors = []
        try:
            return self._poll()
        except GitHubSourceError:
            raise
        except Exception:
            raise GitHubSourceError('invalid GitHub merge metadata') from None

    def _poll(self):
        bundles = []
        heads = {}
        for run in self._pages('/actions/workflows/postmerge.yml/runs?status=completed', 'workflow_runs'):
            try:
                bundle = self._run(run)
            except Exception as exc:
                run_id = run.get('id') if isinstance(run, dict) else None
                run_id = str(run_id) if type(run_id) is int and run_id > 0 else None
                attempt = run.get('run_attempt') if isinstance(run, dict) else None
                attempt = str(attempt) if type(attempt) is int and attempt > 0 else None
                head = run.get('head_sha') if isinstance(run, dict) else None
                head = head.lower() if isinstance(head, str) and re.fullmatch(r'[0-9a-fA-F]{40}', head) else None
                message = str(exc) if isinstance(exc, GitHubSourceError) else 'invalid GitHub merge metadata'
                self.errors.append({'run_id': run_id, 'attempt': attempt, 'head_sha': head, 'error': message})
                continue
            if bundle:
                bundles.append(bundle)
                heads[bundle['delivery_key']] = run.get('head_sha', '').lower()
        if any(error['run_id'] is None or error['attempt'] is None or error['head_sha'] is None for error in self.errors):
            raise GitHubSourceError('unavailable workflow run has unknown identity')
        bundles = [bundle for bundle in bundles if not any(
            error['head_sha'] == heads[bundle['delivery_key']]
            and (int(error['run_id']), int(error['attempt'])) >= (int(bundle['run_id']), int(bundle['attempt']))
            for error in self.errors)]
        if not bundles and self.errors:
            raise GitHubSourceError('no verified merge bundles; ' + self.errors[0]['error'])
        return bundles

    def _run(self, run):
        if not isinstance(run, dict) or run.get('status') != 'completed' or run.get('path') != '.github/workflows/postmerge.yml' or run.get('event') != 'pull_request' or run.get('repository', {}).get('full_name') != self.repository:
            raise GitHubSourceError('workflow provenance mismatch')
        run_id, attempt = self._id(run.get('id')), self._id(run.get('run_attempt'))
        bundle = None
        for artifact in self._pages(f'/actions/runs/{run_id}/artifacts', 'artifacts'):
            name = artifact.get('name', '')
            match = re.fullmatch(r'task-tower-merge-([1-9][0-9]*)-(linux|macos|windows)', name)
            if not match:
                continue
            if artifact.get('expired') is not False:
                raise GitHubSourceError('merge artifact expired')
            provenance = artifact.get('workflow_run', {})
            if provenance.get('id') != run_id or provenance.get('head_sha') != run.get('head_sha'):
                raise GitHubSourceError('artifact provenance mismatch')
            number, platform = int(match[1]), match[2]
            refs = run.get('pull_requests', [])
            if not isinstance(refs, list) or (refs and not any(ref.get('number') == number for ref in refs)):
                raise GitHubSourceError('artifact PR does not belong to workflow run')
            pr = self._get(f'/pulls/{number}')
            if pr.get('number') != number or pr.get('head', {}).get('sha') != run.get('head_sha') or pr.get('base', {}).get('repo', {}).get('full_name') != self.repository:
                raise GitHubSourceError('merge provenance mismatch')
            try:
                merged_at = datetime.datetime.fromisoformat(pr['merged_at'].replace('Z', '+00:00'))
                created_at = datetime.datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
                if merged_at.utcoffset() is None or created_at.utcoffset() is None or created_at < merged_at:
                    raise ValueError()
            except (KeyError, TypeError, ValueError, AttributeError):
                raise GitHubSourceError('workflow predates merge or has invalid timestamps') from None
            event = self._event(artifact)
            try:
                expected = build_merge_event({'action': 'closed', 'repository': {'full_name': self.repository}, 'pull_request': pr}, self.repository, platform, event.get('checks'), run_id, attempt)
            except ValueError:
                raise GitHubSourceError('invalid merge metadata') from None
            if event != expected:
                raise GitHubSourceError('merge event identity mismatch')
            identity = {k: event[k] for k in ('repository', 'pr_number', 'merge_commit', 'task_ids', 'run_url')}
            if bundle is None:
                key = hashlib.sha256(json.dumps([self.repository, number, event['merge_commit'], str(run_id), str(attempt)], separators=(',', ':')).encode()).hexdigest()
                bundle = dict(identity, run_id=str(run_id), attempt=str(attempt), platforms={}, delivery_key=key)
            if any(bundle[k] != value for k, value in identity.items()) or platform in bundle['platforms']:
                raise GitHubSourceError('conflicting merge artifacts')
            bundle['platforms'][platform] = event['checks']
        if bundle is None:
            raise GitHubSourceError('merge artifacts unavailable')
        return bundle




