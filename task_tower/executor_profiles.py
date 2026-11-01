"""Installation-owned executor policy; task input cannot extend this authority."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

from .project_connections import safe_config_path


def profile_fingerprint(profile):
    """Canonical policy digest, also used for the pinned instruction manifest."""
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode('utf-8')).hexdigest()


def child_environment(environ):
    return {key: value for key, value in environ.items()
            if key.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN')}


def _path(value, *, directory=False):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('Executor paths must be absolute')
    path = Path(os.path.abspath(value))
    # safe_config_path also checks every ancestor for links/junctions.
    safe_config_path(path / '.executor-path-check' if directory else path)
    if path.exists():
        if directory and not path.is_dir():
            raise ValueError('Invalid executor directory')
        if not directory and path.stat().st_nlink != 1:
            raise ValueError('Hardlinked executor file')
    return path


def _private(path, checkouts):
    if any(path.resolve().is_relative_to(checkout.resolve()) for checkout in checkouts):
        raise ValueError('Executor private state must be outside checkouts')


def _integer(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('Invalid executor limit')
    return value


def _pins(value):
    if not isinstance(value, dict) or set(value) != {'root', 'revision', 'manifest', 'manifest_sha256'}:
        raise ValueError('Invalid Superpowers pin')
    root = _path(value['root'], directory=True)
    if not root.is_dir() or not isinstance(value['revision'], str) or not re.fullmatch('[0-9a-f]{40}', value['revision']):
        raise ValueError('Invalid Superpowers revision')
    manifest = value['manifest']
    if not isinstance(manifest, dict) or not manifest or profile_fingerprint(manifest) != value['manifest_sha256']:
        raise ValueError('Invalid Superpowers manifest')
    for name, expected in manifest.items():
        if (not isinstance(name, str) or '\\' in name or ':' in name or
                PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') for p in name.split('/')) or
                not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)):
            raise ValueError('Invalid Superpowers manifest entry')
        path = _path(str(root / name))
        text = path.read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        if hashlib.sha256(text.encode('utf-8')).hexdigest() != expected:
            raise ValueError('Superpowers instruction drift')
    return dict(value, root=str(root))


def load_executor_config(path, connections):
    """Validate strict v1 policy and return JSON-safe normalized dictionaries.

    Profiles are keyed by installation ID; allowlist rows bind a repository Issue,
    task ID and runner to one such profile. No environment or model policy exists.
    """
    try:
        path = _path(str(path))
        checkouts = [c.checkout for c in connections]
        _private(path, checkouts)
        value = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(value, dict) or set(value) - {'version','profiles','allowlist','max_active'} or
                not {'version','profiles','allowlist'} <= set(value) or type(value['version']) is not int or value['version'] != 1):
            raise ValueError('Invalid executor configuration')
        maximum = _integer(value.get('max_active', 2), 2)
        if not isinstance(value['profiles'], dict) or not isinstance(value['allowlist'], list):
            raise ValueError('Invalid executor configuration')
        normalized = {}
        directories = []
        required = {'kind','repository','checkout','runner_label','argv','source_ref','timeout_seconds',
                    'log_max_bytes','max_attempts','runs_dir','superpowers'}
        for name, raw in value['profiles'].items():
            if not isinstance(name,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',name):
                raise ValueError('Invalid executor profile identity')
            if not isinstance(raw,dict) or not required <= set(raw) or set(raw) - required - {'trusted','approve_for_me'}:
                raise ValueError('Invalid executor profile')
            profile = dict(raw, trusted=raw.get('trusted',False), approve_for_me=raw.get('approve_for_me',False))
            if profile['kind'] not in ('codex','custom') or type(profile['trusted']) is not bool or type(profile['approve_for_me']) is not bool:
                raise ValueError('Invalid executor trust policy')
            if profile['kind']=='custom' and (not profile['trusted'] or profile['approve_for_me']):
                raise ValueError('Custom executor requires explicit trust')
            matches=[c for c in connections if c.repository.casefold()==str(profile['repository']).casefold()]
            checkout=_path(profile['checkout'],directory=True)
            if len(matches)!=1 or checkout != matches[0].checkout or profile['runner_label'] != matches[0].runner_label:
                raise ValueError('Executor connection mismatch')
            profile['repository']=matches[0].repository
            profile['checkout']=str(checkout)
            argv=profile['argv']
            if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a or '\x00' in a for a in argv):
                raise ValueError('Invalid executor argv')
            executable=_path(argv[0])
            if not executable.is_file() or (profile['kind'] == 'codex' and len(argv) != 1):
                raise ValueError('Invalid executor executable policy')
            profile['argv']=[str(executable),*argv[1:]]
            ref=profile['source_ref']
            if not isinstance(ref,str) or not (re.fullmatch('[0-9a-f]{40}',ref) or re.fullmatch(r'refs/(heads|tags)/[A-Za-z0-9][A-Za-z0-9_./-]*',ref)) or '..' in ref or ref.endswith(('/', '.')):
                raise ValueError('Invalid executor source ref')
            for field,bound in [('timeout_seconds',86400),('log_max_bytes',67108864),('max_attempts',10)]:
                _integer(profile[field],bound)
            runs=_path(profile['runs_dir'],directory=True)
            _private(runs,checkouts)
            if path.is_relative_to(runs) or any(runs.is_relative_to(other) or other.is_relative_to(runs) for other in directories):
                raise ValueError('Executor private path collision')
            directories.append(runs)
            profile['runs_dir']=str(runs)
            profile['superpowers']=_pins(profile['superpowers'])
            if runs.is_relative_to(Path(profile['superpowers']['root'])) or Path(profile['superpowers']['root']).is_relative_to(runs):
                raise ValueError('Executor instruction/output collision')
            normalized[name]=profile
        seen=set()
        for row in value['allowlist']:
            if not isinstance(row,dict) or set(row)!={'repository','issue','task_id','runner_label','profile'}:
                raise ValueError('Invalid executor allowlist')
            profile=normalized.get(row['profile']) if isinstance(row['profile'],str) else None
            if (profile is None or type(row['issue']) is not int or row['issue']<1 or
                    not isinstance(row['task_id'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,199}',row['task_id']) or
                    row['repository']!=profile['repository'] or row['runner_label']!=profile['runner_label']):
                raise ValueError('Invalid executor allowlist binding')
            identity=(row['repository'].casefold(),row['issue'])
            if identity in seen: raise ValueError('Duplicate executor authorization')
            seen.add(identity)
        return dict(version=1,max_active=maximum,profiles=normalized,allowlist=value['allowlist'])
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('Invalid executor configuration') from None
