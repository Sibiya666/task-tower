"""Genuine registration-backed queued metadata never enables execution."""
import copy
import json
import sqlite3
import unittest
from contextlib import closing
from tests import test_group_registration as fixture
from tests.test_pipeline_journal import request

class QueuedAdmissionTests(unittest.TestCase):
    setUp=fixture.RegistrationContextTests.setUp
    load=fixture.RegistrationContextTests.load
    seed=fixture.RegistrationContextTests.seed

    def req(self):return dict(request(18),repository='owner/repo',task_id='TT-GROUPS-001',runner_label='local')

    def test_actual_queue_identity_repeat_and_execution_remains_closed(self):
        self.seed();before=self.j.status()['runs']
        self.assertTrue(callable(getattr(self.j,'submit_group',None)),'Missing genuine queue producer')
        with self.load() as ctx:
            self.j.register_groups(ctx);req=self.req();receipt=self.j.submit_group(req,context=ctx)
            self.assertEqual(self.j.submit_group(req,context=ctx),receipt)
            self.assertEqual(self.j.lookup(req['delivery_id']),receipt)
            with self.assertRaises(ValueError):self.j.submit_group(self.req(),context=ctx)
        rows=self.j.status()['runs'];self.assertEqual(len(rows),len(before)+1)
        self.assertEqual([r for r in rows if r['run_id']==before[0]['run_id']][0],before[0])
        row=next(r for r in rows if r['run_id']==receipt['receipt_id'])
        self.assertEqual(row['state'],'queued');self.assertIsNone(row['owner_id']);self.assertEqual(row['process_count'],0)
        with closing(sqlite3.connect(self.j.path)) as db:
            self.assertEqual(db.execute("SELECT run_kind,group_id FROM group_runs WHERE run_id=?",(row['run_id'],)).fetchone(),('group','core'))
            for table in ('group_actions','group_resource_leases','group_resource_observations','group_base_epochs','group_reservations'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        with self.assertRaises(ValueError):self.j.claim('00000000-0000-4000-8000-000000000002',2)
        self.f.path.unlink();self.f.executor_path.unlink()
        self.assertEqual(self.j.lookup(req['delivery_id']),receipt)
        self.assertEqual(len(self.j.status()['runs']),2)

    def test_bad_context_and_private_identity_refuse_without_mutation(self):
        self.seed()
        self.assertTrue(callable(getattr(self.j,'submit_group',None)),'Missing genuine queue producer')
        with self.load() as ctx:
            self.j.register_groups(ctx);before=self.j.path.read_bytes()
            for context,req in [(dict(policy=ctx.policy),self.req()),(ctx,dict(self.req(),task_id='TT-FOREIGN-001')),(ctx,dict(self.req(),runner_label='other'))]:
                with self.assertRaises(ValueError):self.j.submit_group(req,context=context)
                self.assertEqual(self.j.path.read_bytes(),before)

    def test_queued_cancel_is_offline_and_never_creates_resources(self):
        self.seed()
        with self.load() as ctx:
            self.j.register_groups(ctx);receipt=self.j.submit_group(self.req(),context=ctx)
        self.f.path.unlink();self.f.executor_path.unlink()
        self.j.cancel(receipt['receipt_id'])
        self.assertEqual(self.j.status(receipt['receipt_id'])['state'],'cancelled')

    def test_self_consistent_scope_mutation_is_not_a_saved_private_task(self):
        from task_tower.pipeline_inputs import canonical_json,digest_manifest
        self.seed()
        with self.load() as ctx:
            self.j.register_groups(ctx);receipt=self.j.submit_group(self.req(),context=ctx)
        with closing(sqlite3.connect(self.j.path)) as db:
            raw=db.execute('SELECT binding_json FROM group_runs WHERE run_id=?',(receipt['receipt_id'],)).fetchone()[0]
            binding=json.loads(raw);binding['task_policy']['allowed_paths'].append('outside/')
            raw=canonical_json(binding).decode();digest=digest_manifest(binding)
            db.execute('UPDATE group_runs SET binding_json=?,binding_sha256=? WHERE run_id=?',(raw,digest,receipt['receipt_id']))
            seq,raw_event=db.execute("SELECT sequence,body_json FROM group_events WHERE run_id=? AND kind='binding'",(receipt['receipt_id'],)).fetchone()
            event=json.loads(raw_event);event.update(binding=binding,binding_sha256=digest)
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',(canonical_json(event).decode(),digest_manifest(event),seq));db.commit()
        before=self.j.path.read_bytes()
        with self.assertRaises(ValueError):self.j.status()
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_last_private_reload_failure_rolls_back_all_queue_rows(self):
        from unittest.mock import patch
        self.seed()
        with self.load() as ctx:
            self.j.register_groups(ctx);before=self.j.path.read_bytes();real=ctx.revalidate;calls=[]
            def reload_actual():
                real();calls.append(True)
                if len(calls)==3:raise ValueError('Injected source loss after real reload')
            with patch.object(ctx,'revalidate',side_effect=reload_actual),self.assertRaises(ValueError):
                self.j.submit_group(self.req(),context=ctx)
            self.assertEqual(self.j.path.read_bytes(),before)

    def test_mutable_context_pipeline_copy_cannot_replace_actual_private_policy(self):
        self.seed()
        with self.load() as ctx:
            self.j.register_groups(ctx);expected=ctx.policy['_pipeline_config']['policy_sha256']
            ctx.pipeline=copy.deepcopy(ctx.pipeline);ctx.pipeline['policy_sha256']='f'*64
            receipt=self.j.submit_group(self.req(),context=ctx)
        self.assertEqual(self.j.status(receipt['receipt_id'])['policy_sha256'],expected)
