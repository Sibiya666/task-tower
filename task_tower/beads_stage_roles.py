"""Host-owned stage invocation and provenance; model declarations grant no rights.

RoleAuthority is an in-memory trust boundary, constructed only by the coordinator
after independent verification of operator approval and backend containment. It
does not read approvals from model/profile JSON, claim tasks, or qualify a backend.
No installed backend has been qualified merely by importing this module.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Callable, TypedDict

from . import beads_admission as admission
from .processes import run_command
from .project_connections import safe_config_path

LIMIT = 65536
CAPTURE_LIMIT = 8 * 1024 * 1024
SOURCE_INPUT_LIMIT = 16 * 1024 * 1024
ARTIFACT_INPUT_LIMIT = 16 * 1024 * 1024
# Capture standard-library code once: instance/class overrides cannot become
# supervisor callbacks, and an Event subclass may carry arbitrary behavior.
_EVENT_TYPE = threading.Event
_EVENT_IS_SET = threading.Event.is_set
_ATTEMPT = threading.local()
ROLE_MAP = {
    'spec_author': ('spec_output', 'spec_artifacts_only'),
    'spec_acceptor': ('review_readonly', 'review_result_only'),
    'dev_implementer': ('dev_owned', 'owned_source_and_result'),
    'dev_acceptor': ('review_readonly', 'review_result_only'),
    'test_executor': ('test_sandbox', 'disposable_test_and_result'),
    'test_acceptor': ('review_readonly', 'review_result_only'),
}
VARIANTS = {'spec_output', 'dev_owned', 'review_readonly', 'test_sandbox'}
CRITERIA = {'title', 'description', 'design', 'acceptance_criteria', 'notes'}
BINDING = {'task', 'session_id', 'run_id', 'attempt_id', 'instance_id', 'actor', 'stage',
           'policy_digest', 'input_digest', 'superpowers_digest', 'base', 'head', 'tree',
           'diff_digest', 'accepted_artifacts'}


class Artifact(TypedDict):
    name: str
    sha256: str


class SourceSnapshot(TypedDict):
    base: str
    head: str
    tree: str
    diff_digest: str
    files: list[Artifact]
    manifest_sha256: str
    git_config_digest: str
    index_digest: str


class RoleBinding(TypedDict):
    task: str
    session_id: str
    run_id: str
    attempt_id: str
    instance_id: str
    actor: str
    stage: str
    policy_digest: str
    input_digest: str
    superpowers_digest: str
    base: str
    head: str
    tree: str
    diff_digest: str
    accepted_artifacts: list[Artifact]


class RoleRequest(TypedDict):
    schema: int
    kind: str
    binding: RoleBinding
    role: str
    criteria: dict[str, str]
    source_manifest: SourceSnapshot | Artifact
    output_names: list[str]


class RoleVariant(TypedDict):
    argv: list[str]
    containment_contract: str
    prerequisite_sha256: str


class RolePermission(TypedDict):
    variant: str
    write_contract: str


class RoleProfile(TypedDict):
    schema: int
    executable: str
    executable_sha256: str
    request_schema: int
    result_schema: int
    superpowers: list[dict[str, str]]
    variants: dict[str, RoleVariant]
    roles: dict[str, RolePermission]
    qualification_approval_reference: str
    production_qualification_sha256: str | None


class RoleResult(TypedDict):
    schema: int
    kind: str
    binding: RoleBinding
    artifacts: list[Artifact]
    findings: list[str]


class ReviewResult(RoleResult):
    verdict: str
    reviewed: list[Artifact]


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _require(condition):
    if not condition:
        raise ValueError('invalid_role_contract')


def _cancelled(event):
    _require(event is None or type(event) is _EVENT_TYPE)
    value = _EVENT_IS_SET(event) if event is not None else False
    _require(type(value) is bool)
    return value


def _check_cancel(event):
    _require(not _cancelled(event))
    remaining_budget(30*60)


@contextmanager
def attempt_budget(deadline,clock=None):
    """Live host-only scope; child requests/JSON cannot create an attempt budget."""
    _require(type(deadline) in (int,float) and math.isfinite(deadline) and callable(clock or time.monotonic))
    prior=getattr(_ATTEMPT,'value',None)
    _ATTEMPT.value=(deadline,clock or time.monotonic)
    try:
        yield
    finally:
        _ATTEMPT.value=prior


def remaining_budget(limit):
    value=getattr(_ATTEMPT,'value',None)
    remaining=limit if value is None else min(limit,value[0]-value[1]()-5)
    _require(type(remaining) in (int,float) and math.isfinite(remaining) and remaining>0)
    return remaining


def within_scope(path,prefix):
    """Compare Windows relative paths without changing their actual spelling."""
    path,prefix=path.casefold(),prefix.casefold()
    return path==prefix or path.startswith(prefix+'/')


class ProcessCleanupUnknown(ValueError):
    """A live supervisor did not prove both process cleanup and stream EOF."""


def _keys(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys))


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def _name(value):
    _require(isinstance(value, str) and 0 < len(value) <= 240 and '\\' not in value)
    parts = value.split('/')
    _require(all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) and p not in {'.', '..'}
                 and not p.endswith(('.', ' ')) and p.casefold() != '.git'
                 and p.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
                     *('COM%d' % i for i in range(1, 10)), *('LPT%d' % i for i in range(1, 10))}
                 for p in parts))
    return value


def _source_name(value):
    """Repository paths have a wider vocabulary than generated artifacts.

    Keep Windows relative-path/device restrictions without excluding ordinary
    Unicode, spaces or brackets used by the actual repository. No normalization
    or lossy round-trip changes the path the host hashes or grants ownership of.
    """
    _require(isinstance(value, str) and 0 < len(value) <= 240 and '\\' not in value)
    reserved = {'CON', 'PRN', 'AUX', 'NUL',
                *(prefix + digit for prefix in ('COM', 'LPT') for digit in '123456789¹²³')}
    for part in value.split('/'):
        _require(bool(part) and part not in {'.', '..'} and not part.endswith(('.', ' '))
                 and part.casefold() != '.git'
                 and not any(char in '<>:"|?*' or ord(char) < 32 or 127 <= ord(char) <= 159
                             or 0xD800 <= ord(char) <= 0xDFFF for char in part)
                 and part.split('.')[0].rstrip(' ').upper() not in reserved)
    _require(len(value.encode('utf-16-le')) <= 480)
    return value


def _file(path, maximum=None):
    path = safe_config_path(path)
    info = path.stat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    if maximum is not None:
        _require(info.st_size <= maximum)
    return path


def _hash_file(path, *, cancel_requested=None):
    _check_cancel(cancel_requested)
    path = _file(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            _check_cancel(cancel_requested)
            h.update(chunk)
    return h.hexdigest()


def _read(path):
    path = _file(path, LIMIT)
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    _require(len(raw) <= LIMIT)
    return admission._json(raw.decode('utf-8'))


def _artifacts(value):
    _require(isinstance(value, list) and len(value) <= 128)
    seen = set()
    for artifact in value:
        _keys(artifact, {'name', 'sha256'})
        name = _name(artifact['name']).casefold()
        _require(name not in seen and _hex(artifact['sha256']))
        seen.add(name)


def _binding(value):
    _keys(value, BINDING)
    for key in BINDING - {'accepted_artifacts'}:
        _require(isinstance(value[key], str) and 0 < len(value[key]) <= 256
                 and not any(ord(c) < 32 for c in value[key]))
    for key in ('policy_digest', 'input_digest', 'superpowers_digest', 'diff_digest'):
        _require(_hex(value[key]))
    for key in ('base', 'head', 'tree'):
        _require(_hex(value[key], 40))
    _require(value['stage'] in {'spec', 'development', 'test'})
    _artifacts(value['accepted_artifacts'])


def validate_role_result(path: Path, binding: dict, *, reviewer: bool,cancel_requested=None) -> dict:
    _check_cancel(cancel_requested)
    """Validate declarations and independently hash output; this is NOT acceptance."""
    _binding(binding)
    value = _read(path)
    _keys(value, {'schema', 'kind', 'binding', 'artifacts', 'findings'} |
          ({'verdict', 'reviewed'} if reviewer else set()))
    _require(type(value['schema']) is int and value['schema'] == 1
             and value['kind'] == 'beads.role.result' and value['binding'] == binding)
    _artifacts(value['artifacts'])
    _require(isinstance(value['findings'], list) and len(value['findings']) <= 128
             and all(isinstance(s, str) and len(s.encode('utf-8')) <= 4096 for s in value['findings']))
    if reviewer:
        _artifacts(value['reviewed'])
        _require(value['verdict'] in {'approve', 'reject', 'needs_input'}
                 and value['reviewed'] == binding['accepted_artifacts'])
    for artifact in value['artifacts']:
        _require(_hash_file(Path(path).parent / artifact['name'],cancel_requested=cancel_requested) == artifact['sha256'])
    return value


def bundle_digest(profile):
    """The two external references cannot recursively contribute to their own pin."""
    return _digest({k: v for k, v in profile.items() if k not in {
        'qualification_approval_reference', 'production_qualification_sha256'}})


def _logical_input_name(value):
    _name(value)
    _require('/' not in value)
    return value


def _snapshot(value):
    _keys(value, {'base', 'head', 'tree', 'diff_digest', 'files', 'manifest_sha256', 'git_config_digest', 'index_digest'})
    for key in ('base', 'head', 'tree'):
        _require(_hex(value[key], 40))
    for key in ('diff_digest', 'manifest_sha256', 'git_config_digest', 'index_digest'):
        _require(_hex(value[key]))
    _require(isinstance(value['files'], list) and len(value['files']) <= 10000)
    names = set()
    for item in value['files']:
        _keys(item, {'name', 'sha256'})
        name = _source_name(item['name']).casefold()
        _require(name not in names and _hex(item['sha256']))
        names.add(name)
    _require(value['manifest_sha256'] == _digest({k:v for k,v in value.items() if k != 'manifest_sha256'}))
    return value


def _read_snapshot_input(path, *, cancel_requested=None):
    _check_cancel(cancel_requested)
    _require(isinstance(path, Path) and path.is_absolute())
    path = _file(path, SOURCE_INPUT_LIMIT)
    with path.open('rb') as stream:
        chunks=[]; size=0
        while chunk:=stream.read(min(65536,SOURCE_INPUT_LIMIT+1-size)):
            _check_cancel(cancel_requested); chunks.append(chunk); size+=len(chunk)
            _require(size<=SOURCE_INPUT_LIMIT)
        raw=b''.join(chunks)
    _require(len(raw) <= SOURCE_INPUT_LIMIT)
    value = _snapshot(admission._json(raw.decode('utf-8')))
    _require(_bytes(value) == raw)
    return value, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ReadOnlySourceInput:
    """Opaque live registration, not an approval or prior accepted artifact.

    Only the exact authority-registered instance can confirm the verifier's
    qualified exposure of this one file read-only, never its parent directory.
    Broader private configuration/evidence exclusions remain mandatory backend
    prerequisites, independently of the wrapper's three current-root checks.
    """
    name: str
    sha256: str
    path: Path


def _read_artifact_input(path, *, cancel_requested=None):
    _check_cancel(cancel_requested)
    _require(isinstance(path, Path) and path.is_absolute())
    path = _file(path, ARTIFACT_INPUT_LIMIT)
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while chunk := stream.read(min(65536, ARTIFACT_INPUT_LIMIT + 1 - size)):
            _check_cancel(cancel_requested)
            size += len(chunk)
            _require(size <= ARTIFACT_INPUT_LIMIT)
            digest.update(chunk)
    return path, digest.hexdigest()


@dataclass(frozen=True)
class AcceptedArtifactInput:
    """Live immutable pin, not acceptance or filesystem-access authority.

    Host registration follows actual process/result/hash validation; proposed
    outputs may be immutable review inputs before independent stage approval.
    Only the same live record
    returned after qualified individual read-only exposure can enter a grant.
    Qualified backends additionally exclude private configuration/database roots.
    """
    name: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class ContainmentGrant:
    """Live backend verification, never deserialized. Verifier must establish
    write prevention/private-access exclusion, not infer it from argv or hashes.
    It binds the complete backend dependencies through prerequisite_sha256.
    owned_paths is host policy, never task text. Lifetime is one actual call.
    """
    bundle_sha256: str
    prerequisite_sha256: str
    source: Path
    output: Path
    evidence: Path
    role: str
    owned_paths: tuple[str, ...] = ()
    source_input: ReadOnlySourceInput | None = None
    accepted_artifacts: tuple[AcceptedArtifactInput, ...] = ()


@dataclass(frozen=True)
class PhaseScope:
    instance_id: str
    owned_paths: tuple[str, ...]


class RoleAuthority:
    """Coordinator-only authority; caller verifies records before construction.

    approvals maps opaque references to exact plan approval records. qualifications
    maps accepted production digests to immutable bundle digests (already host
    verified and independently accepted). containment_verifier is qualified host
    code returning a live ContainmentGrant for exact paths and role. There is no
    permissive default backend, JSON factory, historical receipt or resume route.
    """
    def __init__(self, *, approvals: dict, qualifications: dict,
                 containment_verifier: Callable, accepted_artifact_paths: dict | None = None,
                 source_input_paths: dict[str, Path] | None = None):
        _require(callable(containment_verifier))
        self._approvals = json.loads(json.dumps(approvals))
        self._qualifications = dict(qualifications)
        self._verifier = containment_verifier
        self._artifacts = {}
        self._used = set()
        self._actors = {}
        self._counts = {}
        self._lock = threading.RLock()
        self._phase_scopes = {}
        self._revoked_bundles = set()
        for name, path in (accepted_artifact_paths or {}).items():
            path, sha256 = _read_artifact_input(path)
            self.register_accepted_artifact(name, path, sha256)
        self._source_inputs = {}
        for name, path in (source_input_paths or {}).items():
            self.register_source_input(name, path)

    def register_phase_scope(self, instance_id, owned_paths):
        _name(instance_id)
        _require('/' not in instance_id and type(owned_paths) is tuple and len(owned_paths)<=1000)
        for path in owned_paths: _source_name(path)
        normalized=[p.casefold() for p in owned_paths]
        _require(not any(a==b or a.startswith(b+'/') or b.startswith(a+'/')
            for i,a in enumerate(normalized) for b in normalized[i+1:]))
        with self._lock:
            _require(instance_id not in self._phase_scopes)
            record=PhaseScope(instance_id,owned_paths)
            self._phase_scopes[instance_id]=record
            return record

    def get_phase_scope(self, instance_id):
        with self._lock:
            return self._phase_scopes.get(instance_id)

    def revoke_bundle(self,profile):
        with self._lock:
            self._revoked_bundles.add(bundle_digest(profile))

    def register_accepted_artifact(self, name: str, path: Path,
                                   expected_sha256: str, *, cancel_requested=None) -> AcceptedArtifactInput:
        """Host-only immutable review/stage input registration; no replacement.

        Keep this authority's existing call/instance accounting across stages.
        A validated proposed output may be pinned for its independent reviewer;
        registration never means the stage has been approved.
        """
        _name(name)
        _require(_hex(expected_sha256))
        path, sha256 = _read_artifact_input(path,cancel_requested=cancel_requested)
        _require(sha256 == expected_sha256)
        with self._lock:
            _require(name.casefold() not in {key.casefold() for key in self._artifacts})
            entry = AcceptedArtifactInput(name, path, sha256)
            self._artifacts[name] = entry
            return entry

    def get_accepted_artifact(self, name: str) -> AcceptedArtifactInput:
        """Pure memory lookup, including from the verifier under reserve's RLock."""
        _name(name)
        with self._lock:
            entry = self._artifacts.get(name)
            _require(type(entry) is AcceptedArtifactInput)
            return entry

    def register_source_input(self, name: str, path: Path, *, cancel_requested=None) -> ReadOnlySourceInput:
        """Host-only immutable registration; never replace an existing name.

        Reads and validates the full canonical file. New checkpoints use new
        names, keeping prior call/instance accounting in the same live authority.
        """
        _logical_input_name(name)
        _require(isinstance(path, Path) and path.is_absolute())
        path = _file(path, SOURCE_INPUT_LIMIT)
        _, sha256 = _read_snapshot_input(path,cancel_requested=cancel_requested)
        with self._lock:
            _require(name.casefold() not in {key.casefold() for key in self._source_inputs})
            entry = ReadOnlySourceInput(name, sha256, path)
            self._source_inputs[name] = entry
            return entry

    def get_source_input(self, name: str) -> ReadOnlySourceInput:
        """Pure memory lookup for the qualified verifier, including in reserve.

        Returning/copying this record never grants access by itself. The verifier
        must actually establish exact read-only exposure before returning a grant.
        """
        _logical_input_name(name)
        with self._lock:
            entry = self._source_inputs.get(name)
            _require(type(entry) is ReadOnlySourceInput)
            return entry

    def _resolve_source(self, value, roots=(), *, cancel_requested=None):
        _check_cancel(cancel_requested)
        if not isinstance(value, dict) or set(value) != {'name', 'sha256'}:
            return value, None
        _logical_input_name(value['name'])
        _require(_hex(value['sha256']))
        entry = self.get_source_input(value['name'])
        _require(entry.sha256 == value['sha256'] and all(not entry.path.is_relative_to(root) for root in roots))
        snapshot, sha256 = _read_snapshot_input(entry.path,cancel_requested=cancel_requested)
        _require(sha256 == entry.sha256)
        return snapshot, entry

    def _check(self, profile, mode, request=None, *, cancel_requested=None):
        _check_cancel(cancel_requested)
        _require(mode in {'qualification', 'production'})
        digest = bundle_digest(profile)
        _require(digest not in self._revoked_bundles)
        if request is not None:
            _artifacts(request['binding']['accepted_artifacts'])
            for artifact in request['binding']['accepted_artifacts']:
                entry = self.get_accepted_artifact(artifact['name'])
                _, actual_sha256 = _read_artifact_input(entry.path,cancel_requested=cancel_requested)
                _require(actual_sha256 == entry.sha256 == artifact['sha256'])
        if mode == 'production':
            reference = profile['production_qualification_sha256']
            _require(_hex(reference) and self._qualifications.get(reference) == digest)
        else:
            approval = self._approvals.get(profile['qualification_approval_reference'])
            _keys(approval, {'schema', 'purpose', 'bundle_sha256', 'task', 'source_manifest_sha256',
                             'native_contract_sha256', 'roles', 'max_calls', 'expires_at'})
            _require(type(approval['schema']) is int and approval['schema'] == 1
                     and approval['purpose'] == 'six_role_qualification_only'
                     and approval['bundle_sha256'] == digest
                     and isinstance(approval['roles'], list) and len(approval['roles']) == 6
                     and set(approval['roles']) == set(ROLE_MAP)
                     and _hex(approval['source_manifest_sha256']) and _hex(approval['native_contract_sha256'])
                     and type(approval['max_calls']) is int and 1 <= approval['max_calls'] <= 24)
            expires = datetime.fromisoformat(approval['expires_at'])
            _require(expires.tzinfo is not None and expires > datetime.now(timezone.utc))
            if request is not None:
                snapshot, _ = self._resolve_source(request['source_manifest'],cancel_requested=cancel_requested)
                _require(request['binding']['task'] == approval['task']
                         and snapshot['manifest_sha256'] == approval['source_manifest_sha256'])

    def reserve(self, profile, mode, request, source, output, evidence, *, cancel_requested=None):
        with self._lock:
            self._check(profile, mode, request,cancel_requested=cancel_requested)
            if mode == 'qualification':
                reference = profile['qualification_approval_reference']
                _require(self._counts.get(reference, 0) < self._approvals[reference]['max_calls'])
            b, role = request['binding'], request['role']
            keys = {(name, b[name]) for name in ('attempt_id', 'instance_id')}
            _require(not self._used.intersection(keys))
            actor_role = self._actors.get((b['session_id'], b['actor']))
            _require(actor_role is None or actor_role == role)
            _, source_input = self._resolve_source(request['source_manifest'], (source, output, evidence),cancel_requested=cancel_requested)
            artifacts = tuple(self.get_accepted_artifact(a['name']) for a in b['accepted_artifacts'])
            for entry in artifacts:
                _require(all(not entry.path.is_relative_to(root) for root in (source, output, evidence)))
            grant = self._verifier(profile, request, source, output, evidence)
            phase_scope=self.get_phase_scope(b['instance_id'])
            if phase_scope is not None:
                _require(type(grant) is ContainmentGrant and grant.owned_paths==phase_scope.owned_paths)
            variant = profile['variants'][ROLE_MAP[role][0]]
            _require(type(grant) is ContainmentGrant and grant.bundle_sha256 == bundle_digest(profile)
                     and grant.prerequisite_sha256 == variant['prerequisite_sha256']
                     and (grant.source, grant.output, grant.evidence, grant.role) == (source, output, evidence, role)
                     and grant.source_input is source_input
                     and type(grant.accepted_artifacts) is tuple
                     and len(grant.accepted_artifacts) == len(artifacts)
                     and all(actual is expected for actual, expected in zip(grant.accepted_artifacts, artifacts)))
            for name in grant.owned_paths:
                _source_name(name)
            self._used.update(keys)
            self._actors[(b['session_id'], b['actor'])] = role
            ref = profile['qualification_approval_reference']
            self._counts[ref] = self._counts.get(ref, 0) + 1
            return grant


def _profile(value, *, cancel_requested=None):
    _check_cancel(cancel_requested)
    _keys(value, {'schema', 'executable', 'executable_sha256', 'request_schema', 'result_schema',
                  'superpowers', 'variants', 'roles', 'qualification_approval_reference',
                  'production_qualification_sha256'})
    _require(all(type(value[k]) is int and value[k] == 1 for k in ('schema', 'request_schema', 'result_schema')))
    executable = Path(value['executable'])
    _require(executable.is_absolute() and executable.suffix.lower() == '.exe'
             and executable.stem.lower() not in {'cmd', 'powershell', 'pwsh', 'bash', 'sh', 'wscript', 'cscript', 'mshta'}
             and _hex(value['executable_sha256']) and _hash_file(executable,cancel_requested=cancel_requested) == value['executable_sha256'])
    _require(isinstance(value['superpowers'], list) and 1 <= len(value['superpowers']) <= 64)
    pins = set()
    for pin in value['superpowers']:
        _keys(pin, {'path', 'sha256'})
        path = Path(pin['path'])
        _require(path.is_absolute() and str(path).casefold() not in pins
                 and _hex(pin['sha256']) and _hash_file(path,cancel_requested=cancel_requested) == pin['sha256'])
        pins.add(str(path).casefold())
    _keys(value['roles'], ROLE_MAP)
    for role, (variant, contract) in ROLE_MAP.items():
        _require(value['roles'][role] == dict(variant=variant, write_contract=contract))
    _keys(value['variants'], VARIANTS)
    for variant in value['variants'].values():
        _keys(variant, {'argv', 'containment_contract', 'prerequisite_sha256'})
        argv = variant['argv']
        _require(isinstance(argv, list) and 1 <= len(argv) <= 64
                 and isinstance(variant['containment_contract'], str)
                 and re.fullmatch(r'[a-z][a-z0-9_.:-]{0,95}', variant['containment_contract'])
                 and _hex(variant['prerequisite_sha256']))
        for arg in argv:
            _require(isinstance(arg, str) and len(arg) <= 4096 and '\0' not in arg
                     and (('{' not in arg and '}' not in arg) or arg in {'{request}', '{result}', '{source}', '{output}'})
                     and not any(flag in arg.lower() for flag in ('resume', 'approve_for_me', '--model', '--auth')))
    _require(isinstance(value['qualification_approval_reference'], str)
             and len(value['qualification_approval_reference']) <= 256
             and (value['production_qualification_sha256'] is None or _hex(value['production_qualification_sha256'])))
    return value


def load_role_profile(path: Path, *, mode: str, authority: object,cancel_requested=None) -> dict:
    try:
        profile = _profile(_read(path),cancel_requested=cancel_requested)
        _require(type(authority) is RoleAuthority)
        authority._check(profile, mode,cancel_requested=cancel_requested)
        return profile
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('invalid_role_profile') from None


def _environment():
    # Environment is intentionally allowlisted; no Beads/private/harness vars.
    allowed = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
               'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS'}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='NUL', GIT_NO_LAZY_FETCH='1',
               GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0')
    return env


def _git(source, *args, cancel_requested=None):
    import tempfile
    _check_cancel(cancel_requested)
    argv = ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL',
            '-c', 'core.untrackedCache=false', '-c', 'protocol.allow=never', *args]
    with tempfile.TemporaryDirectory(prefix='tower-role-git-') as directory:
        try:
            receipt = run_command(argv, source, remaining_budget(10), env=_environment(),
                cancel_requested=(lambda: _cancelled(cancel_requested)) if cancel_requested is not None else None,
                capture=dict(directory=Path(directory), max_bytes_per_stream=CAPTURE_LIMIT))
        except Exception:
            raise ProcessCleanupUnknown('git_process_unknown') from None
        if not (receipt.get('cleanup_confirmed') is True and all(receipt.get(s+'_tail_unknown') is False for s in ('stdout','stderr'))):
            raise ProcessCleanupUnknown('git_process_unknown')
        _require(receipt.get('status') == 'passed' and receipt.get('cleanup_confirmed') is True
                 and all(receipt.get(s+'_tail_unknown') is False and receipt.get(s+'_truncated') is False
                         for s in ('stdout', 'stderr')))
        return (Path(directory) / 'stdout.log').read_bytes()


def snapshot_source(source: Path, base: str, *, cancel_requested=None) -> dict:
    _check_cancel(cancel_requested)
    def git(*args):
        return _git(source, *args, cancel_requested=cancel_requested)
    source = admission._directory(str(source))
    _require(_hex(base, 40))
    metadata = admission._git_metadata(source)
    config = git('config', '--null', '--no-includes', '--list')
    admission._validate_git_config(config.decode('utf-8'))
    _require(Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() == source.resolve()
             and Path(git('rev-parse', '--absolute-git-dir').decode().strip()).resolve() == metadata)
    index = git('ls-files', '--stage', '-v', '-z').decode('utf-8')
    for entry in index.split('\0'):
        _check_cancel(cancel_requested)
        if not entry:
            continue
        _require(re.fullmatch(r'H (100644|100755) [0-9a-f]{40} 0\t[^\0]+', entry) is not None)
        _source_name(entry.partition('\t')[2])
    _require(git('rev-parse', '--verify', base+'^{commit}').decode().strip() == base)
    git('merge-base', '--is-ancestor', base, 'HEAD')
    head = git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    tree = git('rev-parse', '--verify', 'HEAD^{tree}').decode().strip()
    diff = git('diff', '--no-ext-diff', '--no-textconv', '--binary', base, '--')
    files = []
    def enumeration_failed(error):
        raise error

    for directory, dirs, names in os.walk(source, followlinks=False, onerror=enumeration_failed):
        _check_cancel(cancel_requested)
        if Path(directory) == source and '.git' in dirs:
            dirs.remove('.git')
        for name in dirs:
            _check_cancel(cancel_requested)
            admission._directory(str(Path(directory) / name))
        for name in names:
            _check_cancel(cancel_requested)
            path = Path(directory) / name
            if path == source / '.git':
                continue
            relative = _source_name(path.relative_to(source).as_posix())
            _require(len(files) < 10000)
            files.append(dict(name=relative, sha256=_hash_file(path,cancel_requested=cancel_requested)))
    files.sort(key=lambda item:item['name'])
    _require(len({f['name'].casefold() for f in files}) == len(files))
    result = dict(base=base, head=head, tree=tree, diff_digest=hashlib.sha256(diff).hexdigest(), files=files,
                  git_config_digest=hashlib.sha256(config).hexdigest(), index_digest=hashlib.sha256(index.encode('utf-8')).hexdigest())
    result['manifest_sha256'] = _digest(result)
    return result


def verify_stage_source(source: Path, before: dict, *, role: str, owned_paths: list[str], cancel_requested=None) -> dict:
    try:
        _keys(before, {'base', 'head', 'tree', 'diff_digest', 'files', 'manifest_sha256', 'git_config_digest', 'index_digest'})
        _require(before['manifest_sha256'] == _digest({k:v for k,v in before.items() if k != 'manifest_sha256'})
                 and role in ROLE_MAP)
        current = snapshot_source(source, before['base'],cancel_requested=cancel_requested)
        if current != before:
            _require(role == 'dev_implementer' and all(current[k] == before[k] for k in ('head', 'tree', 'git_config_digest', 'index_digest')))
            _require(isinstance(owned_paths, list) and bool(owned_paths))
            for prefix in owned_paths:
                _source_name(prefix)
            old = {f['name']: f['sha256'] for f in before['files']}
            new = {f['name']: f['sha256'] for f in current['files']}
            changed = {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
            _require(bool(changed) and all(any(within_scope(p,prefix) for prefix in owned_paths) for p in changed))
        return dict(outcome='ok', reason='source_verified', source=current)
    except ProcessCleanupUnknown:
        raise
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, admission._Stop):
        return dict(outcome='refused', reason='source_invalid')


def _request(request):
    _require(len(_bytes(request)) <= LIMIT)
    _keys(request, {'schema', 'kind', 'binding', 'role', 'criteria', 'source_manifest', 'output_names'})
    _require(type(request['schema']) is int and request['schema'] == 1 and request['kind'] == 'beads.role.request'
             and request['role'] in ROLE_MAP)
    _binding(request['binding'])
    manifest = request['source_manifest']
    if isinstance(manifest, dict) and set(manifest) == {'name', 'sha256'}:
        _logical_input_name(manifest['name'])
        _require(_hex(manifest['sha256']))
    else:
        _snapshot(manifest)
    stage = {'spec': 'spec', 'dev': 'development', 'test': 'test'}[request['role'].split('_')[0]]
    _require(request['binding']['stage'] == stage)
    _keys(request['criteria'], CRITERIA)
    _require(all(isinstance(v, str) for v in request['criteria'].values())
             and sum(len(v.encode('utf-8')) for v in request['criteria'].values()) <= 24*1024
             and _digest(request['criteria']) == request['binding']['input_digest'])
    _require(isinstance(request['output_names'], list) and len(request['output_names']) <= 128)
    for name in request['output_names']:
        _name(name)
    _require(len(set(n.casefold() for n in request['output_names'])) == len(request['output_names']))


def run_role(profile: dict, request: dict, *, mode: str, authority: object, source: Path,
             output: Path, evidence: Path, cancel_requested, clock=None) -> dict:
    """Cancellation accepts ONLY a threading.Event; never executes external callbacks.

    A result is execution_completed, never accepted/done. The coordinator rechecks
    fresh native owner, task inputs and policy before using this host observation.
    """
    started = False
    fact = None
    try:
        _require(os.name == 'nt' and type(authority) is RoleAuthority
                 and type(cancel_requested) is _EVENT_TYPE)

        def cancellation_requested():
            value = _EVENT_IS_SET(cancel_requested)
            # Never ask an unexpected object for truthiness: __bool__ can do
            # external work just as an overridden callback can.
            _require(type(value) is bool)
            return value

        cancellation_requested()  # Refuse corrupted state before any effects.
        _profile(profile,cancel_requested=cancel_requested); _request(request)
        authority._check(profile, mode, request,cancel_requested=cancel_requested)
        source, output, evidence = (admission._directory(str(p)) for p in (source, output, evidence))
        for a, b in ((source, output), (source, evidence), (output, evidence)):
            _require(a != b and not a.is_relative_to(b) and not b.is_relative_to(a))
        _require(not any(output.iterdir()) and not any(evidence.iterdir()))
        manifest, source_input = authority._resolve_source(request['source_manifest'], (source, output, evidence),cancel_requested=cancel_requested)
        before = snapshot_source(source, request['binding']['base'],cancel_requested=cancel_requested)
        _require(before == manifest
                 and all(request['binding'][k] == before[k] for k in ('base', 'head', 'tree', 'diff_digest'))
                 and request['binding']['superpowers_digest'] == _digest(profile['superpowers']))
        grant = authority.reserve(profile, mode, request, source, output, evidence,cancel_requested=cancel_requested)
        # Only immutable host input is in the evidence directory; backend must
        # allow this one file read while denying all host evidence writes.
        request_path, result_path = evidence / 'request.json', output / 'result.json'
        with request_path.open('xb') as stream:
            stream.write(_bytes(request))
        substitutions = {'{request}': str(request_path), '{result}': str(result_path),
                         '{source}': str(source), '{output}': str(output)}
        argv = [profile['executable'], *(substitutions.get(arg, arg) for arg in
                profile['variants'][ROLE_MAP[request['role']][0]]['argv'])]
        # Rehash immediately before launch; mutable script/backend dependencies
        # are forbidden unless the independently verified prerequisite pins them.
        _profile(profile,cancel_requested=cancel_requested)
        _require(authority._resolve_source(request['source_manifest'], (source, output, evidence),cancel_requested=cancel_requested) == (before, source_input))
        authority._check(profile, mode, request,cancel_requested=cancel_requested)
        started = True
        receipt = run_command(argv, source, remaining_budget(30*60), env=_environment(), cancel_requested=cancellation_requested,
                              capture=dict(directory=evidence, max_bytes_per_stream=CAPTURE_LIMIT))
        fact = admission._process_fact('role', receipt)
        for stream in ('stdout', 'stderr'):
            for suffix in ('sha256', 'captured_bytes', 'truncated', 'tail_unknown'):
                fact[stream+'_'+suffix] = receipt.get(stream+'_'+suffix)
        if not (fact['status'] == 'passed' and fact['eof_confirmed'] and fact['cleanup_confirmed']
                and receipt.get('started') is True and fact['exit_code'] == 0):
            return dict(outcome='unknown', reason='role_process_incomplete', process=fact)
        _require(_hash_file(request_path,cancel_requested=cancel_requested) == hashlib.sha256(_bytes(request)).hexdigest())
        _require(authority._resolve_source(request['source_manifest'], (source, output, evidence),cancel_requested=cancel_requested) == (before, source_input))
        source_result = verify_stage_source(source, before, role=request['role'], owned_paths=list(grant.owned_paths),cancel_requested=cancel_requested)
        if source_result['outcome']!='ok' and not _cancelled(cancel_requested):
            authority.revoke_bundle(profile)
        _require(source_result['outcome'] == 'ok')
        value = validate_role_result(result_path, request['binding'], reviewer=request['role'].endswith('_acceptor'),cancel_requested=cancel_requested)
        _require(set(a['name'] for a in value['artifacts']) == set(request['output_names']))
        _profile(profile,cancel_requested=cancel_requested)
        authority._check(profile, mode, request,cancel_requested=cancel_requested)
        result_digest = _hash_file(result_path,cancel_requested=cancel_requested)
        event = dict(kind='beads.role.execution_completed', instance_id=request['binding']['instance_id'],
                     role=request['role'], binding_sha256=_digest(request['binding']), result_sha256=result_digest,
                     source_manifest_sha256=source_result['source']['manifest_sha256'], artifacts=value['artifacts'])
        if source_input is not None:
            event['source_input'] = dict(name=source_input.name, sha256=source_input.sha256)
        return dict(outcome='ok', reason='execution_completed', event=event, process=fact,
                    source=source_result['source'], result=value, result_sha256=result_digest)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, admission._Stop) as error:
        stopped=False
        if type(cancel_requested) is _EVENT_TYPE:
            value=_EVENT_IS_SET(cancel_requested)
            stopped=type(value) is bool and value
        proof = fact if fact is not None else dict(operation='role_not_started',started=False,
            status='cancelled' if stopped else 'unavailable',exit_code=None,pid=None,
            cleanup_confirmed=not started and not isinstance(error,ProcessCleanupUnknown),
            eof_confirmed=not started and not isinstance(error,ProcessCleanupUnknown))
        if isinstance(error,ProcessCleanupUnknown):
            proof=dict(cleanup_confirmed=False,eof_confirmed=False)
        return dict(outcome='unknown' if started else 'refused', reason='role_contract_invalid',process=proof)
