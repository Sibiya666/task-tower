import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from task_tower import tasks
from task_tower.postmerge_worker import Worker


class FetchBudgetTests(unittest.TestCase):
    def worker(self):
        worker = Worker.__new__(Worker)
        worker.project = Path('fixture')
        worker.repository = 'owner/repo'
        return worker

    def test_only_remote_fetch_has_network_budget(self):
        with patch.object(tasks, '_git', side_effect=['https://github.com/owner/repo.git', '']) as git:
            self.worker()._refresh()
        self.assertEqual(git.call_args_list[0].kwargs, {})
        self.assertEqual(git.call_args_list[1].args[1:], ('fetch', 'origin', 'main'))
        self.assertEqual(git.call_args_list[1].kwargs, {'timeout': 60})

    def test_local_git_keeps_ten_seconds_and_explicit_fetch_uses_sixty(self):
        with patch.object(subprocess, 'run', return_value=Mock(stdout='ok\n')) as run:
            self.assertEqual(tasks._git(Path('fixture'), 'rev-parse', 'HEAD'), 'ok')
            self.assertEqual(run.call_args.kwargs['timeout'], 10)
            tasks._git(Path('fixture'), 'fetch', 'origin', 'main', timeout=60)
            self.assertEqual(run.call_args.kwargs['timeout'], 60)
            self.assertTrue(run.call_args.kwargs['check'])

    def test_refresh_failure_never_polls_or_reviews(self):
        for error in (subprocess.TimeoutExpired(['git'], 60),
                      subprocess.CalledProcessError(128, ['git'])):
            with self.subTest(error=type(error).__name__):
                worker = self.worker()
                worker.source = Mock()
                worker.reviewer = Mock()
                worker.refresh = worker._refresh
                with patch.object(subprocess, 'run', side_effect=[Mock(stdout='https://github.com/owner/repo.git\n'), error]):
                    with self.assertRaisesRegex(ValueError, 'Git validation failed: fetch origin main'):
                        worker.once()
                worker.source.poll.assert_not_called()
                worker.reviewer.review.assert_not_called()

    def test_wrong_origin_stops_before_fetch(self):
        with patch.object(tasks, '_git', return_value='https://github.com/other/repo.git') as git:
            with self.assertRaisesRegex(ValueError, 'origin does not match'):
                self.worker()._refresh()
        self.assertEqual(git.call_count, 1)
