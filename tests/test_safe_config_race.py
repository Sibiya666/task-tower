"""No-follow path observations remain valid when SQLite removes a sidecar."""
import os
import stat
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


class ExecutorTransientLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve()
        self.base=self.root/'state.sqlite3';self.base.touch()

    def unlinked_info(self,directory=False):
        """Actual removed inode; directory link counts differ across filesystems."""
        path=self.root/'held'
        if directory:path.mkdir()
        else:path.write_bytes(b'actual unlinked inode')
        if os.name=='nt':
            import ctypes as C
            from ctypes import wintypes as W
            import msvcrt
            kernel=C.WinDLL('kernel32',use_last_error=True)
            kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
            kernel.CreateFileW.restype=W.HANDLE
            handle=kernel.CreateFileW(str(path),0x80000000,7,None,3,0x02000000 if directory else 0,None)
            if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
            descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY)
        else:descriptor=os.open(path,os.O_RDONLY)
        try:
            path.rmdir() if directory else path.unlink()
            info=os.fstat(descriptor)
            self.assertFalse(path.exists())
            if directory:self.assertTrue(stat.S_ISDIR(info.st_mode))
            else:
                self.assertTrue(stat.S_ISREG(info.st_mode))
                self.assertEqual(info.st_nlink,0)
            return info
        finally:os.close(descriptor)

    def modeled_directory_zero_info(self):
        """Explicit synthetic zero-link boundary, not a kernel metadata claim."""
        values=list(self.unlinked_info(directory=True));values[3]=0
        return os.stat_result(values)

    def fault(self,path,info,replace=None):
        original=Path.stat;observed=[]
        def stat(candidate,*args,**kwargs):
            if candidate==path and kwargs.get('follow_symlinks',True) and not observed:
                observed.append(True)
                if replace is not None:replace()
                return info
            return original(candidate,*args,**kwargs)
        return patch.object(Path,'stat',stat)

    def test_deleted_directory_fixture_accepts_modeled_apfs_link_count_two(self):
        """Model only APFS link count; the directory is genuinely removed."""
        original=os.fstat
        def apfs_count(descriptor):
            info=original(descriptor)
            self.assertTrue(stat.S_ISDIR(info.st_mode))
            values=list(info);values[3]=2
            return os.stat_result(values)
        with patch('os.fstat',apfs_count):info=self.unlinked_info(directory=True)
        self.assertTrue(stat.S_ISDIR(info.st_mode));self.assertEqual(info.st_nlink,2)

    def test_typed_sidecars_allow_genuine_unlinked_stat_snapshot(self):
        from task_tower.executor import _paths
        info=self.unlinked_info()
        for suffix in ('-journal','-wal','-shm'):
            sidecar=Path(str(self.base)+suffix)
            with self.subTest(suffix=suffix),self.fault(sidecar,info):
                self.assertEqual(_paths([self.base,sidecar],[],transient_paths=[sidecar]),[self.base,sidecar])

    def test_main_config_inputs_and_untyped_suffix_zero_stay_rejected(self):
        from task_tower.executor import _paths
        info=self.unlinked_info()
        for name in ('state.sqlite3','config.json','request.json','config-journal','config-wal','config-shm'):
            path=self.root/name
            with self.subTest(name=name),self.fault(path,info),self.assertRaises(ValueError):_paths([path],[])

    def test_deleted_directory_snapshot_is_never_treated_as_sidecar(self):
        from task_tower.executor import _paths
        info=self.unlinked_info(directory=True);sidecar=Path(str(self.base)+'-journal')
        with self.fault(sidecar,info),self.assertRaises(ValueError):
            _paths([self.base,sidecar],[],transient_paths=[sidecar])

    def test_modeled_zero_link_directory_is_never_treated_as_sidecar(self):
        from task_tower.executor import _paths
        info=self.modeled_directory_zero_info();sidecar=Path(str(self.base)+'-journal')
        with self.fault(sidecar,info),self.assertRaises(ValueError):
            _paths([self.base,sidecar],[],transient_paths=[sidecar])

    def test_main_and_all_sidecar_hardlinks_stay_rejected(self):
        from task_tower.executor import _paths
        for suffix in ('','-journal','-wal','-shm'):
            path=Path(str(self.base)+suffix)
            if suffix:path.touch()
            alias=self.root/('alias'+suffix);os.link(path,alias)
            try:
                paths=[self.base,path] if suffix else [path]
                with self.subTest(suffix=suffix),self.assertRaises(ValueError):
                    _paths(paths,[],transient_paths=[path] if suffix else [])
            finally:alias.unlink()

    def test_replacement_hardlink_and_directory_stay_rejected(self):
        from task_tower.executor import _paths
        info=self.unlinked_info();sidecar=Path(str(self.base)+'-journal')
        target=self.root/'input.json';target.touch();os.link(target,sidecar)
        with self.fault(sidecar,info),self.assertRaises(ValueError):
            _paths([self.base,sidecar],[],transient_paths=[sidecar])
        sidecar.unlink()
        with self.fault(sidecar,info,sidecar.mkdir),self.assertRaises(ValueError):
            _paths([self.base,sidecar],[],transient_paths=[sidecar])

    def test_replacement_symlink_or_junction_stays_rejected(self):
        from task_tower.executor import _paths
        info=self.unlinked_info();sidecar=Path(str(self.base)+'-journal')
        target=self.root/'target';target.mkdir()
        def replace():
            if os.name=='nt':subprocess.run(['cmd','/c','mklink','/J',str(sidecar),str(target)],check=True,capture_output=True)
            else:sidecar.symlink_to(target,target_is_directory=True)
        try:
            with self.fault(sidecar,info,replace),self.assertRaises(ValueError):
                _paths([self.base,sidecar],[],transient_paths=[sidecar])
        finally:
            if sidecar.is_symlink():sidecar.unlink()
            elif sidecar.exists():sidecar.rmdir()

    def test_transient_roles_require_exact_membership_suffix_and_base(self):
        from task_tower.executor import _paths
        sidecar=Path(str(self.base)+'-journal')
        for paths,typed in [([self.base],[sidecar]),([self.base],[self.base]),([sidecar],[sidecar]),([self.base,sidecar],str(sidecar))]:
            with self.subTest(paths=paths,typed=typed),self.assertRaises(ValueError):_paths(paths,[],transient_paths=typed)
