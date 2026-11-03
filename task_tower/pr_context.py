"""Private installed inputs and genuine current stage/Git authority.

Retained PR process readers and every publication/effect API remain separate
gates. A current stage result alone cannot authorize a PR action.
"""
import copy
from contextlib import closing, contextmanager
from dataclasses import dataclass
import hashlib
import os
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace

from .executor_profiles import load_executor_config, profile_fingerprint
from .pipeline import _runtime
from .pipeline_journal import APP_ID, SCHEMAS, _open_database_pin, _pin_identity
from .pipeline_policy import _current
from .github_tasks import parse_metadata
from .pipeline_policy import criteria_snapshot
from .pr_evidence import StageAuthorityContext, load_stage_authority
from .pr_journal import PRJournal, APP_ID as PR_APP_ID, SCHEMAS as PR_SCHEMAS
from .pr_policy import (load_pr_policy, policy_fingerprint, private_paths, strict_json,
    authorized_task, canonical, text, SHA)
from .pr_review import _private_directory
from .pr_source import PRSource, PRSourceError, _git, _fetch
from .project_connections import load_connections, safe_config_path


@dataclass(frozen=True)
class PRPrivateInputs:
    connections_path: Path
    policy_path: Path
    journal_path: Path
    pipeline_config_path: Path | None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(value):
    if not isinstance(value, (Path, str)) or not Path(value).is_absolute():
        raise ValueError('Explicit absolute PR private input required')
    return safe_config_path(value)


def _identity(info):
    _pin_identity(info)
    return dict(device=info.st_dev, inode=info.st_ino)


def _inside(path, root):
    # samefile validation is performed on regular paths separately; this covers
    # existing/nonexisting ancestor relationships on case-insensitive Windows.
    name=os.path.normcase(str(path.resolve())); base=os.path.normcase(str(root.resolve()))
    return name==base or name.startswith(base.rstrip('/\\')+os.sep)


def _overlaps(left, right):
    if left.exists() and right.exists() and os.path.samefile(left,right):
        return True
    return _inside(left,right) or _inside(right,left)


def _load(inputs):
    connections=load_connections(inputs.connections_path)
    # Read only the reference needed for the real strict executor+PR loaders.
    raw=strict_json(inputs.policy_path.read_text(encoding='utf-8'))
    if not isinstance(raw,dict) or 'executor_config' not in raw:
        raise ValueError('Invalid PR configuration')
    executor_path=_path(raw['executor_config'])
    executor=load_executor_config(executor_path,connections)
    policy=load_pr_policy(inputs.policy_path,connections,executor)
    has_pipeline=policy['pipeline_journal'] is not None
    if has_pipeline != (inputs.pipeline_config_path is not None):
        raise ValueError('Explicit pipeline locator required only for pipeline tasks')
    paths=[inputs.connections_path,inputs.policy_path,inputs.journal_path,executor_path]
    paths.extend(Path(policy[k]) for k in ('pipeline_journal','legacy_provenance') if policy[k] is not None)
    if inputs.pipeline_config_path is not None: paths.append(inputs.pipeline_config_path)
    checkouts=tuple(c.checkout for c in connections)
    private_paths(paths,checkouts)
    namespace=Path(str(inputs.journal_path)+'.private')
    safe_config_path(namespace/'.pr-private-path-check')
    if namespace.exists() and not namespace.is_dir():
        raise ValueError('Invalid PR private artifact namespace')
    # Private host files/SQLite sidecars cannot share either ancestry or actual
    # file identity with any executor output/instruction root. Check the whole
    # cross-product, including roots belonging to otherwise unused profiles.
    private=[*paths]
    for path in paths:
        private.extend(Path(str(path)+s) for s in ('-journal','-wal','-shm','.owner-lock'))
    roots=[]
    for profile in executor['profiles'].values():
        roots.extend((Path(profile['runs_dir']),Path(profile['superpowers']['root'])))
    if any(_overlaps(path,root) for path in private for root in roots):
        raise ValueError('PR private input overlaps executor output or instructions')
    # The future artifact namespace is another private output, isolated from
    # all private inputs, checkouts, executor outputs and instruction roots.
    if any(_overlaps(namespace,p) for p in (*private,*checkouts,*roots)):
        raise ValueError('PR private artifact namespace collision')
    config=journal=None
    if has_pipeline:
        loaded,journal,config=_runtime(SimpleNamespace(connections=inputs.connections_path,
            config=inputs.pipeline_config_path,executor_config=executor_path,
            journal=Path(policy['pipeline_journal'])))
        if loaded!=connections or not _current(config):
            raise ValueError('Changed current pipeline configuration')
        for project in policy['projects']:
            for task in project['tasks']:
                if task['source']!='pipeline': continue
                matches=[row for row in config['tasks'] if
                    row['repository'].casefold()==project['repository'].casefold() and
                    row['issue']==task['issue'] and row['task_id']==task['task_id']]
                if len(matches)!=1: raise ValueError('PR task outside configured pipeline')
    return dict(connections=connections,executor=executor,policy=policy,
                pipeline_config=config,pipeline_journal=journal,paths=paths,namespace=namespace)


class PRHostContext:
    """Factory-owned pinned inputs; current stage proof is not PR acceptance."""

    def __init__(self):
        raise TypeError('Use PRHostContext.from_inputs')

    @classmethod
    def from_inputs(cls, inputs: PRPrivateInputs):
        if type(inputs) is not PRPrivateInputs:
            raise ValueError('Typed private PR inputs required')
        context=object.__new__(cls)
        context._closed=False; context._pins={}; context._manifest=None
        try:
            context._inputs=PRPrivateInputs(_path(inputs.connections_path),_path(inputs.policy_path),
                _path(inputs.journal_path),None if inputs.pipeline_config_path is None else _path(inputs.pipeline_config_path))
            # Pin the two bootstrap files before reading any configuration.
            for path in (context._inputs.connections_path,context._inputs.policy_path): context._pin(path)
            loaded=_load(context._inputs)
            for path in loaded['paths']:
                if path!=context._inputs.journal_path: context._pin(path)
            if context._inputs.journal_path.exists(): context._pin(context._inputs.journal_path)
            # Pin every actual instruction file as well as validating full pins
            # through load_executor_config on every fresh use.
            for profile in loaded['executor']['profiles'].values():
                root=Path(profile['superpowers']['root'])
                for relative in profile['superpowers']['manifest']: context._pin(root/relative)
            context._manifest=context._provenance(loaded)
            # Detect changes while the real factories were loading and between
            # first path reads and lifetime pin installation.
            context._fresh_inputs()
            return context
        except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError):
            context.close()
            raise ValueError('Invalid private PR host inputs') from None

    def _pin(self,path):
        path=_path(path)
        if path in self._pins: return
        before=_identity(path.stat()); descriptor=_open_database_pin(path)
        try:
            if _identity(os.fstat(descriptor))!=before or _identity(path.stat())!=before:
                raise ValueError('Private PR input replaced during pin')
            self._pins[path]=(descriptor,before)
        except BaseException:
            os.close(descriptor); raise

    def _check_pins(self):
        if self._closed: raise ValueError('Private PR host context closed')
        for path,(descriptor,identity) in self._pins.items():
            _path(path)
            if _identity(os.fstat(descriptor))!=identity or _identity(path.stat())!=identity:
                raise ValueError('Private PR input replaced')

    def _provenance(self,loaded):
        self._check_pins()
        source=loaded['pipeline_journal']; source_identity=None
        if source is not None:
            # mode=ro, initialize=False, the actual configured source schema and
            # validation. Never hash the mutable whole database as authority.
            with source._pinned_database() as identity:
                if identity is None: raise ValueError('Missing pipeline source')
                with source._existing_database(identity),source._db(False,initialize=False) as db:
                    if db is None: raise ValueError('Missing pipeline source')
                    source._assert_existing()
                    source_identity=dict(path=str(source.path),**_identity(identity),application_id=APP_ID,
                        user_version=1,schema_sha256=profile_fingerprint(SCHEMAS))
        files=[]
        for path,(descriptor,identity) in sorted(self._pins.items(),key=lambda item:str(item[0])):
            if path==self._inputs.journal_path or (source is not None and path==source.path): continue
            files.append(dict(path=str(path),raw_sha256=_sha(path.read_bytes()),**identity))
        connections=[dict(vars(c),checkout=str(c.checkout)) for c in loaded['connections']]
        config=loaded['pipeline_config']
        result=dict(version=1,connections_path=str(self._inputs.connections_path),
            policy_path=str(self._inputs.policy_path),journal_path=str(self._inputs.journal_path),
            pipeline_config_path=None if self._inputs.pipeline_config_path is None else str(self._inputs.pipeline_config_path),
            artifact_namespace=str(loaded['namespace']),files=files,source_journal=source_identity,
            pr_journal=self._pr_journal_provenance(),
            connections_sha256=profile_fingerprint(connections),executor_sha256=profile_fingerprint(loaded['executor']),
            policy_sha256=policy_fingerprint(loaded['policy']),
            pipeline_policy_sha256=None if config is None else config['policy_sha256'])
        self._check_pins()
        return result

    def _pr_journal_provenance(self):
        """Validate existing host state in one RO snapshot; never initialize it."""
        path=self._inputs.journal_path
        if path not in self._pins:
            if path.exists(): raise ValueError('PR journal appeared after context creation')
            return None
        with self._pr_snapshot(): pass
        return dict(path=str(path),**self._pins[path][1],application_id=PR_APP_ID,
            user_version=1,schema_sha256=profile_fingerprint(PR_SCHEMAS))

    @contextmanager
    def _pr_snapshot(self):
        """One physically pinned existing transaction for validation and readers."""
        path=self._inputs.journal_path
        if path not in self._pins: raise ValueError('No pinned existing PR journal')
        self._check_pins()
        journal=PRJournal(path)
        try:
            with path.open('rb') as stream: header=stream.read(100)
            if (header[:16]!=b'SQLite format 3\x00' or header[18:20]!=b'\x01\x01'
                    or any(Path(str(path)+s).exists() for s in ('-journal','-wal','-shm'))):
                raise ValueError('Unsupported PR journal state')
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
                db.row_factory=sqlite3.Row
                db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
                app=db.execute('PRAGMA application_id').fetchone()[0]
                version=db.execute('PRAGMA user_version').fetchone()[0]
                objects={(r['type'],r['name'],r['sql']) for r in db.execute(
                    "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
                if (app!=PR_APP_ID or version!=1 or
                        objects!={('table',name,sql) for name,sql in PR_SCHEMAS.items()}):
                    raise ValueError('Unrecognized private PR journal')
                journal._validate(db)
                self._check_pins()
                yield db
                self._check_pins()
            if any(Path(str(path)+s).exists() for s in ('-journal','-wal','-shm')):
                raise ValueError('PR journal changed during validation')
            self._check_pins()
        except sqlite3.Error:
            raise ValueError('Private PR journal unavailable') from None

    def prepared_record(self,input_sha256):
        from .pr_records import read_prepared_record
        return read_prepared_record(self,input_sha256)

    def review_record(self,input_sha256):
        from .pr_records import read_review_record
        return read_review_record(self,input_sha256)

    def _fresh_inputs(self):
        """Internal factory gate; not a stage-authority or effect authorization."""
        self._check_pins()
        try:
            loaded=_load(self._inputs)
            provenance=self._provenance(loaded)
            if provenance!=self._manifest: raise ValueError('Private PR inputs changed')
            return loaded
        except (OSError,ValueError,TypeError,KeyError,AttributeError,UnicodeError):
            raise ValueError('Private PR inputs unavailable or changed') from None

    def _authority_mirror(self, loaded, connection, snapshot):
        """Fresh host-created object-only mirror, never an original worktree.

        No existing directory/object cache is reused as evidence. Task5 owns
        retention/cleanup of these private host artifacts; this gate never
        recursively removes a path or changes any source checkout/ref.
        """
        base=text(snapshot['base_sha'],SHA); head=text(snapshot['head_sha'],SHA)
        namespace=loaded['namespace']
        safe_config_path(namespace/'.pr-private-path-check')
        directory=_private_directory(namespace/('authority-'+str(uuid.uuid4())),connection.checkout)
        logs=directory/'logs'; logs.mkdir()
        mirror=directory/'objects'; mirror.mkdir()
        origin=_git(connection.checkout,['config','--no-includes','--local','--get','remote.origin.url'],logs,16384).decode('utf-8').strip()
        url='https://github.com/'+connection.repository.casefold()+'.git'
        if origin.casefold() not in (url,url.removesuffix('.git'),'git@github.com:'+connection.repository.casefold()+'.git'):
            raise ValueError('Repository remote does not match configured identity')
        _git(mirror,['init','--bare','--template='],logs)
        _fetch(mirror,url,base,head,logs)
        for sha in (base,head):
            actual=_git(mirror,['rev-parse','--verify',sha+'^{commit}'],logs,1024).decode('ascii').strip()
            if actual!=sha: raise ValueError('Immutable PR object mismatch')
        _git(mirror,['merge-base','--is-ancestor',base,head],logs,1024)
        safe_config_path(directory/'.pr-private-path-check')
        return mirror

    def current(self, source: PRSource, task_identity: dict) -> dict:
        """Reconstruct actual current stage proof, with a fixed refusal channel.

        This does not verify an admitted PR review record or permit effects.
        Configuration/identity/source uncertainty raises rather than producing
        a negative-status authorization. Recognized stage refusals are data
        only; consumers must independently enforce every PR effect gate.
        """
        loaded=self._fresh_inputs()
        if type(source) is not PRSource or not isinstance(task_identity,dict):
            raise ValueError('Genuine configured PR source and task identity required')
        task=authorized_task(loaded['policy'],task_identity.get('repository'),task_identity.get('pr_number'))
        for key in ('issue','issue_id','task_id','pr_number'):
            if type(task_identity.get(key)) is not type(task[key]) or task_identity[key]!=task[key]:
                raise ValueError('Foreign current PR identity')
        for key in ('source','pipeline_run_id'):
            if key in task_identity and task_identity[key]!=task[key]: raise ValueError('Foreign PR authority identity')
        matches=[c for c in loaded['connections'] if c.repository.casefold()==task['repository'].casefold()]
        if len(matches)!=1 or source.connection!=matches[0] or canonical(source.policy)!=canonical(loaded['policy']):
            raise ValueError('PR source disagrees with current private inputs')
        connection=matches[0]
        if source.repository!=connection.repository.casefold(): raise ValueError('Foreign current PR source')
        # Source/journal identities are canonical lower-case repository names;
        # connection/profile spelling remains unchanged in their fingerprints.
        task['repository']=source.repository
        task['_review_profile']=copy.deepcopy(loaded['executor']['profiles'][task['reviewer_profile']])
        snapshot=source.snapshot(task)
        if snapshot['policy_sha256']!=policy_fingerprint(loaded['policy']): raise ValueError('Current source policy mismatch')
        authority=None; authority_error='stage_authority_unverified'
        if task['source']=='pipeline':
            config=loaded['pipeline_config']
            rows=[r for r in config['tasks'] if r['repository'].casefold()==task['repository'] and
                  r['issue']==task['issue'] and r['task_id']==task['task_id']]
            if len(rows)!=1: raise ValueError('Current task outside configured pipeline')
            profile=config['profiles'][rows[0]['executor_profile']]
            try:
                issue=snapshot['issue_payload']; metadata=parse_metadata(issue['body'])
                criteria=criteria_snapshot(issue,metadata,task['repository'])
            except ValueError:
                criteria=None
            if criteria is not None:
                # Unknown/foreign Git identity is a hard refusal, never the
                # recognized stage-negative diagnostic channel.
                mirror=self._authority_mirror(loaded,connection,snapshot)
                context=StageAuthorityContext(pipeline_journal=loaded['pipeline_journal'],pipeline_config=config,
                    git_mirror=mirror,criteria_sha256=profile_fingerprint(criteria),
                    superpowers_sha256=profile['superpowers']['manifest_sha256'],
                    profile_sha256=profile_fingerprint(profile))
                try:
                    authority=load_stage_authority(task,snapshot,context=context)
                    authority_error=None
                except ValueError:
                    authority=None
        # A fetch/retained-process audit may take time. Recheck actual private
        # inputs and the complete coherent live source before returning proof.
        self._fresh_inputs()
        if canonical(source.snapshot(task))!=canonical(snapshot):
            raise ValueError('Current PR source changed during authority audit')
        return dict(task=task,snapshot=snapshot,authority=authority,authority_error=authority_error,
            policy_sha256=policy_fingerprint(loaded['policy']),private_inputs_sha256=self.private_inputs_sha256)

    @property
    def private_input_provenance(self):
        self._check_pins()
        return copy.deepcopy(self._manifest)

    @property
    def private_inputs_sha256(self):
        return policy_fingerprint(self.private_input_provenance)

    def close(self):
        if self._closed: return
        self._closed=True
        failure=None
        for descriptor,_ in self._pins.values():
            try: os.close(descriptor)
            except BaseException as error:
                if failure is None: failure=error
        self._pins.clear()
        if failure is not None: raise failure

    def __enter__(self):
        try:
            self._check_pins()
            return self
        except BaseException as error:
            try: self.close()
            except BaseException as cleanup_error: raise error from cleanup_error
            raise

    def __exit__(self,*args):
        self.close()
