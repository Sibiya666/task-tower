"""Controller contract fixtures are synthetic; they grant no live role authority."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import time
import tempfile
import sys
import uuid
import unittest
from unittest.mock import patch

from task_tower import beads_stages as stages


class BoundaryTests(unittest.TestCase):
    def test_qualification_cannot_enter_ordinary_dispatch_before_candidate_binding(self):
        runner=object.__new__(stages.StageRoleRunner);runner.mode='qualification'
        runner.host_checks=stages.HostCheckAuthority(documentation_tasks={'tt-a'},
            sandbox_factory=lambda *a:None,qualification_verifier=lambda *a:True)
        with patch.object(stages,'load_stage_policy',side_effect=AssertionError('ordinary policy dispatch forbidden')) as policy:
            result=runner.run_session(Path('not-a-policy.json'),stop_requested=threading.Event())
            policy.assert_not_called()
        self.assertEqual(result,dict(outcome='refused',reason='qualification_requires_explicit_candidate',tasks=[]))
    def test_runtime_helper_rejects_case_alias_overlap_even_before_policy_loader(self):
        execution=stages.RuntimeExecutionCapability(launcher=lambda *a:None,qualification_verifier=lambda *a:True)
        checks=stages.RuntimeCheckAuthority(test_paths={'tt-a':('tests',)},selected_tests={'tt-a':('tests.test_behavior',)},
            sandbox_factory=lambda *a:None,qualification_verifier=lambda *a:True,execution=execution)
        with self.assertRaises(ValueError):checks._scopes('tt-a',dict(paths=['src','tests','TESTS/helper'],domains=['runtime']))
    def test_runtime_windows_mixed_case_scope_and_test_pins_preserve_actual_names(self):
        execution=stages.RuntimeExecutionCapability(launcher=lambda *a:None,qualification_verifier=lambda *a:True)
        checks=stages.RuntimeCheckAuthority(test_paths={'tt-a':('tests',)},selected_tests={'tt-a':('tests.test_behavior',)},
            sandbox_factory=lambda *a:None,qualification_verifier=lambda *a:True,execution=execution)
        scope=checks._scopes('tt-a',dict(paths=['SRC','TESTS'],domains=['runtime']))
        self.assertEqual(scope,(('tests',),('SRC',)))
        pin=dict(name='Tests/Test_Behavior.py',sha256='a'*64)
        self.assertEqual(checks.test_pins(dict(files=[pin]),'tt-a'),[pin])

    def test_runtime_supervisor_consumes_same_absolute_attempt_budget(self):
        from tests.test_beads_admission import facts
        clock=ManualClock();clock.advance(1790);timeouts=[]
        execution=stages.RuntimeExecutionCapability(launcher=lambda *a:timeouts.append(a[-1]) or facts(started=True),
            qualification_verifier=lambda *a:True)
        grant=stages.RuntimeCheckSandbox(Path.cwd(),Path.cwd(),'a'*64,execution,
            reporter=execution.reporter,report_output=Path.cwd()/'unused-synthetic-report.json')
        with stages.roles.attempt_budget(1800,clock):
            execution.run(grant,('tests.test_behavior','-v'),threading.Event())
        self.assertEqual(timeouts,[5])
    def test_runtime_capability_has_nine_fixed_phases_and_refuses_folder_only_execution(self):
        with self.assertRaises(ValueError):
            stages.RuntimeCheckAuthority(test_paths={'tt-a':('tests',)},
                selected_tests={'tt-a':('tests.test_behavior',)},sandbox_factory=lambda *a:None,
                qualification_verifier=lambda *a:True,execution=None)
        execution=stages.RuntimeExecutionCapability(launcher=lambda *a:None,qualification_verifier=lambda *a:True)
        checks=stages.RuntimeCheckAuthority(test_paths={'tt-a':('tests',)},
            selected_tests={'tt-a':('tests.test_behavior',)},sandbox_factory=lambda *a:None,
            qualification_verifier=lambda *a:True,execution=execution)
        self.assertEqual([p[0] for p in checks.phase_plan('tt-a')],
            ['spec_design','spec_design_review','spec_plan','spec_plan_review','tests_only',
             'development','development_review','test','test_review'])

    def test_runtime_fixed_selections_reject_commands_and_invalid_test_subsets(self):
        execution=stages.RuntimeExecutionCapability(launcher=lambda *a:None,qualification_verifier=lambda *a:True)
        for selected in (('tests.test_a;echo PRIVATE',),('--model=bad',),('../bad',),()):
            with self.subTest(selected=selected),self.assertRaises(ValueError):
                stages.RuntimeCheckAuthority(test_paths={'tt-a':('tests',)},selected_tests={'tt-a':selected},
                    sandbox_factory=lambda *a:None,qualification_verifier=lambda *a:True,execution=execution)
    def test_default_backend_refuses_before_any_claim_or_worktree_effect(self):
        effects = []
        result = stages.run_session(Path('private-policy.json'), stop_requested=threading.Event(),
                                    port_factory=lambda *a, **k: effects.append('port'))
        self.assertEqual(result['outcome'], 'refused')
        self.assertEqual(result['reason'], 'qualified_backend_unavailable')
        self.assertEqual(effects, [])

    def test_injected_runner_dictionary_is_not_live_authority(self):
        result = stages.run_session(Path('private-policy.json'), stop_requested=threading.Event(),
                                    role_runner={'qualified': True, 'done': True})
        self.assertEqual(result['reason'], 'qualified_backend_unavailable')

    def test_integration_release_never_consumes_forged_done(self):
        self.assertEqual(stages.integration_release({'done': True, 'closed': True}),
                         {'outcome': 'refused', 'reason': 'integration_barrier_unavailable'})

    def test_cli_does_not_echo_private_arguments(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = stages.main(['--policy', 'PRIVATE_SECRET', '--project', 'PRIVATE_PROJECT'])
        self.assertEqual(code, 2)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['reason'], 'qualified_backend_unavailable')

    def test_concrete_adapter_missing_check_capability_refuses_before_policy_or_port(self):
        from task_tower import beads_stage_roles as roles
        authority = roles.RoleAuthority(approvals={}, qualifications={}, containment_verifier=lambda *a: None)
        with patch.object(roles, 'load_role_profile', return_value={'synthetic': True}):
            runner = stages.StageRoleRunner(Path('synthetic-profile.json'), authority)
        effects = []
        result = stages.run_session(Path('DO_NOT_READ'), stop_requested=threading.Event(),
            role_runner=runner, port_factory=lambda *a, **k: effects.append('port'))
        self.assertEqual(result['reason'], 'host_check_capability_unavailable')
        self.assertEqual(effects, [])

    def test_check_capability_never_accepts_runtime_tdd_without_midpoint_protocol(self):
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda *a: None, qualification_verifier=lambda *a: True)
        self.assertEqual(checks.preflight({'ownership': {'tt-code': {'paths': ['task_tower/a.py'],
            'domains': ['code']}}})['reason'], 'dev_red_checkpoint_unavailable')

    def test_check_capability_requires_live_host_qualification(self):
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda *a: None, qualification_verifier=lambda *a: False)
        self.assertEqual(checks.preflight({'ownership': {'tt-doc': {'paths': ['docs/a.md'],
            'domains': ['docs']}}})['outcome'], 'refused')

    def test_check_capability_never_takes_commands_from_task_prose(self):
        with self.assertRaises(TypeError):
            stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
                sandbox_factory=lambda *a: None, qualification_verifier=lambda *a: True,
                argv=['powershell', '-Command', 'UNTRUSTED'])

    def test_documentation_attestation_does_not_allow_product_code_paths(self):
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda *a: None, qualification_verifier=lambda *a: True)
        result = checks.preflight({'ownership': {'tt-doc': dict(paths=['code.py'], domains=['docs'])}})
        self.assertEqual(result['outcome'], 'refused')


class OwnershipTests(unittest.TestCase):
    def test_disjoint_paths_shared_domain_cannot_run_concurrently(self):
        self.assertFalse(stages.ownership_disjoint(
            {'paths': ['src/a'], 'domains': ['state']},
            {'paths': ['src/b'], 'domains': ['state']}))

    def test_shared_path_disjoint_domains_cannot_run_concurrently(self):
        for path in ('SRC/A', 'src/a/child', 'src'):
            with self.subTest(path=path):
                self.assertFalse(stages.ownership_disjoint(
                    {'paths': ['src/a'], 'domains': ['state']},
                    {'paths': [path], 'domains': ['other']}))

    def test_disjoint_paths_and_domains_allow_two_slots(self):
        self.assertTrue(stages.ownership_disjoint(
            {'paths': ['src/a'], 'domains': ['state']},
            {'paths': ['src/ab'], 'domains': ['other']}))

    def test_unknown_domain_never_inferred_from_prose(self):
        for bad in ({'paths': ['b']}, {'paths': ['b'], 'domains': []},
                    {'paths': ['b'], 'domains': ['unknown prose']},
                    {'paths': ['b'], 'domains': ['unknown']}):
            self.assertFalse(stages.ownership_disjoint({'paths': ['a'], 'domains': ['state']}, bad))

    def test_windows_aliases_cannot_prove_disjoint_ownership(self):
        for path in ('a/../b', 'a.', 'a\\b', 'a:stream', 'NUL.txt', 'x//b', '/x', '.git/config'):
            with self.subTest(path=path):
                self.assertFalse(stages.ownership_disjoint(
                    {'paths': ['valid'], 'domains': ['state']},
                    {'paths': [path], 'domains': ['other']}))


class NativePortFixture:
    """External native contract double, never production authority."""
    def __init__(self, tasks=('tt-a', 'tt-b', 'tt-c')):
        self.tasks = tasks
        self.effects = []
        self.claims = {}
        self.changed_inputs = set()
        self.owner_lost = set()
        self.heartbeat_outcome = 'ok'
        self.policy = 'a' * 64
        self.stage_values = {}
        self.native_event_ids = []

    def ready(self):
        self.effects.append(('ready',))
        return dict(outcome='ok', tasks=[dict(bead=b, priority=1, issue_type='task')
                    for b in self.tasks if b not in self.claims])

    def claim(self, bead, actor, admission):
        self.effects.append(('claim', bead, actor))
        if bead in self.claims:
            return dict(outcome='refused', reason='already_claimed')
        self.claims[bead] = actor
        return dict(outcome='ok', pins=dict(policy_digest=self.policy,
            native_contract_digest='b' * 64, project='fixture',
            base=dict(head='c' * 40, tree='d' * 40)))

    def verify_owner_and_eligibility(self, bead, actor, pins):
        self.effects.append(('verify', bead))
        good = self.claims.get(bead) == actor and bead not in self.owner_lost
        return dict(outcome='ok' if good else 'refused', reason='fixture_owner')

    def read_task_inputs(self, bead, actor, pins):
        from task_tower.beads_admission import _digest
        self.effects.append(('inputs', bead))
        inputs = dict(title='task', description='', design='', acceptance_criteria='', notes='')
        if bead in self.changed_inputs:
            inputs['description'] = 'changed private task text'
        return dict(outcome='ok', inputs=inputs, input_digest=_digest(inputs))

    def append_event(self, bead, actor, event):
        if set(event) != {'value', 'reference', 'digest'}:
            raise AssertionError('public event schema')
        self.effects.append(('event', bead, event['value']))
        if self.stage_values.get(bead)==event['value']:
            return dict(outcome='unknown',reason='native_noop_has_no_event')
        self.stage_values[bead]=event['value']
        event_id='synthetic-event-'+str(len(self.native_event_ids)+1)
        self.native_event_ids.append(event_id)
        return dict(outcome='ok', event_reference=event_id, event_digest=event['digest'])

    def heartbeat(self, bead, actor):
        self.effects.append(('heartbeat', bead))
        return dict(outcome=self.heartbeat_outcome, reason='fixture_renewal')


class SyntheticBackend:
    """No executable/profile/authority. Only private coordinator simulations."""
    def __init__(self):
        self.effects = []
        self.calls = []
        self.results = {}
        self.hook = None
        self.active = 0
        self.maximum = 0
        self.lock = threading.Lock()
        self.event_bodies = {}

    def prepare(self, slot):
        self.effects.append(('prepare', slot.bead))
        return {'checkpoint': 'initial'}

    def persist_host_event(self,slot,state,body):
        from task_tower.beads_stage_roles import _bytes
        reference='host-'+uuid.uuid4().hex
        envelope=stages.StageRoleRunner._event_envelope(slot,state,reference,body)
        self.event_bodies[reference]=copy.deepcopy(envelope)
        return stages.FrozenHostEvent(reference,hashlib.sha256(_bytes(envelope)).hexdigest(),Path(__file__).resolve().parent/(reference+'.json'))

    def verify_host_event(self,record,slot,state,body):
        self_expected=stages.StageRoleRunner._event_envelope(slot,state,record.reference,body)
        if self.event_bodies[record.reference]!=self_expected:raise ValueError('synthetic_event_changed')

    def revalidate(self, slot):
        return dict(outcome='ok')

    def execute(self, slot, call, cancel):
        if type(cancel) is not threading.Event:
            raise AssertionError('memory-only cancellation event required')
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.calls.append((slot.bead, call.copy()))
        try:
            if self.hook:
                self.hook(slot, call, cancel)
            return dict(outcome='ok', verdict=self.results.get((slot.bead, call['phase']), 'approve'),
                        findings=['fixture finding'], process=dict(eof_confirmed=True, cleanup_confirmed=True),
                        evidence={'synthetic': True})
        finally:
            with self.lock:
                self.active -= 1

    def complete(self, slot, call, result):
        return result

    def invalidate(self, slot, stage):
        pass


class CoordinatorTests(unittest.TestCase):
    def test_native_attempt_budget_is_rechecked_after_renewal(self):
        clock=ManualClock();controller=stages._Coordinator(self.policy(),NativePortFixture(),SyntheticBackend(),threading.Event(),clock)
        with patch.object(controller,'_leases',side_effect=lambda:clock.advance(1770)),patch.object(controller,'_port_call') as call:
            with self.assertRaises(stages._Halt):controller._native('verify',attempt_deadline=1800)
            call.assert_not_called()

    def test_host_completion_cannot_reset_attempt_deadline(self):
        clock=ManualClock();port=NativePortFixture(('tt-a',));backend=SyntheticBackend()
        controller=stages._Coordinator(self.policy(),port,backend,threading.Event(),clock)
        slot=stages._Slot('tt-a','actor',{},dict(paths=['src'],domains=['a']),{},'',uuid.uuid4().hex,0,10000)
        slot.attempt_deadline=1800;slot.call={'phase':'development'};slot.launched=0
        clock.advance(1790)
        def completion():clock.advance(8);return dict(outcome='ok')
        with self.assertRaises(stages._Halt):controller._host_wait(slot,completion)
        controller._cleanup()
    def policy(self):
        return dict(project='fixture', ownership={b: dict(paths=['src/'+b], domains=[b])
                    for b in ('tt-a', 'tt-b', 'tt-c')})

    def run_fixture(self, port=None, backend=None, policy=None, stop=None, clock=None):
        self.port = port or NativePortFixture()
        self.backend = backend or SyntheticBackend()
        self.controller = stages._Coordinator(policy or self.policy(), self.port, self.backend,
                                              stop or threading.Event(), clock or time.monotonic)
        return self.controller.run()

    def test_candidate_retains_slot_and_third_task_is_not_claimed(self):
        result = self.run_fixture()
        self.assertEqual([s['state'] for s in result['tasks']],
                         ['candidate_for_integration', 'candidate_for_integration'])
        self.assertEqual(set(self.port.claims), {'tt-a', 'tt-b'})
        self.assertLessEqual(self.backend.maximum, 2)
        for bead in ('tt-a', 'tt-b'):
            self.assertEqual([c['phase'] for b, c in self.backend.calls if b == bead],
                ['spec_design', 'spec_design_review', 'spec_plan', 'spec_plan_review',
                 'development', 'development_review', 'test', 'test_review'])
        calls = [call for _, call in self.backend.calls]
        self.assertEqual(len({c['instance_id'] for c in calls}), 16)
        self.assertEqual(len({c['attempt_id'] for c in calls}), 16)

    def test_every_host_projection_changes_native_state_and_saves_exact_event_envelope(self):
        result=self.run_fixture()
        self.assertEqual(result['outcome'],'ok')
        for bead in ('tt-a','tt-b'):
            values=[e[2] for e in self.port.effects if e[:2]==('event',bead)]
            self.assertEqual(values,['claimed','spec_pending','spec_review','spec_pending','spec_review',
                'spec_approved','dev_pending','dev_review','dev_approved','test_pending','test_review','candidate_for_integration'])
        self.assertTrue(self.backend.event_bodies)

    def test_claimed_progress_does_not_rerun_preclaim_observe(self):
        self.run_fixture()
        self.assertEqual(sum(e[0] == 'claim' for e in self.port.effects), 2)
        for bead in self.port.claims:
            effects = [e[0] for e in self.port.effects if len(e) > 1 and e[1] == bead]
            self.assertEqual(effects[:4], ['claim', 'verify', 'inputs', 'event'])
        self.assertEqual(len(self.backend.effects), 2)

    def test_needs_input_allows_independent_peer(self):
        backend = SyntheticBackend()
        backend.results[('tt-a', 'spec_design_review')] = 'needs_input'
        result = self.run_fixture(backend=backend)
        self.assertEqual([s['state'] for s in result['tasks']],
                         ['needs_input', 'candidate_for_integration'])
        self.assertEqual(self.controller.slots[0].findings, ['fixture finding'])

    def test_rejected_stage_has_one_correction_then_pauses(self):
        backend = SyntheticBackend()
        backend.results[('tt-a', 'spec_plan_review')] = 'reject'
        result = self.run_fixture(backend=backend)
        self.assertEqual(result['tasks'][0]['state'], 'needs_input')
        phases = [c['phase'] for b, c in backend.calls if b == 'tt-a']
        self.assertEqual(phases, ['spec_design', 'spec_design_review', 'spec_plan', 'spec_plan_review',
                                 'spec_design', 'spec_design_review', 'spec_plan', 'spec_plan_review'])
        self.assertEqual(self.controller.slots[0].earliest_affected_stage, 'spec')

    def test_task_input_mutation_invalidates_stage(self):
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        backend.hook = lambda slot, call, cancel: port.changed_inputs.add(slot.bead)
        result = self.run_fixture(port=port, backend=backend)
        self.assertEqual(result['tasks'][0]['state'], 'needs_input')
        self.assertEqual(len(backend.calls), 1)

    def test_host_history_and_heartbeat_do_not_invalidate_task_inputs(self):
        result = self.run_fixture()
        self.assertEqual(result['outcome'], 'ok')

    def test_owner_base_or_unowned_source_change_blocks_advancement(self):
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        backend.hook = lambda slot, call, cancel: port.owner_lost.add(slot.bead)
        result = self.run_fixture(port=port, backend=backend)
        self.assertEqual(result['outcome'], 'unknown')
        self.assertEqual(len(backend.calls), 1)

    def test_foreign_prior_claim_is_never_adopted(self):
        port = NativePortFixture(('tt-a',))
        port.claims['tt-a'] = 'prior-session'
        self.run_fixture(port=port)
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(port.claims['tt-a'], 'prior-session')

    def test_stop_prevents_claims(self):
        stop = threading.Event()
        stop.set()
        result = self.run_fixture(stop=stop)
        self.assertEqual(self.port.claims, {})
        self.assertEqual(result['reason'], 'stop_requested')

    def test_stop_during_host_work_prevents_due_renewal(self):
        clock=ManualClock(); stop=threading.Event()
        port,backend=NativePortFixture(('tt-a',)),SyntheticBackend()
        def checking(slot):
            clock.advance(61); stop.set(); slot.cancel.wait(2)
            return dict(outcome='ok')
        backend.revalidate=checking
        result=self.run_fixture(port=port,backend=backend,clock=clock,stop=stop)
        self.assertEqual(result['reason'],'stop_requested')
        self.assertEqual(sum(e[0]=='heartbeat' for e in port.effects),0)

    def test_shared_domain_serializes_at_retained_candidate(self):
        policy = self.policy()
        policy['ownership']['tt-b']['domains'] = ['tt-a']
        policy['ownership']['tt-c']['domains'] = ['tt-a']
        result = self.run_fixture(policy=policy)
        self.assertEqual(len(result['tasks']), 1)
        self.assertEqual(len(self.backend.calls), 8)

    def test_serial_lane_renews_claim_during_long_role(self):
        clock = ManualClock()
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        renewed = threading.Event()
        original = port.heartbeat
        def heartbeat(bead, actor):
            result = original(bead, actor)
            renewed.set()
            return result
        port.heartbeat = heartbeat
        def long_role(slot, call, cancel):
            if call['phase'] == 'spec_design':
                clock.advance(61)
                if not renewed.wait(2):
                    raise AssertionError('renewal did not run while role was active')
        backend.hook = long_role
        result = self.run_fixture(port=port, backend=backend, clock=clock)
        self.assertEqual(result['outcome'], 'ok')
        self.assertEqual(sum(e[0] == 'heartbeat' for e in port.effects), 1)

    def test_unknown_heartbeat_cancels_without_retry_or_reassignment(self):
        clock = ManualClock()
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        port.heartbeat_outcome = 'unknown'
        saw_cancel = threading.Event()
        def waiting(slot, call, cancel):
            clock.advance(61)
            if cancel.wait(2):
                saw_cancel.set()
        backend.hook = waiting
        result = self.run_fixture(port=port, backend=backend, clock=clock)
        self.assertEqual(result['reason'], 'heartbeat_unknown')
        self.assertTrue(saw_cancel.is_set())
        self.assertEqual(sum(e[0] == 'heartbeat' for e in port.effects), 1)
        self.assertEqual(len(port.claims), 1)
        self.assertTrue(result['cleanup_confirmed'])

    def test_expiry_cleanup_reservation_refuses_renewal_before_expiry(self):
        clock = ManualClock()
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        def waiting(slot, call, cancel):
            clock.advance(236)
            cancel.wait(2)
        backend.hook = waiting
        result = self.run_fixture(port=port, backend=backend, clock=clock)
        self.assertEqual(result['reason'], 'lease_safety_deadline')
        self.assertEqual(sum(e[0] == 'heartbeat' for e in port.effects), 0)

    def test_bad_process_eof_is_not_reported_as_confirmed_cleanup(self):
        backend = SyntheticBackend()
        execute = backend.execute
        def incomplete(slot, call, cancel):
            result = execute(slot, call, cancel)
            result['process']['eof_confirmed'] = False
            return result
        backend.execute = incomplete
        result = self.run_fixture(port=NativePortFixture(('tt-a',)), backend=backend)
        self.assertEqual(result['outcome'], 'unknown')
        self.assertFalse(result['cleanup_confirmed'])

    def test_unknown_role_with_unknown_cleanup_retains_project_fence(self):
        backend = SyntheticBackend()
        backend.execute = lambda *a: dict(outcome='unknown', process=dict(cleanup_confirmed=False, eof_confirmed=False))
        result = self.run_fixture(port=NativePortFixture(('tt-a',)), backend=backend)
        self.assertEqual(result['outcome'], 'unknown')
        self.assertFalse(result['cleanup_confirmed'])

    def test_one_role_per_task_and_two_independent_roles_really_overlap(self):
        backend = SyntheticBackend()
        barrier = threading.Barrier(2)
        def overlap(slot, call, cancel):
            if call['phase'] == 'spec_design':
                barrier.wait(2)
        backend.hook = overlap
        result = self.run_fixture(backend=backend)
        self.assertEqual(result['outcome'], 'ok')
        self.assertEqual(backend.maximum, 2)

    def test_known_claim_refusal_is_not_retried_while_peer_runs(self):
        port, backend = NativePortFixture(('tt-a', 'tt-b')), SyntheticBackend()
        original = port.claim
        def refuse(bead, actor, admission):
            if bead == 'tt-a':
                port.effects.append(('claim', bead, actor))
                return dict(outcome='refused', reason='foreign_claim')
            return original(bead, actor, admission)
        port.claim = refuse
        self.run_fixture(port=port, backend=backend)
        self.assertEqual(sum(e[:2] == ('claim', 'tt-a') for e in port.effects), 1)

    def test_synthetic_fixture_summary_cannot_be_product_acceptance(self):
        result = self.run_fixture()
        self.assertEqual(result['kind'], 'beads.stages.synthetic_observation')
        self.assertFalse(result['production_acceptance'])

    def test_role_completion_after_attempt_deadline_cannot_advance(self):
        backend = SyntheticBackend()
        backend.hook = lambda slot, call, cancel: setattr(slot, 'launched', slot.launched-1800)
        result = self.run_fixture(port=NativePortFixture(('tt-a',)), backend=backend)
        self.assertEqual(result['reason'], 'role_attempt_deadline')
        self.assertEqual(len(backend.calls), 1)

    def test_eight_hour_foreground_budget_prevents_new_claims(self):
        clock = ManualClock()
        port, backend = NativePortFixture(), SyntheticBackend()
        controller = stages._Coordinator(self.policy(), port, backend, threading.Event(), clock)
        clock.advance(8*60*60-5)
        result = controller.run()
        self.assertEqual(result['reason'], 'stop_requested')
        self.assertEqual(port.claims, {})

    def test_session_reserves_full_native_budget_and_cleanup_before_effects(self):
        clock=ManualClock();port=NativePortFixture();backend=SyntheticBackend()
        controller=stages._Coordinator(self.policy(),port,backend,threading.Event(),clock)
        clock.advance(8*60*60-20)
        result=controller.run()
        self.assertEqual(result['reason'],'stop_requested')
        self.assertEqual(port.effects,[])

    def test_known_timed_out_role_with_proven_absence_does_not_stop_independent_peer(self):
        backend=SyntheticBackend();execute=backend.execute
        def timeout(slot,call,cancel):
            if slot.bead=='tt-a':
                return dict(outcome='unknown',process=dict(status='timeout',cleanup_confirmed=True,eof_confirmed=True))
            return execute(slot,call,cancel)
        backend.execute=timeout
        result=self.run_fixture(backend=backend)
        self.assertEqual([s['state'] for s in result['tasks']],['needs_input','candidate_for_integration'])

    def test_native_operation_deadline_prevents_claim_effect(self):
        clock = ManualClock()
        port = NativePortFixture()
        ready = port.ready
        def late():
            value = ready()
            clock.advance(31)
            return value
        port.ready = late
        result = self.run_fixture(port=port, clock=clock)
        self.assertEqual(result['reason'], 'native_operation_deadline')
        self.assertEqual(port.claims, {})

    def test_source_revalidation_does_not_starve_native_renewal_lane(self):
        clock = ManualClock()
        port, backend = NativePortFixture(('tt-a',)), SyntheticBackend()
        renewed = threading.Event()
        original = port.heartbeat
        def heartbeat(bead, actor):
            result = original(bead, actor)
            renewed.set()
            return result
        port.heartbeat = heartbeat
        first = [True]
        def revalidate(slot):
            if first[0]:
                first[0] = False
                clock.advance(61)
                if not renewed.wait(2):
                    return dict(outcome='refused')
            return dict(outcome='ok')
        backend.revalidate = revalidate
        result = self.run_fixture(port=port, backend=backend, clock=clock)
        self.assertEqual(result['outcome'], 'ok')
        self.assertTrue(renewed.is_set())

    def test_test_repair_returns_to_dev_and_invalidates_downstream_acceptance(self):
        backend = SyntheticBackend()
        backend.results[('tt-a', 'test_review')] = 'reject'
        result = self.run_fixture(port=NativePortFixture(('tt-a',)), backend=backend)
        self.assertEqual(result['tasks'][0]['state'], 'needs_input')
        phases = [c['phase'] for _, c in backend.calls]
        self.assertEqual(phases[8:], ['development', 'development_review', 'test', 'test_review'])
        self.assertEqual(self.controller.slots[0].earliest_affected_stage, 'development')


class ManualClock:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def advance(self, seconds):
        with self.lock:
            self.value += seconds


class LocalSourceTests(unittest.TestCase):
    """Actual disposable local Git/files; no qualified model/native Beads claims."""
    def setUp(self):
        from task_tower import beads_stage_roles as roles
        self.roles = roles
        self.temp = tempfile.TemporaryDirectory(prefix='tower-stage-src-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/'original'
        self.source.mkdir()
        (self.source/'docs').mkdir()
        (self.source/'docs'/'a.md').write_bytes(b'# Original\n')
        (self.source/'code.py').write_bytes(b'value = 1\n')
        roles._git(self.source, 'init', '--initial-branch=main')
        roles._git(self.source, 'add', '--all')
        roles._git(self.source, '-c', 'user.name=Synthetic Fixture', '-c', 'user.email=fixture@invalid',
                   'commit', '--no-gpg-sign', '-m', 'fixture base')
        self.base = roles._git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.before = roles.snapshot_source(self.source, self.base)
        self.worktrees, self.evidence = self.root/'worktrees', self.root/'evidence'
        self.worktrees.mkdir()
        self.evidence.mkdir()
        self.authority = roles.RoleAuthority(approvals={}, qualifications={}, containment_verifier=lambda *a: None)
        # Method-level synthetic fixture, not valid preflight/profile authority.
        self.runner = object.__new__(stages.StageRoleRunner)
        self.runner.authority = self.authority
        self.runner.policy = dict(worktree_root=str(self.worktrees), evidence_root=str(self.evidence))
        self.runner.project = dict(source=str(self.source), expected_head=self.base)
        self.runner._profile_current = lambda *a,**k: None
        self.runner.host_checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda *a: None, qualification_verifier=lambda *a: True)
        self.slot = stages._Slot('tt-doc', 'fixture-owner',
            dict(base=dict(head=self.base, tree=self.before['tree']), policy_digest='a'*64),
            dict(paths=['docs/a.md'], domains=['documentation']), {}, '', uuid.uuid4().hex, 0, 270)
        self.slot.context = self.runner.prepare(self.slot)

    def test_prepare_creates_isolated_host_branch_and_preserves_original(self):
        context = self.slot.context
        self.assertNotEqual(context['source'], self.source)
        branch = self.roles._git(context['source'], 'branch', '--show-current').decode().strip()
        self.assertTrue(branch.startswith('tower-stage/'))
        self.assertEqual(context['snapshot']['head'], self.base)
        self.assertEqual((self.source/'docs'/'a.md').read_bytes(), b'# Original\n')

    def test_check_factory_receives_exact_task_cancel_event(self):
        cancel=threading.Event();seen=[]
        checks=stages.HostCheckAuthority(documentation_tasks={'tt-doc'},qualification_verifier=lambda *a:True,
            sandbox_factory=lambda *args:seen.append(args[-1]))
        with self.assertRaises(ValueError):checks.run(self.slot,dict(instance_id=uuid.uuid4().hex),cancel)
        self.assertEqual(seen,[cancel])

    def test_owned_dev_progress_advances_at_new_checkpoint(self):
        context = self.slot.context
        (context['source']/'docs'/'a.md').write_bytes(b'# Changed\n')
        observed = self.roles.snapshot_source(context['source'], self.base)
        checkpoint = self.runner._checkpoint(self.slot, dict(source=observed))
        self.assertNotEqual(checkpoint['head'], self.base)
        self.assertEqual(checkpoint['base'], self.base)
        self.assertEqual(self.roles._git(context['source'], 'diff', '--name-only', self.base, '--'), b'docs/a.md\n')
        self.assertEqual(self.roles.verify_stage_source(context['source'], checkpoint,
            role='spec_acceptor', owned_paths=['docs/a.md'])['outcome'], 'ok')
        self.assertEqual((self.source/'docs'/'a.md').read_bytes(), b'# Original\n')

    def test_artifact_only_qualification_retains_exact_initial_source_without_empty_commit(self):
        before = copy.deepcopy(self.slot.context['snapshot'])
        checkpoint = self.runner._checkpoint(self.slot, dict(source=before))
        self.assertEqual(checkpoint, before)
        self.assertEqual(self.roles._git(self.slot.context['source'], 'rev-parse', 'HEAD').decode().strip(), self.base)

    def test_unowned_source_delta_refuses_host_checkpoint(self):
        context = self.slot.context
        (context['source']/'code.py').write_bytes(b'value = 2\n')
        observed = self.roles.snapshot_source(context['source'], self.base)
        with self.assertRaises(ValueError):
            self.runner._checkpoint(self.slot, dict(source=observed))
        self.assertEqual(self.roles._git(context['source'], 'rev-parse', 'HEAD').decode().strip(), self.base)

    def test_manifest_reference_pins_complete_actual_file_and_live_authority(self):
        ref = self.runner._manifest(self.slot, dict(instance_id=uuid.uuid4().hex))
        entry = self.authority.get_source_input(ref['name'])
        self.assertEqual(hashlib.sha256(entry.path.read_bytes()).hexdigest(), ref['sha256'])
        self.assertEqual(json.loads(entry.path.read_bytes()), self.slot.context['snapshot'])
        self.assertNotEqual(ref['sha256'], self.slot.context['snapshot']['manifest_sha256'])
        self.assertFalse(entry.path.is_relative_to(self.slot.context['source']))
        self.assertFalse(entry.path.is_relative_to(self.slot.context['evidence']))

    def test_frozen_review_input_is_independent_and_does_not_accept_stage(self):
        output = self.slot.context['outputs']/'synthetic-call'
        output.mkdir()
        (output/'design.md').write_bytes(b'proposed design')
        digest = hashlib.sha256(b'proposed design').hexdigest()
        refs = self.runner._freeze(self.slot, dict(output=output,
            result=dict(result=dict(artifacts=[dict(name='design.md', sha256=digest)]))))
        entry = self.authority.get_accepted_artifact('design.md')
        self.assertEqual(refs, [dict(name='design.md', sha256=digest)])
        self.assertEqual(entry.path.read_bytes(), b'proposed design')
        (output/'design.md').write_bytes(b'mutated model output')
        self.assertEqual(entry.path.read_bytes(), b'proposed design')
        self.assertEqual(self.slot.accepted, [])

    def test_exact_private_rejection_feedback_survives_invalidation_into_next_request(self):
        call=dict(phase='spec_design_review',role='spec_acceptor',stage='spec',instance_id=uuid.uuid4().hex)
        rejected=dict(findings=['PRIVATE_CORRECTION_SENTINEL'],reviewed=[dict(name='proposal.md',sha256='a'*64)])
        ref=self.runner._feedback(self.slot,call,rejected,self.slot.context['snapshot'])
        self.runner.invalidate(self.slot,'spec')
        self.assertIn(ref,self.slot.context['review_inputs'])
        entry=self.authority.get_accepted_artifact(ref['name'])
        value=json.loads(entry.path.read_bytes())
        self.assertEqual(value['findings'],['PRIVATE_CORRECTION_SENTINEL'])
        self.assertEqual(value['rejected_artifacts'],rejected['reviewed'])
        self.assertEqual(value['affected_stage'],'spec')
        self.assertEqual(value['source']['manifest_sha256'],self.slot.context['snapshot']['manifest_sha256'])
        self.runner.project.update(repository='Sibiya666/task-tower',id='fixture')
        self.runner.profile=dict(superpowers=[]);self.runner.mode='production'
        self.slot.inputs=dict.fromkeys(('title','description','design','acceptance_criteria','notes'),'')
        self.slot.input_digest=self.roles._digest(self.slot.inputs)
        correcting=dict(phase='spec_design',role='spec_author',stage='spec',instance_id=uuid.uuid4().hex,
            attempt_id=uuid.uuid4().hex,actor='fresh-corrector',session_id='session',run_id=self.slot.run_id)
        requests=[]
        with patch.object(self.roles,'run_role',side_effect=lambda profile,request,**kw:requests.append(request) or dict(outcome='synthetic')):
            self.runner.execute(self.slot,correcting,threading.Event())
        self.assertIn(ref,requests[0]['binding']['accepted_artifacts'])
        self.assertNotIn('PRIVATE_CORRECTION_SENTINEL',json.dumps(requests[0]))

    def test_documentation_capability_refuses_code_delta(self):
        changed = copy.deepcopy(self.before)
        next(f for f in changed['files'] if f['name'] == 'code.py')['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            stages.HostCheckAuthority.check_documentation_delta(self.before, changed)

    def test_unknown_preparation_git_proof_keeps_actual_project_mutex_held(self):
        from tests.test_beads_admission import facts
        profile=self.root/'synthetic-profile.json';profile.write_text('{}',encoding='utf-8')
        database=self.root/'synthetic-database';(database/'.beads').mkdir(parents=True)
        (database/'.beads'/'metadata.json').write_text('{"backend":"dolt","dolt_mode":"embedded"}',encoding='utf-8')
        project=dict(id='fixture',repository='Sibiya666/task-tower',directory=str(database),source=str(self.source),
                     expected_head=self.base,allowed_beads=['tt-doc'])
        config=self.root/'synthetic-admission.json';config.write_text(json.dumps(dict(version=1,
            executable=str(Path(sys.executable).resolve()),projects=[project])),encoding='utf-8')
        policy=self.root/'synthetic-policy.json';policy.write_text(json.dumps(dict(schema=1,admission_config=str(config),
            project='fixture',role_profile=str(profile),evidence_root=str(self.evidence),worktree_root=str(self.worktrees),
            ownership={'tt-doc':dict(paths=['docs/a.md'],domains=['documentation'])})),encoding='utf-8')
        self.runner.profile_path=profile
        port=NativePortFixture(('tt-doc',));claim=port.claim
        def exact_claim(bead,actor,packet):
            value=claim(bead,actor,packet);value['pins']['base']=dict(head=self.base,tree=self.before['tree']);return value
        port.claim=exact_claim
        count=len(stages._FENCED_GUARDS)
        try:
            with patch.object(stages,'BeadsStagePort',return_value=port),patch.object(self.roles,'run_command',
                return_value=facts(status='unknown',started=True,cleanup_confirmed=False,stdout_tail_unknown=True)):
                result=self.runner.run_session(policy,stop_requested=threading.Event())
            self.assertEqual(result['outcome'],'unknown')
            self.assertFalse(result['cleanup_confirmed'])
            self.assertEqual(len(stages._FENCED_GUARDS),count+1)
            identity=project['repository']+'\0fixture\0'+str(database.resolve())
            with self.assertRaises(ValueError):stages.ProjectGuard(identity).acquire()
        finally:
            # Only this fixture's simulated unknown call ran; no live child was
            # launched. Test cleanup owns this newly created actual guard.
            if len(stages._FENCED_GUARDS)>count:
                stages._FENCED_GUARDS.pop().release()

    def test_frozen_host_event_is_canonical_private_and_rehashed_before_native_append(self):
        self.slot.session_id='synthetic-session'
        port=NativePortFixture(('tt-doc',));controller=stages._Coordinator({},port,self.runner,threading.Event(),time.monotonic)
        body=dict(kind='host_start',private_sentinel='PRIVATE_EVENT_PROSE')
        for mutation in ('missing','changed','oversized','unsafe','hardlink'):
            with self.subTest(mutation=mutation):
                record=self.runner.persist_host_event(self.slot,'claimed',body)
                envelope=json.loads(record.path.read_bytes())
                self.assertEqual(envelope['session_id'],'synthetic-session')
                self.assertEqual(envelope['actor'],self.slot.actor)
                self.assertEqual(hashlib.sha256(record.path.read_bytes()).hexdigest(),record.sha256)
                self.assertFalse(record.path.is_relative_to(self.slot.context['source']))
                self.assertFalse(record.path.is_relative_to(self.slot.context['inputs']))
                if mutation=='unsafe':record=stages.FrozenHostEvent(record.reference,record.sha256,self.root/'outside.json')
                else:
                    record.path.chmod(0o644)
                    if mutation=='missing':record.path.unlink()
                    elif mutation=='changed':record.path.write_bytes(b'changed')
                    elif mutation=='oversized':record.path.write_bytes(b'x'*65537)
                    elif mutation=='hardlink':os.link(record.path,self.root/('linked-'+record.reference))
                with patch.object(self.runner,'persist_host_event',return_value=record):
                    with self.assertRaises(ValueError):controller._event(self.slot,'claimed',body)
                self.assertEqual(port.effects,[])

    def test_unknown_native_append_preserves_frozen_host_event_and_never_retries(self):
        self.slot.session_id='synthetic-session'
        port=NativePortFixture(('tt-doc',));port.claims['tt-doc']=self.slot.actor
        attempted=[]
        def unknown(*args):attempted.append(args);return dict(outcome='unknown',reason='synthetic_write_unknown')
        port.append_event=unknown
        controller=stages._Coordinator({},port,self.runner,threading.Event(),time.monotonic)
        with self.assertRaises(stages._Halt):controller._event(self.slot,'claimed',dict(kind='host_start'))
        files=list(self.slot.event_root.glob('*.json'))
        self.assertEqual(len(files),1);self.assertEqual(len(attempted),1)
        self.assertEqual(port.claims['tt-doc'],self.slot.actor)
        self.assertEqual(hashlib.sha256(files[0].read_bytes()).hexdigest(),attempted[0][2]['digest'])

    def test_documentation_check_has_actual_supervised_receipt_at_exact_checkpoint(self):
        context = self.slot.context
        (context['source']/'docs'/'a.md').write_bytes(b'# Checked\n')
        current = self.roles.snapshot_source(context['source'], self.base)
        self.runner._checkpoint(self.slot, dict(source=current))
        snapshot = context['snapshot']
        sandbox, evidence = self.root/'check-source', self.root/'check-evidence'
        evidence.mkdir()
        self.roles._git(context['source'], 'worktree', 'add', '--detach', str(sandbox), snapshot['head'])
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda *a: stages.HostCheckSandbox(sandbox, evidence, snapshot['manifest_sha256']),
            qualification_verifier=lambda *a: True)  # Synthetic grant, actual command facts only.
        result = checks.run(self.slot, dict(instance_id=uuid.uuid4().hex), threading.Event())
        self.assertEqual(result['kind'], 'documentation.validation')
        self.assertEqual(result['runtime_tests'], 'not_run')
        self.assertEqual(result['source_manifest_sha256'], snapshot['manifest_sha256'])
        self.assertEqual(result['process']['exit_code'], 0)
        self.assertTrue(result['process']['eof_confirmed'])
        self.assertTrue(result['process']['cleanup_confirmed'])

    def test_valid_artifact_check_cannot_hide_failing_source_diff_check(self):
        context = self.slot.context
        (context['source']/'docs'/'a.md').write_bytes(b'# Bad trailing whitespace \n')
        current = self.roles.snapshot_source(context['source'], self.base)
        self.runner._checkpoint(self.slot, dict(source=current))
        output = context['outputs']/'synthetic-output'
        output.mkdir()
        (output/'valid.md').write_bytes(b'# Valid artifact\n')
        sha = hashlib.sha256(b'# Valid artifact\n').hexdigest()
        context['review_inputs'] = self.runner._freeze(self.slot, dict(output=output,
            result=dict(result=dict(artifacts=[dict(name='valid.md', sha256=sha)]))))
        snapshot = context['snapshot']
        sandbox, evidence = self.root/'whitespace-source', self.root/'whitespace-evidence'
        evidence.mkdir()
        self.roles._git(context['source'], 'worktree', 'add', '--detach', str(sandbox), snapshot['head'])
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'},
            sandbox_factory=lambda source, observed, instance, artifacts, cancel: stages.HostCheckSandbox(
                sandbox, evidence, snapshot['manifest_sha256'], artifacts),
            qualification_verifier=lambda *a: True)
        with self.assertRaises(ValueError):
            checks.run(self.slot, dict(instance_id=uuid.uuid4().hex), threading.Event())

    def test_production_mode_nonempty_dev_checkpoint_is_bound_to_actual_fresh_reviewer(self):
        self._actual_pipeline(runtime=False)

    def test_runtime_nine_fresh_roles_actual_new_test_red_then_implementation_green(self):
        self._actual_pipeline(runtime=True)

    def test_runtime_full_test_zero_discovered_tests_cannot_be_candidate(self):
        self._actual_pipeline(runtime=True,zero_full_test=True)

    def test_actual_full_test_zero_inventory_is_refused_despite_exit_zero(self):
        with self.assertRaises(ValueError):
            self._direct_runtime_check('import unittest,atexit,os\n'
                'atexit.register(lambda:os._exit(0))\ndef load_tests(loader,suite,pattern):\n return unittest.TestSuite()\n','test')
        self.assertEqual(len(self.direct_receipts),1)
        self.assertEqual(self.direct_receipts[0]['exit_code'],0)
        self.assertEqual(self.direct_receipts[0]['status'],'passed')

    def test_genuine_red_with_footer_beyond_context_prefix_is_accepted(self):
        result=self._direct_runtime_check('import unittest,sys\nclass Loud(unittest.TestCase):\n'
            ' def test_missing(self):\n  print("X"*12000,file=sys.stderr)\n  self.assertEqual(1,2)\n','tests_only')
        self.assertEqual(result['coverage']['tests_run'],1)
        self.assertEqual(result['coverage']['failures'],1)
        self.assertIn('AssertionError',result['failure_context']['stderr'])
        record=self.authority.get_accepted_artifact(result['runner_report']['name'])
        actual=json.loads(record.path.read_bytes())
        self.assertGreater(actual['host_supervisor']['streams']['stderr']['bytes'],8192)
        self.assertEqual(actual['context']['kind'],'captured_prefix_and_suffix')
        self.assertLess(len(result['failure_context']['stderr'].encode('utf-8')),8300)

    def _direct_runtime_check(self,test_source,phase):
        roles=self.roles;context=self.slot.context;source=context['source']
        (source/'tests').mkdir();(source/'tests'/'__init__.py').write_bytes(b'')
        (source/'tests'/'test_boundary.py').write_text(test_source,encoding='utf-8')
        roles._git(source,'add','--all');roles._git(source,'-c','user.name=Fixture','-c','user.email=fixture@invalid',
            'commit','--no-gpg-sign','-m','runtime boundary fixture')
        context['snapshot']=roles.snapshot_source(source,self.base)
        self.slot.owned=dict(paths=['code.py','tests'],domains=['runtime'])
        receipts=[];self.direct_receipts=receipts;grants=[]
        from task_tower.processes import run_command
        def launch(argv,source,evidence,cancel,env,timeout):
            receipt=run_command(argv,source,timeout,env=env,cancel_requested=lambda:threading.Event.is_set(cancel),
                capture=dict(directory=evidence,max_bytes_per_stream=8388608));receipts.append(receipt);return receipt
        execution=stages.RuntimeExecutionCapability(launcher=launch,qualification_verifier=lambda *a:True)
        def sandbox(source,snapshot,instance,artifacts,capability,reporter,cancel):
            target,capture=self.root/'zero-check-source',self.root/'zero-check-capture';capture.mkdir()
            roles._git(source,'worktree','add','--detach',str(target),snapshot['head'],cancel_requested=cancel)
            if reporter is None:grant=stages.RuntimeCheckSandbox(target,capture,snapshot['manifest_sha256'],capability,artifacts)
            else:
                output=self.root/'zero-check-output';output.mkdir()
                grant=stages.RuntimeCheckSandbox(target,capture,snapshot['manifest_sha256'],capability,artifacts,
                    reporter,output/'runner-observations.json')
            grants.append(grant);return grant
        checks=stages.RuntimeCheckAuthority(test_paths={'tt-doc':('tests',)},selected_tests={'tt-doc':('tests.test_boundary',)},
            execution=execution,sandbox_factory=sandbox,qualification_verifier=lambda *a:True)
        with roles.attempt_budget(time.monotonic()+120):
            return checks.run(self.slot,dict(phase=phase,instance_id=uuid.uuid4().hex),threading.Event())

    def test_runtime_implementation_test_write_breaches_phase_scope_and_revokes_live_bundle(self):
        self._actual_pipeline(runtime=True,mutate_tests=True)

    def _actual_pipeline(self,runtime=False,mutate_tests=False,zero_full_test=False):
        """Synthetic role program/containment/port; actual Git and OS processes."""
        roles = self.roles
        instruction = self.root/'synthetic-instructions.md'
        instruction.write_bytes(b'Explicitly synthetic test instructions; no model qualification.\n')
        program = (
            'import hashlib,json,sys\nfrom pathlib import Path\n'
            'request=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))\n'
            'result=dict(schema=1,kind="beads.role.result",binding=request["binding"],artifacts=[],findings=[])\n'
            'for name in request["output_names"]:\n'
            ' p=Path(sys.argv[3])/name\n p.write_bytes(b"# Synthetic role document\\n")\n'
            ' result["artifacts"].append(dict(name=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))\n'
            'if request["role"]=="dev_implementer":\n'
            ' (Path.cwd()/"docs"/"a.md").write_bytes(b"# Actual owned DEV change\\n")\n'
            'if request["role"].endswith("_acceptor"):\n'
            ' result.update(verdict="approve",reviewed=request["binding"]["accepted_artifacts"])\n'
            'Path(sys.argv[2]).write_text(json.dumps(result),encoding="utf-8")\n')
        if runtime:
            test_source=('import unittest\nimport importlib.util\nfrom pathlib import Path\n'
                'spec=importlib.util.spec_from_file_location("owned_product",Path(__file__).resolve().parents[1]/"code.py")\n'
                'product=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(product)\n'
                'class Behavior(unittest.TestCase):\n def test_new_behavior(self):\n  self.assertEqual(product.value,42)\n')
            if zero_full_test:
                test_source+='def load_tests(loader,suite,pattern):\n if pattern:\n  import atexit,os\n  atexit.register(lambda:os._exit(0))\n  return unittest.TestSuite()\n return suite\n'
            program=program.replace('if request["role"]=="dev_implementer":\n'
                ' (Path.cwd()/"docs"/"a.md").write_bytes(b"# Actual owned DEV change\\n")\n',
                'inputs=Path.cwd().parent/Path.cwd().name.replace("source-","inputs-")\n'
                'name=next(a["name"] for a in reversed(request["binding"]["accepted_artifacts"]) if a["name"].startswith("phase-"))\n'
                'phase=json.loads((inputs/name).read_text(encoding="utf-8"))["phase"]\n'
                'if phase=="tests_only":\n'
                ' (Path.cwd()/"tests").mkdir(exist_ok=True)\n'
                ' (Path.cwd()/"tests"/"__init__.py").write_bytes(b"")\n'
                ' (Path.cwd()/"tests"/"test_behavior.py").write_text('+repr(test_source)+',encoding="utf-8")\n'
                'if phase=="development":\n (Path.cwd()/"code.py").write_bytes(b"value = 42\\n")\n')
            if mutate_tests:
                program=program.replace('if phase=="development":\n (Path.cwd()/"code.py").write_bytes(b"value = 42\\n")\n',
                    'if phase=="development":\n (Path.cwd()/"code.py").write_bytes(b"value = 42\\n")\n'
                    ' p=Path.cwd()/"tests"/"test_behavior.py"\n p.write_bytes(p.read_bytes()+b"# Unauthorized test edit\\n")\n')
        profile = dict(schema=1, executable=str(Path(sys.executable).resolve()),
            executable_sha256=roles._hash_file(Path(sys.executable).resolve()), request_schema=1, result_schema=1,
            superpowers=[dict(path=str(instruction), sha256=roles._hash_file(instruction))],
            variants={name: dict(argv=['-I', '-B', '-c', program, '{request}', '{result}', '{output}'],
                containment_contract='synthetic-not-qualified', prerequisite_sha256='1'*64) for name in roles.VARIANTS},
            roles={role: dict(variant=value[0], write_contract=value[1]) for role, value in roles.ROLE_MAP.items()},
            qualification_approval_reference='synthetic', production_qualification_sha256='2'*64)
        holder = {}
        def synthetic_grant(p, request, source, output, evidence):
            authority = holder['authority']
            scope=authority.get_phase_scope(request['binding']['instance_id'])
            return roles.ContainmentGrant(roles.bundle_digest(p), '1'*64, source, output, evidence,
                request['role'], scope.owned_paths, authority.get_source_input(request['source_manifest']['name']),
                tuple(authority.get_accepted_artifact(a['name']) for a in request['binding']['accepted_artifacts']))
        authority = roles.RoleAuthority(approvals={}, qualifications={'2'*64: roles.bundle_digest(profile)},
                                        containment_verifier=synthetic_grant)
        holder['authority'] = authority
        profile_path = self.root/'synthetic-profile.json'
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        def check_sandbox(source, snapshot, instance, artifacts, cancel):
            sandbox, evidence = self.root/('check-'+instance), self.root/('capture-'+instance)
            evidence.mkdir()
            roles._git(source, 'worktree', 'add', '--detach', str(sandbox), snapshot['head'],cancel_requested=cancel)
            return stages.HostCheckSandbox(sandbox, evidence, snapshot['manifest_sha256'], artifacts)
        checks = stages.HostCheckAuthority(documentation_tasks={'tt-doc'}, sandbox_factory=check_sandbox,
                                           qualification_verifier=lambda *a: True)
        if runtime:
            from task_tower.processes import run_command
            execution=stages.RuntimeExecutionCapability(qualification_verifier=lambda *a:True,
                launcher=lambda argv,source,evidence,cancel,env,timeout:run_command(argv,source,timeout,env=env,
                    cancel_requested=lambda:threading.Event.is_set(cancel),
                    capture=dict(directory=evidence,max_bytes_per_stream=8388608)))
            def runtime_sandbox(source,snapshot,instance,artifacts,capability,reporter,cancel):
                sandbox,evidence=self.root/('runtime-source-'+instance),self.root/('runtime-evidence-'+instance)
                output=self.root/('runtime-output-'+instance)
                evidence.mkdir();output.mkdir()
                roles._git(source,'worktree','add','--detach',str(sandbox),snapshot['head'],cancel_requested=cancel)
                return stages.RuntimeCheckSandbox(sandbox,evidence,snapshot['manifest_sha256'],capability,artifacts,
                    reporter,output/'runner-observations.json')
            checks=stages.RuntimeCheckAuthority(test_paths={'tt-doc':('tests',)},selected_tests={'tt-doc':('tests.test_behavior',)},
                execution=execution,sandbox_factory=runtime_sandbox,qualification_verifier=lambda *a:True)
        runner = stages.StageRoleRunner(profile_path, authority, mode='production', host_checks=checks)
        database = self.root/'synthetic-project'
        (database/'.beads').mkdir(parents=True)
        (database/'.beads'/'metadata.json').write_text('{"backend":"dolt","dolt_mode":"embedded"}', encoding='utf-8')
        config = self.root/'synthetic-admission.json'
        project = dict(id='fixture', repository='Sibiya666/task-tower', directory=str(database),
                       source=str(self.source), expected_head=self.base, allowed_beads=['tt-doc'])
        config.write_text(json.dumps(dict(version=1, executable=str(Path(sys.executable).resolve()),
                                         projects=[project])), encoding='utf-8')
        policy_path = self.root/'synthetic-policy.json'
        policy_path.write_text(json.dumps(dict(schema=1, admission_config=str(config), project='fixture',
            role_profile=str(profile_path), evidence_root=str(self.evidence), worktree_root=str(self.worktrees),
            ownership={'tt-doc': dict(paths=['code.py','tests'] if runtime else ['docs/a.md'], domains=['runtime' if runtime else 'documentation'])})), encoding='utf-8')
        runner.policy, runner.project = stages.load_stage_policy(policy_path), project
        self.assertEqual(checks.preflight(runner.policy)['outcome'],'ok')
        port = NativePortFixture(('tt-doc',))
        claim = port.claim
        def exact_claim(bead, actor, packet):
            result = claim(bead, actor, packet)
            result['pins']['base'] = dict(head=self.base, tree=self.before['tree'])
            return result
        port.claim = exact_claim
        controller = stages._Coordinator(runner.policy, port, runner, threading.Event(), time.monotonic)
        result = controller.run()
        if zero_full_test:
            self.assertNotEqual(result['outcome'],'ok',result)
            self.assertNotEqual(result['tasks'][0]['state'],'candidate_for_integration')
            return
        if mutate_tests:
            self.assertEqual(result['outcome'],'unknown',result)
            self.assertEqual(result['tasks'][0]['state'],'fenced')
            self.assertFalse(result['production_acceptance'])
            self.assertEqual(len(controller.slots[0].provenance),5)
            with self.assertRaises(ValueError): authority._check(profile,'production')
            return
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertEqual(result['tasks'][0]['state'], 'candidate_for_integration')
        self.assertFalse(result['production_acceptance'])
        slot = controller.slots[0]
        self.assertEqual(len(slot.provenance), 9 if runtime else 8)
        self.assertEqual(len({r['call']['instance_id'] for r in slot.provenance}), 9 if runtime else 8)
        self.assertNotEqual(slot.context['snapshot']['head'], self.base)
        development_review = next(a for a in slot.accepted if a['phase'] == 'development_review')
        self.assertEqual(development_review['source'], slot.context['snapshot'])
        if runtime:
            self.assertEqual((slot.context['source']/'code.py').read_bytes(),b'value = 42\n')
            red,green,test=slot.context['checks']
            self.assertEqual([red['process']['exit_code'],green['process']['exit_code'],test['process']['exit_code']],[1,0,0])
            self.assertEqual(red['selection'],green['selection'])
            self.assertEqual(red['test_pins'],green['test_pins'])
            self.assertIn('AssertionError',red['failure_context']['stderr'])
            self.assertEqual(test['selection'],['discover','-s','tests','-v'])
            self.assertNotEqual(red['source_manifest_sha256'],green['source_manifest_sha256'])
            for checked in (red,green,test):
                report=authority.get_accepted_artifact(checked['runner_report']['name'])
                actual=json.loads(report.path.read_bytes())
                self.assertEqual(report.sha256,checked['runner_report']['sha256'])
                self.assertGreater(actual['runner_observations']['tests_run'],0)
                self.assertEqual(actual['source_manifest_sha256'],checked['source_manifest_sha256'])
                self.assertIn('streams',actual['host_supervisor'])
            review_refs=slot.accepted[-1]['references']
            self.assertIn(test['runner_report'],review_refs)
        else:self.assertEqual((slot.context['source']/'docs'/'a.md').read_bytes(), b'# Actual owned DEV change\n')
        self.assertEqual((self.source/'docs'/'a.md').read_bytes(), b'# Original\n')
        self.assertTrue(all(p['evidence']['process']['cleanup_confirmed'] and
                            p['evidence']['process']['eof_confirmed'] for p in slot.provenance))
        values=[e[2] for e in port.effects if e[:2]==('event','tt-doc')]
        self.assertTrue(all(a!=b for a,b in zip(values,values[1:])))
        if runtime:
            self.assertLess(values.index('dev_tests_pending'),values.index('dev_red_observed'))
            self.assertLess(values.index('dev_red_observed'),values.index('dev_pending'))
        self.assertEqual(len({e.reference for e in slot.events}),len(slot.events))
        self.assertEqual(len(set(port.native_event_ids)),len(slot.events))
        observed_completions=set()
        for event in slot.events:
            self.assertEqual(hashlib.sha256(event.path.read_bytes()).hexdigest(),event.sha256)
            self.assertNotIn('failure_context',event.path.read_text(encoding='utf-8'))
            body=json.loads(event.path.read_bytes())['body']
            previous=body.get('previous_completion')
            if previous:
                self.assertTrue(previous['evidence']['process']['cleanup_confirmed'])
                self.assertTrue(previous['evidence']['process']['eof_confirmed'])
                observed_completions.add(previous['call']['instance_id'])
            if body.get('kind')=='host_checkpoint':
                self.assertTrue(body['evidence']['process']['cleanup_confirmed'])
                self.assertTrue(body['evidence']['process']['eof_confirmed'])
                observed_completions.add(body['call']['instance_id'])
        self.assertEqual(observed_completions,{p['call']['instance_id'] for p in slot.provenance})


@unittest.skipUnless(os.name == 'nt', 'Windows OS mutex contract')
class ProjectGuardTests(unittest.TestCase):
    def test_second_live_guard_refuses_and_handle_is_noninheritable(self):
        identity = 'synthetic-project-'+uuid.uuid4().hex
        first = stages.ProjectGuard(identity).acquire()
        try:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetHandleInformation.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            flags = wintypes.DWORD()
            self.assertTrue(kernel.GetHandleInformation(first.handle, ctypes.byref(flags)))
            self.assertEqual(flags.value & 1, 0)
            with self.assertRaises(ValueError):
                stages.ProjectGuard(identity).acquire()
            from task_tower.processes import run_command
            with tempfile.TemporaryDirectory(prefix='tower-guard-') as root:
                script = ('from task_tower.beads_stages import ProjectGuard; import sys; '
                          'ProjectGuard(sys.argv[1]).acquire()')
                receipt = run_command([sys.executable, '-c', script, identity], Path.cwd(), 10,
                    capture=dict(directory=Path(root), max_bytes_per_stream=65536))
                self.assertEqual(receipt['exit_code'], 1)
                self.assertTrue(receipt['cleanup_confirmed'])
                self.assertFalse(receipt['stdout_tail_unknown'])
                self.assertFalse(receipt['stderr_tail_unknown'])
        finally:
            first.release()
        second = stages.ProjectGuard(identity).acquire()
        second.release()

    def test_actual_owner_death_abandons_mutex_without_restoring_prior_claim(self):
        import ctypes
        from ctypes import wintypes
        from task_tower.processes import run_command
        identity = 'synthetic-death-'+uuid.uuid4().hex
        probe = stages.ProjectGuard(identity)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.OpenMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        with tempfile.TemporaryDirectory(prefix='tower-mutex-death-') as root:
            root = Path(root)
            capture = root/'capture'
            capture.mkdir()
            script = ('import os,sys,time; from pathlib import Path; '
                'from task_tower.beads_stages import ProjectGuard; '
                'g=ProjectGuard(sys.argv[1]).acquire(); p=Path(sys.argv[2]); '
                '(p/"ready").write_bytes(b"ready"); deadline=time.monotonic()+5\n'
                'while not (p/"exit").exists() and time.monotonic()<deadline: time.sleep(.01)\n'
                'os._exit(0)\n')
            facts = []
            worker = threading.Thread(target=lambda: facts.append(run_command(
                [sys.executable, '-c', script, identity, str(root)], Path.cwd(), 10,
                capture=dict(directory=capture, max_bytes_per_stream=65536))), daemon=False)
            worker.start()
            keepalive = None
            try:
                deadline = time.monotonic()+4
                while not (root/'ready').exists() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue((root/'ready').exists())
                keepalive = kernel.OpenMutexW(0x100001, False, 'Local\\TaskTowerStages-'+probe.key)
                self.assertTrue(keepalive)
                (root/'exit').write_bytes(b'exit')
                worker.join(10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(facts[0]['exit_code'], 0)
                self.assertTrue(facts[0]['cleanup_confirmed'])
                self.assertFalse(facts[0]['stdout_tail_unknown'])
                self.assertFalse(facts[0]['stderr_tail_unknown'])
                live = stages.ProjectGuard(identity).acquire()
                try:
                    self.assertTrue(live.abandoned)
                    # A new live mutex has no task/actor/claim recovery state.
                    self.assertFalse(hasattr(live, 'claims'))
                finally:
                    live.release()
            finally:
                (root/'exit').write_bytes(b'exit')
                worker.join(10)
                if keepalive:
                    kernel.CloseHandle(keepalive)


if __name__ == '__main__':
    unittest.main()
