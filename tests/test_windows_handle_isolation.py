"""Actual native proof: another worker's inheritable pipe is not inherited."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path


@unittest.skipUnless(os.name=='nt','Windows handle inheritance')
class WindowsHandleIsolationTests(unittest.TestCase):
    def test_child_does_not_keep_unrelated_inheritable_pipe_open(self):
        from task_tower.windows_job import WindowsJobProcess
        with tempfile.TemporaryDirectory() as directory:
            read_fd,write_fd=os.pipe();os.set_inheritable(write_fd,True)
            reader=os.fdopen(read_fd,'rb',buffering=0);complete=threading.Event()
            def drain():
                try:reader.read(1)
                finally:complete.set();reader.close()
            thread=threading.Thread(target=drain,daemon=True);thread.start();process=None
            try:
                with open(Path(directory)/'stdout','wb') as stdout,open(Path(directory)/'stderr','wb') as stderr:
                    process=WindowsJobProcess([sys.executable,'-B','-c','import time; time.sleep(20)'],Path(directory),stdout,stderr)
                    os.close(write_fd);write_fd=None
                    self.assertTrue(complete.wait(1),'Child inherited an unrelated pipe writer')
            finally:
                if write_fd is not None:os.close(write_fd)
                if process is not None:
                    process.terminate();process.wait(5);process.close()
                thread.join(5)
            self.assertFalse(thread.is_alive())
