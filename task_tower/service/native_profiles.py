"""Exact executable identities and native version fences, from operator config only."""
import copy
import hashlib
from pathlib import Path
import re
import time
from ..project_connections import safe_config_path
from .beads import ServiceError


def verify_binary(path,digest,deadline=None):
    path=safe_config_path(Path(path));h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):
            if deadline is not None and time.monotonic()>=deadline:raise ServiceError('native_deadline')
            h.update(chunk)
    if h.hexdigest()!=digest:raise ServiceError('native_binary_changed')


def profiles(projects,configured):
    if not isinstance(configured,dict) or set(configured)-set(projects):raise ValueError('invalid_native_profiles')
    result=copy.deepcopy(configured)
    for p,v in result.items():
        if (not isinstance(v,dict) or set(v)-{'history_reader'}!={'executable','version','sha256','history'}
                or not isinstance(v['executable'],str) or not Path(v['executable']).is_absolute()
                or not isinstance(v['version'],str) or re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',v['version']) is None
                or not isinstance(v['sha256'],str) or re.fullmatch('[0-9a-f]{64}',v['sha256']) is None
                or v['history'] not in ('events-v1','unavailable','dolt-server-events-v1')):
            raise ValueError('invalid_native_profile')
        if (v['history']=='dolt-server-events-v1')!=('history_reader' in v):raise ValueError('invalid_history_reader')
        if (v['history']=='events-v1' and v['version']!='1.3.4') or (v['history']=='dolt-server-events-v1' and v['version']!='1.0.2'):
            raise ValueError('unsupported_native_history_version')
        if 'history_reader' in v:
            from .dolt_events import validate_reader
            validate_reader(v['history_reader'])
    return result


def guard(project,profile,deadline=None):
    try:
        verify_binary(profile['executable'],profile['sha256'],deadline)
        path=safe_config_path(Path(project)/'.beads/.local_version')
        with path.open('rb') as stream:version=stream.read(65)
        if len(version)>64 or version.decode('ascii').strip()!=profile['version']:raise ValueError()
        if profile['history']=='dolt-server-events-v1':
            from .dolt_events import verify_source
            verify_source(project,profile['history_reader'])
    except ServiceError:raise
    except Exception:raise ServiceError('native_version_fence') from None
