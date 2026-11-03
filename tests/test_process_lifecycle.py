"""Indefinite control-plane lifetime still has mandatory bounded cancellation."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from task_tower.processes import run_command


class LifecycleTests(unittest.TestCase):
    def test_lifecycle_requires_cancel_and_bounded_capture_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);marker=root/'launched'
            command=[sys.executable,'-c',"from pathlib import Path;Path("+repr(str(marker))+").write_text('launched')"]
            for kwargs in ({},{'cancel_requested':lambda:False}):
                with self.assertRaises(ValueError):run_command(command,root,None,**kwargs)
                self.assertFalse(marker.exists())

    def test_lifecycle_cancel_has_real_process_cleanup_and_full_eof(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);capture=root/'capture';capture.mkdir();start=time.monotonic()
            result=run_command([sys.executable,'-c','import time;print("started",flush=True);time.sleep(30)'],root,None,
                cancel_requested=lambda:time.monotonic()-start>.3,
                capture=dict(directory=capture,max_bytes_per_stream=4096))
            self.assertEqual(result['status'],'cancelled');self.assertTrue(result['started'])
            self.assertTrue(result['cleanup_confirmed']);self.assertLess(time.monotonic()-start,5)
            self.assertFalse(result['stdout_tail_unknown']);self.assertFalse(result['stderr_tail_unknown'])

    def test_lifecycle_cancel_kills_real_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);capture=root/'capture';capture.mkdir();marker=root/'escaped'
            descendant="import pathlib,time;time.sleep(.8);pathlib.Path("+repr(str(marker))+").write_text('escaped')"
            parent='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(descendant)+']);time.sleep(30)'
            start=time.monotonic()
            result=run_command([sys.executable,'-c',parent],root,None,cancel_requested=lambda:time.monotonic()-start>.25,
                capture=dict(directory=capture,max_bytes_per_stream=4096))
            self.assertEqual(result['status'],'cancelled');self.assertTrue(result['cleanup_confirmed'])
            time.sleep(1);self.assertFalse(marker.exists())
