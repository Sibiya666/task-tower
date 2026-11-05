"""Deterministic ancestry-work budget model; no hosted root-cause claim."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from task_tower import executor_queue, pipeline_journal


class PipelineValidationBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name).resolve() / 'synthetic.sqlite3'
        self.journal = pipeline_journal.PipelineJournal(self.path)
        # Real initialized SQLite state, established outside the cost model.
        with self.journal._db(write=True):
            pass
        self.targets = (self.path, *(Path(str(self.path) + suffix)
                                     for suffix in ('-journal', '-wal', '-shm')))

    @contextmanager
    def measured_walks(self):
        milliseconds = [0]
        measurements = dict(walks=dict.fromkeys(self.targets, 0), lstat_count=0)
        original_journal = pipeline_journal.safe_config_path
        original_executor = executor_queue.safe_config_path
        original_lstat = Path.lstat
        # Predeclared 150ms per original journal/sidecar ancestry validation.
        # Eight duplicate walks cost 1.2s; four retained walks cost 0.6s.
        def wrap(original):
            def validate(path):
                result = original(path)
                if result in measurements['walks']:
                    measurements['walks'][result] += 1
                    milliseconds[0] += 150
                return result
            return validate
        def lstat(path, *args, **kwargs):
            measurements['lstat_count'] += 1
            return original_lstat(path, *args, **kwargs)
        clock = SimpleNamespace(monotonic=lambda: milliseconds[0] / 1000)
        # Replace this module's namespace only; never mutate global time.
        with patch.object(pipeline_journal, 'time', clock), \
                patch.object(pipeline_journal, 'safe_config_path', wrap(original_journal)), \
                patch.object(executor_queue, 'safe_config_path', wrap(original_executor)), \
                patch.object(Path, 'lstat', lstat):
            yield measurements, clock

    def test_real_status_fits_original_one_second_budget_with_retained_validation(self):
        with self.measured_walks() as (measurements, clock):
            with self.journal.operation_deadline(clock.monotonic() + 1.0):
                try:
                    result = self.journal.status()
                except ValueError:
                    self.fail('Real status exhausted its original one-second budget after '
                              + str(sum(measurements['walks'].values())) + ' ancestry walks')
                self.assertEqual(result, dict(runs=[], active=0, queued=0, unknown=0))
                self.assertAlmostEqual(self.journal._wait_seconds(), .4)
            self.assertAlmostEqual(clock.monotonic(), .6)

    def test_safe_performs_one_actual_ancestry_walk_for_each_database_path(self):
        with self.measured_walks() as (measurements, clock):
            self.journal._safe()
        self.assertEqual([measurements['walks'][path] for path in self.targets], [1, 1, 1, 1])
        # Each original validator lstat-checks its leaf and every ancestor.
        # This independently measures real traversal work, including missing
        # legitimate sidecars, rather than only counting wrapper entry points.
        self.assertEqual(measurements['lstat_count'], sum(1 + len(path.parents) for path in self.targets))
        self.assertAlmostEqual(clock.monotonic(), .6)

    def test_already_exhausted_original_budget_still_fails_before_validation(self):
        with self.measured_walks() as (measurements, clock):
            with self.journal.operation_deadline(clock.monotonic()):
                with self.assertRaisesRegex(ValueError, 'operation deadline exhausted'):
                    self.journal.status()
        self.assertEqual(sum(measurements['walks'].values()), 0)
        self.assertEqual(measurements['lstat_count'], 0)


if __name__ == '__main__':
    unittest.main()
