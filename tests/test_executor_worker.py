import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid
import copy
import threading
import time
import contextlib
import io
import zipfile
from types import SimpleNamespace
from contextlib import ExitStack
from task_tower import executor_worker as worker

class WorkerTests(unittest.TestCase):
    def test_revoked_authority_prevents_preparation_and_keeps_owner_fenced(self):
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower.executor_queue import ExecutionQueue
        with tempfile.TemporaryDirectory() as raw:
            queue=ExecutionQueue(Path(raw)/'queue.db'); profile={'kind':'custom'}
            receipt=queue.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local'),profile_fingerprint(profile),profile_id='custom')
            with patch.object(worker,'_authorized',return_value=False),patch.object(worker,'prepare_attempt') as prepare:
                result=worker.execute_one(dict(profiles={'custom':profile}),queue)
            self.assertEqual(result['status'],'needs_input'); prepare.assert_not_called()
            self.assertTrue(queue.status(receipt['receipt_id'])['evidence']['no_child_created'])
            self.assertEqual(worker.execute_one(dict(profiles={'custom':profile}),queue)['status'],'idle')

    def test_real_custom_process_worktree_result_and_token_removal(self):
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower.executor_queue import ExecutionQueue
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve(); source=root/'source'; source.mkdir()
            def git(*args): return subprocess.run(['git',*args],cwd=source,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
            git('init'); git('config','user.email','test@example.test'); git('config','user.name','Test')
            (source/'file').write_text('source'); git('add','.'); git('commit','-m','initial')
            pins=root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('instructions\n')
            manifest={'SKILL.md':hashlib.sha256(b'instructions\n').hexdigest()}
            helper=root/'helper.py'
            helper.write_text('import argparse,json,os,pathlib\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--result");a=p.parse_args();r=json.loads(pathlib.Path(a.request).read_text());assert "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ;pathlib.Path("file").write_text("isolated");v={k:r[k] for k in ("run_id","attempt_id","source_sha")};v.update(version=1,status="completed",summary="ok");pathlib.Path(a.result).write_text(json.dumps(v));print("output")\n')
            profile=dict(kind='custom',trusted=True,argv=[str(Path(os.sys.executable).resolve()),str(helper)],checkout=str(source),source_ref=git('rev-parse','HEAD'),runs_dir=str(root/'runs'),superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)),timeout_seconds=10,log_max_bytes=128)
            queue=ExecutionQueue(root/'queue.db')
            request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local')
            receipt=queue.submit(request,profile_fingerprint(profile),profile_id='custom')
            config=dict(profiles={'custom':profile},max_active=2)
            with patch.object(worker,'_authorized',return_value=True),patch.dict(os.environ,{'GH_TOKEN':'secret','GITHUB_TOKEN':'secret'}): report=worker.execute_one(config,queue)
            self.assertEqual(report['status'],'execution_completed')
            self.assertEqual((source/'file').read_text(),'source')
            saved=queue.status(receipt['receipt_id']); self.assertTrue(saved['evidence']['cleanup_confirmed'])
            worktree=next((root/'runs').glob('*/*/worktree'))
            self.assertEqual((worktree/'file').read_text(),'isolated')
            git('worktree','remove','--force',str(worktree))

    def test_prepare_uses_committed_source_and_snapshots_pins(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve(); checkout=root/'source'; checkout.mkdir()
            def git(*args): return subprocess.run(['git',*args],cwd=checkout,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
            git('init'); git('config','user.email','test@example.test'); git('config','user.name','Test')
            (checkout/'file').write_text('committed'); git('add','.'); git('commit','-m','source')
            sha=git('rev-parse','HEAD'); (checkout/'file').write_text('dirty source preserved')
            pins=root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('instructions\n')
            manifest={'SKILL.md':hashlib.sha256(b'instructions\n').hexdigest()}
            from task_tower.executor_profiles import profile_fingerprint
            profile=dict(checkout=str(checkout),source_ref=sha,runs_dir=str(root/'runs'),superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)))
            job=dict(run_id='11111111-1111-4111-8111-111111111111',attempt_id='22222222-2222-4222-8222-222222222222')
            attempt=worker.prepare_attempt(job,profile)
            self.assertEqual(attempt['source_sha'],sha)
            self.assertFalse(Path(attempt['worktree']).exists())
            self.assertEqual((checkout/'file').read_text(),'dirty source preserved')
            self.assertEqual(Path(attempt['instructions_path']).read_text(),'instructions\n')
            with self.assertRaises(ValueError): worker.prepare_attempt(job,profile)
            unsafe=dict(job,attempt_id='../escape')
            with self.assertRaises(ValueError): worker.prepare_attempt(unsafe,profile)

class WorkerFaultTests(unittest.TestCase):
    def setUp(self):
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower.executor_queue import ExecutionQueue
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.source=self.root/'source'; self.source.mkdir()
        self.git('init'); self.git('config','user.email','test@example.test'); self.git('config','user.name','Test')
        (self.source/'file').write_text('source'); self.git('add','.'); self.git('commit','-m','source')
        pins=self.root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('instructions\n')
        manifest={'SKILL.md':hashlib.sha256(b'instructions\n').hexdigest()}
        self.helper=self.root/'helper.py'
        self.helper.write_text('import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--result");a=p.parse_args();r=json.loads(pathlib.Path(a.request).read_text());v={k:r[k] for k in ("run_id","attempt_id","source_sha")};v.update(version=1,status="completed",summary="ok");pathlib.Path(a.result).write_text(json.dumps(v))\n')
        self.profile=dict(kind='custom',trusted=True,approve_for_me=False,repository='Owner/Repo',runner_label='local',argv=[str(Path(os.sys.executable).resolve()),str(self.helper)],checkout=str(self.source),source_ref=self.git('rev-parse','HEAD'),runs_dir=str(self.root/'runs'),superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)),timeout_seconds=5,log_max_bytes=128,max_attempts=2)
        self.queue=ExecutionQueue(self.root/'queue.db')
        request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local')
        self.run=self.queue.submit(request,profile_fingerprint(self.profile),profile_id='custom')['receipt_id']
        self.rows=[dict(number=15,state='open',title='Implement task',body='Issue prose',meta=dict(version=1,kind='task',mode='autonomous',status='open',task_id='TT-15'))]
        case=self
        class Store:
            def list_issues(self): return copy.deepcopy(case.rows)
            def metadata(self,row): return row['meta']
            def get(self,n): return copy.deepcopy(next(r for r in case.rows if r['number']==n))
            def request(self,*args): return case.request_fn(*args)
        self.request_fn=lambda *args:[]
        self.network_source=SimpleNamespace()
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('task_tower.github_tasks.GitHubTasks',side_effect=lambda c:Store()))
        self.stack.enter_context(patch('task_tower.dispatcher._source',return_value=self.network_source))
        connection=SimpleNamespace(repository='Owner/Repo',checkout=self.source,runner_label='local')
        self.config=dict(profiles={'custom':self.profile},allowlist=[dict(repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local',profile='custom')],_connections=[connection],_authority_check=lambda:True)
        self.addCleanup(self.remove_worktrees)
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.source,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.decode().strip()
    def remove_worktrees(self):
        for path in (self.root/'runs').glob('*/*/worktree'):
            self.git('worktree','remove','--force',str(path))
    def execute(self): return worker.execute_one(self.config,self.queue)
    def test_real_selection_path_and_private_task_data(self):
        self.assertEqual(self.execute()['status'],'execution_completed')
        request=json.loads(next((self.root/'runs').glob('*/*/request.json')).read_text())
        self.assertEqual(request['task_data']['body'],'Issue prose')
    def test_closed_issue_prevents_any_worktree(self):
        self.rows[0]['state']='closed'
        self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse((self.root/'runs').exists())
    def test_real_verified_done_rejects_unproved_dependency(self):
        self.rows[0]['meta']['blocked_by']=['Owner/Repo#14']
        self.rows.append(dict(number=14,state='closed',body='',meta=dict(version=1,kind='task',mode='autonomous',status='done',task_id='TT-14')))
        self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse((self.root/'runs').exists())
    def install_dependency_receipt(self):
        self.rows[0]['meta']['blocked_by']=['Owner/Repo#14']
        self.rows.append(dict(number=14,state='closed',body='',meta=dict(version=1,kind='task',mode='autonomous',status='done',task_id='TT-14',remote_attempt=dict(status='done',run_id='41'))))
        bundle=dict(merge_commit='a'*40,task_ids=['TT-14'],platforms=dict(linux='passed'))
        receipt=dict(repository='Owner/Repo',issue=14,run_id='41',run_attempt='1',bundle=bundle,review=dict(verdict='approve',commit='a'*40,task_id='TT-14'),required_platforms=['linux'],policy=dict(reviewer='postmerge-agent',executor='dev',superpowers_sha256='c'*64))
        packed=io.BytesIO()
        with zipfile.ZipFile(packed,'w') as archive: archive.writestr('14.json',json.dumps(receipt))
        raw=packed.getvalue()
        artifact=dict(id=1,name='task-tower-review-14-1',expired=False,digest='sha256:'+hashlib.sha256(raw).hexdigest(),workflow_run=dict(id=41,head_sha='b'*40))
        self.network_source._pages=lambda *args:[artifact]
        self.network_source._get=lambda *args,**kw:raw
        self.network_source._id=lambda n:n
        self.network_source.poll=lambda:[bundle]
        run=dict(status='completed',run_attempt=1,event='workflow_dispatch',head_branch='main',path='.github/workflows/task-tower-project.yml',repository=dict(full_name='Owner/Repo'),head_sha='b'*40)
        self.request_fn=lambda method,path: [] if '/comments?' in path else (run if '/actions/runs/' in path else dict(status='ahead'))
        return artifact
    def test_real_byte_receipt_authorizes_dependency(self):
        self.install_dependency_receipt()
        self.assertEqual(self.execute()['status'],'execution_completed')
    def test_lost_byte_receipt_after_worktree_prevents_launch(self):
        artifact=self.install_dependency_receipt(); original=worker._git
        def git(checkout,*args):
            result=original(checkout,*args)
            if args[:2]==('worktree','add'): artifact['digest']='sha256:forged'
            return result
        with patch.object(worker,'_git',side_effect=git),patch.object(worker,'run_command') as command:
            self.assertEqual(self.execute()['status'],'needs_input'); command.assert_not_called()
    def test_body_changed_after_preparation_prevents_worktree(self):
        original=worker.prepare_attempt
        def prepare(*args):
            result=original(*args); self.rows[0]['body']='changed'; return result
        with patch.object(worker,'prepare_attempt',side_effect=prepare): self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(list((self.root/'runs').glob('*/*/worktree')))
    def test_source_ref_changed_after_prepare_prevents_worktree(self):
        self.profile['source_ref']='refs/heads/approved'; self.git('branch','approved')
        from task_tower.executor_profiles import profile_fingerprint
        self.queue.cancel(self.run)
        self.run=self.queue.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local'),profile_fingerprint(self.profile),profile_id='custom')['receipt_id']
        original=worker.prepare_attempt
        def prepare(*args):
            result=original(*args)
            (self.source/'file').write_text('next'); self.git('add','.'); self.git('commit','-m','next'); self.git('branch','-f','approved','HEAD')
            return result
        with patch.object(worker,'prepare_attempt',side_effect=prepare): self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(list((self.root/'runs').glob('*/*/worktree')))
    def test_policy_revoked_after_worktree_prevents_launch(self):
        calls=0
        def authority():
            nonlocal calls
            calls+=1
            return calls<5
        self.config['_authority_check']=authority
        with patch.object(worker,'run_command') as command:
            self.assertEqual(self.execute()['status'],'needs_input'); command.assert_not_called()
        self.assertTrue(list((self.root/'runs').glob('*/*/worktree')))
    def test_zero_exit_without_result_is_failed(self):
        self.helper.write_text('pass\n')
        self.assertEqual(self.execute()['status'],'failed')
    def test_wrong_attempt_result_is_failed(self):
        self.helper.write_text(self.helper.read_text().replace('status="completed"','attempt_id="wrong",status="completed"'))
        self.assertEqual(self.execute()['status'],'failed')
    def test_cleanup_uncertainty_never_completes(self):
        with patch.object(worker,'run_command',return_value=dict(status='cleanup_failed',exit_code=0,started=True,cleanup_confirmed=False)):
            self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual(self.execute()['status'],'idle')
    def test_durable_intents_precede_external_effects(self):
        original=worker._git
        def git(checkout,*args):
            if args[:2]==('worktree','add'):
                self.assertTrue(self.queue.status(self.run)['evidence']['worktree_intent'])
            return original(checkout,*args)
        command=worker.run_command
        def launch(*args,**kwargs):
            self.assertTrue(self.queue.status(self.run)['evidence']['launch_intent'])
            return command(*args,**kwargs)
        with patch.object(worker,'_git',side_effect=git),patch.object(worker,'run_command',side_effect=launch): self.assertEqual(self.execute()['status'],'execution_completed')
    def test_cancel_after_worktree_prevents_launch(self):
        original=worker._git
        def git(checkout,*args):
            result=original(checkout,*args)
            if args[:2]==('worktree','add'): self.queue.cancel(self.run)
            return result
        with patch.object(worker,'_git',side_effect=git),patch.object(worker,'run_command') as command:
            self.assertEqual(self.execute()['status'],'cancelled'); command.assert_not_called()
    def test_worker_crash_after_launch_intent_cannot_restart(self):
        with patch.object(worker,'run_command',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.execute()
        self.assertEqual(self.queue.status(self.run)['state'],'running')
        self.assertEqual(self.execute()['status'],'idle')
    def test_crash_after_worktree_intent_preserves_claim_without_reexecution(self):
        original=worker._git
        def git(checkout,*args):
            if args[:2]==('worktree','add'): raise KeyboardInterrupt
            return original(checkout,*args)
        with patch.object(worker,'_git',side_effect=git):
            with self.assertRaises(KeyboardInterrupt): self.execute()
        saved=self.queue.status(self.run)
        self.assertEqual(saved['state'],'claimed'); self.assertTrue(saved['evidence']['worktree_intent'])
        self.assertEqual(self.execute()['status'],'idle')
    def test_cancel_after_prepare_prevents_worktree(self):
        original=worker.prepare_attempt
        def prepare(*args):
            result=original(*args); self.queue.cancel(self.run); return result
        with patch.object(worker,'prepare_attempt',side_effect=prepare): self.assertEqual(self.execute()['status'],'cancelled')
        self.assertFalse(list((self.root/'runs').glob('*/*/worktree')))
    def test_unknown_start_fences_without_retry(self):
        with patch.object(worker,'run_command',return_value=dict(status='unknown',exit_code=None,started=False,cleanup_confirmed=True)):
            self.assertEqual(self.execute()['status'],'unknown')
        from task_tower.executor_profiles import profile_fingerprint
        with self.assertRaises(ValueError): self.queue.retry_prelaunch(self.run,profile_fingerprint=profile_fingerprint(self.profile),max_attempts=2)
        self.assertEqual(self.execute()['status'],'idle')
    def test_cancel_during_real_child_has_cleanup_proof(self):
        self.helper.write_text('import pathlib,time\npathlib.Path("started").write_text("yes")\ntime.sleep(30)\n')
        errors=[]
        def cancel():
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if list((self.root/'runs').glob('*/*/worktree/started')):
                    self.queue.cancel(self.run); return
                time.sleep(.01)
            errors.append('child never started')
        thread=threading.Thread(target=cancel); thread.start()
        try: self.assertEqual(self.execute()['status'],'cancelled')
        finally: thread.join(6)
        self.assertFalse(errors)
        evidence=self.queue.status(self.run)['evidence']
        self.assertTrue(evidence['started']); self.assertTrue(evidence['cleanup_confirmed'])
    def test_ref_changed_after_worktree_prevents_launch(self):
        self.profile['source_ref']='refs/heads/approved'
        self.git('branch','approved')
        from task_tower.executor_profiles import profile_fingerprint
        # Re-admit the policy-bound job because changing a saved profile is revocation.
        self.queue.cancel(self.run)
        self.run=self.queue.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-15',runner_label='local'),profile_fingerprint(self.profile),profile_id='custom')['receipt_id']
        original=worker._git
        def git(checkout,*args):
            result=original(checkout,*args)
            if args[:2]==('worktree','add'):
                (self.source/'file').write_text('next'); self.git('add','.'); self.git('commit','-m','next'); self.git('branch','-f','approved','HEAD')
            return result
        with patch.object(worker,'_git',side_effect=git),patch.object(worker,'run_command') as command:
            self.assertEqual(self.execute()['status'],'needs_input'); command.assert_not_called()
    def test_prelaunch_failure_retry_cli_archives_then_new_attempt(self):
        from task_tower.executor import main
        with patch.object(worker,'run_command',return_value=dict(status='unavailable',exit_code=None,started=False,cleanup_confirmed=True)):
            self.assertEqual(self.execute()['status'],'failed')
        config_path=self.root/'config.json'; config_path.write_text(json.dumps(dict(version=1,profiles=self.config['profiles'],allowlist=self.config['allowlist'])))
        connections=self.root/'connections.json'; connections.write_text(json.dumps(dict(version=1,projects=[dict(id='test',repository='Owner/Repo',checkout=str(self.source),runner_label='local')])))
        args=['retry','--connections',str(connections),'--config',str(config_path),'--queue',str(self.queue.path),'--run-id',self.run]
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(main(args),0)
        self.assertEqual(len(self.queue.history(self.run)),1)
        self.assertEqual(self.execute()['status'],'execution_completed')
        self.assertEqual(self.queue.status(self.run)['attempt'],2)
        with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(main(args),2)
