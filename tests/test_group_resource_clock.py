"""Clock fault injection is not a sample supplier or process-reboot simulation."""
from datetime import timedelta
import unittest
from unittest.mock import patch
from task_tower import group_resources


class GroupResourceClockTests(unittest.TestCase):
    def test_backward_monotonic_clock_refuses_without_advancing_state(self):
        before=group_resources._LAST_MONOTONIC
        with patch('task_tower.group_resources.time.monotonic_ns',return_value=before-1),self.assertRaises(ValueError):
            group_resources._collector_clock()
        self.assertEqual(group_resources._LAST_MONOTONIC,before)

    def test_backward_wall_clock_refuses_without_advancing_state(self):
        before_mono=group_resources._LAST_MONOTONIC; before_wall=group_resources._LAST_WALL
        with patch('task_tower.group_resources.datetime') as clock:
            clock.now.return_value=before_wall-timedelta(seconds=1)
            with self.assertRaises(ValueError): group_resources._collector_clock()
        self.assertEqual(group_resources._LAST_MONOTONIC,before_mono)
        self.assertEqual(group_resources._LAST_WALL,before_wall)
