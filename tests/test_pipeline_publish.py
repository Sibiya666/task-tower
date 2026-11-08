import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

from task_tower import pipeline_worker as worker
from tests import test_pipeline_worker


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pipeline_worker.WorkerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture
        self.config = self.f.config
        from task_tower import pipeline_publish
        self.publish = pipeline_publish
        self.config['_publisher'] = lambda *args: pipeline_publish.publish_one(*args, store_factory=lambda c: self.store)
        self.store = Store()
        self.store.run = self.f.state
        self.bare = self.f.fixture.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(self.bare)], check=True, capture_output=True)
        self.calls = []
        from task_tower.pipeline_inputs import _git
        self.real_git = _git
        def transport(root, *args, **kwargs):
            if 'ls-remote' in args or 'push' in args:
                self.calls.append(args)
                args = tuple(str(self.bare) if a == 'origin' else a for a in args)
            return _git(root, *args, **kwargs)
        self.transport = patch.object(pipeline_publish, '_git', side_effect=transport)
        self.transport.start(); self.addCleanup(self.transport.stop)

    def accepted(self, enabled=False):
        f = self.f.fixture
        f.row['publish']['enabled'] = enabled
        self.config = f.load()
        # Reload before admission; the policy fingerprint must remain host derived.
        self.f.config = self.config
        self.config['_publisher'] = lambda *args: self.publish.publish_one(*args, store_factory=lambda c: self.store)
        if enabled:
            # Submission binds installed policy. Recreate the untouched initial queue.
            from task_tower.pipeline_journal import PipelineJournal
            from task_tower.pipeline_inputs import digest_manifest
            import uuid
            self.f.journal = PipelineJournal(f.root/'publish.db', checkouts=(Path(f.profile['checkout']),))
            envelope = dict(profile_id='local', profile_fingerprint=digest_manifest(f.profile), policy_sha256=self.config['policy_sha256'], component_keys=['core'], limits={k:self.config[k] for k in ('task_timeout_seconds','max_processes','max_reworks','role_timeout_seconds','log_max_bytes')})
            self.f.run_id = self.f.journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=f.row['task_id'],runner_label='local'),envelope)['receipt_id']
        self.f.until(lambda r,h:r['state']=='ready' and worker.next_action(r,h)=='publish')
        self.real_git(self.f.state()['worktree'], 'remote', 'add', 'origin', 'https://github.com/owner/repo.git')

    def test_only_current_three_stage_acceptance_can_publish(self):
        self.f.tick()
        r=self.f.state()
        with self.assertRaises(ValueError): self.publish.project_evidence(r,self.f.journal.history(r['run_id']),self.config['tasks'][0])
        self.assertEqual(self.calls,[])

    def test_projection_does_not_change_accepted_product_hash(self):
        self.accepted()
        before=self.f.state()['manifest']['product_sha256']
        answer=self.f.tick()
        self.assertEqual(answer['status'],'ready_for_pr')
        r=self.f.state(); h=self.f.journal.history(r['run_id'])
        self.assertEqual(r['manifest']['product_sha256'],before)
        final=h['effects'][-1]
        self.assertIsNone(final['intent']['contributing_executor_attempt_id'])
        self.assertIsNotNone(final['intent']['evidence_manifest_sha256'])
        self.assertNotEqual(r['checkpoint_sha'],r['manifest']['checkpoint_sha'])
        self.assertEqual(self.calls,[])
        self.assertEqual(self.store.writes,[])

    def test_host_push_then_pr_with_no_closing_keywords(self):
        self.accepted(True)
        accepted=self.f.state()['manifest']['checkpoint_sha']
        self.assertEqual(self.f.tick()['status'],'ready')
        self.assertNotEqual(self.f.state()['checkpoint_sha'],accepted)
        self.assertEqual(self.f.tick()['status'],'ready')
        self.assertEqual(self.f.tick()['status'],'awaiting_pr')
        self.assertEqual(len(self.store.writes),1)
        payload=self.store.writes[0]
        self.assertEqual(payload['body'].count('\nTask-Tower: TT-PIPELINE-001\n'),1)
        import re
        self.assertIsNone(re.search(r'(?i)\b(closes|fixes|resolves)\b',payload['body']))
        self.assertEqual(self.real_git(self.bare,'rev-parse','refs/heads/'+self.f.state()['branch']).decode().strip(),self.f.state()['checkpoint_sha'])
        self.assertNotIn('--force',[a for call in self.calls for a in call])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows delete-sharing regression')
    def test_final_commit_cleanup_sharing_violation_retries_without_replay(self):
        from tests.fixtures.windows_file_lease import DeleteLease
        self.accepted(True)
        journal = self.f.journal
        before = journal.history(self.f.run_id)
        finish_effect = journal.finish_effect
        remove = tempfile.TemporaryDirectory._rmtree
        leases, directories, errors = [], [], []

        def finish(effect_id, owner, observation):
            result = finish_effect(effect_id, owner, observation)
            effect = next(e for e in journal.history(self.f.run_id)['effects']
                          if e['effect_id'] == effect_id)
            if (effect['kind'] == 'commit'
                    and effect['intent']['evidence_manifest_sha256'] is not None):
                indexes = list((journal.path.parent / ('checkpoint-' + self.f.run_id)).glob('*/index'))
                self.assertEqual(len(indexes), 1)
                leases.append(DeleteLease(indexes[0]))
                directories.append(indexes[0].parent)
            return result

        def cleanup(name, *args, **kwargs):
            try:
                return remove(name, *args, **kwargs)
            except PermissionError as error:
                if directories and Path(name) == directories[0]:
                    errors.append(getattr(error, 'winerror', None))
                    for lease in leases:
                        lease.close()
                raise

        try:
            with patch.object(journal, 'finish_effect', side_effect=finish), \
                    patch.object(tempfile.TemporaryDirectory, '_rmtree', side_effect=cleanup):
                result = self.f.tick()
        finally:
            for lease in leases:
                lease.close()
        history = journal.history(self.f.run_id)
        self.assertEqual(errors, [32])
        self.assertEqual(result['status'], 'ready', result['reason'])
        self.assertFalse(directories[0].exists())
        self.assertEqual(len(history['effects']) - len(before['effects']), 1)
        self.assertEqual(history['effects'][-1]['kind'], 'commit')
        self.assertEqual(history['effects'][-1]['status'], 'completed')
        self.assertEqual(len(history['verdicts']), 3)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.writes, [])

    def test_lost_response_never_repeats_write(self):
        self.accepted(True); self.f.tick(); self.f.tick()
        self.store.lost=True
        self.assertEqual(self.f.tick()['status'],'unknown')
        self.f.tick()
        self.assertEqual(self.f.state()['state'],'unknown')
        self.assertEqual(len(self.store.writes),1)
        e=self.f.journal.history(self.f.run_id)['effects'][-1]
        self.store.rows=[]
        self.config['_journal']=self.f.journal
        observed=self.publish.inspect_effect(self.config,e,store_factory=lambda c:self.store)
        self.assertEqual(observed['status'],'unknown')
        self.assertEqual(len(self.store.writes),1)

    def test_exact_task_marker_and_private_mapping_required(self):
        self.accepted()
        run=self.f.state();history=self.f.journal.history(run['run_id']);task=self.config['tasks'][0]
        for key,value in [('task_id','TT-OTHER-001'),('issue',99),('repository','other/repo')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.publish.project_evidence(run,history,dict(task,**{key:value}))
        projection=self.publish.project_evidence(run,history,task)
        contents=b''.join(projection['files'].values())
        self.assertNotIn(str(self.f.fixture.root).encode(),contents)
        self.assertNotIn(b'\nfixture\n',contents)
        self.assertNotIn(b'Actual task',contents)
        self.assertNotIn(b'projection-',contents)

    def test_remote_repository_and_changed_branch_rejected(self):
        self.accepted(True);self.f.tick();r=self.f.state()
        self.real_git(r['worktree'],'remote','set-url','origin','https://github.com/other/repo.git')
        with self.assertRaises(ValueError):self.publish._remote(r)
        self.real_git(r['worktree'],'remote','set-url','origin','https://github.com/owner/repo.git')
        for key,value in [('remote.origin.pushurl','https://github.com/owner/repo.git'),('url.https://other.invalid/.insteadOf','https://github.com/'),('push.followTags','true'),('remote.origin.vcs','unsafe-helper')]:
            self.real_git(r['worktree'],'config',key,value)
            with self.assertRaises(ValueError):self.publish._remote(r)
            self.real_git(r['worktree'],'config','--unset',key)
        self.real_git(r['worktree'],'symbolic-ref','HEAD','refs/heads/foreign')
        with self.assertRaises(ValueError):self.publish.validate_publication_current(r,self.config['tasks'][0],self.f.journal)
        self.assertEqual(self.calls,[])

    def test_changed_base_invalidates_pending_evidence(self):
        self.accepted(True);self.f.tick();before=len(self.f.journal.history(self.f.run_id)['effects'])
        self.f.fixture.sha='b'*40
        self.assertEqual(self.f.tick()['status'],'needs_input')
        self.assertEqual(len(self.f.journal.history(self.f.run_id)['effects']),before)
        self.assertEqual(self.calls,[])

    def test_commit_push_post_intents_precede_effects(self):
        self.accepted(True)
        from task_tower import pipeline_inputs
        original=pipeline_inputs._git
        def commit(root,*args,**kwargs):
            if 'commit-tree' in args or 'update-ref' in args:
                e=self.f.journal.history(self.f.run_id)['effects'][-1]
                self.assertEqual((e['kind'],e['status']),('commit','intent'))
            return original(root,*args,**kwargs)
        with patch.object(pipeline_inputs,'_git',side_effect=commit):self.f.tick()
        original_transport=self.publish._git
        def push(root,*args,**kwargs):
            if 'push' in args:
                e=self.f.journal.history(self.f.run_id)['effects'][-1]
                self.assertEqual((e['kind'],e['status']),('push','intent'))
            return original_transport(root,*args,**kwargs)
        with patch.object(self.publish,'_git',side_effect=push):self.f.tick()
        self.store.before_post=lambda:self.assertEqual(self.f.journal.history(self.f.run_id)['effects'][-1]['status'],'intent')
        self.assertEqual(self.f.tick()['status'],'awaiting_pr')

    def test_multiple_or_mismatched_prs_fence(self):
        self.accepted(True);self.f.tick();self.f.tick()
        self.store.lookup_conflict=True
        self.assertEqual(self.f.tick()['status'],'unknown')
        self.assertEqual(self.store.writes,[])
        self.f.tick();self.assertEqual(self.store.writes,[])

    def test_final_evidence_mutation_is_not_stage_input_or_acceptance(self):
        self.accepted(True);self.f.tick();r=self.f.state();h=self.f.journal.history(self.f.run_id)
        projection=self.publish.project_evidence(r,h,self.config['tasks'][0])
        p=Path(r['worktree'])/next(iter(projection['files']))
        p.write_text('forged host evidence')
        with self.assertRaises(ValueError):self.publish.validate_publication_current(r,self.config['tasks'][0],self.f.journal)
        self.assertEqual(self.f.tick()['status'],'needs_input')
        self.assertEqual(self.calls,[])

    def test_no_merge_or_issue_close_api(self):
        source=Path(self.publish.__file__).read_text()
        self.assertNotIn("'PATCH'",source)
        self.assertNotIn("'/merge'",source)

    def test_unknown_commit_intent_is_never_replayed(self):
        self.accepted(True)
        from task_tower import pipeline_inputs
        original=pipeline_inputs._git
        def crash(root,*args,**kwargs):
            if 'commit-tree' in args:raise KeyboardInterrupt('effect crash')
            return original(root,*args,**kwargs)
        with patch.object(pipeline_inputs,'_git',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.f.tick()
        effects=self.f.journal.history(self.f.run_id)['effects'];self.assertEqual(effects[-1]['status'],'intent')
        self.assertEqual(self.f.tick()['status'],'unknown')
        self.assertEqual(len(self.f.journal.history(self.f.run_id)['effects']),len(effects))

    def test_final_commit_cannot_reuse_normal_contributor_or_omit_evidence(self):
        self.accepted()
        journal=self.f.journal; run=worker._record(journal,self.f.state(),self.f.owner,state='publishing')
        history=journal.history(run['run_id'])
        executor=[a for a in history['attempts'] if a['role']=='test_executor'][-1]
        intent=dict(kind='commit',parent=run['checkpoint_sha'],tree='b'*40,message='Task Tower publication '+run['run_id'],branch=run['branch'],contributing_executor_attempt_id=None,evidence_manifest_sha256=None)
        with self.assertRaises(ValueError):journal.begin_effect(run['run_id'],self.f.owner,intent)
        intent.update(contributing_executor_attempt_id=executor['attempt_id'],evidence_manifest_sha256='b'*64)
        with self.assertRaises(ValueError):journal.begin_effect(run['run_id'],self.f.owner,intent)

    def test_typed_pr_observation_and_database_reload_reject_forgery(self):
        self.accepted(True);self.f.tick();self.f.tick()
        journal=self.f.journal;run=self.f.state();owner=self.f.owner
        self.assertEqual(run['state'],'ready')
        run=worker._record(journal,run,owner,state='publishing')
        effect=journal.begin_pr_effect(run['run_id'],owner,'owner'); intent=effect['intent']
        payload=dict(title='Task Tower '+run['task_id'],body=self.publish._body(run,intent['marker']),head=run['branch'],base='main')
        row=self.store.request('POST','/pulls',payload)
        observed=self.publish._pr_observation(row,intent,effect['effect_id'])
        for key,value in [('url','https://evil.invalid/pr/7'),('number',True),('author','attacker'),('head_sha','a'*40),('issue',99),('marker','bad')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                journal.finish_effect(effect['effect_id'],owner,dict(observed,**{key:value}))
        with self.assertRaises(ValueError):journal.finish_effect(effect['effect_id'],owner,dict(observed,private_path='secret'))
        for key,value in [('body',payload['body']+'\nTask-Tower: '+run['task_id']),('state','closed'),('user',dict(login='attacker')),('html_url','https://evil.invalid/')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.publish._pr_observation(dict(row,**{key:value}),intent,effect['effect_id'])
        journal.finish_effect(effect['effect_id'],owner,observed)
        from task_tower.pipeline_journal import PipelineJournal
        reloaded=PipelineJournal(journal.path)
        self.assertEqual(reloaded.history(run['run_id'])['effects'][-1]['observation'],observed)
        import sqlite3
        bad=dict(intent,body_sha256='a'*64)
        from task_tower.pipeline_inputs import digest_manifest
        with sqlite3.connect(journal.path) as db:
            db.execute('UPDATE effects SET intent=?,intent_sha256=? WHERE effect_id=?',(json.dumps(bad),digest_manifest(bad),effect['effect_id']))
        with self.assertRaises(ValueError):reloaded.status(run['run_id'])

    def test_push_crash_observes_without_replay_or_unfencing(self):
        self.accepted(True);self.f.tick()
        journal=self.f.journal;original=journal.finish_effect
        def crash(effect_id,owner,observation):
            if journal.history(self.f.run_id)['effects'][-1]['kind']=='push':raise KeyboardInterrupt('after push')
            return original(effect_id,owner,observation)
        with patch.object(journal,'finish_effect',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.f.tick()
        self.assertEqual(self.f.tick()['status'],'unknown')
        effect=journal.history(self.f.run_id)['effects'][-1]
        config=dict(self.config,_journal=journal)
        observed=self.publish.inspect_effect(config,effect,store_factory=lambda c:self.store)
        self.assertEqual(observed['status'],'completed')
        self.assertEqual(journal.status(self.f.run_id)['state'],'unknown')
        self.assertEqual(len([call for call in self.calls if 'push' in call]),1)
        self.assertEqual(self.store.writes,[])

    def test_completed_host_commit_recovery_preserves_stage_checkpoint(self):
        self.accepted(True);accepted=self.f.state()['manifest']
        original=self.publish.freeze_checkpoint
        def crash(*args):
            original(*args)
            raise KeyboardInterrupt('completed host freeze')
        with patch.object(self.publish,'freeze_checkpoint',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.f.tick()
        self.assertEqual(self.f.state()['manifest'],accepted)
        before=len([e for e in self.f.journal.history(self.f.run_id)['effects'] if e['kind']=='commit'])
        self.assertEqual(self.f.tick()['status'],'ready')
        self.assertEqual(len([e for e in self.f.journal.history(self.f.run_id)['effects'] if e['kind']=='commit']),before)
        self.assertEqual(self.f.tick()['status'],'awaiting_pr')

    def test_revocation_after_final_commit_intent_fences_before_git_write(self):
        self.accepted(True)
        journal=self.f.journal;original=journal.begin_effect
        def revoke(*args):
            effect=original(*args)
            self.f.fixture.sha='b'*40
            return effect
        with patch.object(journal,'begin_effect',side_effect=revoke):answer=self.f.tick()
        self.assertEqual(answer['status'],'unknown')
        self.assertEqual(journal.history(self.f.run_id)['effects'][-1]['status'],'intent')
        r=self.f.state()
        self.assertEqual(self.real_git(r['worktree'],'rev-parse','HEAD').decode().strip(),r['manifest']['checkpoint_sha'])
        self.assertEqual(self.calls,[])

    def test_final_commit_crash_after_ref_is_observed_without_mutation(self):
        self.accepted(True)
        from task_tower import pipeline_inputs
        original=pipeline_inputs._git
        def crash(root,*args,**kwargs):
            result=original(root,*args,**kwargs)
            if 'update-ref' in args:raise KeyboardInterrupt('after ref update')
            return result
        with patch.object(pipeline_inputs,'_git',side_effect=crash),self.assertRaises(KeyboardInterrupt):self.f.tick()
        self.assertEqual(self.f.tick()['status'],'unknown')
        journal=self.f.journal;effect=journal.history(self.f.run_id)['effects'][-1]
        before=journal.history(self.f.run_id)
        config=dict(self.config,_journal=journal)
        result=self.publish.inspect_effect(config,effect,store_factory=lambda c:self.store)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(journal.history(self.f.run_id),before)
        self.assertEqual(self.f.state()['state'],'unknown')
        run=self.f.state();intent=effect['intent'];head=result['commit_sha']
        forged=self.real_git(run['worktree'],'-c','user.name=Fixture','-c','user.email=f@example.invalid','commit-tree',intent['tree'],'-p',intent['parent'],data=b'wrong message\n').decode().strip()
        self.real_git(run['worktree'],'update-ref','refs/heads/'+run['branch'],forged,head)
        self.assertEqual(self.publish.inspect_effect(config,effect,store_factory=lambda c:self.store)['status'],'unknown')
        self.assertEqual(journal.history(self.f.run_id),before)


class ContractTests(unittest.TestCase):
    def test_lookup_adopts_one_exact_binding_and_rejects_multiple_or_mismatch(self):
        from task_tower import pipeline_publish as publish
        run=dict(repository='owner/repo',issue=16,issue_id=123,task_id='TT-PIPELINE-001',run_id='11111111-1111-4111-8111-111111111111',checkpoint_sha='a'*40,base_sha='b'*40,branch='pipeline/11111111-1111-4111-8111-111111111111')
        effect_id='22222222-2222-4222-8222-222222222222';marker='<!-- task-tower:pipeline:v1 '+run['run_id']+' '+effect_id+' -->'
        body=publish._body(run,marker);title='Task Tower '+run['task_id']
        intent=dict(repository=run['repository'],issue=16,issue_id=123,task_id=run['task_id'],run_id=run['run_id'],head_sha=run['checkpoint_sha'],base_sha=run['base_sha'],branch=run['branch'],marker=marker,publisher_account='owner',title_sha256=hashlib.sha256(title.encode()).hexdigest(),body_sha256=hashlib.sha256(body.encode()).hexdigest())
        row=dict(number=7,html_url='https://github.com/owner/repo/pull/7',state='open',title=title,body=body,user=dict(login='owner'),head=dict(sha=run['checkpoint_sha'],ref=run['branch'],repo=dict(full_name='owner/repo')),base=dict(sha=run['base_sha'],ref='main',repo=dict(full_name='owner/repo')))
        class Lookup:
            def __init__(self,rows):self.rows=rows;self.calls=[]
            def request(self,method,path):
                self.calls.append((method,path));return copy.deepcopy(self.rows)
        one=Lookup([row]);self.assertEqual(publish._lookup(one,intent,effect_id)['number'],7)
        self.assertTrue(all(method=='GET' and 'state=all' in path for method,path in one.calls))
        for rows in [[row,row],[dict(row,body=body+'changed')],[dict(row,user=dict(login='attacker'))]]:
            with self.assertRaises(ValueError):publish._lookup(Lookup(rows),intent,effect_id)
        for side in ('head','base'):
            bad=copy.deepcopy(row);bad[side]['sha']='c'*40
            with self.assertRaises(ValueError):publish._lookup(Lookup([bad]),intent,effect_id)
        exhausted=Lookup([row]*100)
        with self.assertRaises(ValueError):publish._lookup(exhausted,intent,effect_id)
        self.assertEqual(len(exhausted.calls),10)
        self.assertIsNone(publish._lookup(Lookup([]),intent,effect_id))

    def test_github_repository_url_casing_is_bound_and_canonicalized(self):
        from task_tower import pipeline_publish as publish
        run=dict(repository='owner/repo',issue=16,issue_id=123,task_id='TT-PIPELINE-001',run_id='11111111-1111-4111-8111-111111111111',checkpoint_sha='a'*40,base_sha='b'*40,branch='pipeline/11111111-1111-4111-8111-111111111111')
        effect_id='22222222-2222-4222-8222-222222222222';marker='<!-- task-tower:pipeline:v1 '+run['run_id']+' '+effect_id+' -->'
        body=publish._body(run,marker);title='Task Tower '+run['task_id']
        intent=dict(repository=run['repository'],issue=16,issue_id=123,task_id=run['task_id'],run_id=run['run_id'],head_sha=run['checkpoint_sha'],base_sha=run['base_sha'],branch=run['branch'],marker=marker,publisher_account='owner',title_sha256=hashlib.sha256(title.encode()).hexdigest(),body_sha256=hashlib.sha256(body.encode()).hexdigest())
        row=dict(number=7,html_url='https://github.com/Owner/Repo/pull/7',state='open',title=title,body=body,user=dict(login='Owner'),head=dict(sha=run['checkpoint_sha'],ref=run['branch'],repo=dict(full_name='Owner/Repo')),base=dict(sha=run['base_sha'],ref='main',repo=dict(full_name='Owner/Repo')))
        self.assertEqual(publish._pr_observation(row,intent,effect_id)['url'],'https://github.com/owner/repo/pull/7')
        mixed=copy.deepcopy(row);mixed['html_url']='https://github.com/Sibiya666/task-tower/pull/7'
        for side in ('head','base'):mixed[side]['repo']['full_name']='Sibiya666/task-tower'
        self.assertEqual(publish._pr_observation(mixed,dict(intent,repository='sibiya666/task-tower'),effect_id)['url'],'https://github.com/sibiya666/task-tower/pull/7')
        for url in ['https://github.com/Owner/Repo/PULL/7','https://github.com/Owner/Repo/pull/07','https://github.com/Owner/Repo/pull/7?x=1','https://github.com/Owner/Repo/pull/7#x','https://github.com:443/Owner/Repo/pull/7','https://owner@github.com/Owner/Repo/pull/7','https://github.com/Owner%2FRepo/pull/7','https://github.com/other/repo/pull/7']:
            with self.subTest(url=url),self.assertRaises(ValueError):publish._pr_observation(dict(row,html_url=url),intent,effect_id)


class HostCommitBlobTests(unittest.TestCase):
    def checkpoint(self,long_path=False):
        from task_tower.pipeline_inputs import _git
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name).resolve();worktree=root/'worktree'
        if long_path:
            while len(str(worktree))<180:
                worktree/='x'*max(1,min(40,180-len(str(worktree))-1))
        worktree.mkdir(parents=True)
        hooks=root/'empty-hooks';hooks.mkdir()
        run_id=str(uuid.uuid4());branch='pipeline/'+run_id
        _git(root,'init','--separate-git-dir='+str(root/'git'),'--initial-branch='+branch,str(worktree))
        def commit(message):
            _git(worktree,'-c','core.hooksPath='+str(hooks),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--no-gpg-sign','-m',message)
            return _git(worktree,'rev-parse','HEAD').decode().strip()
        (worktree/'baseline.txt').write_bytes(b'baseline\n');_git(worktree,'add','--','baseline.txt')
        parent=commit('Baseline')
        name='docs/evidence/pipeline-'+run_id+'.md';data=b'# Genuine host projection\n\nExact blob bytes.\n'
        path=worktree/name;path.parent.mkdir(parents=True);path.write_bytes(data)
        _git(worktree,'add','--',name);message='Task Tower publication '+run_id;head=commit(message)
        tree=_git(worktree,'rev-parse','HEAD^{tree}').decode().strip()
        run=dict(run_id=run_id,worktree=str(worktree),branch=branch,manifest=dict(checkpoint_sha=parent),checkpoint_sha=head)
        effect=dict(intent=dict(kind='commit',parent=parent,branch=branch,message=message,contributing_executor_attempt_id=None,evidence_manifest_sha256='b'*64,tree=tree))
        return run,effect,dict(files={name:data},manifest_sha256='b'*64)

    def test_exact_blob_on_normal_path(self):
        from task_tower.pipeline_publish import _commit_object
        run,effect,projection=self.checkpoint()
        self.assertEqual(_commit_object(run,effect,projection)['commit_sha'],run['checkpoint_sha'])

    def test_exact_blob_on_long_cwd_with_short_separate_git_dir(self):
        from task_tower.pipeline_publish import _commit_object
        run,effect,projection=self.checkpoint(long_path=True)
        name=next(iter(projection['files']))
        self.assertGreater(len(run['worktree'])+1+len(run['checkpoint_sha']+':'+name),260)
        self.assertLess(len(str(Path(run['worktree'])/name)),260)
        self.assertEqual(_commit_object(run,effect,projection)['commit_sha'],run['checkpoint_sha'])

    def test_parent_tree_message_file_set_and_blob_forgery_stay_rejected(self):
        from task_tower.pipeline_publish import _commit_object
        run,effect,projection=self.checkpoint()
        for field,value in [('parent','a'*40),('tree','a'*40),('message','Other message')]:
            bad=copy.deepcopy(effect);bad['intent'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):_commit_object(run,bad,projection)
        name=next(iter(projection['files']))
        for files in ({name:b'forged\n'},{},dict(projection['files'],extra=b'extra')):
            with self.subTest(files=list(files)),self.assertRaises(ValueError):_commit_object(run,effect,dict(projection,files=files))


class Store:
    def __init__(self): self.writes=[]; self.rows=[]; self.lost=False; self.lookup_conflict=False;self.before_post=lambda:None
    def request(self,method,path,payload=None):
        if method=='GET' and path.startswith('/pulls?'): return [dict(body='other')] if self.lookup_conflict else copy.deepcopy(self.rows)
        if method=='POST' and path=='/pulls':
            self.before_post()
            self.writes.append(copy.deepcopy(payload))
            run=self.run()
            row=dict(number=7,html_url='https://github.com/owner/repo/pull/7',state='open',title=payload['title'],body=payload['body'],user=dict(login='owner'),head=dict(sha=run['checkpoint_sha'],ref=payload['head'],repo=dict(full_name='owner/repo')),base=dict(sha=run['base_sha'],ref=payload['base'],repo=dict(full_name='owner/repo')))
            self.rows=[row]
            if self.lost: raise OSError('lost response')
            return copy.deepcopy(row)
        raise AssertionError((method,path))
