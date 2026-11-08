"""Fail-closed cleanup boundaries; the native publication test covers real IO."""
from pathlib import Path
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from task_tower import pipeline_inputs as inputs


def sharing_error():
    error = PermissionError(13, 'fixture sharing violation')
    error.winerror = 32
    return error


class CheckpointCleanupTests(unittest.TestCase):
    def setUp(self):
        self.outer = tempfile.TemporaryDirectory()
        self.addCleanup(self.outer.cleanup)
        self.parent = Path(self.outer.name).resolve()
        self.remove = tempfile.TemporaryDirectory._rmtree

    def test_transient_sharing_violation_requires_guard_and_actual_removal(self):
        guard = Mock()
        directory = inputs._CheckpointDirectory(self.parent, guard)
        calls = []
        def remove(name, **kwargs):
            calls.append(name)
            if len(calls) == 1:
                raise sharing_error()
            return self.remove(name, **kwargs)
        with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=remove):
            directory.cleanup()
        self.assertEqual(len(calls), 2)
        guard.assert_called_once_with()
        self.assertFalse(Path(directory.name).exists())

    def test_other_permission_errors_and_missing_guard_are_not_retried(self):
        for code, guarded in ((None, True), (5, True), (32, False)):
            with self.subTest(code=code, guarded=guarded):
                guard = Mock()
                directory = inputs._CheckpointDirectory(self.parent, guard if guarded else None)
                error = PermissionError(13, 'fixture refused')
                if code is not None:
                    error.winerror = code
                with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=error) as remove:
                    with self.assertRaises(PermissionError):
                        directory.cleanup()
                remove.assert_called_once()
                guard.assert_not_called()
                self.assertTrue(Path(directory.name).is_dir())

    def test_guard_deadline_refusal_prevents_another_delete(self):
        directory = inputs._CheckpointDirectory(self.parent, Mock(side_effect=ValueError('deadline')))
        with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=sharing_error()) as remove:
            with self.assertRaisesRegex(ValueError, 'deadline'):
                directory.cleanup()
        remove.assert_called_once()
        self.assertTrue(Path(directory.name).is_dir())

    def test_persistent_lock_never_starts_cleanup_after_retry_horizon(self):
        now, starts = [0.0], []
        def guard():
            now[0] += 2.0  # A slow guard consumes the retry horizon too.
        def sleep(seconds):
            now[0] += seconds
        def remove(name, **kwargs):
            starts.append(now[0])
            raise sharing_error()
        clock = SimpleNamespace(monotonic=lambda: now[0], sleep=sleep)
        directory = inputs._CheckpointDirectory(self.parent, guard)
        with patch.object(inputs, 'time', clock), \
                patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=remove):
            with self.assertRaises(PermissionError):
                directory.cleanup()
        self.assertGreater(len(starts), 1)
        self.assertTrue(all(value < 5 for value in starts))
        self.assertTrue(Path(directory.name).is_dir())

    def test_replaced_directory_is_not_deleted(self):
        directory = None
        backup = self.parent / 'original'
        def guard():
            path = Path(directory.name)
            path.rename(backup)
            path.mkdir()
            (path / 'replacement.txt').write_bytes(b'preserve')
        directory = inputs._CheckpointDirectory(self.parent, guard)
        with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=sharing_error()) as remove:
            with self.assertRaisesRegex(ValueError, 'Changed checkpoint cleanup directory'):
                directory.cleanup()
        remove.assert_called_once()
        self.assertEqual((Path(directory.name) / 'replacement.txt').read_bytes(), b'preserve')
        self.assertTrue(backup.is_dir())

    def test_reparse_or_symlink_replacement_is_refused(self):
        directory = None
        outside = self.parent / 'outside'
        outside.mkdir()
        (outside / 'preserve.txt').write_bytes(b'preserve')
        def guard():
            path = Path(directory.name)
            path.rename(self.parent / 'original')
            try:
                os.symlink(outside, path, target_is_directory=True)
            except OSError:
                self.skipTest('symlink creation unavailable')
        directory = inputs._CheckpointDirectory(self.parent, guard)
        with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=sharing_error()) as remove:
            with self.assertRaises(ValueError):
                directory.cleanup()
        remove.assert_called_once()
        self.assertEqual((outside / 'preserve.txt').read_bytes(), b'preserve')

    def test_successful_cleanup_retry_preserves_body_exception(self):
        directory = inputs._CheckpointDirectory(self.parent, lambda: None)
        calls = []
        def remove(name, **kwargs):
            calls.append(name)
            if len(calls) == 1:
                raise sharing_error()
            return self.remove(name, **kwargs)
        with patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=remove):
            with self.assertRaisesRegex(RuntimeError, 'body failure'):
                with directory:
                    raise RuntimeError('body failure')
        self.assertFalse(Path(directory.name).exists())
