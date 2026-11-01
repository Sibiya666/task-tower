"""Bounded GitHub Issue store. Issue bodies are data, never execution authority."""
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import quote

from .github_source import resolve_token, GitHubSourceError, MAX_BYTES, MAX_PAGES

START = '<!-- task-tower:v1\n'
END = '\n-->'


def parse_metadata(body):
    body = body or ''
    if not isinstance(body, str): raise ValueError('Invalid Issue body')
    if body.count('<!-- task-tower:') > 1: raise ValueError('Duplicate task metadata')
    if '<!-- task-tower:' not in body: return None
    if START not in body: raise ValueError('Unsupported task metadata')
    try:
        raw = body.split(START, 1)[1].split(END, 1)
        if len(raw) != 2: raise ValueError()
        data = json.loads(raw[0])
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1 or data.get('kind') not in ('idea', 'task'):
            raise ValueError()
        stages = data.get('stages', {})
        order = ('spec', 'development', 'test', 'postmerge')
        if not isinstance(stages, dict) or set(stages) - set(order): raise ValueError()
        pending = False
        for stage in order:
            record = stages.get(stage, {'status': 'pending'})
            if not isinstance(record, dict) or record.get('status') not in ('pending', 'accepted'): raise ValueError()
            if record['status'] == 'pending': pending = True
            else:
                if pending or not isinstance(data.get('executor'), str) or not data['executor'] or not isinstance(record.get('reviewer'), str) or not record['reviewer'] or record['reviewer'] == data['executor']:
                    raise ValueError()
                if not isinstance(record.get('evidence'), str) or not record['evidence'] or not isinstance(record.get('sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', record['sha256']): raise ValueError()
                if stage == 'postmerge' and (record.get('main_ref') not in ('refs/heads/main', 'refs/remotes/origin/main') or not isinstance(record.get('commit'), str) or not re.fullmatch(r'[a-f0-9]{40}', record['commit'])): raise ValueError()
        if 'capture' in data or 'capture_promotion' in data:
            from .capture import capture_projection
            capture_projection(data)
        return data
    except (ValueError, IndexError): raise ValueError('Invalid task metadata') from None


def replace_metadata(body, metadata):
    block = START + json.dumps(metadata, ensure_ascii=False, sort_keys=True) + END
    parse_metadata(block)
    body = body or ''
    existing = parse_metadata(body)
    if existing is None: return body + ('\n\n' if body and not body.endswith('\n') else '') + block
    begin = body.index(START)
    finish = body.index(END, begin) + len(END)
    return body[:begin] + block + body[finish:]


def task_status(metadata):
    # Even structurally convincing body metadata is user-editable, not attestation.
    if not metadata: return 'open'
    status = metadata.get('status', 'open')
    if status == 'done' or metadata.get('stages', {}).get('postmerge', {}).get('status') == 'accepted':
        return 'needs_input'
    return status if status in ('open', 'in_progress', 'needs_input', 'awaiting_merge', 'awaiting_postmerge', 'postmerge_review', 'postmerge_failed') else 'needs_input'


class GitHubRequestError(GitHubSourceError):
    """A closed set of diagnostics; remote strings are never retained."""
    def __init__(self, *, http_status=None, category='invalid_response'):
        self.http_status=http_status if type(http_status) is int and 100<=http_status<=599 else None
        self.category=category if category in ('network','invalid_response') else 'invalid_response'
        message=('GitHub HTTP '+str(self.http_status) if self.http_status is not None else
                 'GitHub network unavailable' if self.category=='network' else 'GitHub response unavailable or invalid')
        super().__init__(message)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise GitHubSourceError('GitHub redirects are not allowed')


def _transport(method, url, headers, payload, limit):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
        content = response.read(limit + 1)
    if len(content) > limit: raise GitHubSourceError('GitHub response too large')
    return content


class GitHubTasks:
    def __init__(self, connection, token=None, transport=None):
        self.connection = connection
        self.repository = connection.repository
        self.transport = transport or _transport
        self.headers = {'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Task-Tower'}
        token = token if token is not None else (resolve_token() if transport is None else None)
        if token: self.headers['Authorization'] = 'Bearer ' + token

    def request(self, method, path, payload=None):
        if method not in ('GET', 'POST', 'PATCH', 'PUT') or not path.startswith('/') or ('..' in path and not re.fullmatch(r'/compare/[0-9a-f]{40}\.\.\.main', path)) or '://' in path or '#' in path:
            raise ValueError('Invalid GitHub request')
        try:
            raw = self.transport(method, 'https://api.github.com/repos/' + self.repository + ('' if path == '/' else path), dict(self.headers), payload, MAX_BYTES)
            if not isinstance(raw, bytes) or len(raw) > MAX_BYTES: raise ValueError()
            return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise GitHubRequestError(http_status=error.code) from None
        except (urllib.error.URLError, OSError):
            raise GitHubRequestError(category='network') from None
        except Exception:
            raise GitHubRequestError() from None

    @staticmethod
    def _number(number):
        if type(number) is not int or number < 1: raise ValueError('Invalid Issue number')
        return str(number)

    def list_issues(self):
        rows = []
        for page in range(1, MAX_PAGES + 1):
            data = self.request('GET', f'/issues?state=all&per_page=100&page={page}')
            if not isinstance(data, list) or len(data) > 100: raise GitHubSourceError('Invalid Issue page')
            if any(not isinstance(item, dict) for item in data): raise GitHubSourceError('Invalid Issue row')
            rows.extend(item for item in data if 'pull_request' not in item)
            if len(data) < 100: return rows
        raise GitHubSourceError('Issue pagination limit exceeded')

    def get(self, number):
        issue = self.request('GET', '/issues/' + self._number(number))
        if not isinstance(issue, dict) or issue.get('number') != number or 'pull_request' in issue:
            raise GitHubSourceError('Invalid Issue identity')
        return issue

    def update(self, number, **fields):
        if set(fields) - {'body', 'title', 'state', 'labels'}: raise ValueError('Invalid Issue update')
        return self.request('PATCH', '/issues/' + self._number(number), fields)

    metadata = staticmethod(lambda issue: parse_metadata(issue.get('body')))

    def import_card(self, path):
        from .tasks import load_task
        from .project_onboarding import preflight
        from .projects_board import sync_issue
        from .creation_journal import CreationJournal
        path = Path(path).resolve()
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or not raw['id'].strip(): raise ValueError('Invalid legacy card')
        # Preserve evidence as historical data; imports never attest remote completion.
        try:
            verified = load_task(path)
            status = verified['status'] if verified['status'] != 'done' else 'needs_input'
        except ValueError:
            status = 'needs_input'
        # This must succeed before any Issue POST, including retries.
        repository=preflight(self.connection, self)
        journal=CreationJournal(self.connection.checkout/'.task-tower'/'create-intents.sqlite3')

        def find_existing():
            matches=[]
            for issue in self.list_issues():
                metadata=self.metadata(issue)
                if not metadata: continue
                aliases=[metadata[key] for key in ('task_id','legacy_id','id') if key in metadata]
                if raw['id'] in aliases:
                    if any(alias!=raw['id'] for alias in aliases): raise ValueError('Conflicting task identity aliases; repair existing Issue metadata')
                    matches.append(issue)
            if len(matches)>1: raise ValueError('Ambiguous task identity; repair duplicate Issues before importing')
            return matches[0] if matches else None

        def repair(issue):
            if not isinstance(issue,dict) or type(issue.get('number')) is not int or issue['number']<1:
                raise ValueError('Issue creation outcome uncertain; inspect repository before retrying')
            result=dict(issue)
            try:
                from .project_worker import issue_lifecycle, verified_done
                from .github_source import GitHubSource
                source=GitHubSource(self.repository,transport=lambda url,headers,limit: self.transport('GET',url,dict(self.headers),None,limit))
                def current_status(current):
                    metadata=issue_lifecycle(self,current)
                    if metadata.get('status')=='done' and verified_done(self.connection,self,source,current): return 'done'
                    return task_status(metadata)
                result['project_sync']=sync_issue(self.connection,self,issue['number'],verified_status=current_status)
            except (GitHubSourceError,ValueError,KeyError,TypeError):
                result['project_sync']=dict(status='unavailable',detail='Project repair unavailable; check access and rerun import')
            if result['project_sync']['status']!='synced':
                result['project_sync'].update(stage='membership_or_status',issue_url='https://github.com/'+self.repository+'/issues/'+str(issue['number']),retry='Rerun import to repair the existing Issue')
            return result

        def reconcile_and_repair(issue):
            try:
                journal.reconcile('issue',repository['id'],raw['id'],str(issue['number']))
            except ValueError:
                return dict(issue,project_sync=dict(status='unavailable',stage='creation_journal',
                    issue_url='https://github.com/'+self.repository+'/issues/'+str(issue['number']),
                    detail='Issue retained; private creation journal could not reconcile',
                    retry='Preserve the journal, restore access or inspect its existing identity, then retry the same card'))
            return repair(issue)

        existing=find_existing()
        if existing: return reconcile_and_repair(existing)
        metadata = dict(version=1, kind='task', legacy_id=raw['id'], status=status, legacy_card=raw)
        body = replace_metadata(raw.get('description', '') if isinstance(raw.get('description', ''), str) else '', metadata)
        if not journal.reserve('issue',repository['id'],raw['id']):
            raise ValueError('Issue creation outcome uncertain or previously resolved Issue unavailable; inspect repository task identity. Preserve .task-tower/create-intents.sqlite3; no POST retried')
        try:
            issue=self.request('POST', '/issues', dict(title=str(raw.get('title') or raw['id'])[:256], body=body))
            if not isinstance(issue,dict) or type(issue.get('number')) is not int: raise GitHubRequestError()
        except GitHubSourceError:
            issue=find_existing()
            if issue is None: raise ValueError('Issue creation outcome uncertain; inspect repository task identity before retrying; no POST retried') from None
        return reconcile_and_repair(issue)

    def library(self):
        repository = self.request('GET', '/')
        branch = repository.get('default_branch')
        if not isinstance(branch, str): raise GitHubSourceError('Default branch unavailable')
        commit = self.request('GET', '/commits/' + quote(branch, safe='')).get('sha')
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit): raise GitHubSourceError('Invalid library commit')
        tree = self.request('GET', '/git/trees/' + commit + '?recursive=1')
        if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list): raise GitHubSourceError('Library tree incomplete')
        return [dict(title=item['path'], source='https://github.com/' + self.repository + '/blob/' + commit + '/' + quote(item['path'], safe='/')) for item in tree['tree'] if item.get('type') == 'blob' and isinstance(item.get('path'), str) and item['path'].lower().endswith('.md')]
