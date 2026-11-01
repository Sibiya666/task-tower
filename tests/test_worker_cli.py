import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from task_tower.github_source import GitHubSourceError
from task_tower.postmerge_worker import main


class WatchTests(unittest.TestCase):
    def test_watch_retries_network_failure_without_exiting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            skill = root / 'SKILL.md'
            skill.write_text('fixture')
            config = root / 'worker.json'
            config.write_text(json.dumps({'project': str(root), 'repository': 'owner/repo',
                'reviewer': {'kind': 'custom', 'timeout_seconds': 5, 'superpowers': {
                    'path': str(skill), 'sha256': hashlib.sha256(skill.read_bytes()).hexdigest()}}}))
            worker = Mock()
            worker.once.side_effect = [GitHubSourceError('temporary'), []]
            source = Mock(errors=[])
            with patch('task_tower.postmerge_worker.Worker', return_value=worker), \
                 patch('task_tower.postmerge_worker.GitHubSource', return_value=source), \
                 patch('task_tower.postmerge_worker.resolve_token', return_value=None), \
                 patch('task_tower.postmerge_worker.time.sleep', side_effect=[None, KeyboardInterrupt]):
                self.assertEqual(main(['--config', str(config)]), 130)
            self.assertEqual(worker.once.call_count, 2)
