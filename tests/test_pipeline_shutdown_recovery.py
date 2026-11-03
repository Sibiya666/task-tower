"""Strict existing-only shutdown recovery never initializes private state."""
import contextlib
import os
import json
import shutil
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from task_tower import pipeline
from task_tower.pipeline_journal import PipelineJournal
from tests.test_pipeline_journal import request,policy


class ExistingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()

    def test_missing_parent_and_database_are_never_created(self):
        path=self.root/'absent'/'state.db';journal=PipelineJournal(path)
        with self.assertRaises(ValueError):journal._recover_existing()
        self.assertFalse(path.parent.exists())

    def test_readonly_pin_holds_identity_without_blocking_writes_or_unlink(self):
        path=self.root/'pinned.db';journal=PipelineJournal(path);journal.submit(request(),policy())
        before_files={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        with journal.operation_deadline(time.monotonic()+4.8),journal._pinned_database() as identity:
            fd=journal._pinned_database_fd
            self.assertFalse(os.get_inheritable(fd));self.assertTrue(os.path.samestat(identity,os.fstat(fd)))
            self.assertEqual(before_files,{p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()})
            with journal._existing_database(identity):
                journal.submit(request(2),policy())
                journal._assert_existing()
                self.assertEqual(len(journal.status()['runs']),2)
                path.unlink();PipelineJournal(path).submit(request(999),policy())
                self.assertFalse(os.path.samestat(os.fstat(fd),path.stat()))
                with self.assertRaises(ValueError):journal._assert_existing()
        with self.assertRaises(OSError):os.fstat(fd)
        self.assertIsNone(getattr(journal,'_pinned_database_fd',None))

    def test_pin_missing_path_does_not_create_parent(self):
        path=self.root/'absent'/'state.db';journal=PipelineJournal(path)
        with journal.operation_deadline(time.monotonic()+4.8),journal._pinned_database() as identity:self.assertIsNone(identity)
        self.assertFalse(path.parent.exists())

    def test_pin_close_failure_propagates_and_preserves_original_body_error(self):
        journal=PipelineJournal(self.root/'close.db');journal.submit(request(),policy())
        close=os.close;closed=[]
        def fail_after_actual_close(fd):closed.append(fd);close(fd);raise OSError('explicit close failure')
        with patch('task_tower.pipeline_journal.os.close',fail_after_actual_close):
            with self.assertRaisesRegex(OSError,'explicit close failure'):
                with journal._pinned_database():pass
        self.assertEqual(len(closed),1)
        original=ValueError('original body failure')
        with patch('task_tower.pipeline_journal.os.close',fail_after_actual_close):
            with self.assertRaises(ValueError) as failure:
                with journal._pinned_database():raise original
        self.assertIs(failure.exception,original);self.assertEqual(len(closed),2)
        self.assertIsNone(getattr(journal,'_pinned_database_fd',None))

    def test_expired_open_budget_closes_actual_owned_pin(self):
        from task_tower import pipeline_journal as module
        journal=PipelineJournal(self.root/'deadline.db');journal.submit(request(),policy())
        clock=[0.0];opened=[];original=module._open_database_pin
        def expire_after_actual_open(path):
            fd=original(path);opened.append(fd);clock[0]=2.0;return fd
        with patch.object(module.time,'monotonic',lambda:clock[0]),patch.object(module,'_open_database_pin',expire_after_actual_open):
            with journal.operation_deadline(1.0),self.assertRaisesRegex(ValueError,'deadline'):
                with journal._pinned_database():pass
        self.assertEqual(len(opened),1)
        with self.assertRaises(OSError):os.fstat(opened[0])

    def test_shutdown_pin_close_failure_never_reports_success(self):
        journal=PipelineJournal(self.root/'shutdown-close.db');journal.submit(request(),policy())
        before=journal.status();state=dict(owner=None,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0)
        close=os.close;closed=[]
        def fail_after_actual_close(fd):closed.append(fd);close(fd);raise OSError('explicit close failure')
        with patch('task_tower.pipeline_journal.os.close',fail_after_actual_close):
            self.assertFalse(pipeline._shutdown({},journal,state))
        self.assertTrue(state['_shutdown_journal_done'].is_set());self.assertEqual(len(closed),1)
        self.assertEqual(before,journal.status())

    def test_normal_shutdown_rejects_replacement_or_deletion_after_read_and_before_writes(self):
        for boundary in ('initial_read','recover','controller_tick','release_controller','final_proof'):
            for replacement in (False,True):
                with self.subTest(boundary=boundary,replacement=replacement):
                    directory=self.root/(boundary+str(replacement));directory.mkdir()
                    journal=PipelineJournal(directory/'state.db');journal.submit(request(),policy())
                    owner=str(uuid.uuid4());journal.claim_controller(owner,'b'*64)
                    alternate=directory/'alternate.db';PipelineJournal(alternate).submit(request(999),policy())
                    state=dict(owner=owner,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0)
                    method={'initial_read':'status','final_proof':'_assert_existing'}.get(boundary,boundary)
                    original=getattr(PipelineJournal,method);mutated=[]
                    def mutate(target):
                        target.path.unlink()
                        if replacement:shutil.copy2(alternate,target.path)
                        mutated.append(True)
                    def observe(target,*args,**kwargs):
                        if target.path!=journal.path:return original(target,*args,**kwargs)
                        if boundary=='initial_read' and not mutated:
                            value=original(target,*args,**kwargs);mutate(target);return value
                        if boundary=='final_proof':
                            caller=sys._getframe(1)
                            if caller.f_code.co_name=='finish_journal' and not mutated:mutate(target)
                        elif not mutated:mutate(target)
                        return original(target,*args,**kwargs)
                    with patch.object(PipelineJournal,method,observe):
                        self.assertFalse(pipeline._shutdown({},journal,state))
                    self.assertEqual(len(mutated),1)
                    if replacement:self.assertEqual(journal.status()['runs'][0]['issue'],999)
                    else:self.assertFalse(journal.path.exists())

    def test_initially_missing_shutdown_keeps_startup_behavior(self):
        path=self.root/'startup'/'state.db';journal=PipelineJournal(path)
        state=dict(owner=None,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0)
        self.assertTrue(pipeline._shutdown({},journal,state))
        self.assertEqual(journal.status()['runs'],[])

    def test_empty_and_foreign_state_never_initialize(self):
        for kind in ('empty_file','empty_sqlite','foreign','malformed'):
            with self.subTest(kind=kind):
                path=self.root/(kind+'.db')
                if kind=='empty_file':path.touch()
                elif kind=='malformed':path.write_bytes(b'not SQLite')
                else:
                    with contextlib.closing(sqlite3.connect(path)) as db:
                        if kind=='foreign':db.execute('CREATE TABLE foreign_state(value)')
                        else:db.execute('VACUUM')
                        db.commit()
                before=path.read_bytes()
                with self.assertRaises(ValueError):PipelineJournal(path)._recover_existing()
                self.assertEqual(before,path.read_bytes())

    def test_existing_database_disappears_before_connect_is_not_recreated(self):
        path=self.root/'state.db';journal=PipelineJournal(path);journal.submit(request(),policy())
        original=journal._safe;calls=[]
        def remove_after_validation():
            original();calls.append(True)
            if len(calls)==2:path.unlink()
        with patch.object(journal,'_safe',remove_after_validation),self.assertRaises(ValueError):journal._recover_existing()
        self.assertFalse(path.exists())

    def test_nonrollback_read_failure_does_not_attempt_recovery(self):
        path=self.root/'empty.db';path.touch();journal=PipelineJournal(path)
        state=dict(owner=None,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0)
        with patch.object(PipelineJournal,'_recover_existing',wraps=journal._recover_existing) as recover:
            self.assertFalse(pipeline._shutdown({},journal,state))
            recover.assert_not_called()
        self.assertEqual(path.read_bytes(),b'')

    def test_hot_app_zero_empty_and_foreign_database_are_not_initialized(self):
        for foreign in (False,True):
            with self.subTest(foreign=foreign):
                directory=self.root/str(foreign);directory.mkdir();path=directory/'state.db'
                with contextlib.closing(sqlite3.connect(path)) as db:
                    db.execute('VACUUM')
                    if foreign:db.execute('CREATE TABLE foreign_state(value)');db.execute('INSERT INTO foreign_state VALUES(?)',('original',));db.commit()
                code="""import os,sqlite3,sys
db=sqlite3.connect(sys.argv[1]);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=1');db.execute('PRAGMA cache_spill=ON');db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE uncommitted_spill(value)');db.executemany('INSERT INTO uncommitted_spill VALUES(?)',[(bytes(4096),)]*80);os._exit(23)
"""
                outcome=pipeline.processes.run_command([str(Path(sys.executable).resolve()),'-c',code,str(path)],directory,20,cancel_requested=lambda:False)
                self.assertEqual(outcome['exit_code'],23);self.assertTrue(outcome['cleanup_confirmed'])
                journal=PipelineJournal(path)
                with self.assertRaises(ValueError) as failure:journal.status()
                self.assertEqual(failure.exception.__cause__.sqlite_errorname,'SQLITE_READONLY_ROLLBACK')
                done=threading.Event();done.set()
                host=SimpleNamespace(owner=None,done=done,outcome=outcome,close=lambda:None)
                state=dict(owner=None,stop=threading.Event(),workers=[host],dispatcher=None,ticks=0,failures=0)
                self.assertFalse(pipeline._shutdown({},journal,state))
                with contextlib.closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                    self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0],0)
                    self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],0)
                    tables=db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    self.assertEqual(tables,[('foreign_state',)] if foreign else [])
                with self.assertRaises(ValueError):journal.status()

    def test_wal_database_is_rejected_without_recovery(self):
        path=self.root/'wal.db';journal=PipelineJournal(path);journal.submit(request(),policy())
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            state=dict(owner=None,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0)
            with patch.object(PipelineJournal,'_recover_existing',wraps=journal._recover_existing) as recover:
                self.assertFalse(pipeline._shutdown({},journal,state));recover.assert_not_called()

    def hot_owned_fixture(self,directory,controller=False):
        directory.mkdir();path=directory/'state.db';journal=PipelineJournal(path)
        for number in range(1,81):journal.submit(request(number),policy())
        owner=str(uuid.uuid4());saved=directory/'claimed.json'
        controller_owner=str(uuid.uuid4()) if controller else None
        if controller_owner:journal.claim_controller(controller_owner,'b'*64)
        code="""import json,os,sqlite3,sys
from pathlib import Path
from task_tower.pipeline_journal import PipelineJournal
j=PipelineJournal(Path(sys.argv[1]))
with j.owner(sys.argv[2]):
 row=j.claim(sys.argv[2],2);Path(sys.argv[3]).write_text(json.dumps(dict(claimed=row,rows=j.status()['runs'],history=j.history(row['run_id']),controller=j.controller_health())))
 db=sqlite3.connect(sys.argv[1]);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=1');db.execute('PRAGMA cache_spill=ON');db.execute('BEGIN IMMEDIATE');db.execute('UPDATE runs SET policy_sha256=?',('c'*64,));os._exit(23)
"""
        env=dict(os.environ,PYTHONPATH=str(Path(pipeline.__file__).resolve().parent.parent)+os.pathsep+os.environ.get('PYTHONPATH',''))
        outcome=pipeline.processes.run_command([str(Path(sys.executable).resolve()),'-c',code,str(path),owner,str(saved)],directory,20,env=env,cancel_requested=lambda:False)
        self.assertEqual(outcome['exit_code'],23);self.assertTrue(outcome['cleanup_confirmed'])
        before=json.loads(saved.read_text());claimed=before['claimed'];self.assertEqual(claimed['owner_pid'],outcome['pid'])
        with self.assertRaises(ValueError) as error:journal.status()
        self.assertEqual(error.exception.__cause__.sqlite_errorname,'SQLITE_READONLY_ROLLBACK')
        done=threading.Event();done.set()
        host=SimpleNamespace(owner=owner,done=done,outcome=outcome,close=lambda:None)
        state=dict(owner=controller_owner,stop=threading.Event(),workers=[host],dispatcher=None,ticks=0,failures=0,_before=before)
        return journal,state

    def test_fallback_disappearance_after_recovery_or_before_later_writes_never_creates(self):
        for boundary in ('after_recovery','cancel','controller_tick','release_controller','commit'):
            with self.subTest(boundary=boundary):
                journal,state=self.hot_owned_fixture(self.root/boundary,controller=boundary in ('controller_tick','release_controller','commit'))
                method='_recover_existing' if boundary=='after_recovery' else ('_assert_existing' if boundary=='commit' else boundary)
                original=getattr(PipelineJournal,method)
                def remove_at_boundary(target,*args,**kwargs):
                    if boundary=='commit':
                        db=sys._getframe(1).f_locals.get('db')
                        if db is not None and db.in_transaction:target.path.unlink()
                        return original(target,*args,**kwargs)
                    if boundary=='after_recovery':
                        result=original(target,*args,**kwargs);target.path.unlink();return result
                    target.path.unlink();return original(target,*args,**kwargs)
                with patch.object(PipelineJournal,method,remove_at_boundary):
                    self.assertFalse(pipeline._shutdown({},journal,state,cancel_runs=True))
                self.assertTrue(state['_shutdown_journal_done'].is_set())
                if boundary=='commit' and journal.path.exists():
                    # Rollback may restore the filename (Windows) or leave it
                    # absent (POSIX). A restored journal must be the original.
                    before=state['_before']
                    self.assertEqual(len(before['rows']),80)
                    self.assertEqual(journal.status()['runs'],before['rows'])
                    self.assertEqual(journal.status(before['claimed']['run_id']),before['claimed'])
                    self.assertEqual(journal.history(before['claimed']['run_id']),before['history'])
                    self.assertEqual(journal.controller_health(),before['controller'])
                    self.assertFalse(journal.controller_health()['health']['stopped'])
                    with contextlib.closing(sqlite3.connect(journal.path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                        self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0],1414808656)
                    self.assertIsNone(journal.claim(str(uuid.uuid4()),2))
                    self.assertEqual(journal.history(before['claimed']['run_id']),before['history'])
                else:self.assertFalse(journal.path.exists())

    def test_fallback_rejects_valid_database_replacement_after_recovery(self):
        journal,state=self.hot_owned_fixture(self.root/'replacement')
        replacement=self.root/'replacement.db';PipelineJournal(replacement).submit(request(999),policy())
        original=PipelineJournal._recover_existing
        def replace_after_recovery(target):
            result=original(target);target.path.unlink();shutil.copy2(replacement,target.path);return result
        with patch.object(PipelineJournal,'_recover_existing',replace_after_recovery):
            self.assertFalse(pipeline._shutdown({},journal,state,cancel_runs=True))


if __name__=='__main__':unittest.main()
