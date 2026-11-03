"""Trusted stage authority must come from actual retained journal/Git edges."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest

from tests import test_pipeline_publish as pipeline_fixture
from task_tower import pr_evidence as evidence
from task_tower.pr_policy import policy_fingerprint


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f = pipeline_fixture.PublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.accepted(True)
        for _ in range(3):
            self.f.f.tick()
        self.run = self.f.f.state()
        self.history = self.f.f.journal.history(self.run['run_id'])
        self.task = dict(repository='owner/repo', issue=16, issue_id=self.run['issue_id'],
                         task_id=self.run['task_id'], pr_number=self.f.store.rows[0]['number'],
                         source='pipeline', pipeline_run_id=self.run['run_id'])
        self.snapshot = dict(self.task, head_sha=self.run['checkpoint_sha'], base_sha=self.run['base_sha'])
        self.context = evidence.StageAuthorityContext(
            pipeline_journal=self.f.f.journal, pipeline_config=self.f.config,
            git_mirror=Path(self.run['worktree']), criteria_sha256=self.run['criteria_sha256'],
            superpowers_sha256=self.run['superpowers_sha256'], profile_sha256=self.run['profile_fingerprint'])

    def test_actual_chain_and_single_host_md_roundtrip(self):
        authority = evidence.load_stage_authority(self.task,self.snapshot,context=self.context)
        self.assertEqual(len(authority['receipts']),3)
        self.assertEqual(len(authority['artifacts']),1)
        artifact = authority['artifacts'][0]
        raw = base64.b64decode(artifact['content_base64'],validate=True)
        self.assertIn(b'## spec',raw)
        self.assertIn(b'## development',raw)
        self.assertIn(b'## test',raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),artifact['raw_sha256'])
        self.assertEqual(authority['authority_sha256'],policy_fingerprint({k:v for k,v in authority.items() if k!='authority_sha256'}))
        json.dumps(authority)

    def test_private_projection_maps_real_md_and_refuses_tracked_card(self):
        authority=evidence.load_stage_authority(self.task,self.snapshot,context=self.context)
        root=Path(self.run['worktree']); head=self.run['checkpoint_sha']; base=self.run['base_sha']
        tree=self.f.real_git(root,'rev-parse',head+'^{tree}').decode().strip()
        # A real immutable merge object with exact reviewed parents and tree.
        merge=self.f.real_git(root,'-c','user.name=Fixture','-c','user.email=f@example.invalid','commit-tree',tree,'-p',base,'-p',head,'-m','merged').decode().strip()
        proof=dict(repository='owner/repo',pr_number=self.task['pr_number'],issue=16,issue_id=self.run['issue_id'],task_id=self.run['task_id'],
                   head_sha=head,base_sha=base,merge_commit=merge,main_sha=merge,parents=[base,head])
        mirror=self.f.f.fixture.root/'private-main'
        self.f.real_git(root,'clone','--shared','--no-checkout',str(root),str(mirror))
        self.f.real_git(mirror,'-c','core.autocrlf=false','checkout','--detach',merge)
        bad=copy.deepcopy(authority);bad['artifacts'][0]['sha256']='0'*64
        bad['authority_sha256']=policy_fingerprint({k:v for k,v in bad.items() if k!='authority_sha256'})
        with self.assertRaises(ValueError): evidence.project_postmerge_card(bad,proof,mirror)
        card_path=evidence.project_postmerge_card(authority,proof,mirror)
        from task_tower import tasks
        card=tasks.load_task(card_path)
        self.assertEqual(card['status'],'awaiting_merge')
        self.assertEqual(len({r['evidence'] for r in card['stages'].values() if r['status']=='accepted'}),1)
        self.assertEqual(self.f.real_git(mirror,'ls-files','--',str(card_path.relative_to(mirror))),b'')
        before=card_path.read_bytes()
        self.assertEqual(evidence.project_postmerge_card(authority,proof,mirror).read_bytes(),before)
        # Compatibility proof uses a real full-profile custom process and the
        # genuine public predicate; no callback replaces verified_done.
        import uuid
        from types import SimpleNamespace
        from tests.test_reviewer import loaded_postmerge_profile
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower.reviewer import ReviewRunner
        from task_tower.postmerge_worker import Worker
        from task_tower.github_publication import GitHubPublisher,publication_id,LIFECYCLE,canonical
        from task_tower.github_tasks import GitHubTasks,replace_metadata
        from task_tower.project_worker import verified_done
        self.f.real_git(mirror,'update-ref','refs/remotes/origin/main',merge)
        bundle=dict(repository='owner/repo',pr_number=self.task['pr_number'],merge_commit=merge,run_id='100',attempt='1',
                    task_ids=[self.task['task_id']],platforms={'windows':'passed'})
        source=SimpleNamespace(poll=lambda:[bundle])
        profile,selected=loaded_postmerge_profile(self.f.f.fixture.root/'compat-install',mirror,self.task['task_id'],issue=16,issue_id=self.run['issue_id'],pr_number=self.task['pr_number'])
        self.assertEqual(selected['readiness_reason'],'writer_boundary_required')
        private_binding={k:proof[k] for k in ('repository','pr_number','issue','issue_id','task_id','head_sha','base_sha')}
        private_binding.update(input_sha256='a'*64,policy_sha256='b'*64)
        values=dict(pr_binding=private_binding,merge_commit=merge,bundle_sha256=policy_fingerprint(bundle),snapshot_sha256=tasks.task_snapshot(card),
            reviewer_instance_id=str(uuid.uuid4()),excluded_instances=tuple(authority['executor_instances']+authority['reviewer_instances']),
            profile_sha256=profile_fingerprint(profile),instructions_sha256=profile_fingerprint(profile['superpowers']))
        material=dict(values,excluded_instances=list(values['excluded_instances']))
        review_binding=evidence.PostmergeReviewBinding(**values,effect_id=str(uuid.uuid4()),request_sha256=policy_fingerprint(dict(binding=material,task=card,bundle=bundle)))
        worker=Worker(dict(project=str(mirror),repository='owner/repo',required_platforms=['windows']),source,ReviewRunner(profile),refresh=lambda:None)
        row=worker.review_one(self.task['task_id'],bundle,review_binding=review_binding)
        issue=dict(id=self.run['issue_id'],number=16,state='closed',state_reason='completed',
            body=replace_metadata('Fixture task',dict(version=1,kind='task',task_id=self.task['task_id'])))
        comments=[]
        def transport(method,url,headers,payload,limit):
            path=url.removeprefix('https://api.github.com/repos/owner/repo')
            if method!='GET': raise AssertionError('Compatibility verification must be read-only')
            return json.dumps({'status':'identical'} if path.startswith('/compare/') else comments if '/comments?' in path else issue).encode()
        store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
        publisher=GitHubPublisher('owner/repo',dict(issue_tasks={self.task['task_id']:16},publisher_account='bot'),store=store,verify_source=source.poll)
        receipt=publisher.receipt(card_path,bundle,row,['windows']);receipt['issue_id']=issue['id']
        lifecycle=dict(remote_attempt=dict(kind='local-postmerge',status='done',commit=merge,publication_id=publication_id(receipt),receipt=receipt),status='done')
        comments.append(dict(id=1,user={'login':'bot'},body=LIFECYCLE+canonical(lifecycle)+'\n-->'))
        self.assertTrue(verified_done(SimpleNamespace(repository='owner/repo',trusted_publishers=['bot']),store,source,issue))
        self.assertEqual(set(receipt['evidence']),{'spec','development','test','postmerge'})
        self.f.real_git(mirror,'add','--',str(card_path.relative_to(mirror)))
        with self.assertRaises(ValueError): evidence.project_postmerge_card(authority,proof,mirror)

    def test_completed_observed_pr_and_original_contributor_are_required(self):
        for mutation in ('pr','executor','reviewer','superseded','rework','contribution_tree'):
            h=copy.deepcopy(self.history)
            if mutation=='pr': h['effects'][-1]['status']='unknown'
            elif mutation=='executor': h['attempts'][0]['evidence']['cleanup_confirmed']=False
            elif mutation=='reviewer': h['verdicts'][-1]['body']['reviewer_attempt_id']=h['attempts'][0]['attempt_id']
            elif mutation=='superseded': h['verdicts'][0]['superseded']=True
            elif mutation=='rework':
                h['events'].append(dict(kind='rework_applied',target_stage='spec',generation_floor=100))
            else:
                from task_tower.pipeline_inputs import digest_manifest
                commit=next(e for e in h['effects'] if e['kind']=='commit' and e['intent']['contributing_executor_attempt_id'] is not None)
                commit['intent']['tree']='e'*40;commit['intent_sha256']=digest_manifest(commit['intent'])
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                evidence.validate_pipeline_publication(self.context,self.run,h,self.snapshot)

    def test_wrong_head_criteria_and_public_md_never_authorize(self):
        from dataclasses import replace
        with self.assertRaises(ValueError):
            evidence.load_stage_authority(self.task,dict(self.snapshot,head_sha='a'*40),context=self.context)
        with self.assertRaises(ValueError):
            evidence.load_stage_authority(self.task,self.snapshot,context=replace(self.context,criteria_sha256='0'*64))
        with self.assertRaises(ValueError):
            evidence.load_stage_authority(self.task,self.snapshot,context=evidence.StageAuthorityContext(
                pipeline_journal=None,pipeline_config=None,git_mirror=self.context.git_mirror,
                criteria_sha256=self.run['criteria_sha256'],superpowers_sha256=self.run['superpowers_sha256'],profile_sha256=self.run['profile_fingerprint']))

    def test_snapshot_reads_existing_database_without_mutation(self):
        path=self.f.f.journal.path
        before=path.read_bytes()
        snapshot=evidence.read_pipeline_authority(self.context,self.run['run_id'])
        self.assertEqual(snapshot['run']['checkpoint_sha'],self.run['checkpoint_sha'])
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(Path(str(path)+'-journal').exists())

    def test_changed_retained_role_and_host_check_results_cannot_grant_authority(self):
        profile=self.f.config['profiles'][self.run['profile_id']]
        for role in ('spec_reviewer','host_check'):
            attempt=next(a for a in self.history['attempts'] if a['role']==role)
            path=Path(profile['runs_dir'])/attempt['artifacts']['result']
            original=path.read_bytes()
            path.write_bytes(b'{}')
            try:
                with self.subTest(role=role),self.assertRaises(ValueError):
                    evidence.load_stage_authority(self.task,self.snapshot,context=self.context)
            finally: path.write_bytes(original)

    def test_changed_original_branch_does_not_replace_immutable_objects(self):
        self.f.real_git(self.run['worktree'],'update-ref','refs/heads/unrelated',self.run['source_sha'])
        self.f.real_git(self.run['worktree'],'symbolic-ref','HEAD','refs/heads/unrelated')
        authority=evidence.load_stage_authority(self.task,self.snapshot,context=self.context)
        self.assertEqual(authority['head_sha'],self.run['checkpoint_sha'])


class ReadOnlySourceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from task_tower.pipeline_journal import PipelineJournal
        from tests.test_pipeline_journal import request,policy
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.path=self.root/'pipeline.db'
        self.j=PipelineJournal(self.path); self.run_id=self.j.submit(request(),policy())['receipt_id']
        self.context=evidence.StageAuthorityContext(self.j,None,self.root,'a'*64,'b'*64,'c'*64)

    def inventory(self):
        return {p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}

    def test_legacy_labels_and_private_assertions_have_no_accepting_fallback(self):
        from dataclasses import replace
        task=dict(repository='owner/repo',issue=9,issue_id=900,task_id='TT-LEGACY-1',pr_number=1,source='legacy')
        before=self.inventory()
        context=replace(self.context,legacy_provenance={'original_reviewer':'review-agent','approved':True})
        with self.assertRaisesRegex(ValueError,'stage_authority_unverified'):
            evidence.load_stage_authority(task,dict(task,head_sha='a'*40,base_sha='b'*40),context=context)
        self.assertEqual(self.inventory(),before)

    def test_missing_and_hot_source_never_initializes_or_recovers(self):
        from dataclasses import replace
        import sys
        from task_tower.pipeline_journal import PipelineJournal
        from task_tower.processes import run_command
        missing=self.root/'absent'/'missing.db'
        with self.assertRaises(ValueError): evidence.read_pipeline_authority(replace(self.context,pipeline_journal=PipelineJournal(missing)),self.run_id)
        self.assertFalse(missing.parent.exists())
        code="import sqlite3,sys,os\ndb=sqlite3.connect(sys.argv[1]);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=1');db.execute('PRAGMA cache_spill=ON');db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE uncommitted_spill(value)');db.executemany('INSERT INTO uncommitted_spill VALUES(?)',[(bytes(4096),)]*80);os._exit(23)"
        execution=run_command([sys.executable,'-c',code,str(self.path)],self.root,20,cancel_requested=lambda:False)
        self.assertEqual(execution['exit_code'],23); self.assertTrue(execution['cleanup_confirmed'])
        before=self.inventory()
        with self.assertRaises(ValueError) as raised: evidence.read_pipeline_authority(self.context,self.run_id)
        self.assertEqual(raised.exception.__cause__.sqlite_errorname,'SQLITE_READONLY_ROLLBACK')
        self.assertEqual(self.inventory(),before)

    def test_wal_and_foreign_schema_refuse_without_source_changes(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            before=self.inventory()
            with self.assertRaises(ValueError): evidence.read_pipeline_authority(self.context,self.run_id)
            self.assertEqual(self.inventory(),before)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA journal_mode=DELETE');db.execute('CREATE VIEW unexpected AS SELECT 1');db.commit()
        before=self.inventory()
        with self.assertRaises(ValueError): evidence.read_pipeline_authority(self.context,self.run_id)
        self.assertEqual(self.inventory(),before)

    def test_one_transaction_blocks_interleaved_commit_and_returns_consistent_source(self):
        import sqlite3
        from contextlib import closing
        from unittest.mock import patch
        original=self.j._validate_db; observed=[]
        def validate(db):
            original(db)
            if db.in_transaction:
                observed.append(True)
                with closing(sqlite3.connect(self.path,timeout=0)) as writer:
                    writer.execute('BEGIN IMMEDIATE')
                    writer.execute("UPDATE runs SET updated_at='2099-01-01T00:00:00+00:00'")
                    with self.assertRaises(sqlite3.OperationalError): writer.commit()
                    writer.rollback()
        before=self.inventory()
        with patch.object(self.j,'_validate_db',validate): snapshot=evidence.read_pipeline_authority(self.context,self.run_id)
        self.assertEqual(observed,[True]);self.assertNotEqual(snapshot['run']['updated_at'],'2099-01-01T00:00:00+00:00')
        self.assertEqual(before,self.inventory())

    def test_v1_and_pipeline_v2_keep_original_bom_and_lone_cr_semantics(self):
        from task_tower import tasks
        from task_tower.pipeline_inputs import canonical_artifact
        path=self.root/'old.md';path.write_bytes(b'\xef\xbb\xbfline\rnext\r\n')
        self.assertEqual(tasks._hash(path,self.root,'sha256-utf8-lf-v1')[0],hashlib.sha256(b'\xef\xbb\xbfline\rnext\n').hexdigest())
        with self.assertRaises(ValueError): canonical_artifact(path.read_bytes())
        self.assertEqual(canonical_artifact(b'line\rnext\r\n'),b'line\nnext\n')


if __name__=='__main__': unittest.main()
