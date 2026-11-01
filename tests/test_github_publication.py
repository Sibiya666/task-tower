import unittest
import tempfile
from pathlib import Path
from task_tower.postmerge_journal import Journal
from task_tower.github_publication import GitHubPublisher, PublicationError

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
