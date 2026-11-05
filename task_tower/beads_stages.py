"""Bounded foreground coordination, never an integration/closure authority.

No backend is discovered from JSON or environment. A live StageRoleRunner with
independently qualified containment and host check capability must be supplied
by trusted host code. The CLI therefore refuses when no such host exists.
_Coordinator is the private state machine; injected doubles only test ordering,
not native ownership, model containment or production acceptance.
"""
import argparse
import copy
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
import uuid

from . import beads_admission as admission
from . import beads_stage_roles as roles
from . import beads_test_reporter as test_reporter
from .beads_stage_port import BeadsStagePort, OperationProof, load_stage_policy
from .processes import run_command

_EVENT_TYPE = threading.Event
_EVENT_IS_SET = threading.Event.is_set
_LOCAL_GUARDS = set()
_GUARD_LOCK = threading.Lock()
_FENCED_GUARDS = []  # Retain live OS exclusion if owned cleanup is unknown.
PHASES = (
    ('spec_design', 'spec_author', 'spec_pending'),
    ('spec_design_review', 'spec_acceptor', 'spec_review'),
    ('spec_plan', 'spec_author', 'spec_pending'),
    ('spec_plan_review', 'spec_acceptor', 'spec_review'),
    ('development', 'dev_implementer', 'dev_pending'),
    ('development_review', 'dev_acceptor', 'dev_review'),
    ('test', 'test_executor', 'test_pending'),
    ('test_review', 'test_acceptor', 'test_review'),
)
RUNTIME_PHASES=(*PHASES[:4],('tests_only','dev_implementer','dev_tests_pending'),*PHASES[4:])


def _id():
    return uuid.uuid4().hex


def _stage(index):
    return 'spec' if index < 4 else 'development' if index < 6 else 'test'


def _owned(value):
    roles._keys(value, {'paths', 'domains'})
    paths, domains = value['paths'], value['domains']
    roles._require(isinstance(paths, list) and 1 <= len(paths) <= 1000
                   and isinstance(domains, list) and 1 <= len(domains) <= 1000)
    for path in paths:
        roles._source_name(path)
    roles._require(all(isinstance(d, str) and d not in {'unknown', 'unspecified', 'unattested'}
                       and re.fullmatch(r'[a-z][a-z0-9_.:-]{0,95}', d)
                       for d in domains) and len(set(domains)) == len(domains))
    return [p.casefold() for p in paths], set(domains)


def ownership_disjoint(left, right):
    """Both attested semantic domains AND Windows path prefixes must be disjoint."""
    try:
        a, da = _owned(left)
        b, db = _owned(right)
        return da.isdisjoint(db) and not any(x == y or x.startswith(y+'/') or y.startswith(x+'/')
                                             for x in a for y in b)
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False


def _changed_paths(before,after):
    old={f['name']:f['sha256'] for f in before['files']}
    new={f['name']:f['sha256'] for f in after['files']}
    return {p for p in old.keys()|new.keys() if old.get(p)!=new.get(p)}


def integration_release(candidate):
    return dict(outcome='refused', reason='integration_barrier_unavailable')


class ProjectGuard:
    """Noninheritable, process-lifetime Windows exclusion; no PID/file adoption."""
    def __init__(self, identity):
        roles._require(os.name == 'nt' and isinstance(identity, str) and bool(identity))
        self.key = hashlib.sha256(identity.casefold().encode('utf-8')).hexdigest()
        self.handle = None
        self.abandoned = False

    def acquire(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.SetHandleInformation.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD)
        kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        with _GUARD_LOCK:
            if self.key in _LOCAL_GUARDS:
                raise ValueError('project_session_active')
            handle = kernel.CreateMutexW(None, False, 'Local\\TaskTowerStages-'+self.key)
            if not handle:
                raise ValueError('project_guard_unavailable')
            if not kernel.SetHandleInformation(handle, 1, 0):
                kernel.CloseHandle(handle)
                raise ValueError('project_guard_unavailable')
            outcome = kernel.WaitForSingleObject(handle, 0)
            if outcome not in (0, 0x80):
                kernel.CloseHandle(handle)
                raise ValueError('project_session_active')
            self.handle, self.kernel = handle, kernel
            self.abandoned = outcome == 0x80
            _LOCAL_GUARDS.add(self.key)
        return self

    def release(self):
        with _GUARD_LOCK:
            if self.handle is not None:
                if not self.kernel.ReleaseMutex(self.handle):
                    raise ValueError('project_guard_release_unknown')
                if not self.kernel.CloseHandle(self.handle):
                    raise ValueError('project_guard_release_unknown')
                self.handle = None
                _LOCAL_GUARDS.discard(self.key)


@dataclass
class _Slot:
    bead: str
    actor: str
    pins: dict
    owned: dict
    inputs: dict
    input_digest: str
    run_id: str
    renewed: float
    expiry: float
    index: int = 0
    state: str = 'spec_pending'
    context: dict = field(default_factory=dict)
    corrections: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    earliest_affected_stage: str | None = None
    accepted: list = field(default_factory=list)
    provenance: list = field(default_factory=list)
    cancel: object = None
    thread: object = None
    call: dict | None = None
    launched: float = 0
    worker_kind: str | None = None
    phases: tuple = PHASES
    session_id: str = ''
    event_root: object = None
    events: list = field(default_factory=list)
    pending_correction: object = None
    attempt_deadline: float = 0


class _Halt(Exception):
    def __init__(self, reason, outcome='unknown'):
        self.reason, self.outcome = reason, outcome


@dataclass(frozen=True)
class FrozenHostEvent:
    reference: str
    sha256: str
    path: Path


class _Coordinator:
    """Session-local slots only. All port calls execute on this one caller lane."""
    def __init__(self, policy, port, backend, stop, clock):
        roles._require(type(stop) is _EVENT_TYPE)
        self.policy, self.port, self.backend = copy.deepcopy(policy), port, backend
        self.stop, self.clock = stop, clock
        self.session_id, self.slots = _id(), []
        self.started = self.clock()
        self.results = queue.Queue()
        self.attempted_claims = set()
        self.halting = False
        self.cleanup_confirmed = True
        self._proof_sequence = 0
        if type(port) is BeadsStagePort:
            port.bind_cancellation(stop)

    def _stopping(self):
        return roles._cancelled(self.stop) or self.clock() >= self.started + 8*60*60 - 5

    def _leases(self):
        self._check_stop()
        now = self.clock()
        # A native operation has 30s, then cleanup must finish before expiry.
        for slot in sorted(self.slots, key=lambda s:s.expiry):
            if now + 35 >= slot.expiry:
                raise _Halt('lease_safety_deadline')
            if now >= slot.renewed + 60:
                began = self.clock()
                result = self._port_call('heartbeat',slot.bead,slot.actor)
                if not isinstance(result, dict) or result.get('outcome') != 'ok':
                    raise _Halt('heartbeat_unknown')
                if self.clock() >= began + 30 or self.clock() + 5 >= slot.expiry:
                    raise _Halt('heartbeat_deadline')
                slot.renewed, slot.expiry = began, began + 270
                now = self.clock()

    def _native(self, name, *args,attempt_deadline=None):
        self._check_stop()
        if attempt_deadline is not None and self.clock()+35>=attempt_deadline:
            raise _Halt('role_attempt_deadline')
        self._leases()
        self._check_stop()
        if attempt_deadline is not None and self.clock()+35>=attempt_deadline:
            raise _Halt('role_attempt_deadline')
        began = self.clock()
        value = self._port_call(name,*args)
        if attempt_deadline is not None and self.clock()+5>=attempt_deadline:
            raise _Halt('role_attempt_deadline')
        if self.clock() >= began + 30:
            raise _Halt('native_operation_deadline')
        if not isinstance(value, dict) or value.get('outcome') not in {'ok', 'refused', 'unknown'}:
            raise _Halt('native_operation_unknown')
        return value

    def _check_stop(self):
        if self._stopping():
            self.stop.set()
            raise _Halt('stop_requested','refused')

    def _port_call(self,name,*args):
        if self.clock()+35>=self.started+8*60*60:
            self.stop.set()
            raise _Halt('stop_requested','refused')
        try:
            return getattr(self.port,name)(*args)
        finally:
            if type(self.port) is BeadsStagePort:
                proof=self.port.get_operation_proof()
                if (type(proof) is not OperationProof or proof.sequence != self._proof_sequence+1
                        or proof.complete is not True):
                    self.cleanup_confirmed=False
                if type(proof) is OperationProof:
                    self._proof_sequence=proof.sequence

    def _host_wait(self, slot, operation):
        """Host Git/hash/check work must never hold the serialized renewal lane."""
        roles._require(slot.thread is None)
        self._check_stop()
        completed = queue.Queue(maxsize=1)
        slot.cancel = threading.Event()
        slot.worker_kind = 'host'
        began = self.clock()
        deadline=slot.attempt_deadline or min(self.started+8*60*60,began+30*60)
        def worker():
            try:
                with roles.attempt_budget(deadline,self.clock):
                    value=operation()
                completed.put((True,value))
            except Exception as error:
                if isinstance(error,roles.ProcessCleanupUnknown):
                    self.cleanup_confirmed=False
                completed.put((False, None))
        slot.thread = threading.Thread(target=worker, name='tower-host-'+_id(), daemon=False)
        slot.thread.start()
        while True:
            self._check_stop()
            self._leases()
            if self._stopping():
                raise _Halt('stop_requested', 'refused')
            if self.clock() >= deadline-5 or any(s.worker_kind == 'role' and s.thread is not None
                    and self.clock() >= s.launched+30*60-5 for s in self.slots):
                raise _Halt('role_attempt_deadline')
            try:
                success, result = completed.get(timeout=.05)
                break
            except queue.Empty:
                continue
        slot.thread.join(timeout=5)
        if self.clock()>=deadline-5:
            raise _Halt('role_attempt_deadline')
        if slot.thread.is_alive():
            raise _Halt('host_thread_completion_unknown')
        slot.thread, slot.worker_kind = None, None
        if not success:
            self.cleanup_confirmed = False
            raise _Halt('host_operation_unknown')
        return result

    def _event(self, slot, state, body):
        self._check_stop()
        record=self.backend.persist_host_event(slot,state,body)
        roles._require(type(record) is FrozenHostEvent)
        self.backend.verify_host_event(record,slot,state,body)
        event = dict(value=state, reference=record.reference, digest=record.sha256)
        result = self._native('append_event', slot.bead, slot.actor, event,attempt_deadline=slot.attempt_deadline or None)
        if result['outcome'] != 'ok':
            raise _Halt('host_event_unknown')
        self.backend.verify_host_event(record,slot,state,body)
        slot.events.append(record)
        slot.state = state

    def _verify(self, slot):
        result = self._native('verify_owner_and_eligibility', slot.bead, slot.actor, slot.pins,attempt_deadline=slot.attempt_deadline or None)
        if result['outcome'] != 'ok':
            raise _Halt('owner_policy_or_base_invalid')
        inputs = self._native('read_task_inputs', slot.bead, slot.actor, slot.pins,attempt_deadline=slot.attempt_deadline or None)
        if inputs['outcome'] != 'ok':
            raise _Halt('task_input_read_unknown')
        if inputs.get('input_digest') != slot.input_digest or inputs.get('inputs') != slot.inputs:
            slot.earliest_affected_stage = 'spec'
            slot.accepted.clear()
            self._event(slot, 'needs_input', {'reason': 'task_inputs_changed', 'stage': 'spec'})
            return False
        result = self._host_wait(slot, lambda: self.backend.revalidate(slot))
        if not isinstance(result, dict) or result.get('outcome') != 'ok':
            raise _Halt('source_or_backend_invalid')
        return True

    def _admit(self):
        if len(self.slots) == 2 or self._stopping():
            return False
        ready = self._native('ready')
        if ready['outcome'] != 'ok':
            raise _Halt('ready_unavailable', ready['outcome'])
        tasks = ready.get('tasks')
        if not isinstance(tasks, list) or len(tasks) > 1000:
            raise _Halt('ready_invalid')
        seen = set()
        for task in tasks:
            if not isinstance(task, dict) or set(task) != {'bead', 'priority', 'issue_type'}:
                raise _Halt('ready_invalid')
            if not admission._match(task['bead'], admission.BEAD) or task['bead'] in seen:
                raise _Halt('ready_invalid')
            if type(task['priority']) is not int or not 0 <= task['priority'] <= 4:
                raise _Halt('ready_invalid')
            seen.add(task['bead'])
        changed = False
        for task in sorted(tasks, key=lambda t:(t['priority'], t['bead'])):
            if len(self.slots) == 2 or self._stopping():
                break
            bead = task['bead']
            owned = self.policy['ownership'].get(bead)
            if bead in self.attempted_claims or owned is None:
                continue
            try:
                _owned(owned)
            except (ValueError, TypeError, KeyError):
                continue
            if not all(ownership_disjoint(owned, slot.owned) for slot in self.slots):
                continue
            actor, began = 'ttstage-'+_id(), self.clock()
            self.attempted_claims.add(bead)
            claim = self._native('claim', bead, actor, {})  # Port itself performs fresh admission.
            if claim['outcome'] == 'unknown':
                raise _Halt('claim_unknown')
            if claim['outcome'] != 'ok':
                continue  # No effect/retry/adoption for this observation.
            pins = claim.get('pins')
            if not isinstance(pins, dict):
                raise _Halt('claim_pins_unknown')
            slot = _Slot(bead, actor, pins, copy.deepcopy(owned), {}, '', _id(), began, began+270)
            slot.session_id=self.session_id;slot.cancel=threading.Event()
            if type(self.backend) is StageRoleRunner:
                slot.phases=self.backend.host_checks.phase_plan(bead)
            self.slots.append(slot)  # Retain ownership even when subsequent validation fails.
            check = self._native('verify_owner_and_eligibility', bead, actor, pins)
            if check['outcome'] != 'ok':
                raise _Halt('postclaim_invalid')
            inputs = self._native('read_task_inputs', bead, actor, pins)
            if inputs['outcome'] != 'ok' or not isinstance(inputs.get('inputs'), dict):
                raise _Halt('task_inputs_unknown')
            roles._keys(inputs['inputs'], roles.CRITERIA)
            if inputs.get('input_digest') != admission._digest(inputs['inputs']):
                raise _Halt('task_input_digest_unknown')
            slot.inputs, slot.input_digest = copy.deepcopy(inputs['inputs']), inputs['input_digest']
            self._event(slot, 'claimed', dict(kind='host_start', run_id=slot.run_id,
                owned=owned, policy_digest=pins['policy_digest'], input_digest=slot.input_digest))
            slot.context = self._host_wait(slot, lambda: self.backend.prepare(slot))
            changed = True
        return changed

    def _launch(self, slot):
        if slot.thread is not None or slot.state in {'needs_input', 'fenced', 'candidate_for_integration'}:
            return False
        slot.launched=self.clock();slot.attempt_deadline=slot.launched+30*60
        if not self._verify(slot):
            return False
        phase, role, state = slot.phases[slot.index]
        call = dict(phase=phase, role=role, instance_id=_id(), attempt_id=_id(), actor='ttrole-'+_id(),
                    session_id=self.session_id, run_id=slot.run_id,
                    stage={'spec':'spec','dev':'development','test':'test'}[role.split('_')[0]])
        self._event(slot, state, dict(kind='launch_intent', call=call,correction=slot.pending_correction,
            previous_completion=copy.deepcopy(slot.provenance[-1]) if slot.provenance else None))
        slot.pending_correction=None
        if self._stopping():
            raise _Halt('stop_requested', 'refused')
        slot.cancel, slot.call = threading.Event(), call
        slot.worker_kind = 'role'
        def worker():
            try:
                with roles.attempt_budget(slot.attempt_deadline,self.clock):
                    result = self.backend.execute(slot, call, slot.cancel)
            except Exception:
                result = dict(outcome='unknown', reason='role_worker_unknown')
            self.results.put((slot, call, result))
        slot.thread = threading.Thread(target=worker, name='tower-role-'+call['instance_id'], daemon=False)
        slot.thread.start()
        return True

    def _completed(self, slot, call, result):
        slot.thread.join(timeout=5)
        if slot.thread.is_alive():
            raise _Halt('role_thread_completion_unknown')
        slot.thread, slot.worker_kind = None, None
        fact = result.get('process', {}) if isinstance(result,dict) else {}
        if (isinstance(result,dict) and result.get('outcome')!='ok' and fact.get('status')=='timeout'
                and fact.get('cleanup_confirmed') is True and fact.get('eof_confirmed') is True):
            if not self._verify(slot): return
            slot.findings=['The owned role attempt reached its fixed deadline.']
            slot.earliest_affected_stage=call['stage']
            slot.provenance.append(dict(call=call,evidence=dict(kind='role_timeout',process=fact)))
            self._event(slot,'needs_input',dict(reason='role_attempt_timeout',process_sha256=admission._digest(fact)))
            return
        if not isinstance(result, dict) or result.get('outcome') != 'ok':
            fact = result.get('process', {}) if isinstance(result, dict) else {}
            if fact.get('cleanup_confirmed') is not True or fact.get('eof_confirmed') is not True:
                self.cleanup_confirmed = False
            raise _Halt('role_completion_unknown')
        fact = result.get('process', {})
        if fact.get('cleanup_confirmed') is not True or fact.get('eof_confirmed') is not True:
            self.cleanup_confirmed = False
            raise _Halt('role_cleanup_unknown')
        if self.clock() >= slot.launched + 30*60-5:
            raise _Halt('role_attempt_deadline')
        if not self._verify(slot):
            return
        result = self._host_wait(slot, lambda: self.backend.complete(slot, call, result))
        if not isinstance(result, dict) or result.get('outcome') != 'ok':
            raise _Halt('role_evidence_unverified')
        if not self._verify(slot):  # Recheck after host checkpoint/artifact effects and before acceptance.
            return
        slot.provenance.append(dict(call=call, evidence=copy.deepcopy(result.get('evidence', {}))))
        findings = result.get('findings', [])
        if not isinstance(findings, list) or len(findings) > 128 or any(not isinstance(s, str) or len(s.encode('utf-8')) > 4096 for s in findings):
            raise _Halt('findings_invalid')
        verdict = result.get('verdict')
        if verdict not in {'approve', 'reject', 'needs_input'}:
            raise _Halt('verdict_invalid')
        if verdict != 'approve':
            # TEST rejection implies a repair at DEV, invalidating downstream TEST.
            stage = 'development' if call['stage']=='test' else call['stage']
            slot.findings = findings
            slot.earliest_affected_stage = stage
            slot.accepted = [a for a in slot.accepted if a['stage'] != stage and
                             {'spec': 0, 'development': 1, 'test': 2}[a['stage']] <
                             {'spec': 0, 'development': 1, 'test': 2}[stage]]
            self.backend.invalidate(slot, stage)
            if verdict == 'needs_input' or slot.corrections.get(stage, 0) >= 1:
                self._event(slot, 'needs_input', dict(stage=stage, findings_sha256=admission._digest(findings)))
                return
            slot.corrections[stage] = 1
            slot.index = {'spec': 0, 'development': 4, 'test': 6}[stage]
            slot.pending_correction=dict(stage=stage,findings_sha256=admission._digest(findings),
                feedback=copy.deepcopy(slot.context.get('feedback_inputs',[])))
            slot.state=slot.phases[slot.index][2]
            return
        slot.index += 1
        milestones={'spec_plan_review':'spec_approved','tests_only':'dev_red_observed',
                    'development_review':'dev_approved','test_review':'candidate_for_integration'}
        if call['phase'] in milestones:
            state = milestones[call['phase']]
            self._event(slot, state, dict(kind='host_checkpoint', call=call,
                evidence=copy.deepcopy(result.get('evidence', {}))))
        if slot.index < len(slot.phases):
            slot.state = slot.phases[slot.index][2]

    def _cleanup(self):
        deadline = time.monotonic() + 5  # Actual cleanup bound, independent of injected policy clock.
        if self.halting or _EVENT_IS_SET(self.stop):
            self.stop.set()
        for slot in self.slots:
            if slot.thread is not None:
                slot.cancel.set()
        for slot in self.slots:
            if slot.thread is not None:
                slot.thread.join(max(0, deadline-time.monotonic()))
                if slot.thread.is_alive():
                    self.cleanup_confirmed = False
        while True:
            try:
                slot, call, result = self.results.get_nowait()
            except queue.Empty:
                break
            fact = result.get('process', {}) if isinstance(result, dict) else {}
            if fact.get('cleanup_confirmed') is not True or fact.get('eof_confirmed') is not True:
                self.cleanup_confirmed = False

    def run(self):
        outcome, reason = 'ok', 'known_handoff'
        finished=threading.Event()
        def fanout():
            try:
                while not finished.wait(.01):
                    if roles._cancelled(self.stop):
                        for owned in tuple(self.slots):
                            if type(owned.cancel) is _EVENT_TYPE: owned.cancel.set()
            except Exception:
                self.cleanup_confirmed=False;self.stop.set()
        watcher=threading.Thread(target=fanout,name='tower-stop-fanout',daemon=False)
        watcher.start()
        try:
            while True:
                if self._stopping():
                    raise _Halt('stop_requested', 'refused')
                self._leases()
                self._admit()
                for slot in self.slots:
                    self._launch(slot)
                if not any(s.thread is not None for s in self.slots):
                    if any(s.state == 'needs_input' for s in self.slots):
                        outcome, reason = 'refused', 'task_needs_input'
                    break
                try:
                    slot, call, result = self.results.get(timeout=.05)
                except queue.Empty:
                    if any(s.thread is not None and self.clock() >= s.launched+30*60-5 for s in self.slots):
                        raise _Halt('role_attempt_deadline')
                    continue
                self._completed(slot, call, result)
        except _Halt as halt:
            outcome, reason, self.halting = halt.outcome, halt.reason, True
        except Exception:
            outcome, reason, self.halting = 'unknown', 'session_operation_unknown', True
        finally:
            self._cleanup()
            finished.set();watcher.join(1)
            if watcher.is_alive(): self.cleanup_confirmed=False
        if not self.cleanup_confirmed:
            outcome, reason = 'unknown', 'owned_cleanup_unknown'
        if self.halting and outcome == 'unknown':
            for slot in self.slots:
                slot.state = 'fenced'
        production = type(self.backend) is StageRoleRunner
        return dict(kind='beads.stages.session' if production else 'beads.stages.synthetic_observation',
                    production_acceptance=False, outcome=outcome, reason=reason, cleanup_confirmed=self.cleanup_confirmed,
                    tasks=[dict(bead=s.bead, state=s.state) for s in self.slots])


def run_session(policy_path: Path, *, stop_requested, clock=None, port_factory=None, role_runner=None):
    # A default CLI or arbitrary injected callable must never reach native claim.
    if type(role_runner) is not StageRoleRunner:
        return dict(outcome='refused', reason='qualified_backend_unavailable', tasks=[])
    return role_runner.run_session(policy_path, stop_requested=stop_requested, clock=clock,
                                   port_factory=port_factory)


class StageRoleRunner:
    """Concrete live host adapter; qualification is supplied by host authority."""
    def __init__(self, profile_path: Path, authority, *, mode='production', host_checks=None):
        roles._require(type(authority) is roles.RoleAuthority and mode in {'production', 'qualification'})
        self.profile_path, self.authority, self.mode = profile_path, authority, mode
        self.host_checks = host_checks
        self.profile = roles.load_role_profile(profile_path, mode=mode, authority=authority)

    def run_session(self, policy_path, *, stop_requested, clock=None, port_factory=None):
        guard, controller = None, None
        try:
            # These are live host objects, never profile booleans/JSON factories.
            if type(self.host_checks) not in (HostCheckAuthority,RuntimeCheckAuthority):
                return dict(outcome='refused', reason='host_check_capability_unavailable', tasks=[])
            if port_factory is not None:
                return dict(outcome='refused', reason='synthetic_port_cannot_enable_production', tasks=[])
            roles._require(os.name == 'nt' and type(stop_requested) is _EVENT_TYPE)
            self.policy = load_stage_policy(policy_path)
            roles._require(Path(self.policy['role_profile']).resolve() == self.profile_path.resolve())
            self._profile_current()
            check = self.host_checks.preflight(self.policy)
            if check['outcome'] != 'ok':
                return dict(outcome='refused', reason=check['reason'], tasks=[])
            config = admission.load_config(Path(self.policy['admission_config']))
            self.project = next(p for p in config['projects'] if p['id'] == self.policy['project'])
            # Identity is the qualified repository + project + actual local database.
            identity = self.project['repository']+'\0'+self.project['id']+'\0'+str(
                admission._directory(self.project['directory']).resolve())
            guard = ProjectGuard(identity).acquire()
            port = BeadsStagePort(self.policy, clock=clock,cancel_requested=stop_requested)
            controller = _Coordinator(self.policy, port, self, stop_requested, clock or time.monotonic)
            return controller.run()
        except (ValueError, OSError, KeyError, TypeError, UnicodeError, admission._Stop):
            return dict(outcome='unknown' if controller is not None else 'refused',
                        reason='session_preflight_unavailable', tasks=[])
        finally:
            if guard is not None:
                if controller is not None and not controller.cleanup_confirmed:
                    _FENCED_GUARDS.append(guard)
                else:
                    try:
                        guard.release()
                    except (OSError, ValueError):
                        _FENCED_GUARDS.append(guard)
                        return dict(outcome='unknown', reason='project_guard_release_unknown', tasks=[])

    def _profile_current(self,cancel_requested=None):
        profile = roles.load_role_profile(self.profile_path, mode=self.mode, authority=self.authority,cancel_requested=cancel_requested)
        roles._require(profile == self.profile)

    @staticmethod
    def _event_envelope(slot,state,reference,body):
        return dict(schema=1,kind='beads.host.event',bead=slot.bead,actor=slot.actor,
            session_id=slot.session_id,run_id=slot.run_id,state=state,reference=reference,body=body)

    def persist_host_event(self,slot,state,body):
        roles._check_cancel(slot.cancel)
        if slot.event_root is None:
            parent=admission._directory(self.policy['evidence_root'])
            root=admission.safe_config_path(parent/('host-events-'+slot.run_id))
            roles._require(not root.exists())
            root.mkdir();slot.event_root=root
        root=admission._directory(str(slot.event_root))
        reference='host-'+_id()
        raw=roles._bytes(self._event_envelope(slot,state,reference,body))
        roles._require(len(raw)<=roles.LIMIT)
        path=admission.safe_config_path(root/(reference+'.json'))
        with path.open('xb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        path.chmod(0o444)
        record=FrozenHostEvent(reference,hashlib.sha256(raw).hexdigest(),path)
        self.verify_host_event(record,slot,state,body)
        return record

    def verify_host_event(self,record,slot,state,body):
        roles._check_cancel(slot.cancel)
        roles._require(type(record) is FrozenHostEvent and slot.event_root is not None
            and record.path==slot.event_root/(record.reference+'.json'))
        try:
            path=roles._file(record.path,roles.LIMIT)
            raw=path.read_bytes()
        except OSError:
            raise ValueError('host_event_unavailable') from None
        expected=roles._bytes(self._event_envelope(slot,state,record.reference,body))
        roles._require(raw==expected and hashlib.sha256(raw).hexdigest()==record.sha256)

    def prepare(self, slot):
        self._profile_current(slot.cancel)
        root = admission._directory(self.policy['worktree_root'])
        evidence = admission._directory(self.policy['evidence_root'])
        source = admission._directory(self.project['source'])
        session = slot.run_id
        worktree = admission.safe_config_path(root / ('source-'+session))
        inputs = admission.safe_config_path(root / ('inputs-'+session))
        outputs = admission.safe_config_path(root / ('outputs-'+session))
        private = admission.safe_config_path(evidence / ('run-'+session))
        roles._require(not any(p.exists() for p in (worktree, inputs, outputs, private)))
        base = slot.pins['base']['head']
        roles._require(base == self.project['expected_head'])
        # Fixed host Git only. Unknown mutations remain intact; never retry/remove.
        roles._git(source, 'worktree', 'add', '--lock', '-b', 'tower-stage/'+session, str(worktree), base,cancel_requested=slot.cancel)
        for path in (inputs, outputs, private):
            roles._check_cancel(slot.cancel)
            path.mkdir()
        snapshot = roles.snapshot_source(worktree, base,cancel_requested=slot.cancel)
        roles._require(snapshot['head'] == base and snapshot['tree'] == slot.pins['base']['tree'])
        return dict(source=worktree, inputs=inputs, outputs=outputs, evidence=private,
                    snapshot=snapshot, pending_role=None, review_inputs=[], pending=None, checks=[], authority=self.authority,
                    feedback_inputs=[],red=None)

    def _host_input(self,slot,name,value):
        roles._check_cancel(slot.cancel)
        raw=roles._bytes(value)
        roles._require(len(raw)<=roles.LIMIT)
        path=slot.context['inputs']/name
        with path.open('xb') as stream: stream.write(raw)
        path.chmod(0o444)
        record=self.authority.register_accepted_artifact(name,path,hashlib.sha256(raw).hexdigest(),cancel_requested=slot.cancel)
        return dict(name=record.name,sha256=record.sha256)

    def _feedback(self,slot,call,value,source):
        stage='development' if call['stage']=='test' else call['stage']
        body=dict(schema=1,kind='beads.stage.correction',task=slot.bead,instance_id=call['instance_id'],
            affected_stage=stage,source={k:v for k,v in source.items() if k!='files'},
            rejected_artifacts=copy.deepcopy(value['reviewed']),findings=copy.deepcopy(value['findings']))
        ref=self._host_input(slot,'feedback-'+_id()+'.json',body)
        slot.context['feedback_inputs'].append(ref)
        slot.context['review_inputs'].append(ref)
        return ref

    def revalidate(self, slot):
        try:
            self._profile_current(slot.cancel)
            roles._require(load_stage_policy(self.policy._source_path) == self.policy)
            context = slot.context
            role = context.get('pending_role') or 'spec_acceptor'
            check = roles.verify_stage_source(context['source'], context['snapshot'],
                                             role=role, owned_paths=slot.owned['paths'],cancel_requested=slot.cancel)
            roles._require(check['outcome'] == 'ok')
            return dict(outcome='ok')
        except roles.ProcessCleanupUnknown:
            raise
        except (ValueError, OSError, KeyError, TypeError, UnicodeError, admission._Stop):
            return dict(outcome='refused', reason='source_or_backend_changed')

    def _manifest(self, slot, call):
        roles._check_cancel(slot.cancel)
        context = slot.context
        name = 'manifest-'+call['instance_id']+'.json'
        path = context['inputs']/name
        raw = roles._bytes(context['snapshot'])
        roles._require(len(raw) <= roles.SOURCE_INPUT_LIMIT)
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o444)
        record = self.authority.register_source_input(name, path,cancel_requested=slot.cancel)
        roles._require(record.sha256 == hashlib.sha256(raw).hexdigest())
        return dict(name=name, sha256=record.sha256)

    def execute(self, slot, call, cancel):
        self._profile_current(cancel)
        context = slot.context
        scope=self.host_checks.scope(slot,call) if type(self.host_checks) is RuntimeCheckAuthority else (
            tuple(slot.owned['paths']) if call['role']=='dev_implementer' else ())
        if type(self.authority) is roles.RoleAuthority:
            self.authority.register_phase_scope(call['instance_id'],tuple(scope))
        phase_input=dict(schema=1,kind='beads.stage.phase',phase=call['phase'],allowed_paths=list(scope),
            selection=self.host_checks.selection(slot.bead,call['phase']),
            checks=self._check_references(context['checks']),
            review_requirement='Assess actual RED relevance to intended missing behavior; process exit alone is insufficient.')
        context['review_inputs'].append(self._host_input(slot,'phase-'+call['phase']+'-'+call['instance_id']+'.json',phase_input))
        snapshot = context['snapshot']
        output = context['outputs']/call['instance_id']
        evidence = context['evidence']/call['instance_id']
        for path in (output, evidence):
            roles._check_cancel(cancel)
            admission.safe_config_path(path).mkdir()
        references = copy.deepcopy(context['review_inputs'])
        binding = dict(task=self.project['repository']+':beads:'+self.project['id']+':'+slot.bead,
            session_id=call['session_id'], run_id=call['run_id'], attempt_id=call['attempt_id'],
            instance_id=call['instance_id'], actor=call['actor'], stage=call['stage'],
            policy_digest=slot.pins['policy_digest'], input_digest=slot.input_digest,
            superpowers_digest=admission._digest(self.profile['superpowers']),
            base=snapshot['base'], head=snapshot['head'], tree=snapshot['tree'],
            diff_digest=snapshot['diff_digest'], accepted_artifacts=references)
        # Each call has a collision-free host-selected output. Prose supplies no paths/commands.
        names = [] if call['role'].endswith('_acceptor') else [call['phase']+'-'+call['instance_id']+'.md']
        request = dict(schema=1, kind='beads.role.request', binding=binding, role=call['role'],
            criteria=copy.deepcopy(slot.inputs), source_manifest=self._manifest(slot, call), output_names=names)
        context['pending_role'] = call['role']
        result = roles.run_role(self.profile, request, mode=self.mode, authority=self.authority,
            source=context['source'], output=output, evidence=evidence, cancel_requested=cancel)
        # Only live adapter-private state carries the actual source and output paths.
        context['pending'] = dict(call=copy.deepcopy(call), request=request, output=output,
                                  evidence=evidence, result=copy.deepcopy(result))
        return result

    def _freeze(self, slot, pending):
        references = []
        for item in pending['result']['result']['artifacts']:
            source = pending['output']/item['name']
            roles._require(roles._hash_file(source,cancel_requested=slot.cancel) == item['sha256'])
            target = slot.context['inputs']/item['name']
            admission.safe_config_path(target)
            roles._require(not target.exists())
            # File bytes are copied only after known EOF/cleanup and actual hash checks.
            with roles._file(source, roles.SOURCE_INPUT_LIMIT).open('rb') as incoming, target.open('xb') as outgoing:
                while block := incoming.read(65536):
                    roles._check_cancel(slot.cancel)
                    outgoing.write(block)
            target.chmod(0o444)
            record = self.authority.register_accepted_artifact(item['name'], target, item['sha256'],cancel_requested=slot.cancel)
            references.append(dict(name=record.name, sha256=record.sha256))
        return references

    def _checkpoint(self, slot, result):
        context = slot.context
        before = context['snapshot']
        verified = roles.verify_stage_source(context['source'], before,
            role='dev_implementer', owned_paths=slot.owned['paths'],cancel_requested=slot.cancel)
        roles._require(verified['outcome'] == 'ok' and verified['source'] == result['source'])
        if verified['source'] == before:
            return before  # Explicit artifact-only docs qualification; no empty commit/fake code delta.
        if type(self.host_checks) is HostCheckAuthority:
            self.host_checks.check_documentation_delta(before, verified['source'])
        paths=context.get('phase_scope',slot.owned['paths'])
        roles._git(context['source'], 'add', '--all', '--', *paths,cancel_requested=slot.cancel)
        roles._git(context['source'], '-c', 'user.name=Task Tower', '-c', 'user.email=task-tower@invalid',
            'commit', '--no-verify', '--no-gpg-sign', '-m', 'Task Tower owned stage checkpoint',cancel_requested=slot.cancel)
        after = roles.snapshot_source(context['source'], before['base'],cancel_requested=slot.cancel)
        roles._require(after['files'] == verified['source']['files']
                       and after['git_config_digest'] == before['git_config_digest'])
        context['snapshot'] = after
        return after

    def complete(self, slot, call, result):
        try:
            pending, context = slot.context['pending'], slot.context
            roles._require(pending['call'] == call and pending['result'] == result)
            # Re-parse actual files, not just a caller's copied result dictionary.
            value = roles.validate_role_result(pending['output']/'result.json', pending['request']['binding'],
                                              reviewer=call['role'].endswith('_acceptor'),cancel_requested=slot.cancel)
            roles._require(value == result['result'] and result['event']['instance_id'] == call['instance_id']
                           and result['event']['binding_sha256'] == admission._digest(pending['request']['binding'])
                           and roles._hash_file(pending['output']/'result.json',cancel_requested=slot.cancel) == result['result_sha256'])
            references = self._freeze(slot, pending)
            verdict = value.get('verdict', 'approve')
            if call['role'] == 'dev_implementer':
                if type(self.host_checks) is RuntimeCheckAuthority:
                    scope=self.host_checks.scope(slot,call)
                    before=context['snapshot'];after=result['source']
                    changed=_changed_paths(before,after)
                    roles._require(call['phase']!='development' or (context['red'] is not None and
                        self.host_checks.test_pins(after,slot.bead)==context['red']['test_pins']))
                    roles._require(all(any(roles.within_scope(p,s) for s in scope) for p in changed))
                    context['phase_scope']=scope
                self._checkpoint(slot, result)
            else:
                roles._require(result['source'] == context['snapshot'])
            context['pending_role'] = None
            if references:
                # Accepted as immutable review INPUT; never stage acceptance.
                context['review_inputs'].extend(references)
            if verdict in {'reject','needs_input'}:
                self._feedback(slot,call,value,result['source'])
            if call['role'].endswith('_acceptor') and verdict == 'approve':
                if type(self.host_checks) is RuntimeCheckAuthority and call['phase']=='development_review':
                    roles._require(context['red'] is not None and any(c.get('phase')=='development' for c in context['checks']))
                    context['red']['relevance']='independently_reviewed'
                    context['red']['review_instance_id']=call['instance_id']
                slot.accepted.append(dict(stage=call['stage'], phase=call['phase'],
                    references=copy.deepcopy(context['review_inputs']), source=copy.deepcopy(context['snapshot'])))
            if call['role'] in {'dev_implementer', 'test_executor'}:
                check = self.host_checks.run(slot, call, slot.cancel)
                roles._require(check['outcome'] == 'ok')
                if 'runner_report' in check:
                    context['review_inputs'].append(check['runner_report'])
                report=self._host_input(slot,'check-report-'+call['phase']+'-'+call['instance_id']+'.json',check)
                check['report']=report
                context['review_inputs'].append(report)
                context['checks'].append(check)
            evidence = dict(event=result['event'], process=result['process'],
                checkpoint={k:v for k,v in context['snapshot'].items() if k!='files'},
                checks=self._check_references(context['checks']))
            context['pending'] = None
            return dict(outcome='ok', verdict=verdict, findings=value['findings'], evidence=evidence)
        except roles.ProcessCleanupUnknown:
            raise
        except (ValueError, OSError, KeyError, TypeError, UnicodeError, admission._Stop):
            return dict(outcome='unknown', reason='live_role_evidence_invalid')

    @staticmethod
    def _check_references(checks):
        return [{k:copy.deepcopy(c[k]) for k in ('kind','phase','source_manifest_sha256','process','processes',
            'selection_digest','report') if k in c} for c in checks]

    def invalidate(self, slot, stage):
        context = slot.context
        # Keep immutable registry entries as inert evidence, removing only active
        # review/acceptance references. Rejected evidence never regains authority.
        inputs = {}
        for accepted in slot.accepted:
            for reference in accepted['references']:
                inputs[reference['name']] = reference
        for reference in context['feedback_inputs']:
            inputs[reference['name']]=reference
        context['review_inputs'] = list(inputs.values())
        context['checks'] = []
        context['red']=None
        context['pending'] = None
        context['pending_role'] = None


@dataclass(frozen=True)
class HostCheckSandbox:
    """Live grant from independently qualified host containment, never model JSON."""
    source: Path
    evidence: Path
    manifest_sha256: str
    artifacts: tuple = ()


class HostCheckAuthority:
    """Host construction requires independently verified fixed check containment.

    No serializable factory/default is provided. qualification_verifier is trusted
    host code that verifies the installed sandbox's prevention/private exclusion
    facts; sandbox_factory establishes that isolation per actual invocation.
    Only explicitly host-attested documentation tasks are supported for now.
    Runtime TDD needs a separately approved midpoint protocol, not baseline RED.
    """
    def __init__(self, *, documentation_tasks, sandbox_factory, qualification_verifier):
        roles._require(isinstance(documentation_tasks, set) and bool(documentation_tasks)
                       and all(admission._match(t, admission.BEAD) for t in documentation_tasks)
                       and callable(sandbox_factory) and callable(qualification_verifier))
        self.documentation_tasks = frozenset(documentation_tasks)
        self._sandbox_factory, self._qualification_verifier = sandbox_factory, qualification_verifier

    def preflight(self, policy):
        try:
            if not set(policy['ownership']) <= self.documentation_tasks:
                return dict(outcome='refused', reason='dev_red_checkpoint_unavailable')
            from .ci_docs import _prose
            for owned in policy['ownership'].values():
                _owned(owned)
                roles._require(all(_prose(p) for p in owned['paths']))
            roles._require(self._qualification_verifier(self) is True)
            return dict(outcome='ok')
        except Exception:
            return dict(outcome='refused', reason='host_check_capability_unavailable')

    def phase_plan(self,bead): return PHASES

    def selection(self,bead,phase): return dict(kind='documentation.validation',runtime_tests='not_run')

    @staticmethod
    def check_documentation_delta(before, after):
        from .ci_docs import _prose
        old = {f['name']: f['sha256'] for f in before['files']}
        new = {f['name']: f['sha256'] for f in after['files']}
        changed = {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)}
        roles._require(bool(changed) and all(_prose(p) and p in new for p in changed))

    def run(self, slot, call, cancel):
        roles._require(slot.bead in self.documentation_tasks and type(cancel) is _EVENT_TYPE
                       and self._qualification_verifier(self) is True)
        context = slot.context
        before = context['snapshot']
        records = tuple(context['authority'].get_accepted_artifact(a['name'])
                        for a in context['review_inputs'])
        roles._require(type(cancel) is _EVENT_TYPE);roles._check_cancel(cancel)
        grant = self._sandbox_factory(context['source'], copy.deepcopy(before), call['instance_id'], records, cancel)
        roles._check_cancel(cancel)
        roles._require(type(grant) is HostCheckSandbox and grant.manifest_sha256 == before['manifest_sha256'])
        roles._require(type(grant.artifacts) is tuple and len(grant.artifacts) == len(records)
                       and all(a is b for a, b in zip(grant.artifacts, records)))
        for record, reference in zip(records, context['review_inputs']):
            roles._require(type(record) is roles.AcceptedArtifactInput and record.sha256 == reference['sha256']
                           and roles._hash_file(record.path,cancel_requested=cancel) == record.sha256)
        source, evidence = (admission._directory(str(p)) for p in (grant.source, grant.evidence))
        roots = (context['source'], context['inputs'], context['outputs'], context['evidence'])
        roles._require(all(source != p and not source.is_relative_to(p) and not p.is_relative_to(source) for p in roots)
                       and source != evidence and not source.is_relative_to(evidence) and not evidence.is_relative_to(source)
                       and not any(evidence.iterdir()))
        actual = roles.snapshot_source(source, before['base'],cancel_requested=cancel)
        roles._require(actual == before)
        # Every source diff is checked, including when there are also artifacts.
        commands = [('documentation_diff_check',
            ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL',
             '-c', 'protocol.allow=never', 'diff', '--no-ext-diff', '--no-textconv', '--check', before['base'], '--'])]
        # Explicit docs-only route: no artificial RED, no task/model supplied argv.
        documents=tuple(r for r in records if r.name.endswith('.md'))
        if documents:
            # Fixed host-selected validation over exact immutable, readonly-granted
            # files. This verifies document structure, never semantic acceptance.
            program = (
                'import pathlib,sys\n'
                'for name in sys.argv[1:]:\n'
                ' p=pathlib.Path(name)\n'
                ' raw=p.read_bytes()\n'
                ' assert 0<len(raw)<=16777216 and p.suffix==".md" and b"\\x00" not in raw\n'
                ' text=raw.decode("utf-8")\n'
                ' assert text.strip() and any(s.startswith("# ") for s in text.splitlines())\n'
                ' assert all(s==s.rstrip() for s in text.splitlines())\n'
                'print("validated_documents",len(sys.argv)-1)\n')
            commands.append(('documentation_artifact_check',
                [sys.executable, '-I', '-B', '-c', program, *(str(record.path) for record in documents)]))
        facts = []
        for operation, argv in commands:
            capture = evidence/operation
            capture.mkdir()
            receipt = run_command(argv, source, roles.remaining_budget(10), env=roles._environment(),
                cancel_requested=lambda: _EVENT_IS_SET(cancel),
                capture=dict(directory=capture, max_bytes_per_stream=roles.CAPTURE_LIMIT))
            fact = admission._process_fact(operation, receipt)
            if not fact['cleanup_confirmed'] or not fact['eof_confirmed']:
                raise roles.ProcessCleanupUnknown('host_check_cleanup_unknown')
            roles._require(fact['status'] == 'passed' and fact['exit_code'] == 0 and fact['cleanup_confirmed']
                           and fact['eof_confirmed'] and receipt.get('started') is True
                           and all(receipt.get(s+'_truncated') is False for s in ('stdout', 'stderr')))
            facts.append(fact)
        roles._require(roles.snapshot_source(source, before['base'],cancel_requested=cancel) == before
                       and all(roles._hash_file(r.path,cancel_requested=cancel) == r.sha256 for r in records))
        return dict(outcome='ok', kind='documentation.validation', runtime_tests='not_run',
                    source_manifest_sha256=before['manifest_sha256'], process=facts[-1], processes=facts)


@dataclass(frozen=True)
class RuntimeCheckSandbox:
    source: Path
    evidence: Path
    manifest_sha256: str
    execution: object
    artifacts: tuple = ()
    reporter: Path | None = None
    report_output: Path | None = None


class RuntimeExecutionCapability:
    """Host-only independently qualified execution of untrusted project tests.

    A source folder is not this capability. The trusted launcher must establish
    actual command containment/private exclusion and use the Windows supervisor.
    No JSON factory, guessed backend or plain-host fallback is provided here.
    """
    def __init__(self,*,launcher,qualification_verifier):
        roles._require(callable(launcher) and callable(qualification_verifier))
        self._launcher,self._verifier=launcher,qualification_verifier
        self.executable=Path(sys.executable).resolve()
        self.executable_sha256=roles._hash_file(self.executable)
        self.reporter=Path(test_reporter.__file__).resolve()
        self.reporter_sha256=roles._hash_file(self.reporter)

    def preflight(self,cancel_requested=None):
        return (self._verifier(self) is True
            and roles._hash_file(self.executable,cancel_requested=cancel_requested)==self.executable_sha256
            and roles._hash_file(self.reporter,cancel_requested=cancel_requested)==self.reporter_sha256)

    def run(self,grant,selection,cancel):
        roles._require(type(grant) is RuntimeCheckSandbox and grant.execution is self
                       and type(cancel) is _EVENT_TYPE and self.preflight(cancel)
                       and grant.reporter == self.reporter and isinstance(grant.report_output,Path))
        roles._check_cancel(cancel)
        invocation=_id()
        argv=[str(self.executable),'-I','-B',str(self.reporter),str(grant.report_output),
            invocation,grant.manifest_sha256,json.dumps(list(selection),separators=(',',':'))]
        environment=roles._environment();environment['PYTHONDONTWRITEBYTECODE']='1'
        try:
            receipt=self._launcher(argv,grant.source,grant.evidence,cancel,environment,roles.remaining_budget(30*60))
        except Exception:
            raise roles.ProcessCleanupUnknown('runtime_execution_unknown') from None
        fact=admission._process_fact('runtime_unittest',receipt)
        if not fact['cleanup_confirmed'] or not fact['eof_confirmed']:
            raise roles.ProcessCleanupUnknown('runtime_execution_cleanup_unknown')
        roles._require(receipt.get('started') is True and all(receipt.get(s+'_truncated') is False for s in ('stdout','stderr')))
        return receipt,fact,invocation


class RuntimeCheckAuthority:
    """Fixed operator selections and live execution; runtime route is nine calls."""
    def __init__(self,*,test_paths,selected_tests,sandbox_factory,qualification_verifier,execution):
        roles._require(type(execution) is RuntimeExecutionCapability and callable(sandbox_factory)
            and callable(qualification_verifier) and isinstance(test_paths,dict) and bool(test_paths)
            and set(test_paths)==set(selected_tests) and len(test_paths)<=1000)
        for bead,paths in test_paths.items():
            roles._require(admission._match(bead,admission.BEAD) and type(paths) is tuple and 1<=len(paths)<=1000)
            _owned(dict(paths=list(paths),domains=['runtime-tests']))
            normalized=[p.casefold() for p in paths]
            roles._require(not any(a==b or a.startswith(b+'/') or b.startswith(a+'/')
                for i,a in enumerate(normalized) for b in normalized[i+1:]))
            tests=selected_tests[bead]
            roles._require(type(tests) is tuple and 1<=len(tests)<=64 and len(set(tests))==len(tests)
                and all(isinstance(t,str) and len(t)<=256 and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,15}',t) for t in tests))
        self.test_paths=copy.deepcopy(test_paths);self.selected_tests=copy.deepcopy(selected_tests)
        self.execution=execution;self._factory=sandbox_factory;self._verifier=qualification_verifier

    def phase_plan(self,bead):
        roles._require(bead in self.test_paths)
        return RUNTIME_PHASES

    def _scopes(self,bead,owned):
        tests=self.test_paths[bead]
        paths=owned['paths'];_owned(owned)
        normalized=[p.casefold() for p in paths]
        roles._require(not any(a==b or a.startswith(b+'/') or b.startswith(a+'/')
            for i,a in enumerate(normalized) for b in normalized[i+1:]))
        roles._require(all(any(roles.within_scope(t,p) for p in paths) for t in tests))
        implementation=tuple(p for p in paths if all(not(roles.within_scope(p,t) or roles.within_scope(t,p)) for t in tests))
        roles._require(bool(implementation))
        return tests,implementation

    def preflight(self,policy):
        try:
            roles._require(set(policy['ownership'])<=set(self.test_paths) and self.execution.preflight()
                           and self._verifier(self) is True)
            for bead,owned in policy['ownership'].items():self._scopes(bead,owned)
            return dict(outcome='ok')
        except Exception:
            return dict(outcome='refused',reason='runtime_check_capability_unavailable')

    def scope(self,slot,call):
        tests,implementation=self._scopes(slot.bead,slot.owned)
        return tests if call['phase']=='tests_only' else implementation if call['phase']=='development' else ()

    def selection(self,bead,phase):
        tests=self.selected_tests[bead]
        return dict(kind='runtime.unittest',selected_tests=list(tests),test_paths=list(self.test_paths[bead]),
                    phase=phase,full_test=phase in {'test','test_review'},executable_sha256=self.execution.executable_sha256)

    def test_pins(self,snapshot,bead):
        return [copy.deepcopy(f) for f in snapshot['files'] if any(roles.within_scope(f['name'],p) for p in self.test_paths[bead])]

    def run(self,slot,call,cancel):
        phase=call['phase'];roles._require(phase in {'tests_only','development','test'} and self._verifier(self) is True)
        context=slot.context;before=context['snapshot']
        records=tuple(context['authority'].get_accepted_artifact(a['name']) for a in context['review_inputs'])
        roles._require(type(cancel) is _EVENT_TYPE);roles._check_cancel(cancel)
        grant=self._factory(context['source'],copy.deepcopy(before),call['instance_id'],records,self.execution,self.execution.reporter,cancel)
        roles._check_cancel(cancel)
        roles._require(type(grant) is RuntimeCheckSandbox and grant.execution is self.execution
            and grant.manifest_sha256==before['manifest_sha256'] and type(grant.artifacts) is tuple
            and len(grant.artifacts)==len(records) and all(a is b for a,b in zip(grant.artifacts,records))
            and grant.reporter==self.execution.reporter and isinstance(grant.report_output,Path))
        source,evidence=(admission._directory(str(p)) for p in (grant.source,grant.evidence))
        roles._require(grant.source==source and grant.evidence==evidence)
        for root in (context['source'],context['inputs'],context['outputs'],context['evidence']):
            roles._require(source!=root and not source.is_relative_to(root) and not root.is_relative_to(source))
        roles._require(source!=evidence and not evidence.is_relative_to(source) and not source.is_relative_to(evidence)
                       and not any(evidence.iterdir()))
        report_output=admission.safe_config_path(grant.report_output)
        report_parent=admission._directory(str(report_output.parent))
        roles._require(grant.report_output==report_output and grant.report_output.is_absolute()
            and not report_output.exists() and not any(report_parent.iterdir()))
        for root in (source,evidence,context['source'],context['inputs'],context['outputs'],context['evidence']):
            roles._require(report_parent!=root and not report_parent.is_relative_to(root) and not root.is_relative_to(report_parent))
        roles._require(roles.snapshot_source(source,before['base'],cancel_requested=cancel)==before)
        for record,ref in zip(records,context['review_inputs']):
            roles._require(record.sha256==ref['sha256'] and roles._hash_file(record.path,cancel_requested=cancel)==record.sha256)
        selection=(*self.selected_tests[slot.bead],'-v') if phase!='test' else ('discover','-s','tests','-v')
        selection_digest=admission._digest(list(selection))
        pins=self.test_pins(before,slot.bead);roles._require(bool(pins))
        if phase=='development':
            roles._require(context['red'] is not None and context['red']['selection_digest']==selection_digest
                           and context['red']['test_pins']==pins)
        receipt,fact,invocation=self.execution.run(grant,selection,cancel)
        observations=admission._json(roles._file(report_output,test_reporter.MAX_REPORT).read_bytes())
        exclusions=test_reporter.validate(observations,invocation,before['manifest_sha256'],selection,
            check_cancel=lambda:roles._check_cancel(cancel))
        streams={}
        for stream in ('stdout','stderr'):
            path=roles._file(evidence/(stream+'.log'),roles.CAPTURE_LIMIT)
            digest=roles._hash_file(path,cancel_requested=cancel)
            roles._require(digest==receipt.get(stream+'_sha256')
                and path.stat().st_size==receipt.get(stream+'_bytes')==receipt.get(stream+'_captured_bytes'))
            streams[stream]=dict(sha256=digest,bytes=path.stat().st_size)
        output={s:roles._file(evidence/(s+'.log'),roles.CAPTURE_LIMIT).read_bytes()[:8192].decode('utf-8',errors='replace')
                for s in ('stdout','stderr')}
        if phase=='tests_only':
            roles._require(fact['status']=='failed' and fact['exit_code']==1
                           and re.search(r'Ran [1-9][0-9]* tests?',output['stderr']) is not None
                           and 'FAILED (' in output['stderr'])
        else:roles._require(fact['status']=='passed' and fact['exit_code']==0)
        roles._require(observations['successful']==(phase!='tests_only'))
        roles._require(roles.snapshot_source(source,before['base'],cancel_requested=cancel)==before
            and all(roles._hash_file(record.path,cancel_requested=cancel)==record.sha256 for record in records)
            and self.execution.preflight(cancel))
        result=dict(outcome='ok',kind='runtime.check',phase=phase,source_manifest_sha256=before['manifest_sha256'],
            process=fact,selection=list(selection),selection_digest=selection_digest,test_pins=pins)
        report=dict(schema=1,kind='runtime.execution.report',source_manifest_sha256=before['manifest_sha256'],
            selection=list(selection),selection_digest=selection_digest,runner_observations=observations,
            exclusions=exclusions,host_supervisor=dict(process=fact,streams=streams),
            reporter_sha256=self.execution.reporter_sha256,
            context=dict(streams=output,limit_bytes_per_stream=8192,kind='captured_prefix'))
        raw=roles._bytes(report);roles._require(len(raw)<=test_reporter.MAX_REPORT)
        name='runtime-report-'+call['instance_id']+'.json';target=context['inputs']/name
        with target.open('xb') as stream:stream.write(raw)
        target.chmod(0o444)
        record=context['authority'].register_accepted_artifact(name,target,hashlib.sha256(raw).hexdigest(),cancel_requested=cancel)
        result['runner_report']=dict(name=record.name,sha256=record.sha256)
        result['coverage']={key:observations[key] for key in ('tests_run','failures','errors','skips','expected_failures','unexpected_successes')}
        if phase=='tests_only':
            result['failure_context']=output
            result['relevance']='pending_independent_dev_review'
            context['red']=copy.deepcopy(result)
        return result


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('invalid_arguments')
    parser = Parser(prog='task-tower-beads-stages', allow_abbrev=False)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--project', required=True)
    try:
        args = parser.parse_args(argv)
        result = run_session(args.policy, stop_requested=threading.Event())
    except ValueError:
        result = dict(outcome='refused', reason='invalid_arguments', tasks=[])
    print(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return {'ok': 0, 'refused': 2, 'unknown': 3}[result['outcome']]


if __name__ == '__main__':
    raise SystemExit(main())
