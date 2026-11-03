"""Actual unlinked metadata at both private journal stat race boundaries."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from task_tower.executor_queue import ExecutionQueue
from task_tower.pipeline_journal import PipelineJournal
from tests import test_safe_config_race as fixtures


class PrivateSQLiteStatTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ExecutorTransientLinkTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root

    def owner(self,kind,forbidden=()):
        path=self.root/(kind.__name__+'.sqlite3');path.touch(exist_ok=True)
        return kind(path,forbidden_paths=forbidden)

    def fault(self,path,info,replace=None):
        original=Path.stat;seen=[]
        def observed(candidate,*args,**kwargs):
            if candidate==path and kwargs.get('follow_symlinks',True) and sys._getframe(1).f_code.co_name!='exists' and not seen:
                seen.append(True)
                if candidate.exists():candidate.unlink()
                if replace is not None:replace()
                return info
            return original(candidate,*args,**kwargs)
        return patch.object(Path,'stat',observed)

    def test_all_three_exact_sidecars_allow_actual_deleted_file_metadata(self):
        info=self.fixture.unlinked_info()
        for kind in (ExecutionQueue,PipelineJournal):
            owner=self.owner(kind)
            for suffix in ('-journal','-wal','-shm'):
                path=Path(str(owner.path)+suffix);path.touch()
                with self.subTest(kind=kind.__name__,suffix=suffix),self.fault(path,info):owner._safe()

    def test_main_and_all_forbidden_input_names_remain_strict_at_zero(self):
        info=self.fixture.unlinked_info()
        for kind in (ExecutionQueue,PipelineJournal):
            for name in ('main','config.json','config-journal','config-wal','config-shm'):
                other=self.root/name
                if name!='main':other.touch()
                owner=self.owner(kind,() if name=='main' else (other,))
                path=owner.path if name=='main' else other
                with self.subTest(kind=kind.__name__,name=name),self.fault(path,info),self.assertRaises(ValueError):owner._safe()

    def test_main_and_sidecar_hardlinks_stay_rejected(self):
        for kind in (ExecutionQueue,PipelineJournal):
            for suffix in ('','-journal','-wal','-shm'):
                owner=self.owner(kind);path=Path(str(owner.path)+suffix)
                if suffix:path.touch()
                alias=self.root/'alias';os.link(path,alias)
                try:
                    with self.subTest(kind=kind.__name__,suffix=suffix),self.assertRaises(ValueError):owner._safe()
                finally:
                    alias.unlink()
                    if suffix:path.unlink()

    def test_main_database_with_sidecar_suffix_is_still_strict(self):
        info=self.fixture.unlinked_info()
        for kind in (ExecutionQueue,PipelineJournal):
            for suffix in ('-journal','-wal','-shm'):
                path=self.root/('main'+suffix);path.touch()
                owner=kind(path)
                with self.subTest(kind=kind.__name__,suffix=suffix),self.fault(path,info),self.assertRaises(ValueError):owner._safe()

    def test_actual_deleted_directory_never_becomes_missing_sidecar(self):
        info=self.fixture.unlinked_info(directory=True)
        for kind in (ExecutionQueue,PipelineJournal):
            owner=self.owner(kind);path=Path(str(owner.path)+'-journal');path.touch()
            with self.subTest(kind=kind.__name__),self.fault(path,info),self.assertRaises(ValueError):owner._safe()

    def test_modeled_zero_link_directory_never_becomes_missing_sidecar(self):
        """Synthetic zero-link directory boundary, distinct from actual fstat."""
        info=self.fixture.modeled_directory_zero_info()
        for kind in (ExecutionQueue,PipelineJournal):
            owner=self.owner(kind);path=Path(str(owner.path)+'-journal');path.touch()
            with self.subTest(kind=kind.__name__),self.fault(path,info),self.assertRaises(ValueError):owner._safe()

    def test_current_hardlink_directory_and_link_replacements_stay_rejected(self):
        info=self.fixture.unlinked_info()
        for kind in (ExecutionQueue,PipelineJournal):
            for replacement in ('hardlink','directory','link'):
                owner=self.owner(kind);path=Path(str(owner.path)+'-journal');path.touch()
                target=self.root/'target'
                if replacement=='hardlink':target.write_bytes(b'input')
                else:target.mkdir()
                def replace():
                    if replacement=='hardlink':os.link(target,path)
                    elif replacement=='directory':path.mkdir()
                    elif os.name=='nt':subprocess.run(['cmd','/c','mklink','/J',str(path),str(target)],check=True,capture_output=True)
                    else:path.symlink_to(target,target_is_directory=True)
                try:
                    with self.subTest(kind=kind.__name__,replacement=replacement),self.fault(path,info,replace),self.assertRaises(ValueError):owner._safe()
                finally:
                    if path.is_symlink() or replacement=='hardlink':path.unlink(missing_ok=True)
                    elif path.exists():path.rmdir()
                    target.unlink() if replacement=='hardlink' else target.rmdir()

    def test_forbidden_alias_to_exact_sidecar_stays_rejected(self):
        for kind in (ExecutionQueue,PipelineJournal):
            owner=self.owner(kind)
            owner.forbidden_paths=(Path(str(owner.path)+'-journal'),)
            with self.subTest(kind=kind.__name__),self.assertRaises(ValueError):owner._safe()

    def test_queue_alias_check_allows_actual_sidecar_unlink_only(self):
        other=self.root/'input.json';other.touch()
        owner=self.owner(ExecutionQueue,(other,));path=Path(str(owner.path)+'-journal');path.touch()
        original=os.path.samefile
        def same(left,right):
            if left==path and right==other:path.unlink()
            return original(left,right)
        with patch('os.path.samefile',same):owner._safe()

    def test_queue_alias_check_does_not_ignore_disappeared_forbidden_input(self):
        other=self.root/'input.json';other.touch()
        owner=self.owner(ExecutionQueue,(other,));path=Path(str(owner.path)+'-journal');path.touch()
        original=os.path.samefile
        def same(left,right):
            if left==path and right==other:path.unlink();other.unlink()
            return original(left,right)
        with patch('os.path.samefile',same),self.assertRaises(FileNotFoundError):owner._safe()

    def test_queue_main_disappearance_after_positive_exists_remains_error(self):
        owner=self.owner(ExecutionQueue);original=Path.exists;removed=[]
        def exists(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if path==owner.path and result and not removed:path.unlink();removed.append(True)
            return result
        with patch.object(Path,'exists',exists),self.assertRaises(FileNotFoundError):owner._safe()

    def test_initially_missing_optional_forbidden_output_still_works(self):
        for kind in (ExecutionQueue,PipelineJournal):
            missing=self.root/(kind.__name__+'-output.json')
            self.assertFalse(missing.exists())
            owner=self.owner(kind,(missing,));owner._safe()
            self.assertFalse(missing.exists())

