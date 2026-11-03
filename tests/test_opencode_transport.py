"""Bounded stdin transport fixtures; never invoke OpenCode or a model."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from task_tower import processes
from task_tower.opencode_files import identity


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.path=self.root/'native-input.txt'
        self.data=b'private input\n';self.path.write_bytes(self.data)

    def spec(self):
        return dict(path=str(self.path),expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                    expected_bytes=self.path.stat().st_size,expected_identity=identity(self.path.stat()))

    def run_input(self,spec=None,code=None,**kwargs):
        code=code or 'import sys,hashlib;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'
        logs=self.root/('logs'+str(len(list(self.root.glob('logs*')))));logs.mkdir()
        result=processes.run_command([sys.executable,'-c',code],self.root,kwargs.pop('timeout',5),
            stdin_spec=self.spec() if spec is None else spec,capture=dict(directory=logs,max_bytes_per_stream=1024),**kwargs)
        return result,logs

    def test_full_instruction_bundle_reaches_stdin_exactly(self):
        # Full60 raw size plus sixty delimiters and request; transport is byte exact.
        self.data=b'A'*357576+b''.join(('<instruction path="skill%d">\n</instruction>\n'%i).encode() for i in range(60))+b'REQUEST private issue prose\n'
        self.path.write_bytes(self.data)
        result,logs=self.run_input()
        self.assertEqual(result['status'],'passed');self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual((logs/'stdout.log').read_bytes().strip(),hashlib.sha256(self.data).hexdigest().encode())
        self.assertNotIn('argv',result);self.assertFalse(result['stdout_tail_unknown'])

    def test_frozen_mismatch_and_oversize_reject_before_lookup(self):
        original=self.spec()
        cases=[{**original,'extra':True},{**original,'expected_bytes':True},
               {**original,'expected_bytes':4194305},{**original,'expected_sha256':'0'*64},
               {**original,'expected_identity':{**original['expected_identity'],'file_id':'0'}}]
        for spec in cases:
            with self.subTest(spec=spec),patch.object(processes.shutil,'which',side_effect=AssertionError('spawn lookup reached')):
                result=processes.run_command([sys.executable,'-c','pass'],self.root,3,stdin_spec=spec)
            self.assertEqual(result['reason'],'stdin_binding_mismatch');self.assertFalse(result['started'])
            self.assertTrue(result['cleanup_confirmed'])

    def test_stage_is_readonly_anonymous_and_original_closed(self):
        with processes._stage_stdin(self.spec()) as stream:
            self.assertFalse(os.get_inheritable(stream.fileno()))
            with self.assertRaises(OSError):os.write(stream.fileno(),b'changed')
            self.assertEqual(stream.read(),self.data)
            # Original source is closed; replacing it cannot change staged bytes.
            self.path.unlink();self.path.write_bytes(b'replacement')
            stream.seek(0);self.assertEqual(stream.read(),self.data)
            if os.name!='nt':self.assertEqual(os.fstat(stream.fileno()).st_nlink,0)

    def test_replace_after_producer_hash_before_runner_open(self):
        spec=self.spec();self.path.unlink();self.path.write_bytes(self.data)
        with patch.object(processes.shutil,'which',side_effect=AssertionError('lookup reached')):
            result=processes.run_command([sys.executable,'-c','pass'],self.root,3,stdin_spec=spec)
        self.assertFalse(result['started']);self.assertEqual(result['reason'],'stdin_binding_mismatch')

    def test_staging_failure_closes_all_handles(self):
        with patch.object(processes,'_stdin_storage',side_effect=OSError('private stage failure')):
            result=processes.run_command([sys.executable,'-c','pass'],self.root,3,stdin_spec=self.spec())
        self.assertFalse(result['started']);self.assertEqual(result['reason'],'stdin_binding_mismatch')
        self.path.unlink()  # Windows source handle cannot remain open denying delete.

    def test_early_exit_and_nonreader_timeout(self):
        self.path.write_bytes(b'x'*4194304)
        for code,timeout,status in [('pass',3,'passed'),('import time;time.sleep(30)',.2,'timeout')]:
            with self.subTest(status=status):
                before=time.monotonic();result,_=self.run_input(code=code,timeout=timeout)
                self.assertEqual(result['status'],status);self.assertTrue(result['cleanup_confirmed'])
                self.assertLess(time.monotonic()-before,5)

    def test_short_staging_write_is_not_verified_input(self):
        storage=processes._stdin_storage
        def short_storage():
            writer,reader=storage()
            class ShortWriter:
                def write(self,data):return 0
                def close(self):writer.close()
            return ShortWriter(),reader
        with patch.object(processes,'_stdin_storage',side_effect=short_storage):
            with self.assertRaisesRegex(ValueError,'stdin_binding_mismatch'):
                processes._stage_stdin(self.spec())

    def test_inplace_mutation_or_size_change_during_staging_blocks(self):
        original_read=os.read
        for mutation in ('different_bytes','short_read','long_read'):
            with self.subTest(mutation=mutation):
                first=True
                def read(fd,limit):
                    nonlocal first
                    data=original_read(fd,limit)
                    if first:
                        first=False
                        if mutation=='different_bytes':return b'X'*len(data)
                        if mutation=='short_read':return data[:-1]
                        return data+b'X'
                    return data
                with patch.object(processes.os,'read',side_effect=read),patch.object(processes.shutil,'which',side_effect=AssertionError('lookup reached')):
                    result=processes.run_command([sys.executable,'-c','pass'],self.root,3,stdin_spec=self.spec())
                self.assertFalse(result['started']);self.assertEqual(result['reason'],'stdin_binding_mismatch')

    def test_original_replacement_after_staging_cannot_change_child_bytes(self):
        stage=processes._stage_stdin
        def replace(spec):
            stream=stage(spec);self.path.unlink();self.path.write_bytes(b'UNTRUSTED replacement')
            return stream
        with patch.object(processes,'_stage_stdin',side_effect=replace):result,logs=self.run_input()
        self.assertEqual(result['status'],'passed')
        self.assertEqual((logs/'stdout.log').read_bytes().strip(),hashlib.sha256(self.data).hexdigest().encode())

    def test_nonreader_cancel_kills_descendant(self):
        marker=self.root/'escaped'
        child='import pathlib,time;time.sleep(1);pathlib.Path('+repr(str(marker))+').write_text("escaped")'
        code='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(30)'
        start=time.monotonic()
        result,_=self.run_input(code=code,cancel_requested=lambda:time.monotonic()-start>.25)
        self.assertEqual(result['status'],'cancelled');self.assertTrue(result['cleanup_confirmed'])
        self.assertLess(time.monotonic()-start,5);time.sleep(1.1);self.assertFalse(marker.exists())

    def test_hardlink_directory_and_symlink_sources_are_rejected(self):
        original=self.spec();link=self.root/'hardlink'
        os.link(self.path,link)
        with self.assertRaises(ValueError):processes._stage_stdin(original)
        link.unlink()
        spec={**original,'path':str(self.root),'expected_identity':identity(self.root.stat())}
        with self.assertRaises(ValueError):processes._stage_stdin(spec)
        alias=self.root/'alias'
        try:alias.symlink_to(self.path)
        except OSError:return  # Other unconditional alias cases above remain exercised.
        with self.assertRaises(ValueError):processes._stage_stdin({**original,'path':str(alias)})

    def test_storage_stream_conversion_failure_closes_raw_handles(self):
        original=os.fdopen
        for fail_at in (1,2):
            descriptors=[]
            def fail(fd,*args,**kwargs):
                descriptors.append(fd)
                if len(descriptors)==fail_at:raise OSError('stream conversion failed')
                return original(fd,*args,**kwargs)
            with self.subTest(fail_at=fail_at),patch.object(processes.os,'fdopen',side_effect=fail):
                with self.assertRaises(OSError):processes._stdin_storage()
            for fd in descriptors:
                with self.assertRaises(OSError):os.fstat(fd)

    def test_actual_source_write_during_staging_is_blocked_or_detected(self):
        storage=processes._stdin_storage
        for longer in (False,True):
            with self.subTest(longer=longer):
                self.path.write_bytes(self.data);spec=self.spec();blocked=[]
                def mutate():
                    try:self.path.write_bytes(b'Z'*(len(self.data)+(1 if longer else 0)))
                    except PermissionError:blocked.append(True)
                    return storage()
                with patch.object(processes,'_stdin_storage',side_effect=mutate):
                    if os.name=='nt':
                        with processes._stage_stdin(spec) as stage:self.assertEqual(stage.read(),self.data)
                        self.assertTrue(blocked)  # Source share flags deny existing/new writers.
                    else:
                        with self.assertRaisesRegex(ValueError,'stdin_binding_mismatch'):processes._stage_stdin(spec)

    def test_inherited_child_stdin_is_not_writable(self):
        code='import os,sys\ntry:\n os.write(0,b"UNAUTHORIZED")\nexcept OSError:\n print("readonly")\nelse:\n raise SystemExit(7)\n'
        result,logs=self.run_input(code=code)
        self.assertEqual(result['status'],'passed')
        self.assertEqual((logs/'stdout.log').read_bytes().strip(),b'readonly')

    def test_source_and_transport_closed_on_spawn_failure(self):
        stage=processes._stage_stdin;opened=[]
        def remember(spec):
            value=stage(spec);opened.append(value);return value
        if os.name=='nt':target='task_tower.windows_job.WindowsJobProcess'
        else:target='task_tower.processes.subprocess.Popen'
        with patch.object(processes,'_stage_stdin',side_effect=remember),patch(target,side_effect=OSError('spawn failed')):
            result,_=self.run_input()
        self.assertFalse(result['started']);self.assertEqual(result['status'],'unavailable')
        self.assertTrue(result['cleanup_confirmed']);self.assertTrue(opened[0].closed)
        self.path.unlink()

    def test_transport_close_failure_never_reports_success(self):
        stage=processes._stage_stdin
        def closing_failure(spec):
            value=stage(spec)
            class BrokenClose:
                def fileno(self):return value.fileno()
                def close(self):value.close();raise OSError('close confirmation lost')
            return BrokenClose()
        with patch.object(processes,'_stage_stdin',side_effect=closing_failure):
            result,_=self.run_input(code='pass')
        self.assertEqual(result['status'],'cleanup_failed');self.assertFalse(result['cleanup_confirmed'])

    def test_stdin_without_capture_retains_optional_digest_shape(self):
        result=processes.run_command([sys.executable,'-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                                    self.root,3,stdin_spec=self.spec())
        self.assertEqual(result['status'],'passed');self.assertNotIn('argv',result)
        self.assertEqual(result['stdout_sha256'],hashlib.sha256(self.data).hexdigest())
        self.assertEqual(result['stdout_captured_bytes'],0);self.assertFalse(result['stdout_tail_unknown'])

    def test_staging_writer_close_failure_also_closes_reader(self):
        storage=processes._stdin_storage;readers=[]
        def broken_storage():
            writer,reader=storage();readers.append(reader)
            class BrokenWriter:
                def write(self,data):return writer.write(data)
                def close(self):writer.close();raise OSError('close failed')
            return BrokenWriter(),reader
        with patch.object(processes,'_stdin_storage',side_effect=broken_storage):
            with self.assertRaises((ValueError,OSError)):processes._stage_stdin(self.spec())
        self.assertTrue(readers[0].closed)

    @unittest.skipUnless(os.name=='nt','Windows constructor ownership transfer')
    def test_storage_constructor_failure_closes_each_owner_and_preserves_failure(self):
        opened=[];paths=[];original=os.fdopen;inheritance_error=OSError('inheritance failure')
        class BrokenWriter:
            def __init__(self,stream):self.stream=stream
            def fileno(self):return self.stream.fileno()
            def close(self):self.stream.close();raise OSError('writer close confirmation failed')
        def wrapped(fd,mode,**kwargs):
            stream=original(fd,mode,**kwargs);opened.append(stream)
            import ctypes as C
            from ctypes import wintypes as W
            import msvcrt
            function=C.WinDLL('kernel32',use_last_error=True).GetFinalPathNameByHandleW
            function.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD];function.restype=W.DWORD
            buffer=C.create_unicode_buffer(32768)
            length=function(msvcrt.get_osfhandle(fd),buffer,len(buffer),0)
            self.assertTrue(0<length<len(buffer));paths.append(buffer.value)
            return BrokenWriter(stream) if mode=='w+b' else stream
        with patch.object(processes.os,'fdopen',side_effect=wrapped),patch.object(processes.os,'set_inheritable',side_effect=inheritance_error):
            with self.assertRaises(OSError) as caught:processes._stdin_storage()
        try:
            self.assertIs(caught.exception,inheritance_error)
            self.assertEqual([stream.closed for stream in opened],[True,True])
            self.assertTrue(paths);self.assertTrue(all(not Path(path).exists() for path in paths))
        finally:
            for stream in opened:stream.close()

    def test_storage_second_stream_failure_still_cleans_writer(self):
        original=os.fdopen;opened=[];raw=[];primary=OSError('reader conversion failure')
        class BrokenWriter:
            def __init__(self,value):self.value=value
            def close(self):self.value.close();raise OSError('writer close failure')
        def convert(fd,mode,**kwargs):
            raw.append(fd)
            if mode=='rb':raise primary
            value=original(fd,mode,**kwargs);opened.append(value);return BrokenWriter(value)
        with patch.object(processes.os,'fdopen',side_effect=convert):
            with self.assertRaises(OSError) as caught:processes._stdin_storage()
        self.assertIs(caught.exception,primary);self.assertTrue(opened[0].closed)
        self.assertFalse(caught.exception.stdin_cleanup_confirmed)
        for fd in raw:
            with self.assertRaises(OSError):os.fstat(fd)

    @unittest.skipUnless(os.name=='nt','Windows constructor ownership transfer')
    def test_constructor_cleanup_uncertainty_is_not_reported_confirmed(self):
        original=os.fdopen;opened=[];set_inheritable=os.set_inheritable;calls=0
        class BrokenWriter:
            def __init__(self,value):self.value=value
            def fileno(self):return self.value.fileno()
            def close(self):self.value.close();raise OSError('close confirmation lost')
        def wrapped(fd,mode,**kwargs):
            stream=original(fd,mode,**kwargs);opened.append(stream)
            return BrokenWriter(stream) if mode=='w+b' else stream
        def fail_storage(fd,value):
            nonlocal calls
            calls+=1
            if calls==1:return set_inheritable(fd,value)  # Source open precedes staging.
            raise OSError('storage setup failure')
        with patch.object(processes.os,'fdopen',side_effect=wrapped),patch.object(processes.os,'set_inheritable',side_effect=fail_storage):
            result=processes.run_command([sys.executable,'-c','pass'],self.root,3,stdin_spec=self.spec())
        try:
            self.assertFalse(result['started']);self.assertFalse(result['cleanup_confirmed'])
            self.assertEqual(result['status'],'cleanup_failed');self.assertEqual(result['reason'],'stdin_binding_mismatch')
            self.assertEqual([stream.closed for stream in opened],[True,True])
        finally:
            for stream in opened:stream.close()


if __name__=='__main__':unittest.main()
