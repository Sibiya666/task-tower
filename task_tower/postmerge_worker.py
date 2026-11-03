"""Durable receipt -> independent review -> local task acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from . import tasks
from .github_source import GitHubSource, GitHubSourceError, resolve_token
from .postmerge_journal import Journal
from .reviewer import ReviewRunner


def snapshot(card):
    return tasks.task_snapshot(card)


def _write_json(path, value):
    path = tasks._safe_path(Path(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tasks._save_task(path, value)


class Worker:
    def __init__(self, config, source, reviewer, refresh=None, publisher=None, *, task_provider=None):
        self.project = Path(config['project']).resolve()
        self.repository = config['repository']
        if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', self.repository):
            raise ValueError('Invalid GitHub repository')
        if Path(tasks._git(self.project, 'rev-parse', '--show-toplevel')).resolve() != self.project:
            raise ValueError('Worker project must be the Git root')
        self.required = config.get('required_platforms', ['windows', 'macos', 'linux'])
        if (not isinstance(self.required, list) or not self.required or
                any(p not in ('windows', 'macos', 'linux') for p in self.required)):
            raise ValueError('Invalid required platforms')
        self.max_reviews = config.get('max_reviews', 1)
        if type(self.max_reviews) is not int or not 1 <= self.max_reviews <= 100:
            raise ValueError('max_reviews must be 1..100')
        self.state = tasks._safe_path(self.project / '.task-tower')
        self.state.mkdir(exist_ok=True)
        self.journal = Journal(self.state / 'postmerge.sqlite')
        self.source, self.reviewer = source, reviewer
        if task_provider is not None and not callable(task_provider): raise ValueError('Invalid trusted task provider')
        self.task_provider=task_provider
        self.refresh = refresh or self._refresh
        self.publisher = publisher
        if self.publisher is None and config.get('github_publication') is not None:
            from .github_publication import GitHubPublisher
            self.publisher = GitHubPublisher(self.repository, config['github_publication'], token=resolve_token())

    def _refresh(self):
        remote = tasks._git(self.project, 'remote', 'get-url', 'origin')
        expected = self.repository.lower()
        match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:)([^\s]+?)(?:\.git)?/?', remote)
        if not match or match[1].lower().removesuffix('.git') != expected:
            raise ValueError('origin does not match the configured GitHub repository')
        # Remote HTTPS teardown can outlast the short local-validation budget.
        tasks._git(self.project, 'fetch', 'origin', 'main', timeout=60)

    def _mark(self, path, state, bundle, detail):
        return tasks.update_postmerge_state(path, state, bundle['merge_commit'], detail,
                                             main_ref='refs/remotes/origin/main')

    def _task_path(self,task_id,bundle):
        path=(self.task_provider(task_id,bundle) if self.task_provider is not None else
              self.project/'docs/tasks'/(task_id+'.json'))
        path=tasks._safe_path(Path(path))
        if path!=self.project/'docs/tasks'/(task_id+'.json'):
            raise ValueError('Private card provider returned foreign path')
        return path

    def review_one(self,task_id,bundle,*,review_binding):
        """One genuine bound review; no publication or implicit unknown retry."""
        from .pr_evidence import PostmergeReviewBinding
        from .pr_policy import policy_fingerprint, strict_json
        from .pipeline_inputs import _ordinary
        from .pr_evidence import _persist_envelope, _git as bound_git, _validate_bound_envelope
        if type(review_binding) is not PostmergeReviewBinding: raise ValueError('Bound host review required')
        if not re.fullmatch(r'TT-[A-Z0-9]+(?:-[A-Z0-9]+)*',task_id): raise ValueError('Invalid selected task')
        self.refresh()
        relevant=[b for b in self.source.poll() if task_id in b.get('task_ids',[])]
        if not relevant: raise ValueError('Missing genuine selected bundle')
        latest=max((int(b['run_id']),int(b['attempt'])) for b in relevant)
        current=[b for b in relevant if (int(b['run_id']),int(b['attempt']))==latest]
        if any(b!=bundle for b in current) or bundle.get('repository')!=self.repository:
            raise ValueError('Superseded or foreign bundle')
        sha=bundle.get('merge_commit','')
        if not re.fullmatch('[0-9a-f]{40}',sha) or any(bundle.get('platforms',{}).get(p)!='passed' for p in self.required):
            raise ValueError('Incomplete selected CI')
        tasks._check_commit(self.project,sha,'refs/remotes/origin/main')
        if bound_git(self.project,'rev-parse','refs/remotes/origin/main').decode().strip()!=sha:
            raise ValueError('Selected bundle is not exact current main')
        path=self._task_path(task_id,bundle); card=tasks.load_task(path)
        if card['id']!=task_id or review_binding.merge_commit!=sha: raise ValueError('Selected card mismatch')
        envelope_path=tasks._safe_path(self.state/'bound-reviews'/(review_binding.effect_id+'.json'))
        row=self.journal.get(task_id,sha)
        if row is not None:
            if row['status'] not in ('reviewed','done') or not envelope_path.is_file():
                raise ValueError('Orphan or unbound review fenced')
            _ordinary(envelope_path); envelope=strict_json(envelope_path.read_bytes())
            _validate_bound_envelope(envelope)
            request=envelope['request']
            if (request!=review_binding.request(request['task'],bundle,self.reviewer.config) or
                    envelope['receipt_sha256']!=policy_fingerprint({k:v for k,v in envelope.items() if k!='receipt_sha256'}) or
                    envelope['result_sha256']!=policy_fingerprint(envelope['result']) or row['result']!=envelope['result'] or
                    row['snapshot']!=review_binding.snapshot_sha256): raise ValueError('Changed bound review')
            prior=json.loads(json.dumps(card)); prior['stages']['postmerge']={'status':'pending'}
            if snapshot(prior)!=row['snapshot']:
                prior['stages'].pop('postmerge')
                if snapshot(prior)!=row['snapshot']: raise ValueError('Changed bound review card')
            if row['status']=='reviewed': self._apply(path,bundle,row)
            return dict(self.journal.get(task_id,sha),host_review=envelope)
        if card['status']=='done': raise ValueError('Unbound completed card')
        review_binding.request(card,bundle,self.reviewer.config)
        if envelope_path.exists(): raise ValueError('Orphan envelope fenced')
        if not self.journal.claim(task_id,sha,snapshot(card)): raise ValueError('Review already claimed')
        self._mark(path,'reviewing',bundle,'Independent bound reviewer running')
        with tempfile.TemporaryDirectory(prefix='checkout-',dir=self.state) as directory:
            checkout=Path(directory).resolve()
            bound_git(self.project,'-c','protocol.file.allow=always','clone','--shared','--no-checkout',str(self.project),str(checkout))
            bound_git(checkout,'-c','core.autocrlf=false','checkout','--detach',sha)
            if bound_git(checkout,'rev-parse','HEAD').decode().strip()!=sha or bound_git(checkout,'status','--porcelain=v1','--untracked-files=all'):
                raise ValueError('Reviewer checkout mismatch')
            output=tasks._safe_path(self.state/'bound-output'/review_binding.effect_id)
            envelope=self.reviewer.review_bound(checkout,card,bundle,output,binding=review_binding,executor_profile=self.reviewer.config)
            _validate_bound_envelope(envelope)
            if bound_git(checkout,'rev-parse','HEAD').decode().strip()!=sha or bound_git(checkout,'status','--porcelain=v1','--untracked-files=all'):
                raise ValueError('Readonly reviewer changed checkout')
        _persist_envelope(envelope_path,envelope)
        self.journal.save_review(task_id,sha,envelope['result'])
        self._apply(path,bundle,self.journal.get(task_id,sha))
        return dict(self.journal.get(task_id,sha),host_review=envelope)

    def _apply(self, path, bundle, row):
        task_id, sha = row['task_id'], bundle['merge_commit']
        card = tasks.load_task(path)
        if card['status'] == 'done':
            self.journal.finish(task_id, sha, 'done', 'Already accepted')
            return
        if snapshot(card) != row['snapshot']:
            self._mark(path, 'needs_input', bundle, 'Task changed during review')
            self.journal.finish(task_id, sha, 'needs_input', 'Task changed during review')
            return
        result = row['result']
        if (not isinstance(result, dict) or result.get('task_id') != task_id or
                result.get('commit') != sha or result.get('verdict') not in
                ('approve', 'reject', 'needs_input') or not isinstance(result.get('summary'), str)
                or not result['summary'].strip() or not isinstance(result.get('findings'), list)
                or any(not isinstance(x, str) for x in result['findings'])):
            result = dict(task_id=task_id, commit=sha, verdict='needs_input',
                          summary='Invalid reviewer response', findings=[])
        report = self.project / 'docs/tasks/evidence' / task_id / f'postmerge-{sha}.json'
        _write_json(report, {'task_id': task_id, 'commit': sha, 'bundle': bundle, 'review': result})
        if result['verdict'] == 'approve':
            tasks.accept_task(path, 'postmerge', 'postmerge-agent', report, sha,
                              main_ref='refs/remotes/origin/main', expected_snapshot=row['snapshot'])
            self.journal.finish(task_id, sha, 'done', result['summary'])
        else:
            state = 'failed' if result['verdict'] == 'reject' else 'needs_input'
            self._mark(path, state, bundle, result['summary'])
            self.journal.finish(task_id, sha, 'needs_input', result['summary'])

    def once(self):
        self.refresh()
        # Latest run/attempt wins for a task+SHA, regardless of API ordering.
        latest = {}
        for bundle in self.source.poll():
            if bundle.get('repository') != self.repository or not re.fullmatch(
                    '[0-9a-f]{40}', bundle.get('merge_commit', '')):
                raise ValueError('Invalid verified bundle')
            for task_id in bundle['task_ids']:
                if not re.fullmatch(r'TT-[A-Z0-9]+(?:-[A-Z0-9]+)*', task_id):
                    raise ValueError('Invalid task ID')
                key = task_id, bundle['merge_commit']
                rank = int(bundle['run_id']), int(bundle['attempt'])
                if key not in latest or rank > latest[key][0]:
                    latest[key] = rank, bundle
        selected = {}
        for (task_id, sha), (rank, bundle) in latest.items():
            if task_id not in selected or rank > selected[task_id][0]:
                selected[task_id] = rank, bundle
        active = {(task_id, item[1]['merge_commit']) for task_id, item in selected.items()}
        started = 0
        for task_id, (_, bundle) in sorted(selected.items()):
            sha = bundle['merge_commit']
            row = self.journal.get(task_id, sha)
            if row and row['status'] in ('done', 'running', 'needs_input'):
                continue
            path = self.project / 'docs/tasks' / (task_id + '.json')
            try:
                path = self._task_path(task_id,bundle)
                if not path.is_file():
                    if self.journal.claim(task_id, sha, ''):
                        self.journal.finish(task_id, sha, 'waiting', 'Task card not available locally yet')
                    continue
                card = tasks.load_task(path)
                if card['id'] != task_id:
                    raise ValueError('Task ID does not match its filename')
                if card['status'] == 'done':
                    continue  # Never implicitly reopen a completed task.
                tasks._check_commit(self.project, sha, 'refs/remotes/origin/main')
                platforms = bundle['platforms']
                if not isinstance(platforms, dict) or any(
                        p not in ('windows', 'linux', 'macos') or v not in ('passed', 'failed')
                        for p, v in platforms.items()):
                    raise ValueError('Invalid platform checks')
                failed = any(platforms.get(p) == 'failed' for p in self.required)
                missing = any(p not in platforms for p in self.required)
                if failed or missing or (started >= self.max_reviews and not (row and row['status'] == 'reviewed')):
                    if self.journal.claim(task_id, sha, snapshot(card)):
                        self._mark(path, 'failed' if failed else 'pending', bundle,
                                   'CI failed' if failed else 'Waiting for platforms or reviewer budget')
                        self.journal.finish(task_id, sha, 'blocked' if failed else 'waiting')
                    continue
                if row and row['status'] == 'reviewed':
                    self._apply(path, bundle, row)
                    continue
                if not self.journal.claim(task_id, sha, snapshot(card)):
                    continue
                self._mark(path, 'reviewing', bundle, 'Independent reviewer running')
                started += 1
                with tempfile.TemporaryDirectory(prefix='checkout-', dir=self.state) as directory:
                    checkout = Path(directory).resolve()
                    tasks._git(self.project, 'clone', '--shared', '--no-checkout', str(self.project), str(checkout))
                    tasks._git(checkout, 'checkout', '--detach', sha)
                    if tasks._git(checkout, 'rev-parse', 'HEAD') != sha:
                        raise ValueError('Reviewer checkout mismatch')
                    output = tasks._safe_path(self.state / 'reviews' / task_id / sha)
                    result = self.reviewer.review(checkout, card, bundle, output)
                self.journal.save_review(task_id, sha, result)
                self._apply(path, bundle, self.journal.get(task_id, sha))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                row = self.journal.get(task_id, sha)
                if row is None:
                    self.journal.claim(task_id, sha, '')
                self.journal.finish(task_id, sha, 'needs_input', str(error))
                try:
                    self._mark(path, 'needs_input', bundle, str(error))
                except (OSError, ValueError):
                    pass  # Stale/missing cards are not rewritten to bypass validation.
        rows = [dict(row, active=(row['task_id'], row['commit']) in active)
                for row in self.journal.rows()]
        if self.publisher:
            for row in rows:
                mapping = getattr(self.publisher, 'mapping', None)
                if mapping is not None and row['task_id'] not in mapping:
                    row.pop('publication', None)
                    continue
                if row['status'] != 'done' or not row['active']:
                    continue
                bundle = selected[row['task_id']][1]
                try:
                    path = self._task_path(row['task_id'],bundle)
                    if hasattr(self.publisher, 'verify_source'):
                        self.publisher.verify_source = self.source.poll
                    row['publication'] = self.publisher.publish(path, bundle, row, self.required, self.journal)
                except Exception:
                    row['publication'] = {'status': 'failed', 'detail': 'Publication proof unavailable or rejected'}
        return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--retry', nargs=2, metavar=('TASK', 'COMMIT'))
    parser.add_argument('--recover', nargs=2, metavar=('TASK', 'COMMIT'))
    parser.add_argument('--confirm-stopped', action='store_true')
    parser.add_argument('--project', type=Path)
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        config_dir = args.config.resolve().parent
        project = args.project or Path(config['project'])
        config['project'] = str((config_dir / project).resolve() if not project.is_absolute() else project.resolve())
        if 'superpowers' not in config['reviewer']:
            from .harness import load_config
            bootstrap = load_config(Path(config['project'])) or {}
            if 'superpowers' not in bootstrap:
                raise ValueError('Configure bootstrap Superpowers or provide reviewer.superpowers')
            config['reviewer']['superpowers'] = bootstrap['superpowers']
        pin = config['reviewer']['superpowers']
        pin['path'] = str((config_dir / Path(pin['path'])).resolve())
        interval = config.get('interval_seconds', 30)
        if type(interval) not in (int, float) or not 5 <= interval <= 3600:
            raise ValueError('interval_seconds must be 5..3600')
        source = GitHubSource(config['repository'])
        worker = Worker(config, source, ReviewRunner(config['reviewer']))
        if args.retry:
            worker.journal.retry(*args.retry)
        if args.recover:
            worker.journal.recover(*args.recover, confirm_stopped=args.confirm_stopped)
        if args.confirm_stopped and not args.recover:
            raise ValueError('--confirm-stopped is only used with --recover')
        if args.status or args.retry or args.recover:
            print(json.dumps(worker.journal.rows(), ensure_ascii=False, indent=2))
            return 0
        last = None
        while True:
            try:
                worker.source = GitHubSource(config['repository'], token=resolve_token())
                rows = worker.once()
            except (GitHubSourceError, ValueError) as error:
                if args.once:
                    raise
                text = 'Receipt paused: ' + str(error)
                if text != last:
                    print(text, flush=True)
                    last = text
                time.sleep(interval)
                continue
            summary = [{k: row[k] for k in ('task_id', 'commit', 'status', 'detail', 'active', 'publication') if k in row} for row in rows]
            source_errors = getattr(worker.source, 'errors', [])
            text = json.dumps({'tasks': summary, 'source_errors': source_errors}, ensure_ascii=False, sort_keys=True)
            if text != last:
                print(text, flush=True)
                last = text
            if args.once:
                return 1 if source_errors or any(row['active'] and (row['status'] in ('needs_input', 'blocked') or row.get('publication', {}).get('status') in ('failed', 'publishing', 'pending')) for row in rows) else 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, KeyError, GitHubSourceError) as error:
        print('postmerge-worker: ' + str(error), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
