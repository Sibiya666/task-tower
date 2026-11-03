"""Bounded argument-array commands; raw output never enters JSON reports."""

import hashlib
import errno
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time


def _digest(file):
    file.seek(0)
    digest, size = hashlib.sha256(), 0
    while chunk := file.read(65536):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def run_command(argv, cwd, timeout_seconds, env=None):
    started = time.monotonic()
    result = {"argv": argv, "status": "unavailable", "exit_code": None}
    executable = shutil.which(argv[0], path=env.get("PATH") if env is not None else None)
    if not executable:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        return result
    actual = [executable, *argv[1:]]
    # .cmd/.bat cannot be executed directly without implicit shell parsing.
    if Path(executable).suffix.lower() in (".cmd", ".bat"):
        result["reason"] = "shell_script_requires_explicit_interpreter"
        return result
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = None
        timeout_group_reaped = False
        try:
            if os.name == "nt":
                from .windows_job import WindowsJobProcess
                process = WindowsJobProcess(actual, cwd, stdout, stderr, env=env)
            else:
                process = subprocess.Popen(actual, cwd=cwd, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True, env=env)
            try:
                code = process.wait(timeout_seconds)
                result.update(status="passed" if code == 0 else "failed", exit_code=code)
            except subprocess.TimeoutExpired:
                result["status"] = "timeout"
                if os.name == "nt":
                    process.terminate()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                result["exit_code"] = process.wait(5)
                timeout_group_reaped = os.name != "nt"
        except OSError:
            result["status"] = "unavailable"
        finally:
            if process is not None:
                try:
                    if os.name == "nt":
                        process.close()  # Kill descendants even if the parent already exited.
                    else:
                        retry_deadline = None
                        while True:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                                break
                            except ProcessLookupError:
                                break
                            except PermissionError as error:
                                if (sys.platform != "darwin" or not timeout_group_reaped
                                        or error.errno != errno.EPERM):
                                    raise
                                # Darwin can retain a zombie-only group after SIGKILL
                                # and report EPERM until its last child is reaped.
                                if retry_deadline is None:
                                    retry_deadline = time.monotonic() + .5
                                remaining = retry_deadline - time.monotonic()
                                if remaining <= 0:
                                    raise
                                time.sleep(min(.01, remaining))
                        process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    result["status"] = "cleanup_failed"
            for name, file in (("stdout", stdout), ("stderr", stderr)):
                result[name + "_sha256"], result[name + "_bytes"] = _digest(file)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


# Optional executor mode keeps raw output bounded in storage and memory.
class _Drain:
    def __init__(self, reader, log, cap):
        import threading
        self.reader, self.log, self.cap = reader, log, cap
        self.digest, self.size, self.saved = hashlib.sha256(), 0, 0
        self.complete = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            while chunk := self.reader.read(65536):
                self.digest.update(chunk)
                self.size += len(chunk)
                if self.log is not None and self.saved < self.cap:
                    part = chunk[:self.cap - self.saved]
                    self.log.write(part)
                    self.saved += len(part)
            self.complete = True
        except (OSError, ValueError):
            pass
        finally:
            self.reader.close()
            if self.log is not None:
                self.log.close()


def _capture_files(capture):
    if capture is None:
        return [None, None], 0
    if (not isinstance(capture, dict) or set(capture) != {'directory', 'max_bytes_per_stream'}
            or type(capture['max_bytes_per_stream']) is not int
            or not 0 < capture['max_bytes_per_stream'] <= 1024 * 1024 * 1024):
        raise ValueError('invalid_capture')
    directory = Path(capture['directory']).absolute()
    for path in (directory, *directory.parents):
        try:
            info = path.lstat()
        except OSError as error:
            raise ValueError('unsafe_capture_directory') from error
        reparse = (getattr(info, 'st_file_attributes', 0)
                   & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if path.is_symlink() or reparse:
            raise ValueError('unsafe_capture_directory')
    if not directory.is_dir():
        raise ValueError('unsafe_capture_directory')
    paths = [directory / (name + '.log') for name in ('stdout', 'stderr')]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError('capture_exists')
    logs = []
    try:
        for path in paths:
            logs.append(path.open('xb', buffering=0))
    except OSError as error:
        for log in logs:
            log.close()
        raise ValueError('capture_unavailable') from error
    return logs, capture['max_bytes_per_stream']


_legacy_run_command = run_command


def _stdin_storage():
    """Private anonymous storage with a separately read-only transport handle."""
    import tempfile
    def cleanup(error, callbacks):
        """Attempt every owner; never replace the construction failure."""
        confirmed = getattr(error, 'stdin_cleanup_confirmed', True)
        for callback in callbacks:
            try:
                callback()
            except BaseException:
                confirmed = False
        if not confirmed:
            error.stdin_cleanup_confirmed = False
    def stream(fd, mode):
        try:
            return os.fdopen(fd, mode, buffering=0)
        except BaseException as error:
            cleanup(error, [lambda: os.close(fd)])
            raise
    if os.name != 'nt':
        fd, name = tempfile.mkstemp(prefix='task-tower-stdin-')
        read_fd = writer = reader = None
        try:
            read_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0))
            os.unlink(name)
            owned, fd = fd, None
            writer = stream(owned, 'w+b')
            owned, read_fd = read_fd, None
            reader = stream(owned, 'rb')
            return writer, reader
        except BaseException as error:
            callbacks = [lambda raw=raw: os.close(raw) for raw in (fd, read_fd) if raw is not None]
            callbacks.extend(opened.close for opened in (writer, reader) if opened is not None)
            def unlink():
                try:
                    os.unlink(name)
                except FileNotFoundError:
                    pass
            callbacks.append(unlink)
            cleanup(error, callbacks)
            raise
    import ctypes as C
    from ctypes import wintypes as W
    import msvcrt
    import secrets
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.DuplicateHandle.argtypes = [W.HANDLE, W.HANDLE, W.HANDLE, C.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD]
    kernel.DuplicateHandle.restype = W.BOOL
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL
    name = str(Path(tempfile.gettempdir()) / ('task-tower-stdin-' + secrets.token_hex(24)))
    # CREATE_NEW, share-read only, temporary + delete-on-last-close.
    handle = kernel.CreateFileW(name, 0xc0010000, 1, None, 1, 0x04000100, None)
    if handle == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    read_handle = W.HANDLE()
    writer = reader = None
    try:
        owner = kernel.GetCurrentProcess()
        if not kernel.DuplicateHandle(owner, handle, owner, C.byref(read_handle), 0x00120089, False, 0):
            raise C.WinError(C.get_last_error())
        fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
        handle = None
        writer = stream(fd, 'w+b')
        fd = msvcrt.open_osfhandle(read_handle.value, os.O_RDONLY | os.O_BINARY)
        read_handle = W.HANDLE()
        reader = stream(fd, 'rb')
        os.set_inheritable(writer.fileno(), False)
        os.set_inheritable(reader.fileno(), False)
        return writer, reader
    except BaseException as error:
        callbacks = [opened.close for opened in (writer, reader) if opened is not None]
        def close_handle(raw):
            if not kernel.CloseHandle(raw):
                raise C.WinError(C.get_last_error())
        if handle:
            callbacks.append(lambda: close_handle(handle))
        if read_handle.value:
            callbacks.append(lambda: close_handle(read_handle))
        cleanup(error, callbacks)
        raise


def _stage_stdin(spec):
    """Verify mutable source bytes before exposing an anonymous read-only copy."""
    import re
    from .opencode_files import safe_path, identity, validate_identity, _open_readonly
    source = writer = reader = None
    try:
        if (not isinstance(spec, dict) or set(spec) != {'path', 'expected_sha256', 'expected_bytes', 'expected_identity'}
                or type(spec['expected_bytes']) is not int or not 0 <= spec['expected_bytes'] <= 4194304
                or not isinstance(spec['expected_sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', spec['expected_sha256'])):
            raise ValueError('stdin_binding_mismatch')
        expected = validate_identity(spec['expected_identity'], kind='file')
        path = safe_path(spec['path'])
        before = path.lstat()
        if identity(before) != expected or before.st_nlink != 1 or before.st_size != spec['expected_bytes']:
            raise ValueError('stdin_binding_mismatch')
        source = _open_readonly(path)
        opened = os.fstat(source)
        if identity(opened) != expected or opened.st_nlink != 1 or opened.st_size != spec['expected_bytes']:
            raise ValueError('stdin_binding_mismatch')
        writer, reader = _stdin_storage()
        digest, size = hashlib.sha256(), 0
        while size <= spec['expected_bytes']:
            chunk = os.read(source, min(65536, spec['expected_bytes'] + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            if writer.write(chunk) != len(chunk):
                raise ValueError('stdin_binding_mismatch')
        after, current = os.fstat(source), safe_path(spec['path']).lstat()
        if (size != spec['expected_bytes'] or digest.hexdigest() != spec['expected_sha256']
                or any(identity(info) != expected or info.st_nlink != 1 or info.st_size != size
                       or info.st_mtime_ns != opened.st_mtime_ns for info in (after, current))):
            raise ValueError('stdin_binding_mismatch')
        writer.close()
        writer = None
        os.close(source)
        source = None
        reader.seek(0)
        result, reader = reader, None
        return result
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        failure = ValueError('stdin_binding_mismatch')
        failure.stdin_cleanup_confirmed = getattr(error, 'stdin_cleanup_confirmed', True)
        raise failure from None
    finally:
        cleanup_error = False
        if source is not None:
            try:
                os.close(source)
            except OSError:
                cleanup_error = True
        for stream in (writer, reader):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    cleanup_error = True
        if cleanup_error:
            failure = ValueError('stdin_binding_mismatch')
            failure.stdin_cleanup_confirmed = False
            raise failure from None


def run_command(argv, cwd, timeout_seconds, env=None, *, cancel_requested=None, capture=None, stdin_spec=None):
    """Capture schema: {directory: private existing dir, max_bytes_per_stream: int}.

    Optional mode omits argv. Stream hashes/counts cover observed bytes, with
    tail_unknown set unless EOF was proved; .log files contain capped prefixes.
    The caller validates installation/checkouts exclusion of the directory.
    """
    if cancel_requested is None and capture is None and stdin_spec is None:
        return _legacy_run_command(argv, cwd, timeout_seconds, env)
    started = time.monotonic()
    result = dict(status='unavailable', exit_code=None, started=False, cleanup_confirmed=True, pid=None)
    logs, cap = _capture_files(capture)
    drains, writers, process, staged = [], [], None, None
    try:
        try:
            cancelled = cancel_requested is not None and cancel_requested()
        except Exception:
            result['status'] = 'unknown'
            return result
        if cancelled:
            result['status'] = 'cancelled'
            return result
        if stdin_spec is not None:
            try:
                staged = _stage_stdin(stdin_spec)
            except (OSError, ValueError) as error:
                result['reason'] = 'stdin_binding_mismatch'
                if not getattr(error, 'stdin_cleanup_confirmed', True):
                    result.update(status='cleanup_failed', cleanup_confirmed=False)
                return result
        executable = shutil.which(argv[0], path=env.get('PATH') if env is not None else None)
        if not executable:
            return result
        if Path(executable).suffix.lower() in ('.cmd', '.bat'):
            result['reason'] = 'shell_script_requires_explicit_interpreter'
            return result
        for log in logs:
            read_fd, write_fd = os.pipe()
            reader = os.fdopen(read_fd, 'rb', buffering=0)
            writers.append(os.fdopen(write_fd, 'wb', buffering=0))
            drains.append(_Drain(reader, log, cap))
        actual = [executable, *argv[1:]]
        if os.name == 'nt':
            from .windows_job import WindowsJobProcess
            process = WindowsJobProcess(actual, cwd, *writers, env=env, stdin=staged) if staged is not None else WindowsJobProcess(actual, cwd, *writers, env=env)
        else:
            process = subprocess.Popen(actual, cwd=cwd, stdin=staged if staged is not None else subprocess.DEVNULL,
                                       stdout=writers[0], stderr=writers[1],
                                       start_new_session=True, env=env)
        result.update(started=True, pid=int(process.pid))
        if staged is not None:
            transport, staged = staged, None
            try:
                transport.close()
            except OSError:
                result.update(status='cleanup_failed', cleanup_confirmed=False)
                return result
        for writer in writers:
            writer.close()
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                if cancel_requested is not None and cancel_requested():
                    result['status'] = 'cancelled'
                    break
            except Exception:
                result['status'] = 'unknown'
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result['status'] = 'timeout'
                break
            try:
                code = process.wait(min(.25, remaining))
                result.update(status='passed' if code == 0 else 'failed', exit_code=code)
                break
            except subprocess.TimeoutExpired:
                pass
    except OSError:
        result['status'] = 'unavailable' if process is None else 'unknown'
    finally:
        if staged is not None:
            try:
                staged.close()
            except OSError:
                result.update(status='cleanup_failed', cleanup_confirmed=False)
        cleanup_deadline = time.monotonic() + 5
        if process is not None:
            try:
                if os.name == 'nt':
                    if result['exit_code'] is None:
                        process.terminate()
                    # Wait before closing process handle, then kill remaining descendants.
                    result['exit_code'] = process.wait(max(.001, cleanup_deadline-time.monotonic()))
                    process.close()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    result['exit_code'] = process.wait(timeout=max(.001, cleanup_deadline-time.monotonic()))
            except (OSError, subprocess.TimeoutExpired):
                result.update(status='cleanup_failed', cleanup_confirmed=False)
                if os.name == 'nt':
                    try:
                        process.close()
                    except OSError:
                        pass
        for writer in writers:
            writer.close()
        for drain in drains:
            drain.thread.join(max(0, cleanup_deadline-time.monotonic()))
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
        result['duration_seconds'] = round(time.monotonic() - started, 3)
    return result
