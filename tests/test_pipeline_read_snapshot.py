"""Concurrent publication must not split journal validation across snapshots."""
import threading
import unittest
from task_tower import pipeline_journal as journal
from tests.test_pipeline_journal import JournalFixture, request, policy


class ReadSnapshotTests(JournalFixture, unittest.TestCase):
    def test_concurrent_submit_cannot_create_apparent_orphan_event(self):
        self.journal.submit(request(1), policy())
        published = threading.Event()
        finished = threading.Event()
        errors = []
        path = self.path

        class Writer(journal.PipelineJournal):
            @staticmethod
            def _event(db, run_id, kind, *args, **kwargs):
                journal.PipelineJournal._event(db, run_id, kind, *args, **kwargs)
                if kind == 'submitted':
                    published.set()

        def submit():
            try:
                Writer(path).submit(request(2), policy())
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

        worker = threading.Thread(target=submit)

        class Reader(journal.PipelineJournal):
            def _validate_db(self, db):
                class BetweenTables:
                    def execute(self, sql, *args):
                        if sql == 'SELECT * FROM attempts':
                            worker.start()
                            if not published.wait(5):
                                raise AssertionError('writer did not publish its transaction')
                            # Autocommit permits the writer to finish here. A
                            # read snapshot holds its commit until this read ends.
                            finished.wait(.25)
                        return db.execute(sql, *args)
                return super()._validate_db(BetweenTables())

        try:
            rows = Reader(path).status()['runs']
        finally:
            if worker.ident is not None:
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(self.journal.status()['runs']), 2)
