"""Actual stage/role fixtures for pure premerge consistency; no remote writes."""
import copy
import json
import unittest
import uuid
from unittest.mock import patch

import test_pr_retained_records as record_fixtures
from task_tower.pr_journal import BINDING
try:
    from task_tower.pr_effects import premerge_gate
except ImportError:
    premerge_gate=None


class PremergeGateTests(unittest.TestCase):
    with_review=True
    tearDownClass=classmethod(record_fixtures.PreparedRecordTests.tearDownClass.__func__)
    source=record_fixtures.PreparedRecordTests.source
    current=record_fixtures.PreparedRecordTests.current
    identity=record_fixtures.PreparedRecordTests.identity
    fetch_transport=record_fixtures.PreparedRecordTests.fetch_transport

    def context(self):
        # Explicit declarations in disposable fixture files, not live operator
        # attestation and not an authority callback passed to product code.
        policy=json.loads(self.policy.read_text(encoding='utf-8'))
        policy['projects'][0]['merge_enabled']=True
        policy['projects'][0]['exclusive_writer']['enabled']=True
        self.policy.write_text(json.dumps(policy),encoding='utf-8')
        return record_fixtures.PreparedRecordTests.context(self)

    @classmethod
    def setUpClass(cls):
        record_fixtures.PreparedRecordTests.setUpClass.__func__(cls)
        try:
            cls.fresh=cls.host.current(cls.ctx,cls.host.source(cls.ctx))
            if cls.fresh['authority_error'] is not None: raise AssertionError(cls.fresh['authority_error'])
        except BaseException:
            cls.tearDownClass(); raise

    def gate(self,*,task=None,receipt=None,current=None,authority=None,barrier=None):
        self.assertIsNotNone(premerge_gate,'Missing pure premerge consistency gate')
        return premerge_gate(self.fresh['task'] if task is None else task,
            self.receipt if receipt is None else receipt,
            self.fresh['snapshot'] if current is None else current,
            self.fresh['authority'] if authority is None else authority,barrier)

    def test_real_bound_receipt_and_current_source_yield_exact_binding(self):
        before=self.journal.read_bytes()
        self.assertEqual(self.gate(),{key:self.request[key] for key in BINDING})
        self.assertEqual(before,self.journal.read_bytes())

    def test_disabled_or_unattested_policy_cannot_pass(self):
        for change in ('disabled','writer','legacy'):
            task=copy.deepcopy(self.fresh['task'])
            if change=='disabled': task['merge_enabled']=False
            elif change=='writer': task['exclusive_writer']['enabled']=False
            else: task['source']='legacy';task['pipeline_run_id']=None
            with self.subTest(change=change),self.assertRaises(ValueError): self.gate(task=task)

    def test_current_head_base_policy_and_ready_gates_must_match(self):
        for change in ('head_sha','base_sha','policy_sha256','ready','ci','protection','pr_head','blocked'):
            current=copy.deepcopy(self.fresh['snapshot'])
            if change in ('head_sha','base_sha'): current[change]='0'*40
            elif change=='policy_sha256': current[change]='0'*64
            elif change=='ready': current['ready']=False
            elif change in ('ci','protection'): current[change]['ready']=False
            elif change=='pr_head': current['pr']['head']['sha']='0'*40
            else: current['pr']['mergeable_state']='blocked'
            with self.subTest(change=change),self.assertRaises(ValueError): self.gate(current=current)

    def test_tampered_receipt_and_nonpositive_decisions_cannot_pass(self):
        for change in ('receipt_sha256','process_sha256','reviewer_instance_id','verdict','whole_diff_reviewed'):
            receipt=copy.deepcopy(self.receipt)
            if change in ('receipt_sha256','process_sha256'): receipt[change]='0'*64
            elif change=='reviewer_instance_id': receipt[change]=str(uuid.uuid4())
            elif change=='verdict': receipt[change]='reject'
            else: receipt[change]=False
            with self.subTest(change=change),self.assertRaises(ValueError): self.gate(receipt=receipt)

    def test_foreign_authority_or_barrier_never_passes(self):
        authority=copy.deepcopy(self.fresh['authority']); authority['head_sha']='0'*40
        with self.assertRaises(ValueError): self.gate(authority=authority)
        barrier={key:self.request[key] for key in BINDING}
        barrier.update(owner_id=self.owner_id,owner_pid=self.pr.get(self.request['repository'],self.request['pr_number'])['owner_pid'],
            completed=False,proof=None)
        barrier['base_sha']='0'*40
        with self.assertRaises(ValueError): self.gate(barrier=barrier)

    def test_actual_retained_semantic_proof_is_readonly(self):
        from task_tower import pr_effects
        self.assertTrue(callable(getattr(pr_effects,'_unpublished_proof',None)),
            'Missing genuine retained/current semantic proof')
        before=self.journal.read_bytes()
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            proof=pr_effects._unpublished_proof(self.ctx,self.host.source(self.ctx),self.pr,
                self.fresh['task'],self.receipt)
        self.assertEqual(proof['receipt'],self.receipt)
        self.assertEqual(before,self.journal.read_bytes())

    def test_imported_receipt_cannot_replace_confirmed_process(self):
        from task_tower import pr_effects
        self.assertTrue(callable(getattr(pr_effects,'_unpublished_proof',None)))
        receipt=copy.deepcopy(self.receipt); receipt['summary']='Imported replacement'
        from task_tower.pr_policy import policy_fingerprint
        from task_tower.pr_review import RESULT_KEYS
        receipt['result_sha256']=policy_fingerprint({k:receipt[k] for k in RESULT_KEYS})
        receipt['receipt_sha256']=policy_fingerprint({k:v for k,v in receipt.items() if k!='receipt_sha256'})
        with self.assertRaises(ValueError):
            pr_effects._unpublished_proof(self.ctx,self.host.source(self.ctx),self.pr,
                self.fresh['task'],receipt)

    def test_current_pr_title_change_refuses_even_when_ci_stays_green(self):
        from task_tower.pr_effects import _unpublished_proof
        def change(path,data,count):
            if path=='/pulls/1': data['title']='Changed after independent review'
            return data
        source=self.host.source(self.ctx,change)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
            _unpublished_proof(self.ctx,source,self.pr,self.fresh['task'],self.receipt)

    def test_only_documented_pr_counters_and_timestamp_are_volatile(self):
        from task_tower.pr_effects import _unpublished_proof
        def change(path,data,count):
            if path=='/pulls/1':
                data.update(updated_at='2026-11-03T00:00:00Z',comments=23,review_comments=11)
            return data
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            proof=_unpublished_proof(self.ctx,self.host.source(self.ctx,change),self.pr,
                self.fresh['task'],self.receipt)
        self.assertEqual(proof['receipt'],self.receipt)

    def test_current_private_revocation_refuses_without_rewriting_journal(self):
        from task_tower.pr_effects import _unpublished_proof
        source=self.host.source(self.ctx); raw=self.policy.read_bytes(); before=self.journal.read_bytes()
        try:
            self.policy.write_bytes(raw+b' ')
            with self.assertRaises(ValueError):
                _unpublished_proof(self.ctx,source,self.pr,self.fresh['task'],self.receipt)
            self.assertEqual(self.journal.read_bytes(),before)
        finally:
            self.policy.write_bytes(raw)

    def test_other_actual_journal_cannot_supply_effect_authority(self):
        from task_tower.pr_effects import _unpublished_proof
        from task_tower.pr_journal import PRJournal
        other=PRJournal(self.root/'other-effect-journal.sqlite')
        with self.assertRaises(ValueError):
            _unpublished_proof(self.ctx,self.host.source(self.ctx),other,self.fresh['task'],self.receipt)
        self.assertFalse(other.path.exists())

    def test_new_reviews_own_status_and_still_green_ci_refuse_semantically(self):
        from task_tower.pr_effects import _unpublished_proof
        for mutation in ('review','own_status','green_ci'):
            def change(path,data,count):
                if mutation=='review' and path=='/pulls/1/reviews':
                    return data+[dict(id=909,user=dict(id=809,login='external'),state='COMMENTED',
                        commit_id=self.request['head_sha'],body='New feedback after independent review')]
                if mutation=='own_status' and path.endswith('/statuses'):
                    return data+[dict(id=910,context='task-tower/pr-acceptance',state='success',
                        creator=dict(login=self.fresh['task']['publisher_account']))]
                if mutation=='green_ci' and path.endswith('/check-runs'):
                    data['check_runs'][0]['output']=dict(title='Changed green CI observation')
                return data
            source=self.host.source(self.ctx,change); before=self.journal.read_bytes()
            # Prove refusal is semantic drift, not failed CI/mergeability/source
            # parsing or a fabricated current-ready callback.
            snapshot=source.snapshot(self.fresh['task'])
            self.assertTrue(snapshot['ready'],snapshot['reasons'])
            with self.subTest(mutation=mutation),patch('task_tower.pr_context._fetch',
                    side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
                _unpublished_proof(self.ctx,source,self.pr,self.fresh['task'],self.receipt)
            self.assertEqual(before,self.journal.read_bytes())
