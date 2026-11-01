import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from task_tower import project_onboarding as onboarding
from task_tower.project_connections import ProjectConnection, load_connections
from task_tower.github_tasks import GitHubTasks, replace_metadata


class API:
    def __init__(self,repository='o/r'):
        self.repository=repository
        self.repository_id='R1' if repository=='o/r' else 'R_'+repository.replace('/','_')
        self.projects = []
        self.calls = []
        self.options = [dict(id='existing', name='Todo', color='GRAY', description='keep')]
        self.fail = None
    def transport(self, method, url, headers, payload, limit):
        query, variables = payload['query'], payload['variables']
        self.calls.append((query, variables))
        if self.fail: return json.dumps(dict(errors=[dict(message='SECRET')])).encode()
        owner=self.repository.split('/')[0]
        project = dict(id='P1', title='Task Tower: '+self.repository, url='https://github.com/users/'+owner+'/projects/1',
                       viewerCanUpdate=True, owner=dict(id='O1', login=owner),
                       fields=dict(nodes=[dict(id='F1', name='Status', dataType='SINGLE_SELECT', options=self.options)], pageInfo=dict(hasNextPage=False)),
                       repositories=dict(nodes=[dict(id=self.repository_id)],pageInfo=dict(hasNextPage=False)))
        page = lambda rows: dict(nodes=rows,pageInfo=dict(hasNextPage=False,endCursor=None))
        if 'query RepositoryIdentity' in query:
            data = dict(repository=dict(id=self.repository_id,nameWithOwner=self.repository,viewerPermission='ADMIN',owner=dict(id='O1',login=owner,__typename='User')))
        elif 'query LinkedProjects' in query: data = dict(node=dict(projectsV2=page([project] if self.projects else [])))
        elif 'query OwnerProjects' in query: data = dict(node=dict(projectsV2=page([project] if self.projects else [])))
        elif 'query ProjectDetails' in query: data = dict(node=project)
        elif 'mutation CreateProject' in query:
            self.projects.append('P1'); data = dict(createProjectV2=dict(projectV2=project))
        elif 'mutation LinkProject' in query: data = dict(linkProjectV2ToRepository=dict(repository=dict(id='R1')))
        elif 'mutation UpdateStatus' in query:
            self.options = [dict(option, id=option.get('id', 'new'+str(index))) for index, option in enumerate(variables['options'])]
            data = dict(updateProjectV2Field=dict(projectV2Field=dict(id='F1')))
        else: raise AssertionError(query)
        return json.dumps(dict(data=data)).encode()


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.path = self.root/'connections.json'
        self.api = API()
    def tearDown(self): self.tmp.cleanup()
    def ensure(self, **kwargs):
        return onboarding.ensure_project_connection(self.path, 'main', 'o/r', self.root, 'runner', transport=self.api.transport, **kwargs)
    def test_create_then_repeat_preserves_existing_option_and_private_connection(self):
        connection = self.ensure()
        self.assertEqual(connection.board['status_options']['open'], 'existing')
        self.assertEqual(set(connection.board['status_options']), set(onboarding.STATES))
        self.assertEqual(self.ensure(), connection)
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls), 1)
        self.assertEqual(self.api.options[0],dict(id='existing',name='Todo',color='GRAY',description='keep'))
        self.assertEqual(load_connections(self.path), [connection])
    def test_graphql_partial_error_is_sanitized_and_preserves_config(self):
        self.api.fail = True
        with self.assertRaisesRegex(onboarding.OnboardingError,'project') as caught: self.ensure()
        self.assertNotIn('SECRET',str(caught.exception))
        self.assertFalse(self.path.exists())
    def test_different_repository_existing_id_fails_before_remote(self):
        self.path.write_text(json.dumps(dict(version=1, projects=[dict(id='main',repository='x/y',checkout=str(self.root),runner_label='r')])))
        with self.assertRaises(onboarding.OnboardingError): self.ensure()
        self.assertEqual(self.api.calls, [])
    def test_config_conflict_preserves_newer_bytes(self):
        from task_tower.project_connections import write_connections
        self.path.write_text('{"version":1,"projects":[]}')
        before = self.path.read_bytes()
        self.path.write_text('{"version": 1, "projects": []}')
        with self.assertRaises(ValueError): write_connections(self.path, [], expected=before)
        self.assertNotEqual(self.path.read_bytes(),before)
    def test_unknown_create_reconciles_without_second_create(self):
        real = self.api.transport
        def transport(*args):
            result = real(*args)
            if 'mutation CreateProject' in args[3]['query']: raise OSError('secret')
            return result
        connection = onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=transport)
        self.assertEqual(connection.board['project_id'],'P1')
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls),1)

    def changed_transport(self, change):
        real=self.api.transport
        def transport(method,url,headers,payload,limit):
            value=json.loads(real(method,url,headers,payload,limit))
            change(payload['query'],value)
            return json.dumps(value).encode()
        return transport
    def test_ambiguous_linked_projects_never_create(self):
        self.api.projects=['P1']
        def change(query,value):
            if 'query LinkedProjects' in query:
                page=value['data']['node']['projectsV2']; page['nodes'] += [dict(page['nodes'][0],id='P2',url='https://github.com/users/o/projects/2')]
        with self.assertRaisesRegex(onboarding.OnboardingError,'Ambiguous'):
            onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=self.changed_transport(change))
        self.assertFalse(any('mutation' in q for q,v in self.api.calls))
    def test_incomplete_owner_pagination_never_create(self):
        def change(query,value):
            if 'query OwnerProjects' in query: value['data']['node']['projectsV2']['pageInfo']=dict(hasNextPage=True,endCursor='same')
        with self.assertRaises(onboarding.OnboardingError):
            onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=self.changed_transport(change))
        self.assertFalse(any('mutation' in q for q,v in self.api.calls))
    def test_wrong_owner_or_nonwritable_board_fails_without_mutation(self):
        self.api.projects=['P1']
        for wrong in (dict(owner=dict(id='WRONG')),dict(viewerCanUpdate=False),dict(url='https://github.com/orgs/o/projects/1')):
            def change(query,value):
                if 'query LinkedProjects' in query: value['data']['node']['projectsV2']['nodes'][0].update(wrong)
            with self.assertRaises(onboarding.OnboardingError):
                onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=self.changed_transport(change))
        self.assertFalse(any('mutation' in q for q,v in self.api.calls))
    def test_preserves_unrelated_connection_and_trusted_publishers(self):
        self.ensure()
        value=json.loads(self.path.read_text())
        value['projects'][0]['trusted_publishers']=['trusted']
        value['projects'][0]['board']['status_options']['custom']='existing'
        value['projects'].append(dict(id='other',repository='o/other',checkout=str(self.root),runner_label='other'))
        self.path.write_text(json.dumps(value))
        self.ensure()
        updated=load_connections(self.path)
        self.assertEqual(updated[0].trusted_publishers,['trusted'])
        self.assertEqual(updated[0].board['status_options']['custom'],'existing')
        self.assertEqual(updated[1].repository,'o/other')
    def test_two_competing_writers_only_one_can_commit(self):
        from task_tower.project_connections import write_connections
        self.path.write_text('{"version":1,"projects":[]}')
        expected=self.path.read_bytes()
        def writer(name):
            try:
                write_connections(self.path,[ProjectConnection(name,'o/'+name,self.root,name)],expected=expected)
                return 'saved'
            except ValueError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(writer,['one','two']))
        self.assertEqual(sorted(results),['conflict','saved'])
        self.assertEqual(len(load_connections(self.path)),1)
    def test_local_failure_reports_remote_url_then_rerun_reuses(self):
        with patch('task_tower.project_onboarding.write_connections',side_effect=OSError('SECRET')):
            with self.assertRaisesRegex(onboarding.OnboardingError,'https://github.com/users/o/projects/1') as caught: self.ensure()
        self.assertNotIn('SECRET',str(caught.exception))
        self.ensure()
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls),1)
    def test_org_identity_comes_from_authenticated_api(self):
        def change(query,value):
            if 'query RepositoryIdentity' in query: value['data']['repository']['owner']['__typename']='Organization'
            def fix(project): project['url']='https://github.com/orgs/o/projects/1'
            if 'query ProjectDetails' in query: fix(value['data']['node'])
            elif 'query LinkedProjects' in query or 'query OwnerProjects' in query:
                for project in value['data']['node']['projectsV2']['nodes']: fix(project)
        connection=onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=self.changed_transport(change))
        self.assertEqual(connection.project_url,'https://github.com/orgs/o/projects/1')
    def test_incompatible_status_type_is_not_replaced(self):
        self.api.projects=['P1']
        def change(query,value):
            if 'query LinkedProjects' in query: value['data']['node']['projectsV2']['nodes'][0]['fields']['nodes'][0]['dataType']='TEXT'
        with self.assertRaisesRegex(onboarding.OnboardingError,'Status'):
            onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=self.changed_transport(change))
        self.assertFalse(any('mutation' in q for q,v in self.api.calls))
    def test_unsafe_path_is_rejected_before_remote_calls(self):
        from types import SimpleNamespace
        original=Path.lstat
        def lstat(path,*args,**kwargs):
            if path==self.path: return SimpleNamespace(st_mode=0o100600,st_file_attributes=0x400)
            return original(path,*args,**kwargs)
        with patch.object(Path,'lstat',lstat):
            with self.assertRaisesRegex(onboarding.OnboardingError,'unsafe'): self.ensure()
        self.assertEqual(self.api.calls,[])
    def test_unknown_create_with_no_unique_match_stops(self):
        real=self.api.transport
        def transport(method,url,headers,payload,limit):
            if 'mutation CreateProject' in payload['query']:
                self.api.calls.append((payload['query'],payload['variables']))
                raise OSError('SECRET')
            return real(method,url,headers,payload,limit)
        with self.assertRaisesRegex(onboarding.OnboardingError,'uncertain'):
            onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=transport)
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls),1)
        self.assertFalse(self.path.exists())
    def test_new_invocation_cannot_repeat_unresolved_project_create(self):
        real=self.api.transport
        def transport(method,url,headers,payload,limit):
            if 'mutation CreateProject' in payload['query']:
                self.api.calls.append((payload['query'],payload['variables']))
                raise OSError('pending request')
            return real(method,url,headers,payload,limit)
        for _ in range(2):
            with self.assertRaisesRegex(onboarding.OnboardingError,'uncertain'):
                onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=transport)
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls),1)
        self.api.projects=['P1']
        self.assertEqual(onboarding.ensure_project_connection(self.path,'main','o/r',self.root,'runner',transport=transport).board['project_id'],'P1')
        self.assertEqual(sum('mutation CreateProject' in q for q,v in self.api.calls),1)
    def test_creation_journal_preserves_unrelated_sqlite_database(self):
        from task_tower.creation_journal import CreationJournal
        path=self.root/'thirdparty.sqlite3'
        database=sqlite3.connect(path)
        database.execute('CREATE TABLE valuable(data TEXT)')
        database.execute("INSERT INTO valuable VALUES('KEEP')")
        database.commit(); database.close()
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'journal'):
            CreationJournal(path).reserve('project','R1','identity')
        self.assertEqual(path.read_bytes(),before)
    def test_creation_journal_rejects_hardlinks(self):
        import os
        from task_tower.creation_journal import CreationJournal
        target=self.root/'original'
        target.write_bytes(b'KEEP')
        linked=self.root/'journal.sqlite3'
        os.link(target,linked)
        with self.assertRaisesRegex(ValueError,'hardlink'): CreationJournal(linked).reserve('project','R1','identity')
        self.assertEqual(target.read_bytes(),b'KEEP')

class ImportTests(unittest.TestCase):
    ensure=OnboardingTests.ensure
    tearDown=OnboardingTests.tearDown
    def setUp(self):
        OnboardingTests.setUp(self)
        self.connection=self.ensure()
        self.card=self.root/'card.json'
        self.card.write_text(json.dumps(dict(version=1,id='TT-PROJECT-ROLLOUT-001',title='Project',status='open',stages={})))
        self.issues=[]; self.posts=0; self.fail_membership=False; self.unknown_post=False
    def transport(self,method,url,headers,payload,limit):
        if url.endswith('/graphql'):
            query=payload['query']
            if 'addProjectV2ItemById' in query:
                if self.fail_membership: raise OSError('SECRET')
                return b'{"data":{"addProjectV2ItemById":{"item":{"id":"ITEM"}}}}'
            if 'updateProjectV2ItemFieldValue' in query:
                return b'{"data":{"updateProjectV2ItemFieldValue":{"projectV2Item":{"id":"ITEM"}}}}'
            return self.api.transport(method,url,headers,payload,limit)
        if '/comments?' in url: return b'[]'
        if method=='POST':
            self.posts+=1
            self.issues.append(dict(payload,number=24,node_id='I24',html_url='https://github.com/o/r/issues/24'))
            if self.unknown_post: raise OSError('secret')
            return json.dumps(self.issues[-1]).encode()
        if '/issues?' in url: return json.dumps(self.issues).encode()
        return json.dumps(self.issues[0]).encode()
    def store(self,connection=None): return GitHubTasks(connection or self.connection,transport=self.transport)
    def test_missing_board_stops_issue_post(self):
        with self.assertRaises(ValueError): self.store(ProjectConnection('p','o/r',self.root,'r')).import_card(self.card)
        self.assertEqual(self.posts,0)
    def test_task_id_reuses_issue_24_preserving_prose_and_repairs(self):
        issue=dict(number=24,node_id='I24',body=replace_metadata('KEEP',dict(version=1,kind='task',task_id='TT-PROJECT-ROLLOUT-001',status='awaiting_merge')))
        self.issues.append(issue)
        result=self.store().import_card(self.card)
        self.assertEqual(result['number'],24)
        self.assertEqual(self.posts,0)
        self.assertEqual(self.issues[0],issue)
    def test_duplicate_identity_and_conflicting_aliases_block_post(self):
        for metadata in ([dict(task_id='TT-PROJECT-ROLLOUT-001'),dict(legacy_id='TT-PROJECT-ROLLOUT-001')], [dict(task_id='TT-PROJECT-ROLLOUT-001',legacy_id='other')]):
            self.issues[:]=[dict(number=i+1,body=replace_metadata('',dict(version=1,kind='task',**row))) for i,row in enumerate(metadata)]
            with self.assertRaises(ValueError): self.store().import_card(self.card)
        self.assertEqual(self.posts,0)
    def test_unknown_issue_post_reconciles_single_identity(self):
        self.unknown_post=True
        result=self.store().import_card(self.card)
        self.assertEqual(result['number'],24)
        self.assertEqual(self.posts,1)
    def test_partial_membership_retry_reuses_issue(self):
        self.fail_membership=True
        result=self.store().import_card(self.card)
        self.assertEqual(result['number'],24)
        self.assertEqual(result['project_sync']['status'],'unavailable')
        self.fail_membership=False
        self.assertEqual(self.store().import_card(self.card)['project_sync']['status'],'synced')
        self.assertEqual(self.posts,1)
    def test_permission_loss_after_post_is_visible_partial(self):
        real=self.transport
        def transport(method,url,headers,payload,limit):
            if method=='GET' and '/issues/24' in url: raise OSError('SECRET')
            return real(method,url,headers,payload,limit)
        result=GitHubTasks(self.connection,transport=transport).import_card(self.card)
        self.assertEqual(result['number'],24)
        self.assertEqual(result['project_sync']['status'],'unavailable')
        self.assertIn('/issues/24',result['project_sync']['issue_url'])
    def test_verified_done_is_preserved_but_unverified_done_is_denied(self):
        self.issues.append(dict(number=24,node_id='I24',body=replace_metadata('',dict(version=1,kind='task',task_id='TT-PROJECT-ROLLOUT-001',status='done'))))
        for verified,expected in ((True,'done'),(False,'needs_input')):
            with patch('task_tower.project_worker.verified_done',return_value=verified):
                result=self.store().import_card(self.card)
            self.assertEqual(result['project_sync']['issue_status'],expected)
    def test_cli_partial_result_exposes_issue_and_failed_stage(self):
        from task_tower.books import main
        self.fail_membership=True
        output=io.StringIO()
        with patch('task_tower.books.GitHubTasks',return_value=self.store()),redirect_stdout(output):
            code=main(['--connections',str(self.path),'--project','main','--import-card',str(self.card)])
        result=json.loads(output.getvalue())
        self.assertEqual(code,1)
        self.assertEqual(result['number'],24)
        self.assertEqual(result['project_sync']['stage'],'membership_or_status')
    def test_incomplete_issue_lookup_never_posts(self):
        real=self.transport
        def transport(method,url,headers,payload,limit):
            if '/issues?' in url: return json.dumps([dict(number=i+1,body='') for i in range(100)]).encode()
            return real(method,url,headers,payload,limit)
        with self.assertRaises(Exception): GitHubTasks(self.connection,transport=transport).import_card(self.card)
        self.assertEqual(self.posts,0)
    def test_new_store_cannot_repeat_unresolved_issue_create(self):
        real=self.transport
        def transport(method,url,headers,payload,limit):
            if method=='POST' and url.endswith('/issues'):
                self.posts+=1
                raise OSError('pending request')
            return real(method,url,headers,payload,limit)
        for _ in range(2):
            with self.assertRaisesRegex(ValueError,'uncertain'):
                GitHubTasks(self.connection,transport=transport).import_card(self.card)
        self.assertEqual(self.posts,1)
        self.issues.append(dict(number=24,node_id='I24',body=replace_metadata('',dict(version=1,kind='task',legacy_id='TT-PROJECT-ROLLOUT-001'))))
        self.assertEqual(GitHubTasks(self.connection,transport=transport).import_card(self.card)['number'],24)
        self.assertEqual(self.posts,1)
    def test_post_success_journal_failure_retains_visible_issue(self):
        with patch('task_tower.creation_journal.CreationJournal.reconcile',side_effect=ValueError('local failure')):
            result=self.store().import_card(self.card)
        self.assertEqual(result['number'],24)
        self.assertEqual(result['project_sync']['stage'],'creation_journal')
        self.assertEqual(self.posts,1)


if __name__ == '__main__': unittest.main()
