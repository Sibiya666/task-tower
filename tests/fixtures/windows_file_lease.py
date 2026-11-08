"""Read-only Windows fixture handle that deliberately withholds delete sharing."""
import ctypes
from ctypes import wintypes
import os


class DeleteLease:
    def __init__(self, path):
        if os.name != 'nt':
            raise RuntimeError('Windows fixture only')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
            wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
            wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateFileW(str(path), 0x80000000, 3,
                                              None, 3, 0x80, None)
        if self.handle in (None, ctypes.c_void_p(-1).value):
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
