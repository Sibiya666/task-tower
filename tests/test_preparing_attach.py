"""Disposable known preparing attach contracts; never live transport state."""
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from task_tower import preparing_recovery as contract
from task_tower.connector.preparing_recovery import PreparingRecovery
from task_tower.connector.store import ConnectorStore
from task_tower.connector.worktrees import Worktrees
from tests.fixtures.preparing_recovery import GitCase,receipt

class SimulatedCrash(BaseException):pass

class PreparingAttachTests(GitCase):
    def setUp(self):
        super().setUp()
        self.transport=tempfile.TemporaryDirectory();self.addCleanup(self.transport.cleanup)
        self.path=Path(self.transport.name)/'journal';self.connector='fixture-'+uuid.uuid4().hex
        self.store=ConnectorStore(self.path,self.connector);self.addCleanup(self.store.close)
        self.tree_root=Path(self.transport.name)/'trees';self.mapping={'project1':dict(repository=str(self.root),worktree_root=str(self.tree_root))}
        self.trees=Worktrees(self.mapping,self.store)
        self.command=dict(version=1,kind='execute',command_id='command1',attempt_id='attempt1',project_id='project1',base_sha=self.head,input={'text':'original approved task'},source=dict(base_sha=self.head,head_sha=self.head,diff=''))
        self.store.receive(self.command);self.store.update('command1',phase='needs_reconciliation')
        self.r=dict(receipt(),connector_id=self.connector,base_sha=self.head,branch_sha=self.head,engine_sha=self.head)
        self.target=self.tree_root/'attempt1';self.intent=dict(project_id='project1',path=str(self.target),branch=self.r['branch'],base_sha=self.head,state='preparing',review=False)
        self.store.save_worktree('attempt1',self.intent);self.git(self.root,'branch',self.r['branch'],self.head)
        self.r.update(command_sha256=contract.fingerprint(self.command),worktree_sha256=contract.fingerprint(self.intent),cleanup_sha256=contract.fingerprint(dict(cleanup_resources=None,cleanup_confirmed=None)))
        self.approved={'project1':frozenset({contract.fingerprint(self.r)})}
        self.source=patch.object(contract,'__file__',str(self.module));self.source.start();self.addCleanup(self.source.stop)
        self.manager=PreparingRecovery(self.store,self.trees,approved=self.approved)

    def unchanged(self):
        self.assertEqual(self.store.worktree('attempt1'),self.intent)
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')
        self.assertEqual(self.store.pending_events(),[])

    def test_default_empty_approval_has_no_effect(self):
        with self.assertRaisesRegex(ValueError,'^preparing_receipt_not_approved$'):PreparingRecovery(self.store,self.trees).run(self.r)
        self.assertFalse(self.target.exists());self.unchanged()
        self.assertIsNone(self.store.preparing_operation(self.r['operation_id']))

    def test_actual_engine_source_must_match_before_intent(self):
        changed=dict(self.r,engine_sha='b'*40)
        manager=PreparingRecovery(self.store,self.trees,approved={'project1':frozenset({contract.fingerprint(changed)})})
        with self.assertRaisesRegex(ValueError,'^preparing_source_or_connector_changed$'):manager.run(changed)
        self.assertFalse(self.target.exists());self.unchanged()
        self.assertIsNone(self.store.preparing_operation(self.r['operation_id']))

    def test_one_attach_known_result_and_duplicate_read(self):
        result=self.manager.run(self.r)
        self.assertEqual(result['state'],'prepared');self.assertEqual(result['receipt_sha256'],contract.fingerprint(self.r))
        self.assertEqual(self.git(self.target,'rev-parse','HEAD'),self.head)
        self.assertEqual(self.git(self.target,'status','--porcelain'),'')
        self.assertEqual(self.store.worktree('attempt1'),dict(self.intent,state='ready'))
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')
        events=self.store.pending_events();self.assertEqual(len(events),1);self.assertEqual(events[0]['preparing'],result)
        with patch.object(self.trees,'attach_preparing',side_effect=AssertionError('replayed Git')):
            self.assertEqual(self.manager.run(self.r),result)
        self.assertEqual(self.store.pending_events(),events)

    def test_conflicting_approved_receipt_cannot_reuse_operation(self):
        result=self.manager.run(self.r);other=dict(self.r,cleanup_sha256='4'*64)
        manager=PreparingRecovery(self.store,self.trees,approved={'project1':frozenset({contract.fingerprint(self.r),contract.fingerprint(other)})})
        with self.assertRaisesRegex(ValueError,'^preparing_operation_conflict$'):manager.run(other)
        self.assertEqual(self.manager.run(self.r),result);self.assertEqual(len(self.store.pending_events()),1)

    def test_changed_cleanup_fingerprint_denies_before_intent(self):
        self.store.update('command1',cleanup_confirmed=True)
        with self.assertRaisesRegex(ValueError,'^preparing_cleanup_changed$'):self.manager.run(self.r)
        self.assertFalse(self.target.exists());self.unchanged()
        self.assertIsNone(self.store.preparing_operation(self.r['operation_id']))

    def test_repository_replaced_after_preflight_never_attaches(self):
        clone=Path(self.transport.name)/'replacement';saved=Path(self.transport.name)/'original'
        self.git(self.root,'clone','--no-hardlinks','--quiet',str(self.root),str(clone))
        self.git(clone,'branch',self.r['branch'],self.head)
        inspect=self.trees.inspect_preparing;git=self.trees._git;observations=[];attaches=[]
        def inspected(*args):
            result=inspect(*args);observations.append(True)
            if len(observations)==2:
                self.root.rename(saved);clone.rename(self.root)
            return result
        def observed(repo,*args,**kwargs):
            if args[:2]==('worktree','add'):attaches.append(args)
            return git(repo,*args,**kwargs)
        with patch.object(self.trees,'inspect_preparing',side_effect=inspected),patch.object(self.trees,'_git',side_effect=observed):
            with self.assertRaisesRegex(ValueError,'^preparing_attach_unknown$'):self.manager.run(self.r)
        self.assertEqual(attaches,[]);self.assertFalse(self.target.exists());self.unchanged()
        self.assertEqual(self.store.preparing_operation('op-1')['state'],'unknown')

    def test_unknown_git_result_is_fenced_without_replay(self):
        with patch.object(self.trees,'attach_preparing',side_effect=RuntimeError('fixture unknown')):
            with self.assertRaises(ValueError):self.manager.run(self.r)
        self.assertEqual(self.store.preparing_operation(self.r['operation_id'])['state'],'unknown')
        with patch.object(self.trees,'attach_preparing',side_effect=AssertionError('replayed Git')) as git:
            with self.assertRaisesRegex(ValueError,'^preparing_operation_unknown$'):self.manager.run(self.r)
            git.assert_not_called()
        self.assertFalse(self.target.exists());self.unchanged()


    def reopen(self):
        self.store.close();self.store=ConnectorStore(self.path,self.connector);self.addCleanup(self.store.close)
        self.trees=Worktrees(self.mapping,self.store);self.manager=PreparingRecovery(self.store,self.trees,approved=self.approved)

    def crash_boundary(self,boundary):
        original=self.store.complete_preparing;database=self.store.db
        class FailOutbox:
            def __getattr__(proxy,key):return getattr(database,key)
            def __enter__(proxy):database.__enter__();return proxy
            def __exit__(proxy,*args):return database.__exit__(*args)
            def execute(proxy,sql,*args):
                if sql.startswith('INSERT INTO outbox'):raise SimulatedCrash()
                return database.execute(sql,*args)
        def after_commit(*args):original(*args);raise SimulatedCrash()
        if boundary=='intent':guard=patch.object(self.trees,'attach_preparing',side_effect=SimulatedCrash)
        elif boundary=='git':guard=patch.object(self.trees,'verify_preparing_attachment',side_effect=SimulatedCrash)
        elif boundary=='before_commit':guard=patch.object(self.store,'complete_preparing',side_effect=SimulatedCrash)
        elif boundary=='during_commit':guard=patch.object(self.store,'db',FailOutbox())
        else:guard=patch.object(self.store,'complete_preparing',side_effect=after_commit)
        with guard:
            with self.assertRaises(SimulatedCrash):self.manager.run(self.r)
        known=boundary=='after_commit'
        self.assertEqual(self.target.exists(),boundary!='intent')
        self.assertEqual(self.store.preparing_operation(self.r['operation_id'])['state'],'prepared' if known else 'intent')
        self.assertEqual(self.store.worktree('attempt1'),dict(self.intent,state='ready') if known else self.intent)
        self.assertEqual(len(self.store.pending_events()),1 if known else 0)
        self.reopen()
        with patch.object(self.trees,'attach_preparing',side_effect=AssertionError('crash replay')) as git:
            if known:self.assertEqual(self.manager.run(self.r)['state'],'prepared')
            else:
                with self.assertRaisesRegex(ValueError,'^preparing_operation_unknown$'):self.manager.run(self.r)
            git.assert_not_called()
        self.assertEqual(len(self.store.pending_events()),1 if known else 0)
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')

    def test_crash_after_durable_intent_never_replays(self):self.crash_boundary('intent')
    def test_crash_after_git_never_replays(self):self.crash_boundary('git')
    def test_crash_before_atomic_commit_never_replays(self):self.crash_boundary('before_commit')
    def test_crash_inside_atomic_commit_rolls_back_all_records(self):self.crash_boundary('during_commit')
    def test_crash_after_atomic_commit_returns_recorded_result(self):self.crash_boundary('after_commit')

    def test_lost_return_after_commit_reads_known_result(self):
        original=self.store.complete_preparing
        def lost(*args):original(*args);raise RuntimeError('fixture lost return')
        with patch.object(self.store,'complete_preparing',side_effect=lost):result=self.manager.run(self.r)
        self.assertEqual(result['state'],'prepared');self.assertEqual(len(self.store.pending_events()),1)
        self.assertEqual(self.manager.run(self.r),result)

    def test_journal_change_during_git_keeps_resource_and_fence(self):
        original=self.trees.attach_preparing
        def changed(*args):
            tree=original(*args);self.store.update('command1',resource_id='resource1');return tree
        with patch.object(self.trees,'attach_preparing',side_effect=changed):
            with self.assertRaises(ValueError):self.manager.run(self.r)
        self.assertEqual(self.store.command('command1')['resource_id'],'resource1')
        self.assertEqual(self.store.preparing_operation(self.r['operation_id'])['state'],'unknown')
        self.unchanged()


    def test_expired_attach_budget_never_starts_git(self):
        self.store.begin_preparing(self.r)
        with patch.object(self.trees,'inspect_preparing',return_value=self.intent),patch('task_tower.connector.worktrees.time.monotonic',side_effect=[100,111]),patch.object(self.trees,'_git',side_effect=AssertionError('Git after deadline')) as git:
            with self.assertRaisesRegex(ValueError,'^preparing_observation_deadline$'):self.trees.attach_preparing(self.r,self.command)
            git.assert_not_called()

    def test_typed_git_failure_is_retained_with_unknown_fence(self):
        from task_tower.connector.diagnostics import GitFailure
        def failed(*args):return self.git(self.root,'worktree','add','--fixture-invalid-option')
        with patch.object(self.trees,'attach_preparing',side_effect=failed):
            with self.assertRaises(GitFailure) as caught:self.manager.run(self.r)
        self.assertEqual(str(caught.exception),'git_operation_unknown')
        self.assertEqual(self.store.preparing_operation(self.r['operation_id'])['state'],'unknown');self.unchanged()

    def test_dirty_postcondition_never_commits_ready_ack(self):
        original=self.trees.verify_preparing_attachment
        def dirty(*args,**kwargs):
            (self.target/'untracked.txt').write_text('changed\n',encoding='utf-8');return original(*args,**kwargs)
        with patch.object(self.trees,'verify_preparing_attachment',side_effect=dirty):
            with self.assertRaises(ValueError):self.manager.run(self.r)
        self.assertTrue(self.target.exists());self.unchanged()
        self.assertEqual(self.store.preparing_operation(self.r['operation_id'])['state'],'unknown')

if __name__=='__main__':unittest.main()
