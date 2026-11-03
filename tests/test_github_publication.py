import unittest
import tempfile
from pathlib import Path
from task_tower.postmerge_journal import Journal
from task_tower.github_publication import GitHubPublisher, PublicationError


class BoundedPublicationTests(unittest.TestCase):
    def setUp(self):
        import uuid
        from types import SimpleNamespace
        from tests import test_postmerge_worker as wf, test_pr_review as rf
        from task_tower import tasks
        from task_tower.pr_journal import PRJournal, BINDING
        from task_tower.pr_policy import policy_fingerprint
        from task_tower.pr_review import validate_pr_review
        from task_tower.pr_evidence import PostmergeReviewBinding, PublicationContext
        self.f=wf.WorkerTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        head=self.f.sha; base=self.f.git('rev-parse','HEAD^')
        tree=self.f.git('rev-parse','HEAD^{tree}')
        merge=self.f.git('-c','user.name=Fixture','-c','user.email=f@example.invalid','commit-tree',tree,'-p',base,'-p',head,'-m','merge')
        self.f.sha=merge; self.f.bundle['merge_commit']=merge
        self.f.git('update-ref','refs/remotes/origin/main',merge)
        self.r=rf.ReviewTests(); self.r.setUp(); self.addCleanup(self.r.doCleanups)
        identities=dict(repository='owner/repo',pr_number=1,issue=9,issue_id=900,task_id='TT-WORKER-1',head_sha=head,base_sha=base)
        self.r.req.update(identities); self.r.req['input'].update(identities)
        self.r.req['input_sha256']=policy_fingerprint(self.r.req['input'])
        self.r.child(); pr_envelope=self.r.run_review(); self.pr_receipt=validate_pr_review(pr_envelope,self.r.req,())
        self.binding={k:self.r.req[k] for k in BINDING}
        self.j=PRJournal(self.f.root.parent/(self.f.root.name+'-pr.sqlite'))
        self.addCleanup(lambda:self.j.path.unlink(missing_ok=True))
        self.owner=str(uuid.uuid4()); ownership=self.j.owner(self.owner); ownership.__enter__(); self.addCleanup(ownership.__exit__,None,None,None)
        self.j.admit(self.binding)
        self.advance('validating'); self.advance('reviewing')
        role=self.j.begin_effect('owner/repo',1,self.owner,'pr_review',dict(reviewer_instance_id=self.r.req['reviewer_instance_id'],request_sha256=self.binding['input_sha256']))
        self.j.observe(role['effect_id'],self.owner,dict(status='confirmed',result_sha256=pr_envelope['result_sha256'],receipt_sha256=self.pr_receipt['receipt_sha256'],reviewer_instance_id=self.r.req['reviewer_instance_id'],process={k:pr_envelope['process'][k] for k in ('pid','exit_code','started','cleanup_confirmed')}))
        self.advance('reviewed',pr_receipt_sha256=self.pr_receipt['receipt_sha256'],reviewer_instance_id=self.r.req['reviewer_instance_id'])
        self.advance('publishing_acceptance')
        for kind,payload in [('acceptance_status',dict(state='success',context='task-tower/pr-acceptance',sha=head,target_url='https://github.com/owner/repo/pull/1',description='Accepted',receipt_sha256=self.pr_receipt['receipt_sha256'])),('acceptance_review',dict(commit_id=head,event='COMMENT',body='checked',receipt_sha256=self.pr_receipt['receipt_sha256']))]:
            effect=self.j.begin_effect('owner/repo',1,self.owner,kind,payload)
            self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',remote_id=42,body_sha256='7'*64,author='bot'))
        self.advance('accepted'); self.j.acquire_barrier('owner/repo',1,self.owner,self.binding)
        effect=self.j.begin_effect('owner/repo',1,self.owner,'merge',dict(sha=head,merge_method='merge',merge_action='direct_merge',bypass_rules=False))
        self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',merge_commit=merge,main_sha=merge,parents=[base,head],result='merged'))
        self.advance('awaiting_postmerge')
        import tempfile
        from tests.test_reviewer import loaded_postmerge_profile
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower.reviewer import ReviewRunner
        installation=tempfile.TemporaryDirectory();self.addCleanup(installation.cleanup)
        profile,self.selected_policy_task=loaded_postmerge_profile(Path(installation.name),self.f.root,'TT-WORKER-1',counter=self.f.counter)
        self.assertEqual(self.selected_policy_task['readiness_reason'],'writer_boundary_required')
        self.worker=self.f.worker(reviewer=ReviewRunner(profile))
        card=tasks.load_task(self.f.card)
        values=dict(pr_binding=self.binding,merge_commit=merge,bundle_sha256=policy_fingerprint(self.f.bundle),snapshot_sha256=tasks.task_snapshot(card),reviewer_instance_id=str(uuid.uuid4()),excluded_instances=(self.r.req['reviewer_instance_id'],),profile_sha256=profile_fingerprint(self.worker.reviewer.config),instructions_sha256=profile_fingerprint(self.worker.reviewer.config['superpowers']))
        material=dict(values,excluded_instances=list(values['excluded_instances']))
        request_hash=policy_fingerprint(dict(binding=material,task=card,bundle=self.f.bundle))
        effect=self.j.begin_effect('owner/repo',1,self.owner,'postmerge_review',dict(reviewer_instance_id=values['reviewer_instance_id'],request_sha256=request_hash,merge_commit=merge))
        binding=PostmergeReviewBinding(**values,request_sha256=request_hash,effect_id=effect['effect_id'])
        self.row=self.worker.review_one(card['id'],self.f.bundle,review_binding=binding)
        post=self.row['host_review']; self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',result_sha256=post['result_sha256'],receipt_sha256=post['receipt_sha256'],reviewer_instance_id=post['reviewer_instance_id'],process=post['process']))
        self.advance('awaiting_closure',postmerge_receipt_sha256=post['receipt_sha256'])
        self.context=PublicationContext(connection=SimpleNamespace(repository='owner/repo',trusted_publishers=['bot']),source=self.worker.source,
            binding=dict(self.binding,merge_commit=merge),main_reader=lambda:self.f.git('rev-parse','refs/remotes/origin/main'),pr_receipt=self.pr_receipt,postmerge_review=post)
        self.store=WorkerPublicationTests.publisher_store(self.f)
        from task_tower.github_tasks import parse_metadata
        self.store.metadata=lambda issue:parse_metadata(issue.get('body'))
        self.writes=[]; request=self.store.request
        def transport(method,path,payload=None):
            if method in ('POST','PATCH'):
                self.writes.append(method)
                pub=self.j.publication(self.identity())
                self.assertEqual(pub['phase'],'comment_intent' if method=='POST' else 'close_intent')
            return request(method,path,payload)
        self.store.request=transport
        self.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=self.store,verify_source=self.worker.source.poll,publication_context=self.context)

    def advance(self,state,**extra):
        row=self.j.get('owner/repo',1)
        return self.j.transition('owner/repo',1,self.owner,dict(state=row['state'],input_sha256=row['input_sha256']),dict(state=state,**extra))

    def identity(self):
        from task_tower.github_publication import publication_id
        receipt=self.publisher.receipt(self.f.card,self.f.bundle,self.row,self.worker.required); receipt['issue_id']=900
        return publication_id(receipt)

    def step(self):
        return self.publisher.publish_step(self.f.card,self.f.bundle,self.row,self.worker.required,effect_store=self.j,owner_id=self.owner)

    def test_comment_close_and_verified_published_are_distinct_ticks(self):
        self.assertEqual(self.step()['phase'],'comment_confirmed'); self.assertEqual(self.writes,['POST'])
        self.assertEqual(self.step()['phase'],'closure_observed'); self.assertEqual(self.writes,['POST','PATCH'])
        self.assertEqual(self.step()['status'],'published'); self.assertEqual(self.writes,['POST','PATCH'])
        self.assertIsNotNone(self.j.barrier('owner/repo'))

    def test_lost_comment_and_close_response_never_repeat_write(self):
        self.store.fail_post=True
        self.assertEqual(self.step()['status'],'unknown')
        self.assertEqual(self.step()['phase'],'comment_confirmed'); self.assertEqual(self.writes,['POST'])
        self.store.fail_close=True
        self.assertEqual(self.step()['status'],'unknown')
        self.assertEqual(self.step()['phase'],'closure_observed'); self.assertEqual(self.writes,['POST','PATCH'])
        self.assertEqual(self.step()['status'],'published')

    def test_comment_intent_before_send_is_never_replayed(self):
        original=self.store.request
        def crash(method,path,payload=None):
            if method=='POST': raise KeyboardInterrupt('before send')
            return original(method,path,payload)
        self.store.request=crash
        with self.assertRaises(KeyboardInterrupt): self.step()
        self.store.request=original
        self.assertEqual(self.step()['status'],'unknown'); self.assertEqual(self.writes,[])

    def test_changed_main_does_not_close(self):
        self.step(); self.f.git('update-ref','refs/remotes/origin/main',self.binding['head_sha'])
        self.assertNotEqual(self.step()['status'],'published'); self.assertEqual(self.writes,['POST'])

    def test_live_closed_issue_alone_does_not_publish(self):
        self.store.closed=True
        self.assertNotEqual(self.step()['status'],'published')
        self.assertEqual(self.writes,['POST'])

    def test_comment_ack_crash_reconciles_once_without_reposting(self):
        from unittest.mock import patch
        observe=self.j.observe
        def crash(effect_id,*args):
            if self.j.effect(effect_id)['kind']=='comment_post': raise KeyboardInterrupt('before ack save')
            return observe(effect_id,*args)
        with patch.object(self.j,'observe',crash),self.assertRaises(KeyboardInterrupt): self.step()
        self.assertEqual(self.j.publication(self.identity())['phase'],'comment_intent')
        self.assertEqual(self.step()['phase'],'comment_confirmed'); self.assertEqual(self.writes,['POST'])

    def test_close_intent_before_send_remains_unknown_without_second_patch(self):
        self.step(); original=self.store.request
        def crash(method,path,payload=None):
            if method=='PATCH': raise KeyboardInterrupt('before send')
            return original(method,path,payload)
        self.store.request=crash
        with self.assertRaises(KeyboardInterrupt): self.step()
        self.store.request=original
        self.assertEqual(self.step()['status'],'unknown'); self.assertEqual(self.writes,['POST'])
        self.assertEqual(self.step()['status'],'unknown'); self.assertEqual(self.writes,['POST'])

    def test_close_ack_crash_uses_positive_genuine_closure_without_repatch(self):
        from unittest.mock import patch
        self.step(); observe=self.j.observe
        def crash(effect_id,*args):
            if self.j.effect(effect_id)['kind']=='issue_close': raise KeyboardInterrupt('before ack save')
            return observe(effect_id,*args)
        with patch.object(self.j,'observe',crash),self.assertRaises(KeyboardInterrupt): self.step()
        self.assertEqual(self.step()['phase'],'closure_observed'); self.assertEqual(self.writes,['POST','PATCH'])
        self.assertEqual(self.step()['status'],'published'); self.assertEqual(self.writes,['POST','PATCH'])

    def test_lost_owner_returns_readonly_without_owner_cas_or_next_write(self):
        from unittest.mock import patch
        self.step()
        # A fresh journal instance cannot take over another watch's owner.
        self.j=type(self.j)(self.j.path)
        def forbidden(*args,**kwargs): raise AssertionError('Owner-only mutation after loss')
        with patch.object(self.j,'observe',forbidden),patch.object(self.j,'record_publication',forbidden),patch.object(self.j,'begin_effect',forbidden):
            self.assertEqual(self.step()['status'],'unknown')
        self.assertEqual(self.writes,['POST']);self.assertFalse(self.store.closed)

    def test_changed_lifecycle_author_never_closes(self):
        self.step(); self.store.comments[0]['user']['login']='untrusted'
        self.assertNotEqual(self.step()['status'],'published'); self.assertEqual(self.writes,['POST'])

class PublicationTests(unittest.TestCase):
    def test_claim_has_owner_and_expiring_lease(self):
        with tempfile.TemporaryDirectory() as d:
            a=Journal(Path(d).resolve()/'journal.sqlite'); b=Journal(a.path)
            self.assertTrue(a.claim_publication('id','one',now=100,lease_seconds=120))
            self.assertFalse(b.claim_publication('id','two',now=110,lease_seconds=120))
            self.assertTrue(b.claim_publication('id','two',now=221,lease_seconds=120))
            with self.assertRaises(ValueError): a.finish_publication('id','one','published')
            b.finish_publication('id','two','published')
            self.assertFalse(a.claim_publication('id','three',now=500,lease_seconds=120))

    def test_mapping_is_explicit_and_validated(self):
        for config in ({}, {'issue_tasks':{'TT-A-1':True},'publisher_account':'bot'},
                       {'issue_tasks':{'bad':9},'publisher_account':'bot'}):
            with self.assertRaises(ValueError): GitHubPublisher('a/b',config)

class WorkerPublicationTests(__import__('test_postmerge_worker').WorkerTests):
    def test_accepted_row_is_published_without_second_review(self):
        calls=[]
        class Publisher:
            def publish(inner,*args):
                calls.append(args[2]['status']); return {'status':'published'}
        worker=self.worker(); worker.publisher=Publisher()
        worker.once(); worker.once()
        self.assertEqual(calls,['done','done'])
        self.assertEqual(self.counter.read_text(),'x')

    def test_publication_failure_does_not_change_acceptance(self):
        class Publisher:
            def publish(inner,*args): raise ValueError('private secret')
        worker=self.worker(); worker.publisher=Publisher()
        rows=worker.once()
        self.assertEqual(rows[0]['status'],'done')
        self.assertEqual(rows[0]['publication']['status'],'failed')
        self.assertNotIn('secret',str(rows))
        worker.once(); self.assertEqual(self.counter.read_text(),'x')

    def publisher_store(self):
        class Store:
            def __init__(inner):
                inner.comments=[];inner.closed=False;inner.posts=0;inner.fail_post=False;inner.fail_close=False;inner.author='bot'
            def get(inner, number):
                return dict(id=900,number=number,state='closed' if inner.closed else 'open',state_reason='completed' if inner.closed else None,
                    body='user prose\n<!-- task-tower:v1\n'+__import__('json').dumps(dict(version=1,kind='task',legacy_id='TT-WORKER-1'))+'\n-->')
            def request(inner,method,path,payload=None):
                if path.startswith('/compare/'): return {'status':'identical'}
                if method=='GET': return inner.comments
                if method=='POST':
                    inner.posts+=1
                    comment=dict(id=inner.posts,body=payload['body'],user={'login':inner.author})
                    inner.comments.append(comment)
                    if inner.fail_post: inner.fail_post=False;raise OSError('secret')
                    return comment
                if method=='PATCH':
                    self.assertEqual(payload,{'state':'closed','state_reason':'completed'})
                    inner.closed=True
                    if inner.fail_close: inner.fail_close=False;raise OSError('secret')
                    return inner.get(9)
        return Store()

    def test_publish_success_and_ambiguous_post_restart_no_model(self):
        store=self.publisher_store();store.fail_post=True
        publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        worker=self.worker();worker.publisher=publisher
        first=worker.once();self.assertEqual(first[0]['publication']['status'],'failed')
        second=worker.once();self.assertEqual(second[0]['publication']['status'],'published')
        self.assertEqual(store.posts,1);self.assertTrue(store.closed)
        worker.once();self.assertEqual(store.posts,1);self.assertEqual(self.counter.read_text(),'x')

    def test_ambiguous_close_is_reconciled(self):
        store=self.publisher_store();store.fail_close=True
        worker=self.worker();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        self.assertEqual(worker.once()[0]['publication']['status'],'failed')
        self.assertEqual(worker.once()[0]['publication']['status'],'published')
        self.assertEqual(store.posts,1);self.assertEqual(self.counter.read_text(),'x')

    def test_actual_wrong_author_never_closes(self):
        store=self.publisher_store();store.author='attacker'
        worker=self.worker();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        self.assertEqual(worker.once()[0]['publication']['status'],'failed')
        self.assertEqual(worker.once()[0]['publication']['status'],'failed')
        self.assertFalse(store.closed);self.assertEqual(store.posts,1)

    def test_stale_evidence_never_posts(self):
        worker=self.worker();worker.once();(self.root/'evidence.md').write_text('tampered')
        store=self.publisher_store();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        self.assertEqual(worker.once()[0]['publication']['status'],'failed')
        self.assertEqual(store.posts,0)

    def test_existing_rejection_blocks_approval(self):
        store=self.publisher_store()
        store.comments=[dict(id=99,body='<!-- task-tower:lifecycle:v1\n'+__import__('json').dumps({'remote_attempt':{'status':'needs_input'},'status':'needs_input'})+'\n-->',user={'login':'bot'})]
        worker=self.worker();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        self.assertEqual(worker.once()[0]['publication']['status'],'failed')
        self.assertFalse(store.closed);self.assertEqual(store.posts,0)

    def test_unmapped_done_task_has_no_publication_failure(self):
        worker=self.worker();worker.once()
        store=self.publisher_store()
        worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-OTHER-1':9},'publisher_account':'bot'},store=store)
        rows=worker.once()
        self.assertEqual(rows[0]['status'],'done')
        self.assertNotIn('publication',rows[0])
        self.assertEqual(store.posts,0)
        self.assertEqual(self.counter.read_text(),'x')

    def test_failed_publication_records_safe_phase_and_category(self):
        from task_tower.github_tasks import GitHubRequestError
        store=self.publisher_store()
        original=store.request
        def request(method,path,payload=None):
            if method=='POST': raise GitHubRequestError(http_status=403)
            return original(method,path,payload)
        store.request=request
        worker=self.worker();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=store)
        row=worker.once()[0]
        self.assertEqual(row['publication']['detail'],'comment_post: http_403')
        self.assertEqual(worker.journal.rows()[0]['publication']['detail'],'comment_post: http_403')
        self.assertEqual(row['status'],'done')

    def conflicting_history_case(self, edit_after_post):
        import json
        from types import SimpleNamespace
        from task_tower.github_tasks import GitHubTasks
        store=self.publisher_store()
        store.comments=[dict(id=1,body='Ordinary project discussion',user={'login':'bot'})]
        store.posts=1
        patches=[]
        rejection='<!-- task-tower:lifecycle:v1\n'+json.dumps({'status':'needs_input','remote_attempt':{'status':'needs_input','run_id':'999','run_attempt':'1'}})+'\n-->'
        def transport(method,url,headers,payload,limit):
            path=url.removeprefix('https://api.github.com/repos/owner/repo')
            if method=='GET' and path=='/issues/9': return json.dumps(store.get(9)).encode()
            if method=='PATCH':
                patches.append(payload)
                raise OSError('Uncertain transport response')
            result=store.request(method,path,payload)
            if method=='POST' and edit_after_post: store.comments[0]['body']=rejection
            return json.dumps(result).encode()
        client=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
        worker=self.worker();worker.publisher=GitHubPublisher('owner/repo',{'issue_tasks':{'TT-WORKER-1':9},'publisher_account':'bot'},store=client)
        first=worker.once()[0]
        self.assertEqual(first['status'],'done')
        self.assertEqual(first['publication']['status'],'failed')
        if edit_after_post:
            self.assertEqual(first['publication']['detail'],'final_remote: proof_rejected')
            self.assertEqual(patches,[])
        else:
            self.assertEqual(first['publication']['detail'],'issue_close: network')
            self.assertEqual(len(patches),1)
            store.comments[0]['body']=rejection
        retried=worker.once()[0]
        self.assertEqual(retried['publication']['status'],'failed')
        self.assertEqual(retried['publication']['detail'],'remote_check: proof_rejected')
        self.assertFalse(store.closed)
        self.assertEqual(len(patches),0 if edit_after_post else 1)
        self.assertEqual(store.posts,2)
        self.assertEqual(self.counter.read_text(),'x')
        self.assertEqual(worker.journal.rows()[0]['status'],'done')

    def test_edited_older_lifecycle_blocks_retry_after_uncertain_patch(self):
        self.conflicting_history_case(False)

    def test_edited_older_lifecycle_between_post_and_close_blocks_close(self):
        self.conflicting_history_case(True)

class SafeTransportDiagnostics(unittest.TestCase):
    def test_http_status_is_retained_without_sensitive_error_data(self):
        import io
        import urllib.error
        from types import SimpleNamespace
        from task_tower.github_tasks import GitHubTasks
        def transport(*args):
            raise urllib.error.HTTPError('https://secret-token.invalid',403,'secret reason',{'Secret':'secret header'},io.BytesIO(b'secret body'))
        store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
        with self.assertRaises(Exception) as caught:
            store.request('POST','/issues/9/comments',{'body':'receipt'})
        self.assertEqual(str(caught.exception),'GitHub HTTP 403')
        self.assertEqual(caught.exception.http_status,403)
        self.assertNotIn('secret',str(caught.exception))

    def test_network_error_omits_sensitive_message(self):
        from types import SimpleNamespace
        from task_tower.github_tasks import GitHubTasks
        def transport(*args): raise OSError('secret token in network error')
        store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
        with self.assertRaises(Exception) as caught: store.request('GET','/issues/9')
        self.assertEqual(str(caught.exception),'GitHub network unavailable')
