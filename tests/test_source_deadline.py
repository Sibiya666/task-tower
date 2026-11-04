"""An original collection deadline is shared across requests, never renewed."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from task_tower.github_tasks import GitHubTasks,GitHubRequestError


class SourceDeadlineTests(unittest.TestCase):
    def test_expiry_after_response_prevents_next_request(self):
        from task_tower.source_deadline import source_deadline
        now=[10.0];calls=[]
        def transport(*args):
            calls.append(args);now[0]=12.0
            return b'[]'
        store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
        with patch('task_tower.source_deadline.time.monotonic',side_effect=lambda:now[0]),self.assertRaises(ValueError),source_deadline(11.0):
            with self.assertRaises((ValueError,GitHubRequestError)):store.request('GET','/issues')
            with self.assertRaises((ValueError,GitHubRequestError)):store.request('GET','/issues')
        self.assertEqual(len(calls),1)

    def test_nested_scope_cannot_extend_original_deadline(self):
        from task_tower.source_deadline import source_deadline,remaining
        with patch('task_tower.source_deadline.time.monotonic',return_value=10.0):
            with source_deadline(12.0):
                self.assertEqual(remaining(30),2)
                with source_deadline(100.0):self.assertEqual(remaining(30),2)
            self.assertEqual(remaining(30),30)
