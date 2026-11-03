"""Retained-record prerequisites: genuine own journal identity, never contents."""
import os
import sqlite3
import unittest
from contextlib import closing

import test_pr_context as context_fixtures
from task_tower.pr_journal import APP_ID, SCHEMAS, PRJournal
from task_tower.executor_profiles import profile_fingerprint


class OwnJournalTests(unittest.TestCase):
    # Reuse actual installed-factory fixture, not synthetic provenance.
    setUp=context_fixtures.ContextFactoryTests.setUp
    make=context_fixtures.ContextFactoryTests.make
    write=staticmethod(context_fixtures.ContextFactoryTests.write)

    def initialize(self):
        with PRJournal(self.journal)._db(True):
            pass

    def test_missing_own_journal_is_explicit_and_does_not_create_it(self):
        context=self.make()
        self.assertIsNone(context.private_input_provenance['pr_journal'])
        self.assertFalse(self.journal.exists())

    def test_later_journal_appearance_requires_new_context(self):
        context=self.make()
        self.initialize()
        with self.assertRaises(ValueError):
            context._fresh_inputs()
        fresh=self.make()
        self.assertIsNotNone(fresh.private_input_provenance['pr_journal'])

    def test_actual_schema_and_identity_are_bound_without_content_hash(self):
        self.initialize(); context=self.make()
        info=self.journal.stat()
        self.assertEqual(context.private_input_provenance['pr_journal'],dict(
            path=str(self.journal),device=info.st_dev,inode=info.st_ino,
            application_id=APP_ID,user_version=1,schema_sha256=profile_fingerprint(SCHEMAS)))
        self.assertNotIn(str(self.journal),[f['path'] for f in context.private_input_provenance['files']])

    def test_normal_journal_writes_keep_context_current(self):
        self.initialize(); context=self.make(); before=context.private_inputs_sha256
        with PRJournal(self.journal).owner('00000000-0000-4000-8000-000000000042'):
            context._fresh_inputs()
            self.assertEqual(context.private_inputs_sha256,before)
        context._fresh_inputs()

    def test_same_byte_journal_replacement_is_refused(self):
        self.initialize(); context=self.make(); raw=self.journal.read_bytes()
        self.journal.rename(self.root/'retained-pr.db'); self.journal.write_bytes(raw)
        with self.assertRaises(ValueError): context._fresh_inputs()

    def test_existing_nonjournal_is_refused_without_modification(self):
        self.journal.write_bytes(b'not a journal')
        with self.assertRaises(ValueError): self.make()
        self.assertEqual(self.journal.read_bytes(),b'not a journal')

    def test_schema_change_is_refused_and_never_repaired(self):
        self.initialize(); context=self.make()
        with closing(sqlite3.connect(self.journal)) as db:
            db.execute('CREATE TABLE alien(value)'); db.commit()
        raw=self.journal.read_bytes()
        with self.assertRaises(ValueError): context._fresh_inputs()
        self.assertEqual(self.journal.read_bytes(),raw)

    def test_genuine_schema_with_invalid_rows_is_refused(self):
        self.initialize()
        with closing(sqlite3.connect(self.journal)) as db:
            db.execute("INSERT INTO owners VALUES(?,?,?)",('invalid-uuid',os.getpid(),'active'))
            db.commit()
        with self.assertRaises(ValueError): self.make()
