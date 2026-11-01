"""Windows command lifetime: assign suspended process to kill-on-close job."""

import ctypes as C
from ctypes import wintypes as W
import math
import msvcrt
import os
import subprocess


class _BasicLimit(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong),
                ("flags", W.DWORD), ("min_working_set", C.c_size_t),
                ("max_working_set", C.c_size_t), ("active_process_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class _IoCounters(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in (
        "read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class _ExtendedLimit(C.Structure):
    _fields_ = [("basic", _BasicLimit), ("io", _IoCounters),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class _StartupInfo(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR),
                ("title", W.LPWSTR), ("x", W.DWORD), ("y", W.DWORD),
                ("xsize", W.DWORD), ("ysize", W.DWORD), ("xchars", W.DWORD),
                ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD),
                ("reserved_bytes", C.POINTER(C.c_ubyte)), ("stdin", W.HANDLE),
                ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class _ProcessInfo(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]


def _kernel():
    kernel = C.WinDLL("kernel32", use_last_error=True)
    declarations = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL,
                            W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(_StartupInfo),
                            C.POINTER(_ProcessInfo)], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
    }
    for name, (args, result) in declarations.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


class WindowsJobProcess:
    def __init__(self, argv, cwd, stdout, stderr):
        self.kernel = kernel = _kernel()
        self.info = _ProcessInfo()
        self.job = kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise C.WinError(C.get_last_error())
        try:
            limits = _ExtendedLimit()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)):
                raise C.WinError(C.get_last_error())
            with open(os.devnull, "rb") as stdin:
                files = [stdin, stdout, stderr]
                handles = [msvcrt.get_osfhandle(file.fileno()) for file in files]
                old_inheritance = [os.get_handle_inheritable(handle) for handle in handles]
                startup = _StartupInfo()
                startup.cb, startup.flags = C.sizeof(startup), 0x100
                startup.stdin, startup.stdout, startup.stderr = handles
                try:
                    for handle in handles:
                        os.set_handle_inheritable(handle, True)
                    command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
                    # No command runs before successful assignment to the job.
                    if not kernel.CreateProcessW(argv[0], command, None, None, True,
                                                 0x08000004, None, str(cwd),
                                                 C.byref(startup), C.byref(self.info)):
                        raise C.WinError(C.get_last_error())
                finally:
                    for handle, old in zip(handles, old_inheritance):
                        os.set_handle_inheritable(handle, old)
            if not kernel.AssignProcessToJobObject(self.job, self.info.process):
                raise C.WinError(C.get_last_error())
            if kernel.ResumeThread(self.info.thread) == 0xFFFFFFFF:
                raise C.WinError(C.get_last_error())
        except BaseException:
            if self.info.process:
                kernel.TerminateProcess(self.info.process, 1)
                kernel.WaitForSingleObject(self.info.process, 5000)
            self.close()
            raise

    def wait(self, timeout):
        outcome = self.kernel.WaitForSingleObject(self.info.process, min(
            math.ceil(timeout * 1000), 0xFFFFFFFE))
        if outcome == 0x102:
            raise subprocess.TimeoutExpired("command", timeout)
        if outcome != 0:
            raise C.WinError(C.get_last_error())
        code = W.DWORD()
        if not self.kernel.GetExitCodeProcess(self.info.process, C.byref(code)):
            raise C.WinError(C.get_last_error())
        return C.c_int(code.value).value

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.job, 1):
            raise C.WinError(C.get_last_error())

    def close(self):
        errors = []
        for owner, field in ((self, "job"), (self.info, "thread"), (self.info, "process")):
            handle = getattr(owner, field)
            if handle:
                if not self.kernel.CloseHandle(handle):
                    errors.append(C.get_last_error())
                setattr(owner, field, None)
        if errors:
            raise C.WinError(errors[0])
