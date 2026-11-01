"""Actions-serialized remote postmerge acceptance (no development executor)."""
import argparse
import hashlib
import json
import io
import zipfile
import os
from pathlib import Path
import re
import tempfile

from . import tasks
from .github_source import GitHubSource, resolve_token
from .reviewer import ReviewRunner


LIFECYCLE = '<!-- task-tower:lifecycle:v1\n'


def issue_lifecycle(store, issue):
    metadata = dict(store.metadata(issue) or {})
    latest = None
    for page in range(1,21):
        comments = store.request('GET', f"/issues/{issue['number']}/comments?per_page=100&page={page}")
        if not isinstance(comments,list): raise ValueError('Invalid lifecycle comments')
        for comment in comments:
            body = comment.get('body','')
            if body.startswith(LIFECYCLE) and body.endswith('\n-->'):
                data = json.loads(body[len(LIFECYCLE):-4])
                if not isinstance(data,dict) or set(data) - {'remote_attempt','status'}: raise ValueError('Invalid lifecycle')
                if type(comment.get('id')) is not int: raise ValueError('Invalid lifecycle identity')
                if latest is None or comment['id'] > latest[0]: latest=(comment['id'],data)
        if len(comments)<100: break
    else: raise ValueError('Lifecycle pagination exceeded')
    if latest: metadata.update(latest[1])
    return metadata


def verified_receipt(connection, store, source, number, attempt):
    """Fetch a bounded receipt attested by the installed workflow, never Issue prose."""
    run_id, run_attempt = str(attempt.get('run_id', '')), str(attempt.get('run_attempt', '1'))
    if not re.fullmatch('[1-9][0-9]*', run_id) or not re.fullmatch('[1-9][0-9]*', run_attempt): return None
    run = store.request('GET', '/actions/runs/' + run_id + '/attempts/' + run_attempt)
    if (run.get('status') != 'completed' or str(run.get('run_attempt')) != run_attempt
        or run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main'
        or run.get('path') != '.github/workflows/task-tower-project.yml'
        or run.get('repository', {}).get('full_name') != connection.repository): return None
    head = run.get('head_sha', '')
    if not re.fullmatch('[0-9a-f]{40}', head): return None
    comparison = store.request('GET', '/compare/' + head + '...main')
    if comparison.get('status') not in ('ahead', 'identical'): return None
    name = f'task-tower-review-{number}-{run_attempt}'
    artifacts = list(source._pages('/actions/runs/' + run_id + '/artifacts', 'artifacts'))
    matches = [a for a in artifacts if a.get('name') == name]
    if len(matches) != 1: return None
    artifact = matches[0]
    if (artifact.get('expired') is not False or artifact.get('workflow_run', {}).get('id') != int(run_id)
        or artifact.get('workflow_run', {}).get('head_sha') != head): return None
    data = source._get('/actions/artifacts/' + str(source._id(artifact.get('id'))) + '/zip', raw=True)
    if artifact.get('digest') != 'sha256:' + hashlib.sha256(data).hexdigest(): return None
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != f'{number}.json' or entries[0].file_size > 2*1024*1024: return None
        receipt = json.loads(archive.read(entries[0]))
    if (receipt.get('repository') != connection.repository or receipt.get('issue') != number
        or str(receipt.get('run_id')) != run_id or str(receipt.get('run_attempt')) != run_attempt): return None
    policy = receipt.get('policy', {})
    if (policy.get('reviewer') != 'postmerge-agent' or not policy.get('executor')
        or policy.get('executor') == policy.get('reviewer')
        or not re.fullmatch('[0-9a-fA-F]{64}',str(policy.get('superpowers_sha256','')))): return None
    required = receipt.get('required_platforms')
    if (not isinstance(required,list) or not required or any(not isinstance(p,str) or p not in ('windows','macos','linux') for p in required)
        or len(set(required)) != len(required)): return None
    bundle, review = receipt.get('bundle', {}), receipt.get('review', {})
    if bundle not in source.poll(): return None
    merge = bundle.get('merge_commit', '')
    if not re.fullmatch('[0-9a-f]{40}', merge): return None
    if store.request('GET', '/compare/' + merge + '...main').get('status') not in ('ahead','identical'): return None
    if (review.get('verdict') != 'approve' or review.get('commit') != bundle.get('merge_commit')
        or review.get('task_id') not in bundle.get('task_ids', [])
        or any(bundle.get('platforms', {}).get(p) != 'passed' for p in receipt.get('required_platforms', ['windows','macos','linux']))): return None
    return receipt


def verified_done(connection, store, source, issue):
    try:
        meta = issue_lifecycle(store, issue)
        if meta.get('remote_attempt', {}).get('status') != 'done': return False
        return verified_receipt(connection, store, source, issue['number'], meta['remote_attempt']) is not None
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile):
        return False


class ProjectWorker:
    def __init__(self, connection, config, store, source, reviewer, run_id=None):
        self.connection, self.config, self.store = connection, config, store
        self.source, self.reviewer = source, reviewer
        self.run_id = str(run_id or os.environ.get('GITHUB_RUN_ID', ''))
        self.state = tasks._safe_path(Path(config['state_dir']))
        self.state.mkdir(parents=True, exist_ok=True)
        self.mapping = config['issue_tasks']
        if not isinstance(self.mapping, dict): raise ValueError('issue_tasks must be a trusted mapping')
        for number, path in self.mapping.items():
            if not re.fullmatch('[1-9][0-9]*', number) or not re.fullmatch(r'docs/tasks/TT-[A-Z0-9-]+\.json', path):
                raise ValueError('Invalid issue task mapping')

    def _get(self, number):
        if str(number) not in self.mapping: raise ValueError('Issue has no trusted task mapping')
        issue = self.store.get(number)
        meta = self.store.metadata(issue) if hasattr(self.store,'put_metadata') else issue_lifecycle(self.store, issue)
        if not isinstance(meta, dict) or meta.get('kind') != 'task': raise ValueError('Issue is not a task')
        return issue, meta

    def _put(self, number, meta, **fields):
        # Append-only lifecycle never rewrites concurrent user prose.
        lifecycle = {key:meta[key] for key in ('remote_attempt','status') if key in meta}
        self.store.request('POST', f'/issues/{number}/comments',
                           {'body':LIFECYCLE + json.dumps(lifecycle,sort_keys=True) + '\n-->'})
        if fields: self.store.update(number, **fields)

    def _save(self, number, meta, **fields):
        if hasattr(self.store, 'put_metadata'): return self.store.put_metadata(number, meta, **fields)
        return self._put(number, meta, **fields)

    def dispatch(self, number):
        issue, meta = self._get(number)
        attempt = meta.get('remote_attempt', {})
        state = attempt.get('status')
        if state == 'needs_input' or (state == 'done' and issue.get('state') == 'closed'):
            return {'status': state, 'dispatched': False}
        if state in ('running','reviewed','done'):
            run_id = str(attempt.get('run_id',''))
            if not re.fullmatch('[1-9][0-9]*',run_id): raise ValueError('Invalid recorded attempt')
            if self.store.request('GET','/actions/runs/'+run_id).get('status') != 'completed':
                return {'status':state,'dispatched':False}
        # Immutable request survives API failure without racing the serialized lifecycle.
        self.store.request('POST', f'/issues/{number}/comments', {'body':'<!-- task-tower:queue:v1 --> Postmerge acceptance requested.'})
        workflow = self.config.get('workflow', 'task-tower-project.yml')
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.yml', workflow): raise ValueError('Invalid workflow filename')
        self.store.request('POST', '/actions/workflows/' + workflow + '/dispatches',
                           {'ref': 'main', 'inputs': {'issue': str(number)}})
        return {'status': 'queued', 'dispatched': True}

    def reconcile(self):
        results = []
        for n in self.mapping:
            number = int(n)
            _, meta = self._get(number)
            state = meta.get('remote_attempt', {}).get('status')
            if state == 'needs_input': continue
            if state in ('running','reviewed','done'):
                results.append(self.dispatch(number))
                continue
            found = False
            for page in range(1,21):
                comments = self.store.request('GET', f'/issues/{number}/comments?per_page=100&page={page}')
                if not isinstance(comments,list): raise ValueError('Invalid queue comments')
                found = found or any('<!-- task-tower:queue:v1 -->' in c.get('body','') for c in comments)
                if len(comments)<100: break
            else: raise ValueError('Queue comments pagination exceeded')
            if found: results.append(self.dispatch(number))
        return results

    def recover(self, number, confirm_stopped=False):
        if not confirm_stopped: raise ValueError('Explicit recovery requires --confirm-stopped')
        self._get(number)
        return self.store.request('POST', '/actions/workflows/task-tower-project.yml/dispatches',
            {'ref':'main','inputs':{'issue':str(number),'recover':'true'}})

    def _recover_serialized(self, number, confirm_stopped=False):
        _, meta = self._get(number)
        attempt = meta.get('remote_attempt', {})
        run = attempt.get('run_id', '')
        if not confirm_stopped or not re.fullmatch('[1-9][0-9]*', str(run)):
            raise ValueError('Explicit recovery requires --confirm-stopped and a recorded run')
        info = self.store.request('GET', '/actions/runs/' + str(run))
        if info.get('status') != 'completed': raise ValueError('Recorded Actions run is still active')
        identity = hashlib.sha256(f'{self.connection.repository}#{number}'.encode()).hexdigest()
        (self.state / (identity + '.json')).unlink(missing_ok=True)
        meta['remote_attempt'] = {'status': 'queued', 'recovered_run': run}
        self._save(number, meta)
        return meta['remote_attempt']

    def _refresh(self):
        root = self.connection.checkout
        remote = tasks._git(root, 'remote', 'get-url', 'origin')
        match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([^\s]+?)(?:\.git)?/?', remote)
        if not match or match[1].lower().removesuffix('.git') != self.connection.repository.lower():
            raise ValueError('origin does not match connected repository')
        tasks._git(root, 'fetch', 'origin', 'main')

    def _prepare(self, number):
        self._refresh()
        relative = self.mapping[str(number)]
        task_id = Path(relative).stem
        bundles = [b for b in self.source.poll() if b['repository'] == self.connection.repository and task_id in b['task_ids']]
        if not bundles: raise ValueError('No verified postmerge CI bundle for mapped task')
        bundle = max(bundles, key=lambda b: (int(b['run_id']), int(b['attempt'])))
        required = self.config.get('required_platforms', ['windows', 'macos', 'linux'])
        if (not isinstance(required,list) or not required or any(not isinstance(p,str) or p not in ('windows','macos','linux') for p in required)
            or len(set(required)) != len(required)):
            raise ValueError('Invalid required platforms')
        if any(bundle['platforms'].get(p) != 'passed' for p in required): raise ValueError('Required CI unavailable or failed')
        sha = bundle['merge_commit']
        tasks._check_commit(self.connection.checkout, sha, 'refs/remotes/origin/main')
        with self._checkout(sha) as directory:
            card = tasks.load_task(Path(directory) / relative)
            if card['executor'] == 'postmerge-agent': raise ValueError('Executor must differ from independent reviewer')
            if card['id'] != task_id or any(card['stages'].get(s, {}).get('status') != 'accepted' for s in ('spec','development','test')):
                raise ValueError('Verified prior independent acceptance required')
        return card, bundle, tasks.task_snapshot(card)

    def _checkout(self, sha):
        from contextlib import contextmanager
        @contextmanager
        def checkout():
            with tempfile.TemporaryDirectory(prefix='review-', dir=self.state) as directory:
                tasks._git(self.connection.checkout, 'clone', '--shared', '--no-checkout', str(self.connection.checkout), directory)
                tasks._git(Path(directory), 'checkout', '--detach', sha)
                yield directory
        return checkout()

    def _review(self, card, bundle):
        with self._checkout(bundle['merge_commit']) as directory:
            return self.reviewer.review(Path(directory), card, bundle, self.state / 'reviews' / self.run_id)

    def _remote_receipt(self, number, attempt):
        if self.source is None: return None
        return verified_receipt(self.connection, self.store, self.source, number, attempt)

    def consume(self, number, recover=False):
        if not re.fullmatch('[1-9][0-9]*', self.run_id): raise ValueError('Consumer requires Actions run identity')
        run = self.store.request('GET', '/actions/runs/' + self.run_id)
        if (run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main'
            or run.get('path') != '.github/workflows/task-tower-project.yml'
            or run.get('repository',{}).get('full_name') != self.connection.repository):
            raise ValueError('Consumer requires trusted main workflow dispatch')
        if recover: self._recover_serialized(number, True)
        _, meta = self._get(number)
        identity = hashlib.sha256(f'{self.connection.repository}#{number}'.encode()).hexdigest()
        receipt = self.state / (identity + '.json')
        saved = json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else None
        attempt = meta.get('remote_attempt', {})
        # Recovery supersedes receipts on every machine, even for the same commit.
        if saved and (str(saved.get('run_id','')) != str(attempt.get('run_id',''))
                      or str(saved.get('run_attempt','1')) != str(attempt.get('run_attempt','1'))):
            saved = None
        if not saved and attempt.get('status') in ('running', 'reviewed', 'done'):
            saved = self._remote_receipt(number, attempt)
        if attempt.get('status') in ('running', 'reviewed', 'done', 'needs_input') and not saved:
            raise ValueError('Explicit recovery required; receipt unavailable on this runner')
        card, bundle, snapshot = self._prepare(number)
        if saved:
            if saved['snapshot'] != snapshot or saved['bundle'] != bundle:
                raise ValueError('Receipt no longer matches authoritative evidence; explicit recovery required')
            result = saved['review']
        else:
            meta['remote_attempt'] = {'status': 'running', 'run_id': self.run_id, 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT','1'), 'commit': bundle['merge_commit']}
            self._save(number, meta)
            result = self._review(card, bundle)
            if (not isinstance(result, dict) or result.get('task_id') != card['id'] or result.get('commit') != bundle['merge_commit']
                or result.get('verdict') not in ('approve','reject','needs_input') or not isinstance(result.get('summary'), str)
                or not result['summary'].strip() or not isinstance(result.get('findings'), list)
                or any(not isinstance(f,str) for f in result['findings'])):
                raise ValueError('Invalid independent review')
            saved = {'snapshot': snapshot, 'bundle': bundle, 'review': result, 'run_id': self.run_id,
                     'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT','1'), 'repository': self.connection.repository,
                     'issue': number, 'policy': {'reviewer':'postmerge-agent','executor':card.get('executor'),
                         'superpowers_sha256':self.config.get('reviewer',{}).get('superpowers',{}).get('sha256')}, 'required_platforms': self.config.get('required_platforms',['windows','macos','linux'])}
            tasks._save_task(receipt, saved)
        public = self.state / 'public'
        public.mkdir(exist_ok=True)
        tasks._save_task(public / f'{number}.json', saved)
        # Receipt is durable before either remote publication. A second machine fails closed.
        _, current = self._get(number)
        current['remote_attempt'] = {'status':'reviewed', 'run_id': saved['run_id'], 'run_attempt':saved.get('run_attempt','1'), 'commit': bundle['merge_commit'],
                                     'review': result, 'snapshot': snapshot, 'ci_run': bundle.get('run_id')}
        self._save(number, current)
        current['remote_attempt']['status'] = 'done' if result['verdict'] == 'approve' else 'needs_input'
        current['status'] = 'done' if result['verdict'] == 'approve' else 'needs_input'
        self._save(number, current, state='closed' if result['verdict'] == 'approve' else 'open')
        return current['remote_attempt']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connections', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('command', choices=('dispatch','consume','recover','reconcile'))
    parser.add_argument('--issue', type=int)
    parser.add_argument('--confirm-stopped', action='store_true')
    args = parser.parse_args(argv)
    from .project_connections import load_connections
    from .github_tasks import GitHubTasks
    connection = next((c for c in load_connections(args.connections) if c.id == args.project), None)
    if connection is None: parser.error('Unknown project')
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    token = resolve_token()
    worker = ProjectWorker(connection, config, GitHubTasks(connection, token=token),
                           GitHubSource(connection.repository, token=token), ReviewRunner(config['reviewer']))
    if args.command != 'reconcile' and not args.issue: parser.error('--issue is required')
    result = worker.recover(args.issue, args.confirm_stopped) if args.command == 'recover' else (
        worker.reconcile() if args.command == 'reconcile' else worker.consume(args.issue, recover=args.confirm_stopped) if args.command == 'consume' else worker.dispatch(args.issue))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
