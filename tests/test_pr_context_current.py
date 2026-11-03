"""Genuine retained stage processes/Git objects through actual installed loaders."""
import copy
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from task_tower.executor_profiles import load_executor_config
from task_tower.pipeline import _runtime
from task_tower.pr_context import PRHostContext, PRPrivateInputs
from task_tower.pr_policy import policy_fingerprint
from task_tower.pr_source import PRSource, _git
from task_tower.project_connections import load_connections
from tests import test_pipeline_policy as policy_fixture
from tests import test_pipeline_publish as publication_fixture
from tests import test_pr_source as source_fixture


def installed_load(f):
    """Real fixture installation before actual admission, never boolean authority."""
    connections=f.root/'connections.json'; executor=f.root/'executor.json'
    projects=[dict(id='fixture',repository=c.repository,checkout=str(c.checkout),
        runner_label=c.runner_label,trusted_publishers=c.trusted_publishers) for c in f.connections]
    connections.write_text(json.dumps(dict(version=1,projects=projects)),encoding='utf-8')
    f.connections=load_connections(connections)
    f.executor.setdefault('version',1)
    f.profile.setdefault('max_attempts',1)
    executor.write_text(json.dumps(f.executor),encoding='utf-8')
    normalized=load_executor_config(executor,f.connections)
    f.profile.clear(); f.profile.update(normalized['profiles']['local'])
    executor.write_text(json.dumps(f.executor),encoding='utf-8')
    f.path.write_text(json.dumps(f.value),encoding='utf-8')
    return _runtime(SimpleNamespace(connections=connections,executor_config=executor,
        config=f.path,journal=f.root/'publish.db'))[2]


class CurrentAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=publication_fixture.PublicationTests()
        try:
            with patch.object(policy_fixture.PipelinePolicyTests,'load',installed_load):
                cls.f.setUp(); cls.f.accepted(True)
                for _ in range(3): cls.f.f.tick()
            cls.fixture=cls.f.f.fixture; cls.stage_run=cls.f.f.state()
            cls.root=cls.fixture.root
            cls.policy=cls.root/'pr.json'; cls.journal=cls.root/'pr.db'
            helper=source_fixture.SourceTests(); cls.helper=helper
            cls.checks=helper.fixture()['actions']['checks']
            cls.raw=dict(version=1,executor_config=str(cls.root/'executor.json'),
                pipeline_journal=str(cls.f.f.journal.path),legacy_provenance=None,
                projects=[dict(repository=cls.fixture.connections[0].repository,base_ref='refs/heads/main',
                    publisher_account='owner',merge_enabled=False,
                    exclusive_writer=dict(enabled=False,boundary_id='fixture',asserted_by='owner'),
                    tasks=[dict(issue=16,issue_id=123,task_id='TT-PIPELINE-001',pr_number=7,
                        source='pipeline',pipeline_run_id=cls.stage_run['run_id'],legacy_card=None,
                        reviewer_profile='local',postmerge_profile='local',
                        required_checks=[dict(context=c['name'],app_id=15368) for c in cls.checks],
                        required_platforms=['linux','windows','macos'])])])
            cls.policy.write_text(json.dumps(cls.raw),encoding='utf-8')
            cls.inputs=PRPrivateInputs(cls.root/'connections.json',cls.policy,cls.journal,cls.fixture.path)
        except BaseException:
            cls.f.doCleanups(); raise

    @classmethod
    def tearDownClass(cls): cls.f.doCleanups()

    def context(self):
        c=PRHostContext.from_inputs(self.inputs); self.addCleanup(c.close); return c

    def source(self,context,change=None):
        run=self.stage_run; base=run['base_sha']; head=run['checkpoint_sha']
        logs=self.root/'fixture-read-git'; logs.mkdir(exist_ok=True)
        commits=_git(Path(run['worktree']),['rev-list','--reverse',base+'..'+head],logs).decode().splitlines()
        files=_git(Path(run['worktree']),['diff','--name-only',base,head,'--'],logs).decode().splitlines()
        issue=copy.deepcopy(self.fixture.snapshot()['owner/repo']['issues'][16]); issue['state_reason']=None
        pr=copy.deepcopy(self.f.store.rows[0]); pr.update(draft=False,merged=False,mergeable=True,
            mergeable_state='clean',commits=len(commits),changed_files=len(files))
        def transform(path,data,count):
            data=json.loads(json.dumps(data).replace('a'*40,head).replace('b'*40,base).replace('trusted','owner'))
            def refs(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key=='pull_requests':
                            for row in item: row['number']=7
                        refs(item)
                elif isinstance(value,list):
                    for item in value: refs(item)
            refs(data)
            if path=='/pulls/1': data=copy.deepcopy(pr)
            elif path=='/issues/2': data=copy.deepcopy(issue)
            elif path=='/pulls/1/commits': data=[dict(sha=sha) for sha in commits]
            elif path=='/pulls/1/files': data=[dict(filename=name) for name in files]
            if change is not None: data=change(path,data,count)
            return data
        backing,_,_=self.helper.whole_source(transform)
        def transport(method,url,headers,body,timeout,max_bytes):
            url=url.replace(head,'a'*40).replace(base,'b'*40).replace('/pulls/7','/pulls/1').replace('/issues/16','/issues/2')
            return backing.transport(method,url,headers,body,timeout,max_bytes)
        loaded=context._fresh_inputs()
        return PRSource(loaded['connections'][0],loaded['policy'],transport=transport)

    def fetch_transport(self,mirror,url,base,head,logs):
        self.assertEqual(url,'https://github.com/owner/repo.git')
        self.assertEqual((base,head),(self.stage_run['base_sha'],self.stage_run['checkpoint_sha']))
        # Only the network fetch boundary is replaced; actual contained hardened
        # Git copies immutable fixture objects from the scratch source worktree.
        _git(mirror,['-c','protocol.file.allow=always','fetch','--no-tags','--no-recurse-submodules',
            '--',self.stage_run['worktree'],base,head],logs)

    def identity(self):
        return dict(repository='owner/repo',issue=16,issue_id=123,task_id='TT-PIPELINE-001',pr_number=7)

    def current(self,context,source):
        self.assertTrue(callable(getattr(context,'current',None)), 'Genuine current authority factory is missing')
        with patch('task_tower.pr_context._fetch',side_effect=self.fetch_transport,create=True):
            return context.current(source,self.identity())

    def test_actual_installed_current_authority_uses_retained_processes_and_immutable_objects(self):
        context=self.context(); source=self.source(context)
        before=self.f.f.journal.path.read_bytes()
        fresh=self.current(context,source)
        self.assertEqual(set(fresh),{'task','snapshot','authority','authority_error','policy_sha256','private_inputs_sha256'})
        self.assertTrue(fresh['snapshot']['ready'],fresh['snapshot']['reasons'])
        self.assertIsNone(fresh['authority_error']); self.assertEqual(len(fresh['authority']['receipts']),3)
        self.assertEqual(fresh['authority']['head_sha'],self.stage_run['checkpoint_sha'])
        self.assertEqual(fresh['authority']['run_id'],self.stage_run['run_id'])
        self.assertEqual(before,self.f.f.journal.path.read_bytes()); self.assertFalse(self.journal.exists())
        self.assertEqual(fresh['private_inputs_sha256'],context.private_inputs_sha256)

    def test_actual_criteria_drift_cannot_grant_authority(self):
        context=self.context()
        def change(path,data,count):
            if path=='/issues/2': data['title']='Changed criteria'
            return data
        fresh=self.current(context,self.source(context,change))
        self.assertIsNone(fresh['authority']); self.assertEqual(fresh['authority_error'],'stage_authority_unverified')

    def test_private_revocation_and_foreign_source_refuse_before_git(self):
        context=self.context(); source=self.source(context)
        source.policy=copy.deepcopy(source.policy); source.policy['max_pages']-=1
        with patch('task_tower.pr_context._fetch',side_effect=AssertionError('foreign source reached fetch'),create=True):
            with self.assertRaises(ValueError): context.current(source,self.identity())

    def test_foreign_checkout_origin_is_hard_refusal_not_negative_authority(self):
        context=self.context(); source=self.source(context)
        checkout=self.fixture.profile['checkout']
        self.f.real_git(checkout,'remote','set-url','origin','https://github.com/foreign/repository.git')
        try:
            with self.assertRaises(ValueError): self.current(context,source)
        finally:
            self.f.real_git(checkout,'remote','set-url','origin','https://github.com/owner/repo.git')

    def test_retained_actual_role_result_mutation_refuses_stage_authority(self):
        context=self.context(); source=self.source(context)
        attempt=next(a for a in self.f.f.journal.history(self.stage_run['run_id'])['attempts'] if a['role']=='spec_reviewer')
        result=Path(self.fixture.profile['runs_dir'])/attempt['artifacts']['result']; original=result.read_bytes()
        try:
            result.write_bytes(original+b' ')
            fresh=self.current(context,source)
            self.assertIsNone(fresh['authority']); self.assertEqual(fresh['authority_error'],'stage_authority_unverified')
        finally: result.write_bytes(original)

    def test_private_byte_drift_during_object_fetch_never_returns_proof(self):
        context=self.context(); source=self.source(context)
        path=self.fixture.path; original=path.read_bytes()
        def drift(*args):
            self.fetch_transport(*args); path.write_bytes(original+b' ')
        try:
            with patch('task_tower.pr_context._fetch',side_effect=drift):
                with self.assertRaises(ValueError): context.current(source,self.identity())
        finally: path.write_bytes(original)

    def test_mutating_returned_context_and_rehash_cannot_change_private_mapping(self):
        context=self.context(); source=self.source(context)
        mutable=context._fresh_inputs()
        mutable['policy']['projects'][0]['tasks'][0]['pipeline_run_id']='00000000-0000-4000-8000-000000000001'
        mutable['forged_policy_sha256']=policy_fingerprint(mutable['policy'])
        mutable['pipeline_config']['_authority_check']=lambda:True
        identity=self.identity(); identity['pipeline_run_id']='00000000-0000-4000-8000-000000000001'
        with patch('task_tower.pr_context._fetch',side_effect=AssertionError('forged mapping reached Git')):
            with self.assertRaises(ValueError): context.current(source,identity)
        self.assertEqual(context._fresh_inputs()['policy']['projects'][0]['tasks'][0]['pipeline_run_id'],self.stage_run['run_id'])

    def test_source_changes_after_authority_audit_refuse_current_proof(self):
        context=self.context()
        def change(path,data,count):
            if path=='/pulls/1' and count>2: data['title']='Changed while reading authority'
            return data
        with self.assertRaises(ValueError): self.current(context,self.source(context,change))

    def test_v2_source_copy_is_refused_without_changing_original_source(self):
        before=self.f.f.journal.path.read_bytes()
        copy_path=self.root/'v2-copy.db'; copy_path.write_bytes(before)
        with sqlite3.connect(copy_path) as db: db.execute('PRAGMA user_version=2')
        policy=copy.deepcopy(self.raw); policy['pipeline_journal']=str(copy_path)
        policy_path=self.root/'v2-pr.json'; policy_path.write_text(json.dumps(policy),encoding='utf-8')
        inputs=PRPrivateInputs(self.inputs.connections_path,policy_path,self.root/'v2-pr.db',self.inputs.pipeline_config_path)
        with self.assertRaises(ValueError): PRHostContext.from_inputs(inputs)
        self.assertEqual(before,self.f.f.journal.path.read_bytes())

