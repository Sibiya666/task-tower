import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

from task_tower import pipeline_inputs as inputs


class InputTests(unittest.TestCase):
    def test_mixed_line_endings_are_stable_but_content_change_is_not(self):
        self.assertEqual(inputs.canonical_text(b'a\r\nb\rc\n'), b'a\nb\nc\n')
        self.assertNotEqual(inputs.canonical_text(b'a\n'), inputs.canonical_text(b'a'))
        with self.assertRaises(UnicodeDecodeError): inputs.canonical_text(b'\xff')

    def test_bom_powershell_lf_crlf_equal_and_bom_presence_changes_hash(self):
        bom = b'\xef\xbb\xbf'
        text = '# Привет\nWrite-Host x\n'.encode()
        self.assertEqual(inputs.canonical_text(bom + text.replace(b'\n', b'\r\n')), bom + text)
        self.assertNotEqual(inputs.canonical_text(bom + text), text)
        with self.assertRaises(ValueError): inputs.canonical_artifact(bom + text)

    def test_canonical_json_rejects_nan(self):
        self.assertEqual(inputs.canonical_json({'z': 'я', 'a': 1}), b'{"a":1,"z":"\\u044f"}')
        with self.assertRaises(ValueError): inputs.canonical_json({'x': float('nan')})


class GitFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root/'a.ps1').write_bytes(b'\xef\xbb\xbf' + '# Привет\r\nx\r'.encode())
        (self.root/'spec.md').write_bytes(b'spec\n')
        (self.root/'plan.md').write_bytes(b'plan\n')
        (self.root/'docs/tasks').mkdir(parents=True)
        (self.root/'docs/tasks/T.json').write_bytes(b'{}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'initial')
        self.source = self.git('rev-parse', 'HEAD').strip()
        self.policy = dict(allowed_paths=['a.ps1','spec.md','plan.md','assets/','docs/tasks/','evidence/'],spec_path='spec.md',plan_path='plan.md',evidence_dir='evidence/',source_sha=self.source)

    def git(self,*args):
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        return subprocess.check_output(['git','-C',str(self.root),*args],env=env,stderr=subprocess.STDOUT).decode()


class GitInputs(GitFixture, unittest.TestCase):
    def test_hashing_preserves_source_bytes_and_binary_assets(self):
        before=(self.root/'a.ps1').read_bytes()
        (self.root/'assets').mkdir()
        data=b'\0'+b'x'*(4*1024*1024)
        (self.root/'assets/image.png').write_bytes(data)
        manifest=inputs.product_manifest(self.root,self.policy)
        rows={r['path']:r for r in manifest['files']}
        self.assertEqual(rows['assets/image.png']['scheme'],'sha256-bytes-v1')
        self.assertEqual(rows['assets/image.png']['sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual(rows['a.ps1']['scheme'],'sha256-utf8-lf-v2')
        self.assertEqual((self.root/'a.ps1').read_bytes(),before)
        self.assertNotIn('docs/tasks/T.json',rows)
        self.assertIn('spec.md',rows)

    def test_size_limits_and_designated_artifact_bom(self):
        (self.root/'spec.md').write_bytes(b'x'*(1024*1024+1))
        with self.assertRaisesRegex(ValueError,'size_limit'): inputs.product_manifest(self.root,self.policy)
        (self.root/'spec.md').write_bytes(b'\xef\xbb\xbfhi')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)
        (self.root/'spec.md').write_bytes(b'ok')
        (self.root/'assets').mkdir()
        with (self.root/'assets/large').open('wb') as stream: stream.truncate(16*1024*1024+1)
        with self.assertRaisesRegex(ValueError,'size_limit'): inputs.product_manifest(self.root,self.policy)

    def test_model_git_or_evidence_mutation_rejected(self):
        (self.root/'docs/tasks/T.json').write_bytes(b'{"accepted":true}')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)
        self.git('checkout','--','docs/tasks/T.json')
        (self.root/'evidence').mkdir()
        (self.root/'evidence/approval.md').write_bytes(b'approve')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)

    def test_outside_allowed_and_hardlink_rejected(self):
        (self.root/'foreign').write_bytes(b'x')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)
        (self.root/'foreign').unlink()
        os.link(self.root/'a.ps1', self.root/'assets-link')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)


if __name__=='__main__': unittest.main()

class CheckpointTests(GitFixture, unittest.TestCase):
    def journal_run(self):
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import policy,request,uid
        store=PipelineJournal(Path(self.tmp.name)/'private/journal.sqlite3',checkouts=(self.root,))
        store.submit(request(),policy()); owner=uid(); run=store.claim(owner,2)
        self.git('checkout','-b',run['branch'])
        run=store.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='preparing',source_sha=self.source,base_sha=self.source,worktree=str(self.root)))
        return store,owner,run

    def test_private_checkpoint_has_exact_parent_and_preserves_user_index(self):
        store,owner,run=self.journal_run()
        (self.root/'a.ps1').write_bytes(b'new\r\n')
        index=(self.root/'.git/index').read_bytes()
        checkpoint=inputs.freeze_checkpoint(run,self.policy,store,owner)
        self.assertEqual(self.git('rev-parse','HEAD').strip(),checkpoint['checkpoint_sha'])
        self.assertEqual(self.git('rev-parse','HEAD^').strip(),self.source)
        self.assertEqual((self.root/'.git/index').read_bytes(),index)
        self.assertEqual(store.history(run['run_id'])['effects'][0]['status'],'completed')
        self.assertEqual((self.root/'a.ps1').read_bytes(),b'new\r\n')

    def test_checkpoint_crash_before_and_after_ref_update_never_replays(self):
        from unittest.mock import patch
        for after in (False,True):
            with self.subTest(after=after):
                # Each crash has a fresh real repository and journal.
                other=CheckpointTests(); other.setUp()
                try:
                    store,owner,run=other.journal_run(); original=inputs._git
                    def broken(root,*args,**kwargs):
                        if 'update-ref' in args:
                            if after: original(root,*args,**kwargs)
                            raise RuntimeError('simulated host death')
                        return original(root,*args,**kwargs)
                    with patch.object(inputs,'_git',broken):
                        with self.assertRaises(RuntimeError): inputs.freeze_checkpoint(run,other.policy,store,owner)
                    self.assertEqual(store.history(run['run_id'])['effects'][0]['status'],'intent')
                    head=other.git('rev-parse','HEAD').strip()
                    self.assertEqual(head==other.source,not after)
                    with self.assertRaises(ValueError): inputs.freeze_checkpoint(run,other.policy,store,owner)
                    self.assertEqual(len(store.history(run['run_id'])['effects']),1)
                finally: other.doCleanups()

    def test_actual_bom_source_lf_and_crlf_and_binary_control(self):
        original=(self.root/'a.ps1').read_bytes()
        first={r['path']:r for r in inputs.product_manifest(self.root,self.policy)['files']}
        (self.root/'a.ps1').write_bytes(original.replace(b'\r\n',b'\n').replace(b'\r',b'\n'))
        second={r['path']:r for r in inputs.product_manifest(self.root,self.policy)['files']}
        self.assertEqual(first['a.ps1']['sha256'],second['a.ps1']['sha256'])
        (self.root/'a.ps1').write_bytes((self.root/'a.ps1').read_bytes()[3:])
        third={r['path']:r for r in inputs.product_manifest(self.root,self.policy)['files']}
        self.assertNotEqual(second['a.ps1']['sha256'],third['a.ps1']['sha256'])
        (self.root/'a.ps1').write_bytes(b'valid\x00utf8\r\n')
        row=next(r for r in inputs.product_manifest(self.root,self.policy)['files'] if r['path']=='a.ps1')
        self.assertEqual(row['scheme'],'sha256-bytes-v1')
        self.assertEqual(row['sha256'],hashlib.sha256(b'valid\x00utf8\r\n').hexdigest())

class AdditionalInputTests(GitFixture, unittest.TestCase):
    def test_legacy_v1_proof_unchanged_and_newline_presence_is_bound(self):
        from task_tower.tasks import _hash
        path=self.root/'a.ps1'; before=path.read_bytes(); proof=_hash(path,self.root.resolve())
        inputs.product_manifest(self.root,self.policy)
        self.assertEqual(_hash(path,self.root.resolve()),proof)
        self.assertEqual(path.read_bytes(),before)
        path.write_bytes(b'x\n')
        first=inputs.digest_manifest(inputs.product_manifest(self.root,self.policy))
        path.write_bytes(b'x')
        self.assertNotEqual(inputs.digest_manifest(inputs.product_manifest(self.root,self.policy)),first)

    def test_inherited_git_index_cannot_redirect_host_git(self):
        from unittest.mock import patch
        foreign=Path(self.tmp.name)/'foreign-index'
        with patch.dict(os.environ,{'GIT_INDEX_FILE':str(foreign)}):
            result=inputs.product_manifest(self.root,self.policy)
        self.assertIn('a.ps1',[r['path'] for r in result['files']])
        self.assertFalse(foreign.exists())



class PortablePathTests(GitFixture, unittest.TestCase):
    def test_windows_alias_and_portable_case_collision_are_rejected(self):
        for name in ('alias.','CON.txt','bad\x01name'):
            with self.subTest(name=name), self.assertRaises(ValueError): inputs._relative(name)
        (self.root/'Spec.md').write_bytes(b'alias')
        self.policy['allowed_paths'].append('Spec.md')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)

    @unittest.skipIf(os.name=='nt','POSIX executable mode transition')
    def test_worktree_executable_mode_change_is_bound(self):
        first=inputs.digest_manifest(inputs.product_manifest(self.root,self.policy))
        (self.root/'a.ps1').chmod(0o755)
        second=inputs.product_manifest(self.root,self.policy)
        self.assertNotEqual(first,inputs.digest_manifest(second))
        self.assertEqual(next(r for r in second['files'] if r['path']=='a.ps1')['mode'],'100755')

class IgnoredArtifactTests(GitFixture, unittest.TestCase):
    def test_new_ignored_required_artifact_is_not_silently_omitted(self):
        (self.root/'.gitignore').write_text('ignored.md\n',encoding='utf-8')
        (self.root/'ignored.md').write_text('required',encoding='utf-8')
        self.policy.update(spec_path='ignored.md',allowed_paths=self.policy['allowed_paths']+['.gitignore','ignored.md'])
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,self.policy)

class HostEvidenceTests(GitFixture, unittest.TestCase):
    def test_only_exact_host_md_attestation_is_excluded_and_product_unchanged(self):
        before=inputs.product_manifest(self.root,self.policy)
        (self.root/'evidence').mkdir()
        data=b'Host receipt\r\n'; (self.root/'evidence/spec.md').write_bytes(data)
        attested=dict(self.policy,_host_evidence={'evidence/spec.md':hashlib.sha256(b'Host receipt\n').hexdigest()})
        self.assertEqual(inputs.product_manifest(self.root,attested),before)
        (self.root/'evidence/extra.md').write_bytes(b'model approval')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,attested)
        (self.root/'evidence/extra.md').unlink()
        (self.root/'evidence/spec.md').write_bytes(b'\xef\xbb\xbfHost receipt\n')
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,attested)
        with self.assertRaises(ValueError): inputs.product_manifest(self.root,dict(self.policy,_host_evidence={'spec.md':'a'*64}))

    def test_host_evidence_map_cannot_authorize_nonpublication_checkpoint(self):
        # A real initial host checkpoint rejects the publication-only capability.
        other=CheckpointTests(); other.setUp()
        try:
            store,owner,run=other.journal_run()
            (other.root/'evidence').mkdir(); (other.root/'evidence/spec.md').write_bytes(b'host\n')
            attested=dict(other.policy,_host_evidence={'evidence/spec.md':hashlib.sha256(b'host\n').hexdigest()})
            with self.assertRaises(ValueError): inputs.freeze_checkpoint(run,attested,store,owner)
            self.assertEqual(store.history(run['run_id'])['effects'],[])
        finally: other.doCleanups()

class PublicationCheckpointTests(GitFixture, unittest.TestCase):
    def test_final_host_evidence_is_committed_without_changing_product(self):
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import policy,request,uid
        store=PipelineJournal(Path(self.tmp.name)/'private/journal.sqlite3',checkouts=(self.root,))
        store.submit(request(),policy()); owner=uid(); run=store.claim(owner,2)
        self.git('checkout','-b',run['branch'])
        def move(**transition):
            nonlocal run
            run=store.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},transition)
        criteria={'issue_id':123}
        admission=dict(version=1,repository=run['repository'],issue=run['issue'],issue_id=123,task_id=run['task_id'],runner_label=run['runner_label'],criteria=criteria,criteria_sha256=inputs.digest_manifest(criteria),policy_sha256=run['policy_sha256'],profile_id=run['profile_id'],profile_fingerprint=run['profile_fingerprint'],source_sha=self.source,base_sha=self.source)
        move(state='preparing',admission=admission,issue_id=123,criteria_sha256=admission['criteria_sha256'],source_sha=self.source,base_sha=self.source,superpowers_sha256='d'*64,worktree=str(self.root))
        checkpoint=dict(checkpoint_sha=self.source,product_sha256=inputs.digest_manifest(inputs.product_manifest(self.root,self.policy)))
        prior=None; proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        for stage in ('spec','development','test'):
            generation=run['generation']+(stage!='spec')
            manifest=inputs.stage_manifest(run,checkpoint,stage=stage,generation=generation,prior_receipt=prior,checks=None)
            move(state='executing',stage=stage,generation=generation,manifest=manifest)
            executor=store.begin_attempt(run['run_id'],owner,dict(role=stage+'_executor',manifest=manifest,artifact_names={}))
            store.finish_attempt(executor['attempt_id'],owner,proof)
            checkpoint=inputs.freeze_checkpoint(run,self.policy,store,owner)
            manifest=inputs.stage_manifest(run,checkpoint,stage=stage,generation=generation+1,prior_receipt=prior,checks=None)
            move(state='ready',generation=generation+1,manifest=manifest)
            if stage=='test':
                move(state='checking')
                check=store.begin_attempt(run['run_id'],owner,dict(role='host_check',manifest=manifest,artifact_names={},check_id='unit',check_sha256='a'*64))
                store.finish_attempt(check['attempt_id'],owner,dict(proof,check_id='unit',check_sha256='a'*64,source_unchanged=True))
                checks={'version':1,'status':'passed'}
                manifest=inputs.stage_manifest(run,checkpoint,stage=stage,generation=run['generation']+1,prior_receipt=prior,checks=checks)
                move(state='ready',generation=manifest['generation'],manifest=manifest,evidence=dict(cleanup_confirmed=True,checks_sha256=inputs.digest_manifest(checks)))
            move(state='reviewing')
            reviewer=store.begin_attempt(run['run_id'],owner,dict(role=stage+'_reviewer',manifest=manifest,artifact_names={}))
            store.finish_attempt(reviewer['attempt_id'],owner,proof)
            prior=store.save_verdict(run['run_id'],owner,dict(manifest=manifest,input_sha256=run['input_sha256'],stage=stage,generation=manifest['generation'],executor_instance_id=executor['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None))
            move(state='ready')
        move(state='publishing')
        (self.root/'evidence').mkdir(); (self.root/'evidence/accepted.md').write_bytes(b'Host evidence\n')
        host=dict(self.policy,_host_evidence={'evidence/accepted.md':hashlib.sha256(b'Host evidence\n').hexdigest()})
        final=inputs.freeze_checkpoint(run,host,store,owner)
        self.assertEqual(final['product_sha256'],checkpoint['product_sha256'])
        self.assertEqual(self.git('show','HEAD:evidence/accepted.md'),'Host evidence\n')
        self.assertIsNotNone(final['evidence_manifest_sha256'])
        self.assertEqual(store.history(run['run_id'])['effects'][-1]['intent']['evidence_manifest_sha256'],final['evidence_manifest_sha256'])

class ReworkCheckpointTests(GitFixture, unittest.TestCase):
    def mutation_attempt(self, checking=False):
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import policy,request,uid
        store=PipelineJournal(Path(self.tmp.name)/'private/journal.sqlite3',checkouts=(self.root,))
        store.submit(request(),policy()); owner=uid(); run=store.claim(owner,2)
        self.git('checkout','-b',run['branch'])
        def move(**transition):
            nonlocal run
            run=store.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},transition)
        criteria={'issue_id':123}
        admission=dict(version=1,repository=run['repository'],issue=run['issue'],issue_id=123,task_id=run['task_id'],runner_label=run['runner_label'],criteria=criteria,criteria_sha256=inputs.digest_manifest(criteria),policy_sha256=run['policy_sha256'],profile_id=run['profile_id'],profile_fingerprint=run['profile_fingerprint'],source_sha=self.source,base_sha=self.source)
        move(state='preparing',admission=admission,issue_id=123,criteria_sha256=admission['criteria_sha256'],source_sha=self.source,base_sha=self.source,superpowers_sha256='d'*64,worktree=str(self.root))
        checkpoint=dict(checkpoint_sha=self.source,product_sha256=inputs.digest_manifest(inputs.product_manifest(self.root,self.policy)))
        receipts={}; prior=None; proof=dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64)
        for stage in ('spec','development','test'):
            manifest=inputs.stage_manifest(run,checkpoint,stage=stage,generation=run['generation']+(stage!='spec'),prior_receipt=prior,checks=None)
            move(state='executing',stage=stage,generation=manifest['generation'],manifest=manifest)
            attempt=store.begin_attempt(run['run_id'],owner,dict(role=stage+'_executor',manifest=manifest,artifact_names={}))
            if stage=='test' and not checking: break
            store.finish_attempt(attempt['attempt_id'],owner,proof)
            checkpoint=inputs.freeze_checkpoint(run,self.policy,store,owner)
            manifest=inputs.stage_manifest(run,checkpoint,stage=stage,generation=run['generation']+1,prior_receipt=prior,checks=None)
            move(state='ready',generation=manifest['generation'],manifest=manifest)
            if stage=='test':
                move(state='checking')
                attempt=store.begin_attempt(run['run_id'],owner,dict(role='host_check',manifest=manifest,artifact_names={},check_id='unit',check_sha256='a'*64))
                break
            move(state='reviewing')
            reviewer=store.begin_attempt(run['run_id'],owner,dict(role=stage+'_reviewer',manifest=manifest,artifact_names={}))
            store.finish_attempt(reviewer['attempt_id'],owner,proof)
            prior=store.save_verdict(run['run_id'],owner,dict(manifest=manifest,input_sha256=run['input_sha256'],stage=stage,generation=manifest['generation'],executor_instance_id=attempt['instance_id'],reviewer_instance_id=reviewer['instance_id'],reviewer_attempt_id=reviewer['attempt_id'],superpowers_sha256='d'*64,policy_sha256='b'*64,result_sha256='f'*64,process=proof,decision='approve',return_stage=None))
            receipts[stage]=prior; move(state='ready')
        import sys
        child=subprocess.run([sys.executable,'-c',"from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'changed by failed check\\n'); sys.exit(1)",str(self.root/'a.ps1')],env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')},capture_output=True,timeout=10)
        self.assertEqual(child.returncode,1,child.stderr)
        failure=dict(status='failed',started=True,cleanup_confirmed=True,exit_code=child.returncode,result_sha256='f'*64,source_unchanged=False)
        if checking: failure.update(check_id='unit',check_sha256='a'*64)
        store.finish_attempt(attempt['attempt_id'],owner,failure)
        return store,owner,run,attempt,receipts

    def test_actual_failed_executing_and_checking_freeze_only_rework(self):
        for checking in (False,True):
            other=ReworkCheckpointTests(); other.setUp()
            try:
                store,owner,run,attempt,receipts=other.mutation_attempt(checking)
                expected={k:run[k] for k in ('state','stage','generation','input_sha256')}
                fake=dict(run['manifest'],stage='development',generation=run['generation']+1)
                with self.assertRaises(ValueError): store.record(run['run_id'],owner,expected,dict(state='ready',stage='development',generation=fake['generation'],manifest=fake,reason='stale_input',evidence={'cleanup_confirmed':True}))
                with self.assertRaises(ValueError): inputs.freeze_checkpoint(run,other.policy,store,owner)
                frozen=inputs.freeze_rework_checkpoint(run,other.policy,store,owner,attempt['attempt_id'])
                self.assertEqual(other.git('rev-parse','HEAD').strip(),frozen['checkpoint_sha'])
                self.assertEqual(other.git('show','HEAD:a.ps1'),'changed by failed check\n')
                effect=store.history(run['run_id'])['effects'][-1]
                self.assertEqual(effect['kind'],'rework_commit')
                self.assertEqual(effect['intent']['failed_attempt_id'],attempt['attempt_id'])
                self.assertIsNone(effect['intent']['contributing_executor_attempt_id'])
                current=store.status(run['run_id'])
                with self.assertRaises(ValueError): inputs.freeze_rework_checkpoint(current,other.policy,store,owner,attempt['attempt_id'])
                with self.assertRaises(ValueError): inputs.freeze_rework_checkpoint(current,other.policy,store,owner,str(uuid.uuid4()))
                manifest=inputs.stage_manifest(run,frozen,stage='development',generation=run['generation']+1,prior_receipt=receipts['spec'],checks=None)
                with self.assertRaises(ValueError): store.record(run['run_id'],owner,expected,dict(state='ready',stage='development',generation=manifest['generation'],manifest=manifest,evidence={'cleanup_confirmed':True}))
                run=store.record(run['run_id'],owner,expected,dict(state='ready',stage='development',generation=manifest['generation'],manifest=manifest,reason='stale_input',evidence={'cleanup_confirmed':True}))
                self.assertEqual(run['reworks']['development'],1)
                verdicts=store.history(run['run_id'])['verdicts']
                self.assertTrue(all(v['superseded'] for v in verdicts if v['stage']=='development'))
                expected={k:run[k] for k in ('state','stage','generation','input_sha256')}
                with self.assertRaises(ValueError): store.record(run['run_id'],owner,expected,dict(state='reviewing'))
                run=store.record(run['run_id'],owner,expected,dict(state='executing'))
                with self.assertRaises(ValueError): inputs.freeze_rework_checkpoint(run,other.policy,store,owner,attempt['attempt_id'])
                fresh=store.begin_attempt(run['run_id'],owner,dict(role='development_executor',manifest=manifest,artifact_names={}))
                self.assertNotEqual(fresh['attempt_id'],attempt['attempt_id'])
            finally: other.doCleanups()

class InitialReadyCheckpointTests(GitFixture, unittest.TestCase):
    def prepared_ready(self,owner):
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import policy,request
        self.journal=PipelineJournal(self.root.parent/'private/initial.sqlite3',checkouts=(self.root,))
        with self.journal.owner(owner):
            self.journal.submit(request(),policy()); run=self.journal.claim(owner,2)
            worktree=self.root.parent/'owned-worktree'; git_dir=self.root/'.git/worktrees/owned-worktree'
            criteria={'issue_id':123}
            admission=dict(version=1,repository=run['repository'],issue=run['issue'],issue_id=123,task_id=run['task_id'],runner_label=run['runner_label'],criteria=criteria,criteria_sha256=inputs.digest_manifest(criteria),policy_sha256=run['policy_sha256'],profile_id=run['profile_id'],profile_fingerprint=run['profile_fingerprint'],source_sha=self.source,base_sha=self.source)
            run=self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='preparing',admission=admission,issue_id=123,criteria_sha256=admission['criteria_sha256'],source_sha=self.source,base_sha=self.source,superpowers_sha256='d'*64,worktree=str(worktree),git_dir=str(git_dir)))
            effect=self.journal.begin_effect(run['run_id'],owner,dict(kind='worktree_create',source_sha=self.source,branch=run['branch'],worktree=str(worktree),git_dir=str(git_dir)))
            self.git('worktree','add','-b',run['branch'],str(worktree),self.source)
            self.journal.finish_effect(effect['effect_id'],owner,dict(status='completed',source_sha=self.source))
            manifest=inputs.product_manifest(worktree,dict(self.policy,git_dir=str(git_dir)))
            checkpoint=dict(checkpoint_sha=self.source,product_sha256=inputs.digest_manifest(manifest))
            binding=inputs.stage_manifest(run,checkpoint,stage='spec',generation=1,prior_receipt=None,checks=None)
            return self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='ready',manifest=binding))

    def test_initial_actual_worktree_ready_and_dead_owner_handoff(self):
        import sys
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import uid
        code="from pathlib import Path; import sys; from tests.test_pipeline_inputs import InitialReadyCheckpointTests; from tests.test_pipeline_journal import uid; f=InitialReadyCheckpointTests(); f.root=Path(sys.argv[1]); f.source=f.git('rev-parse','HEAD').strip(); f.policy=dict(allowed_paths=['a.ps1','spec.md','plan.md','assets/','docs/tasks/','evidence/'],spec_path='spec.md',plan_path='plan.md',evidence_dir='evidence/',source_sha=f.source); r=f.prepared_ready(uid()); print(r['run_id'])"
        child=subprocess.run([sys.executable,'-c',code,str(self.root)],env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')},capture_output=True,timeout=20)
        self.assertEqual(child.returncode,0,child.stderr)
        run_id=child.stdout.decode().strip(); store=PipelineJournal(self.root.parent/'private/initial.sqlite3')
        self.assertEqual(store.recover(),[])
        with store.owner(uid()) as owner:
            run=store.claim(owner,1)
            self.assertEqual(run['run_id'],run_id)
            self.assertEqual(run['generation'],1)
            self.assertEqual(run['process_count'],0)
            self.assertEqual(store.history(run_id)['attempts'],[])
            run=store.record(run_id,owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='executing'))
            attempt=store.begin_attempt(run_id,owner,dict(role='spec_executor',manifest=run['manifest'],artifact_names={}))
            self.assertEqual(attempt['role'],'spec_executor')
