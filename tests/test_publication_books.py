import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from task_tower.project_connections import ProjectConnection
from task_tower.project_worker import LIFECYCLE, issue_lifecycle, verified_done


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


class PublicationBookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.connection = SimpleNamespace(repository='a/b',trusted_publishers=['publisher'])
        self.bundle = dict(repository='a/b',merge_commit='a'*40,task_ids=['TT-X'],run_id='12',attempt='1',platforms=dict(windows='passed',macos='passed',linux='passed'))
        evidence={s:dict(sha256='b'*64,hash_scheme='sha256',reviewer='reviewer',evidence='../evidence/review.json') for s in ('spec','development','test','postmerge')}
        self.receipt = dict(version=1,kind='local-postmerge',repository='a/b',issue=1,issue_id=123,task_id='TT-X',commit='a'*40,bundle=self.bundle,review=dict(task_id='TT-X',commit='a'*40,verdict='approve',summary='Approved',findings=[]),required_platforms=['windows','macos','linux'],policy=dict(executor='dev',reviewer='reviewer'),input_snapshot='c'*64,evidence=evidence,evidence_digest=digest(evidence))
        self.issue=dict(number=1,id=123,state='closed')
        self.comments=[]
        self.store=SimpleNamespace(metadata=lambda issue:dict(version=1,kind='task',legacy_id='TT-X'),request=self.request)
        self.source=SimpleNamespace(poll=lambda:[copy.deepcopy(self.bundle)])
        self.set_receipt()
    def request(self,method,path,payload=None):
        if '/comments?' in path: return self.comments
        if '/compare/' in path: return {'status':'ahead'}
        self.fail('Unexpected request '+path)
    def set_receipt(self,author='publisher'):
        attempt=dict(kind='local-postmerge',status='done',commit=self.receipt['commit'],publication_id=digest(self.receipt),receipt=copy.deepcopy(self.receipt))
        self.comments=[dict(id=1,user=dict(login=author),body=LIFECYCLE+json.dumps(dict(status='done',remote_attempt=attempt))+'\n-->')]
    def test_books_aggregate_accepts_only_proven_local_done(self):
        from task_tower.books import aggregate
        from task_tower.github_tasks import START, END
        from unittest.mock import patch
        self.connection.id='project'
        self.issue.update(body=START+json.dumps(dict(version=1,kind='task',legacy_id='TT-X'))+END,title='Task')
        self.store.list_issues=lambda:[self.issue]
        self.store.headers={}
        with patch('task_tower.github_source.GitHubSource',return_value=self.source):
            report=aggregate([self.connection],store_factory=lambda connection:self.store)
        self.assertEqual(report['entries'][0]['status'],'done')
        self.assertEqual(report['errors'],[])

    def test_trusted_receipt_projects_done(self):
        self.assertTrue(verified_done(self.connection,self.store,self.source,self.issue))
    def test_actual_comment_author_is_derived_and_not_body_supplied(self):
        self.assertEqual(issue_lifecycle(self.store,self.issue).get('_lifecycle_author'),'publisher')
    def test_connection_default_denies_and_validates_accounts(self):
        base=dict(id='p',repository='a/b',checkout=Path(self.temp.name).resolve(),runner_label='runner')
        self.assertEqual(ProjectConnection(**base).trusted_publishers,[])
        for invalid in ('publisher',['bad/name'],['-bad'],['a--b'],['a','A'],[1]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ProjectConnection(**base,trusted_publishers=invalid)
    def test_untrusted_or_no_config_cannot_forge_done(self):
        self.set_receipt('attacker')
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
        self.set_receipt()
        self.connection.trusted_publishers=[]
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
    def test_altered_proofs_fail_even_with_recomputed_receipt_identity(self):
        original=copy.deepcopy(self.receipt)
        for field,value in [('repository','other/repo'),('issue',2),('issue_id',999),('task_id','TT-OTHER'),('input_snapshot','bad'),('evidence_digest','d'*64),('required_platforms',[]),('policy',dict(executor='reviewer',reviewer='reviewer'))]:
            with self.subTest(field=field):
                self.receipt=copy.deepcopy(original); self.receipt[field]=value; self.set_receipt()
                self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
    def test_stale_ci_and_newer_rejection_fail(self):
        self.source.poll=lambda:[]
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
        self.source.poll=lambda:[self.bundle]
        self.comments.append(dict(id=2,user=dict(login='publisher'),body=LIFECYCLE+json.dumps(dict(status='needs_input',remote_attempt=dict(status='needs_input')))+'\n-->'))
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
    def test_newer_ci_attempt_and_nonmain_commit_invalidate_approval(self):
        newer=copy.deepcopy(self.bundle); newer['attempt']='2'; newer['platforms']['linux']='failed'
        self.source.poll=lambda:[self.bundle,newer]
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
        self.source.poll=lambda:[self.bundle]
        self.store.request=lambda method,path,payload=None: self.comments if '/comments?' in path else {'status':'diverged'}
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
    def test_platform_failure_and_modified_review_or_stage_fail(self):
        original=copy.deepcopy(self.receipt)
        mutations=[lambda r:r['bundle']['platforms'].update(linux='failed'),
                   lambda r:r['review'].update(verdict='reject'),
                   lambda r:r['evidence']['spec'].update(reviewer='dev'),
                   lambda r:r['evidence']['spec'].update(evidence='C:/private/review.json'),
                   lambda r:r['evidence']['spec'].pop('evidence')]
        for mutate in mutations:
            self.receipt=copy.deepcopy(original); mutate(self.receipt)
            self.receipt['evidence_digest']=digest(self.receipt['evidence']); self.set_receipt()
            self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))
    def test_malformed_newer_lifecycle_cannot_expose_older_approval(self):
        self.comments.append(dict(id=2,user=dict(login='publisher'),body=LIFECYCLE+'truncated'))
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))

    def test_reposting_old_approval_cannot_supersede_rejection(self):
        old=copy.deepcopy(self.comments[0])
        self.comments.append(dict(id=2,user=dict(login='publisher'),body=LIFECYCLE+json.dumps(dict(status='needs_input',remote_attempt=dict(status='needs_input',run_id='99',publication_id=digest(self.receipt))))+'\n-->'))
        old['id']=3; self.comments.append(old)
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))

    def test_older_workflow_rejection_requires_explicit_reconciliation(self):
        older=copy.deepcopy(self.bundle); older['run_id']='11'
        self.source.poll=lambda:[older,self.bundle]
        prior=dict(status='needs_input',remote_attempt=dict(status='needs_input',run_id='999',ci_run='11'))
        self.comments.insert(0,dict(id=0,user=dict(login='publisher'),body=LIFECYCLE+json.dumps(prior)+'\n-->'))
        self.comments[0]['id']=1; self.comments[1]['id']=2
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))

    def test_issue_body_local_receipt_is_not_attestation(self):
        attempt=json.loads(self.comments[0]['body'][len(LIFECYCLE):-4])['remote_attempt']
        self.comments=[]
        self.store.metadata=lambda issue:dict(kind='task',legacy_id='TT-X',remote_attempt=attempt,_lifecycle_author='publisher')
        self.assertFalse(verified_done(self.connection,self.store,self.source,self.issue))

if __name__=='__main__': unittest.main()
