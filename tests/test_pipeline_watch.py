import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import unittest
import uuid
from unittest.mock import patch

from task_tower import pipeline
from task_tower.executor_worker import _git
from task_tower.github_tasks import replace_metadata
from tests import test_pipeline_default_source as source_fixture


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.source=source_fixture.DefaultSourceTests();self.source.setUp();self.addCleanup(self.source.doCleanups)
        f=self.source.fixture;self.root=f.root
        Path(f.profile['runs_dir']).mkdir(exist_ok=True)
        f.profile.update(max_attempts=1,approve_for_me=False)
        f.row['checks']=[dict(id='tokens',argv=[str(Path(sys.executable).resolve()),'-c',"import os;assert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)"],timeout_seconds=10)]
        self.connections=self.root/'connections.json';self.executor=self.root/'executor.json'
        self.connections.write_text(json.dumps(dict(version=1,projects=[dict(id='fixture',repository='Owner/Repo',checkout=f.profile['checkout'],runner_label='local',trusted_publishers=['owner'])])))
        self.executor.write_text(json.dumps(dict(version=1,profiles={'local':f.profile},allowlist=f.executor['allowlist'])))
        f.path.write_text(json.dumps(f.value))
        self.args=argparse.Namespace(command='watch',connections=self.connections,config=f.path,executor_config=self.executor,
            journal=self.root/'watch.db',dispatch_config=self.root/'dispatch.json',dispatch_journal=self.root/'dispatch.db')
        backend=dict(argv=pipeline._fixed(self.args,'adapter')+['--request','{request}','--result','{result}'],cwd=str(Path(pipeline.__file__).resolve().parent.parent),timeout_seconds=30)
        self.dispatch=dict(version=1,allowlist=[{k:f.row[k] for k in ('repository','issue','task_id')}],backend=backend,interval_seconds=5)
        self.args.dispatch_config.write_text(json.dumps(self.dispatch))
        self.http=self.root/'http.json';self.http.write_text(json.dumps(dict(sha=f.sha,issues=self.source.issues)))
        fixture_site=Path(__file__).parent/'fixtures/pipeline_http_site'
        self.environment=patch.dict(os.environ,dict(TT_HTTP_FIXTURE=str(self.http),TT_HTTP_REQUIRE_ENV_AUTH='1',PYTHONPATH=str(fixture_site)+os.pathsep+str(Path(pipeline.__file__).resolve().parent.parent),GH_TOKEN='fixture-env-only-private-value',GITHUB_TOKEN='fixture-env-only-private-value'))
        self.environment.start();self.addCleanup(self.environment.stop)
        _,self.journal,self.config=pipeline._runtime(self.args)

    def start(self):
        owner=str(uuid.uuid4());self.journal.claim_controller(owner,self.config['policy_sha256'])
        self.config['_watch']=dict(owner=owner,stop=threading.Event(),workers=[],dispatcher=None,ticks=0,failures=0,next_dispatch=0)
        self.addCleanup(self.stop)

    def stop(self):
        state=self.config.get('_watch')
        if not state:return
        state['stop'].set()
        hosts=[*state['workers']]+([state['dispatcher']] if state['dispatcher'] else [])
        for host in hosts:host.done.wait(5);host.close()
        self.journal.recover()
        self.journal.release_controller(state['owner']);self.config.pop('_watch')

    def until(self,predicate,seconds=180):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            pipeline.watch_tick(self.config,self.journal)
            if predicate():return
            time.sleep(.05)
        self.fail('Watch condition timed out: '+str(self.journal.status()))

    def test_real_dispatch_adapter_to_six_roles_and_host_tests(self):
        self.start()
        self.until(lambda:any(r['state']=='ready_for_pr' for r in self.journal.status()['runs']))
        run=self.journal.status()['runs'][0];history=self.journal.history(run['run_id'])
        self.assertEqual(len([a for a in history['attempts'] if a['role']!='host_check']),6)
        self.assertEqual(len(history['verdicts']),3)
        self.assertEqual(len({a['instance_id'] for a in history['attempts']}),7)
        self.assertEqual(len(pipeline.DeliveryJournal(self.args.dispatch_journal,readonly=True).rows()),1)
        before=self.journal.history(run['run_id']);self.stop();self.start()
        pipeline.watch_tick(self.config,self.journal)
        self.assertTrue(self.config['_watch']['dispatcher'].done.wait(30))
        pipeline.watch_tick(self.config,self.journal)
        self.assertEqual(before,self.journal.history(run['run_id']))
        for path in self.root.rglob('*'):
            if path.is_file() and path.suffix in ('.json','.log','.md'):
                self.assertNotIn(b'fixture-env-only-private-value',path.read_bytes(),str(path))

    def test_slow_source_helper_does_not_block_watch_and_cancels(self):
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'source-started'))
        self.http.write_text(json.dumps(value));self.start()
        self.until(lambda:(self.root/'source-started').exists(),10)
        start=time.monotonic();pipeline.watch_tick(self.config,self.journal)
        self.assertLess(time.monotonic()-start,1)
        host=self.config['_watch']['dispatcher'];host.stop.set();self.assertTrue(host.done.wait(5))
        self.assertLess(time.monotonic()-start,5)
        self.assertEqual(host.outcome['status'],'cancelled')
        self.assertTrue(host.outcome['cleanup_confirmed'])
        self.assertEqual(self.journal.status()['runs'],[])

    def test_shutdown_budget_with_external_sqlite_lock_and_live_owned_helper(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'owned-started'),slow_after_claim=str(self.args.journal))
        self.http.write_text(json.dumps(value));self.start();state=self.config['_watch']
        host=pipeline._Host(self.args,'_action',30,state['stop']);state['workers'].append(host)
        end=time.monotonic()+10
        while not (self.root/'owned-started').exists() and time.monotonic()<end:time.sleep(.05)
        self.assertTrue((self.root/'owned-started').exists())
        self.journal.controller_tick(state['owner'],dict(ticks=0,read_failures=0,workers=1,dispatcher=0))
        lock_marker=self.root/'locked';lock_stop=threading.Event();outcome={}
        code="import sqlite3,sys,time;from pathlib import Path;db=sqlite3.connect(sys.argv[1]);db.execute('BEGIN EXCLUSIVE');Path(sys.argv[2]).write_text('locked');time.sleep(60)"
        def hold():outcome.update(pipeline.processes.run_command([str(Path(sys.executable).resolve()),'-c',code,str(self.args.journal),str(lock_marker)],self.root,30,cancel_requested=lock_stop.is_set))
        holder=threading.Thread(target=hold);holder.start()
        try:
            end=time.monotonic()+10
            while not lock_marker.exists() and time.monotonic()<end:time.sleep(.02)
            self.assertTrue(lock_marker.exists())
            started=time.monotonic();self.assertFalse(pipeline._shutdown(self.config,self.journal,state))
            self.assertLess(time.monotonic()-started,5)
            self.assertTrue(state['stop'].is_set())
        finally:lock_stop.set();holder.join(5);host.done.wait(5)
        self.assertTrue(state['_shutdown_journal_done'].wait(5))
        self.assertTrue(host.outcome['cleanup_confirmed'])
        self.assertEqual(self.journal.controller_health()['owner_id'],state['owner'])
        self.assertFalse(self.journal.controller_health()['health']['stopped'])
        self.journal.recover();self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')

    def test_public_work_interrupt_under_exclusive_lock_stops_first_and_exits_uncertain(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'work-interrupt-started'),slow_after_claim=str(self.args.journal))
        self.http.write_text(json.dumps(value));host=pipeline._Host(self.args,'_action',30,threading.Event())
        end=time.monotonic()+10
        while not (self.root/'work-interrupt-started').exists() and time.monotonic()<end:time.sleep(.02)
        self.assertTrue((self.root/'work-interrupt-started').exists())
        real_done=host.done
        class InterruptOnce:
            raised=False
            def wait(self,timeout=None):
                if not self.raised:self.raised=True;raise KeyboardInterrupt()
                return real_done.wait(timeout)
            def is_set(self):return real_done.is_set()
            def set(self):real_done.set()
        host.done=InterruptOnce()
        locked=self.root/'work-locked';lock_stop=threading.Event()
        code="import sqlite3,sys,time;from pathlib import Path;db=sqlite3.connect(sys.argv[1]);db.execute('BEGIN EXCLUSIVE');Path(sys.argv[2]).write_text('locked');time.sleep(60)"
        holder=threading.Thread(target=lambda:pipeline.processes.run_command([str(Path(sys.executable).resolve()),'-c',code,str(self.args.journal),str(locked)],self.root,30,cancel_requested=lock_stop.is_set));holder.start()
        def existing(args,kind,timeout,stop):host.stop=stop;return host
        try:
            end=time.monotonic()+10
            while not locked.exists() and time.monotonic()<end:time.sleep(.02)
            self.assertTrue(locked.exists());output=io.StringIO();started=time.monotonic()
            with patch('task_tower.pipeline._Host',side_effect=existing),contextlib.redirect_stdout(output):
                exit_code=pipeline.main(['work','--connections',str(self.connections),'--journal',str(self.args.journal),'--config',str(self.args.config),'--executor-config',str(self.executor),'--once'])
            self.assertLess(time.monotonic()-started,5)
            self.assertTrue(host.stop.is_set());self.assertEqual(exit_code,1)
            self.assertEqual(json.loads(output.getvalue())['status'],'unknown')
        finally:lock_stop.set();holder.join(5);host.stop.set();real_done.wait(5);host.close()
        self.assertTrue(host.outcome['cleanup_confirmed'])
        self.journal.recover();self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')

    def test_watch_interrupt_uses_shared_shutdown_budget_and_preserves_unknown(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'watch-started'),slow_after_claim=str(self.args.journal))
        self.http.write_text(json.dumps(value));real_tick=pipeline.watch_tick;interrupted=[]
        def tick(config,journal):
            result=real_tick(config,journal)
            if (self.root/'watch-started').exists() and any(r['owner_id'] for r in journal.status()['runs']):
                interrupted.append(time.monotonic());raise KeyboardInterrupt()
            return result
        with patch('task_tower.pipeline.watch_tick',side_effect=tick):self.assertEqual(pipeline.watch(self.config,self.journal),0)
        self.assertTrue(interrupted);self.assertLess(time.monotonic()-interrupted[0],5)
        self.assertTrue(self.journal.controller_health()['health']['stopped'])
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')

    def test_cancelled_owned_action_is_contained_and_fenced(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'action-started'),slow_after_claim=str(self.args.journal))
        self.http.write_text(json.dumps(value))
        stop=threading.Event();host=pipeline._Host(self.args,'_action',30,stop)
        try:
            end=time.monotonic()+10
            while not (self.root/'action-started').exists() and time.monotonic()<end:time.sleep(.05)
            self.assertTrue((self.root/'action-started').exists())
            self.journal.cancel(receipt['receipt_id'])
            self.assertTrue(host.done.wait(5))
            self.assertTrue(host.outcome['cleanup_confirmed'])
            self.journal.recover()
            self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')
        finally:stop.set();host.done.wait(5);host.close()

    def test_public_work_task_budget_stops_real_blocked_host(self):
        f=self.source.fixture;f.value['task_timeout_seconds']=2;f.path.write_text(json.dumps(f.value))
        _,self.journal,self.config=pipeline._runtime(self.args)
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        value=json.loads(self.http.read_text());value.update(slow=True,started=str(self.root/'budget-started'),slow_after_claim=str(self.args.journal))
        self.http.write_text(json.dumps(value));started=time.monotonic()
        pipeline.work(self.config,self.journal)
        self.assertLess(time.monotonic()-started,5)
        self.assertTrue((self.root/'budget-started').exists())
        run=self.journal.status(receipt['receipt_id'])
        self.assertEqual(run['state'],'unknown')
        self.assertEqual(run['process_count'],0)
        self.assertEqual(self.journal.history(run['run_id'])['attempts'],[])

    def test_status_cancel_inspect_after_profile_revocation_are_readonly(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        self.executor.write_text('{}');self.source.fixture.path.write_text('{}')
        common=['--connections',str(self.connections),'--journal',str(self.args.journal)]
        before=self.args.journal.read_bytes();files=set(self.root.rglob('*'))
        for command in ('status','reconcile'):
            argv=[command,*common,'--run-id',receipt['receipt_id']]+(['--inspect'] if command=='reconcile' else [])
            output=io.StringIO()
            with contextlib.redirect_stdout(output):self.assertEqual(pipeline.main(argv),0)
            self.assertNotIn('checkout',output.getvalue())
            self.assertEqual(self.args.journal.read_bytes(),before)
            self.assertEqual(set(self.root.rglob('*')),files)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(pipeline.main(['cancel',*common,'--run-id',receipt['receipt_id']]),0)
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'cancelled')

    def test_clean_dead_ready_run_cancels_after_profile_revocation(self):
        task=self.config['tasks'][0]
        receipt=pipeline.adapter(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),self.config,self.journal)
        self.assertEqual(pipeline.work(self.config,self.journal)['status'],'ready')
        self.executor.write_text('{}');self.source.fixture.path.write_text('{}')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pipeline.main(['cancel','--connections',str(self.connections),'--journal',str(self.args.journal),'--run-id',receipt['receipt_id']]),0)
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'cancelled')

    def test_backend_redirection_and_aliases_are_rejected(self):
        backend=self.dispatch['backend'];backend['argv'][backend['argv'].index('adapter')]='executor'
        self.args.dispatch_config.write_text(json.dumps(self.dispatch))
        with self.assertRaises(ValueError):pipeline._runtime(self.args)

    def test_read_failure_backoff_is_exact_and_never_submits(self):
        value=json.loads(self.http.read_text());value['unavailable']=True;self.http.write_text(json.dumps(value))
        host=pipeline._Host(self.args,'_dispatch',30,threading.Event())
        try:
            self.assertTrue(host.done.wait(30));self.assertTrue(host.result['read_failure'])
            self.assertEqual(pipeline.DeliveryJournal(self.args.dispatch_journal,readonly=True).rows(),[])
            self.assertEqual(self.journal.status()['runs'],[])
        finally:host.close()
        self.start();state=self.config['_watch']
        class Finished:
            result=dict(read_failure=True)
            done=threading.Event()
            def close(self):pass
        Finished.done.set()
        for index,delay in enumerate((5,10,20,40,60,60),1):
            state['dispatcher']=Finished()
            with patch('task_tower.pipeline.time.monotonic',return_value=100):pipeline.watch_tick(self.config,self.journal)
            self.assertEqual(state['failures'],index);self.assertEqual(state['next_dispatch'],100+delay)
        Finished.result=dict(read_failure=False);state['dispatcher']=Finished()
        with patch('task_tower.pipeline.time.monotonic',return_value=100):pipeline.watch_tick(self.config,self.journal)
        self.assertEqual(state['failures'],0);self.assertEqual(state['next_dispatch'],105)

    def test_dependency_claim_without_real_receipt_never_admitted(self):
        value=json.loads(self.http.read_text())
        meta=dict(version=1,kind='task',mode='autonomous',task_id=self.source.fixture.row['task_id'],status='open',blocked_by=['Owner/Repo#17'])
        value['issues'][0]['body']=replace_metadata('Build from installed policy',meta)
        value['issues'].append(dict(number=17,id=124,state='closed',title='Unverified',body=replace_metadata('Says done',dict(version=1,kind='task',mode='autonomous',task_id='TT-DEPENDENCY-001',status='done'))))
        self.http.write_text(json.dumps(value))
        host=pipeline._Host(self.args,'_dispatch',30,threading.Event())
        try:
            self.assertTrue(host.done.wait(30));self.assertIsNotNone(host.result)
            self.assertEqual(self.journal.status()['runs'],[])
            self.assertEqual(pipeline.DeliveryJournal(self.args.dispatch_journal,readonly=True).rows(),[])
        finally:host.close()

    def test_stripped_host_tokens_cannot_pass_via_keyring_fallback(self):
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        result=self.root/'stripped-host-result.json'
        argv=pipeline._fixed(self.args,'_dispatch')+['--host-result',str(result)]
        outcome=pipeline.processes.run_command(argv,Path(pipeline.__file__).resolve().parent.parent,30,env=env,cancel_requested=lambda:False)
        self.assertEqual(outcome['status'],'passed')
        self.assertTrue(json.loads(result.read_text())['read_failure'])
        self.assertEqual(self.journal.status()['runs'],[])
        self.assertEqual(pipeline.DeliveryJournal(self.args.dispatch_journal,readonly=True).rows(),[])

    def test_two_real_slots_clean_blocker_automatic_refill_and_unknown_retention(self):
        f=self.source.fixture
        profile=f.profile;profile['argv'][1]=str(Path(__file__).parent.resolve()/'fixtures/pipeline_watch_role.py')
        checkout2=self.root/'checkout2';_git(profile['checkout'],'clone',profile['checkout'],str(checkout2))
        runs2=self.root/'runs2';runs2.mkdir()
        profile2=copy.deepcopy(profile);profile2.update(repository='Owner/Repo2',checkout=str(checkout2),runs_dir=str(runs2))
        connection=json.loads(self.connections.read_text());connection['projects'].append(dict(id='second',repository='Owner/Repo2',checkout=str(checkout2),runner_label='local',trusted_publishers=['owner']))
        self.connections.write_text(json.dumps(connection))
        nexttask=copy.deepcopy(f.row);nexttask.update(issue=17,task_id='TT-REFILL-001')
        second=copy.deepcopy(f.row);second.update(repository='Owner/Repo2',executor_profile='second',task_id='TT-SECOND-001')
        value=copy.deepcopy(f.value);value['tasks']=[f.row,nexttask,second];f.path.write_text(json.dumps(value))
        allow=[dict(repository=t['repository'],issue=t['issue'],task_id=t['task_id'],runner_label='local',profile=t['executor_profile']) for t in value['tasks']]
        self.executor.write_text(json.dumps(dict(version=1,profiles={'local':profile,'second':profile2},allowlist=allow)))
        self.dispatch['allowlist']=[{k:t[k] for k in ('repository','issue','task_id')} for t in value['tasks']];self.args.dispatch_config.write_text(json.dumps(self.dispatch))
        def issue(number,task,mode):return dict(number=number,id=100+number,state='open',title='Fixture '+task,fixture_mode=mode,body=replace_metadata('Bounded fixture',dict(version=1,kind='task',mode='autonomous',task_id=task,status='open')))
        http=dict(sha=f.sha,issues=[issue(16,f.row['task_id'],'no_result'),issue(17,nexttask['task_id'],'sleep')],issues_by_repository={'repo2':[issue(16,second['task_id'],'sleep')]})
        self.http.write_text(json.dumps(http));_,self.journal,self.config=pipeline._runtime(self.args)
        self.start();maximum=0
        def filled():
            nonlocal maximum
            rows=self.journal.status()['runs'];maximum=max(maximum,sum(r['state'] in pipeline.ACTIVE for r in rows))
            self.assertLessEqual(maximum,2)
            return len(rows)==3 and sum(r['state']=='executing' for r in rows)==2 and any(r['state']=='needs_input' for r in rows)
        self.until(filled)
        self.assertEqual(maximum,2)
        self.stop();rows=self.journal.status()['runs']
        self.assertEqual(sum(r['state']=='unknown' for r in rows),2)
        before={r['run_id']:len(self.journal.history(r['run_id'])['attempts']) for r in rows}
        pipeline.work(self.config,self.journal)
        self.assertEqual(before,{r['run_id']:len(self.journal.history(r['run_id'])['attempts']) for r in rows})

    def test_public_work_contains_blocked_git_descendant_and_no_replay(self):
        f=self.source.fixture
        f.row['publish']['enabled']=True;f.path.write_text(json.dumps(f.value))
        _git(f.profile['checkout'],'remote','add','origin','https://github.com/Owner/Repo.git')
        _,self.journal,self.config=pipeline._runtime(self.args)
        # Use actual default API factories, stop precisely between actions.
        admission=pipeline._Host(self.args,'_dispatch',30,threading.Event())
        self.assertTrue(admission.done.wait(30));self.assertFalse(admission.result['operational_failure']);admission.close()
        for _ in range(25):
            pipeline.work(self.config,self.journal)
            run=self.journal.status()['runs'][0]
            if len(self.journal.history(run['run_id'])['verdicts'])==3:break
        self.assertEqual(len(self.journal.history(run['run_id'])['verdicts']),3)
        remote=self.root/'remote.git';_git(f.profile['checkout'],'init','--bare',str(remote))
        value=json.loads(self.http.read_text());value.update(block_git=True,block_git_command='push',remote=str(remote),git_started=str(self.root/'git-started'))
        self.http.write_text(json.dumps(value))
        # First publication action is the final local evidence commit.
        pipeline.work(self.config,self.journal)
        # The public work command itself must supply containment, without watch.
        from task_tower import processes
        argv=pipeline._fixed(self.args,'work')+['--once']
        result={}
        def invoke():result.update(processes.run_command(argv,Path(pipeline.__file__).resolve().parent.parent,30,cancel_requested=lambda:False))
        thread=threading.Thread(target=invoke);thread.start()
        end=time.monotonic()+15
        while not (self.root/'git-started').exists() and time.monotonic()<end:time.sleep(.05)
        self.assertTrue((self.root/'git-started').exists())
        run=self.journal.status()['runs'][0];self.journal.cancel(run['run_id'])
        thread.join(5);self.assertFalse(thread.is_alive())
        self.journal.recover();run=self.journal.status(run['run_id'])
        self.assertEqual(run['state'],'unknown')
        self.assertEqual(self.journal.history(run['run_id'])['effects'][-1]['status'],'intent')
        from task_tower.executor_queue import _dead
        self.assertTrue(_dead(int((self.root/'git-started').read_text())))
        before=self.journal.history(run['run_id'])
        pipeline.work(self.config,self.journal)
        self.assertEqual(before,self.journal.history(run['run_id']))

    def accepted_publication(self):
        # Debug branch only: observe actual helpers without changing decisions.
        observations=[]
        runner=pipeline.processes.run_command
        cancelled=pipeline._Host.cancelled
        close=pipeline._Host.close
        def invoke(argv,*args,**kwargs):
            if '--host-result' in argv:
                directory=Path(argv[argv.index('--host-result')+1]).parent/'diagnostic-streams'
                directory.mkdir()
                kwargs['capture']=dict(directory=directory,max_bytes_per_stream=65536)
            return runner(argv,*args,**kwargs)
        def observe_cancel(host):
            try:return cancelled(host)
            except Exception:
                if len(observations)<64:
                    observations.append(dict(kind='callback_exception',owner=host.owner,trace=traceback.format_exc()))
                raise
        def observe_close(host):
            entry=dict(kind='host',owner=host.owner,outcome=host.outcome,result=host.result)
            for name in ('stdout','stderr'):
                path=host.path.parent/'diagnostic-streams'/(name+'.log')
                try:entry[name]=path.read_bytes()[:16384].decode('utf-8','backslashreplace')
                except OSError as error:entry[name]=dict(read_error=type(error).__name__)
            if len(observations)<64:observations.append(entry)
            return close(host)
        with patch.object(pipeline.processes,'run_command',invoke),patch.object(pipeline._Host,'cancelled',observe_cancel),patch.object(pipeline._Host,'close',observe_close):
            try:return self._accepted_publication()
            except BaseException as error:
                diagnostic=dict(label='debug_fixture_only_publication_failure',helpers=observations)
                try:
                    rows=self.journal.status()['runs']
                    diagnostic['runs']=rows
                    diagnostic['histories']=[self.journal.history(row['run_id']) for row in rows]
                except Exception as read_error:
                    diagnostic['journal_read_error']=dict(type=type(read_error).__name__,message=str(read_error))
                text=json.dumps(diagnostic,sort_keys=True,default=str)
                error.add_note(text.replace('fixture-env-only-private-value','[fixture token redacted]'))
                raise

    def _accepted_publication(self):
        f=self.source.fixture;f.row['publish']['enabled']=True;f.path.write_text(json.dumps(f.value))
        _git(f.profile['checkout'],'remote','add','origin','https://github.com/Owner/Repo.git')
        remote=self.root/'remote.git';_git(f.profile['checkout'],'init','--bare',str(remote))
        value=json.loads(self.http.read_text());value.update(remote=str(remote),prs=str(self.root/'prs.json'))
        self.http.write_text(json.dumps(value));_,self.journal,self.config=pipeline._runtime(self.args)
        host=pipeline._Host(self.args,'_dispatch',30,threading.Event())
        self.assertTrue(host.done.wait(30));self.assertFalse(host.result['operational_failure']);host.close()
        for _ in range(25):
            pipeline.work(self.config,self.journal);run=self.journal.status()['runs'][0]
            self.assertNotIn(run['state'],('unknown','needs_input','timed_out'))
            if len(self.journal.history(run['run_id'])['verdicts'])==3:return run
        self.fail('Three actual independent stages not accepted')

    def test_distinct_worker_processes_commit_push_and_create_one_pr(self):
        run=self.accepted_publication();owners=[]
        checkpoint=run['manifest']['checkpoint_sha']
        for expected in ('ready','ready','awaiting_pr'):
            result=pipeline.work(self.config,self.journal);self.assertEqual(result['status'],expected)
            run=self.journal.status(run['run_id']);owners.append(run['owner_id'])
        self.assertEqual(len(set(owners)),3)
        self.assertNotEqual(run['checkpoint_sha'],checkpoint)
        rows=json.loads((self.root/'prs.json').read_text());self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['head']['sha'],run['checkpoint_sha'])
        history=self.journal.history(run['run_id'])
        self.assertEqual([e['status'] for e in history['effects'][-3:]],['completed']*3)
        pipeline.work(self.config,self.journal)
        self.assertEqual(history,self.journal.history(run['run_id']))

    def test_lost_pr_response_is_unknown_and_restart_never_posts_again(self):
        run=self.accepted_publication()
        pipeline.work(self.config,self.journal);pipeline.work(self.config,self.journal)
        value=json.loads(self.http.read_text());value['lost_post']=True;self.http.write_text(json.dumps(value))
        self.assertEqual(pipeline.work(self.config,self.journal)['status'],'unknown')
        before=self.journal.history(run['run_id'])
        self.assertEqual(before['effects'][-1]['status'],'unknown')
        pipeline.work(self.config,self.journal)
        self.assertEqual(len(json.loads((self.root/'prs.json').read_text())),1)
        self.assertEqual(before,self.journal.history(run['run_id']))


if __name__=='__main__':unittest.main()
