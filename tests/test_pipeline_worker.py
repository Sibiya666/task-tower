import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
from task_tower import pipeline_worker as worker
from task_tower.pipeline_inputs import digest_manifest
from task_tower.pipeline_journal import PipelineJournal
from tests import test_pipeline_policy as policy_fixture


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=policy_fixture.PipelinePolicyTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        self.control=f.root/'control.json'; self.control.write_text('{}')
        script=f.root/'role.py'
        script.write_text('''import argparse,json\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args()\nr=json.loads(Path(a.request).read_text()); c=json.loads(Path(%r).read_text())\nif c.get('sleep_seconds'):\n Path(a.request).with_name('started').write_text('started')\n import time;time.sleep(c['sleep_seconds'])\nif c.get('mutate_spec_role')==r['role']:\n (Path(r['worktree'])/r['host_task_policy'][c.get('mutate_artifact','spec_path')]).write_text('changed accepted spec')\nif c.get('mutate_role')==r['role']:\n q=Path(r['worktree'])/'src/mutated.py';q.parent.mkdir(exist_ok=True);q.write_text('mutated')\nv=dict(version=2,**r['binding'],summary='fixture')\nif r['role'].endswith('_reviewer'): v.update(verdict=c.get('verdict','approve'),return_stage=c.get('return_stage'),findings=[])\nelse: v['status']='completed'\nPath(a.result).write_text(json.dumps(v))\n''' % str(self.control),encoding='utf-8')
        pins=Path(f.profile['superpowers']['root']); manifest={}
        for name in ('using-superpowers','brainstorming','writing-plans','test-driven-development','verification-before-completion','requesting-code-review'):
            p=pins/name/'SKILL.md';p.parent.mkdir();p.write_bytes(b'rules');manifest[name+'/SKILL.md']=hashlib.sha256(b'rules').hexdigest()
        f.profile['superpowers'].update(manifest=manifest,manifest_sha256=digest_manifest(manifest))
        f.profile.update(kind='custom',trusted=True,argv=[str(Path(sys.executable).resolve()),str(script)],runs_dir=str(f.root/'runs'))
        check_code="import json;from pathlib import Path;c=json.loads(Path("+repr(str(self.control))+").read_text());p=Path('src/mutated.py');p.parent.mkdir(exist_ok=True) if c.get('host_mutation') else None;p.write_text('host mutation') if c.get('host_mutation') else None;assert 2+2==4"
        f.row['checks']=[dict(id='unit',argv=[str(Path(sys.executable).resolve()),'-c',check_code],timeout_seconds=20)]
        from task_tower.executor_worker import _git
        checkout=Path(f.profile['checkout'])
        for name in ('spec_path','plan_path'):
            p=checkout/f.row[name];p.parent.mkdir(exist_ok=True);p.write_text(name,encoding='utf-8')
        _git(checkout,'add','docs');_git(checkout,'-c','user.name=Fixture','-c','user.email=f@example.invalid','commit','-m','artifacts')
        f.sha=_git(checkout,'rev-parse','HEAD')
        self.config=f.load();self.journal=PipelineJournal(f.root/'pipeline.db',checkouts=(checkout,));self.owner=str(uuid.uuid4())
        task=self.config['tasks'][0]
        envelope=dict(profile_id='local',profile_fingerprint=digest_manifest(f.profile),policy_sha256=self.config['policy_sha256'],component_keys=['core'],limits={k:self.config[k] for k in ('task_timeout_seconds','max_processes','max_reworks','role_timeout_seconds','log_max_bytes')})
        self.run_id=self.journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),envelope)['receipt_id']
        self.snapshot_patch=patch('task_tower.dispatch_selection.collect_snapshot',side_effect=lambda c:f.snapshot());self.snapshot_patch.start();self.addCleanup(self.snapshot_patch.stop)

    def tick(self): return worker.step(self.config,self.journal,owner_id=self.owner)
    def state(self): return self.journal.status(self.run_id)
    def until(self,predicate,limit=30):
        for _ in range(limit):
            if predicate(self.state(),self.journal.history(self.run_id)):return
            self.tick()
        self.fail('controller did not reach requested durable state: '+str(self.state()))

    def test_six_roles_in_order_with_receipt_bindings(self):
        self.until(lambda r,h:r['state']=='ready' and worker.next_action(r,h)=='publish')
        h=self.journal.history(self.run_id)
        self.assertEqual([a['role'] for a in h['attempts'] if a['role']!='host_check'],['spec_executor','spec_reviewer','development_executor','development_reviewer','test_executor','test_reviewer'])
        self.assertEqual(len({a['instance_id'] for a in h['attempts']}),7)
        self.assertEqual([v['decision'] for v in h['verdicts']],['approve']*3)
        blocked=self.tick();self.assertEqual(blocked['status'],'ready');self.assertEqual(blocked['reason'],'environment_unavailable')
        for v in h['verdicts']:
            self.assertEqual(v['input_sha256'],digest_manifest(v['body']['manifest']))
            self.assertNotEqual(v['executor_instance_id'],v['reviewer_instance_id'])

    def test_forged_card_or_model_completed_cannot_advance(self):
        self.tick();r=self.state();h=self.journal.history(self.run_id)
        self.assertEqual(worker.next_action(dict(r,state='ready'),h),'spec_executor')
        fake=dict(status='completed',result=dict(verdict='approve'))
        with self.assertRaises(ValueError):worker.apply_verdict(self.config,r,{},fake,self.journal,self.owner)
        self.assertEqual(self.journal.history(self.run_id)['verdicts'],[])

    def test_reject_targets_invalidate_downstream_and_keep_history(self):
        self.until(lambda r,h:r['stage']=='development' and any(a['role']=='development_executor' for a in h['attempts']))
        self.control.write_text(json.dumps(dict(verdict='reject',return_stage='spec')))
        self.until(lambda r,h:r['reworks']['spec']==1)
        h=self.journal.history(self.run_id)
        self.assertTrue(all(v['superseded'] for v in h['verdicts']))
        self.assertEqual(h['verdicts'][-1]['decision'],'reject')
        self.control.write_text('{}');self.until(lambda r,h:r['state']=='ready' and worker.next_action(r,h)=='publish')
        self.assertEqual(len([a for a in self.journal.history(self.run_id)['attempts'] if a['role']=='spec_executor']),2)

    def test_two_returns_then_third_parks(self):
        self.control.write_text(json.dumps(dict(verdict='reject',return_stage='spec')))
        self.until(lambda r,h:r['state']=='needs_input')
        self.assertEqual(self.state()['reason'],'rework_limit');self.assertEqual(self.state()['reworks']['spec'],3)

    def test_stale_source_policy_or_main_never_accepts(self):
        self.until(lambda r,h:worker.next_action(r,h)=='spec_reviewer')
        self.fixture.sha='b'*40
        self.tick();self.assertEqual(self.state()['state'],'needs_input');self.assertEqual(self.journal.history(self.run_id)['verdicts'],[])

    def test_ready_restart_does_not_repeat_completed_role(self):
        self.until(lambda r,h:worker.next_action(r,h)=='spec_reviewer')
        before=len(self.journal.history(self.run_id)['attempts']);self.tick()
        self.assertEqual(len(self.journal.history(self.run_id)['attempts']),before+1)
        self.assertEqual(self.journal.history(self.run_id)['attempts'][-1]['role'],'spec_reviewer')

    def test_cancel_timeout_and_process_budget(self):
        self.tick();self.journal.cancel(self.run_id);self.tick();self.assertEqual(self.state()['state'],'cancelled')

    def test_started_unknown_cannot_rework(self):
        self.tick();r=self.state()
        r=worker._record(self.journal,r,self.owner,state='executing')
        self.journal.begin_attempt(self.run_id,self.owner,dict(role='spec_executor',manifest=r['manifest'],artifact_names={}))
        before=self.state()['process_count'];self.tick()
        self.assertEqual(self.state()['state'],'unknown');self.assertEqual(self.state()['process_count'],before)

    def test_real_git_preparation_binds_exact_identity(self):
        self.tick();r=self.state()
        from task_tower.executor_worker import _git
        self.assertEqual(Path(_git(r['worktree'],'rev-parse','--absolute-git-dir')).resolve(),Path(r['git_dir']).resolve())
        effects=self.journal.history(self.run_id)['effects'];self.assertEqual(effects[0]['kind'],'worktree_create');self.assertEqual(effects[0]['status'],'completed')
        self.assertEqual(effects[0]['intent']['git_dir'],r['git_dir'])

    def test_actual_dirty_product_parks_without_fabricating_checkpoint(self):
        self.until(lambda r,h:worker.next_action(r,h)=='spec_reviewer')
        r=self.state();old=r['manifest'];(Path(r['worktree'])/'docs/spec.md').write_text('external mutation')
        self.tick();r=self.state()
        self.assertEqual(r['state'],'needs_input');self.assertEqual(r['manifest'],old)
        self.assertEqual(self.journal.history(self.run_id)['verdicts'],[])

    def test_worktree_collision_has_no_creation_intent(self):
        run=self.state();p=Path(self.fixture.profile['runs_dir'])/run['run_id']/('pipeline-'+run['run_id'])
        p.mkdir(parents=True);(p/'preserve').write_text('existing')
        self.tick();self.assertEqual(self.state()['reason'],'conflict')
        self.assertEqual(self.journal.history(self.run_id)['effects'],[]);self.assertEqual((p/'preserve').read_text(),'existing')

    def test_crash_after_worktree_intent_never_replays_creation(self):
        original=worker._git
        def crashing(root,*args):
            if 'add' in args and 'worktree' in args:raise KeyboardInterrupt('simulated death')
            return original(root,*args)
        with patch.object(worker,'_git',side_effect=crashing),self.assertRaises(KeyboardInterrupt):self.tick()
        self.assertEqual(self.journal.history(self.run_id)['effects'][0]['status'],'intent')
        self.tick();self.assertEqual(self.state()['state'],'unknown')
        self.assertEqual(len(self.journal.history(self.run_id)['effects']),1)

    def test_completed_checkpoint_recovery_does_not_create_second_commit(self):
        self.tick();self.tick()
        original=worker._record
        def crashing(journal,run,owner,**changes):
            if changes['state']=='ready':raise KeyboardInterrupt('after checkpoint')
            return original(journal,run,owner,**changes)
        with patch.object(worker,'_record',side_effect=crashing),self.assertRaises(KeyboardInterrupt):self.tick()
        before=len(self.journal.history(self.run_id)['effects']);self.tick()
        self.assertEqual(self.state()['state'],'ready');self.assertEqual(len(self.journal.history(self.run_id)['effects']),before)

    def test_deadline_and_process_counters_survive_restart(self):
        self.tick()
        from datetime import datetime,timedelta,timezone
        class Future(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.now(timezone.utc)+timedelta(days=2)
        with patch.object(worker,'datetime',Future):self.tick()
        self.assertEqual(self.state()['state'],'timed_out')

    def test_exhausted_process_count_stops_before_new_effect(self):
        self.tick();self.tick()
        import sqlite3
        with sqlite3.connect(self.journal.path) as db:db.execute('UPDATE runs SET process_count=36');db.commit()
        before=len(self.journal.history(self.run_id)['effects']);self.tick()
        self.assertEqual(self.state()['reason'],'process_limit');self.assertEqual(len(self.journal.history(self.run_id)['effects']),before)

    def test_revoked_policy_during_reviewer_never_saves_current_approve(self):
        self.until(lambda r,h:worker.next_action(r,h)=='spec_reviewer')
        from task_tower import pipeline_roles
        original=pipeline_roles.run_role
        def revoke(*args,**kwargs):
            output=original(*args,**kwargs)
            self.fixture.path.write_text(self.fixture.path.read_text()+' ')
            return output
        with patch.object(pipeline_roles,'run_role',side_effect=revoke):self.tick()
        self.assertEqual(self.state()['state'],'needs_input');self.assertEqual(self.state()['reason'],'policy_revoked')
        self.assertEqual(self.journal.history(self.run_id)['verdicts'],[])
        self.assertEqual(self.journal.history(self.run_id)['attempts'][-1]['state'],'completed')

    def test_test_executor_mutation_consumes_development_rework_with_real_snapshot(self):
        self.until(lambda r,h:worker.next_action(r,h)=='advance_test')
        self.control.write_text(json.dumps(dict(mutate_role='test_executor')))
        self.tick();r=self.state();h=self.journal.history(self.run_id)
        self.assertEqual((r['state'],r['stage'],r['reworks']['development']),('ready','development',1))
        self.assertEqual(h['effects'][-1]['kind'],'rework_commit')
        self.assertEqual(h['attempts'][-1]['state'],'failed')
        self.assertEqual(h['effects'][-1]['intent']['failed_attempt_id'],h['attempts'][-1]['attempt_id'])
        self.assertTrue(any(v['stage']=='development' and v['superseded'] for v in h['verdicts']))
        self.control.write_text('{}');self.until(lambda r,h:r['state']=='ready' and worker.next_action(r,h)=='publish')

    def test_host_check_mutation_consumes_development_rework(self):
        self.until(lambda r,h:worker.next_action(r,h)=='checks')
        self.control.write_text(json.dumps(dict(host_mutation=True)))
        self.tick();r=self.state();h=self.journal.history(self.run_id)
        self.assertEqual((r['state'],r['stage'],r['reworks']['development']),('ready','development',1))
        self.assertEqual(h['effects'][-1]['kind'],'rework_commit')
        self.assertEqual(h['attempts'][-1]['role'],'host_check');self.assertEqual(h['attempts'][-1]['state'],'failed')
        self.assertFalse(any(v['stage']=='test' and not v['superseded'] for v in h['verdicts']))

    def test_live_ready_owner_cannot_be_stolen(self):
        self.tick();before=self.state()
        other=worker.step(self.config,self.journal,owner_id=str(uuid.uuid4()))
        self.assertEqual(other['status'],'idle');self.assertEqual(self.state()['owner_id'],before['owner_id'])

    def test_dead_ready_handoff_preserves_deadline_and_counters(self):
        self.tick();before=self.state()
        import subprocess,sqlite3
        child=subprocess.Popen([sys.executable,'-c','pass']);child.wait(timeout=10)
        with sqlite3.connect(self.journal.path) as db:db.execute('UPDATE runs SET owner_pid=?',(child.pid,));db.commit()
        other=str(uuid.uuid4());worker.step(self.config,self.journal,owner_id=other)
        after=self.state();self.assertEqual(after['owner_id'],other)
        self.assertEqual(after['deadline_at'],before['deadline_at']);self.assertEqual(after['process_count'],1)
        self.assertEqual([e['kind'] for e in self.journal.history(self.run_id)['events']].count('handoff'),1)

    def test_cancellation_during_actual_role_waits_for_proven_cleanup(self):
        self.tick();self.control.write_text(json.dumps(dict(sleep_seconds=10)))
        import threading,time
        def cancel():
            until=time.monotonic()+10
            while time.monotonic()<until:
                if list((Path(self.fixture.profile['runs_dir'])/self.run_id).glob('*/started')):
                    self.journal.cancel(self.run_id);return
                time.sleep(.02)
        thread=threading.Thread(target=cancel);thread.start()
        try:self.tick()
        finally:thread.join(timeout=15)
        self.assertFalse(thread.is_alive());self.assertEqual(self.state()['state'],'cancelled')
        attempt=self.journal.history(self.run_id)['attempts'][-1]
        self.assertTrue(attempt['evidence']['cleanup_confirmed']);self.assertTrue(attempt['evidence']['started'])

    def test_completed_checkpoint_recovery_rejects_later_dirty_content(self):
        self.tick();self.tick()
        original=worker._record
        def crashing(journal,run,owner,**changes):
            if changes['state']=='ready':raise KeyboardInterrupt('after checkpoint')
            return original(journal,run,owner,**changes)
        with patch.object(worker,'_record',side_effect=crashing),self.assertRaises(KeyboardInterrupt):self.tick()
        r=self.state();(Path(r['worktree'])/'docs/spec.md').write_text('later dirty content')
        self.tick();self.assertEqual(self.state()['state'],'needs_input')
        self.assertFalse(any(a['role']=='spec_reviewer' for a in self.journal.history(self.run_id)['attempts']))

    def test_publisher_return_cannot_fabricate_awaiting_pr(self):
        self.until(lambda r,h:r['state']=='ready' and worker.next_action(r,h)=='publish')
        seen=[]
        def publisher(config,run,journal,owner):
            seen.append((run['state'],owner));return dict(status='awaiting_pr',pr_url='forged')
        self.config['_publisher']=publisher
        result=self.tick();self.assertEqual(seen,[('publishing',self.owner)])
        self.assertEqual(result['status'],'publishing');self.assertNotIn('pr_url',result)
        self.assertFalse(any(e['kind']=='pr_create' for e in self.journal.history(self.run_id)['effects']))

    def _completed_development_artifact_change(self,field):
        self.until(lambda r,h:worker.next_action(r,h)=='advance_development')
        self.control.write_text(json.dumps(dict(mutate_spec_role='development_executor',mutate_artifact=field)))
        self.tick();r=self.state();h=self.journal.history(self.run_id)
        self.assertEqual((r['state'],r['stage'],r['reworks']['spec']),('ready','spec',1))
        self.assertEqual(h['effects'][-1]['kind'],'commit')
        self.assertEqual(h['effects'][-1]['intent']['contributing_executor_attempt_id'],h['attempts'][-1]['attempt_id'])
        self.assertEqual(h['attempts'][-1]['state'],'completed')
        self.assertEqual(worker.next_action(r,h),'spec_executor')

    def test_completed_development_spec_change_consumes_spec_rework(self):
        self._completed_development_artifact_change('spec_path')

    def test_completed_development_plan_change_consumes_spec_rework(self):
        self._completed_development_artifact_change('plan_path')

    def test_actual_issue_data_reaches_role_as_untrusted(self):
        self.tick();self.tick();attempt=self.journal.history(self.run_id)['attempts'][-1]
        request=json.loads((Path(self.fixture.profile['runs_dir'])/attempt['artifacts']['request']).read_text())
        self.assertEqual(request['task_data'],self.fixture.snapshot()['owner/repo']['issues'][16])
        self.assertEqual(request['task_data_trust'],'untrusted')

    def test_changed_private_request_after_role_cannot_accept(self):
        self.until(lambda r,h:worker.next_action(r,h)=='spec_reviewer')
        from task_tower import pipeline_roles
        original=pipeline_roles.run_role
        def tamper(*args,**kwargs):
            result=original(*args,**kwargs)
            p=Path(self.fixture.profile['runs_dir'])/result['artifact_names']['request'];p.write_text('{}')
            return result
        with patch.object(pipeline_roles,'run_role',side_effect=tamper):self.tick()
        self.assertEqual(self.state()['state'],'needs_input');self.assertEqual(self.journal.history(self.run_id)['verdicts'],[])

    def test_monotonic_task_budget_survives_multiple_live_steps(self):
        self.tick()
        with patch.object(worker.time,'monotonic',return_value=10**12):self.tick()
        self.assertEqual(self.state()['state'],'timed_out');self.assertEqual(self.state()['process_count'],0)

class VerdictCIFreshnessTests(unittest.TestCase):
    def test_apply_seam_rechecks_authoritative_ci_bundle(self):
        from tests import test_github_source as github_fixture
        from types import SimpleNamespace
        from task_tower.pipeline_roles import _ci_evidence
        config={'_connections':[SimpleNamespace(repository='owner/repo')]}
        run=dict(repository='owner/repo',manifest=dict(checkpoint_sha='a'*40))
        task=dict(ci_substitution=dict(enabled=True,required_platforms=['linux']))
        source=github_fixture.GitHubSourceTests().source()
        with patch('task_tower.dispatcher._source',return_value=source):
            evidence=_ci_evidence(config,run,task)
        reviewer=dict(stage='test',evidence=dict(execution_local=False,ci_evidence_sha256=digest_manifest(evidence)))
        with patch('task_tower.dispatcher._source',return_value=source):worker._current_ci(config,run,task,reviewer)
        changed=github_fixture.GitHubSourceTests().source(lambda p,r,e:e.update(checks='failed'))
        with patch('task_tower.dispatcher._source',return_value=changed),self.assertRaises(ValueError):worker._current_ci(config,run,task,reviewer)

if __name__=='__main__':unittest.main()

