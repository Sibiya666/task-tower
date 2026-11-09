"""Preserved approved B2 preflight tests; not part of B1."""
from pathlib import Path
import unittest
import tempfile
import stat
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from task_tower import preparing_recovery as recovery
from tests.fixtures.preparing_recovery import GitCase,receipt

class PreparingPreflightTests(GitCase):
    def setUp(self):
        super().setUp()
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.worktrees import Worktrees
        self.transport=tempfile.TemporaryDirectory();self.addCleanup(self.transport.cleanup)
        self.store=ConnectorStore(Path(self.transport.name)/'journal','fixture-'+uuid.uuid4().hex)
        self.addCleanup(self.store.close)
        self.tree_root=Path(self.transport.name)/'trees'
        self.trees=Worktrees({'project1':dict(repository=str(self.root),worktree_root=str(self.tree_root))},self.store)
        self.command=dict(version=1,kind='execute',command_id='command1',attempt_id='attempt1',
            project_id='project1',base_sha=self.head,input={'text':'original approved task'},
            source=dict(base_sha=self.head,head_sha=self.head,diff=''))
        self.store.receive(self.command);self.store.update('command1',phase='needs_reconciliation')
        self.r=dict(receipt(),connector_id=self.store.connector_id,base_sha=self.head,branch_sha=self.head)
        self.target=self.tree_root/'attempt1'
        self.intent=dict(project_id='project1',path=str(self.target),branch=self.r['branch'],
            base_sha=self.head,state='preparing',review=False)
        self.store.save_worktree('attempt1',self.intent)
        self.r.update(command_sha256=recovery.fingerprint(self.command),worktree_sha256=recovery.fingerprint(self.intent))
        self.git(self.root,'branch',self.r['branch'],self.head)

    def inspect(self):return self.trees.inspect_preparing(self.r,self.command)

    def test_known_partial_branch_is_observed_without_mutation(self):
        before=self.git(self.root,'worktree','list','--porcelain','-z',raw=True)
        self.assertEqual(self.inspect(),self.intent)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.store.worktree('attempt1'),self.intent)
        self.assertEqual(self.store.command('command1')['phase'],'needs_reconciliation')
        self.assertEqual(self.git(self.root,'worktree','list','--porcelain','-z',raw=True),before)

    def test_wrong_command_intent_or_connector_denies_before_git(self):
        for field,value in (('command_sha256','4'*64),('worktree_sha256','4'*64),('connector_id','foreign'),('native_owner','foreign')):
            original=self.r[field];self.r[field]=value
            with self.subTest(field=field),patch.object(self.trees,'_git',side_effect=AssertionError('unexpected Git')),self.assertRaises(ValueError):self.inspect()
            self.r[field]=original

    def test_any_executor_or_cleanup_uncertainty_denies_before_git(self):
        for changes in ({'thread_id':'thread1'},{'turn_id':'turn1'},{'resource_id':'resource1'},
                        {'cleanup_resources':['resource1']},{'cleanup_confirmed':False},{'phase':'executing'}):
            with self.subTest(changes=changes):
                prior=self.store.command('command1')
                self.store.update('command1',**changes)
                with patch.object(self.trees,'_git',side_effect=AssertionError('unexpected Git')),self.assertRaises(ValueError):self.inspect()
                with self.store.lock,self.store.db:self.store._save(prior)

    def test_ready_or_altered_journal_is_not_preparing_recovery(self):
        for changes in ({'state':'ready'},{'review':True},{'base_sha':'f'*40},{'path':str(self.root)}):
            with self.subTest(changes=changes):
                self.store.save_worktree('attempt1',dict(self.intent,**changes))
                with self.assertRaises(ValueError):self.inspect()
                self.store.save_worktree('attempt1',self.intent)

    def test_extra_command_or_pending_own_event_denies(self):
        self.store.receive(dict(self.command,command_id='command2'))
        with self.assertRaises(ValueError):self.inspect()

    def test_pending_own_event_denies_but_unrelated_event_does_not(self):
        other=self.store.lifecycle_event('other-attempt','failed',command_id='other-command')
        self.assertEqual(self.inspect(),self.intent)
        own=self.store.lifecycle_event('attempt1','failed',command_id='command1')
        with self.assertRaises(ValueError):self.inspect()
        self.assertEqual(len(self.store.pending_events()),2)

    def test_existing_target_and_foreign_branch_registration_deny(self):
        self.target.mkdir(parents=True)
        with self.assertRaises(ValueError):self.inspect()
        self.target.rmdir()
        foreign=Path(self.transport.name)/'foreign registration'
        self.git(self.root,'worktree','add',str(foreign),self.r['branch'])
        with self.assertRaises(ValueError):self.inspect()

    def test_dirty_repository_and_moved_ref_deny(self):
        path=self.root/'next.txt';path.write_text('next\n',encoding='utf-8')
        with self.assertRaises(ValueError):self.inspect()
        self.git(self.root,'add','next.txt');self.git(self.root,'-c','commit.gpgsign=false','commit','-qm','next')
        self.git(self.root,'update-ref','refs/heads/'+self.r['branch'],self.git(self.root,'rev-parse','HEAD'),self.head)
        with self.assertRaises(ValueError):self.inspect()

    def test_git_failure_is_never_a_negative_lookup(self):
        with patch.object(self.trees,'_git',side_effect=ValueError('git_operation_unknown')),self.assertRaises(ValueError):self.inspect()

    def test_unknown_start_metadata_is_not_proof_of_no_execution(self):
        self.store.update('command1',start_request_id='unreported-start')
        with self.assertRaises(ValueError):self.inspect()

    def test_empty_git_registration_report_is_unknown_not_absent(self):
        original=self.trees._git
        def observed(repo,*args,**kwargs):
            if args==('worktree','list','--porcelain','-z'):return ''
            return original(repo,*args,**kwargs)
        with patch.object(self.trees,'_git',side_effect=observed),self.assertRaises(ValueError):self.inspect()


    def test_index_flags_cannot_hide_dirty_project_source(self):
        for flag in ('--assume-unchanged','--skip-worktree'):
            with self.subTest(flag=flag):
                self.git(self.root,'update-index',flag,'task_tower/preparing_recovery.py')
                self.module.write_text('# hidden project changes\n',encoding='utf-8')
                try:
                    self.assertEqual(self.git(self.root,'status','--porcelain'),'')
                    with self.assertRaises(ValueError):self.inspect()
                finally:
                    self.module.write_text('# disposable source\n',encoding='utf-8')
                    self.git(self.root,'update-index','--no-assume-unchanged','--no-skip-worktree','task_tower/preparing_recovery.py')

    def test_incomplete_registration_is_not_proof_of_absence(self):
        raw=self.git(self.root,'worktree','list','--porcelain','-z',raw=True)
        original=self.trees._git
        for report in (raw[:-1],'worktree '+str(self.root.resolve())+'\0\0',
                       raw.replace('HEAD '+self.head,'HEAD invalid',1),
                       raw[:raw.index('branch ')]+ 'branch refs/heads/\0\0'):
            def observed(repo,*args,**kwargs):
                return report if args==('worktree','list','--porcelain','-z') else original(repo,*args,**kwargs)
            with self.subTest(report=report),patch.object(self.trees,'_git',side_effect=observed):
                with self.assertRaises(ValueError):self.inspect()


    def test_malformed_cleanup_confirmation_is_unknown(self):
        original=self.store.command('command1')
        for value in (0,1,'yes',{}):
            with self.subTest(value=value):
                self.store.update('command1',cleanup_confirmed=value)
                try:
                    with self.assertRaises(ValueError):self.inspect()
                finally:
                    with self.store.lock,self.store.db:self.store._save(original)


    def test_link_or_stat_error_is_not_target_absence(self):
        self.assertFalse(self.target.exists())
        original=Path.lstat
        for failure in ('link','permission'):
            def observed(path,*args,**kwargs):
                if path==self.target:
                    if failure=='permission':raise PermissionError('fixture unavailable')
                    return SimpleNamespace(st_mode=stat.S_IFLNK,st_file_attributes=0)
                return original(path,*args,**kwargs)
            with self.subTest(failure=failure),patch.object(Path,'lstat',observed),patch.object(self.trees,'_git') as git:
                with self.assertRaises((ValueError,OSError)):self.inspect()
                git.assert_not_called()
            self.assertEqual(self.store.worktree('attempt1'),self.intent)

    def test_git_observations_share_one_deadline(self):
        with patch('task_tower.connector.worktrees.time.monotonic',side_effect=[100,100.1,111]),patch.object(self.trees,'_git',return_value=str(self.root)) as git:
            with self.assertRaisesRegex(ValueError,'^preparing_observation_deadline$'):self.inspect()
        self.assertEqual(git.call_count,1)



if __name__=='__main__':unittest.main()
