import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


class OverlayBooksTests(unittest.TestCase):
    def module(self):
        from task_tower import overlay_books
        return overlay_books

    def test_missing_config_is_unconfigured_without_transport(self):
        module = self.module()
        with patch.object(module, 'aggregate', side_effect=AssertionError('transport')):
            self.assertEqual(module.snapshot(None)['state'], 'unconfigured')

    def test_partial_updates_precede_final_and_private_fields_are_absent(self):
        module = self.module()
        row = dict(id='owner/repo#1', repository='owner/repo', number=1,
                   project='p', book='tasks', title='Issue', source='https://github.com/owner/repo/issues/1',
                   status='open', verification='pending', token='SECRET', checkout='PRIVATE')
        def aggregate(connections, include_library, on_update):
            report = dict(fetched_at='2026-11-01T00:00:00Z', entries=[row], errors=[])
            on_update(report)
            self.assertEqual(len(updates), 1)
            self.assertEqual(updates[0]['state'], 'partial')
            return dict(report, errors=[dict(project='p', source=row['source'], error='Verification unavailable')])
        updates = []
        with patch.object(module, 'load_connections', return_value=[object()]), patch.object(module, 'aggregate', aggregate):
            result = module.snapshot(Path('config.json'), on_update=updates.append)
        self.assertEqual(result['state'], 'partial')
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('token', result['entries'][0])

    def test_main_flushes_first_update_and_reserves_final_with_many_updates(self):
        module = self.module()
        output = io.StringIO()
        def snapshot(path, on_update):
            frame = dict(kind='books', version=1, state='partial', fetched_at=None, entries=[], errors=[])
            for _ in range(100): on_update(frame)
            self.assertTrue(output.getvalue().endswith('\n'))
            return dict(frame, state='ready')
        with patch.object(module, 'snapshot', snapshot), patch.object(module.sys, 'stdout', output):
            self.assertEqual(module.main([]), 0)
        frames = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertGreaterEqual(len(frames), 2)
        self.assertLessEqual(len(frames), 32)
        self.assertEqual([f['sequence'] for f in frames], list(range(1, len(frames)+1)))
        self.assertFalse(frames[0]['final'])
        self.assertTrue(frames[-1]['final'])

    def test_snapshot_caps_fail_visibly_without_silent_truncation(self):
        module = self.module()
        for rows in ([{}] * 10001, [dict(description='x' * (8*1024*1024))]):
            with self.subTest(entries=len(rows)), patch.object(module, 'load_connections', return_value=[object()]), patch.object(module, 'aggregate', return_value=dict(entries=rows, errors=[], fetched_at=None)):
                result = module.snapshot(Path('config.json'))
                self.assertEqual(result['state'], 'unavailable')
                self.assertTrue(result['errors'])
                self.assertLess(len(json.dumps(result)), 8192)

    def test_canonical_connections_projection_publishes_before_blocked_verifier(self):
        module = self.module()
        from task_tower.books import aggregate as real_aggregate
        from task_tower.github_tasks import replace_metadata
        from tests.test_book_projection import Store
        body = replace_metadata('Public description', dict(version=1, kind='task', status='done'))
        store = Store(dict(number=1, title='Actual fixture', body=body, state='closed'))
        entered, release = threading.Event(), threading.Event()
        frames, final = [], []
        def proof(*args):
            entered.set()
            if not release.wait(5): raise AssertionError('proof barrier timeout')
            return True
        def aggregate(connections, include_library, on_update):
            return real_aggregate(connections, lambda c: store, include_library, on_update=on_update)
        with tempfile.TemporaryDirectory(prefix='books config Р® ') as directory:
            path = Path(directory) / 'private connections.json'
            path.write_text(json.dumps(dict(version=1, projects=[dict(id='p',repository='a/b',checkout=directory,runner_label='local')])), encoding='utf-8')
            with patch.object(module, 'aggregate', aggregate), patch('task_tower.project_worker.issue_lifecycle', return_value=dict(version=1,kind='task',status='done')), patch('task_tower.project_worker.verified_done', side_effect=proof):
                thread = threading.Thread(target=lambda: final.append(module.snapshot(path, on_update=frames.append)))
                thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertTrue(thread.is_alive())
                    self.assertEqual({r['book'] for r in frames[-1]['entries']}, {'tasks', 'library'})
                    self.assertEqual(frames[-1]['entries'][0]['verification'], 'pending')
                    self.assertNotIn(directory, json.dumps(frames))
                finally:
                    release.set(); thread.join(5)
                self.assertEqual(final[0]['state'], 'ready')
                self.assertEqual(final[0]['entries'][0]['verification'], 'verified')

    def test_stream_budget_coalesces_updates_and_preserves_first_and_final(self):
        module = self.module()
        output = io.StringIO()
        def snapshot(path, on_update):
            frame = dict(kind='books',version=1,state='partial',fetched_at=None,entries=[dict(description='x'*400)],errors=[])
            on_update(frame)
            self.assertIn('"sequence":1', output.getvalue())
            for _ in range(100): on_update(frame)
            return dict(frame, state='ready')
        with patch.object(module,'snapshot',snapshot), patch.object(module,'FRAME_LIMIT',1024), patch.object(module,'STREAM_LIMIT',4096), patch.object(module.sys,'stdout',output):
            self.assertEqual(module.main([]),0)
        self.assertLessEqual(len(output.getvalue().encode()),4096)
        frames=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertTrue(frames[-1]['final'])
        self.assertLess(len(frames),32)

    def test_invalid_private_configuration_never_serializes_exception(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'; path.write_text('{"token":"SECRET"}',encoding='utf-8')
            with patch.object(module,'aggregate',side_effect=AssertionError('transport')):
                value=module.snapshot(path)
            self.assertEqual(value['state'],'unavailable')
            self.assertNotIn('SECRET',json.dumps(value))
            self.assertNotIn(directory,json.dumps(value))




    def test_real_aggregate_migration_survives_public_helper_without_private_registry(self):
        from tests.books_overlay_fixture import projection
        value = projection()
        self.assertIn('migrations', value['entries'][0])
        migration = value['entries'][0]['migrations'][0]
        self.assertEqual(set(migration), {'number', 'source_sha256', 'status', 'issue_url'})
        self.assertEqual(migration['status'], 'current')
        self.assertEqual(len(migration['source_sha256']), 64)
        self.assertNotIn('PRIVATE', json.dumps(value))

    def test_migration_boundary_excludes_unknown_nested_keys_and_bounds_records(self):
        module = self.module()
        row = dict(migrations=[dict(number=1, source_sha256='a'*64, status='current', issue_url='https://github.com/a/b/issues/1', source_path='PRIVATE', token='SECRET')])
        report = dict(entries=[row], errors=[], fetched_at=None)
        public = module._public(report)['entries'][0]
        self.assertIn('migrations', public)
        migration = public['migrations'][0]
        self.assertEqual(set(migration), {'number', 'source_sha256', 'status', 'issue_url'})
        self.assertNotIn('PRIVATE', json.dumps(migration))
        for bad in ([row['migrations'][0]]*101, [dict(row['migrations'][0], source_sha256='bad')]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                module._public(dict(report, entries=[dict(migrations=bad)]))


if __name__ == '__main__': unittest.main()
