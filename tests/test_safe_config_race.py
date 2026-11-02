"""No-follow path observations remain valid when SQLite removes a sidecar."""
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from task_tower.pipeline_journal import PipelineJournal
from task_tower.project_connections import safe_config_path


class SafeConfigRaceTests(unittest.TestCase):
    def test_actual_journal_sidecar_disappears_after_positive_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'pipeline.sqlite3'
            journal = PipelineJournal(path)
            sidecar = Path(str(path) + '-journal')
            sidecar.write_bytes(b'ordinary transient sidecar')
            original_lstat, original_exists = Path.lstat, Path.exists
            removed = []

            def observe_lstat(candidate, *args, **kwargs):
                info = original_lstat(candidate, *args, **kwargs)
                if candidate == sidecar and not removed:
                    # Old guard next calls exists(); let it observe the file.
                    observed.append(True)
                return info

            def observe_exists(candidate, *args, **kwargs):
                exists = original_exists(candidate, *args, **kwargs)
                if candidate == sidecar and exists and observed and not removed:
                    sidecar.unlink()
                    removed.append(True)
                return exists

            observed = []
            with patch.object(Path, 'lstat', observe_lstat), patch.object(Path, 'exists', observe_exists):
                journal._safe()
            self.assertTrue(observed)
            # The corrected guard need not call exists; delete after its lstat
            # in the companion regression below to cover that implementation.

    def test_actual_journal_sidecar_deleted_after_lstat(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'pipeline.sqlite3'
            journal = PipelineJournal(path)
            sidecar = Path(str(path) + '-journal'); sidecar.touch()
            original = Path.lstat
            removed = []
            def observe(candidate, *args, **kwargs):
                info = original(candidate, *args, **kwargs)
                if candidate == sidecar and not removed:
                    sidecar.unlink(); removed.append(True)
                return info
            with patch.object(Path, 'lstat', observe):
                journal._safe()
            self.assertEqual(removed, [True])

    def test_observed_directory_remains_rejected_after_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'directory'; path.mkdir()
            original = Path.lstat
            def observe(candidate, *args, **kwargs):
                info = original(candidate, *args, **kwargs)
                if candidate == path:
                    path.rmdir()
                return info
            with patch.object(Path, 'lstat', observe), self.assertRaises(ValueError):
                safe_config_path(path)

    def test_leaf_deleted_immediately_after_lstat_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'config.json'
            path.write_text('{}', encoding='utf-8')
            original = Path.lstat
            def observe(candidate, *args, **kwargs):
                info = original(candidate, *args, **kwargs)
                if candidate == path and path.exists():
                    path.unlink()
                return info
            with patch.object(Path, 'lstat', observe):
                self.assertEqual(safe_config_path(path), path)

    def test_main_regular_missing_and_directory_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / 'config.json'
            self.assertEqual(safe_config_path(path), path)
            path.write_text('{}', encoding='utf-8')
            self.assertEqual(safe_config_path(path), path)
            with self.assertRaises(ValueError):
                safe_config_path(root)

    def test_leaf_and_ancestor_symlinks_stay_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'target'; target.mkdir()
            link = root / 'link'
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest('symlink creation unavailable')
            for candidate in (link, link / 'missing.json'):
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    safe_config_path(candidate)

    def test_journal_hardlink_stays_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / 'pipeline.sqlite3'; path.touch()
            os.link(path, root / 'alias')
            with self.assertRaises(ValueError):
                PipelineJournal(path)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction control')
    def test_real_junction_leaf_and_ancestor_stay_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'target'; target.mkdir()
            link = root / 'junction'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                           check=True, capture_output=True)
            try:
                for candidate in (link, link / 'missing.json'):
                    with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                        safe_config_path(candidate)
                original = Path.lstat
                def observe(candidate, *args, **kwargs):
                    info = original(candidate, *args, **kwargs)
                    if candidate == link:
                        link.rmdir()
                    return info
                with patch.object(Path, 'lstat', observe), self.assertRaises(ValueError):
                    safe_config_path(link)
            finally:
                if link.exists():
                    link.rmdir()
