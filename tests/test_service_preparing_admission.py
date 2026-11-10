"""Native-bound preparing admission; no acknowledged-result transition."""
import copy,sqlite3,unittest
from unittest.mock import patch
from task_tower.service.store import Store
from task_tower.preparing_recovery import fingerprint
from task_tower.service.beads import ServiceError
from tests.fixtures.service_preparing_recovery import PreparingServiceFixture

class PreparingAdmissionTests(PreparingServiceFixture,unittest.TestCase):
    def test_default_empty_registry_refuses_without_effect(self):
        self.s.approved_preparing={}
        with self.assertRaises(ServiceError):self.admit()
        self.assertEqual(self.s.lifecycle_commands('host1'),[]);self.original()
    def test_admission_is_idempotent_and_keeps_unknown_fence_capacity(self):
        info=self.admit();self.assertEqual(self.admit(),info);self.assertEqual(self.status(),info)
        self.assertEqual(info['state'],'pending');self.assertEqual(info['receipt_sha256'],fingerprint(self.r));self.original()
        commands=self.s.lifecycle_commands('host1');self.assertEqual(len(commands),1)
        self.assertEqual(commands[0]['kind'],'prepare_existing');self.assertEqual(commands[0]['receipt'],self.r)
        self.assertEqual(commands[0]['command_id'],info['control_command_id']);self.assertNotEqual(info['execute_command_id'],self.command['command_id'])
    def test_conflicting_or_second_operation_never_replaces_intent(self):
        first=self.admit()
        for change in (dict(worktree_sha256='4'*64),dict(operation_id='other-operation')):
            other=dict(self.r,**change);self.s.approved_preparing={'p':frozenset({fingerprint(self.r),fingerprint(other)})}
            with self.assertRaises(ServiceError):self.admit(other)
            self.assertEqual(self.status(),first);self.original()
        self.assertEqual(len(self.s.lifecycle_commands('host1')),1)
    def test_foreign_connector_cannot_admit_or_read(self):
        with self.assertRaises(ServiceError):self.admit(connector='host2')
        self.admit()
        with self.assertRaises(ServiceError):self.s.preparing_status(self.r['operation_id'],'host2')
        self.original()
    def test_fresh_native_owner_dependencies_metadata_and_plan_are_required(self):
        rows=copy.deepcopy(self.native.rows);approved=self.s.approved_plans
        for change in ('owner','dependency','metadata','scope','approval'):
            self.native.rows=copy.deepcopy(rows);self.s.approved_plans=approved
            if change=='owner':self.native.rows['pilot-task']['assignee']='foreign'
            if change=='dependency':self.native.rows['pilot-dep']['status']='open'
            if change=='metadata':self.native.rows['pilot-task']['metadata']={'fence':True}
            if change=='scope':self.native.rows['pilot-task']['description']='changed'
            if change=='approval':self.s.approved_plans={}
            with self.subTest(change=change),self.assertRaises(ServiceError):self.admit()
            self.assertEqual(self.s.lifecycle_commands('host1'),[])
    def test_old_execute_must_be_acknowledged_and_hash_bound(self):
        with self.s.db:self.s.db.execute("UPDATE lifecycle_commands SET state='queued' WHERE command_id=?",(self.command['command_id'],))
        with self.assertRaises(ServiceError):self.admit()
        with self.s.db:self.s.db.execute("UPDATE lifecycle_commands SET state='acknowledged' WHERE command_id=?",(self.command['command_id'],))
        wrong=dict(self.r,command_sha256='0'*64);self.s.approved_preparing={'p':frozenset({fingerprint(wrong)})}
        with self.assertRaises(ServiceError):self.admit(wrong)
        self.original()
    def test_author_head_review_thread_and_other_states_remain_fenced(self):
        changes=[dict(author_thread_id='author'),dict(head_sha='b'*40),dict(review_threads=['review']),dict(thread_id='thread'),dict(turn_id='turn'),dict(quiescent=True),dict(phase='needs_input'),dict(execution_state='running')]
        for change in changes:
            with self.s.db:self.s._save_attempt(dict(self.a,**change))
            with self.subTest(change=change),self.assertRaises(ServiceError):self.admit()
        self.assertEqual(self.s.lifecycle_commands('host1'),[])
    def test_pending_restart_never_resumes_unknown_attempt(self):
        info=self.admit();self.s.close();self.reopen();self.assertEqual(self.status(),info);self.original()
        with self.assertRaises(ServiceError):self.s.resume_lifecycle(self.a['attempt_id'],'host1')
        self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
    def test_control_validate_rechecks_registry_and_native_without_unfencing(self):
        info=self.admit();self.assertEqual(self.s.validate_lifecycle_command(info['control_command_id'],'host1'),self.a)
        self.s.approved_preparing={}
        with self.assertRaises(ServiceError):self.s.validate_lifecycle_command(info['control_command_id'],'host1')
        with self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.original()

    def test_registry_is_bounded_before_effect_and_cannot_mutate_approval(self):
        for value in ([],{'q':[]},{'p':['*']},{'p':['a'*64]*33}):
            with self.subTest(value=value),self.assertRaises(ValueError):Store(self.root/'denied',self.beads,approved_preparing=value)
            self.assertEqual(list(self.root.glob('denied*')),[])
        self.s.close();self.approved={'p':set()};self.reopen();self.approved['p'].add(fingerprint(self.r))
        with self.assertRaises(ServiceError):self.admit()
        self.original()
    def test_profile_drift_is_fenced(self):
        with patch.object(self.beads,'profile_fingerprint',return_value='changed'),self.assertRaises(ServiceError):self.admit()
        self.original()
    def test_additional_command_history_is_fenced(self):
        with self.s.db:self.s.db.execute("INSERT INTO lifecycle_commands SELECT 'extra',attempt_id,connector_id,state,data FROM lifecycle_commands")
        with self.assertRaises(ServiceError):self.admit()
        self.original()
    def test_unknown_decision_history_is_fenced(self):
        with self.s.db:self.s.db.execute("INSERT INTO decisions VALUES ('decision','host1',?,'{}','fixture')",(self.a['attempt_id'],))
        with self.assertRaises(ServiceError):self.admit()
        self.original()
    def test_admission_rolls_back_intent_and_control_together(self):
        self.s.db.execute("CREATE TRIGGER reject_control BEFORE INSERT ON lifecycle_commands BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.admit()
        with self.assertRaises(ServiceError):self.status()
        self.assertEqual(self.s.lifecycle_commands('host1'),[]);self.original()

if __name__=='__main__':unittest.main()
