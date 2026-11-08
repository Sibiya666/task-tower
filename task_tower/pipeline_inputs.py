"""Host-owned canonical product snapshots and fenced Git checkpoints.

The v2 text scheme deliberately does not change the legacy tasks._hash contract.
"""
import codecs
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import time

from .executor_profiles import child_environment
from .project_connections import safe_config_path

ARTIFACT_LIMIT = 1024 * 1024
BLOB_LIMIT = 16 * 1024 * 1024
MANIFEST_LIMIT = 16 * 1024 * 1024


class _CheckpointDirectory(tempfile.TemporaryDirectory):
    """Finish actual private-index cleanup after a transient Windows read lease."""
    def __init__(self, parent, guard):
        self._checkpoint_parent = Path(parent).absolute()
        self._checkpoint_guard = guard
        super().__init__(dir=parent)
        info = Path(self.name).lstat()
        self._checkpoint_identity = (info.st_dev, info.st_ino)

    def _same_directory(self):
        path = Path(self.name)
        if not path.is_absolute() or path.parent != self._checkpoint_parent:
            raise ValueError('Changed checkpoint cleanup directory')
        safe_config_path(path / '.cleanup-path-check')
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if (not stat.S_ISDIR(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400
                or (info.st_dev, info.st_ino) != self._checkpoint_identity):
            raise ValueError('Changed checkpoint cleanup directory')
        return True

    def cleanup(self):
        try:
            return super().cleanup()
        except PermissionError as error:
            # No best-effort success or generic permission-error retry. Actual
            # runtime callers supply the existing authority/cancel/deadline guard.
            if getattr(error, 'winerror', None) != 32 or not callable(self._checkpoint_guard):
                raise
            deadline = time.monotonic() + 5
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise error
                time.sleep(min(.01, remaining))
                self._checkpoint_guard()
                if time.monotonic() >= deadline:
                    raise error
                if not self._same_directory():
                    return
                if time.monotonic() >= deadline:
                    raise error
                try:
                    return super().cleanup()
                except PermissionError as next_error:
                    if getattr(next_error, 'winerror', None) != 32:
                        raise
                    error = next_error


def canonical_text(data: bytes) -> bytes:
    return data.decode('utf-8', errors='strict').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')


def canonical_artifact(data: bytes) -> bytes:
    if data.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Designated artifact must be BOM-free UTF-8')
    return canonical_text(data)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest_manifest(value: dict) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '\x00' in value or PurePosixPath(value).is_absolute()
            or any(p in ('', '.', '..') for p in value.rstrip('/').split('/'))
            or any(p.casefold() == '.git' for p in value.split('/'))):
        raise ValueError('Unsafe product path')
    for part in value.rstrip('/').split('/'):
        if part.endswith((' ','.')) or any(ord(c)<32 or ord(c)==127 or c in '<>"|?*' for c in part) or re.fullmatch(r'(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])',part.split('.')[0]):
            raise ValueError('Nonportable product path')
    return value


def _ordinary(path):
    safe_config_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unsafe product file')
    return info


def _git_environment():
    # No caller-selected Git directory, index, config injection or alternate
    # object database may redirect a host operation.
    return {key:value for key,value in child_environment(os.environ).items()
            if not key.upper().startswith('GIT_')}


def _git(root, *args, env=None, data=None):
    result = subprocess.run(['git', '-c', 'core.quotePath=false', '-C', str(root), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=_git_environment() if env is None else env, check=False)
    if result.returncode:
        raise ValueError('Checkpoint Git operation failed')
    return result.stdout


def _repository(root, policy):
    root = Path(root)
    safe_config_path(root / '.pipeline-path-check')
    if not root.is_dir() or Path(os.fsdecode(_git(root, 'rev-parse', '--show-toplevel')).strip()).resolve() != root.resolve():
        raise ValueError('Unexpected worktree identity')
    git_dir = Path(os.fsdecode(_git(root, 'rev-parse', '--absolute-git-dir')).strip())
    safe_config_path(git_dir / '.pipeline-path-check')
    if not git_dir.is_dir():
        raise ValueError('Unexpected Git directory')
    dotgit = root / '.git'
    if dotgit.is_file():
        _ordinary(dotgit)
        if not policy.get('git_dir') or Path(policy['git_dir']).resolve() != git_dir.resolve():
            raise ValueError('External Git directory is not bound')
    elif not dotgit.is_dir() or git_dir.resolve() != dotgit.resolve():
        raise ValueError('Unexpected external Git directory')
    if policy.get('git_dir') and Path(policy['git_dir']).resolve() != git_dir.resolve():
        raise ValueError('Git directory changed')
    if policy.get('expected_head') and _git(root, 'rev-parse', 'HEAD').decode().strip() != policy['expected_head']:
        raise ValueError('Unexpected HEAD change')
    if policy.get('branch') and _git(root, 'symbolic-ref', '--quiet', 'HEAD').decode().strip() != 'refs/heads/' + policy['branch']:
        raise ValueError('Unexpected branch change')
    if policy.get('refs_sha256') and hashlib.sha256(_git(root, 'show-ref')).hexdigest() != policy['refs_sha256']:
        raise ValueError('Unexpected ref change')
    return root


def _matches(path, entries):
    return any(path.startswith(entry) if entry.endswith('/') else path == entry for entry in entries)


def _is_card(path):
    return re.fullmatch(r'docs/tasks/[^/]+\.json', path) is not None


def _blob(path, designated=False):
    info = _ordinary(path)
    limit = ARTIFACT_LIMIT if designated else BLOB_LIMIT
    if info.st_size > limit:
        raise ValueError(f'size_limit:{path.name}:{limit}')
    # Stream raw hashes, including non-text assets; retain at most the bounded text
    # candidate for strict decoding and newline normalization.
    raw = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    candidate = []
    is_text = True
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            raw.update(chunk)
            if is_text:
                try:
                    text = decoder.decode(chunk, final=False)
                    if any(ord(c) < 32 and c not in '\t\r\n' or ord(c) == 127 for c in text):
                        is_text = False
                except UnicodeDecodeError:
                    is_text = False
                if is_text:
                    candidate.append(chunk)
                else:
                    candidate.clear()
        if is_text:
            try:
                decoder.decode(b'', final=True)
            except UnicodeDecodeError:
                is_text = False
    after = _ordinary(path)
    if after.st_size != info.st_size or after.st_mtime_ns != info.st_mtime_ns or (after.st_dev,after.st_ino)!=(info.st_dev,info.st_ino):
        raise ValueError('Product changed while hashing')
    if designated:
        if not is_text:
            raise ValueError('Designated artifact must be UTF-8 text')
        canonical = canonical_artifact(b''.join(candidate))
    elif not is_text:
        return 'sha256-bytes-v1', raw.hexdigest()
    else:
        canonical = canonical_text(b''.join(candidate))
    if len(canonical) > limit:
        raise ValueError(f'size_limit:{path.name}:{limit}')
    return 'sha256-utf8-lf-v2', hashlib.sha256(canonical).hexdigest()


def product_manifest(worktree: Path, task_policy: dict) -> dict:
    root = _repository(worktree, task_policy)
    allowed = [_relative(p) for p in task_policy['allowed_paths']]
    if len({p.casefold().rstrip('/') for p in allowed})!=len(allowed): raise ValueError('Allowed path alias')
    evidence = _relative(task_policy['evidence_dir'])
    if not evidence.endswith('/'):
        raise ValueError('Evidence must be a directory prefix')
    designated = {_relative(task_policy[k]) for k in ('spec_path', 'plan_path')}
    if task_policy.get('criteria_path'):
        designated.add(_relative(task_policy['criteria_path']))
    source = task_policy.get('source_sha')
    if not isinstance(source, str) or not re.fullmatch('[a-f0-9]{40}', source):
        raise ValueError('Missing initial source SHA')
    _git(root, 'cat-file', '-e', source + '^{commit}')
    # Include deletions and staged changes; NUL-delimited names preserve spaces.
    changed = set(filter(None, os.fsdecode(_git(root, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--name-only', '-z', source, '--')).split('\0')))
    changed.update(filter(None, os.fsdecode(_git(root, 'ls-files', '--others', '--exclude-standard', '-z')).split('\0')))
    host_evidence = task_policy.get('_host_evidence', {})
    if not isinstance(host_evidence,dict) or '_host_evidence' in task_policy and not host_evidence:
        raise ValueError('Invalid host evidence attestation')
    if len({p.casefold() for p in host_evidence})!=len(host_evidence): raise ValueError('Evidence path alias')
    for name,digest in host_evidence.items():
        _relative(name)
        if not name.startswith(evidence) or not name.endswith('.md') or not _matches(name,allowed) or _is_card(name) or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Invalid host evidence path or digest')
        if _blob(root/name,True)[1]!=digest: raise ValueError('Host evidence content mismatch')
    changed_evidence={p for p in changed if p.startswith(evidence)}
    if changed_evidence!=set(host_evidence): raise ValueError('Unattested evidence mutation')
    for name in changed:
        _relative(name)
        if _is_card(name):
            raise ValueError('Host-owned card mutation')
        if name.startswith(evidence): continue
        if not _matches(name, allowed):
            raise ValueError('Product change outside allowed_paths')
    tracked = {}
    for entry in _git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, oid, stage = header.decode('ascii').split(' ')
        path = os.fsdecode(name)
        _relative(path)
        if stage != '0' or mode not in ('100644', '100755'):
            raise ValueError('Submodule, link or unmerged product entry')
        tracked[path] = mode
    names = set(tracked)
    names.update(filter(None, os.fsdecode(_git(root, 'ls-files', '--others', '--exclude-standard', '-z')).split('\0')))
    for name in designated:
        if (root/name).exists() and name not in names: raise ValueError('Ignored required artifact')
    if len({p.casefold() for p in names})!=len(names): raise ValueError('Product path alias')
    if len(names) > 100000:
        raise ValueError('size_limit:manifest:100000')
    files = []
    for name in sorted(names):
        _relative(name)
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue  # deletion is represented by absence in this complete snapshot
        info = _ordinary(path)
        if _is_card(name) or name.startswith(evidence):
            continue
        scheme, digest = _blob(path, name in designated)
        mode = ('100755' if info.st_mode & 0o111 else '100644') if os.name!='nt' else tracked.get(name,'100644')
        files.append(dict(path=name, mode=mode, scheme=scheme, sha256=digest))
    result = dict(version=1, files=files)
    if len(canonical_json(result)) > MANIFEST_LIMIT:
        raise ValueError('size_limit:manifest:16777216')
    return result


STAGE_FIELDS = {'version','repository','issue','issue_id','task_id','run_id','stage','generation',
    'source_sha','base_sha','checkpoint_sha','product_sha256','criteria_sha256','spec_sha256',
    'plan_sha256','prior_verdict_sha256','policy_sha256','superpowers_sha256','checks_sha256'}


def stage_manifest(run: dict, checkpoint: dict, *, stage: str, generation: int,
                   prior_receipt: dict | None, checks: dict | None) -> dict:
    if stage not in ('spec','development','test') or type(generation) is not int or generation < 1:
        raise ValueError('Invalid stage binding')
    result = {key: run[key] for key in ('repository','issue','issue_id','task_id','run_id',
        'source_sha','base_sha','criteria_sha256','policy_sha256','superpowers_sha256')}
    result.update(version=1,stage=stage,generation=generation,
        checkpoint_sha=checkpoint['checkpoint_sha'],product_sha256=checkpoint['product_sha256'],
        spec_sha256=checkpoint.get('spec_sha256'),plan_sha256=checkpoint.get('plan_sha256'),
        prior_verdict_sha256=None if prior_receipt is None else prior_receipt['receipt_sha256'],
        checks_sha256=None if checks is None else digest_manifest(checks))
    validate_stage_manifest(result)
    return result


def validate_stage_manifest(value):
    from .executor_queue import _uuid
    if not isinstance(value, dict) or set(value) != STAGE_FIELDS or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid stage manifest')
    _uuid(value['run_id'])
    if value['stage'] not in ('spec','development','test') or type(value['generation']) is not int or value['generation'] < 1:
        raise ValueError('Invalid stage generation')
    if type(value['issue']) is not int or value['issue'] < 1 or type(value['issue_id']) is not int or value['issue_id'] < 1:
        raise ValueError('Invalid stage identity')
    for key in ('source_sha','base_sha','checkpoint_sha'):
        if not isinstance(value[key],str) or not re.fullmatch('[a-f0-9]{40}',value[key]): raise ValueError('Invalid commit SHA')
    nullable = {'spec_sha256','plan_sha256','prior_verdict_sha256','checks_sha256'}
    for key in ('product_sha256','criteria_sha256','spec_sha256','plan_sha256','prior_verdict_sha256','policy_sha256','superpowers_sha256','checks_sha256'):
        if key in nullable and value[key] is None: continue
        if not isinstance(value[key],str) or not re.fullmatch('[a-f0-9]{64}',value[key]): raise ValueError('Invalid manifest digest')
    return value


def freeze_checkpoint(run: dict, task_policy: dict, journal, owner_id: str) -> dict:
    """One normal output commit; unresolved intents never replay."""
    return _freeze_checkpoint(run,task_policy,journal,owner_id)


def freeze_rework_checkpoint(run: dict, task_policy: dict, journal, owner_id: str,
                             failed_attempt_id: str) -> dict:
    """Preserve actual dirty failed output as rework, never as accepted output."""
    journal._rework_proof(run['run_id'],owner_id,failed_attempt_id)
    if '_host_evidence' in task_policy: raise ValueError('Rework cannot publish evidence')
    return _freeze_checkpoint(run,task_policy,journal,owner_id,failed_attempt_id)


def _freeze_checkpoint(run,task_policy,journal,owner_id,failed_attempt_id=None):
    """Shared private-index implementation for host-owned checkpoint effects."""
    saved=journal.status(run['run_id'])
    for key in ('state','stage','generation','input_sha256','source_sha','base_sha','checkpoint_sha','worktree','git_dir'):
        if type(saved[key]) is not type(run.get(key)) or saved[key]!=run.get(key): raise ValueError('Stale checkpoint run binding')
    if saved['owner_id']!=owner_id: raise ValueError('Foreign checkpoint owner')
    if '_host_evidence' in task_policy and run['state']!='publishing':
        raise ValueError('Host evidence requires publication action')
    parent = run.get('checkpoint_sha') or run['source_sha']
    branch = 'pipeline/' + run['run_id']
    policy = dict(task_policy, source_sha=run['source_sha'], expected_head=parent, branch=branch)
    if run.get('git_dir'): policy['git_dir'] = run['git_dir']
    root = _repository(Path(run['worktree']), policy)
    manifest = product_manifest(root, policy)
    product_digest = digest_manifest(manifest)
    host_evidence=task_policy.get('_host_evidence',{})
    evidence_manifest=None
    if host_evidence:
        if run.get('manifest',{}).get('product_sha256')!=product_digest:
            raise ValueError('Publication product differs from accepted input')
        evidence_manifest=dict(version=1,run_id=run['run_id'],task_id=run['task_id'],product_sha256=product_digest,
            files=[dict(path=p,scheme='sha256-utf8-lf-v2',sha256=host_evidence[p]) for p in sorted(host_evidence)])
    evidence_digest=None if evidence_manifest is None else digest_manifest(evidence_manifest)
    private = journal.path.parent / ('checkpoint-' + run['run_id'])
    safe_config_path(private / '.safe')
    private.mkdir(parents=True, exist_ok=True)
    if private.resolve().is_relative_to(root.resolve()): raise ValueError('Private index inside worktree')
    hooks = private / 'hooks'
    hooks.mkdir(exist_ok=True)
    safe_config_path(hooks / '.safe')
    if list(hooks.iterdir()): raise ValueError('Hooks directory must be empty')
    with _CheckpointDirectory(private, task_policy.get('_before_effect')) as temp:
        index = Path(temp) / 'index'
        env = _git_environment()
        env.update(GIT_INDEX_FILE=str(index),GIT_AUTHOR_NAME='Task Tower',GIT_AUTHOR_EMAIL='task-tower@localhost',
            GIT_COMMITTER_NAME='Task Tower',GIT_COMMITTER_EMAIL='task-tower@localhost')
        prefix = ('-c','core.hooksPath='+str(hooks),'-c','commit.gpgSign=false')
        _git(root,*prefix,'read-tree',parent,env=env)
        source_files = {os.fsdecode(x) for x in _git(root,'ls-tree','-r','--name-only','-z',parent).split(b'\0') if x}
        product_paths = {r['path'] for r in manifest['files']}
        # Private index preserves unchanged host cards/evidence from the parent.
        remove = sorted(p for p in source_files - product_paths if not _is_card(p) and not p.startswith(policy['evidence_dir']))
        for name in remove: _git(root,*prefix,'update-index','--force-remove','--',name,env=env)
        for record in manifest['files']:
            name = record['path']
            # hash-object bypasses clean filters and external diff drivers;
            # no model-controlled .gitattributes command is launched.
            oid = _git(root,*prefix,'hash-object','-w','--no-filters','--',name,env=env).decode().strip()
            _git(root,*prefix,'update-index','--add','--cacheinfo',record['mode'],oid,name,env=env)
        for name in sorted(host_evidence):
            oid=_git(root,*prefix,'hash-object','-w','--no-filters','--',name,env=env).decode().strip()
            _git(root,*prefix,'update-index','--add','--cacheinfo','100644',oid,name,env=env)
        tree = _git(root,*prefix,'write-tree',env=env).decode().strip()
        message = 'Task Tower ' + ('publication ' if host_evidence else 'checkpoint ') + run['run_id']
        contributors=[a for a in journal.history(run['run_id'])['attempts']
            if a['stage']==run['stage'] and a['role']==run['stage']+'_executor']
        contributing = contributors[-1]['attempt_id'] if not host_evidence and contributors and contributors[-1]['state']=='completed' else None
        intent=dict(kind='commit',parent=parent,tree=tree,message=message,branch=branch,
            contributing_executor_attempt_id=contributing,evidence_manifest_sha256=evidence_digest)
        if failed_attempt_id is not None:
            intent.update(kind='rework_commit',failed_attempt_id=failed_attempt_id,contributing_executor_attempt_id=None)
        before=task_policy.get('_before_effect')
        if before is not None:
            if not callable(before):raise ValueError('Invalid host effect guard')
            before()
        effect = journal.begin_effect(run['run_id'],owner_id,intent)
        # Every effect below is fenced by the committed intent above. Exceptions
        # intentionally leave it unresolved for observation-only recovery.
        if before is not None:before()
        commit = _git(root,*prefix,'commit-tree',tree,'-p',parent,env=env,data=(message+'\n').encode()).decode().strip()
        if _git(root,'rev-parse',commit+'^{tree}').decode().strip()!=tree or _git(root,'rev-parse',commit+'^').decode().strip()!=parent:
            raise ValueError('Unexpected checkpoint object')
        _repository(root,policy)
        if digest_manifest(product_manifest(root,policy)) != product_digest:
            raise ValueError('Checkpoint product changed')
        if before is not None:before()
        _git(root,*prefix,'update-ref','refs/heads/'+branch,commit,parent,env=env)
        if _git(root,'rev-parse','HEAD').decode().strip()!=commit:
            raise ValueError('Checkpoint ref observation mismatch')
        journal.finish_effect(effect['effect_id'],owner_id,dict(status='completed',commit_sha=commit,tree_sha=tree))
    result=dict(source_sha=run['source_sha'],base_sha=run['base_sha'],checkpoint_sha=commit,product_sha256=product_digest,manifest=manifest,evidence_manifest_sha256=evidence_digest)
    for key in ('spec_path','plan_path'):
        path=root/task_policy[key]
        result[key.replace('_path','_sha256')]=_blob(path,True)[1] if path.exists() else None
    return result





