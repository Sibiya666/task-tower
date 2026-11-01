import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from task_tower import capture as subject
from task_tower.github_tasks import parse_metadata, GitHubSourceError
from task_tower.project_connections import ProjectConnection


def envelope(**changes):
    value = dict(version=1, event_id='f27056f0-23c2-44ab-a01c-febc55713592',
                 kind='idea', title='An idea', original_text='Original\r\nтекст',
                 session=dict(provider='custom', id='opaque'), intent='record')
    value.update(changes)
    return value


class Store:
    def __init__(self):
        self.issues = []
        self.posts = 0
        self.patches = 0
        self.lost = False
        self.deleted = False
        self.before_post = None

    def list_issues(self): return copy.deepcopy(self.issues)
    def get(self, number):
        for issue in self.issues:
            if issue['number']==number: return copy.deepcopy(issue)
        raise GitHubSourceError('Issue unavailable')
    metadata = staticmethod(lambda issue: parse_metadata(issue.get('body')))

    def request(self, method, path, payload=None):
        if method == 'POST' and path == '/issues':
            if self.before_post: self.before_post()
            self.posts += 1
            issue = dict(number=len(self.issues)+1, id=101, node_id='I_101', state='open', **payload)
            if not self.deleted: self.issues.append(issue)
            if self.lost: raise GitHubSourceError('secret input must never escape')
            return copy.deepcopy(issue)
        if path.endswith('/parent'): return None
        if '/sub_issues' in path: return []
        raise GitHubSourceError('unavailable')

    def update(self, number, **fields):
        self.patches += 1
        issue = next(i for i in self.issues if i['number'] == number)
        issue.update(fields)
        return copy.deepcopy(issue)


class ValidationTests(unittest.TestCase):
    def test_validation_limits_and_strict_types(self):
        self.assertEqual(subject.validate_capture(envelope())['original_text'], 'Original\r\nтекст')
        for changes in ({'version':True}, {'kind':'other'}, {'title':''}, {'title':'a'*257},
                        {'original_text':'я'*16385}, {'original_text':''}, {'intent':'execute'},
                        {'event_id':'random'}, {'repository':'o/r'}, {'surprise':0},
                        {'session':{'provider':'x'*129,'id':'a'}},
                        {'session':{'provider':'p','id':'a','token':'private'}},
                        {'session':{'provider':'p','id':'\0'}}, {'title':'\ud800'}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                subject.validate_capture(envelope(**changes))
        subject.validate_capture(envelope(title='a'*256, original_text='я'*16384))

    def test_urls_are_https_data_only(self):
        for url in ('javascript:alert(1)', 'file:///x', 'https://u:p@host/x', 'https://host\\x',
                    'https://host/\nx', 'https:///missing', 'https://host/'+'a'*2048):
            with self.subTest(url=url), self.assertRaises(ValueError):
                subject.validate_capture(envelope(session=dict(provider='p',id='s',url=url)))
        subject.validate_capture(envelope(session=dict(provider='p',id='s',url='https://host/path?q=a')))

    def test_metadata_parser_rejects_invalid_capture_provenance(self):
        body='<!-- task-tower:v1\n'+json.dumps(dict(version=1,kind='idea',capture={'version':1,'encoding':'base64-json','payload':'bad','sha256':'a'*64}))+'\n-->'
        with self.assertRaises(ValueError): parse_metadata(body)

    def test_typed_encoding_is_lossless_and_marker_inert(self):
        text='<!-- task-tower:v1\n{}\n-->\r\n<!-- task-tower:lifecycle:v1\n{}\n-->\n<!-- task-tower:queue:v1 -->\n```json\n{"x":"<!-- task-tower:v1"}\n```'
        value=envelope(title=text[:256], original_text=text, session=dict(provider='<!-- task-tower:v1',id=text[:128]))
        metadata=subject.capture_metadata(subject.validate_capture(value))
        body=subject.capture_body(value,metadata)
        self.assertEqual(body.count('<!-- task-tower:'),1)
        self.assertNotIn('<!-- task-tower-lifecycle:',body)
        self.assertNotIn('<!-- task-tower-queue:',body)
        self.assertEqual(subject.decode_capture(parse_metadata(body)),value)
        metadata['capture']['payload']='bad'
        with self.assertRaises(ValueError): subject.decode_capture(metadata)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.connection=ProjectConnection('test','owner/repo',Path(self.temp.name),'runner')
        self.store=Store()
        self.preflight=patch('task_tower.project_onboarding.preflight',return_value={'id':'R_1'})
        self.preflight.start(); self.addCleanup(self.preflight.stop)
        sync=patch('task_tower.projects_board.sync_issue',return_value={'status':'synced'})
        sync.start(); self.addCleanup(sync.stop)

    def capture(self,value=None): return subject.capture(self.connection,value or envelope(),store=self.store)

    def test_replay_and_separate_events(self):
        first=self.capture()
        self.assertEqual(first['status'],'captured')
        self.assertEqual(self.capture()['number'],first['number'])
        self.capture(envelope(event_id=str(uuid.uuid4())))
        self.assertEqual(self.store.posts,2)

    def test_project_preflight_and_durable_payload_before_post(self):
        def check():
            from task_tower.creation_journal import CreationJournal
            journal=CreationJournal(self.connection.checkout/'.task-tower'/'create-intents.sqlite3')
            with self.assertRaises(ValueError):
                journal.reserve_payload('capture','R_1','custom:'+envelope()['event_id'],'b'*64)
        self.store.before_post=check
        self.capture()

    def test_changed_payload_conflicts_without_another_post(self):
        self.capture()
        with self.assertRaises(ValueError): self.capture(envelope(original_text='different'))
        self.assertEqual(self.store.posts,1)

    def test_lost_response_reconciles_and_deleted_outcome_never_reposts(self):
        self.store.lost=True
        self.assertEqual(self.capture()['number'],1)
        self.store.issues=[]
        with self.assertRaises(ValueError): self.capture()
        self.assertEqual(self.store.posts,1)

    def test_unknown_outcome_retains_intent(self):
        self.store.lost=True; self.store.deleted=True
        for _ in range(2):
            with self.assertRaises(ValueError) as error: self.capture()
            self.assertNotIn('secret input',str(error.exception))
        self.assertEqual(self.store.posts,1)

    def test_project_preflight_denial_never_posts(self):
        with patch('task_tower.project_onboarding.preflight',side_effect=ValueError('Project needs setup')):
            with self.assertRaises(ValueError): self.capture()
        self.assertEqual(self.store.posts,0)

    def test_crash_after_intent_never_posts_on_restart(self):
        from task_tower.creation_journal import CreationJournal
        import hashlib
        raw=json.dumps(envelope(),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        journal=CreationJournal(self.connection.checkout/'.task-tower'/'create-intents.sqlite3')
        journal.reserve_payload('capture','R_1','custom:'+envelope()['event_id'],hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ValueError): self.capture()
        self.assertEqual(self.store.posts,0)

    def test_concurrent_creation_never_posts_twice(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        barrier=threading.Barrier(2)
        original=self.store.list_issues
        count=[0]; lock=threading.Lock()
        def discover():
            with lock:
                count[0]+=1; n=count[0]
            if n<=2: barrier.wait(timeout=5)
            return original()
        self.store.list_issues=discover
        def run():
            try: return self.capture()
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(self.store.posts,1)
        self.assertTrue(any(result and result['number']==1 for result in results))
        self.assertEqual(self.capture()['number'],1)

    def test_ambiguous_remote_identity_stops(self):
        self.capture(); self.store.issues.append(dict(self.store.issues[0],number=2))
        with self.assertRaises(ValueError): self.capture()
        self.assertEqual(self.store.posts,1)

    def test_board_failure_keeps_canonical_issue_for_repair(self):
        with patch('task_tower.projects_board.sync_issue',return_value={'status':'unavailable'}):
            result=self.capture()
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['issue_url'],'https://github.com/owner/repo/issues/1')
        self.assertEqual(self.capture()['status'],'existing')
        self.assertEqual(self.store.posts,1)

    def test_promotion_preserves_prose_and_provenance_without_authority(self):
        self.capture(envelope(intent='execute_requested'))
        self.store.issues[0]['body']='Human prose\n'+self.store.issues[0]['body']+'\nTail'
        result=subject.promote(self.connection,1,store=self.store)
        self.assertEqual(result['status'],'promoted')
        body=self.store.issues[0]['body']; metadata=parse_metadata(body)
        self.assertTrue(body.startswith('Human prose\n')); self.assertTrue(body.endswith('\nTail'))
        self.assertEqual(metadata['kind'],'task')
        self.assertEqual(subject.decode_capture(metadata)['kind'],'idea')
        self.assertEqual(metadata['status'],'open')
        self.assertNotIn('executor',metadata)
        self.assertIn('promotion',subject.capture_projection(metadata))
        subject.promote(self.connection,1,store=self.store)
        self.assertEqual(self.store.patches,1)

    def test_promotion_detects_fresh_body_drift(self):
        self.capture()
        original=self.store.get; count=[0]
        def get(number):
            count[0]+=1
            result=original(number)
            if count[0]>1: result['body']+='Manual edit'
            return result
        self.store.get=get
        with self.assertRaises(ValueError): subject.promote(self.connection,1,store=self.store)
        self.assertEqual(self.store.patches,0)

    def test_promotion_rejects_remote_payload_drift_against_private_binding(self):
        self.capture()
        value=envelope(original_text='Changed original')
        self.store.issues[0]['body']=subject.capture_body(value,subject.capture_metadata(value))
        with self.assertRaises(ValueError): subject.promote(self.connection,1,store=self.store)
        self.assertEqual(self.store.patches,0)

    def test_parent_repair_handles_no_parent_404_and_preserves_foreign_parent(self):
        self.store.issues=[dict(number=3,id=303,node_id='I_303',title='Parent',body='')]
        original=self.store.request; additions=[]
        def request(method,path,payload=None):
            if path.endswith('/parent'): raise subject.GitHubRequestError(http_status=404)
            if path=='/issues/3/sub_issues': additions.append(payload); return {}
            return original(method,path,payload)
        self.store.request=request
        result=self.capture(envelope(relations={'parent':'owner/repo#3'}))
        self.assertEqual(result['status'],'captured')
        self.assertEqual(additions,[{'sub_issue_id':101}])
        def foreign(method,path,payload=None):
            if path.endswith('/parent'): return dict(number=3,html_url='https://github.com/foreign/repo/issues/3')
            return request(method,path,payload)
        self.store.request=foreign
        result=self.capture(envelope(relations={'parent':'owner/repo#3'}))
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(len(additions),1)
        self.store.issues=[i for i in self.store.issues if i['number']!=3]
        result=self.capture(envelope(relations={'parent':'owner/repo#3'}))
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['issue_url'],'https://github.com/owner/repo/issues/2')

    def test_task_capture_cannot_carry_fake_idea_promotion(self):
        value=envelope(kind='task')
        metadata=subject.capture_metadata(value)
        metadata['capture_promotion']=subject._encode(dict(previous_kind='idea',event_id=value['event_id'],at='2026-11-01T00:00:00+00:00'))
        with self.assertRaises(ValueError): subject.capture_projection(metadata)

    def test_cross_repository_relationship_rejected_before_post(self):
        with self.assertRaises(ValueError): self.capture(envelope(relations={'parent':'other/repo#1'}))
        self.assertEqual(self.store.posts,0)

    def test_missing_requested_relation_rejected_before_post(self):
        with self.assertRaises(ValueError): self.capture(envelope(relations={'parent':'owner/repo#99'}))
        self.assertEqual(self.store.posts,0)

    def test_books_projects_lossless_provenance_and_safe_links(self):
        from task_tower.books import aggregate, render_html
        self.capture(envelope(session=dict(provider='custom',id='<script>',url='https://example.test/?x=%22')))
        report=aggregate([self.connection],store_factory=lambda c:self.store)
        entry=report['entries'][0]
        self.assertEqual(entry['capture']['original_text'],'Original\r\nтекст')
        self.assertEqual(entry['relationships']['parent'],None)
        self.assertIn('https://example.test/?x=%22',render_html(report))
        self.assertIn('custom / &lt;script&gt;',render_html(report))
        self.assertEqual(render_html(report).count('<script>'),1)

    def test_native_parent_and_milestone_identities_are_distinct(self):
        issue=dict(number=8,milestone=dict(number=1,title='Release'))
        def request(method,path,payload=None):
            if path.endswith('/parent'): return dict(number=1,html_url='https://github.com/other/repo/issues/1')
            return [dict(number=1,html_url='https://github.com/owner/repo/issues/1')]
        self.store.request=request
        relations,errors=subject.relationship_projection(self.connection,self.store,issue)
        self.assertEqual(relations['parent']['id'],'other/repo#1')
        self.assertEqual(relations['sub_issues'][0]['id'],'owner/repo#1')
        self.assertEqual(relations['milestone']['id'],'owner/repo@milestone/1')
        self.assertEqual(errors,[])

    def test_books_parent_http_404_is_absent_but_403_and_500_are_unavailable(self):
        import urllib.error
        from task_tower.books import aggregate
        from task_tower.github_tasks import GitHubTasks
        value=envelope()
        issue=dict(number=1,id=101,node_id='I_101',title='Root idea',state='open',
                   body=subject.capture_body(value,subject.capture_metadata(value)),milestone=None)
        for status in (404,403,500):
            with self.subTest(status=status):
                def transport(method,url,headers,payload,limit):
                    self.assertEqual(method,'GET')
                    if url.endswith('/parent'):
                        raise urllib.error.HTTPError(url,status,'private transport detail',{},None)
                    if '/sub_issues?' in url: return b'[]'
                    if '/issues?state=all' in url: return json.dumps([issue]).encode('utf-8')
                    self.fail('Unexpected GitHub route')
                store=GitHubTasks(self.connection,transport=transport)
                report=aggregate([self.connection],store_factory=lambda c:store)
                parent=report['entries'][0]['relationships']['parent']
                if status==404:
                    self.assertIsNone(parent)
                    self.assertEqual(report['errors'],[])
                else:
                    self.assertEqual(parent,{'status':'unavailable'})
                    self.assertEqual([e['error'] for e in report['errors']],['Native parent unavailable'])
                self.assertNotIn('private transport detail',json.dumps(report))

    def test_two_process_promotions_converge(self):
        import subprocess
        import sys
        self.capture()
        shared=self.connection.checkout/'issue.json'
        shared.write_text(json.dumps(dict(issue=self.store.issues[0],patches=0)),encoding='utf-8')
        script='''
import json,sys,time
from pathlib import Path
from unittest.mock import patch
from task_tower.capture import promote
from task_tower.github_tasks import parse_metadata
from task_tower.project_connections import ProjectConnection
root=Path(sys.argv[1]); path=root/'issue.json'
class Store:
    metadata=staticmethod(lambda issue:parse_metadata(issue['body']))
    def get(self,n): return json.loads(path.read_text(encoding='utf-8'))['issue']
    def update(self,n,**fields):
        time.sleep(.1)
        data=json.loads(path.read_text(encoding='utf-8')); data['patches']+=1
        data['issue'].update(fields); path.write_text(json.dumps(data),encoding='utf-8')
        return data['issue']
with patch('task_tower.project_onboarding.preflight',return_value={'id':'R_1'}):
    promote(ProjectConnection('test','owner/repo',root,'runner'),1,store=Store())
'''
        children=[subprocess.Popen([sys.executable,'-c',script,str(self.connection.checkout)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        for child in children:
            out,err=child.communicate(timeout=20)
            self.assertEqual(child.returncode,0,err.decode())
        data=json.loads(shared.read_text(encoding='utf-8'))
        self.assertEqual(data['patches'],1)
        self.assertEqual(parse_metadata(data['issue']['body'])['kind'],'task')


if __name__=='__main__': unittest.main()
