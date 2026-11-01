"""Bounded argument-array commands; raw output never enters JSON reports."""

import hashlib
import errno
import os
from pathlib import Path
import shutil
import signal
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
    if any(path.is_symlink() or getattr(path, 'is_junction', lambda: False)()
           for path in (directory, *directory.parents)) or not directory.is_dir():
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


def run_command(argv, cwd, timeout_seconds, env=None, *, cancel_requested=None, capture=None):
    """Capture schema: {directory: private existing dir, max_bytes_per_stream: int}.

    Optional mode omits argv. Stream hashes/counts cover observed bytes, with
    tail_unknown set unless EOF was proved; .log files contain capped prefixes.
    The caller validates installation/checkouts exclusion of the directory.
    """
    if cancel_requested is None and capture is None:
        return _legacy_run_command(argv, cwd, timeout_seconds, env)
    started = time.monotonic()
    result = dict(status='unavailable', exit_code=None, started=False, cleanup_confirmed=True)
    logs, cap = _capture_files(capture)
    drains, writers, process = [], [], None
    try:
        try:
            cancelled = cancel_requested is not None and cancel_requested()
        except Exception:
            result['status'] = 'unknown'
            return result
        if cancelled:
            result['status'] = 'cancelled'
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
            process = WindowsJobProcess(actual, cwd, *writers, env=env)
        else:
            process = subprocess.Popen(actual, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=writers[0], stderr=writers[1],
                                       start_new_session=True, env=env)
        result['started'] = True
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
