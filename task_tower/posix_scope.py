"""Private, opt-in ownership receipts for fixed trusted POSIX host helpers.

Groups remain signalable only while their Popen leader is an unreaped child.
This is process-group containment, not an OS sandbox for hostile setsid code.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid


_scope = None


class TrustedScopeStopped(BaseException):
    """Leave an interrupted action intent unfinished, after child cleanup."""


class _OwnershipLost(OSError):
    """Our child was reaped elsewhere; its numeric identity is no longer owned."""


def active_scope():
    return _scope


def receipt_path(result_path):
    return Path(str(result_path) + '.scope-receipt')


def request_path(result_path):
    return Path(str(result_path) + '.scope-request')


def _read(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_size > 4096 or path.is_symlink()):
        raise ValueError('Invalid scope proof')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate scope proof key')
            value[key] = item
        return value
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def _uuid(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value


def _atomic(path, value):
    temporary = path.with_name(path.name + '.' + str(uuid.uuid4()))
    try:
        with temporary.open('x', encoding='utf-8') as file:
            json.dump(value, file, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def valid_receipt(result_path, scope_id, pid, kind, stop_nonce=None):
    try:
        value = _read(receipt_path(result_path))
        return (isinstance(value, dict)
                and set(value) == {'version', 'scope_id', 'pid', 'kind', 'stop_nonce'}
                and type(value['version']) is int and value['version'] == 1
                and _uuid(value['scope_id']) and value['scope_id'] == scope_id
                and type(value['pid']) is int and value['pid'] == pid
                and value['kind'] == kind and kind in ('completed', 'stopped')
                and value['stop_nonce'] == stop_nonce
                and (stop_nonce is None if kind == 'completed' else _uuid(stop_nonce)))
    except (OSError, ValueError, TypeError, AttributeError):
        return False


class _Scope:
    def __init__(self, scope_id, result_path):
        if not _uuid(scope_id):
            raise ValueError('Invalid helper scope')
        self.scope_id, self.result_path = scope_id, Path(result_path)
        self.stop_requested = self.closed = self.uncertain = False
        self.entries = []

    @contextmanager
    def masked(self):
        if threading.current_thread() is not threading.main_thread():
            self.uncertain = True
            raise ValueError('Trusted helper runner requires main thread')
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try:
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def checkpoint(self):
        if threading.current_thread() is not threading.main_thread():
            self.uncertain = True
            raise ValueError('Trusted helper runner requires main thread')
        if self.closed:
            raise ValueError('Closed helper scope')
        if self.stop_requested:
            raise TrustedScopeStopped()

    def stopped(self, number, frame):
        # Main-thread-only registry; mutations and child reaping mask TERM.
        # No locks, journals, IO receipts or asynchronous exception unwinding.
        self.stop_requested = True
        for entry in self.entries:
            if entry['signalable']:
                try:
                    os.killpg(entry['process'].pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    self.uncertain = True

    def attest(self, kind):
        if self.uncertain or any(not entry['settled'] for entry in self.entries):
            return
        nonce = None
        if kind == 'stopped':
            if not self.stop_requested:
                return
            request = _read(request_path(self.result_path))
            if (not isinstance(request, dict)
                    or set(request) != {'version', 'scope_id', 'pid', 'stop_nonce'}
                    or type(request['version']) is not int or request['version'] != 1
                    or request['scope_id'] != self.scope_id
                    or type(request['pid']) is not int or request['pid'] != os.getpid()
                    or not _uuid(request['stop_nonce'])):
                return
            nonce = request['stop_nonce']
        elif self.stop_requested:
            return
        self.closed = True
        _atomic(receipt_path(self.result_path), dict(version=1,
            scope_id=self.scope_id, pid=os.getpid(), kind=kind, stop_nonce=nonce))


def run_helper(callback, scope_id, result_path):
    """Install before runtime/launch; only fixed helper main commands call this."""
    global _scope
    if (os.name != 'posix' or _scope is not None
            or threading.current_thread() is not threading.main_thread()
            or threading.active_count() != 1
            or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
        raise ValueError('Unsupported trusted helper scope')
    scope = _Scope(scope_id, result_path)
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    previous_handler = signal.getsignal(signal.SIGTERM)
    if signal.SIGTERM in previous_mask:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        raise ValueError('Helper inherited blocked termination')
    _scope = scope
    try:
        signal.signal(signal.SIGTERM, scope.stopped)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        try:
            result = callback()
            scope.checkpoint()
        except TrustedScopeStopped:
            try:
                scope.attest('stopped')
            except (OSError, ValueError, TypeError):
                pass
            return 1
        scope.attest('completed')
        return result
    finally:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        scope.closed = True
        _scope = None
        signal.signal(signal.SIGTERM, previous_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def _exited(process, remaining):
    """Observe only our unreaped child; never poll()/wait() here."""
    if remaining <= 0:
        raise subprocess.TimeoutExpired('owned child observation', 0)
    if sys.platform == 'darwin':
        observed = subprocess.run(['/bin/ps', '-p', str(process.pid), '-o', 'stat='],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=min(.25, remaining), check=False)
        if observed.returncode == 1 and not observed.stdout.strip():
            raise _OwnershipLost('Owned child no longer observable')
        if observed.returncode or not observed.stdout.strip():
            raise OSError('Owned child observation unavailable')
        return observed.stdout.strip().startswith(b'Z')
    if not all(hasattr(os, key) for key in ('waitid', 'WNOWAIT', 'P_PID', 'WEXITED')):
        raise OSError('Nonreaping child observation unavailable')
    try:
        return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    except ChildProcessError as error:
        raise _OwnershipLost('Owned child was reaped elsewhere') from error


def _deadline(cooperative):
    deadline = time.monotonic() + 5
    if cooperative is not None:
        earlier = cooperative.get('cleanup_deadline')
        if earlier is not None:
            earlier = earlier() if callable(earlier) else earlier
            if earlier is not None:
                deadline = min(deadline, earlier)
    return deadline


def run_command(argv, cwd, timeout_seconds, env, *, cancel_requested, capture,
                cooperative=None):
    """Internal scoped implementation; unopted and Windows runners stay intact."""
    from . import processes
    import shutil
    scope = active_scope()
    if scope is not None:
        scope.checkpoint()
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        if scope is not None:
            scope.uncertain = True
        raise ValueError('Trusted runner requires unreaped child ownership')
    started = time.monotonic()
    result = dict(status='unavailable', exit_code=None, started=False,
                  cleanup_confirmed=True, pid=None)
    logs, cap = processes._capture_files(capture)
    drains, writers, process, entry = [], [], None, None
    stop_nonce = None
    observed_exit = False

    @contextmanager
    def masked():
        if scope is None:
            yield
        else:
            with scope.masked():
                yield

    def check_cancel():
        if scope is not None:
            scope.checkpoint()
        cancelled = cancel_requested is not None and cancel_requested()
        if scope is not None:
            scope.checkpoint()
        return cancelled

    def exited(remaining):
        with masked():
            try:
                return _exited(process, remaining)
            except _OwnershipLost:
                entry['signalable'] = False
                raise

    try:
        if check_cancel():
            result['status'] = 'cancelled'
            return result
        executable = shutil.which(argv[0], path=env.get('PATH') if env is not None else None)
        if not executable:
            return result
        if Path(executable).suffix.lower() in ('.cmd', '.bat'):
            result['reason'] = 'shell_script_requires_explicit_interpreter'
            return result
        actual = [executable, *argv[1:]]
        with masked():
            if scope is not None:
                scope.checkpoint()
            for log in logs:
                read_fd, write_fd = os.pipe()
                writers.append(os.fdopen(write_fd, 'wb', buffering=0))
                drains.append(processes._Drain(os.fdopen(read_fd, 'rb', buffering=0), log, cap))
            invocation = actual if scope is None else [sys.executable,
                str(Path(__file__).with_name('posix_exec.py')), *actual]
            process = subprocess.Popen(invocation, cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=writers[0], stderr=writers[1], start_new_session=True, env=env)
            entry = dict(process=process, signalable=True, settled=False)
            if scope is not None:
                scope.entries.append(entry)
            result.update(started=True, pid=int(process.pid))
        for writer in writers:
            writer.close()
        deadline = time.monotonic() + timeout_seconds
        while True:
            if check_cancel():
                result['status'] = 'cancelled'
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result['status'] = 'timeout'
                break
            if exited(remaining):
                observed_exit = True
                result['status'] = 'passed'  # Actual code is read only after owned group kill.
                break
            time.sleep(min(.05, remaining))
    except TrustedScopeStopped:
        result['status'] = 'cancelled'
    except (OSError, ValueError, subprocess.SubprocessError):
        result['status'] = 'unknown' if process is not None else 'unavailable'
        if scope is not None:
            scope.uncertain = True
    except Exception:
        result['status'] = 'unknown'
        if scope is not None:
            scope.uncertain = True
    finally:
        cleanup_deadline = _deadline(cooperative)
        if process is not None:
            try:
                if cooperative is not None and not observed_exit:
                    stop_nonce = str(uuid.uuid4())
                    _atomic(request_path(Path(cooperative['result_path'])), dict(version=1,
                        scope_id=cooperative['scope_id'], pid=process.pid, stop_nonce=stop_nonce))
                    os.kill(process.pid, signal.SIGTERM)
                    # Reserve cleanup time; four seconds is only a maximum grace.
                    grace = min(time.monotonic() + 4, cleanup_deadline - .5)
                    while time.monotonic() < grace:
                        if exited(grace - time.monotonic()):
                            observed_exit = True
                            break
                        time.sleep(min(.01, max(0, grace - time.monotonic())))
                with masked():
                    # Leader is still unreaped: its group identity cannot be reused.
                    if not entry['signalable']:
                        raise _OwnershipLost('Owned group identity no longer signalable')
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finally:
                        entry['signalable'] = False
                    result['exit_code'] = process.wait(timeout=max(0,
                        cleanup_deadline - time.monotonic()))
                if observed_exit and result['status'] == 'passed':
                    result['status'] = 'passed' if result['exit_code'] == 0 else 'failed'
                if cooperative is not None:
                    kind = 'completed' if stop_nonce is None else 'stopped'
                    if not valid_receipt(cooperative['result_path'], cooperative['scope_id'],
                                         process.pid, kind, stop_nonce):
                        result.update(status='cleanup_failed', cleanup_confirmed=False)
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                result.update(status='cleanup_failed', cleanup_confirmed=False)
                # A proof/TERM/observer failure must still kill the owned unreaped
                # group. Never reuse its number after any successful wait.
                if process.returncode is None and entry['signalable']:
                    with masked():
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                            entry['signalable'] = False
                            result['exit_code'] = process.wait(timeout=max(0,
                                cleanup_deadline - time.monotonic()))
                        except (OSError, subprocess.SubprocessError):
                            pass
        for writer in writers:
            writer.close()
        for drain in drains:
            drain.thread.join(max(0, cleanup_deadline - time.monotonic()))
        for name, drain in zip(('stdout', 'stderr'), drains):
            result[name + '_sha256'] = drain.digest.hexdigest()
            result[name + '_bytes'] = drain.size
            result[name + '_captured_bytes'] = drain.saved
            result[name + '_tail_unknown'] = not drain.complete
            result[name + '_truncated'] = drain.size > drain.saved or not drain.complete
            if not drain.complete:
                result.update(status='cleanup_failed', cleanup_confirmed=False)
        if not drains:
            for log in logs:
                if log is not None:
                    log.close()
        if scope is not None and entry is not None:
            entry['settled'] = (result['cleanup_confirmed'] and process.returncode is not None)
            scope.uncertain |= not entry['settled']
        result['duration_seconds'] = round(time.monotonic() - started, 3)
    if scope is not None:
        scope.checkpoint()
    return result
