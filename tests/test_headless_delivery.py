"""Trusted delivery fault contracts; transport doubles represent external GitHub only."""
import copy
import tempfile
import unittest
from pathlib import Path
from task_tower.connector.store import ConnectorStore
from task_tower.connector import delivery

REPO='Sibiya666/task-tower'
H='b'*40
B='a'*40
M='c'*40

def attempt():
    return dict(attempt_id='attempt',project_id='p',bead_id='pilot',connector_id='stage5-fixture',actor='owner',phase='awaiting_merge',
        head_sha=H,base_sha=B,author_thread_id='author',review_threads=['review'],
        review=dict(verdict='approve',findings=[],head_sha=H,base_sha=B,reviewer_thread_id='review'),
        source=dict(head_sha=H,base_sha=B,diff='complete actual diff'))

class Host:
    def __init__(self):
        self.calls=[];self.lost=False
        self.pr=dict(repository=REPO,head_repository=REPO,number=7,head_sha=H,base_sha=B,base_ref='main',branch='codex/headless-attempt',
                     state='open',merged=False,mergeable=True,mergeable_state='clean',conversations_resolved=True)
        self.checks=[dict(name=n,conclusion='success',head_sha=H,app='github-actions') for n in ['scope','unittest (windows-latest)',*['unittest shard (windows-latest, '+str(i)+')' for i in range(4)]]]
        self.status=None
    def prepare_pr(self,a):self.calls.append('prepare');return copy.deepcopy(self.pr)
    def read_pr(self,repository,number):self.calls.append('read');return copy.deepcopy(self.pr)
    def read_checks(self,repository,sha):return copy.deepcopy(self.checks)
    def protection(self,repository):return dict(enforce_admins=True,required_checks=['scope','unittest (windows-latest)','task-tower/pr-acceptance'],strict=True,allow_force_pushes=False,allow_deletions=False,required_conversation_resolution=True)
    def publish_acceptance(self,repository,head,review):self.status=dict(id=91,head_sha=head,context='task-tower/pr-acceptance',state='success',review=copy.deepcopy(review));return self.status
    def read_acceptance(self,repository,head):return copy.deepcopy(self.status)
    def merge(self,repository,number,head):
        self.calls.append('merge');self.pr.update(merged=True,state='closed',merge_commit_sha=M)
        if self.lost:raise TimeoutError('lost response')
        return dict(merged=True,sha=M)

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ConnectorStore(Path(self.tmp.name)/'journal','stage5-fixture');self.addCleanup(self.store.close)
        self.host=Host();self.d=delivery.Delivery(self.host,self.store,{'p':REPO})
    def prepared(self):
        a=attempt();self.d.prepare_pr(a);return a
    def test_expected_merge_and_lost_response_readback_never_repeat_effect(self):
        a=self.prepared();self.host.lost=True
        result=self.d.merge_expected(REPO,7,H,B)
        self.assertEqual(result['main_sha'],M)
        self.assertEqual(self.d.merge_expected(REPO,7,H,B),result)
        self.assertEqual(self.host.calls.count('merge'),1)
    def test_stale_source_failed_checks_and_fabricated_status_block_merge(self):
        for fault in ('head','base','missing','failed','cancelled','self','foreign_review','unresolved','unprotected','forged_status','foreign_pr'):
            with self.subTest(fault=fault):
                self.host=Host();self.d=delivery.Delivery(self.host,self.store,{'p':REPO});a=attempt()
                if fault=='self':a['review']['reviewer_thread_id']='author'
                if fault=='foreign_review':a['review']['reviewer_thread_id']='invented'
                if fault in ('self','foreign_review'):
                    with self.assertRaises(ValueError):self.d.prepare_pr(a)
                    continue
                self.d.prepare_pr(a)
                if fault=='head':self.host.pr['head_sha']='d'*40
                if fault=='base':self.host.pr['base_sha']='d'*40
                if fault=='missing':self.host.checks.pop()
                if fault in ('failed','cancelled'):self.host.checks[0]['conclusion']=fault
                if fault=='unresolved':self.host.pr['conversations_resolved']=False
                if fault=='unprotected':self.host.protection=lambda r:dict(enforce_admins=False)
                if fault=='forged_status':self.host.read_acceptance=lambda r,h:dict(id=999,state='success')
                if fault=='foreign_pr':self.host.pr['repository']='other/repo'
                with self.assertRaises(ValueError):self.d.merge_expected(REPO,7,H,B)
                self.assertNotIn('merge',self.host.calls)
                # Each fault uses a distinct durable attempt, without clearing unknown effects.
                self.store.close();self.store=ConnectorStore(Path(self.tmp.name)/('journal-'+fault),'stage5-fixture');self.addCleanup(self.store.close)
    def test_foreign_repository_rejected_before_transport(self):
        with self.assertRaises(ValueError):self.d.verify_pr('other/repo',7,H,B)
        self.assertEqual(self.host.calls,[])
    def test_restart_unknown_merge_only_reads_existing_outcome(self):
        self.prepared();self.host.lost=True
        original=self.host.read_pr
        def read(r,p):
            if self.host.pr['merged']:raise TimeoutError()
            return original(r,p)
        self.host.read_pr=read
        with self.assertRaises(ValueError):self.d.merge_expected(REPO,7,H,B)
        self.host.read_pr=original
        self.d=delivery.Delivery(self.host,self.store,{'p':REPO})
        self.assertEqual(self.d.merge_expected(REPO,7,H,B)['main_sha'],M)
        self.assertEqual(self.host.calls.count('merge'),1)


class HostBoundaryTests(unittest.TestCase):
    def test_public_pr_message_uses_source_commit_without_runtime_identities(self):
        from task_tower.connector.delivery import GitHubHost
        a=attempt()
        for field in ('attempt_id','project_id','bead_id','connector_id','actor','author_thread_id'):
            a[field]='private-runtime-'+field
        a['review_threads']=['private-review-thread']
        a['prompt']='private prompt C:/private/config/token.json'
        branch='codex/headless-'+a['attempt_id']
        requests=[]
        class Trees:
            def prepare(self,*args):return dict(path='fixture',branch=branch)
            def source(self,*args):return a['source']
        class Host(GitHubHost):
            def _trusted_git(self,*args,**kw):return 'https://github.com/'+REPO
            def _push(self,*args,**kw):pass
            def _pages(self,*args):return [{'number':7}] if requests else []
            def _request(self,r,method,path,payload):
                requests.append((r,method,path,payload));return {'number':7}
            def read_pr(self,r,p):return dict(repository=r,pr_number=p)
        host=Host(Trees(),None,{a['project_id']:REPO},token='fixture')
        self.assertEqual(host.prepare_pr(a),dict(repository=REPO,pr_number=7))
        self.assertEqual(host.prepare_pr(a),dict(repository=REPO,pr_number=7))
        self.assertEqual(len(requests),1)
        r,method,path,payload=requests[0]
        self.assertEqual((r,method,path),(REPO,'POST','/pulls'))
        self.assertEqual((payload['head'],payload['base']),(branch,'main'))
        public=payload['title']+'\n'+payload['body']
        for private in [a[k] for k in ('attempt_id','project_id','bead_id','connector_id','actor','author_thread_id','prompt')]+a['review_threads']:
            self.assertNotIn(private,public)
        self.assertIn('https://github.com/'+REPO+'/commit/'+a['source']['head_sha'],payload['body'])
        self.assertIn('Independent review is recorded by the trusted connector.',payload['body'])

    def test_fixed_adapter_rejects_wrong_remote_before_push(self):
        from task_tower.connector.delivery import GitHubHost
        class Trees:
            def prepare(self,*args):return dict(path='fixture',branch='codex/headless-attempt')
            def source(self,*args):return attempt()['source']
            def _git(self,path,*args,**kw):
                if args[:2]==('remote','get-url'):return 'https://github.com/other/repository'
                raise AssertionError('effect before verified remote')
        class FixedHost(GitHubHost):
            def _trusted_git(self,path,*args,**kw):return self.trees._git(path,*args)
        host=FixedHost(Trees(),None,{'p':REPO},token='fixture',transport=lambda *a: self.fail('network before verified remote'))
        with self.assertRaises(ValueError):host.prepare_pr(attempt())
    def test_fresh_fetch_failure_stops_before_source_ci_discovery_or_reviewer(self):
        from task_tower.connector.delivery import GitHubHost
        calls=[]
        class Trees:
            projects={'p':(Path('repository'),Path('worktrees'))}
            def _git(self,path,*args,**kw):
                calls.append((args,kw))
                if args==('fetch','origin','main'):
                    self_timeout=kw['timeout'];assert self_timeout==60
                    raise ValueError('fetch failed')
                raise AssertionError('read after failed fetch')
        host=GitHubHost(Trees(),None,{'p':REPO},token='fixture',transport=lambda *a: self.fail('network after failed fetch'))
        with self.assertRaises(ValueError):host.verify_main(attempt(),dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M))
        self.assertEqual(len(calls),1)

    def test_artifact_digest_zip_member_and_fresh_inventory_fail_closed(self):
        import io,zipfile,hashlib
        from task_tower.connector.delivery import artifact_json,verify_manifest_bundle
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('merge-event.json','{"checks":"passed"}')
        raw=stream.getvalue();digest='sha256:'+hashlib.sha256(raw).hexdigest()
        self.assertEqual(artifact_json(raw,digest,'merge-event.json'),{'checks':'passed'})
        for wrong_digest,name in [('sha256:'+'0'*64,'merge-event.json'),(None,'merge-event.json'),(digest,'wrong.json')]:
            with self.assertRaises(ValueError):artifact_json(raw,wrong_digest,name)
        ids=['test.a','test.b','test.c','test.d']
        manifests=[dict(version=2,schedule='duration-balanced-v1',source_sha=M,count=4,index=i,all_ids=ids,selected_ids=[ids[i]],mode='execution',successful=True,tests_run=1,failures=0,errors=0) for i in range(4)]
        verify_manifest_bundle(manifests,M,ids)
        with self.assertRaises(ValueError):verify_manifest_bundle(manifests,M,ids+['test.e'])
        manifests[2]['successful']=False
        with self.assertRaises(ValueError):verify_manifest_bundle(manifests,M,ids)


class MainReviewerTests(unittest.TestCase):
    def test_actual_new_thread_persisted_before_turn_and_bound_to_main(self):
        import json,threading
        from task_tower.connector.delivery import MainReviewer
        from task_tower.connector.app_server import AppServer
        tempdir=tempfile.TemporaryDirectory();self.addCleanup(tempdir.cleanup)
        temp=tempdir.name
        store=ConnectorStore(Path(temp)/'journal','stage5-main-review');self.addCleanup(store.close)
        class Trees:
            def prepare_review(self,*args):return dict(path=temp)
            def _git(self,path,*args,**kw):
                return 'actual whole main diff' if args[0]=='diff' else M
        class Wire:
            def __init__(self):self.pending=[];self.turns=0
            def request(wire,method,params):
                if method=='thread/start':return {'thread':{'id':'fresh-main-review'}}
                if method=='turn/start':
                    wire.turns+=1
                    saved=store.commands()[-1]
                    self.assertEqual(saved['thread_id'],'fresh-main-review')
                    value=dict(verdict='approve',findings=[],head_sha=M,base_sha=B,reviewer_thread_id='fresh-main-review')
                    wire.pending.append(dict(method='turn/completed',params=dict(threadId='fresh-main-review',turn=dict(id='turn',status='completed',items=[dict(type='agentMessage',text=json.dumps(value))]))))
                    return {'turn':{'id':'turn'}}
                raise AssertionError(method)
            def notifications(wire):result=wire.pending;wire.pending=[];return result
            def close(wire):pass
        wire=Wire();review=MainReviewer(Trees(),store,lambda cwd:AppServer(store,transport=wire),threading.Event())
        a=attempt();a['approved_task']=dict(description='Original approved criteria')
        result=review(a,dict(main_sha=M),Path(temp),dict(ci_run_id=42))
        self.assertEqual(result['reviewer_thread_id'],'fresh-main-review')
        self.assertEqual(review(a,dict(main_sha=M),Path(temp),dict(ci_run_id=42)),result)
        self.assertEqual(wire.turns,1)


class PublicationRecoveryTests(unittest.TestCase):
    setUp=DeliveryTests.setUp
    prepared=DeliveryTests.prepared
    def test_lost_status_response_readback_does_not_republish(self):
        self.prepared();original=self.host.publish_acceptance;calls=[]
        def publish(*args):calls.append(1);original(*args);raise TimeoutError('lost status')
        self.host.publish_acceptance=publish
        self.assertEqual(self.d.merge_expected(REPO,7,H,B)['main_sha'],M)
        self.assertEqual(len(calls),1)


class ConfigurationTests(unittest.TestCase):
    def test_delivery_scope_is_explicit_private_config_and_never_assignment_prose(self):
        import json
        from task_tower.connector.cli import load_config
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            cfg=dict(version=1,connector_id='fixture-config',endpoint='http://127.0.0.1:8765',token_file=str(root/'token'),journal=str(root/'journal'),
                app_server=str(root/'codex'),projects={'p':dict(repository=str(root/'repo'),worktree_root=str(root/'trees'))},assignments=[],delivery_projects={'p':REPO})
            file=root/'config';file.write_text(json.dumps(cfg),encoding='utf-8')
            self.assertEqual(load_config(file)['delivery_projects'],{'p':REPO})
            cfg['delivery_projects']={'unapproved':REPO};file.write_text(json.dumps(cfg),encoding='utf-8')
            with self.assertRaises(ValueError):load_config(file)
    def test_source_validation_children_strip_mixed_case_github_tokens(self):
        import os
        from unittest.mock import patch
        from task_tower.connector.delivery import GitHubHost
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'environment-result'
            host=GitHubHost(None,None,{'p':REPO},token='fixture',transport=lambda *args:None)
            code="import os;from pathlib import Path;Path("+repr(str(out))+").write_text(str(any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)),encoding='utf-8')"
            with patch.dict(os.environ,{'gH_tOkEn':'fixture-only','Github_Token':'fixture-only'}):host._python(Path(temp),['-c',code])
            self.assertEqual(out.read_text(encoding='utf-8'),'False')


class GitHubProvenanceTests(unittest.TestCase):
    setUp=DeliveryTests.setUp
    prepared=DeliveryTests.prepared
    def test_acceptance_status_unblocks_protected_pr_before_final_mergeability_read(self):
        self.prepared();self.host.pr['mergeable_state']='blocked';original=self.host.publish_acceptance
        def publish(*args):
            value=original(*args);self.host.pr['mergeable_state']='clean';return value
        self.host.publish_acceptance=publish
        self.assertEqual(self.d.merge_expected(REPO,7,H,B)['main_sha'],M)
    def test_actual_postmerge_empty_pull_request_list_requires_sha_repository_and_chronology(self):
        from task_tower.connector.delivery import select_main_run
        run=dict(id=42,event='pull_request',path='.github/workflows/postmerge.yml',head_sha=H,status='completed',conclusion='success',
            created_at='2026-11-07T10:24:09Z',run_attempt=1,pull_requests=[],repository={'full_name':REPO})
        self.assertEqual(select_main_run([run],REPO,7,H,'2026-11-07T10:24:08Z')['id'],42)
        for field,value in [('head_sha','d'*40),('repository',{'full_name':'other/repo'}),('created_at','2026-11-07T10:24:07Z'),('pull_requests',[{'number':8}])]:
            bad=copy.deepcopy(run);bad[field]=value
            with self.assertRaises(ValueError):select_main_run([bad],REPO,7,H,'2026-11-07T10:24:08Z')


class BaseUpdateTests(unittest.TestCase):
    from tests.test_connector_worktrees import WorktreeTests as _Fixture
    setUp=_Fixture.setUp
    git=_Fixture.git
    def test_conflict_stays_in_same_owned_worktree_until_same_executor_resolves(self):
        import subprocess
        old=self.sha;remote=self.root/'remote.git'
        self.git('clone','--bare',str(self.repo),str(remote));self.git('remote','add','origin',str(remote))
        tree=self.w.prepare('p','attempt1',old);path=Path(tree['path'])
        def git(*args):return subprocess.run(['git',*args],cwd=path,timeout=10,check=True,capture_output=True,encoding='utf-8').stdout.strip()
        (path/'a').write_text('author',encoding='utf-8');git('add','a');git('commit','-m','author')
        (self.repo/'a').write_text('upstream',encoding='utf-8');self.git('add','a');self.git('commit','-m','upstream');new=self.git('rev-parse','HEAD');self.git('push','origin','HEAD:refs/heads/main')
        updated=self.w.prepare_revision('p','attempt1',new,dict(old_base_sha=old,new_base_sha=new))
        self.assertEqual(updated['path'],tree['path'])
        self.assertEqual(git('rev-parse','MERGE_HEAD'),new)
        with self.assertRaises(ValueError):self.w.prepare('p','attempt1',new)
        (path/'a').write_text('resolved',encoding='utf-8');git('add','a');git('commit','-m','resolve')
        source=self.w.source('p','attempt1',new)
        self.assertEqual(source['base_sha'],new)
        self.assertIn('resolved',source['diff'])


    def test_clean_upstream_merge_is_left_for_same_executor_to_commit(self):
        import subprocess
        old=self.sha;remote=self.root/'remote.git'
        self.git('clone','--bare',str(self.repo),str(remote));self.git('remote','add','origin',str(remote))
        tree=self.w.prepare('p','attempt1',old);path=Path(tree['path'])
        def git(*args):return subprocess.run(['git',*args],cwd=path,timeout=10,check=True,capture_output=True,encoding='utf-8').stdout.strip()
        (path/'a').write_text('author',encoding='utf-8');git('add','a');git('commit','-m','author')
        (self.repo/'upstream').write_text('upstream',encoding='utf-8');self.git('add','upstream');self.git('commit','-m','upstream');new=self.git('rev-parse','HEAD');self.git('push','origin','HEAD:refs/heads/main')
        self.w.prepare_revision('p','attempt1',new,dict(old_base_sha=old,new_base_sha=new))
        self.assertEqual(git('rev-parse','MERGE_HEAD'),new)
        self.assertEqual((path/'upstream').read_text(encoding='utf-8'),'upstream')
        git('commit','-m','integrate upstream')
        self.assertEqual(self.w.source('p','attempt1',new)['base_sha'],new)

class MainHostValidationTests(unittest.TestCase):
    def test_authentic_shape_bundle_requires_complete_jobs_digests_event_and_execution(self):
        import json,io,zipfile,hashlib
        from task_tower.connector.delivery import GitHubHost,verify_manifest_bundle
        from task_tower.merge_events import build_merge_event
        from task_tower.service.acceptance import accept
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        pr=dict(number=7,merged=True,state='closed',merge_commit_sha=M,merged_at='2026-11-07T10:24:08Z',body='',
            head=dict(sha=H,ref='codex/headless-attempt',repo=dict(full_name=REPO)),base=dict(sha=B,ref='main',repo=dict(full_name=REPO)))
        run=dict(id=42,event='pull_request',path='.github/workflows/postmerge.yml',head_sha=H,status='completed',conclusion='success',
            created_at='2026-11-07T10:24:09Z',run_attempt=1,pull_requests=[],repository={'full_name':REPO})
        jobs=[dict(name=n,status='completed',conclusion='success') for n in ['scope','verify-merge (windows-latest, windows)',*['merge unittest shard (windows-latest, '+str(i)+')' for i in range(4)]]]
        ids=['test.a','test.b','test.c','test.d']
        manifests=[dict(version=2,schedule='duration-balanced-v1',source_sha=M,count=4,index=i,all_ids=ids,selected_ids=[ids[i]],mode='execution',successful=True,tests_run=1,failures=0,errors=0) for i in range(4)]
        event=build_merge_event(dict(action='closed',repository=dict(full_name=REPO),pull_request=pr),REPO,'windows','passed',42,1)
        for fault in (None,'wrong_delivery_key','missing_job','cancelled_job','missing_shard','stale_manifest','inventory_only','fake_tests_run','bad_digest','expired','wrong_member','latest_failed'):
            with self.subTest(fault=fault):
                rows=copy.deepcopy(jobs);ms=copy.deepcopy(manifests);ev=copy.deepcopy(event);runs=[copy.deepcopy(run)]
                if fault=='wrong_delivery_key':ev['delivery_key']='0'*64
                if fault=='missing_job':rows.pop()
                if fault=='cancelled_job':rows[2]['conclusion']='cancelled'
                if fault=='stale_manifest':ms[0]['source_sha']='d'*40
                if fault=='inventory_only':ms[0]['mode']='inventory'
                if fault=='fake_tests_run':ms[0]['tests_run']=0
                if fault=='latest_failed':runs.append(dict(run,id=43,conclusion='failure',created_at='2026-11-07T10:25:09Z'))
                artifacts=[];zips={}
                payloads=[('task-tower-merge-7-windows','merge-event.json',ev)]+[('ci-unittest-42-'+str(i),'shard-'+str(i)+'.json',ms[i]) for i in range(4)]
                if fault=='missing_shard':payloads.pop()
                for index,(name,member,payload) in enumerate(payloads):
                    buf=io.BytesIO()
                    with zipfile.ZipFile(buf,'w') as archive:archive.writestr('wrong.json' if fault=='wrong_member' and index==0 else member,json.dumps(payload))
                    raw=buf.getvalue();digest='sha256:'+hashlib.sha256(raw).hexdigest();aid=index+1
                    artifacts.append(dict(id=aid,name=name,digest='sha256:'+'0'*64 if fault=='bad_digest' and index==0 else digest,expired=fault=='expired' and index==0,workflow_run=dict(id=42,head_sha=H)))
                    zips[aid]=raw
                class Trees:
                    projects={'p':(root,root/'trees')}
                    def _git(t,path,*args,**kw):
                        if args[0]=='fetch':return ''
                        if args[0]=='rev-list':return M+' '+B+' '+H
                        if args[0]=='rev-parse':return M
                        raise AssertionError(args)
                    def prepare_review(t,*args):return dict(path=str(root))
                reviews=[]
                def reviewer(a,merge,path,proof):
                    reviews.append(1);return dict(verdict='approve',findings=[],head_sha=M,base_sha=B,reviewer_thread_id='fresh-main')
                class HostFixture(GitHubHost):
                    def _conversations(host,*args):return True
                    def _request(host,r,method,path,payload=None):
                        if path=='/pulls/7':return pr
                        raise AssertionError(path)
                    def _pages(host,r,path,key=None):
                        if '/workflows/' in path:return runs
                        if '/jobs?' in path:return rows
                        if '/artifacts' in path:return artifacts
                        raise AssertionError(path)
                    def _python(host,path,args):
                        files=sorted(Path(args[args.index('--verify')+1]).glob('shard-*.json'))
                        from task_tower.ci_unittest import verify
                        actual=[json.loads(f.read_text(encoding='utf-8')) for f in files]
                        verify(actual,M,4)
                        if actual[0]['all_ids']!=ids:raise ValueError('fresh inventory mismatch')
                def transport(method,url,headers,payload,limit):return zips[int(url.split('/')[-2])]
                host=HostFixture(Trees(),None,{'p':REPO},token='fixture',transport=transport,reviewer=reviewer)
                a=attempt();merge=dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M)
                if fault:
                    with self.assertRaises(ValueError):host.verify_main(a,merge)
                    self.assertEqual(reviews,[])
                else:
                    proof=host.verify_main(a,merge)
                    accepted=accept(dict(a,phase='postmerge',**merge),proof)
                    self.assertEqual(accepted['accepted_evidence']['runtime_tests'],'passed')
                    self.assertEqual(len(proof['artifact_digests']),5)


class CurrentCITests(unittest.TestCase):
    setUp=DeliveryTests.setUp
    prepared=DeliveryTests.prepared
    def test_mixed_or_unexpected_skipped_jobs_and_fork_head_block_merge(self):
        for fault in ('mixed_skip','optional_skip','fork'):
            with self.subTest(fault=fault):
                self.host=Host();self.d=delivery.Delivery(self.host,self.store,{'p':REPO});self.prepared()
                if fault=='mixed_skip':self.host.checks[2]['conclusion']='skipped'
                if fault=='optional_skip':self.host.checks.append(dict(name='optional-security',head_sha=H,app='github-actions',conclusion='skipped'))
                if fault=='fork':self.host.pr['head_repository']='other/repo'
                with self.assertRaises(ValueError):self.d.merge_expected(REPO,7,H,B)
                self.assertNotIn('merge',self.host.calls)
                self.store.close();self.store=ConnectorStore(Path(self.tmp.name)/fault,'stage5-fixture');self.addCleanup(self.store.close)


class RemoteScopeTests(unittest.TestCase):
    def test_multiple_push_urls_are_rejected_before_any_push(self):
        from task_tower.connector.delivery import GitHubHost
        class Trees:
            def prepare(self,*args):return dict(path='fixture',branch='codex/headless-attempt')
            def source(self,*args):return attempt()['source']
            def _git(self,path,*args,**kw):
                if args[:2]==('remote','get-url'):
                    return 'https://github.com/'+REPO+('\nhttps://github.com/other/repo' if '--push' in args and '--all' in args else '')
                raise AssertionError(args)
        class HostFixture(GitHubHost):
            def _trusted_git(self,path,*args,**kw):return self.trees._git(path,*args)
            def _push(self,*args,**kw):raise AssertionError('push before all remote targets verified')
        h=HostFixture(Trees(),None,{'p':REPO},token='fixture',transport=lambda *args:None)
        with self.assertRaises(ValueError):h.prepare_pr(attempt())

class MainRestartTests(unittest.TestCase):
    def test_unknown_main_review_start_survives_real_journal_reopen_without_second_turn(self):
        import threading
        from task_tower.connector.delivery import MainReviewer
        from task_tower.connector.app_server import AppServer
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        store=ConnectorStore(root/'journal','main-restart-fixture');self.addCleanup(store.close)
        class Trees:
            def _git(self,path,*args,**kw):return 'whole main diff'
        calls=[]
        class Wire:
            def request(self,method,params):
                if method=='thread/start':return {'thread':{'id':'fresh-main'}}
                calls.append(method);raise TimeoutError('lost turn start')
            def close(self):pass
        a=attempt();a['approved_task']=dict(description='Original criteria')
        reviewer=MainReviewer(Trees(),store,lambda cwd:AppServer(store,transport=Wire()),threading.Event())
        with self.assertRaises(ValueError):reviewer(a,dict(main_sha=M),root,{})
        store.close();store=ConnectorStore(root/'journal','main-restart-fixture');self.addCleanup(store.close)
        reviewer=MainReviewer(Trees(),store,lambda cwd:self.fail('new app after unknown start'),threading.Event())
        with self.assertRaises(ValueError):reviewer(a,dict(main_sha=M),root,{})
        self.assertEqual(calls,['turn/start']);self.assertEqual(store.pending_events(),[])


class HTTPBudgetTests(unittest.TestCase):
    def test_header_reads_cannot_continue_after_total_request_deadline(self):
        import http.client,io,socket
        from unittest.mock import patch
        from task_tower.connector.delivery import bounded_http
        clock=[0];reads=[]
        class Raw(io.RawIOBase):
            def __init__(self,raw):self.raw=raw
            def readable(self):return True
            def readinto(self,buffer):reads.append(1);return self.raw.readinto(buffer)
            def close(self):self.raw.close();super().close()
        class Socket:
            def __init__(self,sock):self.sock=sock
            def __getattr__(self,key):return getattr(self.sock,key)
            def makefile(self,*args,**kw):return io.BufferedReader(Raw(self.sock.makefile('rb',buffering=0)))
        class Connection:
            def __init__(self,*args,**kw):
                left,right=socket.socketpair();right.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}');right.close();self.sock=Socket(left)
            def connect(self):pass
            def request(self,*args):clock[0]=31
            def getresponse(self):
                r=http.client.HTTPResponse(self.sock)
                try:r.begin();return r
                except Exception:r.close();raise
            def close(self):self.sock.close()
        with patch('http.client.HTTPSConnection',Connection),patch('time.monotonic',lambda:clock[0]):
            with self.assertRaises((TimeoutError,ValueError)):bounded_http('GET','https://api.github.com/fixed',{},None,100)
        self.assertEqual(reads,[])


class FetchBudgetTests(unittest.TestCase):
    def test_success_response_after_expired_fetch_budget_stops_before_any_source_read(self):
        from unittest.mock import patch
        from task_tower.connector.delivery import GitHubHost
        clock=[0];calls=[]
        class Trees:
            projects={'p':(Path('repo'),Path('trees'))}
            def _git(self,path,*args,**kw):
                calls.append(args)
                if args==('fetch','origin','main'):clock[0]=61;return ''
                raise AssertionError('source read after expired fetch')
        host=GitHubHost(Trees(),None,{'p':REPO},token='fixture',transport=lambda *args:self.fail('network after expired fetch'))
        with patch('time.monotonic',lambda:clock[0]):
            with self.assertRaises(ValueError):host.verify_main(attempt(),dict(repository=REPO,pr_number=7,main_sha=M))
        self.assertEqual(calls,[('fetch','origin','main')])
    def test_local_git_validations_share_one_ten_second_budget(self):
        from unittest.mock import patch
        from task_tower.connector.delivery import GitHubHost
        clock=[0];budgets=[]
        class Trees:
            projects={'p':(Path('repo'),Path('trees'))}
            def _git(self,path,*args,**kw):
                if args[0]=='fetch':return ''
                if args[0]=='rev-parse':clock[0]=9;return M
                if args[0]=='rev-list':budgets.append(kw['timeout']);raise ValueError('intentional bounded stop')
                raise AssertionError(args)
        host=GitHubHost(Trees(),None,{'p':REPO},token='fixture',transport=lambda *args:None)
        with patch('time.monotonic',lambda:clock[0]):
            with self.assertRaises(ValueError):host.verify_main(attempt(),dict(repository=REPO,pr_number=7,main_sha=M))
        self.assertEqual(budgets,[1])


class EffectiveGitDestinationTests(unittest.TestCase):
    def test_actual_host_read_and_push_share_config_including_rewrites_and_credentials(self):
        import os
        from unittest.mock import patch
        from task_tower.connector.delivery import GitHubHost
        from task_tower.connector.worktrees import Worktrees
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup);path=Path(root.name)
        class Trees:
            _git=Worktrees._git
            def prepare(self,*args):return dict(path=str(path),branch='codex/headless-attempt')
            def source(self,*args):return attempt()['source']
        class HostFixture(GitHubHost):
            def _pages(self,*args):return [dict(number=7)]
            def read_pr(self,*args):return copy.deepcopy(Host().pr)
        for kind in ('global_insteadOf','global_pushInsteadOf','system_insteadOf','system_pushInsteadOf','multiple','credential_config_only'):
            with self.subTest(kind=kind):
                calls=[]
                def runner(argv,cwd,timeout,env=None,capture=None,**kwargs):
                    calls.append((list(argv),dict(env)))
                    enabled=(kind.startswith('global') and env.get('GIT_CONFIG_GLOBAL')!=os.devnull) or (kind.startswith('system') and env.get('GIT_CONFIG_NOSYSTEM')!='1')
                    remote='https://github.com/'+REPO
                    if enabled and (kind.endswith('_insteadOf') or '--push' in argv or 'push' in argv):remote='https://other.invalid/escape'
                    if kind=='multiple' and '--push' in argv and '--all' in argv:remote+='\nhttps://other.invalid/escape'
                    text=remote if 'remote' in argv else ''
                    Path(capture['directory'],'stdout.log').write_text(text,encoding='utf-8');Path(capture['directory'],'stderr.log').write_text('',encoding='utf-8')
                    return dict(status='passed',exit_code=0,cleanup_confirmed=True)
                host=HostFixture(Trees(),None,{'p':REPO},token='fixture',transport=lambda *args:self.fail('network effect'))
                with patch('task_tower.connector.worktrees.run_command',runner),patch('task_tower.processes.run_command',runner),patch.dict(os.environ,{'gH_tOkEn':'fixture-only'}):
                    if kind=='credential_config_only':host.prepare_pr(attempt())
                    else:
                        with self.assertRaises(ValueError):host.prepare_pr(attempt())
                pushes=[(argv,env) for argv,env in calls if 'push' in argv]
                if kind!='credential_config_only':self.assertEqual(pushes,[])
                else:
                    self.assertEqual(len(pushes),1)
                    push_env=pushes[0][1]
                    self.assertNotEqual(push_env.get('GIT_CONFIG_GLOBAL'),os.devnull);self.assertNotEqual(push_env.get('GIT_CONFIG_NOSYSTEM'),'1')
                    self.assertTrue(any(k.upper()=='GH_TOKEN' and v=='fixture-only' for k,v in push_env.items()))
                    for argv,env in calls:
                        if 'remote' in argv:self.assertTrue(env==push_env,'host configuration differs')


class NativeGitRewriteTests(unittest.TestCase):
    def test_effective_global_system_rewrites_and_multiple_urls_with_isolated_native_git_configs(self):
        import os,subprocess
        from unittest.mock import patch
        from task_tower.connector.delivery import GitHubHost
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        for kind in ('global_insteadOf','global_pushInsteadOf','system_insteadOf','system_pushInsteadOf','multiple','allowed_credentials'):
            with self.subTest(kind=kind):
                directory=root/kind;directory.mkdir();repo=directory/'repo';repo.mkdir()
                global_config=directory/'global';system_config=directory/'system'
                global_config.write_text('[credential]\n helper = fixture-not-executed\n',encoding='utf-8');system_config.write_text('',encoding='utf-8')
                env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
                env.update(GIT_CONFIG_GLOBAL=str(global_config),GIT_CONFIG_SYSTEM=str(system_config),GIT_CONFIG_NOSYSTEM='0',GIT_TERMINAL_PROMPT='0')
                def git(*args):return subprocess.run(['git',*args],cwd=repo,env=env,timeout=10,capture_output=True,encoding='utf-8',check=True).stdout.strip()
                git('init');git('remote','add','origin','https://github.com/'+REPO)
                if kind.startswith(('global_','system_')):
                    config=global_config if kind.startswith('global') else system_config
                    rewrite='pushInsteadOf' if kind.endswith('pushInsteadOf') else 'insteadOf'
                    with config.open('a',encoding='utf-8') as file:file.write('[url "https://forbidden.invalid/"]\n '+rewrite+' = https://github.com/\n')
                if kind=='multiple':
                    git('config','--add','remote.origin.pushurl','https://github.com/'+REPO)
                    git('config','--add','remote.origin.pushurl','https://forbidden.invalid/escape')
                host=GitHubHost(None,None,{'p':REPO},token='fixture',transport=lambda *args:self.fail('network effect'))
                with patch.object(host,'_git_environment',return_value=env):
                    if kind=='allowed_credentials':host._remote(repo,REPO)
                    else:
                        with self.assertRaises(ValueError):host._remote(repo,REPO)
