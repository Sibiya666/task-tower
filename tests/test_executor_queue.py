import tempfile
import unittest
import uuid
from pathlib import Path
from task_tower.executor_queue import ExecutionQueue

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.q=ExecutionQueue(Path(self.tmp.name).resolve()/'queue.sqlite3')
    def request(self):
        return dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=15,task_id='TT-EXECUTOR-001',runner_label='local')
    def test_durable_idempotent_admission_collision_and_lookup(self):
        r=self.request(); first=self.q.submit(r,'a'*64,profile_id='custom')
        self.assertEqual(first,self.q.submit(r,'a'*64,profile_id='custom'))
        self.assertEqual(first,self.q.lookup(r['delivery_id']))
        with self.assertRaises(ValueError): self.q.submit(dict(r,issue=16),'a'*64,profile_id='custom')
        self.assertEqual(self.q.status(first['receipt_id'])['state'],'queued')
    def test_cancel_before_claim_and_owner_cas(self):
        a=self.q.submit(self.request(),'a'*64); self.q.cancel(a['receipt_id'])
        self.assertIsNone(self.q.claim(str(uuid.uuid4())))
        b=self.q.submit(self.request(),'a'*64); owner=str(uuid.uuid4()); job=self.q.claim(owner)
        self.assertEqual(job['run_id'],b['receipt_id']); self.assertEqual(job['attempt'],1)
        with self.assertRaises(ValueError): self.q.record(job['run_id'],str(uuid.uuid4()),'running',{})
        self.q.record(job['run_id'],owner,'running',{})
        self.q.record(job['run_id'],owner,'unknown',{})
        with self.assertRaises(ValueError): self.q.record(job['run_id'],owner,'running',{})
    def test_unknown_consumes_capacity_and_unknown_owner_not_recovered(self):
        for _ in range(3): self.q.submit(self.request(),'a'*64)
        for _ in range(2):
            owner=str(uuid.uuid4()); job=self.q.claim(owner); self.q.record(job['run_id'],owner,'unknown',{})
        self.assertIsNone(self.q.claim(str(uuid.uuid4())))
        with self.assertRaises(ValueError): self.q.claim(str(uuid.uuid4()),max_active=3)
        self.assertEqual(self.q.recover(),[])
    def test_lookup_absent_does_not_create_files(self):
        self.assertIsNone(self.q.lookup(str(uuid.uuid4())))
        self.assertEqual(list(Path(self.tmp.name).resolve().iterdir()),[])
    def test_exact_request_and_profile_collision(self):
        r=self.request()
        with self.assertRaises(ValueError): self.q.submit(dict(r,extra='secret'),'a'*64)
        self.q.submit(r,'a'*64)
        with self.assertRaises(ValueError): self.q.submit(r,'b'*64)

    def test_real_live_sibling_survives_recovery_dead_owner_fenced(self):
        import subprocess, sys, time
        receipt=self.q.submit(self.request(),'a'*64)
        script="""import sys,time,uuid
from task_tower.executor_queue import ExecutionQueue
q=ExecutionQueue(sys.argv[1]); owner=str(uuid.uuid4())
with q.owner(owner):
 job=q.claim(owner)
 print(job['run_id'],flush=True)
 time.sleep(30)
"""
        child=subprocess.Popen([sys.executable,'-c',script,str(self.q.path)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),receipt['receipt_id'])
            self.assertEqual(self.q.recover(),[])
            self.assertEqual(self.q.status(receipt['receipt_id'])['state'],'claimed')
            child.kill(); child.wait(timeout=5)
            self.assertEqual(self.q.recover(),[receipt['receipt_id']])
            self.assertEqual(self.q.status(receipt['receipt_id'])['state'],'unknown')
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=5)
            child.stdout.close()
    def test_foreign_corrupt_and_wal_lookup_preserves_files(self):
        import sqlite3
        r=self.request(); self.q.submit(r,'a'*64)
        db=sqlite3.connect(self.q.path)
        try: db.execute("UPDATE jobs SET state='claimed'"); db.commit()
        finally: db.close()
        before=self.q.path.read_bytes()
        with self.assertRaises(ValueError): self.q.lookup(r['delivery_id'])
        self.assertEqual(self.q.path.read_bytes(),before)
    def test_competing_real_process_claims_have_single_winner(self):
        import subprocess,sys
        self.q.submit(self.request(),'a'*64)
        script="import sys,uuid; from task_tower.executor_queue import ExecutionQueue; print(bool(ExecutionQueue(sys.argv[1]).claim(str(uuid.uuid4()))))"
        children=[subprocess.Popen([sys.executable,'-c',script,str(self.q.path)],stdout=subprocess.PIPE,text=True) for _ in range(2)]
        try:
            outcomes=[p.communicate(timeout=10)[0].strip() for p in children]
            self.assertEqual(sorted(outcomes),['False','True'])
            self.assertTrue(all(p.returncode==0 for p in children))
        finally:
            for child in children:
                if child.poll() is None: child.kill(); child.wait()

    def test_sqlite_sidecar_disappearing_after_exists_does_not_block_claim(self):
        from unittest.mock import patch
        self.q.submit(self.request(),'a'*64)
        sidecar=Path(str(self.q.path)+'-journal')
        sidecar.write_bytes(b'transient SQLite rollback journal')
        original=Path.exists; removed=False; calls=0
        def exists(path):
            nonlocal removed,calls
            result=original(path)
            if path==sidecar:calls+=1
            if path==sidecar and result and calls==2:
                # The safety check must allow a genuinely absent transient
                # file after another writer removes it following exists().
                sidecar.unlink(); removed=True
            return result
        with patch.object(Path,'exists',exists):
            claimed=self.q.claim(str(uuid.uuid4()))
        self.assertTrue(removed)
        self.assertEqual(claimed['state'],'claimed')

    def test_hardlinked_sqlite_sidecars_remain_rejected(self):
        import os
        self.q.submit(self.request(),'a'*64)
        for suffix in ('-journal','-wal','-shm'):
            sidecar=Path(str(self.q.path)+suffix)
            with self.subTest(suffix=suffix):
                os.link(self.q.path,sidecar)
                try:
                    with self.assertRaises(ValueError):ExecutionQueue(self.q.path)
                finally:sidecar.unlink()

    def test_wal_lookup_is_fail_closed_without_sidecar_changes(self):
        import sqlite3
        r=self.request(); self.q.submit(r,'a'*64)
        db=sqlite3.connect(self.q.path)
        try:
            db.execute('PRAGMA journal_mode=WAL'); db.execute("UPDATE jobs SET cancel_requested=1"); db.commit()
            before={p.name:p.read_bytes() for p in Path(self.tmp.name).resolve().iterdir()}
            with self.assertRaises(ValueError): self.q.lookup(r['delivery_id'])
            self.assertEqual({p.name:p.read_bytes() for p in Path(self.tmp.name).resolve().iterdir()},before)
        finally: db.close()
    def test_private_aliases_and_checkout_are_rejected(self):
        import os
        checkout=Path(self.tmp.name).resolve()/'checkout'; checkout.mkdir()
        with self.assertRaises(ValueError): ExecutionQueue(checkout/'q',checkouts=[checkout])
        input_path=Path(self.tmp.name).resolve()/'connections'; input_path.write_text('{}')
        with self.assertRaises(ValueError): ExecutionQueue(input_path,forbidden_paths=[input_path])
        alias=Path(self.tmp.name).resolve()/'alias'; os.link(input_path,alias)
        with self.assertRaises(ValueError): ExecutionQueue(alias)
    def test_orphan_attempt_identity_is_corruption(self):
        import sqlite3
        r=self.request(); self.q.submit(r,'a'*64)
        db=sqlite3.connect(self.q.path)
        try: db.execute('UPDATE jobs SET attempt_id=?',(str(uuid.uuid4()),)); db.commit()
        finally: db.close()
        with self.assertRaises(ValueError): self.q.lookup(r['delivery_id'])
    def test_owner_can_record_durable_preparation_intent_before_effect(self):
        receipt=self.q.submit(self.request(),'a'*64); owner=str(uuid.uuid4()); self.q.claim(owner)
        self.q.record(receipt['receipt_id'],owner,'claimed',{'preparation_intent':True})
        self.assertTrue(self.q.status(receipt['receipt_id'])['evidence']['preparation_intent'])

    def test_record_rejects_conflicting_provenance_atomically(self):
        receipt=self.q.submit(self.request(),'a'*64)
        owner=str(uuid.uuid4()); self.q.claim(owner)
        original={'source_sha':'a'*40,'worktree_hash':'b'*64,'launch_intent':True}
        self.q.record(receipt['receipt_id'],owner,'claimed',original)
        for key,value in [('source_sha','c'*40),('worktree_hash','d'*64),('launch_intent',False)]:
            before=self.q.status(receipt['receipt_id'])
            with self.assertRaises(ValueError):
                self.q.record(receipt['receipt_id'],owner,'running',{key:value,'new_marker':True})
            self.assertEqual(self.q.status(receipt['receipt_id']),before)
        self.q.record(receipt['receipt_id'],owner,'claimed',original)
        self.q.record(receipt['receipt_id'],owner,'running',{'launch_intent':True,'new_marker':True})
        self.assertEqual(self.q.status(receipt['receipt_id'])['evidence'],dict(original,new_marker=True))
        self.q.record(receipt['receipt_id'],owner,'running',{'new_marker':True})

    def failed_prelaunch(self,proof=None):
        receipt=self.q.submit(self.request(),'a'*64); owner=str(uuid.uuid4())
        job=self.q.claim(owner)
        evidence={'started':False,'cleanup_confirmed':True,'prelaunch_failure':True,'source_sha':'b'*40}
        if proof is not None: evidence=proof
        self.q.record(job['run_id'],owner,'failed',evidence)
        return job,self.q.status(job['run_id'])
    def test_explicit_retry_archives_provenance_and_next_claim_increments(self):
        job,failed=self.failed_prelaunch()
        retry=self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=2)
        self.assertEqual(retry['state'],'queued'); self.assertEqual(retry['attempt'],1)
        self.assertIsNone(retry['owner_id']); self.assertIsNone(retry['attempt_id']); self.assertIsNone(retry['owner_pid'])
        self.assertEqual(retry['evidence'],{})
        history=self.q.history(job['run_id'])
        self.assertEqual(len(history),1)
        self.assertEqual(history[0],{k:failed[k] for k in ('run_id','attempt','attempt_id','owner_id','owner_pid','evidence')})
        owner=str(uuid.uuid4()); second=self.q.claim(owner)
        self.assertEqual(second['attempt'],2); self.assertNotEqual(second['attempt_id'],job['attempt_id'])
        self.q.record(job['run_id'],owner,'failed',{'started':False,'cleanup_confirmed':True,'prelaunch_failure':True,'source_sha':'c'*40})
        self.assertEqual(self.q.history(job['run_id']),history)
        before=self.q.status(job['run_id'])
        with self.assertRaises(ValueError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=2)
        self.assertEqual(self.q.status(job['run_id']),before); self.assertEqual(self.q.history(job['run_id']),history)
    def test_retry_denies_missing_uncertain_or_counterfeit_proof_atomically(self):
        safe={'started':False,'cleanup_confirmed':True,'prelaunch_failure':True}
        for proof in [{},dict(safe,started=True),dict(safe,started=0),dict(safe,cleanup_confirmed=1),dict(safe,prelaunch_failure=1),dict(safe,cleanup_confirmed=False),dict(safe,prelaunch_failure=False)]:
            with self.subTest(proof=proof):
                job,before=self.failed_prelaunch(proof)
                with self.assertRaises(ValueError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=2)
                self.assertEqual(self.q.status(job['run_id']),before); self.assertEqual(self.q.history(job['run_id']),[])
    def test_retry_denies_other_states_revocation_cancel_and_invalid_bounds(self):
        for state in ('queued','claimed','running','unknown','cancelled','timed_out','execution_completed','needs_input'):
            with self.subTest(state=state):
                receipt=self.q.submit(self.request(),'a'*64); owner=str(uuid.uuid4())
                if state!='queued':
                    job=self.q.claim(owner)
                    if state not in ('claimed',):
                        self.q.record(job['run_id'],owner,'running',{})
                        if state!='running': self.q.record(job['run_id'],owner,state,{'started':False,'cleanup_confirmed':True,'prelaunch_failure':True})
                before=self.q.status(receipt['receipt_id'])
                with self.assertRaises(ValueError): self.q.retry_prelaunch(receipt['receipt_id'],profile_fingerprint='a'*64,max_attempts=2)
                self.assertEqual(self.q.status(receipt['receipt_id']),before)
                # release conservative capacity for this independent case
                self.q=ExecutionQueue(Path(self.tmp.name).resolve()/(str(uuid.uuid4())+'.db'))
        job,before=self.failed_prelaunch()
        for fingerprint,bound in [('b'*64,2),('a'*64,1),('a'*64,True),('a'*64,0),('a'*64,11),('a'*64,2.0)]:
            with self.subTest(fingerprint=fingerprint,bound=bound):
                with self.assertRaises(ValueError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint=fingerprint,max_attempts=bound)
                self.assertEqual(self.q.status(job['run_id']),before)
                self.assertEqual(self.q.history(job['run_id']),[])
        self.q.cancel(job['run_id']); before=self.q.status(job['run_id'])
        with self.assertRaises(ValueError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=2)
        self.assertEqual(self.q.status(job['run_id']),before)
    def test_competing_retry_has_single_winner_and_history_record(self):
        import subprocess,sys
        job,_=self.failed_prelaunch()
        script="""import sys
from task_tower.executor_queue import ExecutionQueue
try:
 ExecutionQueue(sys.argv[1]).retry_prelaunch(sys.argv[2],profile_fingerprint='a'*64,max_attempts=2)
 print('True')
except ValueError: print('False')
"""
        children=[subprocess.Popen([sys.executable,'-c',script,str(self.q.path),job['run_id']],stdout=subprocess.PIPE,text=True) for _ in range(2)]
        try:
            outcomes=[p.communicate(timeout=10)[0].strip() for p in children]
            self.assertEqual(sorted(outcomes),['False','True'])
            self.assertTrue(all(p.returncode==0 for p in children))
        finally:
            for child in children:
                if child.poll() is None: child.kill(); child.wait()
        self.assertEqual(len(self.q.history(job['run_id'])),1)
    def test_previous_v1_schema_rejected_without_migration(self):
        import sqlite3
        from task_tower.executor_queue import APP_ID,SCHEMA
        db=sqlite3.connect(self.q.path)
        try:
            db.execute('PRAGMA application_id='+str(APP_ID)); db.execute('PRAGMA user_version=1'); db.execute(SCHEMA); db.commit()
        finally: db.close()
        before=self.q.path.read_bytes()
        with self.assertRaises(ValueError): self.q.lookup(str(uuid.uuid4()))
        self.assertEqual(self.q.path.read_bytes(),before)

    def test_retry_transaction_failure_preserves_current_and_history(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        job,before=self.failed_prelaunch()
        database=self.q._db
        @contextmanager
        def interrupted(write=False):
            with database(write) as db:
                yield db
                if write: raise OSError('interrupted before commit')
        with patch.object(self.q,'_db',interrupted):
            with self.assertRaises(OSError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=2)
        self.assertEqual(self.q.status(job['run_id']),before)
        self.assertEqual(self.q.history(job['run_id']),[])
    def test_retry_history_preserves_all_nine_attempts_at_cap(self):
        job,_=self.failed_prelaunch()
        for ordinal in range(1,10):
            self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=10)
            history=self.q.history(job['run_id'])
            self.assertEqual([row['attempt'] for row in history],list(range(1,ordinal+1)))
            owner=str(uuid.uuid4()); next_job=self.q.claim(owner)
            self.assertEqual(next_job['attempt'],ordinal+1)
            self.q.record(job['run_id'],owner,'failed',{'started':False,'cleanup_confirmed':True,'prelaunch_failure':True})
            self.assertEqual(self.q.history(job['run_id']),history)
        before=self.q.status(job['run_id'])
        with self.assertRaises(ValueError): self.q.retry_prelaunch(job['run_id'],profile_fingerprint='a'*64,max_attempts=10)
        self.assertEqual(self.q.status(job['run_id']),before)
        self.assertEqual(len(self.q.history(job['run_id'])),9)
