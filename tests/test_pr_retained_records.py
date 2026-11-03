"""Genuine prepared material and admission are required for retained readers."""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import test_pr_preparation_context as preparation_fixture
from task_tower.pr_journal import BINDING, PRJournal
from task_tower.pr_policy import canonical
from task_tower.pr_source import prepare_review
from task_tower.pr_review import PRReviewRunner, validate_pr_review


class PreparedRecordTests(unittest.TestCase):
    context=preparation_fixture.PreparationContextTests.context
    source=preparation_fixture.PreparationContextTests.source
    current=preparation_fixture.PreparationContextTests.current
    identity=preparation_fixture.PreparationContextTests.identity
    fetch_transport=preparation_fixture.PreparationContextTests.fetch_transport

    @classmethod
    def setUpClass(cls):
        current=preparation_fixture.current_fixture
        original_loader=current.installed_load
        def install(f):
            if getattr(cls,'with_review',False):
                child=f.root/'pr-reader-child.py'
                child.write_text('''import argparse,json,pathlib,os
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args()
r=json.loads(pathlib.Path(a.request).read_text(encoding='utf-8'))
assert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)
v={k:r[k] for k in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')}
v.update(verdict='approve',summary='Controlled real process fixture.',findings=[],whole_diff_reviewed=True)
pathlib.Path(a.result).write_text(json.dumps(v),encoding='utf-8')
''',encoding='utf-8')
                profile=copy.deepcopy(f.profile); profile['argv']=[str(Path(sys.executable).resolve()),str(child)]
                profile['max_attempts']=1
                profile['runs_dir']=str(f.root/'pr-reader-runs')
                f.executor['profiles']['pr-reader']=profile
            return original_loader(f)
        with patch.object(current,'installed_load',install):
            preparation_fixture.PreparationContextTests.setUpClass.__func__(cls)
        try:
            instance=cls(); cls.host=instance
            if getattr(cls,'with_review',False):
                cls.raw['projects'][0]['tasks'][0]['reviewer_profile']='pr-reader'
                cls.policy.write_text(json.dumps(cls.raw),encoding='utf-8')
            with PRJournal(cls.journal)._db(True): pass
            cls.ctx=instance.context()
            fresh=instance.current(cls.ctx,instance.source(cls.ctx))
            cls.namespace=Path(str(cls.journal)+'.private')
            cls.directory=cls.namespace/'preparations'/str(uuid.uuid4())
            connection=cls.ctx._fresh_inputs()['connections'][0]
            with patch('task_tower.pr_source._fetch',side_effect=instance.fetch_transport):
                cls.prepared=prepare_review(connection,fresh['task'],fresh['snapshot'],fresh['authority'],
                    cls.directory,private_context=cls.ctx)
            cls.request=cls.prepared['request']; cls.input_sha=cls.request['input_sha256']
            cls.pr=PRJournal(cls.journal)
            cls.pr.admit({k:cls.request[k] for k in BINDING})
            actual=cls.directory/'request.json'; info=actual.stat()
            cls.record=dict(request=cls.request,private_input_provenance=cls.ctx.private_input_provenance,
                private_artifact_identity=dict(version=1,repository=cls.request['repository'],
                    pr_number=cls.request['pr_number'],input_sha256=cls.input_sha,
                    request_relative_path=actual.relative_to(cls.namespace).as_posix(),
                    request_sha256=hashlib.sha256(canonical(cls.request).encode()).hexdigest(),
                    request_raw_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),device=info.st_dev,inode=info.st_ino))
            cls.index=cls.namespace/'prepared'/(cls.input_sha+'.json'); cls.index.parent.mkdir()
            cls.original=canonical(cls.record).encode(); cls.index.write_bytes(cls.original)
            if getattr(cls,'with_review',False):
                cls.owner_id=str(uuid.uuid4()); owner=cls.pr.owner(cls.owner_id); owner.__enter__()
                instance.addCleanup(owner.__exit__,None,None,None)
                for before,after in (('discovered','validating'),('validating','reviewing')):
                    cls.pr.transition(cls.request['repository'],cls.request['pr_number'],cls.owner_id,
                        dict(state=before,input_sha256=cls.input_sha),dict(state=after))
                cls.effect=cls.pr.begin_effect(cls.request['repository'],cls.request['pr_number'],cls.owner_id,
                    'pr_review',dict(reviewer_instance_id=cls.request['reviewer_instance_id'],request_sha256=cls.input_sha))
                cls.envelope=PRReviewRunner(fresh['task']['_review_profile']).review(Path(cls.prepared['checkout']),
                    cls.request,cls.namespace/'roles'/str(uuid.uuid4()))
                cls.receipt=validate_pr_review(cls.envelope,cls.request,())
                if cls.receipt.get('verdict')!='approve': raise AssertionError(cls.receipt)
                cls.review_record=dict(request=cls.request,envelope=cls.envelope,receipt=cls.receipt,
                    review_effect_id=cls.effect['effect_id'],private_input_provenance=cls.ctx.private_input_provenance)
                cls.review_path=cls.namespace/'review-records'/(cls.effect['effect_id']+'.json')
                cls.review_path.parent.mkdir(); cls.review_original=canonical(cls.review_record).encode()
                cls.review_path.write_bytes(cls.review_original)
                process={k:cls.envelope['process'][k] for k in ('pid','exit_code','started','cleanup_confirmed')}
                cls.pr.observe(cls.effect['effect_id'],cls.owner_id,dict(status=getattr(cls,'observation_status','confirmed'),
                    reviewer_instance_id=cls.request['reviewer_instance_id'],result_sha256=cls.receipt['result_sha256'],
                    receipt_sha256=cls.receipt['receipt_sha256'],process=process))
        except BaseException:
            if hasattr(cls,'host'): cls.host.doCleanups()
            preparation_fixture.PreparationContextTests.tearDownClass.__func__(cls)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.host.doCleanups()
        preparation_fixture.PreparationContextTests.tearDownClass.__func__(cls)

    def read(self):
        self.assertTrue(callable(getattr(self.ctx,'prepared_record',None)),'Missing genuine prepared-record reader')
        return self.ctx.prepared_record(self.input_sha)

    def test_actual_preparation_and_admission_resolve_without_journal_writes(self):
        before=self.journal.read_bytes(); self.assertEqual(self.read(),self.record)
        self.assertEqual(before,self.journal.read_bytes())

    def test_consistent_record_without_actual_admission_is_refused(self):
        # A different input cannot be located by copying a self-consistent file.
        fake=copy.deepcopy(self.record); digest='f'*64
        path=self.index.with_name(digest+'.json'); path.write_text(canonical(fake),encoding='utf-8')
        self.addCleanup(path.unlink)
        self.assertTrue(callable(getattr(self.ctx,'prepared_record',None)))
        with self.assertRaises(ValueError): self.ctx.prepared_record(digest)

    def test_record_manifest_and_location_forgery_are_refused(self):
        self.addCleanup(self.index.write_bytes,self.original)
        for change in ('manifest','path','identity','extra'):
            value=copy.deepcopy(self.record)
            if change=='manifest': value['private_input_provenance']['journal_path']='elsewhere'
            elif change=='path': value['private_artifact_identity']['request_relative_path']='../outside.json'
            elif change=='identity': value['private_artifact_identity']['inode']+=1
            else: value['extra']=True
            self.index.write_text(canonical(value),encoding='utf-8')
            with self.subTest(change=change),self.assertRaises(ValueError): self.read()

    def test_same_byte_request_replacement_is_refused(self):
        path=self.directory/'request.json'; retained=path.with_name('retained-request.json')
        path.rename(retained); path.write_bytes(retained.read_bytes())
        def restore(): path.unlink(); retained.rename(path)
        self.addCleanup(restore)
        with self.assertRaises(ValueError): self.read()

    def test_duplicate_json_keys_are_refused(self):
        self.addCleanup(self.index.write_bytes,self.original)
        self.index.write_bytes(b'{"request":{},"request":{}}')
        with self.assertRaises(ValueError): self.read()

    def test_actual_request_hardlink_is_refused(self):
        alias=self.root/'request-alias.json'; os.link(self.directory/'request.json',alias)
        self.addCleanup(alias.unlink)
        with self.assertRaises(ValueError): self.read()

    def test_current_private_raw_byte_revocation_refuses_record(self):
        raw=self.policy.read_bytes(); self.addCleanup(self.policy.write_bytes,raw)
        self.policy.write_bytes(raw+b' ')
        with self.assertRaises(ValueError): self.read()


class VerifiedRecordTests(unittest.TestCase):
    with_review=True
    setUpClass=classmethod(PreparedRecordTests.setUpClass.__func__)
    tearDownClass=classmethod(PreparedRecordTests.tearDownClass.__func__)
    context=PreparedRecordTests.context
    source=PreparedRecordTests.source
    current=PreparedRecordTests.current
    identity=PreparedRecordTests.identity
    fetch_transport=PreparedRecordTests.fetch_transport

    def read(self):
        self.assertTrue(callable(getattr(self.ctx,'review_record',None)),'Missing genuine review-record reader')
        return self.ctx.review_record(self.input_sha)

    def test_real_role_and_confirmed_observation_resolve_before_later_phase_updates(self):
        row=self.pr.get(self.request['repository'],self.request['pr_number'])
        self.assertIsNone(row['pr_receipt_sha256'])
        before=self.journal.read_bytes()
        self.assertEqual(self.read(),self.review_record)
        self.assertEqual(before,self.journal.read_bytes())
        self.pr.transition(self.request['repository'],self.request['pr_number'],self.owner_id,
            dict(state='reviewing',input_sha256=self.input_sha),dict(state='reviewed',
                pr_receipt_sha256=self.receipt['receipt_sha256'],reviewer_instance_id=self.request['reviewer_instance_id']))
        self.assertEqual(self.read(),self.review_record)

    def test_json_process_receipt_effect_and_instance_forgery_are_refused(self):
        self.addCleanup(self.review_path.write_bytes,self.review_original)
        for change in ('process','receipt','effect','instance','provenance','extra'):
            record=copy.deepcopy(self.review_record)
            if change=='process': record['envelope']['process']['pid']+=1
            elif change=='receipt': record['receipt']['summary']='replaced'
            elif change=='effect': record['review_effect_id']=str(uuid.uuid4())
            elif change=='instance': record['envelope']['reviewer_instance_id']=str(uuid.uuid4())
            elif change=='provenance': record['private_input_provenance']['journal_path']='elsewhere'
            else: record['extra']=True
            self.review_path.write_text(canonical(record),encoding='utf-8')
            with self.subTest(change=change),self.assertRaises(ValueError): self.read()

    def test_missing_confirmed_record_never_launches_again(self):
        retained=self.review_path.with_suffix('.retained'); self.review_path.rename(retained)
        self.addCleanup(retained.rename,self.review_path)
        with (patch.object(PRReviewRunner,'review',side_effect=AssertionError('Reader relaunched a role')),
                self.assertRaises(ValueError)): self.read()


class UnknownReviewTests(unittest.TestCase):
    with_review=True
    observation_status='unknown'
    setUpClass=classmethod(PreparedRecordTests.setUpClass.__func__)
    tearDownClass=classmethod(PreparedRecordTests.tearDownClass.__func__)
    context=PreparedRecordTests.context
    source=PreparedRecordTests.source
    current=PreparedRecordTests.current
    identity=PreparedRecordTests.identity
    fetch_transport=PreparedRecordTests.fetch_transport
    read=VerifiedRecordTests.read

    def test_real_role_and_confirmed_observation_resolve_before_later_phase_updates(self):
        with self.assertRaises(ValueError): self.read()
