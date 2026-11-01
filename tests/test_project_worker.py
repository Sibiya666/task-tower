import copy
import hashlib
import io
import json
import zipfile
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
from task_tower.project_worker import ProjectWorker, verified_done, issue_lifecycle, LIFECYCLE

class Store:
    def __init__(self):
        self.issue = {'number': 1, 'body': '', 'state': 'open'}
        self.meta = {'version': 1, 'kind': 'task'}
        self.calls = []
        self.fail_close = False
    def get(self, number): return copy.deepcopy(self.issue)
    def metadata(self, issue): return copy.deepcopy(self.meta)
    def put_metadata(self, number, metadata, **fields):
        if fields.get('state') == 'closed' and self.fail_close: raise OSError('offline')
        self.meta = copy.deepcopy(metadata)
        self.issue.update(fields)
    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return [] if '/comments?' in path else {'status':'completed','event':'workflow_dispatch','head_branch':'main','path':'.github/workflows/task-tower-project.yml','repository':{'full_name':'a/b'}}

class ProjectWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store()
        self.worker = ProjectWorker(SimpleNamespace(repository='a/b', checkout=Path(self.temp.name)),
            {'issue_tasks': {'1': 'docs/tasks/TT-X.json'}, 'state_dir': self.temp.name}, self.store,
            None, None, run_id='42')
    def test_dispatch_persists_pending_and_reconciles(self):
        self.worker.dispatch(1)
        self.assertNotIn('remote_attempt',self.store.meta)
        self.assertEqual(self.store.calls[0][1],'/issues/1/comments')
        self.assertEqual(len(self.store.calls),2)
    def test_running_is_never_implicitly_repeated(self):
        self.store.meta['remote_attempt'] = {'status': 'running', 'run_id': '41'}
        with self.assertRaisesRegex(ValueError, 'recovery'):
            self.worker.consume(1)
        self.assertEqual(len(self.store.calls),1)
    def test_recovery_requires_confirm_and_finished_authoritative_run(self):
        self.store.meta['remote_attempt'] = {'status': 'running', 'run_id': '41'}
        with self.assertRaises(ValueError): self.worker._recover_serialized(1, False)
        self.worker._recover_serialized(1, True)
        self.assertEqual(self.store.meta['remote_attempt']['status'], 'queued')
    def test_review_persisted_before_failed_close_and_reused(self):
        self.worker._prepare = lambda number: ({'id':'TT-X', 'executor':'dev'}, {'merge_commit':'a'*40}, 'stable')
        reviews = []
        self.worker._review = lambda card, bundle: reviews.append(1) or dict(task_id='TT-X', commit='a'*40, verdict='approve', summary='ok', findings=[])
        self.store.fail_close = True
        with self.assertRaises(OSError): self.worker.consume(1)
        self.store.fail_close = False
        self.worker.consume(1)
        self.assertEqual(reviews, [1])
        self.assertEqual(self.store.issue['state'], 'closed')
    def test_missing_remote_receipt_requires_recovery(self):
        self.store.meta['remote_attempt'] = {'status':'reviewed','run_id':'41'}
        self.worker._remote_receipt = lambda number,attempt: None
        with self.assertRaisesRegex(ValueError, 'recovery'): self.worker.consume(1)

    def test_artifact_done_requires_workflow_main_digest_and_ci(self):
        bundle = {'merge_commit':'a'*40, 'task_ids':['TT-X'], 'platforms':dict(windows='passed',macos='passed',linux='passed')}
        receipt = {'repository':'a/b','issue':1,'run_id':'41','run_attempt':'1','bundle':bundle,
                   'review':{'verdict':'approve','commit':'a'*40,'task_id':'TT-X'},
                   'required_platforms':['windows','macos','linux'],
                   'policy':{'reviewer':'postmerge-agent','executor':'dev','superpowers_sha256':'c'*64}}
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive: archive.writestr('1.json',json.dumps(receipt))
        raw=data.getvalue()
        artifact={'id':1,'name':'task-tower-review-1-1','expired':False,'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),
                  'workflow_run':{'id':41,'head_sha':'b'*40}}
        source=SimpleNamespace(_pages=lambda *a:[artifact],_get=lambda *a,**kw:raw,_id=lambda n:n,poll=lambda:[bundle])
        run={'status':'completed','run_attempt':1,'event':'workflow_dispatch','head_branch':'main',
             'path':'.github/workflows/task-tower-project.yml','repository':{'full_name':'a/b'},'head_sha':'b'*40}
        self.store.request=lambda method,path,payload=None: [] if '/comments?' in path else (run if '/actions/runs/' in path else {'status':'ahead'})
        self.store.meta['remote_attempt']={'status':'done','run_id':'41'}
        self.assertTrue(verified_done(self.worker.connection,self.store,source,self.store.issue))
        run['head_branch']='feature'
        self.assertFalse(verified_done(self.worker.connection,self.store,source,self.store.issue))
        run['head_branch']='main'
        artifact['digest']='sha256:forged'
        self.assertFalse(verified_done(self.worker.connection,self.store,source,self.store.issue))
        # A connected project may require Linux only; it cannot omit that check.
        receipt['required_platforms']=['linux']
        def repack():
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w') as archive: archive.writestr('1.json',json.dumps(receipt))
            packed=output.getvalue()
            artifact['digest']='sha256:'+hashlib.sha256(packed).hexdigest()
            source._get=lambda *a,**kw:packed
        repack()
        self.assertTrue(verified_done(self.worker.connection,self.store,source,self.store.issue))
        bundle['platforms']['linux']='failed'
        repack()
        self.assertFalse(verified_done(self.worker.connection,self.store,source,self.store.issue))
        bundle['platforms']['linux']='passed'
        receipt['required_platforms']=['linux','linux']
        repack()
        self.assertFalse(verified_done(self.worker.connection,self.store,source,self.store.issue))


    def test_nonmain_and_failed_ci_do_not_run_reviewer(self):
        bundle={'repository':'a/b','task_ids':['TT-X'],'merge_commit':'a'*40,'run_id':'1','attempt':'1',
                'platforms':dict(windows='passed',macos='passed',linux='passed')}
        self.worker.source=SimpleNamespace(poll=lambda:[bundle])
        self.worker._refresh=lambda:None
        with patch('task_tower.project_worker.tasks._check_commit',side_effect=ValueError('not main')):
            with self.assertRaisesRegex(ValueError,'not main'): self.worker.consume(1)
        bundle['platforms']['linux']='failed'
        with self.assertRaisesRegex(ValueError,'CI'): self.worker.consume(1)
        self.assertEqual(self.store.issue['state'],'open')

    def test_other_machine_reuses_verified_receipt_without_review(self):
        bundle={'merge_commit':'a'*40}
        receipt={'snapshot':'stable','bundle':bundle,'run_id':'41','run_attempt':'1',
                 'review':dict(task_id='TT-X',commit='a'*40,verdict='approve',summary='ok',findings=[])}
        self.store.meta['remote_attempt']={'status':'running','run_id':'41'}
        self.worker._remote_receipt=lambda number,attempt:receipt
        self.worker._prepare=lambda number:({'id':'TT-X'},bundle,'stable')
        self.worker._review=lambda *a:self.fail('review repeated')
        self.worker.consume(1)
        self.assertEqual(self.store.issue['state'],'closed')

    def test_lifecycle_append_preserves_user_body_and_uses_latest_comment(self):
        calls=[]
        store=SimpleNamespace(metadata=lambda issue:{'version':1,'kind':'task'},
            request=lambda method,path,payload=None:calls.append((method,path,payload)),
            update=lambda number,**fields:calls.append(('PATCH',number,fields)))
        self.worker.store=store
        self.worker._put(1,{'status':'done','remote_attempt':{'status':'done'}},state='closed')
        self.assertNotIn('body',calls[-1][2])
        self.assertEqual(calls[0][1],'/issues/1/comments')
        comment={'id':2,'body':LIFECYCLE+json.dumps({'status':'done'})+'\n-->'}
        store.request=lambda *args,**kwargs:[comment]
        self.assertEqual(issue_lifecycle(store,{'number':1,'body':'user prose'})['status'],'done')

    def test_stale_local_approval_cannot_override_newer_rejection(self):
        self.worker._prepare=lambda number:({'id':'TT-X','executor':'dev'},{'merge_commit':'a'*40},'stable')
        self.worker._review=lambda *args:dict(task_id='TT-X',commit='a'*40,verdict='approve',summary='ok',findings=[])
        self.worker.consume(1)
        self.store.meta['remote_attempt']={'status':'needs_input','run_id':'99','run_attempt':'1'}
        self.store.issue['state']='open'
        with self.assertRaisesRegex(ValueError,'recovery'): self.worker.consume(1)
        self.assertEqual(self.store.issue['state'],'open')

    def test_dispatch_and_reconcile_resume_half_published_review(self):
        self.store.meta['remote_attempt']={'status':'done','run_id':'41','run_attempt':'1'}
        self.store.issue['state']='open'
        self.assertTrue(self.worker.dispatch(1)['dispatched'])
        self.assertTrue(self.worker.reconcile()[0]['dispatched'])

    def test_invalid_review_cannot_close(self):
        self.worker._prepare = lambda number: ({'id':'TT-X','executor':'dev'}, {'merge_commit':'a'*40}, 'stable')
        self.worker._review = lambda card,bundle: {'verdict':'approve'}
        with self.assertRaises(ValueError): self.worker.consume(1)
        self.assertEqual(self.store.issue['state'], 'open')

if __name__ == '__main__': unittest.main()
