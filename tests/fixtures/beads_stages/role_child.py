"""Harmless synthetic fixture. Every descendant self-exits within three seconds.

No harness/model/Beads/network use. Caller owns only processes it starts, never
adopts a PID from this fixture. Escaped markers indicate failed job containment.
"""
import os
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode in ('role', 'role-change-source-input', 'role-dev-delta', 'role-change-accepted-artifact'):
        request = json.loads(root.read_text(encoding='utf-8'))
        value = dict(schema=1, kind='beads.role.result', binding=request['binding'], artifacts=[], findings=[])
        Path(sys.argv[3]).write_text(json.dumps(value), encoding='utf-8')
        if mode == 'role-change-source-input':
            Path(sys.argv[6]).write_bytes(b'changed immutable source input')
        elif mode == 'role-dev-delta':
            (Path(sys.argv[4]) / 'owned.txt').write_bytes(b'legitimate DEV delta')
        elif mode == 'role-change-accepted-artifact':
            Path(sys.argv[6]).write_bytes(b'changed accepted artifact')
    elif mode == 'flood':
        os.write(1, b'a'*200000)
        os.write(2, b'b'*200000)
    elif mode == 'handle':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        written = wintypes.DWORD()
        # The harmless private sentinel is owned by this test. A successful
        # write means an unrelated inheritable file handle leaked into child.
        ok = kernel.WriteFile(int(sys.argv[3]), b'leak', 4, ctypes.byref(written), None)
        raise SystemExit(1 if ok else 0)
    elif mode == 'supervisor':
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from task_tower.windows_job import WindowsJobProcess
        process = WindowsJobProcess([sys.executable, __file__, 'tree', str(root)], root,
                                    sys.stdout.buffer, sys.stderr.buffer)
        deadline = time.monotonic() + .8
        while not (root / 'grandchild-ready').exists() and time.monotonic() < deadline:
            time.sleep(.01)
        # Deliberately bypass finally/close: the OS must close the noninherited
        # job handle on actual supervisor death and kill its tree.
        os._exit(23)
    elif mode in ('tree', 'child'):
        child = subprocess.Popen([sys.executable, __file__, 'child' if mode == 'tree' else 'grandchild', str(root)])
        (root / (mode+'-ready')).write_bytes(b'ready')
        try:
            time.sleep(1.1)
            (root / (mode+'-escaped')).write_bytes(b'escaped')
            child.wait(timeout=1.5)
        finally:
            if child.poll() is None:
                child.terminate()  # Only the live handle created immediately above.
                child.wait(timeout=1)
    elif mode == 'grandchild':
        (root / 'grandchild-ready').write_bytes(b'ready')
        time.sleep(1.1)
        (root / 'grandchild-escaped').write_bytes(b'escaped')
    else:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
