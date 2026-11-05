"""Synthetic injected native-schema tests: never invokes Beads or private stores."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import sys
import time
import unittest
from unittest.mock import patch
from tests.test_beads_admission import facts, HEAD, TREE

CONTRACT = json.loads((Path(__file__).parent/'fixtures/beads_stages/native_contract.json').read_text(encoding='utf-8'))
OBS = {o['operation']: o.get('native_json') for e in CONTRACT['examples'] for o in e['observations']}
BEAD = 'stgq-oj9'
ACTOR = 'stage-contract-owner'

class PortTests(unittest.TestCase):
    def setUp(self):
        try:
            from task_tower import beads_stage_port as port
        except ImportError:
            self.fail("fixed stage port API is not implemented")
        self.portmod = port
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ('source/.git', 'db/.beads', 'evidence', 'worktrees'):
            (self.root/name).mkdir(parents=True)
        (self.root/'db/.beads/metadata.json').write_text('{"backend":"dolt","dolt_mode":"embedded"}')
        (self.root/'bd.exe').write_bytes(b'synthetic exe never launched')
        (self.root/'profile.json').write_text('{}')
        self.config = dict(version=1,executable=str(self.root/'bd.exe'),projects=[dict(id='fixture',repository='Sibiya666/task-tower',directory=str(self.root/'db'),source=str(self.root/'source'),expected_head=HEAD,allowed_beads=[BEAD])])
        self.policy = dict(schema=1,admission_config=str(self.root/'admission.json'),project='fixture',role_profile=str(self.root/'profile.json'),evidence_root=str(self.root/'evidence'),worktree_root=str(self.root/'worktrees'),ownership={BEAD:dict(paths=['task_tower'],domains=['port'])})
        self.write()
        self.calls=[]; self.claimed=False; self.now=0.; self.bad={}
        self.row=copy.deepcopy(OBS['show-claimed'][0])
        self.readyrow=copy.deepcopy(OBS['ready-after-prerequisite'][0])
        self.deps=copy.deepcopy(self.row['dependencies'])
        self.event=copy.deepcopy(OBS['event-record-0'])
        self.proc={}
        self.patch=patch('task_tower.beads_admission.sys.platform','win32'); self.patch.start(); self.addCleanup(self.patch.stop)
        self.utcpatch=patch.object(port.BeadsStagePort,"_utcnow",return_value=port.datetime.fromisoformat("2026-11-05T08:33:40+00:00"),create=True); self.utcnow=self.utcpatch.start(); self.addCleanup(self.utcpatch.stop)
        self.port=port.BeadsStagePort(port.load_stage_policy(self.root/'stage.json'),runner=self.runner,clock=lambda:self.now)
    def write(self):
        (self.root/'admission.json').write_text(json.dumps(self.config),encoding='utf-8')
        (self.root/'stage.json').write_text(json.dumps(self.policy),encoding='utf-8')

    def test_live_process_proof_survives_unknown_read_and_runner_exception(self):
        self.proc['beads_ready']={'cleanup_confirmed':False,'stdout_tail_unknown':True}
        self.assertEqual(self.port.ready()['outcome'],'unknown')
        proof=self.port.get_operation_proof()
        self.assertFalse(proof.complete)
        self.assertFalse(proof.processes[-1].cleanup_confirmed)
        self.assertFalse(proof.processes[-1].eof_confirmed)
        self.assertIs(proof,self.port.get_operation_proof())
        self.port._runner=lambda *a: (_ for _ in ()).throw(OSError('synthetic runner failure'))
        self.port.ready()
        later=self.port.get_operation_proof()
        self.assertGreater(later.sequence,proof.sequence)
        self.assertFalse(later.complete)

    def test_cancelled_port_starts_no_native_operation_and_binding_is_once(self):
        event=threading.Event(); event.set()
        self.port.bind_cancellation(event)
        self.assertNotEqual(self.port.ready()['outcome'],'ok')
        self.assertEqual(self.calls,[])
        with self.assertRaises(ValueError): self.port.bind_cancellation(threading.Event())

    def test_port_cancel_state_does_not_call_override_or_corrupt_truthiness(self):
        event=threading.Event();event.is_set=lambda:(_ for _ in ()).throw(AssertionError('override'))
        self.port.bind_cancellation(event)
        self.assertEqual(self.port.ready()['outcome'],'ok')
        class Flag:
            def __bool__(self):raise AssertionError('must not execute truthiness')
        event._flag=Flag()
        self.assertEqual(self.port.ready()['outcome'],'unknown')

    def test_actual_native_surrogate_and_peer_role_cancel_while_main_lane_waits(self):
        from task_tower import beads_admission as admission
        from task_tower.beads_stages import _Coordinator
        from task_tower.processes import run_command
        from tests.test_beads_stages import SyntheticBackend
        stop=threading.Event();self.port.bind_cancellation(stop)
        backend=SyntheticBackend();receipts={};original=self.runner
        peer_capture=self.root/'peer-capture';native_capture=self.root/'native-capture'
        peer_capture.mkdir();native_capture.mkdir()
        peer_ready=self.root/'peer-ready';native_ready=self.root/'native-ready'
        program='import sys,time;from pathlib import Path;Path(sys.argv[1]).write_bytes(b"ready");time.sleep(3)'
        def runner(op,argv,cwd,timeout,env):
            if op!='beads_heartbeat':
                data,receipt=original(op,argv,cwd,timeout,env)
                if op=='beads_claim':
                    actor=argv[argv.index('--actor')+1]
                    data[0]['assignee']=actor;self.row['assignee']=actor
                if op=='beads_set_state':
                    data['new_value']=next(a.split('=',1)[1] for a in argv if a.startswith('tower-stage='))
                    self.event[0]['created_by']=argv[argv.index('--actor')+1]
                    self.event[0]['description']='Synthetic\n\nReason: '+argv[argv.index('--reason')+1]
                return data,receipt
            data,receipt=admission._production_runner('beads_surrogate',[sys.executable,'-c',program,str(native_ready)],
                self.root,timeout,env,cancel_requested=stop)
            receipts['native']=receipt
            return data,receipt
        self.port._runner=runner
        def execute(slot,call,cancel):
            self.now=61
            receipt=run_command([sys.executable,'-c',program,str(peer_ready)],self.root,10,
                cancel_requested=lambda:threading.Event.is_set(cancel),
                capture=dict(directory=peer_capture,max_bytes_per_stream=65536))
            receipts['peer']=receipt
            return dict(outcome='unknown',process=admission._process_fact('synthetic_peer',receipt))
        backend.execute=execute
        def request_stop():
            deadline=time.monotonic()+4
            while not(native_ready.exists() and peer_ready.exists()) and time.monotonic()<deadline:time.sleep(.01)
            stop.set()
        stopper=threading.Thread(target=request_stop,daemon=False);stopper.start()
        began=time.monotonic()
        controller=_Coordinator(self.port._policy,self.port,backend,stop,lambda:self.now)
        result=controller.run();stopper.join(5)
        self.assertLess(time.monotonic()-began,5)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(result['outcome'],'unknown')
        self.assertTrue(controller.cleanup_confirmed)
        self.assertIn('peer',receipts,(result,self.calls))
        for name in ('peer','native'):
            self.assertEqual(receipts[name]['status'],'cancelled')
            self.assertTrue(receipts[name]['cleanup_confirmed'])
            self.assertFalse(receipts[name]['stdout_tail_unknown'])
            self.assertFalse(receipts[name]['stderr_tail_unknown'])
        self.assertTrue(self.port.get_operation_proof().complete)
    def runner(self,op,argv,cwd,timeout,env):
        self.calls.append((op,argv,timeout,env))
        values=dict(git_config='',git_toplevel=str(self.root/'source'),git_metadata=str(self.root/'source/.git'),git_index='',git_head=HEAD,git_tree=TREE,git_status='',beads_ready=[self.readyrow],beads_show=[self.row] if self.claimed else [self.readyrow],beads_dependencies=self.deps,beads_event_read=self.event,beads_set_state=OBS['state-0'],beads_heartbeat=dict(id=BEAD,owner=ACTOR,schema_version=1,status='heartbeat'))
        if op=='beads_claim':
            self.claimed=True
            value=copy.deepcopy(OBS['claim'])
        else: value=copy.deepcopy(values.get(op))
        if op=='beads_heartbeat':
            self.row['heartbeat_at']='2026-11-05T08:33:41Z'; self.row['lease_expires_at']='2026-11-05T08:38:41Z'
        value=self.bad.get(op,value)
        return value,facts(**self.proc.get(op,{}))
    def claim(self): return self.port.claim(BEAD,ACTOR,{'outcome':'eligible_observation'})
    def owned(self):
        result=self.claim(); self.assertEqual(result['outcome'],'ok',result); return result['pins']
    def test_claim_race_has_no_effects_for_loser(self):
        self.proc['beads_claim']={'status':'failed','exit_code':1}
        self.assertEqual(self.claim()['outcome'],'unknown')
        self.assertEqual(sum(c[0]=='beads_claim' for c in self.calls),1)
        self.assertEqual(self.claim()['outcome'],'unknown')
        self.assertEqual(sum(c[0]=='beads_claim' for c in self.calls),1)
    def test_owned_claim_is_not_fresh_ownership(self):
        self.claimed=True
        self.assertEqual(self.claim()['outcome'],'refused')
        self.assertFalse(any(c[0]=='beads_claim' for c in self.calls))
    def test_claim_reobserves_and_packets_are_not_capabilities(self):
        self.bad['beads_ready']=[]
        self.assertEqual(self.claim()['outcome'],'refused')
    def test_legitimately_claimed_task_can_continue_without_observe(self):
        pins=self.owned()
        with patch.object(self.portmod.admission,'observe',side_effect=AssertionError('postclaim observe')):
            self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'ok')
    def test_postclaim_blocker_change_refuses(self):
        pins=self.owned(); self.row['dependencies'][0]['status']='open'; self.deps[0]['status']='open'
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_unknown_gate_semantics_refuse(self):
        pins=self.owned(); self.row['dependencies'][0]['dependency_type']='waits-for'; self.deps[0]['dependency_type']='waits-for'
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_broad_ready_claim_refused(self):
        self.assertEqual(self.port.claim('*',ACTOR,{})['outcome'],'refused'); self.assertFalse(self.calls)
    def test_changed_native_owner_or_authorized_base_refuses(self):
        pins=self.owned(); self.row['assignee']='other'
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'unknown')
        self.setUp(); pins=self.owned(); self.config['projects'][0]['expected_head']='c'*40; self.write()
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_policy_cannot_expand_admission(self):
        self.policy['ownership']['stgq-other']=dict(paths=['tests'],domains=['test']); self.write()
        with self.assertRaises(ValueError): self.portmod.load_stage_policy(self.root/'stage.json')
    def test_ownership_requires_operator_paths_and_domains(self):
        for value in ({'paths':['a']},{'paths':['a'],'domains':[]},{'paths':['../a'],'domains':['x']},{'paths':['a','A/b'],'domains':['x']},{'paths':['a'],'domains':['Unknown']}):
            self.policy['ownership'][BEAD]=value; self.write()
            with self.assertRaises(ValueError): self.portmod.load_stage_policy(self.root/'stage.json')
    def test_overflow_and_secret_sentinels_refuse(self):
        self.bad['beads_ready']=[self.readyrow]*1001
        result=self.port.ready(); self.assertEqual(result['outcome'],'refused'); self.assertNotIn('Synthetic',json.dumps(result))
    def test_event_requires_actor_reference_digest_readback(self):
        self.owned(); self.event[0]['created_by']='foreign'
        self.assertEqual(self.port.append_event(BEAD,ACTOR,dict(value='spec_pending',reference='synthetic-host-ref-0',digest=hashlib.sha256(b'0').hexdigest()))['outcome'],'unknown')
    def test_event_is_verified_and_no_append_notes_logging(self):
        self.owned()
        result=self.port.append_event(BEAD,ACTOR,dict(value='spec_pending',reference='synthetic-host-ref-0',digest=hashlib.sha256(b'0').hexdigest()))
        self.assertEqual(result['outcome'],'ok',result)
        self.assertFalse(any('--append-notes' in c[1] for c in self.calls))
    def test_unknown_write_not_retried(self):
        self.owned(); self.proc['beads_set_state']={'stdout_tail_unknown':True}
        event=dict(value='spec_pending',reference='r',digest='a'*64)
        self.assertEqual(self.port.append_event(BEAD,ACTOR,event)['outcome'],'unknown')
        self.assertEqual(self.port.append_event(BEAD,ACTOR,event)['outcome'],'unknown')
        self.assertEqual(sum(c[0]=='beads_set_state' for c in self.calls),1)
    def test_private_task_inputs_use_reviewed_optional_mapping(self):
        pins=self.owned(); self.row.update(CONTRACT['input_fields_extension']['observed_row']); self.row.update(id=BEAD,status='in_progress',assignee=ACTOR)
        result=self.port.read_task_inputs(BEAD,ACTOR,pins)
        self.assertEqual(result['outcome'],'ok',result); self.assertEqual(set(result['inputs']),{'title','description','design','acceptance_criteria','notes'})
    def test_task_input_utf8_combined_24k_boundary(self):
        pins=self.owned()
        for name in ('title','description','design','acceptance_criteria','notes'): self.row[name]=''
        self.row['title']='x'; self.row['notes']='я'*12287+'x'
        self.assertEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['outcome'],'ok')
        self.row['notes']+='я'
        self.assertEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_input_digest_changes_for_each_of_five_fields(self):
        pins=self.owned(); original=self.port.read_task_inputs(BEAD,ACTOR,pins)['input_digest']
        for key in ('title','description','design','acceptance_criteria','notes'):
            row=copy.deepcopy(self.row); self.row[key]='CHANGED'
            self.assertNotEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['input_digest'],original); self.row=row
    def test_lease_status_timestamp_labels_and_host_events_do_not_change_input_digest(self):
        pins=self.owned(); first=self.port.read_task_inputs(BEAD,ACTOR,pins)['input_digest']
        self.row.update(labels=['tower-stage:spec_review'],updated_at='changed')
        self.assertEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['input_digest'],first)
    def test_task_prose_is_never_public_or_argv_authority(self):
        pins=self.owned(); self.row['notes']='PRIVATE_SENTINEL --claim'
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)))
        self.port.read_task_inputs(BEAD,ACTOR,pins)
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(self.calls))
    def test_heartbeat_requires_advancement_and_fences_uncertainty(self):
        self.owned(); self.assertEqual(self.port.heartbeat(BEAD,ACTOR)['outcome'],'ok')
        self.assertEqual(self.port.heartbeat(BEAD,ACTOR)['outcome'],'unknown')
        count=len(self.calls); self.port.heartbeat(BEAD,ACTOR); self.assertEqual(len(self.calls),count)
    def test_expired_monotonic_lease_never_renews(self):
        self.owned(); self.now=301
        self.assertEqual(self.port.heartbeat(BEAD,ACTOR)['outcome'],'unknown')
        self.assertFalse(any(c[0]=='beads_heartbeat' for c in self.calls))
    def test_process_cleanup_eof_capture_and_budget_are_required(self):
        for changes in ({'cleanup_confirmed':False},{'stdout_truncated':True},{'stdout_tail_unknown':True},{'duration_seconds':None}):
            self.proc['beads_ready']=changes; self.assertEqual(self.port.ready()['outcome'],'unknown')
        for op,argv,timeout,env in self.calls:
            self.assertLessEqual(timeout,25); self.assertNotIn('GH_TOKEN',env); self.assertNotIn('GITHUB_TOKEN',env)

    def test_plain_copied_policy_cannot_create_live_port(self):
        loaded=self.portmod.load_stage_policy(self.root/'stage.json')
        with self.assertRaises(ValueError): self.portmod.BeadsStagePort(dict(loaded),runner=self.runner)
    def test_mutating_returned_pins_cannot_mutate_live_authority(self):
        pins=self.owned(); pins['base']['head']='c'*40
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_native_expired_lease_refuses_even_when_monotonic_is_fresh(self):
        self.utcnow.return_value=self.portmod.datetime.fromisoformat('2026-11-06T08:33:40+00:00')
        self.assertNotEqual(self.claim()['outcome'],'ok')
    def test_lease_readback_cannot_regress_after_claim(self):
        pins=self.owned(); self.row['heartbeat_at']='2026-11-05T08:33:39Z'; self.row['lease_expires_at']='2026-11-05T08:38:39Z'
        self.assertNotEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'ok')
    def test_unknown_dependency_schema_is_not_an_empty_blocker_set(self):
        pins=self.owned(); self.bad['beads_dependencies']=[{'depends_on_id':'stgq-ubp','type':'blocks'}]
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_parent_with_dependencies_and_ancestor_are_refused(self):
        pins=self.owned(); self.row['parent']='stgq-vrw'
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_policy_mutation_refuses_before_more_native_commands(self):
        pins=self.owned(); self.policy['ownership'][BEAD]['domains']=['changed']; self.write(); count=len(self.calls)
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused'); self.assertEqual(len(self.calls),count)
    def test_nontext_null_title_and_optional_mapping(self):
        pins=self.owned(); self.row['notes']=None
        self.assertEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['inputs']['notes'],'')
        self.row['title']=None
        self.assertEqual(self.port.read_task_inputs(BEAD,ACTOR,pins)['outcome'],'refused')
    def test_event_readback_reference_parent_type_and_closed_required(self):
        self.owned(); self.event[0]['parent']='stgq-wrong'
        event=dict(value='spec_pending',reference='synthetic-host-ref-0',digest=hashlib.sha256(b'0').hexdigest())
        self.assertEqual(self.port.append_event(BEAD,ACTOR,event)['outcome'],'unknown')
    def test_secret_environment_is_removed_case_insensitively(self):
        with patch.dict('os.environ',{'gh_token':'SECRET','GitHub_TOKEN':'SECRET','BD_ATTACK':'SECRET','DOLT_ATTACK':'SECRET'}): self.port.ready()
        self.assertNotIn('SECRET',json.dumps([c[3] for c in self.calls]))

    def test_malformed_host_identity_returns_sanitized_refusal(self):
        for bead in (None, [], {}, 1, '*'):
            result=self.port.claim(bead,ACTOR,{})
            self.assertEqual(result['outcome'],'refused')
        self.assertFalse(self.calls)
    def test_structural_parent_uses_bounded_canonical_reads(self):
        original=self.runner
        child=copy.deepcopy(OBS['show-after-heartbeat'][0])
        child.update(id=BEAD,heartbeat_at=self.row['heartbeat_at'],lease_expires_at=self.row['lease_expires_at'])
        parent=copy.deepcopy(OBS['create-parent'])
        def runner(op,argv,cwd,timeout,env):
            if op=='beads_show' and '--id=stgq-vrw' in argv: return [parent],facts()
            if op=='beads_dependencies' and 'stgq-vrw' in argv: return [],facts()
            return original(op,argv,cwd,timeout,env)
        self.port._runner=runner
        pins=self.owned(); self.row=child; self.deps=copy.deepcopy(child['dependencies'])
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'ok')
        parent['parent']='stgq-ancestor'
        self.assertEqual(self.port.verify_owner_and_eligibility(BEAD,ACTOR,pins)['outcome'],'refused')


class HashFileTests(unittest.TestCase):
    """Synthetic byte streams use observed executable size, never installed bytes."""
    class Stream:
        def __init__(self, size):
            self.remaining = size
            self.requests = []
            self.closed = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def read(self, size):
            if not 0 < size <= 65536:
                raise AssertionError('executable hashing must remain bounded and streaming')
            self.requests.append(size)
            count = min(size, self.remaining)
            self.remaining -= count
            return b'x' * count

    def test_observed_157179392_byte_executable_can_be_stream_hashed(self):
        from task_tower.beads_stage_port import _hashfile
        stream = self.Stream(157179392)
        with patch('task_tower.beads_stage_port.admission.safe_config_path') as guard:
            guard.return_value.open.return_value = stream
            try:
                digest = _hashfile(Path('synthetic-executable.exe'))
            except ValueError:
                self.fail('qualified observed executable size is rejected by the hashing ceiling')
            guard.assert_called_once_with(Path('synthetic-executable.exe'))
            guard.return_value.open.assert_called_once_with('rb')
        # SHA256 of exactly 157179392 ASCII x bytes, independently precomputed.
        self.assertEqual(digest, 'bb25351c15ce3c9effee5a18e9caf2865fa3277c8d58e390b990ae3f44dabc60')
        self.assertEqual(stream.remaining, 0)
        self.assertTrue(stream.closed)
        self.assertGreater(len(stream.requests), 1)

    def test_executable_above_256_mib_is_refused_with_bounded_reads(self):
        from task_tower.beads_stage_port import _hashfile
        stream = self.Stream(256 * 1024 * 1024 + 1)
        with patch('task_tower.beads_stage_port.admission.safe_config_path') as guard:
            guard.return_value.open.return_value = stream
            with self.assertRaisesRegex(ValueError, '^executable_limit$'):
                _hashfile(Path('synthetic-executable.exe'))
        self.assertTrue(stream.closed)
        self.assertTrue(stream.requests)
