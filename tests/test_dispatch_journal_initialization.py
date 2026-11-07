"""Regression tests for journal creation ordering and consistent reads."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from task_tower.dispatch_delivery import DeliveryJournal


class InitializationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / 'journal.db'

    def initialize(self, journal=None):
        journal = journal or DeliveryJournal(self.path)
        self.assertTrue(callable(getattr(journal, 'initialize', None)), 'journal has no safe explicit initialization')
        return journal.initialize()

    def files(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def test_new_schema_is_committed_before_return_and_repeat_is_readonly(self):
        self.initialize()
        self.assertEqual(DeliveryJournal(self.path, readonly=True).rows(), [])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0], 1414808644)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], 'delete')
        before = self.files()
        self.initialize()
        self.assertEqual(self.files(), before)

    def test_existing_empty_is_never_adopted(self):
        self.path.touch()
        before = self.files()
        self.assertTrue(callable(getattr(DeliveryJournal(self.path), 'initialize', None)), 'missing initializer')
        with self.assertRaises(ValueError): self.initialize()
        self.assertEqual(self.files(), before)

    def test_existing_foreign_schema_is_never_changed(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE foreign_data(value)')
            db.execute("INSERT INTO foreign_data VALUES('preserve')")
            db.commit()
        before = self.files()
        self.assertTrue(callable(getattr(DeliveryJournal(self.path), 'initialize', None)), 'missing initializer')
        with self.assertRaises(ValueError): self.initialize()
        self.assertEqual(self.files(), before)

    def test_readonly_initializer_cannot_create(self):
        self.assertTrue(callable(getattr(DeliveryJournal(self.path), 'initialize', None)), 'missing initializer')
        with self.assertRaises(ValueError): self.initialize(DeliveryJournal(self.path, readonly=True))
        self.assertFalse(self.path.exists())

    def test_replaced_path_cannot_receive_sqlite_writes_or_sidecars(self):
        foreign = self.root / 'foreign.db'
        with closing(sqlite3.connect(foreign)) as db:
            db.execute('CREATE TABLE secrets(value)')
            db.execute("INSERT INTO secrets VALUES('unchanged')")
            db.commit()
        original_bytes = foreign.read_bytes()
        real_open = os.open
        redirected = []
        def redirect_at_create(target,flags,*args,**kwargs):
            # Model a pathname swap at the create/open boundary. Actual Windows
            # CRT descriptors deny rename while open; never relax that sharing.
            fd = real_open(self.root/'owned-moved.db',flags,*args,**kwargs)
            os.replace(foreign,self.path)
            redirected.append(True)
            return fd
        self.assertTrue(callable(getattr(DeliveryJournal(self.path), 'initialize', None)), 'missing initializer')
        with patch('task_tower.dispatch_delivery.os.open', side_effect=redirect_at_create):
            with self.assertRaises(ValueError): self.initialize()
        self.assertEqual(redirected, [True])
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertFalse(any(self.root.glob('*-journal')))
        self.assertFalse(any(self.root.glob('*-wal')))
        self.assertFalse(any(self.root.glob('*-shm')))

    def test_creation_race_never_adopts_existing_empty(self):
        real_open=os.open
        def existing_empty(target,flags,*args,**kwargs):
            other=real_open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(other)
            return real_open(target,flags,*args,**kwargs)
        with patch('task_tower.dispatch_delivery.os.open',side_effect=existing_empty):
            with self.assertRaises(ValueError):self.initialize()
        self.assertEqual(self.path.read_bytes(),b'')

    def test_failed_partial_write_is_preserved_and_restart_fails_closed(self):
        with patch('task_tower.dispatch_delivery.os.write',return_value=0):
            with self.assertRaises(ValueError):self.initialize()
        self.assertEqual(self.path.read_bytes(),b'')
        before=self.files()
        with self.assertRaises(ValueError):self.initialize()
        self.assertEqual(self.files(),before)

    def test_existing_wrong_version_and_constraints_are_unchanged(self):
        for sql in ('PRAGMA user_version=2','ALTER TABLE metadata RENAME TO foreign_metadata'):
            with self.subTest(sql=sql):
                if self.path.exists():self.path.unlink()
                self.initialize()
                with closing(sqlite3.connect(self.path)) as db:
                    db.execute(sql);db.commit()
                before=self.files()
                with self.assertRaises(ValueError):self.initialize()
                self.assertEqual(self.files(),before)

    def test_reparse_path_is_rejected_without_writing_target(self):
        target=self.root/'target.db';target.write_bytes(b'preserve')
        try:os.symlink(target,self.path)
        except OSError as error:self.skipTest('symlink unavailable: '+str(error.winerror if hasattr(error,'winerror') else error.errno))
        before=target.read_bytes()
        with self.assertRaises(ValueError):self.initialize()
        self.assertEqual(target.read_bytes(),before)

    def test_initializer_never_opens_path_sqlite_for_writing(self):
        connect = sqlite3.connect
        def guarded(target, *args, **kwargs):
            self.assertTrue(target == ':memory:' or (kwargs.get('uri') and 'mode=ro' in str(target)),
                            'initializer opened a pathname for SQLite writes')
            return connect(target, *args, **kwargs)
        with patch('task_tower.dispatch_delivery.sqlite3.connect', side_effect=guarded):
            self.initialize()

    def test_hardlink_and_forbidden_path_are_rejected_without_changes(self):
        self.initialize()
        alias = self.root / 'alias.db'
        os.link(self.path, alias)
        before = self.files()
        with self.assertRaises(ValueError): DeliveryJournal(self.path).initialize()
        self.assertEqual(self.files(), before)
        alias.unlink()
        with self.assertRaises(ValueError): DeliveryJournal(self.path, forbidden_paths=[self.path]).initialize()

    def test_wal_is_rejected_without_changing_database_or_sidecars(self):
        self.initialize()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute("INSERT INTO metadata VALUES('lookup_cursor','[\"owner/repo\",1]')")
            db.commit()
            before = self.files()
            with self.assertRaises(ValueError): self.initialize()
            self.assertEqual(self.files(), before)

    def test_fsync_failure_preserves_bytes_and_restart_only_validates(self):
        self.assertTrue(callable(getattr(DeliveryJournal(self.path), 'initialize', None)), 'missing initializer')
        with patch('task_tower.dispatch_delivery.os.fsync', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(ValueError): self.initialize()
        self.assertTrue(self.path.exists())
        # Unknown bytes are retained, never deleted or silently initialized.
        before = self.files()
        # A fully written valid image may validate; either outcome must be read-only.
        try: self.initialize()
        except ValueError: pass
        self.assertEqual(self.files(), before)


class SnapshotTests(unittest.TestCase):
    def test_schema_reads_cannot_mix_snapshots_across_writer_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'journal.db'
            DeliveryJournal(path).reserve(dict(repository='Owner/Repo', issue=1, task_id='TT-ONE'), 'a' * 64)
            reader_ready, writer_staged, writer_done = threading.Event(), threading.Event(), threading.Event()
            errors = []
            connect = sqlite3.connect
            def writer():
                try:
                    if not reader_ready.wait(5): raise TimeoutError('reader barrier')
                    with closing(connect(path, timeout=5)) as db:
                        db.execute('BEGIN IMMEDIATE')
                        db.execute('PRAGMA user_version=2')
                        writer_staged.set()
                        db.commit()
                except BaseException as error: errors.append(error)
                finally: writer_done.set()
            class Reader(sqlite3.Connection):
                def execute(self, sql, *args, **kwargs):
                    cursor = super().execute(sql, *args, **kwargs)
                    if sql == 'PRAGMA application_id':
                        row = cursor.fetchone()
                        cursor.close()
                        reader_ready.set()
                        if not writer_staged.wait(5): raise TimeoutError('writer stage barrier')
                        # Without an explicit transaction the commit can complete now.
                        # With a snapshot, waiting for commit here would deadlock.
                        if not self.in_transaction and not writer_done.wait(5): raise TimeoutError('writer commit barrier')
                        class Fetched:
                            def fetchone(self): return row
                        return Fetched()
                    return cursor
            def reader_connect(target, *args, **kwargs):
                kwargs['factory'] = Reader
                return connect(target, *args, **kwargs)
            worker = threading.Thread(target=writer)
            worker.start()
            try:
                with patch('task_tower.dispatch_delivery.sqlite3.connect', side_effect=reader_connect):
                    rows = DeliveryJournal(path, readonly=True).rows()
                self.assertEqual(len(rows), 1)
            finally:
                reader_ready.set()
                worker.join(7)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            with self.assertRaises(ValueError): DeliveryJournal(path, readonly=True).rows()
