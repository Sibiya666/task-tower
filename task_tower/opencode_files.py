"""Bounded read-only host metadata; no native OpenCode state is opened here."""
import hashlib
import os
from pathlib import Path
import re
import stat


def safe_path(value):
    if not isinstance(value,str) or not value or '\x00' in value or not Path(value).is_absolute():
        raise ValueError('invalid_path')
    path=Path(os.path.abspath(value))
    if str(path)!=value or any(part in ('.','..') for part in Path(value).parts):
        raise ValueError('invalid_path')
    for part in (path,*path.parents):
        try: info=part.lstat()
        except FileNotFoundError: continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('unsafe_path')
    return path


def identity(info):
    kind='file' if stat.S_ISREG(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else None
    reparse=stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&0x400)
    if kind is None or reparse or type(info.st_dev) is not int or not 0<=info.st_dev<2**128 or type(info.st_ino) is not int or not 0<info.st_ino<2**128:
        raise ValueError('unsupported_identity')
    return dict(device=str(info.st_dev),file_id=str(info.st_ino),kind=kind,reparse=False)


def validate_identity(value, *, kind=None):
    if not isinstance(value,dict) or set(value)!={'device','file_id','kind','reparse'}:
        raise ValueError('invalid_identity')
    for name in ('device','file_id'):
        item=value[name]
        if not isinstance(item,str) or not re.fullmatch('0|[1-9][0-9]{0,38}',item) or int(item)>=2**128:
            raise ValueError('invalid_identity')
    if value['kind'] not in ('file','directory') or type(value['reparse']) is not bool or value['reparse'] or kind is not None and value['kind']!=kind:
        raise ValueError('invalid_identity')
    return value


def _open_readonly(path):
    if os.name!='nt':
        if not hasattr(os,'O_NOFOLLOW'):raise ValueError('unsupported_safe_open')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|getattr(os,'O_CLOEXEC',0))
    else:
        import ctypes as C
        from ctypes import wintypes as W
        import msvcrt
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
        kernel.CreateFileW.restype=W.HANDLE
        kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
        handle=kernel.CreateFileW(str(path),0x80000000,1,None,3,0x00200000,None)
        if handle==C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
        try: fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    try: os.set_inheritable(fd,False)
    except BaseException:
        os.close(fd)
        raise
    return fd


def forbidden_state_path(value):
    path=Path(value);name=path.name.casefold()
    return bool(name in {'auth.json','kv.json','credentials.json','accounts.json','sessions.json'}
                or re.fullmatch(r'.*\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm|journal))?',name)
                or any(part.casefold() in {'storage','credentials','accounts','sessions'} for part in path.parts[:-1]))


def read_bound(value, *, limit, expected=None, private_roots=(), utf8=False):
    """Hash/parse callers consume these same verified bytes, never reopen them."""
    path=safe_path(value)
    if forbidden_state_path(path):
        raise ValueError('forbidden_native_state')
    if any(path.is_relative_to(safe_path(str(root))) for root in private_roots):
        raise ValueError('private_artifact_collision')
    before=path.lstat(); first=identity(before)
    if first['kind']!='file' or before.st_nlink!=1 or before.st_size>limit:
        raise ValueError('unsafe_file')
    fd=_open_readonly(path)
    try:
        opened=os.fstat(fd)
        if identity(opened)!=first or opened.st_nlink!=1 or opened.st_size!=before.st_size:
            raise ValueError('file_identity_changed')
        pieces=[]; size=0
        while size<=limit:
            chunk=os.read(fd,min(65536,limit+1-size))
            if not chunk: break
            pieces.append(chunk);size+=len(chunk)
        data=b''.join(pieces)
        after=os.fstat(fd); current=safe_path(str(path)).lstat()
        if (len(data)!=before.st_size or len(data)>limit or identity(after)!=first or identity(current)!=first
                or after.st_nlink!=1 or current.st_nlink!=1 or after.st_size!=before.st_size or current.st_size!=before.st_size
                or after.st_mtime_ns!=opened.st_mtime_ns or current.st_mtime_ns!=opened.st_mtime_ns):
            raise ValueError('file_changed')
        digest=hashlib.sha256(data).hexdigest()
        if expected is not None and digest!=expected: raise ValueError('file_digest_mismatch')
        if utf8: data.decode('utf-8',errors='strict')
        return data
    finally: os.close(fd)


def digest_executable(value,expected):
    """Stream a bounded native artifact; retain no executable bytes or output."""
    path=safe_path(value)
    if path.suffix.casefold() not in ('','.exe') or path.stem.casefold() in {'sh','bash','zsh','cmd','powershell','pwsh','node','bun','python','python3'}:
        raise ValueError('unsupported_executable_wrapper')
    before=path.lstat();ident=identity(before)
    if ident['kind']!='file' or before.st_nlink!=1 or not 0<before.st_size<=536870912:
        raise ValueError('unsupported_executable_artifact')
    fd=_open_readonly(path)
    try:
        opened=os.fstat(fd)
        if identity(opened)!=ident or opened.st_size!=before.st_size or opened.st_nlink!=1: raise ValueError('artifact_changed')
        digest=hashlib.sha256();size=0
        while size<=before.st_size:
            chunk=os.read(fd,min(1048576,before.st_size+1-size))
            if not chunk:break
            digest.update(chunk);size+=len(chunk)
        after=os.fstat(fd);current=safe_path(str(path)).lstat()
        if size!=before.st_size or identity(after)!=ident or identity(current)!=ident or after.st_nlink!=1 or current.st_nlink!=1 or after.st_size!=size or current.st_size!=size or after.st_mtime_ns!=opened.st_mtime_ns or current.st_mtime_ns!=opened.st_mtime_ns or digest.hexdigest()!=expected:
            raise ValueError('artifact_changed')
        return dict(identity=ident,bytes=size,sha256=digest.hexdigest())
    finally:os.close(fd)
