"""Reproduce independent development-review blockers before fixing them."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from tests.test_shared_worker import WorkServer
from task_tower.shared_queue import SharedQueue
from task_tower.shared_worker import SharedWorker


class ReviewBlockerTests(unittest.TestCase):
    def setUp(self):
        admission=patch('task_tower.shared_worker.native_execution_supported',return_value=True)
        admission.start();self.addCleanup(admission.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.source=self.root/'source';self.source.mkdir()
        def git(*args):
            return subprocess.check_output(['git','-C',str(self.source),*args],stderr=subprocess.DEVNULL).decode().strip()
        git('init','-b','main');(self.source/'plan.md').write_text('# Plan\n\n### Task 1: fixture\n')
        git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','prepared')
        self.server=WorkServer(git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}'));self.addCleanup(self.server.close)
        self.skills=self.root/'skills';(self.skills/'executing-plans').mkdir(parents=True)
        (self.skills/'executing-plans/SKILL.md').write_text('Fixture instruction, not native Superpowers evidence')
        self.settings=dict(worker_name='review-fixture',source_checkout=str(self.source),workspace_root=str(self.root/'worker'),
            superpowers_root=str(self.skills),plans={str(n):'plan.md' for n in (1,2,3)},
            harness=dict(kind='custom',trusted=True,argv=[sys.executable,'-c','pass'],timeout_seconds=10,log_max_bytes=65536))
        self.queue=SharedQueue(self.server.store(),str(uuid.uuid4()),allowlist=[dict(repository='owner/repo',issue=n,task_id='TT-SHARED-'+str(n)) for n in (1,2,3)],assignee='operator')

    def test_rejected_private_config_is_never_copied_to_logs(self):
        secret='fixture-sensitive-header-not-a-real-secret'
        with (self.source/'.git/config').open('a') as stream:stream.write('\n[http]\n\textraHeader = Authorization: '+secret+'\n')
        with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        for path in (self.root/'worker').rglob('*.log'):
            self.assertNotIn(secret,path.read_text(errors='replace'))

    def test_credential_bearing_remote_url_is_rejected_without_logging(self):
        secret='fixture-not-a-real-token'
        with (self.source/'.git/config').open('a') as stream:stream.write('\n[remote "origin"]\n\turl = https://user:'+secret+'@github.com/owner/repo.git\n')
        with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        for path in (self.root/'worker').rglob('*.log'):
            self.assertNotIn(secret,path.read_text(errors='replace'))

    def test_harness_drops_inherited_git_controls(self):
        from task_tower.shared_worker import harness_environment
        with patch.dict(os.environ,{'GIT_DIR':'foreign','git_work_tree':'foreign','GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'core.hooksPath','GIT_CONFIG_VALUE_0':'foreign'}):
            env=harness_environment()
        self.assertNotIn('GIT_DIR',env);self.assertNotIn('git_work_tree',env)
        self.assertNotIn('GIT_CONFIG_COUNT',env);self.assertNotIn('GIT_CONFIG_KEY_0',env)
        self.assertNotIn('GIT_CONFIG_VALUE_0',env)

    def test_unknown_cleanup_fences_live_worker_and_restart(self):
        from task_tower.shared_worker import run_command as actual_run
        calls=[]
        def execute(argv,*args,**kwargs):
            if argv[0]==sys.executable:
                calls.append(argv);return dict(status='cleanup_failed',cleanup_confirmed=False,started=True,pid=12345,
                    exit_code=None,stdout_tail_unknown=False,stdout_truncated=False,stderr_tail_unknown=False,stderr_truncated=False)
            return actual_run(argv,*args,**kwargs)
        worker=SharedWorker(self.queue,self.settings)
        with patch('task_tower.shared_worker.run_command',side_effect=execute):
            with self.assertRaises(ValueError):worker.run_once()
            with self.assertRaises(ValueError):worker.run_once()
            with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        self.assertEqual(len(calls),1)
        self.assertEqual(len(self.server.refs),1)

    def test_removed_assignee_blocks_launch_without_releasing_claim(self):
        claim=self.queue.claim(1);self.assertTrue(self.queue.assign(claim))
        self.server.issues[1]['assignees']=[]
        self.assertIsNone(self.queue.start(claim));self.assertEqual(len(self.server.refs),1)

    def test_null_assignee_is_not_a_successful_execution_assignment(self):
        queue=SharedQueue(self.server.store(),str(uuid.uuid4()),allowlist=[dict(repository='owner/repo',issue=1,task_id='TT-SHARED-1')])
        claim=queue.claim(1);self.assertFalse(queue.assign(claim));self.assertIsNone(queue.start(claim))

    def test_workspace_git_unknown_cleanup_fences_restart(self):
        from task_tower.shared_worker import run_command as actual_run
        calls=[]
        def execute(argv,*args,**kwargs):
            if 'clone' in argv:
                calls.append(argv);return dict(status='cleanup_failed',cleanup_confirmed=False,started=True,pid=12345)
            return actual_run(argv,*args,**kwargs)
        worker=SharedWorker(self.queue,self.settings)
        with patch('task_tower.shared_worker.run_command',side_effect=execute):
            with self.assertRaises(ValueError):worker.run_once()
            with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        self.assertEqual(len(calls),1)

    def test_post_harness_git_unknown_cleanup_fences_refill_and_restart(self):
        from task_tower.shared_worker import run_command as actual_run
        completed=[]
        def execute(argv,*args,**kwargs):
            if argv[0]==sys.executable:
                result_path=Path(argv[argv.index('--result')+1])
                result_path.write_text(json.dumps(dict(version=1,status='execution_completed',summary='Fixture only')))
                completed.append(True)
                return dict(status='passed',cleanup_confirmed=True,started=True,pid=12345,exit_code=0,
                    stdout_tail_unknown=False,stdout_truncated=False,stderr_tail_unknown=False,stderr_truncated=False)
            if completed and 'rev-parse' in argv:
                return dict(status='cleanup_failed',cleanup_confirmed=False,started=True,pid=12346)
            return actual_run(argv,*args,**kwargs)
        worker=SharedWorker(self.queue,self.settings)
        with patch('task_tower.shared_worker.run_command',side_effect=execute):
            with self.assertRaises(ValueError):worker.run_once()
            with self.assertRaises(ValueError):worker.run_once()
            with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        self.assertEqual(len(completed),1)

    def test_unsupported_platform_rejects_worker_before_creating_output(self):
        with patch('task_tower.shared_worker.native_execution_supported',return_value=False,create=True):
            with self.assertRaises(ValueError):SharedWorker(self.queue,self.settings)
        self.assertFalse((self.root/'worker').exists())
