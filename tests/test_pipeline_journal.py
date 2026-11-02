import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from task_tower import pipeline_journal as journal


def uid(): return str(uuid.uuid4())
def request(issue=1): return dict(operation='submit',delivery_id=uid(),repository='example/repo',issue=issue,task_id='TASK-'+str(issue),runner_label='pipeline')
def policy(components=None): return dict(profile_id='default',profile_fingerprint='a'*64,policy_sha256='b'*64,component_keys=components or ['core'],limits=dict(task_timeout_seconds=7200,max_processes=36,max_reworks=2,role_timeout_seconds=900,log_max_bytes=1048576))


class JournalFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name).resolve()/'private/pipeline.sqlite3'
        self.journal=journal.PipelineJournal(self.path)


class JournalTests(JournalFixture, unittest.TestCase):
    def test_admission_identity_idempotent(self):
        req=request(); receipt=self.journal.submit(req,policy())
        self.assertEqual(self.journal.submit(req,policy()),receipt)
        self.assertEqual(self.journal.lookup(req['delivery_id']),receipt)
        with self.assertRaises(ValueError): self.journal.submit(dict(req,delivery_id=uid()),policy())
        self.assertEqual(len(self.journal.status()['runs']),1)

    def test_fresh_db_schema_and_foreign_schema_rejection(self):
        self.journal.submit(request(),policy())
        with __import__("contextlib").closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0],1414808656)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'delete')
            db.execute('CREATE VIEW unexpected AS SELECT 1'); db.commit()
        with self.assertRaises(ValueError): self.journal.status()

    def test_cas_claims_component_locks_and_unknown_capacity(self):
        for issue,components in [(1,['core']),(2,['core']),(3,['other'])]:
            candidate=request(issue)
            if issue==3:candidate['repository']='other/repository'
            self.journal.submit(candidate,policy(components))
        owner=uid(); first=self.journal.claim(owner,2)
        second=self.journal.claim(uid(),2)
        self.assertEqual((first['issue'],second['issue']),(1,3))
        self.assertIsNone(self.journal.claim(uid(),2))
        expected={k:first[k] for k in ('state','stage','generation','input_sha256')}
        with self.assertRaises(ValueError): self.journal.record(first['run_id'],uid(),expected,{'state':'unknown','reason':'owner_dead'})
        self.journal.record(first['run_id'],owner,expected,{'state':'unknown','reason':'owner_dead'})
        with self.assertRaises(ValueError): self.journal.record(first['run_id'],owner,expected,{'state':'ready'})
        self.assertIsNone(self.journal.claim(uid(),2))

    def test_live_or_unprovable_owner_never_stolen(self):
        self.journal.submit(request(),policy())
        run=self.journal.claim(uid(),2)
        self.assertEqual(self.journal.recover(),[])
        self.assertEqual(self.journal.status(run['run_id'])['state'],'preparing')

    def test_effect_intent_is_immutable_and_unknown_is_not_replayed(self):
        receipt=self.journal.submit(request(),policy()); owner=uid(); run=self.journal.claim(owner,2)
        self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},{'state':'preparing','source_sha':'a'*40})
        effect=self.journal.begin_effect(run['run_id'],owner,{'kind':'commit','parent':'a'*40,'tree':'b'*40,'message':'Task Tower checkpoint','branch':'pipeline/'+run['run_id'],'contributing_executor_attempt_id':None,'evidence_manifest_sha256':None})
        with self.assertRaises(ValueError): self.journal.begin_effect(run['run_id'],owner,{'kind':'commit','parent':'a'*40,'tree':'b'*40,'message':'Task Tower checkpoint','branch':'pipeline/'+run['run_id'],'contributing_executor_attempt_id':None,'evidence_manifest_sha256':None})
        self.journal.finish_effect(effect['effect_id'],owner,{'status':'unknown'})
        with self.assertRaises(ValueError): self.journal.finish_effect(effect['effect_id'],owner,{'status':'completed','commit_sha':'c'*40})
        self.assertEqual(self.journal.status(run['run_id'])['state'],'unknown')


if __name__=='__main__': unittest.main()



class AttemptFixture(JournalFixture):
    def bound_run(self,owner=None):
        from task_tower.pipeline_inputs import digest_manifest,stage_manifest
        self.journal.submit(request(),policy()); owner=owner or uid(); run=self.journal.claim(owner,2)
        criteria={'issue_id':123,'prose':'acceptance'}
        admission=dict(version=1,repository=run['repository'],issue=run['issue'],issue_id=123,task_id=run['task_id'],runner_label=run['runner_label'],criteria=criteria,criteria_sha256=digest_manifest(criteria),policy_sha256=run['policy_sha256'],profile_id=run['profile_id'],profile_fingerprint=run['profile_fingerprint'],source_sha='a'*40,base_sha='a'*40)
        init=dict(state='preparing',admission=admission,issue_id=123,criteria_sha256=admission['criteria_sha256'],source_sha='a'*40,base_sha='a'*40,superpowers_sha256='d'*64)
        run=self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},init)
        manifest=stage_manifest(run,dict(checkpoint_sha='a'*40,product_sha256='e'*64),stage='spec',generation=1,prior_receipt=None,checks=None)
        run=self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='executing',manifest=manifest))
        return owner,run,manifest

    def move(self,owner,run,**transition):
        return self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},transition)


    def freeze_output(self,owner,run,manifest,executor):
        commit=f"{run['generation']+1:040x}"
        effect=self.journal.begin_effect(run['run_id'],owner,dict(kind='commit',parent=run['checkpoint_sha'] or run['source_sha'],tree='b'*40,message='Task Tower checkpoint '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=executor['attempt_id'],evidence_manifest_sha256=None))
        self.journal.finish_effect(effect['effect_id'],owner,dict(status='completed',commit_sha=commit,tree_sha='b'*40))
        frozen=dict(manifest,generation=run['generation']+1,checkpoint_sha=commit,product_sha256='1'*64)
        run=self.move(owner,run,state='ready',generation=frozen['generation'],manifest=frozen)
        return run,frozen

class AttemptTests(AttemptFixture, unittest.TestCase):
    def test_attempt_launch_is_committed_once_and_requires_positive_process_proof(self):
        owner,run,manifest=self.bound_run()
        binding=dict(role='spec_executor',manifest=manifest,artifact_names={'result':'attempt/result.json'})
        attempt=self.journal.begin_attempt(run['run_id'],owner,binding)
        self.assertEqual(self.journal.status(run['run_id'])['process_count'],1)
        with self.assertRaises(ValueError): self.journal.begin_attempt(run['run_id'],owner,binding)
        with self.assertRaises(ValueError): self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='completed',started=True,cleanup_confirmed=True,exit_code=1,result_sha256='f'*64))
        self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='completed',started=True,cleanup_confirmed=False,exit_code=0,result_sha256='f'*64))
        self.assertEqual(self.journal.status(run['run_id'])['state'],'unknown')
        self.assertIsNone(self.journal.claim(uid(),1))

    def test_receipt_requires_host_launched_fresh_reviewer_and_preserves_rejection(self):
        owner,run,manifest=self.bound_run()
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run,manifest=self.freeze_output(owner,run,manifest,executor); run=self.move(owner,run,state='reviewing')
        reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=manifest,artifact_names={}))
        receipt=dict(manifest=manifest,input_sha256=run['input_sha256'],stage='spec',generation=manifest['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='reject',return_stage='spec')
        with self.assertRaises(ValueError): self.journal.save_verdict(run['run_id'],owner,receipt)
        self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
        saved=self.journal.save_verdict(run['run_id'],owner,receipt)
        self.assertEqual(self.journal.status(run['run_id'])['reworks']['spec'],1)
        self.assertEqual(self.journal.history(run['run_id'])['verdicts'][0]['superseded'],1)
        self.assertEqual(saved['body']['decision'],'reject')
        applied=[event for event in self.journal.history(run['run_id'])['events'] if event['kind']=='rework_applied']
        self.assertEqual(len(applied),1)
        self.assertEqual(applied[0]['receipt_id'],saved['receipt_id'])
        self.assertEqual(applied[0]['target_stage'],'spec')
        self.assertEqual(applied[0]['generation_floor'],manifest['generation']+1)
        with self.assertRaises(ValueError): self.journal.save_verdict(run['run_id'],owner,receipt)

    def test_positive_dead_worker_retains_slot_and_component(self):
        import subprocess,sys
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(0.1)'],env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')})
        child.wait(timeout=10)
        self.journal.submit(request(),policy()); owner=uid()
        with self.journal.owner(owner): run=self.journal.claim(owner,2)
        # Simulate a row owned by the real positively terminated process.
        with __import__('contextlib').closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE runs SET owner_pid=? WHERE run_id=?',(child.pid,run['run_id'])); db.commit()
        self.assertEqual(self.journal.recover(),[run['run_id']])
        self.assertEqual(self.journal.status(run['run_id'])['owner_id'],owner)
        self.journal.submit(request(2),policy())
        self.assertIsNone(self.journal.claim(uid(),2))

class HistoryGateTests(AttemptFixture, unittest.TestCase):
    def test_state_and_neutral_evidence_cannot_forge_stage_completion(self):
        owner,run,manifest=self.bound_run()
        with self.assertRaises(ValueError): self.move(owner,run,state='ready')
        # Before a process is launched, neither a supplied approve string nor a
        # later-state projection is an independently accepted stage.
        with self.assertRaises(ValueError): self.move(owner,run,state='publishing',evidence={'status':'approve'})

    def test_raw_model_summary_not_persisted_as_process_proof(self):
        owner,run,manifest=self.bound_run()
        attempt=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        with self.assertRaises(ValueError): self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64,summary='trust me'))

class CompetingJournalTests(JournalFixture, unittest.TestCase):
    def test_real_competing_processes_cannot_exceed_capacity(self):
        import subprocess,sys
        for issue in range(1,5): self.journal.submit(dict(request(issue),repository='example/repo'+str(issue)),policy([str(issue)]))
        code="from task_tower.pipeline_journal import PipelineJournal; import sys,uuid; j=PipelineJournal(sys.argv[1]); o=str(uuid.uuid4());\nwith j.owner(o):\n r=j.claim(o,2); print('none' if r is None else r['run_id'])"
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        children=[subprocess.Popen([sys.executable,'-c',code,str(self.path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env) for _ in range(4)]
        outputs=[p.communicate(timeout=20) for p in children]
        self.assertTrue(all(p.returncode==0 for p in children),outputs)
        self.assertEqual(sum(out.strip()!=b'none' for out,err in outputs),2)
        self.assertEqual(self.journal.status()['active'],2)
        self.journal.recover()
        self.assertEqual(self.journal.status()['unknown'],2)
        self.assertIsNone(self.journal.claim(uid(),2))

class StaleReceiptTests(AttemptFixture, unittest.TestCase):
    def test_valid_stale_receipt_preserved_but_never_effective(self):
        owner,run,manifest=self.bound_run()
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run,manifest=self.freeze_output(owner,run,manifest,executor); run=self.move(owner,run,state='reviewing')
        reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
        # Host notices drift before the old reviewer response is consumed and
        # freezes a new input. The old attestation remains auditable only.
        changed=dict(manifest,generation=manifest['generation']+1,product_sha256='2'*64)
        run=self.move(owner,run,state='ready',generation=changed['generation'],manifest=changed,reason='stale_input',evidence={'cleanup_confirmed':True})
        receipt=dict(manifest=manifest,input_sha256=inputs_digest(manifest),stage='spec',generation=manifest['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None)
        forged=dict(receipt,reviewer_attempt_id=uid())
        with self.assertRaises(ValueError): self.journal.save_verdict(run['run_id'],owner,forged)
        self.assertEqual(self.journal.history(run['run_id'])['verdicts'],[])
        saved=self.journal.save_verdict(run['run_id'],owner,receipt)
        self.assertTrue(saved['superseded'])
        self.assertEqual(self.journal.history(run['run_id'])['verdicts'][0]['superseded'],1)
        with self.assertRaises(ValueError): self.move(owner,run,state='publishing')


def inputs_digest(value):
    from task_tower.pipeline_inputs import digest_manifest
    return digest_manifest(value)



class JournalSafetyTests(JournalFixture, unittest.TestCase):
    def test_exact_policy_rejects_model_source_and_boolean_bounds(self):
        with self.assertRaises(ValueError): self.journal.submit(request(),dict(policy(),source_sha='a'*40))
        bad=policy(); bad['limits']['max_processes']=True
        with self.assertRaises(ValueError): self.journal.submit(request(),bad)
        self.assertFalse(self.path.exists())

    def test_foreign_version_and_wal_are_not_migrated(self):
        self.journal.submit(request(),policy())
        with __import__('contextlib').closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA user_version=2'); db.commit()
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): self.journal.lookup(uid())
        self.assertEqual(self.path.read_bytes(),before)
        with __import__('contextlib').closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA user_version=1'); db.execute('PRAGMA journal_mode=WAL')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError): self.journal.status()
        self.assertEqual(self.path.read_bytes(),before)

    def test_journal_inside_checkout_and_hardlinked_alias_blocked(self):
        with self.assertRaises(ValueError): journal.PipelineJournal(self.path,checkouts=(self.path.parent,))
        self.journal.submit(request(),policy())
        alias=self.path.parent/'alias.sqlite3'; os.link(self.path,alias)
        with self.assertRaises(ValueError): journal.PipelineJournal(alias)

    def test_row_tampering_fails_closed(self):
        receipt=self.journal.submit(request(),policy())
        with __import__('contextlib').closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE runs SET generation='bad'"); db.commit()
        with self.assertRaises(ValueError): self.journal.status(receipt['receipt_id'])

class GenerationTests(AttemptFixture, unittest.TestCase):
    def test_executor_output_freezes_new_reviewer_generation(self):
        owner,run,manifest=self.bound_run()
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run,frozen=self.freeze_output(owner,run,manifest,executor)
        run=self.move(owner,run,state='reviewing')
        reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=frozen,artifact_names={}))
        self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
        receipt=dict(manifest=frozen,input_sha256=run['input_sha256'],stage='spec',generation=2,executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None)
        self.assertFalse(self.journal.save_verdict(run['run_id'],owner,receipt)['superseded'])

class ContributionTests(AttemptFixture, unittest.TestCase):
    def test_reviewer_without_checkpoint_contribution_cannot_accept(self):
        owner,run,manifest=self.bound_run()
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run=self.move(owner,run,state='ready'); run=self.move(owner,run,state='reviewing')
        reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
        receipt=dict(manifest=manifest,input_sha256=run['input_sha256'],stage='spec',generation=1,executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None)
        with self.assertRaises(ValueError): self.journal.save_verdict(run['run_id'],owner,receipt)


class HostCheckTests(AttemptFixture, unittest.TestCase):
    def test_host_check_binding_has_separate_closed_schema(self):
        owner,run,manifest=self.bound_run()
        binding=dict(role='host_check',manifest=manifest,artifact_names={},check_id='unit',check_sha256='a'*64)
        with self.assertRaises(ValueError): self.journal.begin_attempt(run['run_id'],owner,binding)
        # Positive setup advances through real journal executor/checkpoint/reviewer
        # proofs; no remote predicate or product-process completion grants approval.
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        for stage in ('spec','development'):
            executor=self.journal.begin_attempt(run['run_id'],owner,dict(role=stage+'_executor',manifest=manifest,artifact_names={}))
            self.journal.finish_attempt(executor['attempt_id'],owner,proof)
            run,manifest=self.freeze_output(owner,run,manifest,executor)
            run=self.move(owner,run,state='reviewing')
            reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role=stage+'_reviewer',manifest=manifest,artifact_names={}))
            self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
            receipt=dict(manifest=manifest,input_sha256=run['input_sha256'],stage=stage,generation=manifest['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None)
            saved=self.journal.save_verdict(run['run_id'],owner,receipt)
            run=self.move(owner,run,state='ready')
            next_stage='development' if stage=='spec' else 'test'
            manifest=dict(manifest,stage=next_stage,generation=run['generation']+1,prior_verdict_sha256=saved['receipt_sha256'])
            run=self.move(owner,run,state='executing',stage=next_stage,generation=manifest['generation'],manifest=manifest)
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='test_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run=self.move(owner,run,state='ready'); run=self.move(owner,run,state='checking')
        binding=dict(binding,manifest=manifest)
        with self.assertRaises(ValueError): self.journal.begin_attempt(run['run_id'],owner,{k:v for k,v in binding.items() if k!='check_sha256'})
        attempt=self.journal.begin_attempt(run['run_id'],owner,binding)
        self.assertEqual(attempt['check_id'],'unit')
        with self.assertRaises(ValueError): self.journal.finish_attempt(attempt['attempt_id'],owner,dict(proof,check_id='other',check_sha256='a'*64,source_unchanged=True))
        with self.assertRaises(ValueError): self.journal.finish_attempt(attempt['attempt_id'],owner,dict(proof,check_id='unit',check_sha256='b'*64,source_unchanged=True))
        self.journal.finish_attempt(attempt['attempt_id'],owner,dict(proof,check_id='unit',check_sha256='a'*64,source_unchanged=True))
        with self.assertRaises(ValueError): self.journal.begin_attempt(run['run_id'],owner,binding)

class EffectGateTests(JournalFixture, unittest.TestCase):
    def test_publication_effect_cannot_start_from_preparing_state(self):
        self.journal.submit(request(),policy()); owner=uid(); run=self.journal.claim(owner,2)
        with self.assertRaises(ValueError): self.journal.begin_effect(run['run_id'],owner,dict(kind='push',repository=run['repository'],head_sha='a'*40,base_sha='b'*40,remote='origin',branch=run['branch']))

class RejectedContributionTests(AttemptFixture, unittest.TestCase):
    def test_rejected_executor_cannot_supply_next_checkpoint(self):
        AttemptTests.test_receipt_requires_host_launched_fresh_reviewer_and_preserves_rejection(self)
        run=self.journal.status()['runs'][0]; owner=run['owner_id']; history=self.journal.history(run['run_id'])
        old=history['attempts'][0]
        run=self.move(owner,run,state='ready')
        manifest=dict(run['manifest'],generation=run['generation']+1)
        run=self.move(owner,run,state='executing',generation=manifest['generation'],manifest=manifest)
        fresh=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        self.journal.finish_attempt(fresh['attempt_id'],owner,proof)
        with self.assertRaises(ValueError): self.journal.begin_effect(run['run_id'],owner,dict(kind='commit',parent=run['checkpoint_sha'],tree='b'*40,message='Task Tower checkpoint '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=old['attempt_id'],evidence_manifest_sha256=None))

class ReadyResumeTests(AttemptFixture, unittest.TestCase):
    def ready(self,owner):
        owner,run,manifest=self.bound_run(owner)
        attempt=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64))
        run,manifest=self.freeze_output(owner,run,manifest,attempt)
        return run

    def test_same_registered_owner_resumes_ready_without_consuming_capacity(self):
        owner=uid()
        with self.journal.owner(owner):
            run=self.ready(owner)
            resumed=self.journal.claim(owner,1)
            self.assertEqual(resumed['run_id'],run['run_id'])
            self.assertEqual(resumed['deadline_at'],run['deadline_at'])
            self.assertEqual(resumed['process_count'],1)
            with self.assertRaises(ValueError): self.move(owner,resumed,state='executing')
        self.assertIsNone(self.journal.claim(owner,1))
        with self.journal.owner(uid()) as other: self.assertIsNone(self.journal.claim(other,1))

    def test_null_pid_ready_cannot_be_stolen(self):
        run=self.ready(uid())
        with self.journal.owner(uid()) as other: self.assertIsNone(self.journal.claim(other,1))
        self.assertEqual(self.journal.status(run['run_id'])['state'],'ready')

    def test_real_dead_ready_owner_reclaimed_same_run_without_replay(self):
        import subprocess,sys
        code="from tests.test_pipeline_journal import ReadyResumeTests,uid; from task_tower.pipeline_journal import PipelineJournal; import sys; f=ReadyResumeTests(); f.journal=PipelineJournal(sys.argv[1]); o=uid();\nwith f.journal.owner(o):\n r=f.ready(o); print(r['run_id'])"
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        child=subprocess.run([sys.executable,'-c',code,str(self.path)],capture_output=True,env=env,timeout=20)
        self.assertEqual(child.returncode,0,child.stderr)
        run_id=child.stdout.decode().strip(); before=self.journal.status(run_id)
        self.assertIsInstance(before['owner_pid'],int)
        self.assertEqual(self.journal.recover(),[])
        with self.journal.owner(uid()) as owner:
            resumed=self.journal.claim(owner,1)
            self.assertEqual(resumed['run_id'],run_id)
            self.assertEqual(resumed['owner_id'],owner)
            for key in ('deadline_at','generation','process_count','reworks','input_sha256'): self.assertEqual(resumed[key],before[key])
            resumed=self.move(owner,resumed,state='reviewing')
            reviewer=self.journal.begin_attempt(run_id,owner,dict(role='spec_reviewer',manifest=resumed['manifest'],artifact_names={}))
            self.assertEqual(reviewer['role'],'spec_reviewer')
            self.assertEqual(len(self.journal.history(run_id)['attempts']),2)

    def test_unresolved_ready_effect_cannot_resume_and_dead_owner_fenced(self):
        owner=uid()
        with self.journal.owner(owner):
            run=self.ready(owner)
            self.journal.begin_effect(run['run_id'],owner,dict(kind='commit',parent=run['checkpoint_sha'],tree='b'*40,message='Task Tower checkpoint '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None))
            self.assertIsNone(self.journal.claim(owner,1))

class UnresolvedReadyRecoveryTests(JournalFixture, unittest.TestCase):
    def test_actual_dead_ready_with_unresolved_effect_is_fenced(self):
        import subprocess,sys
        code="from tests.test_pipeline_journal import ReadyResumeTests,uid; from task_tower.pipeline_journal import PipelineJournal; import sys; f=ReadyResumeTests(); f.journal=PipelineJournal(sys.argv[1]); o=uid();\nwith f.journal.owner(o):\n r=f.ready(o); f.journal.begin_effect(r['run_id'],o,dict(kind='commit',parent=r['checkpoint_sha'],tree='b'*40,message='Task Tower checkpoint '+r['run_id'],branch=r['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None)); print(r['run_id'])"
        child=subprocess.run([sys.executable,'-c',code,str(self.path)],capture_output=True,env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')},timeout=20)
        self.assertEqual(child.returncode,0,child.stderr)
        run_id=child.stdout.decode().strip()
        self.assertEqual(self.journal.recover(),[run_id])
        self.assertEqual(self.journal.status(run_id)['state'],'unknown')
        with self.journal.owner(uid()) as owner: self.assertIsNone(self.journal.claim(owner,1))

class ReviewRegressionTests(AttemptFixture, unittest.TestCase):
    def test_late_stale_reject_does_not_invalidate_replacement_executor(self):
        owner,run,manifest=self.bound_run()
        proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(executor['attempt_id'],owner,proof)
        run,manifest=self.freeze_output(owner,run,manifest,executor)
        run=self.move(owner,run,state='reviewing')
        reviewer=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_reviewer',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(reviewer['attempt_id'],owner,proof)
        receipt=dict(manifest=manifest,input_sha256=run['input_sha256'],stage='spec',generation=manifest['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='reject',return_stage='spec')
        replacement=dict(manifest,generation=manifest['generation']+1,product_sha256='2'*64)
        run=self.move(owner,run,state='ready',generation=replacement['generation'],manifest=replacement,reason='stale_input',evidence={'cleanup_confirmed':True})
        run=self.move(owner,run,state='executing')
        fresh=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=replacement,artifact_names={}))
        counters=dict(run['reworks'])
        stale=self.journal.save_verdict(run['run_id'],owner,receipt)
        self.assertTrue(stale['superseded'])
        self.assertEqual(self.journal.status(run['run_id'])['reworks'],counters)
        self.journal.finish_attempt(fresh['attempt_id'],owner,proof)
        run,new_manifest=self.freeze_output(owner,run,replacement,fresh)
        self.assertEqual(run['state'],'ready')
        applied=[e for e in self.journal.history(run['run_id'])['events'] if e['kind']=='rework_applied']
        self.assertEqual(len(applied),1)
        self.assertIsNone(applied[0]['receipt_id'])

    def test_preparing_fields_validate_types_before_sqlite_coercion(self):
        self.journal.submit(request(),policy()); owner=uid(); run=self.journal.claim(owner,2)
        expected={k:run[k] for k in ('state','stage','generation','input_sha256')}
        for field,value in [('issue_id',True),('issue_id','123'),('issue_id',0),('source_sha','A'*40),('base_sha',True),('criteria_sha256','bad'),('superpowers_sha256',None),('worktree','relative/path'),('git_dir',123),('worktree',str(self.path)),('git_dir',str(self.path.parent/'CON.txt'))]:
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                self.journal.record(run['run_id'],owner,expected,dict(state='preparing',**{field:value}))
        self.assertIsNone(self.journal.status(run['run_id'])['issue_id'])
        self.assertIsNone(self.journal.status(run['run_id'])['source_sha'])
        for evidence in ({'owner_id':'-'*36},{'generation':True},{'process_count':True},{'stdout_bytes':-1},{'result_sha256':'a'*40}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.journal.record(run['run_id'],owner,expected,dict(state='preparing',evidence=evidence))

class ReworkProofTests(AttemptFixture, unittest.TestCase):
    def test_rework_rejects_forged_owner_or_nonmutation_attempt(self):
        cases=[('completed',True,False),('failed',False,False),('failed',True,True),('failed',True,None)]
        for status,cleanup,unchanged in cases:
            other=ReworkProofTests(); other.setUp()
            try:
                owner,run,manifest=other.bound_run()
                attempt=other.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
                evidence=dict(status=status,started=True,cleanup_confirmed=cleanup,exit_code=0 if status=='completed' else 1,result_sha256='f'*64)
                if unchanged is not None: evidence['source_unchanged']=unchanged
                other.journal.finish_attempt(attempt['attempt_id'],owner,evidence)
                intent=dict(kind='rework_commit',parent=run['source_sha'],tree='b'*40,message='Task Tower checkpoint '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None,failed_attempt_id=attempt['attempt_id'])
                with self.subTest(status=status,cleanup=cleanup,unchanged=unchanged), self.assertRaises(ValueError): other.journal.begin_effect(run['run_id'],owner,intent)
                with self.assertRaises(ValueError): other.journal.begin_effect(run['run_id'],uid(),intent)
                with self.assertRaises(ValueError): other.journal.begin_effect(run['run_id'],owner,dict(intent,failed_attempt_id=uid()))
                self.assertEqual(other.journal.history(run['run_id'])['effects'],[])
            finally: other.doCleanups()

    def test_rework_kind_cannot_claim_normal_contributor_or_evidence(self):
        owner,run,manifest=self.bound_run()
        attempt=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='failed',started=True,cleanup_confirmed=True,exit_code=1,result_sha256='f'*64,source_unchanged=False))
        intent=dict(kind='rework_commit',parent=run['source_sha'],tree='b'*40,message='Task Tower checkpoint '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None,failed_attempt_id=attempt['attempt_id'])
        for bad in (dict(intent,contributing_executor_attempt_id=attempt['attempt_id']),dict(intent,evidence_manifest_sha256='a'*64)):
            with self.assertRaises(ValueError): self.journal.begin_effect(run['run_id'],owner,bad)

class InitialReadyProofTests(JournalFixture, unittest.TestCase):
    def prepared(self):
        from task_tower.pipeline_inputs import digest_manifest,stage_manifest
        self.journal.submit(request(),policy()); owner=uid(); run=self.journal.claim(owner,2)
        criteria={'issue_id':123}
        admission=dict(version=1,repository=run['repository'],issue=run['issue'],issue_id=123,task_id=run['task_id'],runner_label=run['runner_label'],criteria=criteria,criteria_sha256=digest_manifest(criteria),policy_sha256=run['policy_sha256'],profile_id=run['profile_id'],profile_fingerprint=run['profile_fingerprint'],source_sha='a'*40,base_sha='a'*40)
        transition=dict(state='preparing',admission=admission,issue_id=123,criteria_sha256=admission['criteria_sha256'],source_sha='a'*40,base_sha='a'*40,superpowers_sha256='d'*64,worktree=str(self.path.parent/'worktree'),git_dir=str(self.path.parent/'gitdir'))
        run=self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},transition)
        manifest=stage_manifest(run,dict(checkpoint_sha='a'*40,product_sha256='e'*64),stage='spec',generation=1,prior_receipt=None,checks=None)
        return owner,run,manifest

    def test_initial_ready_needs_matching_completed_creation_and_initial_binding(self):
        owner,run,manifest=self.prepared(); expected={k:run[k] for k in ('state','stage','generation','input_sha256')}
        with self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,expected,dict(state='ready',manifest=manifest))
        intent=dict(kind='worktree_create',source_sha=run['source_sha'],branch=run['branch'],worktree=run['worktree'],git_dir=run['git_dir'])
        with self.assertRaises(ValueError): self.journal.begin_effect(run['run_id'],owner,dict(intent,worktree=str(self.path.parent/'foreign')))
        effect=self.journal.begin_effect(run['run_id'],owner,intent)
        with self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,expected,dict(state='ready',manifest=manifest))
        self.journal.finish_effect(effect['effect_id'],owner,dict(status='completed',source_sha=run['source_sha']))
        for bad in (dict(manifest,checkpoint_sha='b'*40),dict(manifest,generation=2),dict(manifest,prior_verdict_sha256='a'*64),dict(manifest,checks_sha256='a'*64)):
            with self.subTest(binding=bad), self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,expected,dict(state='ready',generation=bad['generation'],manifest=bad))
        run=self.journal.record(run['run_id'],owner,expected,dict(state='ready',manifest=manifest))
        expected={k:run[k] for k in ('state','stage','generation','input_sha256')}
        with self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,expected,dict(state='reviewing'))
        with self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,expected,dict(state='publishing'))

    def test_initial_ready_wrong_source_observation_is_not_creation_proof(self):
        owner,run,manifest=self.prepared()
        effect=self.journal.begin_effect(run['run_id'],owner,dict(kind='worktree_create',source_sha=run['source_sha'],branch=run['branch'],worktree=run['worktree'],git_dir=run['git_dir']))
        self.journal.finish_effect(effect['effect_id'],owner,dict(status='completed',source_sha='b'*40))
        with self.assertRaises(ValueError): self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='ready',manifest=manifest))

class CrossRunReworkProofTests(AttemptFixture, unittest.TestCase):
    def test_same_owner_cannot_reuse_another_runs_failed_attempt(self):
        from task_tower.pipeline_inputs import digest_manifest,stage_manifest
        owner,first,manifest=self.bound_run()
        attempt=self.journal.begin_attempt(first['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
        self.journal.finish_attempt(attempt['attempt_id'],owner,dict(status='failed',started=True,cleanup_confirmed=True,exit_code=1,result_sha256='f'*64,source_unchanged=False))
        self.journal.submit(dict(request(2),repository='other/repository'),policy(['other'])); second=self.journal.claim(owner,2)
        criteria={'issue_id':124}
        admission=dict(first['admission'],repository=second['repository'],issue=second['issue'],issue_id=124,task_id=second['task_id'],criteria=criteria,criteria_sha256=digest_manifest(criteria))
        second=self.journal.record(second['run_id'],owner,{k:second[k] for k in ('state','stage','generation','input_sha256')},dict(state='preparing',admission=admission,issue_id=124,criteria_sha256=admission['criteria_sha256'],source_sha='a'*40,base_sha='a'*40,superpowers_sha256='d'*64))
        binding=stage_manifest(second,dict(checkpoint_sha='a'*40,product_sha256='e'*64),stage='spec',generation=1,prior_receipt=None,checks=None)
        second=self.journal.record(second['run_id'],owner,{k:second[k] for k in ('state','stage','generation','input_sha256')},dict(state='executing',manifest=binding))
        intent=dict(kind='rework_commit',parent='a'*40,tree='b'*40,message='Task Tower checkpoint '+second['run_id'],branch=second['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None,failed_attempt_id=attempt['attempt_id'])
        with self.assertRaisesRegex(ValueError,'current failed mutation proof'): self.journal.begin_effect(second['run_id'],owner,intent)
        self.assertEqual(self.journal.history(second['run_id'])['effects'],[])

class InitialIdentityGuardTests(JournalFixture, unittest.TestCase):
    def test_worktree_creation_requires_nonnull_absolute_directory_identities(self):
        self.journal.submit(request(),policy()); owner=uid(); run=self.journal.claim(owner,2)
        run=self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='preparing',source_sha='a'*40))
        for worktree,git_dir in ((None,None),('relative/worktree','relative/git'),(123,str(self.path.parent/'gitdir')),(str(self.path.parent/'worktree'),False)):
            intent=dict(kind='worktree_create',source_sha='a'*40,branch=run['branch'],worktree=worktree,git_dir=git_dir)
            with self.subTest(worktree=worktree,git_dir=git_dir), self.assertRaisesRegex(ValueError,'host directory'):
                self.journal.begin_effect(run['run_id'],owner,intent)
        self.assertEqual(self.journal.history(run['run_id'])['effects'],[])
