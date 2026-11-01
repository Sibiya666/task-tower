import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from test_readiness import ProjectFixture
from task_tower import tasks
from task_tower.reviewer import ReviewRunner
from task_tower.postmerge_worker import Worker


class Source:
    def __init__(self, events):
        self.events = events

    def poll(self):
        return self.events


class WorkerTests(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.card = self.root / 'docs/tasks/TT-WORKER-1.json'
        self.card.parent.mkdir(parents=True)
        self.card.write_text(json.dumps({'version': 1, 'id': 'TT-WORKER-1',
            'project_root': '../..', 'executor': 'implementer', 'status': 'in_progress', 'stages': {}}))
        evidence = self.root / 'evidence.md'
        evidence.write_text('independent prior review')
        for stage in ('spec', 'development', 'test'):
            tasks.accept_task(self.card, stage, 'earlier-reviewer', evidence)
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'task')
        self.sha = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', self.sha)
        self.bundle = {'repository': 'owner/repo', 'pr_number': 1, 'merge_commit': self.sha,
            'run_id': '100', 'attempt': '1', 'task_ids': ['TT-WORKER-1'],
            'platforms': dict.fromkeys(('windows', 'linux', 'macos'), 'passed'),
            'run_url': 'https://github.com/owner/repo/actions/runs/100', 'delivery_key': 'fixture'}
        skill = self.root / 'skills/using-superpowers/SKILL.md'
        self.counter = self.root.parent / (self.root.name + '-reviews.txt')
        self.addCleanup(lambda: self.counter.unlink(missing_ok=True))
        script = self.root.parent / (self.root.name + '-reviewer.py')
        self.addCleanup(lambda: script.unlink(missing_ok=True))
        script.write_text("import json,sys\nfrom pathlib import Path\n"
            "r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
            "p=Path(sys.argv[3]); p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
            "Path(sys.argv[2]).write_text(json.dumps({'task_id':r['task']['id'],"
            "'commit':r['bundle']['merge_commit'],'verdict':'approve','summary':'checked',"
            "'findings':[]}),encoding='utf-8')\n", encoding='utf-8')
        self.reviewer = ReviewRunner({'kind': 'custom', 'timeout_seconds': 5,
            'superpowers': {'path': str(skill), 'sha256': hashlib.sha256(skill.read_bytes()).hexdigest()},
            'review_argv': [sys.executable, str(script), '{request}', '{result}', str(self.counter)]})
        self.config = {'project': str(self.root), 'repository': 'owner/repo', 'max_reviews': 1}

    def worker(self, source=None, reviewer=None):
        return Worker(self.config, source or Source([self.bundle]), reviewer or self.reviewer,
                      refresh=lambda: None)

    def test_real_subprocess_review_closes_task_once_across_restart(self):
        self.worker().once()
        card = tasks.load_task(self.card)
        self.assertEqual(card['status'], 'done')
        self.assertEqual(card['stages']['postmerge']['commit'], self.sha)
        self.worker().once()
        self.assertEqual(self.counter.read_text(), 'x')

    def test_missing_platform_waits_without_reviewer(self):
        del self.bundle['platforms']['macos']
        self.worker().once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'awaiting_postmerge')
        self.assertFalse(self.counter.exists())

    def test_latest_merge_for_task_supersedes_old_failed_merge(self):
        old = dict(self.bundle, merge_commit='0' * 40, run_id='99',
                   platforms=dict.fromkeys(('windows', 'linux', 'macos'), 'failed'))
        rows = self.worker(source=Source([old, self.bundle])).once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'done')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['commit'], self.sha)

    def test_failed_checks_do_not_launch_agent(self):
        self.bundle['platforms']['macos'] = 'failed'
        self.worker().once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'postmerge_failed')
        self.assertFalse(self.counter.exists())

    def test_card_arriving_after_event_is_retried_without_manual_reset(self):
        parked = self.card.with_suffix('.parked')
        self.card.rename(parked)
        first = self.worker().once()
        self.assertEqual(first[0]['status'], 'waiting')
        self.assertFalse(self.counter.exists())
        parked.rename(self.card)
        self.worker().once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'done')

    def test_rejection_never_closes(self):
        class Reject:
            def review(inner, checkout, task, bundle, output_dir):
                return dict(task_id=task['id'], commit=bundle['merge_commit'],
                            verdict='reject', summary='defect', findings=['defect'])
        self.worker(reviewer=Reject()).once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'postmerge_failed')

    def test_card_edit_during_review_needs_input_not_overwrite(self):
        class Mutate:
            def review(inner, checkout, task, bundle, output_dir):
                card = json.loads(self.card.read_text())
                card['title'] = 'new user requirement'
                self.card.write_text(json.dumps(card))
                return dict(task_id=task['id'], commit=bundle['merge_commit'],
                            verdict='approve', summary='checked', findings=[])
        self.worker(reviewer=Mutate()).once()
        card = tasks.load_task(self.card)
        self.assertEqual(card['title'], 'new user requirement')
        self.assertNotEqual(card['status'], 'done')

    def test_stale_legacy_does_not_get_silently_reaccepted(self):
        (self.root / 'evidence.md').write_text('changed')
        result = self.worker().once()
        self.assertFalse(self.counter.exists())
        self.assertTrue(any(row['status'] == 'needs_input' for row in result))

    def test_sticky_running_does_not_launch_again(self):
        worker = self.worker()
        worker.journal.claim('TT-WORKER-1', self.sha, 'old snapshot')
        worker.once()
        self.assertFalse(self.counter.exists())
        self.assertEqual(worker.journal.get('TT-WORKER-1', self.sha)['status'], 'running')

    def test_edit_at_acceptance_boundary_is_not_approved(self):
        original = tasks.accept_task
        def edit_then_accept(*args, **kwargs):
            card = json.loads(self.card.read_text())
            card['title'] = 'unreviewed requirement'
            self.card.write_text(json.dumps(card))
            return original(*args, **kwargs)
        with patch.object(tasks, 'accept_task', side_effect=edit_then_accept):
            self.worker().once()
        self.assertNotEqual(tasks.load_task(self.card)['status'], 'done')

    def test_saved_review_applies_after_restart_without_second_process(self):
        worker = self.worker()
        with patch.object(worker, '_apply', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                worker.once()
        self.assertEqual(worker.journal.get('TT-WORKER-1', self.sha)['status'], 'reviewed')
        self.worker().once()
        self.assertEqual(tasks.load_task(self.card)['status'], 'done')
        self.assertEqual(self.counter.read_text(), 'x')
