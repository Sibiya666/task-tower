import copy
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from task_tower.books import aggregate
from task_tower.github_tasks import replace_metadata


def connection(repo='a/b'):
    return SimpleNamespace(id=repo, repository=repo)


class Store:
    headers = {}
    def __init__(self, issue=None):
        self.issue = issue or dict(number=1, title='Ordinary', body='<script>text</script>', state='closed')
    def list_issues(self): return [self.issue]
    def request(self, method, path):
        if '/parent' in path: return None
        if '/sub_issues?' in path: return []
        if '/comments?' in path: return []
        raise ValueError('private transport failure')
    def library(self): return [dict(title='docs/a.md', path='docs/a.md', commit='a'*40, repository='a/b', source='https://github.com/a/b/blob/'+'a'*40+'/docs/a.md')]
    def library_index(self, commit): return None


class ProjectionTests(unittest.TestCase):
    def test_ordinary_native_links_and_closed_is_not_done(self):
        from task_tower.book_projection import project_issue
        row, errors = project_issue(connection(), Store(), Store().issue, None)
        self.assertEqual(row['relationships'], dict(parent=None, sub_issues=[], milestone=None))
        self.assertEqual(row['description'], '<script>text</script>')
        self.assertEqual(row['repository'], 'a/b')
        self.assertNotEqual(row['status'], 'done')
        self.assertEqual(errors, [])

    def test_public_fields_and_limits(self):
        from task_tower.book_projection import project_issue
        meta = dict(version=1, kind='task', phase='p'*300, blockers=['b'*300]*101,
                    results=['https://github.com/a/b/issues/2'], blocked_by=['a/b#2'],
                    secret='TOKEN', config={'checkout':'PRIVATE'},
                    _lifecycle_history=[dict(status='done', remote_attempt=dict(status='done', run_id='42', receipt={'secret':'TOKEN'}, checkout='PRIVATE'))])
        issue = dict(number=1, title='Task', body=replace_metadata('x'*34000, meta))
        row, errors = project_issue(connection(), Store(), issue, meta)
        self.assertLessEqual(len(row['description'].encode()), 32768)
        self.assertEqual(len(row['phase']), 256)
        self.assertEqual(len(row['blockers']), 100)
        self.assertTrue(errors)
        self.assertNotIn('TOKEN', str(row)); self.assertNotIn('PRIVATE', str(row))
        self.assertNotIn('task-tower:v1', row['description'])

    def test_progress_before_blocking_proof_and_snapshot_isolation(self):
        body = replace_metadata('Task', dict(version=1, kind='task', status='done'))
        stores = {'a/b':Store(dict(number=1, title='Task', body=body, state='closed')), 'c/d':Store()}
        snapshots=[]; entered=threading.Event(); release=threading.Event(); result=[]
        def proof(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('test proof barrier timed out')
            return True
        def lifecycle(store, issue): return dict(version=1,kind='task',status='done')
        with patch('task_tower.project_worker.issue_lifecycle', side_effect=lifecycle), patch('task_tower.project_worker.verified_done', side_effect=proof):
            worker=threading.Thread(target=lambda:result.append(aggregate([connection(),connection('c/d')], lambda c:stores[c.repository], True, on_update=snapshots.append)))
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                latest=copy.deepcopy(snapshots[-1])
                self.assertEqual({r['id'] for r in latest['entries'] if r['book']!='library'}, {'a/b#1','c/d#1'})
                self.assertTrue(any(r['book']=='library' for r in latest['entries']))
                self.assertEqual(latest['entries'][0]['verification'], 'pending')
                self.assertNotEqual(latest['entries'][0]['status'], 'done')
                snapshots[0]['entries'][0]['title']='MUTATED'
            finally:
                release.set(); worker.join(6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result[0]['entries'][0]['status'], 'done')
        self.assertEqual(result[0]['entries'][0]['verification'], 'verified')
        self.assertEqual(result[0]['entries'][0]['title'], 'Task')
        self.assertEqual(latest['entries'][0]['verification'], 'pending')

    def test_lifecycle_failure_retains_each_identity(self):
        body=replace_metadata('',dict(version=1,kind='task'))
        with patch('task_tower.project_worker.issue_lifecycle',side_effect=ValueError('PRIVATE')):
            report=aggregate([connection()],lambda c:Store(dict(number=1,title='Kept',body=body)))
        self.assertEqual(report['entries'][0]['id'],'a/b#1')
        self.assertTrue(report['errors']); self.assertNotIn('PRIVATE',str(report))

    def test_library_survives_issue_listing_failure(self):
        store=Store()
        store.list_issues=lambda: (_ for _ in ()).throw(ValueError('PRIVATE'))
        report=aggregate([connection()],lambda c:store,True)
        self.assertTrue(any(row['book']=='library' for row in report['entries']))
        self.assertTrue(report['errors']); self.assertNotIn('PRIVATE',str(report))

    def test_false_and_error_proof_never_done_or_reused(self):
        body=replace_metadata('',dict(version=1,kind='task',status='done'))
        store=Store(dict(number=1,title='Task',body=body,state='closed'))
        for result in (False,ValueError('PRIVATE')):
            kwargs={'side_effect':result} if isinstance(result,Exception) else {'return_value':result}
            with patch('task_tower.project_worker.issue_lifecycle',return_value=dict(kind='task',status='done')), patch('task_tower.project_worker.verified_done',**kwargs):
                report=aggregate([connection()],lambda c:store)
            self.assertEqual(report['entries'][0]['verification'],'unverified')
            self.assertNotEqual(report['entries'][0]['status'],'done')
            self.assertNotIn('PRIVATE',str(report))

    def test_unknown_and_wrong_type_details_are_visible_without_raw_values(self):
        from task_tower.book_projection import project_issue
        meta=dict(kind='task',phase={'secret':'PRIVATE'},blockers='PRIVATE',results=[{'secret':'PRIVATE'}],mystery={'secret':'PRIVATE'})
        row,errors=project_issue(connection(),Store(),Store().issue,meta)
        self.assertTrue(any('Unknown' in e['error'] for e in errors))
        self.assertIsNone(row['phase']); self.assertNotIn('PRIVATE',str(row))

    def test_public_result_sources_and_review_evidence(self):
        from task_tower.book_projection import project_issue
        source='https://github.com/a/b/blob/'+'a'*40+'/docs/result.md'
        meta=dict(kind='task',results=[source,'javascript:alert(1)'],remote_attempt=dict(status='reviewed',review=dict(verdict='approve',commit='a'*40,summary='PRIVATE',findings=['PRIVATE'])))
        row,errors=project_issue(connection(),Store(),Store().issue,meta)
        self.assertEqual(row['results'],[source])
        self.assertEqual(row['remote_attempt']['review'],dict(verdict='approve',commit='a'*40))
        self.assertNotIn('PRIVATE',str(row)); self.assertTrue(errors)

