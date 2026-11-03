"""Real SQLite commit barriers; no fabricated exists result or exception."""
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from task_tower.dispatch_delivery import DeliveryJournal
from tests import test_safe_config_race as path_fixtures
from tests import test_private_sqlite_stat as stat_fixtures


class DeliverySQLiteRaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=path_fixtures.ExecutorTransientLinkTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.path=self.root/'delivery.sqlite3'
        self.input=self.root/'config.json';self.input.write_text('{}')

    def commit_barrier(self,boundary):
        journal=DeliveryJournal(self.path,forbidden_paths=(self.input,))
        journal.reserve(dict(repository='fixture/local',issue=1,task_id='TT-RACE-1'),'a'*64)
        sidecar=Path(str(self.path)+'-journal');ready=threading.Event();release=threading.Event();done=threading.Event();errors=[]
        def writer():
            try:
                with journal._database(write=True) as db:
                    db.execute("INSERT INTO metadata VALUES('lookup_cursor',?)",(json.dumps(['fixture/local',1]),))
                    ready.set()
                    if not release.wait(10):raise AssertionError('Reader never reached real observation')
            except BaseException as error:errors.append(error)
            finally:done.set()
        thread=threading.Thread(target=writer);thread.start();self.addCleanup(lambda:(release.set(),thread.join(10)))
        self.assertTrue(ready.wait(10));self.assertTrue(sidecar.exists())
        reader=threading.get_ident();exists=Path.exists;stat=Path.stat;observed=[];armed=[]
        def actual_exists(path):
            value=exists(path)
            if boundary=='exists' and threading.get_ident()==reader and path==sidecar and not observed:
                self.assertTrue(value);observed.append(True);release.set();self.assertTrue(done.wait(10));self.assertFalse(exists(path))
            return value
        def actual_stat(path,*args,**kwargs):
            value=stat(path,*args,**kwargs)
            if boundary=='stat_snapshot' and threading.get_ident()==reader and kwargs.get('follow_symlinks',True):
                if path==sidecar and sys._getframe(1).f_code.co_name!='exists':armed.append(True)
                if path==self.input and armed and not observed and sys._getframe(1).f_code.co_name=='exists':
                    observed.append(True);release.set();self.assertTrue(done.wait(10));self.assertFalse(exists(sidecar))
            return value
        with patch.object(Path,'exists',actual_exists),patch.object(Path,'stat',actual_stat):
            self.assertEqual(len(journal.rows()),1)
        thread.join(10);self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertEqual(len(observed),1)

    def test_real_commit_after_positive_exists_keeps_read_available(self):
        self.commit_barrier('exists')

    def test_real_commit_after_stat_snapshot_keeps_alias_check_available(self):
        self.commit_barrier('stat_snapshot')

    def test_only_exact_sidecars_allow_genuine_unlinked_file_metadata(self):
        info=self.fixture.unlinked_info()
        for suffix in ('-journal','-wal','-shm'):
            journal=DeliveryJournal(self.path);sidecar=Path(str(self.path)+suffix);sidecar.touch()
            with self.subTest(suffix=suffix),stat_fixtures.PrivateSQLiteStatTests.fault(self,sidecar,info):journal._safe()
        for name in ('delivery.sqlite3','config.json','config-journal','config-wal','config-shm'):
            path=self.root/name;path.touch(exist_ok=True)
            journal=DeliveryJournal(self.path,forbidden_paths=() if path==self.path else (path,))
            with self.subTest(name=name),stat_fixtures.PrivateSQLiteStatTests.fault(self,path,info),self.assertRaises(ValueError):journal._safe()

    def test_hardlinks_directories_aliases_and_suffix_named_main_stay_strict(self):
        for suffix in ('','-journal','-wal','-shm'):
            path=Path(str(self.path)+suffix);path.touch(exist_ok=True);alias=self.root/'alias';os.link(path,alias)
            try:
                with self.subTest(suffix=suffix),self.assertRaises(ValueError):DeliveryJournal(self.path)
            finally:alias.unlink();path.unlink()
        sidecar=Path(str(self.path)+'-journal');sidecar.mkdir()
        with self.assertRaises(ValueError):DeliveryJournal(self.path)
        sidecar.rmdir()
        with self.assertRaises(ValueError):DeliveryJournal(self.path,forbidden_paths=(self.path,))
        info=self.fixture.unlinked_info()
        for suffix in ('-journal','-wal','-shm'):
            path=self.root/('main'+suffix);path.touch()
            journal=DeliveryJournal(path)
            with self.subTest(main=suffix),stat_fixtures.PrivateSQLiteStatTests.fault(self,path,info),self.assertRaises(ValueError):journal._safe()

    def test_previously_observed_input_and_main_disappearance_fail_closed(self):
        for target in (self.input,self.path):
            target.touch(exist_ok=True);journal=DeliveryJournal(self.path,forbidden_paths=(self.input,))
            original=Path.exists;seen=[]
            def disappear(path):
                value=original(path)
                if path==target and value and not seen:seen.append(True);path.unlink()
                return value
            with self.subTest(target=target.name),patch.object(Path,'exists',disappear),self.assertRaises((OSError,ValueError)):journal._safe()

    def test_optional_missing_input_remains_optional(self):
        path=self.root/'optional.json';DeliveryJournal(self.path,forbidden_paths=(path,))._safe();self.assertFalse(path.exists())

    def test_observed_directory_and_zero_link_directory_remain_rejected(self):
        for info in (self.fixture.unlinked_info(directory=True),self.fixture.modeled_directory_zero_info()):
            journal=DeliveryJournal(self.path);sidecar=Path(str(self.path)+'-journal');sidecar.touch()
            with stat_fixtures.PrivateSQLiteStatTests.fault(self,sidecar,info),self.assertRaises(ValueError):journal._safe()

    def test_current_replacement_hardlink_directory_and_reparse_stay_rejected(self):
        info=self.fixture.unlinked_info()
        for replacement in ('hardlink','directory','link'):
            journal=DeliveryJournal(self.path);sidecar=Path(str(self.path)+'-journal');sidecar.touch()
            target=self.root/'target'
            if replacement=='hardlink':target.touch()
            else:target.mkdir()
            def replace():
                if replacement=='hardlink':os.link(target,sidecar)
                elif replacement=='directory':sidecar.mkdir()
                elif os.name=='nt':subprocess.run(['cmd','/c','mklink','/J',str(sidecar),str(target)],check=True,capture_output=True)
                else:sidecar.symlink_to(target,target_is_directory=True)
            try:
                with self.subTest(replacement=replacement),stat_fixtures.PrivateSQLiteStatTests.fault(self,sidecar,info,replace),self.assertRaises(ValueError):journal._safe()
            finally:
                if sidecar.is_symlink() or replacement=='hardlink':sidecar.unlink(missing_ok=True)
                elif sidecar.exists():sidecar.rmdir()
                target.unlink() if replacement=='hardlink' else target.rmdir()

    def test_forbidden_input_hardlink_directory_and_alias_remain_rejected(self):
        alias=self.root/'input-alias';os.link(self.input,alias)
        try:
            with self.assertRaises(ValueError):DeliveryJournal(self.path,forbidden_paths=(self.input,))
        finally:alias.unlink()
        directory=self.root/'input-directory';directory.mkdir()
        with self.assertRaises(ValueError):DeliveryJournal(self.path,forbidden_paths=(directory,))
        for forbidden in (self.path,Path(str(self.path)+'-journal')):
            with self.subTest(alias=forbidden.name),self.assertRaises(ValueError):DeliveryJournal(self.path,forbidden_paths=(forbidden,))

    def test_cold_imports_both_orders_and_neutral_cli_error(self):
        root=Path(__file__).resolve().parent.parent
        for order in ('dispatch_delivery,executor_queue','executor_queue,dispatch_delivery'):
            result=subprocess.run([sys.executable,'-c','from task_tower import '+order],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        from task_tower import pipeline
        with patch.object(pipeline,'_runtime',side_effect=ValueError('Delivery journal unavailable; preserve journal and restore access')):
            import io
            stream=io.StringIO()
            with contextlib.redirect_stderr(stream):code=pipeline.main(['status','--connections',str(self.input),'--journal',str(self.path)])
        self.assertEqual(code,2);self.assertEqual(json.loads(stream.getvalue()),dict(error='invalid_or_unavailable_private_state'))

    def test_sqlite_error_preserves_cause_without_changing_generic_message(self):
        journal=DeliveryJournal(self.path);journal.reserve(dict(repository='fixture/local',issue=1,task_id='TT-RACE-1'),'a'*64)
        with patch('task_tower.dispatch_delivery.sqlite3.connect',side_effect=sqlite3.OperationalError('diagnostic sentinel')):
            with self.assertRaises(ValueError) as raised:journal.rows()
        self.assertIsInstance(raised.exception.__cause__,sqlite3.OperationalError)
        self.assertEqual(str(raised.exception),'Delivery journal unavailable; preserve journal and restore access')


if __name__=='__main__':unittest.main()
