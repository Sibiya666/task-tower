import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from task_tower import tasks


class TaskTests(unittest.TestCase):
    def test_visible_postmerge_states_do_not_mean_done(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        sha = self.git('rev-parse', 'HEAD')
        for state, expected in [('pending', 'awaiting_postmerge'), ('reviewing', 'postmerge_review'),
                                ('failed', 'postmerge_failed'), ('needs_input', 'needs_input')]:
            card = tasks.update_postmerge_state(self.card, state, sha, 'detail')
            self.assertEqual(card['status'], expected)
            self.assertEqual(tasks.load_task(self.card)['status'], expected)
        self.assertNotEqual(card['status'], 'done')

    def test_remote_main_acceptance_is_pinned_and_revalidated(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        sha = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/remotes/origin/main', sha)
        card = tasks.accept_task(self.card, 'postmerge', 'reviewer', self.evidence,
                                 sha, main_ref='refs/remotes/origin/main')
        self.assertEqual(card['status'], 'done')
        self.assertEqual(card['stages']['postmerge']['main_ref'], 'refs/remotes/origin/main')
        self.git('update-ref', '-d', 'refs/remotes/origin/main')
        with self.assertRaises(ValueError):
            tasks.load_task(self.card)

    def test_postmerge_state_does_not_bypass_stale_evidence(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        self.evidence.write_text('changed')
        with self.assertRaises(ValueError):
            tasks.update_postmerge_state(self.card, 'reviewing', self.git('rev-parse', 'HEAD'), '')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # System temp aliases are not the symlinks under test.
        self.root = Path(self.temp.name).resolve()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.card = self.root / 'docs' / 'tasks' / 'task.json'
        self.card.parent.mkdir(parents=True)
        self.card.write_text(json.dumps({'version': 1, 'id': 'T-1', 'project_root': '../..', 'executor': 'executor', 'stages': {}, 'status': 'in_progress'}))
        self.evidence = self.root / 'evidence.txt'
        self.evidence.write_text('reviewed')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()

    def accept(self, stage):
        return tasks.accept_task(self.card, stage, 'reviewer', self.evidence)

    def test_accept_persists_relative_evidence_and_hash(self):
        result = self.accept('spec')
        self.assertEqual(result['stages']['spec']['evidence'], '../../evidence.txt')
        self.assertEqual(result['stages']['spec']['status'], 'accepted')
        self.assertEqual(len(result['stages']['spec']['sha256']), 64)
        self.assertEqual(tasks.load_task(self.card), result)

    def test_text_acceptance_survives_git_crlf_checkout_but_rejects_edits(self):
        self.git('config', 'core.autocrlf', 'false')
        self.evidence.write_bytes(b'reviewed\nsecond line\n')
        accepted = self.accept('spec')
        self.git('add', '.')
        self.git('commit', '-m', 'accepted LF evidence')
        self.git('config', 'core.autocrlf', 'true')
        self.evidence.unlink()
        self.git('checkout', '--', 'evidence.txt')
        self.assertEqual(self.evidence.read_bytes(), b'reviewed\r\nsecond line\r\n')
        self.assertEqual(tasks.load_task(self.card), accepted)
        self.evidence.write_bytes(b'reviewed\r\nchanged line\r\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            tasks.load_task(self.card)

    def test_new_text_acceptance_records_versioned_normalized_digest(self):
        self.evidence.write_bytes(b'reviewed\r\n')
        record = self.accept('spec')['stages']['spec']
        self.assertEqual(record['hash_scheme'], 'sha256-utf8-lf-v1')
        self.assertEqual(record['sha256'], hashlib.sha256(b'reviewed\n').hexdigest())

    def test_legacy_acceptance_remains_byte_strict(self):
        self.evidence.write_bytes(b'reviewed\n')
        card = self.accept('spec')
        record = card['stages']['spec']
        record.pop('hash_scheme', None)
        record['sha256'] = hashlib.sha256(self.evidence.read_bytes()).hexdigest()
        self.card.write_text(json.dumps(card))
        tasks.load_task(self.card)
        self.evidence.write_bytes(b'reviewed\r\n')
        with self.assertRaisesRegex(ValueError, 'stale'):
            tasks.load_task(self.card)

    def test_binary_acceptance_preserves_bytes(self):
        for content in (b'\xff\r\n', b'\x00binary\r\n'):
            with self.subTest(content=content):
                self.evidence.write_bytes(content)
                record = self.accept('spec')['stages']['spec']
                self.assertEqual(record['hash_scheme'], 'sha256')
                self.assertEqual(record['sha256'], hashlib.sha256(content).hexdigest())
                self.evidence.write_bytes(content.replace(b'\r\n', b'\n'))
                with self.assertRaisesRegex(ValueError, 'stale'):
                    tasks.load_task(self.card)

    def test_unknown_hash_scheme_fails_closed(self):
        card = self.accept('spec')
        card['stages']['spec']['hash_scheme'] = 'unknown-v99'
        self.card.write_text(json.dumps(card))
        with self.assertRaises(ValueError):
            tasks.load_task(self.card)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction')
    def test_rejects_junction_card_without_pathlib312_detector(self):
        alias = self.root / 'aliased-tasks'
        target = self.card.parent.resolve()
        created = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(alias), str(target)],
                                 capture_output=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        try:
            with patch.object(Path, 'is_junction', return_value=False, create=True):
                with self.assertRaisesRegex(ValueError, 'symlink|junction|reparse'):
                    tasks.load_task(alias / self.card.name)
        finally:
            os.rmdir(alias)

    def test_cannot_skip_or_self_accept(self):
        with self.assertRaises(ValueError):
            self.accept('development')
        with self.assertRaises(ValueError):
            tasks.accept_task(self.card, 'spec', 'executor', self.evidence)

    def test_changed_or_missing_prior_evidence_blocks_progress(self):
        self.accept('spec')
        self.evidence.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.accept('development')
        with self.assertRaisesRegex(ValueError, 'stale'):
            tasks.load_task(self.card)
        self.evidence.unlink()
        with self.assertRaises(ValueError):
            self.accept('development')

    def test_reaccept_repairs_stage_and_invalidates_downstream(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        self.evidence.write_text('new review')
        result = self.accept('spec')
        self.assertEqual(result['status'], 'in_progress')
        self.assertEqual(result['stages']['development']['status'], 'pending')
        self.assertEqual(result['stages']['test']['status'], 'pending')

    def test_postmerge_requires_commit_on_main(self):
        for stage in ('spec', 'development', 'test'):
            result = self.accept(stage)
        self.assertEqual(result['status'], 'awaiting_merge')
        with self.assertRaises(ValueError):
            self.accept('postmerge')
        self.git('checkout', '-b', 'feature')
        (self.root / 'feature').write_text('new')
        self.git('add', 'feature')
        self.git('commit', '-m', 'feature')
        commit = self.git('rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            tasks.accept_task(self.card, 'postmerge', 'reviewer', self.evidence, commit)
        self.git('checkout', 'main')
        self.git('merge', '--ff-only', 'feature')
        result = tasks.accept_task(self.card, 'postmerge', 'reviewer', self.evidence, commit)
        self.assertEqual(result['status'], 'done')
        self.assertEqual(result['stages']['postmerge']['commit'], commit)

    def test_postmerge_rejects_absent_main(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        commit = self.git('rev-parse', 'HEAD')
        self.git('branch', '-m', 'other')
        with self.assertRaises(ValueError):
            tasks.accept_task(self.card, 'postmerge', 'reviewer', self.evidence, commit)

    def test_evidence_outside_repo_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            evidence = Path(other) / 'review.txt'
            evidence.write_text('review')
            with self.assertRaises(ValueError):
                tasks.accept_task(self.card, 'spec', 'reviewer', evidence)

    def test_atomic_save_does_not_truncate_hardlinked_card(self):
        alias = self.root / 'alias.json'
        os.link(self.card, alias)
        original = alias.read_bytes()
        self.accept('spec')
        self.assertEqual(alias.read_bytes(), original)

    def test_unknown_stage_and_bad_version_rejected(self):
        with self.assertRaises(ValueError):
            self.accept('unknown')
        data = json.loads(self.card.read_text())
        data['version'] = 2
        self.card.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            tasks.load_task(self.card)

    def test_done_card_requires_valid_postmerge_commit_and_current_main(self):
        for stage in ('spec', 'development', 'test'):
            self.accept(stage)
        commit = self.git('rev-parse', 'HEAD')
        tasks.accept_task(self.card, 'postmerge', 'reviewer', self.evidence, commit)
        done = json.loads(self.card.read_text())
        del done['stages']['postmerge']['commit']
        self.card.write_text(json.dumps(done))
        with self.assertRaises(ValueError):
            tasks.load_task(self.card)
        done['stages']['postmerge']['commit'] = commit
        self.card.write_text(json.dumps(done))
        self.git('branch', '-m', 'other')
        with self.assertRaises(ValueError):
            tasks.load_task(self.card)
        # Reopening an earlier stage repairs a card even when old main vanished.
        reopened = self.accept('spec')
        self.assertEqual(reopened['status'], 'in_progress')
