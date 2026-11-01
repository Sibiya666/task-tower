import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from task_tower.postmerge_journal import Journal


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve() / 'state' / 'journal.sqlite'
        self.journal = Journal(self.path)
        self.sha = 'a' * 40

    def test_running_survives_restart_and_only_one_connection_claims(self):
        other = Journal(self.path)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            wins = list(pool.map(lambda j: j.claim('task-1', self.sha, 'snapshot'),
                                 [self.journal, other]))
        self.assertEqual(sorted(wins), [False, True])
        self.assertFalse(Journal(self.path).claim('task-1', self.sha, 'changed'))
        self.assertEqual(self.journal.get('task-1', self.sha)['snapshot'], 'snapshot')

    def test_subprocess_cannot_reclaim_running(self):
        self.assertTrue(self.journal.claim('task-1', self.sha, 'snapshot'))
        code = ('from task_tower.postmerge_journal import Journal; import sys; '
                'print(Journal(sys.argv[1]).claim("task-1", sys.argv[2], "other"))')
        result = subprocess.run([sys.executable, '-c', code, str(self.path), self.sha],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), 'False')

    def test_review_is_durable_and_never_reclaimed(self):
        self.journal.claim('task-1', self.sha, 'snapshot')
        review = {'verdict': 'approve', 'summary': 'Готово', 'findings': []}
        self.journal.save_review('task-1', self.sha, review)
        restarted = Journal(self.path)
        self.assertEqual(restarted.get('task-1', self.sha)['result'], review)
        self.assertFalse(restarted.claim('task-1', self.sha, 'other'))
        restarted.finish('task-1', self.sha, 'done')
        self.assertFalse(restarted.claim('task-1', self.sha, 'other'))
        self.assertEqual(restarted.rows()[0]['status'], 'done')

    def test_explicit_retry_required_for_needs_input(self):
        self.journal.claim('task-1', self.sha, 'snapshot')
        with self.assertRaises(ValueError):
            self.journal.retry('task-1', self.sha)
        self.journal.finish('task-1', self.sha, 'needs_input', 'changed card')
        self.assertFalse(self.journal.claim('task-1', self.sha, 'new'))
        self.journal.retry('task-1', self.sha)
        self.assertTrue(self.journal.claim('task-1', self.sha, 'new'))
        self.assertEqual(self.journal.get('task-1', self.sha)['snapshot'], 'new')
        self.journal.finish('task-1', self.sha, 'done')
        with self.assertRaises(ValueError):
            self.journal.retry('task-1', self.sha)

    def test_waiting_and_blocked_reclaim_but_missing_update_rejected(self):
        self.assertIsNone(self.journal.get('missing', self.sha))
        for status in ('waiting', 'blocked'):
            self.journal.claim('task-1', self.sha, 'snapshot')
            self.journal.finish('task-1', self.sha, status)
            self.assertTrue(self.journal.claim('task-1', self.sha, 'snapshot'))
        with self.assertRaises(ValueError):
            self.journal.finish('missing', self.sha, 'done')
        with self.assertRaises(ValueError):
            self.journal.finish('task-1', self.sha, 'reviewed')
        for task, sha in [('', self.sha), ('task', 'main'), ('x\x00', self.sha)]:
            with self.assertRaises(ValueError):
                self.journal.claim(task, sha, 'snapshot')

    def test_rejects_symlinked_database_parent(self):
        target = Path(self.tmp.name).resolve() / 'target'
        target.mkdir()
        link = target.parent / 'alias'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(ValueError):
            Journal(link / 'journal.sqlite')

    def test_interrupted_running_requires_explicit_stopped_confirmation(self):
        self.journal.claim('task-1', self.sha, 'snapshot')
        restarted = Journal(self.path)
        for confirmation in (False, None, 1, 'yes'):
            with self.assertRaises(ValueError):
                restarted.recover('task-1', self.sha, confirm_stopped=confirmation)
            self.assertEqual(restarted.get('task-1', self.sha)['status'], 'running')
        with self.assertRaises(ValueError):
            restarted.retry('task-1', self.sha)
        restarted.recover('task-1', self.sha, confirm_stopped=True)
        self.assertEqual(restarted.get('task-1', self.sha)['status'], 'waiting')
        self.assertTrue(restarted.claim('task-1', self.sha, 'new snapshot'))
        self.assertFalse(self.journal.claim('task-1', self.sha, 'duplicate'))

    def test_recovery_rejects_missing_and_completed_claims(self):
        with self.assertRaises(ValueError):
            self.journal.recover('missing', self.sha, confirm_stopped=True)
        self.journal.claim('task-1', self.sha, 'snapshot')
        self.journal.finish('task-1', self.sha, 'done')
        with self.assertRaises(ValueError):
            self.journal.recover('task-1', self.sha, confirm_stopped=True)
        self.assertEqual(self.journal.get('task-1', self.sha)['status'], 'done')
