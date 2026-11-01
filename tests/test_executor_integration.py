"""Real file-backend admission and trusted-process execution; no Codex claim."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from task_tower.dispatch_delivery import run_backend
from task_tower.executor_profiles import load_executor_config, profile_fingerprint
from task_tower.executor_queue import ExecutionQueue
from task_tower.executor_worker import execute_one
from task_tower.project_connections import load_connections


HELPER = '''import argparse, json, os, pathlib, time
p = argparse.ArgumentParser()
p.add_argument('--request'); p.add_argument('--result')
a = p.parse_args()
r = json.loads(pathlib.Path(a.request).read_text(encoding='utf-8'))
assert not any(k.upper() in ('GH_TOKEN', 'GITHUB_TOKEN') for k in os.environ)
pathlib.Path('tracked.txt').write_text('isolated output', encoding='utf-8')
print('x' * 4096, flush=True)
print('y' * 4096, file=__import__('sys').stderr, flush=True)
if r['task_data']['body'] == 'wait for cancellation':
    pathlib.Path(a.result + '.ready').write_text('ready')
    time.sleep(30)
v = {k: r[k] for k in ('run_id', 'attempt_id', 'source_sha')}
if r['task_data']['body'] == 'wrong source': v['source_sha'] = '0' * 40
v.update(version=1, status='completed', summary='private helper output')
pathlib.Path(a.result).write_text(json.dumps(v), encoding='utf-8')
'''


class ExecutorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init')
        self.git('config', 'user.name', 'Integration fixture')
        self.git('config', 'user.email', 'fixture@example.test')
        (self.source / 'tracked.txt').write_text('approved source', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-m', 'approved fixture source')
        self.sha = self.git('rev-parse', 'HEAD')
        pins = self.root / 'pins'
        pins.mkdir()
        (pins / 'SKILL.md').write_bytes(b'Pinned fixture instructions\n')
        manifest = {'SKILL.md': hashlib.sha256(b'Pinned fixture instructions\n').hexdigest()}
        helper = self.root / 'helper.py'
        helper.write_text(HELPER, encoding='utf-8', newline='\n')
        connections = self.root / 'connections.json'
        connections.write_text(json.dumps(dict(version=1, projects=[dict(
            id='fixture', repository='Owner/Repo', checkout=str(self.source), runner_label='local')])))
        self.connections = load_connections(connections)
        policy = self.root / 'executor.json'
        profile = dict(kind='custom', trusted=True, repository='Owner/Repo',
            checkout=str(self.source), runner_label='local', argv=[str(Path(sys.executable).resolve()), str(helper)],
            source_ref=self.sha, timeout_seconds=10, log_max_bytes=128, max_attempts=2,
            runs_dir=str(self.root / 'runs'), superpowers=dict(root=str(pins), revision='a' * 40,
            manifest=manifest, manifest_sha256=profile_fingerprint(manifest)))
        policy.write_text(json.dumps(dict(version=1, profiles={'fixture': profile}, allowlist=[dict(
            repository='Owner/Repo', issue=15, task_id='TT-EXECUTOR-001', runner_label='local', profile='fixture')])))
        self.config = load_executor_config(policy, self.connections)
        self.config.update(_connections=self.connections, _authority_check=lambda: True)
        self.queue = ExecutionQueue(self.root / 'queue.db', checkouts=[self.source])
        self.backend = dict(argv=[sys.executable, '-m', 'task_tower', 'executor', 'adapter',
            '--connections', str(connections), '--config', str(policy), '--queue', str(self.queue.path),
            '--request', '{request}', '--result', '{result}'],
            cwd=str(Path(__file__).resolve().parents[1]), timeout_seconds=10)
        self.request = dict(operation='submit', delivery_id=str(uuid.uuid4()), repository='Owner/Repo',
            issue=15, task_id='TT-EXECUTOR-001', runner_label='local')
        self.row = dict(number=15, state='open', body='fixture task', meta=dict(
            version=1, kind='task', mode='autonomous', status='open', task_id='TT-EXECUTOR-001'))
        case = self

        class Store:
            def list_issues(self): return [copy.deepcopy(case.row)]
            def get(self, number): return copy.deepcopy(case.row)
            def metadata(self, row): return row['meta']
            def request(self, method, path): return []

        self.store = Store()
        self.addCleanup(self.remove_worktrees)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.source, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def remove_worktrees(self):
        for path in (self.root / 'runs').glob('*/*/worktree'):
            self.git('worktree', 'remove', '--force', str(path))

    def execute(self):
        # Only remote transport is substituted; production selection/authorization runs.
        with patch('task_tower.github_tasks.GitHubTasks', return_value=self.store), \
                patch('task_tower.dispatcher._source', return_value=SimpleNamespace()):
            return execute_one(self.config, self.queue)

    def submit(self):
        receipt = run_backend(self.backend, self.request)
        self.assertEqual(receipt['status'], 'accepted')
        return receipt['receipt_id']

    def test_dispatcher_admission_deduplicates_then_validated_isolated_execution(self):
        run = self.submit()
        self.assertEqual(self.queue.status(run)['state'], 'queued')
        self.assertFalse((self.root / 'runs').exists())
        self.assertEqual(self.submit(), run)
        self.assertEqual(run_backend(self.backend, dict(self.request, operation='lookup'))['receipt_id'], run)
        with patch.dict(os.environ, {'GH_TOKEN': 'fixture-host-only', 'GITHUB_TOKEN': 'fixture-host-only'}):
            report = self.execute()
            self.assertEqual(os.environ['GH_TOKEN'], 'fixture-host-only')
        self.assertEqual(report['status'], 'execution_completed')
        self.assertNotIn('summary', report)
        saved = self.queue.status(run)
        self.assertEqual(saved['attempt'], 1)
        directory = next((self.root / 'runs').glob('*/*/manifest.json')).parent
        manifest = json.loads((directory / 'manifest.json').read_text())
        request = json.loads((directory / 'request.json').read_text())
        result = json.loads((directory / 'result.json').read_text())
        for key in ('run_id', 'attempt_id', 'source_sha'):
            self.assertEqual(request[key], result[key])
            self.assertEqual(manifest[key], result[key])
        self.assertEqual(result['source_sha'], self.sha)
        self.assertEqual((self.source / 'tracked.txt').read_text(), 'approved source')
        self.assertEqual((directory / 'worktree' / 'tracked.txt').read_text(), 'isolated output')
        for filename, key in [('manifest.json', 'manifest_sha256'), ('request.json', 'request_sha256'), ('result.json', 'result_sha256')]:
            self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(), saved['evidence'][key])
        self.assertTrue(saved['evidence']['cleanup_confirmed'])
        process = json.loads((directory / 'process.json').read_text())
        for stream, letter in [('stdout', 'x'), ('stderr', 'y')]:
            emitted = (letter * 4096 + os.linesep).encode()
            self.assertTrue(process[stream + '_truncated'])
            self.assertEqual(process[stream + '_bytes'], len(emitted))
            self.assertEqual(process[stream + '_sha256'], hashlib.sha256(emitted).hexdigest())
        for log in (directory / 'logs').iterdir():
            self.assertLessEqual(log.stat().st_size, 128)
        self.assertEqual(self.execute()['status'], 'idle')
        self.assertEqual(self.submit(), run)
        self.assertEqual(self.queue.status(run)['attempt'], 1)

    def test_cancel_queued_delivery_never_launches(self):
        run = self.submit()
        self.queue.cancel(run)
        self.assertEqual(self.execute()['status'], 'idle')
        self.assertEqual(self.queue.status(run)['state'], 'cancelled')
        self.assertFalse((self.root / 'runs').exists())

    def test_reopened_queue_fences_abandoned_claim_without_reexecution(self):
        run = self.submit()
        # Claim in a real short-lived process so recovery has positive death proof.
        code = ('import sys,uuid; from task_tower.executor_queue import ExecutionQueue; '
            'q=ExecutionQueue(sys.argv[1]); owner=str(uuid.uuid4()); '
            'context=q.owner(owner); context.__enter__(); q.claim(owner)')
        subprocess.run([sys.executable, '-c', code, str(self.queue.path)],
            cwd=self.backend['cwd'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        reopened = ExecutionQueue(self.queue.path, checkouts=[self.source])
        reopened.recover()
        self.assertEqual(reopened.status(run)['state'], 'unknown')
        self.assertEqual(self.execute()['status'], 'idle')
        self.assertFalse((self.root / 'runs').exists())

    def test_wrong_source_result_fails_after_real_zero_exit(self):
        self.row['body'] = 'wrong source'
        run = self.submit()
        self.assertEqual(self.execute()['status'], 'failed')
        saved = self.queue.status(run)
        self.assertEqual(saved['evidence']['exit_code'], 0)
        self.assertTrue(saved['evidence']['cleanup_confirmed'])
        self.assertNotIn('result_sha256', saved['evidence'])

    def test_cancel_running_real_child_has_cleanup_proof(self):
        self.row['body'] = 'wait for cancellation'
        run = self.submit()
        reports = []
        thread = threading.Thread(target=lambda: reports.append(self.execute()))
        thread.start()
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if list((self.root / 'runs').glob('*/*/result.json.ready')):
                    break
                time.sleep(0.025)
            else:
                self.fail('Trusted child never reached ready boundary')
            self.queue.cancel(run)
        finally:
            self.queue.cancel(run)
            thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(reports[0]['status'], 'cancelled')
        self.assertTrue(self.queue.status(run)['evidence']['cleanup_confirmed'])
        self.assertEqual(self.execute()['status'], 'idle')


if __name__ == '__main__':
    unittest.main()
