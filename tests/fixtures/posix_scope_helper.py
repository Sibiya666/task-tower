"""Trusted helper fixture, with actual nested native role and private receipts."""
import json
import os
from pathlib import Path
import sys
import signal
import subprocess
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from task_tower import processes, posix_scope

root, scope_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]


def body():
    if mode == 'crash':
        os._exit(23)
    if mode == 'ignored-child':
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        try:
            processes.run_command([sys.executable, '-c', 'pass'], root, 2)
        except ValueError:
            root.joinpath('ignored-child-rejected').write_text('rejected')
        return 0
    if mode == 'worker-thread':
        def worker():
            try:
                processes.run_command([sys.executable, '-c', 'pass'], root, 2)
            except ValueError:
                root.joinpath('worker-rejected').write_text('rejected')
        thread = threading.Thread(target=worker)
        thread.start(); thread.join(2)
        if thread.is_alive():
            raise AssertionError('Owned worker did not stop')
        return 0
    if mode == 'legacy-shape':
        argv = [sys.executable, '-c', 'print("private stream")']
        actual = processes.run_command(argv, root, 2)
        missing = processes.run_command(['task-tower-unavailable-native-fixture'], root, 2)
        root.joinpath('legacy-results.json').write_text(json.dumps(dict(actual=actual,missing=missing)))
        return 0
    if mode == 'before-launch':
        os.kill(os.getpid(), signal.SIGTERM)
    if mode == 'launch-signal':
        original = posix_scope.subprocess.Popen
        def launch(*args, **kwargs):
            process = original(*args, **kwargs)
            root.joinpath('launched-pid').write_text(str(process.pid))
            os.kill(os.getpid(), signal.SIGTERM)
            return process
        posix_scope.subprocess.Popen = launch
    role = '''import json,os,signal,time,subprocess,sys
from pathlib import Path
root=Path(%r)
start=subprocess.check_output(['/bin/ps','-p',str(os.getpid()),'-o','lstart='],text=True).strip()
root.joinpath('role.json').write_text(json.dumps(dict(pid=os.getpid(),ppid=os.getppid(),pgid=os.getpgid(0),sid=os.getsid(0),start=start,term_blocked=signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK,[]))))
subprocess.Popen([sys.executable,'-c',"import time;from pathlib import Path;time.sleep(.6);Path("+repr(str(root/'escaped'))+").write_text('escaped')"])
time.sleep(%r)
''' % (str(root), 20)
    if mode == 'normal':
        role = 'pass'
    if mode == 'stolen-reap':
        role = 'pass'
        observe, killpg = posix_scope._exited, os.killpg
        reaped = set()
        def steal(process, remaining):
            process.wait(timeout=remaining)
            reaped.add(process.pid)
            return observe(process, remaining)
        def guarded_kill(pid, number):
            if pid in reaped:
                root.joinpath('unsafe-kill').write_text(str(pid))
                raise AssertionError('Reaped group identity signalled')
            return killpg(pid, number)
        posix_scope._exited, os.killpg = steal, guarded_kill
    if mode == 'wrong-stop-nonce':
        scope = posix_scope.active_scope()
        attest = scope.attest
        def wrong_nonce(kind):
            attest(kind)
            path = posix_scope.receipt_path(root / 'result.json')
            value = json.loads(path.read_text())
            value['stop_nonce'] = '00000000-0000-4000-8000-000000000000'
            posix_scope._atomic(path, value)
        scope.attest = wrong_nonce
    kwargs = {}
    if mode == 'capture':
        capture = root / 'capture'; capture.mkdir()
        kwargs = dict(cancel_requested=lambda: False,
                      capture=dict(directory=capture, max_bytes_per_stream=1024))
    if mode == 'callback-error':
        def broken():
            if (root / 'role.json').exists():
                raise ValueError('private callback failure')
            return False
        kwargs = dict(cancel_requested=broken)
    if mode == 'crash-after-launch':
        def crash():
            if (root / 'role.json').exists():
                os._exit(23)
            return False
        kwargs = dict(cancel_requested=crash)
    processes.run_command([sys.executable, '-c', role], root, 30, **kwargs)
    root.joinpath('after-role').write_text('must not finalize an interrupted role')
    return 0


raise SystemExit(posix_scope.run_helper(body, scope_id, root / 'result.json'))
