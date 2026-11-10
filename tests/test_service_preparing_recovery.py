"""Known preparing acknowledgement contracts; no HTTP or model start."""
import copy,json,sqlite3,unittest
from unittest.mock import patch
from task_tower.service.beads import ServiceError
from task_tower.preparing_recovery import fingerprint
from tests.fixtures.service_preparing_recovery import PreparingServiceFixture

class PreparingAcknowledgementTests(PreparingServiceFixture,unittest.TestCase):
    def test_known_ack_issues_one_original_execute_and_keeps_owner_capacity(self):
        info=self.admit();a=self.s.record_event(self.ack())
        self.assertEqual((a['phase'],a['execution_state']),('executing','not_started'));self.assertEqual(self.status()['state'],'prepared')
        commands=self.s.lifecycle_commands('host1');self.assertEqual(len(commands),1)
        self.assertEqual(commands[0],dict(self.command,command_id=info['execute_command_id']))
        self.assertEqual(a['active_command_id'],commands[0]['command_id']);self.assertEqual(a['attempt_id'],self.a['attempt_id'])
        self.assertEqual(self.s.active_count('host1'),1);self.assertEqual(self.native.rows['pilot-task']['assignee'],self.a['actor'])
        self.assertEqual(sum('--claim' in call for call in self.native.calls),1)
    def test_duplicate_ack_and_reopen_do_not_issue_another_execute(self):
        self.admit();first=self.s.record_event(self.ack());commands=self.s.lifecycle_commands('host1')
        self.assertEqual(self.s.record_event(self.ack()),first);self.s.close();self.reopen()
        self.assertEqual(self.s.lifecycle_commands('host1'),commands);self.assertEqual(self.s.record_event(self.ack()),first)
        self.assertEqual(self.status()['state'],'prepared')
    def test_forged_ack_fields_do_not_advance_or_ack_control(self):
        self.admit()
        for changes in (dict(version=True),dict(receipt_sha256='0'*64),dict(engine_sha='c'*40),dict(extra=True)):
            with self.subTest(changes=changes),self.assertRaises(ServiceError):self.s.record_event(self.ack(**changes))
            self.original();self.assertEqual(self.status()['state'],'pending')
        self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
    def test_native_drift_between_control_and_ack_never_issues_execute(self):
        self.admit();self.native.rows['pilot-task']['assignee']='foreign'
        with self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.assertEqual(self.s.attempt(self.a['attempt_id']),self.a);self.assertEqual(self.status()['state'],'pending')
        self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
    def test_ack_transaction_rolls_back_and_retry_commits_once(self):
        info=self.admit()
        self.s.db.execute("CREATE TRIGGER reject_execute BEFORE INSERT ON lifecycle_commands WHEN NEW.command_id='"+info['execute_command_id']+"' BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.s.record_event(self.ack())
        self.original();self.assertEqual(self.status()['state'],'pending');self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
        self.s.db.execute('DROP TRIGGER reject_execute');self.s.record_event(self.ack());self.assertEqual(len(self.s.lifecycle_commands('host1')),1)

    def failure(self,event_id='control-failed'):
        return dict(version=1,event_id=event_id,attempt_id=self.a['attempt_id'],connector_id='host1',lifecycle=dict(kind='failed',command_id=self.status()['control_command_id']))
    def test_failed_control_is_unknown_and_never_requeued(self):
        self.admit();event=self.failure();self.s.record_event(event);self.original()
        self.assertEqual(self.status()['state'],'unknown');self.assertEqual(self.s.lifecycle_commands('host1'),[])
        self.assertEqual(self.s.record_event(event),self.a)
        with self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.assertEqual(self.admit()['state'],'unknown');self.assertEqual(self.s.lifecycle_commands('host1'),[])
    def test_late_failure_never_downgrades_known_prepared_result(self):
        self.admit();event=self.failure();self.s.record_event(self.ack());commands=self.s.lifecycle_commands('host1');a=self.s.attempt(self.a['attempt_id'])
        self.s.record_event(event);self.assertEqual(self.status()['state'],'prepared');self.assertEqual(self.s.attempt(self.a['attempt_id']),a)
        self.assertEqual(self.s.lifecycle_commands('host1'),commands)
    def test_new_event_for_known_result_does_not_duplicate_execute(self):
        self.admit();first=self.s.record_event(self.ack());commands=self.s.lifecycle_commands('host1');event=dict(self.ack(),event_id='another-ack')
        self.s.approved_preparing={};self.assertEqual(self.s.record_event(event),first);self.assertEqual(self.s.lifecycle_commands('host1'),commands)
    def test_conflicting_duplicate_event_id_is_refused(self):
        self.admit();self.s.record_event(self.ack());commands=self.s.lifecycle_commands('host1')
        with self.assertRaises(ServiceError):self.s.record_event(self.ack(engine_sha='d'*40))
        self.assertEqual(self.s.lifecycle_commands('host1'),commands)
    def test_transport_connection_change_does_not_attest_execution(self):
        self.admit();self.s.record_event(dict(version=1,event_id='transport',attempt_id=self.a['attempt_id'],connector_id='host1',lifecycle=dict(kind='disconnected')))
        a=self.s.record_event(self.ack());self.assertEqual(a['execution_state'],'not_started');self.assertEqual(a['connection_state'],'disconnected')
        self.assertIsNone(a.get('author_thread_id'));self.assertEqual(len(self.s.lifecycle_commands('host1')),1)
    def test_old_source_drift_before_ack_stays_fenced(self):
        self.admit();changed=copy.deepcopy(self.command);changed['source']['head_sha']='c'*40
        with self.s.db:self.s.db.execute('UPDATE lifecycle_commands SET data=? WHERE command_id=?',(json.dumps(changed),self.command['command_id']))
        with self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.original();self.assertEqual(self.status()['state'],'pending')
    def test_all_ack_transaction_writes_roll_back_together(self):
        self.admit()
        for action in ('UPDATE ON preparing_recoveries','UPDATE ON lifecycle_commands','UPDATE ON attempts','INSERT ON lifecycle_commands','INSERT ON events'):
            with self.subTest(action=action):
                self.s.db.execute("CREATE TRIGGER reject_ack BEFORE "+action+" BEGIN SELECT RAISE(ABORT,'fixture'); END")
                try:
                    with self.assertRaises(sqlite3.IntegrityError):self.s.record_event(self.ack())
                finally:self.s.db.execute('DROP TRIGGER reject_ack')
                self.original();self.assertEqual(self.status()['state'],'pending');self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
                self.assertIsNone(self.s.db.execute("SELECT 1 FROM events WHERE event_id='prepared-event'").fetchone())
        self.s.record_event(self.ack());self.assertEqual(len(self.s.lifecycle_commands('host1')),1)
    def test_failed_event_shape_and_scope_are_checked(self):
        self.admit()
        for changes in (dict(version=True),dict(attempt_id='foreign'),dict(connector_id='host2'),dict(extra=True)):
            with self.subTest(changes=changes),self.assertRaises(ServiceError):self.s.record_event(dict(self.failure(),**changes))
            self.original();self.assertEqual(self.status()['state'],'pending')
    def test_prepared_ack_matches_real_connector_result_contract(self):
        from task_tower.connector.store import ConnectorStore
        self.admit();event=self.ack();event['preparing']=ConnectorStore._preparing_result(self.r)
        self.s.record_event(event);self.assertEqual(self.status()['state'],'prepared')

    def test_failure_transaction_writes_are_atomic(self):
        self.admit();event=self.failure()
        for action in ('UPDATE ON preparing_recoveries','UPDATE ON lifecycle_commands','INSERT ON events'):
            with self.subTest(action=action):
                self.s.db.execute("CREATE TRIGGER reject_failure BEFORE "+action+" BEGIN SELECT RAISE(ABORT,'fixture'); END")
                try:
                    with self.assertRaises(sqlite3.IntegrityError):self.s.record_event(event)
                finally:self.s.db.execute('DROP TRIGGER reject_failure')
                self.original();self.assertEqual(self.status()['state'],'pending');self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')
                self.assertIsNone(self.s.db.execute('SELECT 1 FROM events WHERE event_id=?',(event['event_id'],)).fetchone())
        self.s.record_event(event);self.assertEqual(self.status()['state'],'unknown');self.assertEqual(self.s.lifecycle_commands('host1'),[])
    def test_unknown_control_cannot_be_replaced_by_another_approved_operation(self):
        self.admit();self.s.record_event(self.failure());other=dict(self.r,operation_id='another-operation')
        self.s.approved_preparing={'p':frozenset({fingerprint(other)})}
        with self.assertRaises(ServiceError):self.admit(other)
        self.original();self.assertEqual(self.status()['state'],'unknown');self.assertEqual(self.s.lifecycle_commands('host1'),[])
    def test_new_decision_history_before_ack_refuses(self):
        self.admit()
        with self.s.db:self.s.db.execute("INSERT INTO decisions VALUES ('decision','host1',?,'{}','fixture')",(self.a['attempt_id'],))
        with self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.original();self.assertEqual(self.status()['state'],'pending')
    def test_profile_change_before_ack_refuses(self):
        self.admit()
        with patch.object(self.beads,'profile_fingerprint',return_value='changed'),self.assertRaises(ServiceError):self.s.record_event(self.ack())
        self.original();self.assertEqual(self.status()['state'],'pending')

    def test_malformed_known_or_pending_journal_is_not_reported_as_prepared(self):
        self.admit();original=json.loads(self.s.db.execute('SELECT data FROM preparing_recoveries').fetchone()[0])
        for change in (dict(state='prepared',outcome=None),dict(outcome={'foreign':True}),dict(snapshot_sha256='invalid')):
            damaged=dict(original,**change)
            with self.s.db:self.s.db.execute('UPDATE preparing_recoveries SET data=?',(json.dumps(damaged),))
            with self.subTest(change=change),self.assertRaises(ServiceError):self.status()
            self.original();self.assertEqual(self.s.lifecycle_commands('host1')[0]['kind'],'prepare_existing')

if __name__=='__main__':unittest.main()
