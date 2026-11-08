"""Windows disposable test token provisioning, never production credential editing."""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path


def libraries():
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv=C.WinDLL('advapi32',use_last_error=True)
    kernel.GetCurrentProcess.restype=W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    kernel.LocalFree.argtypes=[C.c_void_p];kernel.LocalFree.restype=C.c_void_p
    adv.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)]
    adv.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)]
    adv.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)]
    return kernel,adv


def sid_text(pointer,kernel,adv):
    text=W.LPWSTR()
    if not adv.ConvertSidToStringSidW(pointer,C.byref(text)):raise C.WinError(C.get_last_error())
    try:return text.value
    finally:kernel.LocalFree(text)


def current_sid():
    kernel,adv=libraries();token=W.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,C.byref(token)):raise C.WinError(C.get_last_error())
    try:
        length=W.DWORD();adv.GetTokenInformation(token,1,None,0,C.byref(length))
        data=C.create_string_buffer(length.value)
        if not adv.GetTokenInformation(token,1,data,length,C.byref(length)):raise C.WinError(C.get_last_error())
        return sid_text(C.c_void_p.from_buffer(data).value,kernel,adv)
    finally:kernel.CloseHandle(token)


def provision(path,text,*,write=None):
    raw=text.encode('ascii');path=Path(path)
    kernel,adv=libraries();descriptor=C.c_void_p()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p]
    sid=current_sid()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW('O:'+sid+'D:P(A;;FA;;;'+sid+')',1,C.byref(descriptor),None):
        raise C.WinError(C.get_last_error())
    class Attributes(C.Structure):
        _fields_=[('length',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
    attributes=Attributes(C.sizeof(Attributes),descriptor,False)
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.POINTER(Attributes),W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype=W.HANDLE
    kernel.WriteFile.argtypes=[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p]
    handle=None;created=False;complete=False
    try:
        # CREATE_NEW, share=0, private protected DACL atomically at creation.
        handle=kernel.CreateFileW(str(path),0x40000000,0,C.byref(attributes),1,0x80,None)
        if handle==C.c_void_p(-1).value:handle=None;raise C.WinError(C.get_last_error())
        created=True;written=W.DWORD();buffer=C.create_string_buffer(raw)
        if not (write or kernel.WriteFile)(handle,buffer,len(raw),C.byref(written),None) or written.value!=len(raw):
            raise OSError('incomplete disposable token write')
        complete=True
    finally:
        if handle is not None:kernel.CloseHandle(handle)
        kernel.LocalFree(descriptor)
        if created and not complete:path.unlink()


def security(path):
    kernel,adv=libraries();owner=C.c_void_p();dacl=C.c_void_p();descriptor=C.c_void_p()
    adv.GetNamedSecurityInfoW.argtypes=[W.LPWSTR,C.c_int,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(C.c_void_p)]
    adv.GetSecurityDescriptorControl.argtypes=[C.c_void_p,C.POINTER(W.WORD),C.POINTER(W.DWORD)]
    adv.GetAce.argtypes=[C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)]
    code=adv.GetNamedSecurityInfoW(str(path),1,5,C.byref(owner),None,C.byref(dacl),None,C.byref(descriptor))
    if code:raise C.WinError(code)
    try:
        control=W.WORD();revision=W.DWORD()
        if not adv.GetSecurityDescriptorControl(descriptor,C.byref(control),C.byref(revision)):raise C.WinError(C.get_last_error())
        if not dacl.value:raise OSError('missing DACL')
        trustees=[]
        for index in range(C.c_ushort.from_address(dacl.value+4).value):
            ace=C.c_void_p()
            if not adv.GetAce(dacl,index,C.byref(ace)):raise C.WinError(C.get_last_error())
            if C.c_ubyte.from_address(ace.value).value!=0:raise OSError('unexpected ACE type')
            trustees.append(sid_text(ace.value+8,kernel,adv))
        return sid_text(owner,kernel,adv),bool(control.value&0x1000),trustees
    finally:kernel.LocalFree(descriptor)


if __name__=='__main__':
    provision(os.environ['TOWER_TEST_TOKEN_PATH'],os.environ['TOWER_TEST_TOKEN_TEXT'])
