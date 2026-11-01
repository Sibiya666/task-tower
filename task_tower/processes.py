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

