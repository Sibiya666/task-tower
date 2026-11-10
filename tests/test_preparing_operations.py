"""Typed transport storage only: real disposable SQLite, no Git delivery."""
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from task_tower.preparing_recovery import fingerprint
from task_tower.connector.store import ConnectorStore
from tests.fixtures.preparing_recovery import receipt

class SimulatedCrash(BaseException):pass

class PreparingJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'journal';self.connector='fixture-'+uuid.uuid4().hex
        self.store=ConnectorStore(self.path,self.connector);self.addCleanup(self.store.close)
        self.r=dict(receipt(),connector_id=self.connector)
        self.command=dict(version=1,kind='execute',command_id='command1',attempt_id='attempt1',project_id='project1',base_sha='a'*40,input={'text':'fixture private task body'},source=dict(base_sha='a'*40,head_sha='a'*40,diff=''))
        self.store.receive(self.command);self.store.update('command1',phase='needs_reconciliation')
        self.tree=dict(project_id='project1',path=str(Path(self.tmp.name)/'supplied-tree'),branch=self.r['branch'],base_sha='a'*40,state='preparing',review=False)
        self.ready=dict(self.tree,state='ready');self.store.save_worktree('attempt1',self.tree)
        self.r.update(command_sha256=fingerprint(self.command),worktree_sha256=fingerprint(self.tree),cleanup_sha256=fingerprint(dict(cleanup_resources=None,cleanup_confirmed=None)))

    def reopen(self):
        self.store.close();self.store=ConnectorStore(self.path,self.connector);self.addCleanup(self.store.close)

    def unchanged(self):
        self.assertEqual(self.store.worktree('attempt1'),self.tree)
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')
        self.assertEqual(self.store.pending_events(),[])

    def test_durable_intent_restart_preserves_unknown_fence(self):
        data=self.store.begin_preparing(self.r)
        self.assertEqual(data['state'],'intent');self.assertEqual(data['receipt_sha256'],fingerprint(self.r))
        self.assertNotIn(self.command['input']['text'],str(data));self.assertNotIn(self.tree['path'],str(data))
        self.reopen();self.assertEqual(self.store.preparing_operation('op-1'),data);self.unchanged()
        with self.assertRaises(ValueError):self.store.begin_preparing(self.r)

    def test_unknown_record_never_reopens_attempt(self):
        self.store.begin_preparing(self.r);self.store.unknown_preparing(self.r);self.reopen()
        self.assertEqual(self.store.preparing_operation('op-1')['state'],'unknown')
        with self.assertRaises(ValueError):self.store.begin_preparing(dict(self.r,operation_id='op-2'))
        self.assertIsNone(self.store.preparing_operation('op-2'));self.unchanged()

    def test_result_worktree_and_one_ack_commit_together(self):
        self.store.begin_preparing(self.r);result=self.store.complete_preparing(self.r,self.ready)
        self.assertEqual(result['state'],'prepared');self.assertEqual(result['receipt_sha256'],fingerprint(self.r))
        self.assertEqual(self.store.worktree('attempt1'),self.ready)
        events=self.store.pending_events();self.assertEqual(len(events),1);self.assertEqual(events[0]['preparing'],result)
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')
        self.reopen();self.assertEqual(self.store.preparing_operation('op-1')['result'],result)
        with self.assertRaises(ValueError):self.store.complete_preparing(self.r,self.ready)
        self.store.unknown_preparing(self.r)
        self.assertEqual(self.store.preparing_operation('op-1')['state'],'prepared');self.assertEqual(self.store.pending_events(),events)

    def test_typed_invalid_receipt_has_no_intent(self):
        with self.assertRaises(ValueError):self.store.begin_preparing(dict(self.r,version=True))
        self.assertIsNone(self.store.preparing_operation('op-1'));self.unchanged()

    def test_receipt_for_another_connector_has_no_intent(self):
        with self.assertRaisesRegex(ValueError,'^preparing_connector_mismatch$'):
            self.store.begin_preparing(dict(self.r,connector_id='foreign-connector'))
        self.assertIsNone(self.store.preparing_operation('op-1'));self.unchanged()

    def test_same_attempt_cannot_acquire_a_second_operation(self):
        self.store.begin_preparing(self.r)
        with self.assertRaises(ValueError):self.store.begin_preparing(dict(self.r,operation_id='op-2'))
        self.assertIsNone(self.store.preparing_operation('op-2'));self.unchanged()

    def test_operation_id_cannot_cross_attempts(self):
        self.store.begin_preparing(self.r)
        command=dict(self.command,command_id='command2',attempt_id='attempt2');self.store.receive(command)
        self.store.update('command2',phase='needs_reconciliation')
        tree=dict(self.tree,path=str(Path(self.tmp.name)/'other-tree'),branch='codex/headless-attempt2');self.store.save_worktree('attempt2',tree)
        other=dict(self.r,command_id='command2',attempt_id='attempt2',native_owner='tower-attempt2',branch=tree['branch'],command_sha256=fingerprint(command),worktree_sha256=fingerprint(tree))
        with self.assertRaises(ValueError):self.store.begin_preparing(other)
        self.assertEqual(self.store.preparing_operation('op-1')['receipt'],self.r);self.assertEqual(self.store.worktree('attempt2'),tree)

    def drift_denies(self,change):
        self.store.begin_preparing(self.r);change()
        old_tree=self.store.worktree('attempt1');old_events=self.store.pending_events()
        with self.assertRaisesRegex(ValueError,'^preparing_history_changed$'):self.store.complete_preparing(self.r,self.ready)
        self.assertEqual(self.store.preparing_operation('op-1')['state'],'intent')
        self.assertEqual(self.store.worktree('attempt1'),old_tree);self.assertEqual(self.store.pending_events(),old_events)

    def test_resource_drift_remains_owned(self):
        self.drift_denies(lambda:self.store.update('command1',resource_id='resource1'))
        self.assertEqual(self.store.command('command1')['resource_id'],'resource1')
    def test_worktree_drift_is_not_overwritten(self):self.drift_denies(lambda:self.store.save_worktree('attempt1',dict(self.tree,state='foreign')))
    def test_extra_command_denies_commit(self):self.drift_denies(lambda:self.store.receive(dict(self.command,command_id='other-command')))
    def test_pending_own_event_denies_commit(self):self.drift_denies(lambda:self.store.lifecycle_event('attempt1','failed',command_id='command1'))

    def test_unrelated_event_does_not_change_snapshot(self):
        self.store.begin_preparing(self.r);event=self.store.lifecycle_event('other-attempt','failed',command_id='other-command')
        self.store.complete_preparing(self.r,self.ready)
        self.assertEqual(len(self.store.pending_events()),2);self.assertEqual(self.store.pending_events()[0],event)

    def test_each_interrupted_write_rolls_back_all_three_records(self):
        self.store.begin_preparing(self.r);database=self.store.db
        for prefix in ('UPDATE preparing_operations','UPDATE worktrees','INSERT INTO outbox'):
            class FailingConnection:
                def __getattr__(proxy,key):return getattr(database,key)
                def __enter__(proxy):database.__enter__();return proxy
                def __exit__(proxy,*args):return database.__exit__(*args)
                def execute(proxy,sql,*args):
                    if sql.startswith(prefix):raise SimulatedCrash()
                    return database.execute(sql,*args)
            with self.subTest(prefix=prefix),patch.object(self.store,'db',FailingConnection()):
                with self.assertRaises(SimulatedCrash):self.store.complete_preparing(self.r,self.ready)
            self.assertEqual(self.store.preparing_operation('op-1')['state'],'intent');self.unchanged()

if __name__=='__main__':unittest.main()
