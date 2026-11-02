"""Production snapshot defaults; replace only authentication/HTTP transport."""
from contextlib import ExitStack, contextmanager
import hashlib
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import urlsplit
import uuid
from unittest.mock import patch

from task_tower.dispatch_selection import collect_snapshot, select_ready
from task_tower.executor_profiles import profile_fingerprint
from task_tower.executor_worker import _git
from task_tower.github_source import GitHubSource
from task_tower.github_tasks import GitHubTasks, replace_metadata
from task_tower.pipeline_inputs import digest_manifest, product_manifest, stage_manifest
from task_tower.pipeline_journal import PipelineJournal
from task_tower.pipeline_policy import admission_authorized
from task_tower.project_worker import verified_done


class DefaultSourceTests(unittest.TestCase):
    def setUp(self):
        from tests.test_pipeline_policy import PipelinePolicyTests
        self.fixture=PipelinePolicyTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        fixture=self.fixture; root=Path(fixture.profile['checkout'])
        pins=Path(fixture.profile['superpowers']['root']); manifest={}
        for name in ('using-superpowers','brainstorming','writing-plans','test-driven-development','verification-before-completion','requesting-code-review'):
            path=pins/name/'SKILL.md'; path.parent.mkdir(); path.write_bytes(b'rules')
            manifest[name+'/SKILL.md']=hashlib.sha256(b'rules').hexdigest()
        fixture.profile['superpowers'].update(manifest=manifest,manifest_sha256=profile_fingerprint(manifest))
        fixture.profile.update(kind='custom',trusted=True,argv=[str(Path(sys.executable).resolve()),str(Path(__file__).parent.resolve()/'fixtures/pipeline_role.py')],runs_dir=str(fixture.root/'runs'))
        for key in ('spec_path','plan_path'):
            path=root/fixture.row[key]; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(key,encoding='utf-8')
        _git(root,'add','docs'); _git(root,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','source artifacts')
        fixture.sha=_git(root,'rev-parse','HEAD')
        self.config=fixture.load(); self.calls=[]; self.transport_unavailable=False
        self.metadata=dict(version=1,kind='task',mode='autonomous',task_id=fixture.row['task_id'],status='open')
        self.issues=[dict(number=16,id=123,state='open',title='Default factory integration',body=replace_metadata('Build from installed policy',self.metadata))]

    def http(self,method,url,headers,payload,limit):
        self.assertEqual(method,'GET'); self.assertIsNone(payload)
        self.assertEqual(headers.get('Authorization'),'Bearer fixture-only-token')
        self.calls.append((method,url))
        if self.transport_unavailable: raise OSError('fixture transport unavailable')
        path=urlsplit(url).path
        if path.endswith('/issues'): result=self.issues
        elif '/comments' in path: result=[]
        elif path.endswith('/git/ref/heads/main'): result=dict(object=dict(sha=self.fixture.sha))
        elif '/issues/' in path: result=next(issue for issue in self.issues if str(issue['number'])==path.rsplit('/',1)[-1])
        elif path.endswith('/actions/workflows/postmerge.yml/runs'): result=dict(workflow_runs=[])
        else: self.fail('Unexpected fixture HTTP path: '+path)
        return json.dumps(result).encode('utf-8')

    @contextmanager
    def transport(self):
        # Constructors, factory selection, metadata, lifecycle, continuation and
        # dependency verification are production implementations throughout.
        with ExitStack() as stack:
            stack.enter_context(patch('task_tower.github_tasks._transport',side_effect=self.http))
            stack.enter_context(patch('task_tower.github_source._http_get',side_effect=lambda url,headers,limit:self.http('GET',url,headers,None,limit)))
            stack.enter_context(patch('task_tower.github_tasks.resolve_token',return_value='fixture-only-token'))
            stack.enter_context(patch('task_tower.github_source.resolve_token',return_value='fixture-only-token'))
            yield

    def owned_run(self):
        config=self.config; fixture=self.fixture; task=config['tasks'][0]
        admission=admission_authorized(config,task,collect_snapshot(config['_connections']))
        self.assertIsNotNone(admission)
        journal=PipelineJournal(fixture.root/'default-source.sqlite3',checkouts=(fixture.connections[0].checkout,))
        limits={key:config[key] for key in ('task_timeout_seconds','max_processes','max_reworks','role_timeout_seconds','log_max_bytes')}
        journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='owner/repo',issue=16,task_id=task['task_id'],runner_label='local'),dict(profile_id='local',profile_fingerprint=admission['profile_fingerprint'],policy_sha256=config['policy_sha256'],component_keys=task['components'],limits=limits))
        owner=str(uuid.uuid4()); context=journal.owner(owner); context.__enter__()
        self.addCleanup(context.__exit__,None,None,None)
        run=journal.claim(owner,2)
        def record(**transition):
            nonlocal run
            run=journal.record(run['run_id'],owner,{key:run[key] for key in ('state','stage','generation','input_sha256')},transition)
        record(state='preparing',admission=admission,issue_id=admission['issue_id'],criteria_sha256=admission['criteria_sha256'],source_sha=admission['source_sha'],base_sha=admission['base_sha'])
        root=Path(fixture.profile['checkout']); _git(root,'checkout','-b','pipeline/'+run['run_id'])
        pins=fixture.profile['superpowers']['manifest_sha256']
        manifest=stage_manifest(dict(run,superpowers_sha256=pins),dict(checkpoint_sha=run['source_sha'],product_sha256=digest_manifest(product_manifest(root,dict(task,source_sha=run['source_sha'])))),stage='spec',generation=1,prior_receipt=None,checks=None)
        record(state='executing',manifest=manifest,worktree=str(root),git_dir=str(root/'.git'),superpowers_sha256=pins)
        config['_journal']=journal; config['_owner_id']=owner
        return run,journal,owner

    def test_default_factories_are_real_and_authenticated(self):
        with self.transport():
            project=collect_snapshot(self.config['_connections'])['owner/repo']
            self.assertIsNone(project['error'])
            self.assertIsInstance(project['store'],GitHubTasks)
            self.assertIsInstance(project['source'],GitHubSource)
            self.assertEqual(project['source'].poll(),[])
            result=select_ready({'owner/repo':project},[self.fixture.row],verify_done=verified_done)
            self.assertEqual(len(result['ready']),1)
        self.assertTrue(any('/issues?' in url for _,url in self.calls))
        self.assertTrue(any('/postmerge.yml/runs?' in url for _,url in self.calls))

    def test_real_role_and_worker_authority_use_defaults(self):
        from task_tower.pipeline_roles import run_role
        from task_tower.pipeline_worker import _authority
        with self.transport():
            run,journal,owner=self.owned_run()
            _authority(self.config,run,journal,owner)
            binding=dict(role='spec_executor',manifest=run['manifest'],artifact_names={key:'attempt/'+key+('.log' if key in ('stdout','stderr') else '.json') for key in ('request','result','stdout','stderr')})
            result=run_role(self.config,run,binding,'spec_executor',journal,owner)
            self.assertEqual(result['status'],'completed')
            self.assertTrue(result['process']['started'])
            self.assertEqual(journal.status(run['run_id'])['process_count'],1)

    def test_http_failure_blocks_real_authority_before_role_launch(self):
        from task_tower.pipeline_roles import run_role
        from task_tower.pipeline_worker import _authority
        with self.transport():
            run,journal,owner=self.owned_run(); self.transport_unavailable=True
            snapshot=collect_snapshot(self.config['_connections'])
            self.assertEqual(snapshot['owner/repo']['error'],'source_unavailable')
            with self.assertRaises(ValueError): _authority(self.config,run,journal,owner)
            binding=dict(role='spec_executor',manifest=run['manifest'],artifact_names={key:'attempt/'+key+('.log' if key in ('stdout','stderr') else '.json') for key in ('request','result','stdout','stderr')})
            with self.assertRaises(ValueError): run_role(self.config,run,binding,'spec_executor',journal,owner)
            self.assertEqual(journal.status(run['run_id'])['process_count'],0)
            self.assertEqual(journal.history(run['run_id'])['attempts'],[])

    def test_default_source_never_grants_unverified_dependency(self):
        self.metadata['blocked_by']=['Owner/Repo#17']
        self.issues[0]['body']=replace_metadata('Build from installed policy',self.metadata)
        dependency=dict(version=1,kind='task',mode='autonomous',task_id='TT-DEPENDENCY-001',status='done')
        self.issues.append(dict(number=17,id=124,state='closed',title='Unproven dependency',body=replace_metadata('Model prose says done',dependency)))
        with self.transport():
            snapshot=collect_snapshot(self.config['_connections'])
            result=select_ready(snapshot,[self.fixture.row],verify_done=verified_done)
        self.assertEqual(result['ready'],[])
        self.assertEqual(result['excluded'][0]['reason'],'dependency_unverified')

    def test_explicit_factories_remain_authoritative(self):
        stores=[]; sources=[]
        class Store:
            def list_issues(self): return []
        def store(connection): stores.append(connection); return Store()
        def source(connection): sources.append(connection); return object()
        # Explicit injection does not resolve credentials or construct defaults.
        with patch('task_tower.github_tasks.resolve_token',side_effect=AssertionError('unexpected default auth')),patch('task_tower.github_source.resolve_token',side_effect=AssertionError('unexpected default auth')):
            project=collect_snapshot(self.config['_connections'],store_factory=store,source_factory=source)['owner/repo']
        self.assertIsNone(project['error']); self.assertIsInstance(project['store'],Store)
        self.assertEqual(stores,self.config['_connections']); self.assertEqual(sources,self.config['_connections'])

    def test_each_explicit_factory_can_keep_the_other_default(self):
        class Store:
            def list_issues(self): return []
        store=Store(); source=object()
        with self.transport():
            project=collect_snapshot(self.config['_connections'],store_factory=lambda connection:store)['owner/repo']
            self.assertIs(project['store'],store)
            self.assertIsInstance(project['source'],GitHubSource)
            self.assertIsNone(project['error'])
            project=collect_snapshot(self.config['_connections'],source_factory=lambda connection:source)['owner/repo']
            self.assertIs(project['source'],source)
            self.assertIsInstance(project['store'],GitHubTasks)
            self.assertIsNone(project['error'])
