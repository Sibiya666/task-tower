"""Exact additive group storage; no registration or grouped execution authority."""
from contextlib import closing, contextmanager, ExitStack
import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .pipeline_inputs import canonical_json, digest_manifest

SOURCE_SCHEMA_SHA256 = '5b37731384a2d5a8aa87f38f589bcced2b78db2205861e6aa5290d4b4ccdc9b6'
_HISTORY = ('attempts', 'verdicts', 'effects', 'events')
_IMMUTABLE_RUN = ('run_id', 'delivery_id', 'repository', 'issue', 'task_id', 'runner_label',
                  'profile_id', 'profile_fingerprint', 'policy_sha256', 'branch', 'created_at',
                  'limits', 'component_keys')
_CATALOG = None

DDL = """
CREATE TABLE group_installation(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 installation_id TEXT NOT NULL UNIQUE,
 canonical_journal TEXT NOT NULL UNIQUE,
 journal_file_identity_json TEXT NOT NULL,
 groups_config_path TEXT NOT NULL UNIQUE,
 current_capacity_epoch INTEGER NOT NULL CHECK(current_capacity_epoch>0),
 current_policy_sha256 TEXT NOT NULL CHECK(length(current_policy_sha256)=64),
 current_authorization_sha256 TEXT NOT NULL CHECK(length(current_authorization_sha256)=64),
 bound_at TEXT NOT NULL,
 FOREIGN KEY(current_capacity_epoch,installation_id)
   REFERENCES group_capacity_epochs(epoch,installation_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE group_capacity_epochs(
 epoch INTEGER PRIMARY KEY CHECK(epoch>0),
 installation_id TEXT NOT NULL,
 change_kind TEXT NOT NULL CHECK(change_kind IN('initial','capacity_only','authorization_change')),
 policy_sha256 TEXT NOT NULL CHECK(length(policy_sha256)=64),
 authorization_sha256 TEXT NOT NULL CHECK(length(authorization_sha256)=64),
 group_maximum INTEGER CHECK(group_maximum IS NULL OR group_maximum>0),
 pipeline_maximum INTEGER CHECK(pipeline_maximum IS NULL OR pipeline_maximum>0),
 executor_maximum INTEGER CHECK(executor_maximum IS NULL OR executor_maximum>0),
 effective_maximum INTEGER CHECK(effective_maximum IS NULL OR effective_maximum>0),
 max_inflight INTEGER CHECK(max_inflight IS NULL OR max_inflight>0),
 resource_policy_json TEXT NOT NULL,
 capacity_matrix_json TEXT NOT NULL,
 capacity_sha256 TEXT NOT NULL CHECK(length(capacity_sha256)=64),
 registered_at TEXT NOT NULL,
 UNIQUE(epoch,installation_id),
 FOREIGN KEY(installation_id) REFERENCES group_installation(installation_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE group_resource_observations(
 observation_id TEXT PRIMARY KEY,
 capacity_epoch INTEGER NOT NULL REFERENCES group_capacity_epochs(epoch),
 collector_pid INTEGER NOT NULL CHECK(collector_pid>0),
 boot_id TEXT NOT NULL,
 monotonic_ns INTEGER NOT NULL CHECK(monotonic_ns>=0),
 expires_monotonic_ns INTEGER NOT NULL CHECK(expires_monotonic_ns>monotonic_ns),
 status TEXT NOT NULL CHECK(status IN('available','fallback','unavailable')),
 body_json TEXT NOT NULL,
 body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64)
);
CREATE TABLE group_resource_leases(
 action_id TEXT PRIMARY KEY REFERENCES group_actions(action_id) DEFERRABLE INITIALLY DEFERRED,
 run_id TEXT NOT NULL REFERENCES group_runs(run_id),
 observation_id TEXT REFERENCES group_resource_observations(observation_id),
 capacity_epoch INTEGER REFERENCES group_capacity_epochs(epoch),
 harness_pool TEXT,
 cpu_millis INTEGER CHECK(cpu_millis IS NULL OR cpu_millis>0),
 memory_bytes INTEGER CHECK(memory_bytes IS NULL OR memory_bytes>0),
 unknown_estimate INTEGER NOT NULL CHECK(unknown_estimate IN(0,1)),
 held INTEGER NOT NULL CHECK(held IN(0,1)),
 cleanup_sha256 TEXT CHECK(cleanup_sha256 IS NULL OR length(cleanup_sha256)=64),
 CHECK((unknown_estimate=1 AND cpu_millis IS NULL AND memory_bytes IS NULL) OR
       (unknown_estimate=0 AND cpu_millis IS NOT NULL AND memory_bytes IS NOT NULL AND harness_pool IS NOT NULL)),
 CHECK(held=1 OR cleanup_sha256 IS NOT NULL)
);
CREATE TABLE group_runs(
 run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
 run_kind TEXT NOT NULL CHECK(run_kind IN('legacy','group')),
 group_id TEXT,
 binding_json TEXT NOT NULL,
 binding_sha256 TEXT NOT NULL CHECK(length(binding_sha256)=64),
 authorization_sha256 TEXT,
 isolation_kind TEXT NOT NULL CHECK(isolation_kind IN('unprepared','legacy_linked','independent_clone')),
 first_eligible_sequence INTEGER UNIQUE CHECK(first_eligible_sequence IS NULL OR first_eligible_sequence>0),
 current_base_epoch INTEGER CHECK(current_base_epoch IS NULL OR current_base_epoch>=0),
 CHECK((run_kind='legacy' AND group_id IS NULL AND authorization_sha256 IS NULL AND current_base_epoch IS NULL)
    OR (run_kind='group' AND group_id IS NOT NULL AND authorization_sha256 IS NOT NULL AND length(authorization_sha256)=64)),
 FOREIGN KEY(run_id,current_base_epoch) REFERENCES group_base_epochs(run_id,epoch) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE group_reservations(
 run_id TEXT PRIMARY KEY REFERENCES group_runs(run_id),
 capacity_epoch INTEGER REFERENCES group_capacity_epochs(epoch),
 slot_held INTEGER NOT NULL CHECK(slot_held IN(0,1)),
 component_held INTEGER NOT NULL CHECK(component_held IN(0,1)),
 reserved_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 release_reason TEXT CHECK(release_reason IN('completed','clean_park','cancelled','timed_out','abandoned')),
 cleanup_sha256 TEXT CHECK(cleanup_sha256 IS NULL OR length(cleanup_sha256)=64),
 completion_proof_sha256 TEXT CHECK(completion_proof_sha256 IS NULL OR length(completion_proof_sha256)=64),
 CHECK(slot_held<=component_held)
);
CREATE TABLE group_component_locks(
 repository TEXT NOT NULL CHECK(repository=lower(repository)),
 component TEXT NOT NULL CHECK(length(component) BETWEEN 1 AND 100),
 run_id TEXT NOT NULL REFERENCES group_reservations(run_id),
 PRIMARY KEY(repository,component,run_id)
);
CREATE TABLE group_actions(
 action_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES group_runs(run_id),
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 origin TEXT NOT NULL CHECK(origin IN('execution','legacy_fence')),
 origin_json TEXT,
 origin_sha256 TEXT CHECK(origin_sha256 IS NULL OR length(origin_sha256)=64),
 owner_id TEXT,
 owner_pid INTEGER CHECK(owner_pid IS NULL OR owner_pid>0),
 action_kind TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN('active','completed','unknown')),
 input_sha256 TEXT CHECK(input_sha256 IS NULL OR length(input_sha256)=64),
 capacity_epoch INTEGER REFERENCES group_capacity_epochs(epoch),
 started_at TEXT NOT NULL,
 finished_at TEXT,
 completion_json TEXT,
 completion_sha256 TEXT CHECK(completion_sha256 IS NULL OR length(completion_sha256)=64),
 UNIQUE(run_id,ordinal),
 CHECK((origin='legacy_fence' AND action_kind='legacy_fence' AND state='unknown'
        AND origin_json IS NOT NULL AND origin_sha256 IS NOT NULL
        AND owner_id IS NULL AND owner_pid IS NULL AND input_sha256 IS NULL
        AND capacity_epoch IS NULL AND finished_at IS NULL
        AND completion_json IS NULL AND completion_sha256 IS NULL)
    OR (origin='execution' AND action_kind<>'legacy_fence'
        AND origin_json IS NULL AND origin_sha256 IS NULL
        AND owner_id IS NOT NULL AND owner_pid IS NOT NULL
        AND input_sha256 IS NOT NULL AND capacity_epoch IS NOT NULL
        AND ((state='active' AND finished_at IS NULL AND completion_json IS NULL AND completion_sha256 IS NULL)
          OR (state='completed' AND finished_at IS NOT NULL AND completion_json IS NOT NULL AND completion_sha256 IS NOT NULL)
          OR (state='unknown' AND completion_json IS NOT NULL AND completion_sha256 IS NOT NULL))))
);
CREATE UNIQUE INDEX group_one_live_execution ON group_actions(run_id) WHERE origin='execution' AND state IN('active','unknown');
CREATE INDEX group_legacy_fences ON group_actions(run_id) WHERE origin='legacy_fence';
CREATE TABLE group_fair_cursors(
 scope TEXT NOT NULL CHECK(scope IN('projects','groups')),
 scope_id TEXT NOT NULL,
 last_key TEXT NOT NULL,
 completed_action_id TEXT NOT NULL REFERENCES group_actions(action_id),
 revision INTEGER NOT NULL CHECK(revision>0),
 PRIMARY KEY(scope,scope_id)
);
CREATE TABLE group_observations(
 observation_id TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN('graph','completion')),
 run_id TEXT REFERENCES group_runs(run_id),
 snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64),
 body_json TEXT NOT NULL,
 body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
 observed_at TEXT NOT NULL
);
CREATE TABLE group_main_proofs(
 proof_sha256 TEXT NOT NULL CHECK(length(proof_sha256)=64),
 run_id TEXT NOT NULL REFERENCES group_runs(run_id),
 kind TEXT NOT NULL CHECK(kind IN('accepted_main','initial_source')),
 authorization_sha256 TEXT NOT NULL CHECK(length(authorization_sha256)=64),
 snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64),
 body_json TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 PRIMARY KEY(run_id,proof_sha256)
);
CREATE TABLE group_source_resolutions(
 run_id TEXT PRIMARY KEY REFERENCES group_runs(run_id),
 mode TEXT NOT NULL CHECK(mode IN('pinned','accepted_main')),
 body_json TEXT NOT NULL,
 body_sha256 TEXT NOT NULL UNIQUE CHECK(length(body_sha256)=64),
 source_sha TEXT NOT NULL CHECK(length(source_sha)=40),
 base_sha TEXT NOT NULL CHECK(length(base_sha)=40),
 profile_sha256 TEXT NOT NULL CHECK(length(profile_sha256)=64),
 initial_main_proof_sha256 TEXT,
 FOREIGN KEY(run_id,initial_main_proof_sha256) REFERENCES group_main_proofs(run_id,proof_sha256)
);
CREATE TABLE group_base_epochs(
 run_id TEXT NOT NULL REFERENCES group_runs(run_id),
 epoch INTEGER NOT NULL CHECK(epoch>=0),
 previous_epoch_sha256 TEXT REFERENCES group_base_epochs(epoch_sha256),
 epoch_sha256 TEXT NOT NULL UNIQUE CHECK(length(epoch_sha256)=64),
 body_json TEXT NOT NULL,
 committed_at TEXT NOT NULL,
 PRIMARY KEY(run_id,epoch),
 CHECK((epoch=0 AND previous_epoch_sha256 IS NULL) OR (epoch>0 AND previous_epoch_sha256 IS NOT NULL))
);
CREATE TABLE group_base_updates(
 update_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES group_runs(run_id),
 update_number INTEGER NOT NULL CHECK(update_number BETWEEN 1 AND 2),
 previous_epoch INTEGER NOT NULL CHECK(previous_epoch>=0),
 pre_head_sha TEXT NOT NULL CHECK(length(pre_head_sha)=40),
 proof_sha256 TEXT NOT NULL CHECK(length(proof_sha256)=64),
 authorization_sha256 TEXT NOT NULL CHECK(length(authorization_sha256)=64),
 phase TEXT NOT NULL CHECK(phase IN('intent','fetch_intent','fetched','merge_intent','merged','conflict','post_checkpoint','committed','unknown','quarantined')),
 latest_phase_sequence INTEGER NOT NULL CHECK(latest_phase_sequence>0),
 intent_json TEXT NOT NULL,
 intent_sha256 TEXT NOT NULL CHECK(length(intent_sha256)=64),
 UNIQUE(run_id,update_number),
 FOREIGN KEY(run_id,previous_epoch) REFERENCES group_base_epochs(run_id,epoch),
 FOREIGN KEY(run_id,proof_sha256) REFERENCES group_main_proofs(run_id,proof_sha256),
 FOREIGN KEY(update_id,latest_phase_sequence) REFERENCES group_base_phases(update_id,sequence) DEFERRABLE INITIALLY DEFERRED
);
CREATE UNIQUE INDEX group_one_open_base_update ON group_base_updates(run_id) WHERE phase<>'committed';
CREATE TABLE group_base_phases(
 update_id TEXT NOT NULL REFERENCES group_base_updates(update_id) DEFERRABLE INITIALLY DEFERRED,
 sequence INTEGER NOT NULL CHECK(sequence>0),
 phase TEXT NOT NULL CHECK(phase IN('intent','fetch_intent','fetched','merge_intent','merged','conflict','post_checkpoint','committed','unknown','quarantined')),
 owner_id TEXT NOT NULL,
 effect_id TEXT UNIQUE REFERENCES effects(effect_id),
 body_json TEXT NOT NULL,
 body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
 recorded_at TEXT NOT NULL,
 PRIMARY KEY(update_id,sequence)
);
CREATE TABLE group_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT REFERENCES group_runs(run_id),
 kind TEXT NOT NULL CHECK(kind IN('migration','binding','capacity_epoch','reservation','action','cursor','observation','source_resolution','base_phase','base_epoch','invalidation','resource_observation','resource_release')),
 body_json TEXT NOT NULL,
 body_sha256 TEXT NOT NULL CHECK(length(body_sha256)=64),
 recorded_at TEXT NOT NULL
);
CREATE TABLE group_migration(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 source_schema_sha256 TEXT NOT NULL CHECK(length(source_schema_sha256)=64),
 target_schema_sha256 TEXT NOT NULL CHECK(length(target_schema_sha256)=64),
 legacy_snapshot_sha256 TEXT NOT NULL CHECK(length(legacy_snapshot_sha256)=64),
 backup_path TEXT NOT NULL,
 backup_sha256 TEXT NOT NULL CHECK(length(backup_sha256)=64),
 completed_at TEXT NOT NULL
);
"""


class MigrationFailure(ValueError):
    """A newly created backup is diagnostic evidence, never a replay source."""
    def __init__(self,backup_path):
        super().__init__('Group migration failed; diagnostic backup retained')
        self.backup_path=str(backup_path)


def _dump(value):
    return canonical_json(value).decode('utf-8')


def _json(value):
    parsed = json.loads(value)
    if _dump(parsed) != value or len(value.encode('utf-8')) > 16*1024*1024:
        raise ValueError('Invalid canonical group storage JSON')
    return parsed


def _checkpoint(phase):
    """Named crash boundary for real-process migration regression tests."""


def catalog():
    global _CATALOG
    if _CATALOG is None:
        from .pipeline_journal import SCHEMAS
        with closing(sqlite3.connect(':memory:')) as db:
            for sql in SCHEMAS.values():
                db.execute(sql)
            for statement in DDL.split(';'):
                if statement.strip():
                    db.execute(statement.strip())
            _CATALOG = frozenset(tuple(row) for row in db.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
    return _CATALOG


def schema_digest():
    return digest_manifest([list(row) for row in sorted(catalog())])


def legacy_snapshot(db):
    from .pipeline_journal import SCHEMAS
    return {**{name: [dict(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')]
               for name in SCHEMAS},
            'sqlite_sequence': [dict(row) for row in db.execute("SELECT * FROM sqlite_sequence WHERE name='events'")]}


def _history(db, run_id):
    return {name: [dict(row) for row in db.execute('SELECT * FROM '+name+' WHERE run_id=? ORDER BY '+
             ('sequence' if name=='events' else 'ordinal' if name=='effects' else 'rowid'), (run_id,))]
            for name in _HISTORY}


def _typed_snapshot(journal, snapshot, *, classify=False):
    """Validate historical neutral bytes with the unchanged legacy validator."""
    from .pipeline_journal import SCHEMAS
    if not isinstance(snapshot,dict) or set(snapshot)!=set(SCHEMAS)|{'sqlite_sequence'}:
        raise ValueError('Invalid legacy snapshot shape')
    with closing(sqlite3.connect(':memory:')) as db:
        db.row_factory=sqlite3.Row
        for name,sql in SCHEMAS.items():
            journal._wait_seconds()
            db.execute(sql)
            columns=[row[1] for row in db.execute('PRAGMA table_info('+name+')')]
            if not isinstance(snapshot[name],list):raise ValueError('Invalid legacy snapshot rows')
            for row in snapshot[name]:
                journal._wait_seconds()
                if not isinstance(row,dict) or set(row)!=set(columns):raise ValueError('Invalid legacy snapshot columns')
                db.execute('INSERT INTO '+name+' VALUES('+','.join('?' for _ in columns)+')',tuple(row[k] for k in columns))
            actual=[dict(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')]
            if canonical_json(actual)!=canonical_json(snapshot[name]):raise ValueError('Legacy snapshot types or ordering changed')
        sequence=snapshot['sqlite_sequence']
        if not isinstance(sequence,list) or len(sequence)>1:raise ValueError('Invalid legacy sequence snapshot')
        if sequence and (set(sequence[0])!={'name','seq'} or sequence[0]['name']!='events' or
                         type(sequence[0]['seq']) is not int or sequence[0]['seq']<max((r['sequence'] for r in snapshot['events']),default=0)):
            raise ValueError('Invalid legacy sequence value')
        journal._validate_db(db)
        if classify:
            return {run['run_id']:dict(run_row=run,history=_history(db,run['run_id']))
                    for run in snapshot['runs']
                    if _needs_product(db,run) and not _positive_cleanup(db,journal,run)}
        return len(snapshot['runs'])==1 and _positive_cleanup(db,journal,snapshot['runs'][0])


def _boundary_snapshot(run, history):
    return dict(runs=[run], controller=[], sqlite_sequence=[dict(name='events',seq=max(
        (row['sequence'] for row in history['events']),default=0))], **history)


def _preserved_history(db, snapshot):
    """Original identities and immutable history cannot disappear on v2 reopen."""
    for old in snapshot['runs']:
        current=db.execute('SELECT * FROM runs WHERE run_id=?',(old['run_id'],)).fetchone()
        if current is None or any(type(current[k]) is not type(old[k]) or current[k]!=old[k] for k in _IMMUTABLE_RUN):
            raise ValueError('Legacy run identity changed')
        for key in ('admission','issue_id','criteria_sha256','superpowers_sha256','source_sha','base_sha'):
            if old[key] is not None and current[key]!=old[key]:raise ValueError('Legacy admission changed')
    for name,key in (('attempts','attempt_id'),('verdicts','receipt_id'),('effects','effect_id'),('events','sequence')):
        mutable={'attempts':{'state','evidence','result_sha256','finished_at'},'verdicts':{'superseded'},
                 'effects':{'status','observation','observation_sha256'},'events':set()}[name]
        for old in snapshot[name]:
            current=db.execute('SELECT * FROM '+name+' WHERE '+key+'=?',(old[key],)).fetchone()
            if current is None or any(type(current[k]) is not type(old[k]) or current[k]!=old[k] for k in set(old)-mutable):
                raise ValueError('Legacy history identity changed')
            if name=='attempts' and old['state']!='launch_intent' and any(current[k]!=old[k] for k in mutable):
                raise ValueError('Finished legacy attempt changed')
            if name=='effects' and old['status']!='intent' and any(current[k]!=old[k] for k in mutable):
                raise ValueError('Observed legacy effect changed')
            if name=='verdicts' and old['superseded']==1 and current['superseded']!=1:
                raise ValueError('Historical verdict revived')
        for run_id in {row['run_id'] for row in snapshot[name]}:
            old_ids=[row[key] for row in snapshot[name] if row['run_id']==run_id]
            order='sequence' if name=='events' else 'ordinal' if name=='effects' else 'rowid'
            current_ids=[row[0] for row in db.execute('SELECT '+key+' FROM '+name+' WHERE run_id=? ORDER BY '+order,(run_id,))]
            if current_ids[:len(old_ids)]!=old_ids:raise ValueError('Legacy history boundary order changed')
    saved=snapshot['sqlite_sequence']
    actual=db.execute("SELECT seq FROM sqlite_sequence WHERE name='events'").fetchone()
    if saved and (actual is None or actual[0]<saved[0]['seq']):raise ValueError('Legacy sequence went backwards')


def _utc(value):
    if not isinstance(value,str):raise ValueError('Invalid host UTC timestamp')
    parsed=datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset()!=datetime.timedelta(0):
        raise ValueError('Invalid host UTC timestamp')
    return parsed


def _metadata(db):
    rows=list(db.execute('SELECT * FROM group_migration'))
    if len(rows)!=1:raise ValueError('Missing or duplicate group migration metadata')
    row=dict(rows[0])
    if row['singleton']!=1 or row['source_schema_sha256']!=SOURCE_SCHEMA_SHA256 or row['target_schema_sha256']!=schema_digest():
        raise ValueError('Group migration schema binding mismatch')
    from .pipeline_journal import _sha
    for key in ('source_schema_sha256','target_schema_sha256','legacy_snapshot_sha256','backup_sha256'):_sha(row[key])
    _utc(row['completed_at'])
    if not isinstance(row['backup_path'],str) or not Path(row['backup_path']).is_absolute():
        raise ValueError('Invalid migration backup path')
    return row


def _event(db,kind,body,run_id=None,when=None):
    from .pipeline_journal import _now
    db.execute('INSERT INTO group_events(run_id,kind,body_json,body_sha256,recorded_at) VALUES(?,?,?,?,?)',
               (run_id,kind,_dump(body),digest_manifest(body),when or _now()))


def _binding(run):
    return dict(version=1,**{key:run[key] for key in _IMMUTABLE_RUN})


def _bind_run(db,run):
    body=_binding(run)
    db.execute('INSERT INTO group_runs VALUES(?,?,?,?,?,?,?,?,?)',
        (run['run_id'],'legacy',None,_dump(body),digest_manifest(body),None,
         'legacy_linked' if run['worktree'] else 'unprepared',None,None))


def _positive_cleanup(db,journal,run):
    # A status/PID alone is never cleanup proof. Reuse the release's durable
    # process/effect checks, including manifest and nonempty positive history.
    if run['state'] not in {'ready','ready_for_pr','awaiting_pr','needs_input','cancelled','timed_out'}:
        return False
    return journal._safe_ready(db,dict(run,state='ready'))


def _needs_product(db,run):
    if run['state']=='queued':return False
    return bool(run['owner_id'] or run['admission'] or run['worktree'] or run['process_count'] or
                any(db.execute('SELECT 1 FROM '+name+' WHERE run_id=? LIMIT 1',(run['run_id'],)).fetchone() for name in ('attempts','effects','verdicts')))


def _reserve(db,run,held,when):
    db.execute('INSERT INTO group_reservations VALUES(?,?,?,?,?,?,?,?,?)',
        (run['run_id'],None,int(held),1,when,when,None,None,None))


def _make_fence(db,journal,run,kind,metadata):
    from .pipeline_journal import _now
    when=_now();history=_history(db,run['run_id']);action_id=str(uuid.uuid4())
    origin=dict(version=1,run_id=run['run_id'],observation_kind=kind,observed_at=when,
        original_owner_id=run['owner_id'],original_owner_pid=run['owner_pid'],original_state=run['state'],
        original_input_sha256=run['input_sha256'],original_run_row_sha256=digest_manifest(run),
        original_history_sha256=digest_manifest(history),migration_id=digest_manifest(metadata))
    ordinal=db.execute('SELECT coalesce(max(ordinal),0)+1 FROM group_actions WHERE run_id=?',(run['run_id'],)).fetchone()[0]
    db.execute('INSERT INTO group_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (action_id,run['run_id'],ordinal,'legacy_fence',_dump(origin),digest_manifest(origin),None,None,
         'legacy_fence','unknown',None,None,when,None,None,None))
    db.execute('INSERT INTO group_resource_leases VALUES(?,?,?,?,?,?,?,?,?,?)',
        (action_id,run['run_id'],None,None,None,None,None,1,1,None))
    if kind!='migration':
        marker_kind={'legacy_claim':'action','reconcile':'reservation'}[kind]
        _event(db,marker_kind,_boundary_marker(action_id,run,history,origin,metadata,when),run['run_id'],when)
    body=dict(version=1,action_id=action_id,run_id=run['run_id'],origin_sha256=digest_manifest(origin),run_row=run,history=history)
    _event(db,'observation',body,run['run_id'],when)
    db.execute('UPDATE group_reservations SET slot_held=1,updated_at=?,cleanup_sha256=NULL WHERE run_id=?',(when,run['run_id']))


def _boundary_marker(action_id,run,history,origin,metadata,when):
    tip=history['events'][-1] if history['events'] else None
    return dict(version=1,action_id=action_id,run_id=run['run_id'],migration_id=digest_manifest(metadata),
        origin_sha256=digest_manifest(origin),run_row_sha256=digest_manifest(run),history_sha256=digest_manifest(history),
        history_tip=None if tip is None else dict(sequence=tip['sequence'],sha256=digest_manifest(tip)),observed_at=when)


def _later_boundary(kind,boundary,when,history_floor,clean):
    """Marker kind is checked against actual retained legacy host operations."""
    run=boundary['run_row'];events=boundary['history']['events']
    if not events or events[-1]['sequence']<=history_floor:
        raise ValueError('Later origin lacks a postmigration legacy history boundary')
    tip=events[-1]
    if _utc(tip['timestamp'])>when or _utc(run['updated_at'])>when:
        raise ValueError('Legacy origin predates its retained history')
    if kind=='legacy_claim':
        if run['owner_id'] is None:raise ValueError('Claim origin lacks original legacy owner')
        if run['state']=='preparing':
            if tip['kind']!='claimed' or tip['old_state']!='queued' or tip['new_state']!='preparing' or run['process_count'] or run['generation']!=1 or run['stage']!='spec' or any(run[k] is not None for k in ('admission','manifest','input_sha256')):
                raise ValueError('Claim origin contradicts the actual queued claim')
        elif run['state']!='ready' or not clean:
            raise ValueError('Claim origin lacks genuine safe-ready continuation')
    elif kind=='reconcile':
        product=run['state']!='queued' and bool(run['owner_id'] or run['admission'] or run['worktree'] or run['process_count'] or any(boundary['history'][name] for name in ('attempts','effects','verdicts')))
        if not product or clean or tip['kind']=='claimed' or tip['new_state']!=run['state']:
            raise ValueError('Reconciliation origin contradicts retained legacy boundary')
    else:raise ValueError('Unavailable legacy origin operation')


def reconcile_legacy(db,journal):
    metadata=_metadata(db)
    from .pipeline_journal import _now
    for saved in db.execute('SELECT * FROM runs'):
        run=dict(saved);run_id=run['run_id']
        if not db.execute('SELECT 1 FROM group_runs WHERE run_id=?',(run_id,)).fetchone():_bind_run(db,run)
        db.execute('UPDATE group_runs SET isolation_kind=? WHERE run_id=?',('legacy_linked' if run['worktree'] else 'unprepared',run_id))
        reservation=db.execute('SELECT * FROM group_reservations WHERE run_id=?',(run_id,)).fetchone()
        if reservation is None and _needs_product(db,run):
            when=_now();held=not _positive_cleanup(db,journal,run)
            _reserve(db,run,held,when)
            for component in _json(run['component_keys']):
                db.execute('INSERT INTO group_component_locks VALUES(?,?,?)',(run['repository'],component,run_id))
            if held:_make_fence(db,journal,run,'reconcile',metadata)
        lease=db.execute('SELECT l.*,a.origin_json FROM group_resource_leases l JOIN group_actions a USING(action_id) WHERE l.run_id=? AND l.held=1',(run_id,)).fetchone()
        if lease is not None and _positive_cleanup(db,journal,run):
            origin=_json(lease['origin_json']);history=_history(db,run_id)
            if digest_manifest(history)!=origin['original_history_sha256']:
                proof=digest_manifest(history)
                db.execute('UPDATE group_resource_leases SET held=0,cleanup_sha256=? WHERE action_id=?',(proof,lease['action_id']))
                db.execute('UPDATE group_reservations SET slot_held=0,cleanup_sha256=?,updated_at=? WHERE run_id=?',(proof,_now(),run_id))
                _event(db,'resource_release',dict(version=1,action_id=lease['action_id'],run_id=run_id,cleanup_sha256=proof,run_row=run,history=history),run_id)


def claim_fence(db,journal,run_id):
    run=dict(db.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone())
    if not db.execute('SELECT 1 FROM group_runs WHERE run_id=?',(run_id,)).fetchone():_bind_run(db,run)
    if not db.execute('SELECT 1 FROM group_reservations WHERE run_id=?',(run_id,)).fetchone():
        from .pipeline_journal import _now
        _reserve(db,run,True,_now())
        for component in _json(run['component_keys']):
            db.execute('INSERT INTO group_component_locks VALUES(?,?,?)',(run['repository'],component,run_id))
    if db.execute('SELECT 1 FROM group_resource_leases WHERE run_id=? AND held=1',(run_id,)).fetchone():
        raise ValueError('Legacy execution already held')
    _make_fence(db,journal,run,'legacy_claim',_metadata(db))


def validate_v2(db,journal,*,objects=None):
    from .pipeline_journal import PipelineJournal,_uuid,_sha,_integer
    objects=objects if objects is not None else {tuple(r) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
    if objects!=catalog():raise ValueError('Unrecognized group pipeline schema')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise ValueError('Invalid group foreign keys')
    metadata=_metadata(db);migration_id=digest_manifest(metadata)
    backup=Path(metadata['backup_path'])
    prefix=journal.path.name+'.groups-v2-'
    if backup.parent!=journal.path.parent or not backup.name.startswith(prefix) or not backup.name.endswith('.backup'):
        raise ValueError('Migration backup path binding mismatch')
    _uuid(backup.name[len(prefix):-len('.backup')])
    PipelineJournal(backup,checkouts=journal.checkouts,forbidden_paths=(*journal.forbidden_paths,journal.path))
    from .group_registration import validate_stored
    registration=validate_stored(db,journal)
    # Registration admits metadata/adoption only; execution tables stay closed.
    for name in ('group_resource_observations','group_fair_cursors',
                 'group_observations','group_main_proofs','group_source_resolutions','group_base_epochs','group_base_updates','group_base_phases'):
        if db.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone():raise ValueError('Group execution is not available')
    events=[]
    for saved in db.execute('SELECT * FROM group_events ORDER BY sequence'):
        event=dict(saved);body=_json(event['body_json'])
        if digest_manifest(body)!=event['body_sha256']:raise ValueError('Invalid group event digest')
        _utc(event['recorded_at'])
        events.append((event,body))
    migrations=[(e,b) for e,b in events if e['kind']=='migration']
    if len(migrations)!=1:raise ValueError('Missing or duplicate migration event')
    event,body=migrations[0]
    if set(body)!={'version','migration_id','metadata','legacy_snapshot'} or type(body['version']) is not int or body['version']!=1 or canonical_json(body['metadata'])!=canonical_json(metadata) or body['migration_id']!=migration_id or event['run_id'] is not None:
        raise ValueError('Migration event metadata mismatch')
    if event['sequence']!=1 or event['recorded_at']!=metadata['completed_at']:
        raise ValueError('Migration event boundary mismatch')
    migration_event=event
    snapshot=body['legacy_snapshot'];initial_holdings=_typed_snapshot(journal,snapshot,classify=True)
    if digest_manifest(snapshot)!=metadata['legacy_snapshot_sha256']:raise ValueError('Migration snapshot digest mismatch')
    _preserved_history(db,snapshot)
    runs={r['run_id']:dict(r) for r in db.execute('SELECT * FROM runs')}
    bindings={r['run_id']:dict(r) for r in db.execute('SELECT * FROM group_runs')}
    if set(bindings)!=set(runs):raise ValueError('Missing legacy group binding')
    for event,body in events:
        if event['kind']=='capacity_epoch' and event['run_id'] is not None:
            raise ValueError('Foreign capacity event domain')
        if event['kind']=='binding' and event['run_id'] is not None:
            target=bindings.get(event['run_id'])
            if target is None or target['run_kind']!='group':raise ValueError('Foreign queued binding event')
    for run_id,row in bindings.items():
        if row['run_kind']=='group':
            from .group_queue import validate_queued
            validate_queued(db,journal,runs[run_id],row,events,registration)
            continue
        binding=_json(row['binding_json'])
        if canonical_json(binding)!=canonical_json(_binding(runs[run_id])) or digest_manifest(binding)!=row['binding_sha256'] or row['run_kind']!='legacy' or any(row[k] is not None for k in ('group_id','authorization_sha256','first_eligible_sequence','current_base_epoch')):
            raise ValueError('Invalid legacy group binding')
        if row['isolation_kind']!=('legacy_linked' if runs[run_id]['worktree'] else 'unprepared'):raise ValueError('Legacy isolation changed')
    actions={row['action_id']:dict(row) for row in db.execute('SELECT * FROM group_actions')}
    leases={row['action_id']:dict(row) for row in db.execute('SELECT * FROM group_resource_leases')}
    if set(actions)!=set(leases):raise ValueError('Missing legacy fence lease')
    boundaries={};boundary_events={};boundary_cleanup={};releases={};markers={}
    for event,body in events:
        if event['kind'] in {'migration','binding','capacity_epoch'}:continue
        if event['kind']=='observation':
            if set(body)!={'version','action_id','run_id','origin_sha256','run_row','history'} or type(body['version']) is not int or body['version']!=1:
                raise ValueError('Invalid legacy origin snapshot')
            key=body['action_id']
            if key in boundaries or key not in actions or event['run_id']!=body['run_id'] or body['run_id']!=actions[key]['run_id']:
                raise ValueError('Ambiguous legacy origin snapshot')
            snap=_boundary_snapshot(body['run_row'],body['history']);boundary_cleanup[key]=_typed_snapshot(journal,snap);_preserved_history(db,snap)
            if body['run_row']['run_id']!=body['run_id'] or any(row['run_id']!=body['run_id'] for rows in body['history'].values() for row in rows):raise ValueError('Foreign legacy origin history')
            boundaries[key]=body
            boundary_events[key]=event
        elif event['kind'] in {'action','reservation'}:
            if set(body)!={'version','action_id','run_id','migration_id','origin_sha256','run_row_sha256','history_sha256','history_tip','observed_at'} or type(body['version']) is not int or body['version']!=1:
                raise ValueError('Invalid legacy host boundary marker')
            key=body['action_id']
            if key in markers or key not in actions or event['run_id']!=body['run_id'] or actions[key]['run_id']!=body['run_id']:
                raise ValueError('Missing, duplicate or foreign legacy host boundary marker')
            markers[key]=(event,body)
        elif event['kind']=='resource_release':
            if set(body)!={'version','action_id','run_id','cleanup_sha256','run_row','history'} or type(body['version']) is not int or body['version']!=1 or body['action_id'] in releases:
                raise ValueError('Invalid legacy release snapshot')
            if body['action_id'] not in actions or actions[body['action_id']]['run_id']!=body['run_id'] or event['run_id']!=body['run_id'] or digest_manifest(body['history'])!=body['cleanup_sha256']:
                raise ValueError('Foreign legacy release snapshot')
            release_snapshot=_boundary_snapshot(body['run_row'],body['history'])
            if body['run_row']['run_id']!=body['run_id'] or any(row['run_id']!=body['run_id'] for rows in body['history'].values() for row in rows):
                raise ValueError('Foreign legacy cleanup history')
            if not _typed_snapshot(journal,release_snapshot):raise ValueError('Unproven legacy cleanup')
            _preserved_history(db,release_snapshot)
            releases[body['action_id']]=body
        else:raise ValueError('Unavailable group event kind')
    if set(boundaries)!=set(actions):raise ValueError('Missing legacy origin snapshot')
    held_by_run={};initial_origins={};later_origins=set()
    history_floor=snapshot['sqlite_sequence'][0]['seq'] if snapshot['sqlite_sequence'] else 0
    for action_id,row in actions.items():
        _uuid(action_id);_uuid(row['run_id'])
        _integer(row['ordinal'],1,2**63-1)
        if row['origin']!='legacy_fence' or row['action_kind']!='legacy_fence' or row['state']!='unknown' or any(row[k] is not None for k in ('owner_id','owner_pid','input_sha256','capacity_epoch','finished_at','completion_json','completion_sha256')):
            raise ValueError('Legacy fence imported executable authority')
        origin=_json(row['origin_json']);boundary=boundaries[action_id]
        observed=_utc(row['started_at'])
        if boundary_events[action_id]['recorded_at']!=row['started_at'] or observed<_utc(metadata['completed_at']):
            raise ValueError('Legacy observation boundary time mismatch')
        if 2<=boundary_events[action_id]['sequence']<=len(initial_holdings)+1:
            expected_kind='migration'
            original=initial_holdings.get(row['run_id'])
            if original is None or row['run_id'] in initial_origins or row['ordinal']!=1 or action_id in markers:
                raise ValueError('Unexpected initial migration origin')
            if canonical_json(boundary['run_row'])!=canonical_json(original['run_row']) or canonical_json(boundary['history'])!=canonical_json(original['history']):
                raise ValueError('Migration origin contradicts authoritative legacy snapshot')
            initial_origins[row['run_id']]=action_id
        else:
            marker=markers.get(action_id)
            if marker is None:raise ValueError('Missing later legacy host boundary marker')
            marker_event,marker_body=marker
            expected_kind={'action':'legacy_claim','reservation':'reconcile'}[marker_event['kind']]
            expected_marker=_boundary_marker(action_id,boundary['run_row'],boundary['history'],origin,metadata,row['started_at'])
            if marker_event['sequence']<=len(initial_holdings)+1 or boundary_events[action_id]['sequence']!=marker_event['sequence']+1 or marker_event['recorded_at']!=row['started_at'] or canonical_json(marker_body)!=canonical_json(expected_marker):
                raise ValueError('Legacy host marker identity/order/time/hash mismatch')
            _later_boundary(expected_kind,boundary,observed,history_floor,boundary_cleanup[action_id])
            later_origins.add(action_id)
        expected=dict(version=1,run_id=row['run_id'],observation_kind=expected_kind,observed_at=row['started_at'],
            original_owner_id=boundary['run_row']['owner_id'],original_owner_pid=boundary['run_row']['owner_pid'],original_state=boundary['run_row']['state'],
            original_input_sha256=boundary['run_row']['input_sha256'],original_run_row_sha256=digest_manifest(boundary['run_row']),
            original_history_sha256=digest_manifest(boundary['history']),migration_id=migration_id)
        if canonical_json(origin)!=canonical_json(expected) or origin['observation_kind'] not in {'migration','legacy_claim','reconcile'} or digest_manifest(origin)!=row['origin_sha256'] or boundary['origin_sha256']!=row['origin_sha256']:
            raise ValueError('Legacy origin provenance mismatch')
        lease=leases[action_id]
        if registration is None:
            if lease['run_id']!=row['run_id'] or any(lease[k] is not None for k in ('observation_id','capacity_epoch','harness_pool','cpu_millis','memory_bytes')) or lease['unknown_estimate']!=1:
                raise ValueError('Invalid pre-registration legacy lease')
        if lease['held']==1:
            if lease['cleanup_sha256'] is not None or action_id in releases:raise ValueError('Held lease claims cleanup')
            held_by_run[row['run_id']]=held_by_run.get(row['run_id'],0)+1
        else:
            release=releases.get(action_id)
            if release is None or release['cleanup_sha256']!=lease['cleanup_sha256']:raise ValueError('Released lease lacks positive history')
    if set(initial_origins)!=set(initial_holdings):raise ValueError('Missing or relabeled initial migration origin')
    if set(markers)!=later_origins:raise ValueError('Unexpected legacy host boundary marker')
    for run_id in runs:
        ordered=sorted((boundary_events[key]['sequence'],row['ordinal']) for key,row in actions.items() if row['run_id']==run_id)
        if [ordinal for _,ordinal in ordered]!=list(range(1,len(ordered)+1)):
            raise ValueError('Legacy action ordinal/order mismatch')
    if any(number>1 for number in held_by_run.values()):raise ValueError('Multiple held legacy actions')
    reservations={r['run_id']:dict(r) for r in db.execute('SELECT * FROM group_reservations')}
    for run_id,row in reservations.items():
        if row['capacity_epoch']!=(1 if registration else None) or row['component_held']!=1 or row['slot_held']!=int(bool(held_by_run.get(run_id))) or row['release_reason'] is not None or row['completion_proof_sha256'] is not None:
            raise ValueError('Legacy reservation mismatch')
        if not _needs_product(db,runs[run_id]) or not row['slot_held'] and not _positive_cleanup(db,journal,runs[run_id]):
            raise ValueError('Legacy execution lacks a conservative fence')
        expected={(runs[run_id]['repository'],component,run_id) for component in _json(runs[run_id]['component_keys'])}
        actual={tuple(r) for r in db.execute('SELECT repository,component,run_id FROM group_component_locks WHERE run_id=?',(run_id,))}
        if actual!=expected:raise ValueError('Legacy component ownership mismatch')
    if any(run_id not in reservations for run_id in held_by_run):raise ValueError('Held action lacks reservation')
    if any(_needs_product(db,run) and run_id not in reservations for run_id,run in runs.items()):raise ValueError('Missing legacy product reservation')


def _stopped(db,journal):
    from .pipeline_journal import _dead
    controller=db.execute('SELECT * FROM controller').fetchone()
    if controller is not None:
        health=_json(controller['health'])
        if not health['stopped'] or health['workers'] or health['dispatcher']:
            raise ValueError('Migration requires a stopped controller with zero helpers')
    for run in db.execute('SELECT * FROM runs WHERE owner_id IS NOT NULL'):
        if not _dead(run['owner_pid']):raise ValueError('Migration requires positively stopped legacy execution owners')


def _report(db,status):
    metadata=_metadata(db)
    return dict(status=status,version=2,migration_id=digest_manifest(metadata),**{k:v for k,v in metadata.items() if k!='singleton'})


def _migration_sidecars(journal):
    """Migration-only refusal checks; none of these bytes authorize recovery."""
    from .pipeline_journal import _open_database_pin,_pin_identity
    from .executor_queue import _private_stat
    journal._assert_existing()
    if any(Path(str(journal.path)+suffix).exists() for suffix in ('-wal','-shm')):
        raise ValueError('Unsupported migration WAL sidecar')
    for child in journal.path.parent.iterdir():
        journal._wait_seconds()
        if child.name.casefold().startswith((journal.path.name+'-mj').casefold()):
            raise ValueError('Unsupported migration super-journal')
    rollback=Path(str(journal.path)+'-journal')
    if not rollback.exists():return False
    before=_pin_identity(_private_stat(rollback))
    fd=_open_database_pin(rollback)
    try:
        opened=_pin_identity(os.fstat(fd))
        if not os.path.samestat(before,opened):raise ValueError('Rollback sidecar changed')
        magic=bytes.fromhex('d9d505f920a163d7')
        if opened.st_size<28 or os.read(fd,8)!=magic:
            raise ValueError('Unqualified migration rollback sidecar')
        os.lseek(fd,-8,os.SEEK_END)
        if os.read(fd,8)==magic:
            raise ValueError('Unsupported migration super-journal footer')
        journal._wait_seconds();journal._assert_existing()
        if not os.path.samestat(opened,_pin_identity(_private_stat(rollback))):
            raise ValueError('Rollback sidecar replaced')
        return True
    finally:os.close(fd)


@contextmanager
def _initial_read(journal):
    """Only first existing-only RO's actual rollback error has a neutral result."""
    had_rollback=_migration_sidecars(journal)
    with ExitStack() as stack:
        try:db=stack.enter_context(journal._db())
        except ValueError as error:
            cause=error.__cause__
            code=getattr(cause,'sqlite_errorcode',None)
            if not isinstance(cause,sqlite3.Error) or type(code) is not int or code!=sqlite3.SQLITE_READONLY_ROLLBACK:
                raise
            journal._assert_existing();_migration_sidecars(journal)
            yield None
            return
        # SQLite may ignore empty, incomplete or stale rollback files. Their
        # presence is not cold qualification, even when a readonly query worked.
        if had_rollback or _migration_sidecars(journal):
            raise ValueError('Unqualified migration rollback sidecar')
        yield db


def inspect(journal):
    with journal.operation_deadline(time.monotonic()+60),journal._pinned_database() as identity:
        if identity is None:return dict(status='missing',version=None)
        with journal._existing_database(identity),_initial_read(journal) as db:
            if db is None:return dict(status='recovery_required',version=None)
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid pipeline integrity')
            journal._assert_existing()
            if version==2:return _report(db,'migrated')
            return dict(status='migration_required',version=1,source_schema_sha256=SOURCE_SCHEMA_SHA256,
                        legacy_snapshot_sha256=digest_manifest(legacy_snapshot(db)),target_schema_sha256=schema_digest())


def _backup(journal,db,snapshot):
    from .pipeline_journal import PipelineJournal
    backup=journal.path.with_name(journal.path.name+'.groups-v2-'+str(uuid.uuid4())+'.backup')
    backup_journal=PipelineJournal(backup,checkouts=journal.checkouts,forbidden_paths=(*journal.forbidden_paths,journal.path))
    backup_journal._safe();journal._assert_existing()
    fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,getattr(os,'S_IRUSR',0o400)|getattr(os,'S_IWUSR',0o200))
    try:
        identity=os.fstat(fd);journal._wait_seconds()
        def progress(status,remaining,total):
            journal._wait_seconds();journal._assert_existing();backup_journal._safe()
            if not os.path.samestat(identity,backup.stat()):raise ValueError('Migration backup replaced')
        with closing(sqlite3.connect(journal.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=journal._wait_seconds())) as source:
            source.row_factory=sqlite3.Row;source.execute('PRAGMA query_only=ON')
            with closing(sqlite3.connect(backup.resolve().as_uri()+'?mode=rw',uri=True,timeout=journal._wait_seconds())) as target:
                target.row_factory=sqlite3.Row;target.execute('PRAGMA synchronous=FULL')
                source.backup(target,pages=64,progress=progress,sleep=0)
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or legacy_snapshot(target)!=snapshot:
                    raise ValueError('Migration backup validation failed')
                journal._validate_db(target)
        progress(0,0,0)
        digest=hashlib.sha256()
        with backup.open('rb') as stream:
            for chunk in iter(lambda:stream.read(65536),b''):
                journal._wait_seconds();digest.update(chunk)
        progress(0,0,0)
        return backup,digest.hexdigest()
    except (OSError,ValueError,sqlite3.Error) as error:
        raise MigrationFailure(backup) from error
    finally:
        os.close(fd)


def migrate(journal):
    created=[]
    try:return _migrate(journal,created.append)
    except MigrationFailure:raise
    except (OSError,ValueError,sqlite3.Error) as error:
        if created:raise MigrationFailure(created[-1]) from error
        raise


def _migrate(journal,backup_created):
    from .pipeline_journal import SCHEMAS,_now
    if digest_manifest(SCHEMAS)!=SOURCE_SCHEMA_SHA256:raise ValueError('Unsupported legacy schema definition')
    with journal.operation_deadline(time.monotonic()+60),journal._pinned_database() as identity:
        if identity is None:raise ValueError('Migration requires an existing journal')
        with journal._existing_database(identity):
            with _initial_read(journal) as db:
                if db is None:return dict(status='recovery_required',version=None)
                if db.execute('PRAGMA user_version').fetchone()[0]==2:return _report(db,'already_migrated')
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid pipeline integrity')
                _stopped(db,journal);before=legacy_snapshot(db)
            _checkpoint('after_inspection');journal._assert_existing()
            if _migration_sidecars(journal):raise ValueError('Rollback sidecar appeared after migration inspection')
            with journal._db(True,initialize=False) as db:
                if db.execute('PRAGMA user_version').fetchone()[0]!=1 or legacy_snapshot(db)!=before:
                    raise ValueError('Legacy migration source changed')
                _stopped(db,journal);journal._assert_existing()
                db.set_progress_handler(lambda:int(time.monotonic()>=journal._operation_deadline),1000)
                backup,backup_sha256=_backup(journal,db,before)
                backup_created(backup)
                _checkpoint('after_backup');journal._assert_existing()
                for statement in DDL.split(';'):
                    if statement.strip():db.execute(statement.strip())
                metadata=dict(singleton=1,source_schema_sha256=SOURCE_SCHEMA_SHA256,target_schema_sha256=schema_digest(),
                    legacy_snapshot_sha256=digest_manifest(before),backup_path=str(backup),backup_sha256=backup_sha256,completed_at=_now())
                db.execute('INSERT INTO group_migration VALUES(?,?,?,?,?,?,?)',tuple(metadata.values()))
                _event(db,'migration',dict(version=1,migration_id=digest_manifest(metadata),metadata=metadata,legacy_snapshot=before),when=metadata['completed_at'])
                for saved in db.execute('SELECT * FROM runs'):
                    run=dict(saved);_bind_run(db,run)
                    if _needs_product(db,run):
                        held=not _positive_cleanup(db,journal,run);_reserve(db,run,held,metadata['completed_at'])
                        for component in _json(run['component_keys']):db.execute('INSERT INTO group_component_locks VALUES(?,?,?)',(run['repository'],component,run['run_id']))
                        if held:_make_fence(db,journal,run,'migration',metadata)
                db.execute('PRAGMA user_version=2')
                validate_v2(db,journal)
                if legacy_snapshot(db)!=before:raise ValueError('Migration modified legacy rows or sequence')
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid migrated integrity')
                journal._assert_existing();journal._wait_seconds();_checkpoint('before_commit')
                result=_report(db,'migrated')
            journal._assert_existing();journal._wait_seconds();_checkpoint('after_commit')
            return result

