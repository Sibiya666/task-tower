"""Read-only source regression tests; no live GitHub requests."""
import copy
import json
import unittest
import tempfile
import subprocess
import hashlib
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from types import SimpleNamespace

from task_tower.pr_source import PRSource, PRSourceError, current_ci, prepare_review
from task_tower.pr_policy import policy_fingerprint
from task_tower.executor_profiles import profile_fingerprint


class SourceTests(unittest.TestCase):
    def fixture(self):
        return json.loads((Path(__file__).parent/'fixtures/pr_source_github_2026.json').read_text(encoding='utf-8'))

    def source(self, pages, **limits):
        def transport(method, url, headers, body, timeout, max_bytes):
            self.assertEqual(method, 'GET')
            self.assertEqual(headers['X-GitHub-Api-Version'], '2026-03-10')
            return {'status': 200, 'headers': {}, 'body': json.dumps(pages.pop(0)).encode()}
        return PRSource(SimpleNamespace(repository='owner/repo'), limits, transport=transport)

    def test_pagination_limit_or_changing_totals_block(self):
        rows=[{'id': i} for i in range(100)]
        for pages, limits in [([{'total_count':101,'check_runs':rows}], {'max_pages':1}),
                              ([{'total_count':101,'check_runs':rows}, {'total_count':102,'check_runs':[{'id':101}]}], {})]:
            with self.subTest(limits=limits), self.assertRaises(PRSourceError):
                self.source(pages, **limits)._pages('/checks', 'check_runs')

    def test_http_status_size_duplicate_json_block(self):
        for response in [{'status':403,'headers':{},'body':b'{}'},
                         {'status':200,'headers':{},'body':b'{"x":1,"x":2}'},
                         {'status':200,'headers':{},'body':b' '*100}]:
            source=PRSource(SimpleNamespace(repository='owner/repo'), {'max_response_bytes':50},
                            transport=lambda *args:response)
            with self.subTest(response=response), self.assertRaises(PRSourceError): source._get('/x')
        calls=[]
        source=PRSource(SimpleNamespace(repository='owner/repo'),{},transport=lambda *args:(calls.append(args) or {'status':200,'headers':{},'body':b'{}'}))
        for method,url,body in [('PUT','https://api.github.com/repos/owner/repo/pulls/1/merge',None),
                                ('POST','https://api.github.com/graphql',{'query':'mutation { x }'}),
                                ('GET','https://other.invalid/path',None)]:
            with self.subTest(method=method,url=url), self.assertRaises(PRSourceError): source._request(method,url,body)
        self.assertEqual(calls,[])

    def test_latest_rerun_failure_and_forged_context_block(self):
        good={'id':1,'name':'test','app':{'id':7},'status':'completed','conclusion':'success',
              'check_suite':{'id':4}, 'head_sha':'a'*40, 'started_at':'2026-01-01T00:00:00Z'}
        checks=[good,dict(good,id=2,conclusion='failure',started_at='2026-01-02T00:00:00Z')]
        task={'required_checks':[{'context':'test','app_id':7}], 'publisher_account':'trusted'}
        self.assertFalse(current_ci(checks, [], task, 'a'*40)['ready'])
        forged=dict(good,id=3,app={'id':9})
        self.assertFalse(current_ci([good,forged], [], task, 'a'*40)['ready'])
        for result in ('neutral','skipped',None):
            self.assertFalse(current_ci([dict(good,conclusion=result)], [], task, 'a'*40)['ready'])

    def test_own_context_separate_from_nonacceptance_digest(self):
        task={'required_checks':[{'context':'test','app_id':7}], 'publisher_account':'trusted'}
        status={'id':1,'context':'task-tower/pr-acceptance','state':'pending','creator':{'login':'trusted'}}
        ci=current_ci([], [status], task, 'a'*40)
        self.assertEqual(ci['acceptance_statuses'], [status])
        self.assertFalse(ci['ready'])
        self.assertEqual(ci['statuses'], [])
        status['creator']['login']='forged'
        with self.assertRaises(PRSourceError): current_ci([], [status], task, 'a'*40)

    def test_complete_local_binary_diff_when_api_patch_truncated(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); repo=root/'repo'; repo.mkdir()
            def git(*args):
                result=subprocess.run(['git','-C',str(repo),*args],capture_output=True,check=True)
                return result.stdout.decode().strip()
            git('init'); git('config','user.email','test@example.invalid'); git('config','user.name','Test')
            git('remote','add','origin','https://github.com/owner/repo.git')
            (repo/'a.txt').write_text('before\n',encoding='utf-8'); git('add','.'); git('commit','-m','base'); base=git('rev-parse','HEAD')
            git('mv','a.txt','renamed.txt'); (repo/'binary.bin').write_bytes(b'\x00\x01\xff'*100)
            git('add','.'); git('commit','-m','head'); head=git('rev-parse','HEAD')
            bare=root/'objects.git'
            subprocess.run(['git','clone','--bare',str(repo),str(bare)],check=True,capture_output=True)
            authority=dict(source='legacy',run_id=None,criteria_sha256='1'*64,head_sha=head,base_sha=base,
                           receipts=[],artifacts=[],executor_instances=['11111111-1111-4111-8111-111111111111'],
                           reviewer_instances=['22222222-2222-4222-8222-222222222222'])
            authority['authority_sha256']=policy_fingerprint(authority)
            pins=root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('readonly\n',encoding='utf-8')
            manifest={'SKILL.md':hashlib.sha256(b'readonly\n').hexdigest()}
            profile=dict(kind='custom',trusted=True,repository='owner/repo',argv=[sys.executable,str(root/'child.py')],
                         timeout_seconds=10,log_max_bytes=128,superpowers=dict(root=str(pins),revision='e'*40,
                         manifest=manifest,manifest_sha256=profile_fingerprint(manifest)))
            task=dict(repository='owner/repo',pr_number=1,issue=2,issue_id=3,task_id='TT-TEST-001',_review_profile=profile)
            snapshot={k:task[k] for k in ('repository','pr_number','issue','issue_id','task_id')}
            snapshot.update(head_sha=head,base_sha=base,policy_sha256='3'*64,ci={'sha256':'4'*64,'ready':True,'reasons':[],'acceptance_statuses':[]},
                            protection={'sha256':'5'*64,'ready':True,'reasons':[]},files=[{'patch':'TRUNCATED'}],pr={},commits=[{'sha':head}],reviews=[],
                            threads={'nodes':[],'review_decision':None},acceptance_statuses=[],ready=True,reasons=[],
                            issue_payload={'id':3,'number':2,'title':'Task','body':'criteria','state':'open','state_reason':None})
            snapshot['issue_sha256']=policy_fingerprint(snapshot['issue_payload'])
            connection=SimpleNamespace(repository='owner/repo',checkout=repo)
            # Lower Git fetch fixture transfers real objects from local repo;
            # the production helper still receives only the fixed GitHub URL.
            def fetch(mirror,url,base_arg,head_arg,logdir):
                self.assertEqual(url,'https://github.com/owner/repo.git')
                subprocess.run(['git','-C',str(mirror),'fetch',str(bare),base_arg,head_arg],check=True,capture_output=True)
            with patch('task_tower.pr_source._fetch',fetch):
                prepared=prepare_review(connection,task,snapshot,authority,root/'private')
            diff=Path(prepared['diff_path']).read_bytes()
            self.assertIn(b'GIT binary patch',diff); self.assertIn(b'rename from a.txt',diff)
            self.assertNotIn(b'TRUNCATED',diff)
            request=prepared['request']; self.assertEqual(request['input_sha256'],policy_fingerprint(request['input']))
            self.assertEqual(request['input']['diff']['manifest'][0]['status'][0] in 'AR',True)
            self.assertEqual(git('rev-parse','HEAD'),head)
            for field in ('ready','issue_payload','pr','threads','ci'):
                bad=copy.deepcopy(snapshot); bad.pop(field)
                with self.subTest(missing=field), patch('task_tower.pr_source._git',side_effect=AssertionError('incomplete snapshot reached Git')), self.assertRaises(PRSourceError):
                    prepare_review(connection,task,bad,authority,root/('missing-'+field))

    def protection_source(self, fixture):
        def transport(method,url,headers,body,timeout,max_bytes):
            self.assertEqual(method,'GET')
            path=url.removeprefix('https://api.github.com')
            if path=='/user': data={'login':'trusted'}
            elif path=='/repos/owner/repo': data={'allow_merge_commit':True}
            elif path=='/repos/owner/repo/branches/main/protection': data=fixture['classic']
            elif path.startswith('/repos/owner/repo/rules/branches/main?'): data=[fixture['rule']]
            elif path=='/repos/owner/repo/rulesets/42': data=fixture['ruleset']
            else: self.fail(path)
            return dict(status=200,headers={},body=json.dumps(data).encode())
        return PRSource(SimpleNamespace(repository='owner/repo'),{},transport=transport)

    def test_effective_protection_unknown_bypass_or_queue_block(self):
        task={'publisher_account':'trusted','required_checks':[{'context':'test','app_id':7}]}
        self.assertTrue(self.protection_source(self.fixture()).protection(task)['ready'])
        acceptance=self.fixture(); acceptance['classic']['required_status_checks']['checks'].append({'context':'task-tower/pr-acceptance','app_id':None})
        self.assertTrue(self.protection_source(acceptance).protection(task)['ready'])
        for actor in ('User','Team','Integration','RepositoryRole','OrganizationAdmin','FutureActor'):
            fixture=self.fixture(); fixture['ruleset']['bypass_actors']=[{'actor_id':1,'actor_type':actor,'bypass_mode':'pull_request'}]
            with self.subTest(actor=actor): self.assertFalse(self.protection_source(fixture).protection(task)['ready'])
        for rule in ('merge_queue','required_deployments','FutureRule'):
            fixture=self.fixture(); fixture['rule']['type']=rule
            with self.subTest(rule=rule): self.assertFalse(self.protection_source(fixture).protection(task)['ready'])
        fixture=self.fixture(); fixture['classic']['enforce_admins']['enabled']=False
        self.assertFalse(self.protection_source(fixture).protection(task)['ready'])
        fixture=self.fixture(); fixture['classic']['lock_branch']['enabled']=True
        self.assertFalse(self.protection_source(fixture).protection(task)['ready'])
        fixture=self.fixture(); fixture['classic']['required_status_checks']['checks'].append({'context':'extra-server-gate','app_id':7})
        self.assertFalse(self.protection_source(fixture).protection(task)['ready'])

    def test_async_result_fixed_uuid_head_method_and_no_queue_inference(self):
        pending=self.fixture()['async_pending']; request_uuid=pending['details']['uuid']
        source=self.source([pending]); self.assertEqual(source.merge_result(1,request_uuid)['status'],'pending')
        for field,value in [('uuid','11111111-1111-4111-8111-111111111111'),('merge_action','default'),('bypass_rules',True),('merge_method','squash')]:
            bad=copy.deepcopy(pending); bad['details'][field]=value
            with self.subTest(field=field), self.assertRaises(PRSourceError): self.source([bad]).merge_result(1,request_uuid)
        with self.assertRaises(PRSourceError): self.source([{'status':'merged','details':{}}]).merge_result(1,request_uuid)

    def test_merge_observation_exact_pr_main_and_two_parents(self):
        pr=dict(number=1,merged=True,state='closed',merge_commit_sha='c'*40,merged_by={'login':'trusted'},
                head={'sha':'a'*40,'repo':{'full_name':'owner/repo'}},base={'ref':'main','repo':{'full_name':'owner/repo'}})
        commit={'sha':'c'*40,'parents':[{'sha':'b'*40},{'sha':'a'*40}]}
        main={'object':{'sha':'c'*40}}
        self.assertEqual(self.source([pr,commit,main]).merge_observation(1)['parents'],['b'*40,'a'*40])
        for mutation in ('wrong-pr','unknown-merged','wrong-main','wrong-parents'):
            candidate=copy.deepcopy(pr); obj=copy.deepcopy(commit); ref=copy.deepcopy(main)
            if mutation=='wrong-pr': candidate['number']=2
            elif mutation=='unknown-merged': candidate['merged']=None
            elif mutation=='wrong-main': ref['object']['sha']='d'*40
            else: obj['parents'].append({'sha':'d'*40})
            with self.subTest(mutation=mutation),self.assertRaises(PRSourceError): self.source([candidate,obj,ref]).merge_observation(1)

    def actions_fixture(self):
        return self.fixture()['actions']

    def platform_source(self,fixture):
        def transport(method,url,headers,body,timeout,max_bytes):
            self.assertEqual(method,'GET'); path=url.removeprefix('https://api.github.com/repos/owner/repo')
            if path=='/check-suites/42': data=fixture['suite']
            elif path.startswith('/actions/runs?'): data={'total_count':1,'workflow_runs':[fixture['run']]}
            elif path.startswith('/actions/runs/9/attempts/2/jobs?'): data={'total_count':len(fixture['jobs']),'jobs':fixture['jobs']}
            elif path=='/actions/runs/9': data=fixture['run']
            elif path.startswith('/check-runs/'): data=next(c for c in fixture['checks'] if c['id']==int(path.rsplit('/',1)[1]))
            else: self.fail(path)
            return dict(status=200,headers={},body=json.dumps(data).encode())
        return PRSource(SimpleNamespace(repository='owner/repo'),{},transport=transport)

    def test_premerge_platforms_actual_current_actions_jobs(self):
        fixture=self.actions_fixture()
        task=dict(pr_number=1,required_checks=[{'context':c['name'],'app_id':15368} for c in fixture['checks']],
                  required_platforms=['linux','windows','macos'],publisher_account='trusted')
        ci=current_ci(fixture['checks'],[],task,'a'*40)
        proof=self.platform_source(fixture)._platforms(task,'a'*40,'b'*40,ci)
        self.assertTrue(proof['ready']); self.assertEqual(set(proof['platforms']),set(task['required_platforms']))
        missing=copy.deepcopy(task); missing['required_checks']=missing['required_checks'][:2]
        self.assertFalse(self.platform_source(fixture)._platforms(missing,'a'*40,'b'*40,ci)['ready'])
        for mutation in ('self-hosted','custom-group','unknown','wrong-job-check','wrong-head','wrong-event','wrong-repo','wrong-app','stale-attempt'):
            fixture=self.actions_fixture()
            if mutation=='self-hosted': fixture['jobs'][0]['labels'].append('self-hosted')
            elif mutation=='custom-group': fixture['jobs'][0]['runner_group_id']=2
            elif mutation=='unknown': fixture['jobs'][0]['labels']=['mystery-linux']
            elif mutation=='wrong-job-check': fixture['jobs'][0]['check_run_url']='https://api.github.com/repos/other/repo/check-runs/1'
            elif mutation=='wrong-head': fixture['run']['head_sha']='c'*40
            elif mutation=='wrong-event': fixture['run']['event']='push'
            elif mutation=='wrong-repo': fixture['run']['head_repository']['full_name']='fork/repo'
            elif mutation=='wrong-app': fixture['suite']['app']={'id':9,'slug':'github-actions'}
            elif mutation=='stale-attempt': fixture['jobs'][0]['run_attempt']=1
            with self.subTest(mutation=mutation):
                proof=self.platform_source(fixture)._platforms(task,'a'*40,'b'*40,ci)
                self.assertFalse(proof['ready'])

    def whole_source(self, change=None):
        fixture=self.fixture(); actions=fixture['actions']
        task=dict(pr_number=1,issue=2,issue_id=3,task_id='TT-TEST-001',publisher_account='trusted',
                  required_checks=[{'context':c['name'],'app_id':15368} for c in actions['checks']],required_platforms=['linux','windows','macos'])
        fixture['classic']['required_status_checks']['checks']=task['required_checks']
        pr=dict(number=1,state='open',draft=False,merged=False,mergeable=True,mergeable_state='clean',body='Task-Tower: TT-TEST-001',commits=1,changed_files=0,
                head={'sha':'a'*40,'repo':{'full_name':'owner/repo'}},base={'sha':'b'*40,'ref':'main','repo':{'full_name':'owner/repo'}})
        actions_transport=self.platform_source(actions).transport
        counts={}
        def transport(method,url,headers,body,timeout,max_bytes):
            path=urlsplit(url).path.removeprefix('/repos/owner/repo')
            if method=='POST':
                self.assertEqual(url,'https://api.github.com/graphql')
                self.assertTrue(json.loads(body)['query'].startswith('query('))
                data={'data':{'repository':{'pullRequest':{'reviewDecision':None,'reviewThreads':{'totalCount':0,'nodes':[],'pageInfo':{'hasNextPage':False,'endCursor':None}}}}}}
            else:
                self.assertEqual(method,'GET')
                static={'/pulls/1':pr,'/git/ref/heads/main':{'object':{'sha':'b'*40}},
                        '/issues/2':{'id':3,'number':2,'title':'Task','body':'criteria','state':'open','state_reason':None},
                        '/pulls/1/commits':[{'sha':'a'*40}],'/pulls/1/files':[],'/pulls/1/reviews':[],
                        '/commits/'+'a'*40+'/check-runs':{'total_count':3,'check_runs':actions['checks']},
                        '/commits/'+'a'*40+'/statuses':[],
                        '':{'allow_merge_commit':True},'/user':{'login':'trusted'},
                        '/branches/main/protection':fixture['classic'],'/rules/branches/main':[fixture['rule']],'/rulesets/42':fixture['ruleset']}
                if path not in static: data=json.loads(actions_transport(method,url,headers,body,timeout,max_bytes)['body'])
                else: data=static[path]
            counts[path]=counts.get(path,0)+1
            if change is not None: data=change(path,copy.deepcopy(data),counts[path])
            return dict(status=200,headers={},body=json.dumps(data).encode())
        source=PRSource(SimpleNamespace(repository='owner/repo'),{},transport=transport)
        return source,task,actions

    def test_positive_whole_snapshot_through_readonly_http_transport(self):
        source,task,actions=self.whole_source()
        snapshot=source.snapshot(task)
        self.assertTrue(snapshot['ready'],snapshot['reasons'])
        self.assertEqual(snapshot['ci']['platforms']['platforms'],['linux','macos','windows'])
        actions['jobs'][1]['labels']=['self-hosted','windows-2025']
        self.assertFalse(source.snapshot(task)['ready'])

    def test_final_pr_gate_drift_blocks_through_lower_http_transport(self):
        for field,value in [('number',2),('number',True),('merged',True),('mergeable',False),('mergeable',None),('mergeable',1),('mergeable_state','blocked'),('mergeable_state',None),
                            ('head',{'sha':'c'*40}),('base',{'sha':'c'*40}),('body','changed'),('state','closed'),('draft',True),('commits',2),('changed_files',1)]:
            def change(path,data,count):
                if path=='/pulls/1' and count==2: data[field]=value
                return data
            source,task,_=self.whole_source(change)
            with self.subTest(field=field,value=value),self.assertRaises(PRSourceError): source.snapshot(task)

    def test_final_mutable_gate_drift_and_new_ci_rerun_block(self):
        for gate in ('reviews','threads','review-decision','protection','check-rerun','status','run-attempt'):
            def change(path,data,count):
                if gate=='reviews' and path=='/pulls/1/reviews' and count==2:
                    return [{'id':99,'user':{'id':7},'state':'CHANGES_REQUESTED'}]
                if gate in ('threads','review-decision') and path=='/graphql' and count==2:
                    pr=data['data']['repository']['pullRequest']
                    if gate=='review-decision': pr['reviewDecision']='CHANGES_REQUESTED'
                    else: pr['reviewThreads'].update(totalCount=1,nodes=[{'id':'PRRT_1','isResolved':False,'isOutdated':False}])
                if gate=='protection' and path=='/branches/main/protection' and count==2: data['enforce_admins']['enabled']=False
                if gate=='check-rerun' and path=='/commits/'+'a'*40+'/check-runs' and count==2:
                    rerun=copy.deepcopy(data['check_runs'][0]); rerun.update(id=4,status='queued',conclusion=None)
                    data['check_runs'].insert(0,rerun); data['total_count']=4
                if gate=='status' and path=='/commits/'+'a'*40+'/statuses' and count==2:
                    return [{'id':99,'context':'new-server-gate','state':'pending','creator':{'login':'trusted'}}]
                if gate=='run-attempt' and path=='/actions/runs/9' and count==2:
                    data.update(run_attempt=3,status='queued',conclusion=None)
                return data
            source,task,_=self.whole_source(change)
            with self.subTest(gate=gate),self.assertRaises(PRSourceError): source.snapshot(task)

    def test_coherent_snapshot_keeps_current_own_acceptance_separate(self):
        baseline,task,_=self.whole_source(); baseline_ci=baseline.snapshot(task)['ci']
        def change(path,data,count):
            if path=='/commits/'+'a'*40+'/statuses':
                return [{'id':99 if count==1 else 100,'context':'task-tower/pr-acceptance',
                         'state':'pending' if count==1 else 'success','creator':{'login':'trusted'}}]
            return data
        source,task,_=self.whole_source(change); snapshot=source.snapshot(task)
        self.assertTrue(snapshot['ready'])
        self.assertEqual(snapshot['ci']['sha256'],baseline_ci['sha256'])
        self.assertEqual(snapshot['acceptance_statuses'][0]['state'],'success')

    def test_unresolved_thread_changes_requested_unknown_mergeability_block(self):
        task=dict(pr_number=1,issue=2,issue_id=3,task_id='TT-TEST-001',publisher_account='trusted',required_checks=[],required_platforms=[])
        pr=dict(number=1,state='open',draft=False,merged=False,mergeable=True,mergeable_state='clean',body='Task-Tower: TT-TEST-001',commits=1,changed_files=0,
                head={'sha':'a'*40,'repo':{'full_name':'owner/repo'}},base={'sha':'b'*40,'ref':'main','repo':{'full_name':'owner/repo'}})
        for mutation,expected in [('unknown','mergeability_unknown_or_blocked'),('thread','unresolved_review_thread'),('review','changes_requested')]:
            source=self.source([]); candidate=copy.deepcopy(pr)
            if mutation=='unknown': candidate['mergeable']=None
            reviews=[{'id':1,'user':{'id':7},'state':'CHANGES_REQUESTED'}] if mutation=='review' else []
            def pages(path,key=None):
                if path.endswith('/commits'): return [{'sha':'a'*40}]
                if path.endswith('/reviews'): return reviews
                return []
            issue=dict(id=3,number=2,title='Task',body='criteria',state='open',state_reason=None)
            with patch.object(source,'_get',side_effect=lambda path:issue if path.startswith('/issues/') else candidate), patch.object(source,'main_sha',return_value='b'*40), \
                 patch.object(source,'_pages',side_effect=pages), patch.object(source,'_threads',return_value={'nodes':[{'isResolved':False}] if mutation=='thread' else [],'review_decision':None}), \
                 patch.object(source,'protection',return_value={'ready':True,'reasons':[],'classic':{}}):
                observed=source.snapshot(task)
            with self.subTest(mutation=mutation):
                self.assertFalse(observed['ready']); self.assertIn(expected,observed['reasons'])


if __name__ == '__main__': unittest.main()
