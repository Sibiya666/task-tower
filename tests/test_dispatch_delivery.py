import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from task_tower.dispatch_delivery import DeliveryJournal, backend_fingerprint, deliver, run_backend

CANDIDATE = dict(repository='Owner/Repo', issue=1, task_id='TT-ONE', runner_label='trusted')
BACKEND = dict(argv=[sys.executable, '{request}', '{result}'], cwd=str(Path.cwd().resolve()), timeout_seconds=2)


def race_submit(path, output):
    def invoke(backend, request):
        output.put(request['operation'])
        return dict(status='unknown')
    deliver(CANDIDATE, BACKEND, DeliveryJournal(Path(path)), invoke=invoke)


def race(path, output):
    row, won = DeliveryJournal(Path(path)).reserve(CANDIDATE, backend_fingerprint(BACKEND))
    output.put(won)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'journal.sqlite'

    def test_commit_precedes_submit_and_restart_only_looks_up(self):
        operations = []
        def invoke(backend, request):
            self.assertEqual(DeliveryJournal(self.path, readonly=True).rows()[0]['status'], 'unknown')
            operations.append(request['operation'])
            return dict(status='unknown')
        deliver(CANDIDATE, BACKEND, DeliveryJournal(self.path), invoke=invoke)
        deliver(CANDIDATE, BACKEND, DeliveryJournal(self.path), invoke=invoke)
        self.assertEqual(operations, ['submit', 'lookup'])

    def test_crash_after_reservation_restart_never_submits(self):
        context = multiprocessing.get_context('spawn')
        queue = context.Queue()
        process = context.Process(target=race, args=(str(self.path), queue))
        process.start(); process.join(15)
        self.assertEqual(process.exitcode, 0)
        self.assertTrue(queue.get(timeout=2))
        calls = []
        deliver(CANDIDATE, BACKEND, DeliveryJournal(self.path), invoke=lambda b,r: calls.append(r['operation']) or dict(status='not_found'))
        self.assertEqual(calls, ['lookup'])

    def test_two_processes_have_one_reservation_winner(self):
        context = multiprocessing.get_context('spawn'); queue = context.Queue()
        processes = [context.Process(target=race, args=(str(self.path), queue)) for _ in range(2)]
        for process in processes: process.start()
        for process in processes: process.join(15); self.assertEqual(process.exitcode, 0)
        self.assertEqual(sorted(queue.get(timeout=2) for _ in processes), [False, True])

    def test_accepted_monotonic_and_mismatches_never_invoke(self):
        journal = DeliveryJournal(self.path)
        row, _ = journal.reserve(CANDIDATE, backend_fingerprint(BACKEND))
        changed = dict(CANDIDATE, task_id='TT-TWO')
        for candidate, backend in [(changed, BACKEND), (CANDIDATE, dict(BACKEND, timeout_seconds=3))]:
            result = deliver(candidate, backend, journal, invoke=lambda *a: self.fail('invoked mismatch'))
            self.assertEqual(result['state'], 'needs_input')
        journal.accept(row['delivery_id'], 'receipt:1')
        deliver(CANDIDATE, BACKEND, journal, invoke=lambda *a: self.fail('invoked accepted'))
        self.assertEqual(journal.rows()[0]['status'], 'accepted')
        self.assertNotIn('receipt:1', json.dumps(deliver(CANDIDATE, BACKEND, journal)))

    def test_concurrent_processes_submit_once_and_only_lookup_afterward(self):
        context=multiprocessing.get_context('spawn'); queue=context.Queue()
        workers=[context.Process(target=race_submit,args=(str(self.path),queue)) for _ in range(2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(15); self.assertEqual(worker.exitcode,0)
        self.assertEqual(sorted(queue.get(timeout=2) for _ in workers),['lookup','submit'])

    def test_stale_negative_lookup_preserves_concurrent_accept(self):
        journal=DeliveryJournal(self.path)
        row,_=journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        def invoke(backend,request):
            DeliveryJournal(self.path).accept(row['delivery_id'],'concurrent')
            return dict(status='not_found')
        self.assertEqual(deliver(CANDIDATE,BACKEND,journal,invoke=invoke)['state'],'accepted')

    def test_journal_path_boundaries_and_readonly_reservation(self):
        checkout=self.root/'checkout'; checkout.mkdir()
        with self.assertRaises(ValueError): DeliveryJournal(checkout/'journal',checkouts=[checkout])
        with self.assertRaises(ValueError): DeliveryJournal(self.path,forbidden_paths=[self.path])
        with self.assertRaises(ValueError): DeliveryJournal(self.path,readonly=True).reserve(CANDIDATE,backend_fingerprint(BACKEND))
        self.assertFalse(self.path.exists())

    def test_readonly_wal_journal_does_not_create_sidecars(self):
        journal=DeliveryJournal(self.path); journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        db=sqlite3.connect(self.path)
        self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0],'wal')
        db.close()
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaises(ValueError): DeliveryJournal(self.path,readonly=True).rows()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_readonly_uncheckpointed_wal_preserves_current_acceptance_files(self):
        journal=DeliveryJournal(self.path); row,_=journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        db=sqlite3.connect(self.path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute("UPDATE deliveries SET status='accepted',detail='accepted',receipt_id='in-wal' WHERE delivery_id=?",(row['delivery_id'],))
            db.commit()
            before={p.name:p.read_bytes() for p in self.root.iterdir()}
            self.assertIn(self.path.name+'-wal',before)
            with self.assertRaises(ValueError): DeliveryJournal(self.path,readonly=True).rows()
            self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
            self.assertEqual(db.execute('SELECT status FROM deliveries').fetchone()[0],'accepted')
        finally:
            db.close()

    def test_same_columns_without_required_constraints_are_rejected(self):
        journal=DeliveryJournal(self.path); journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        db=sqlite3.connect(self.path)
        db.execute('ALTER TABLE deliveries RENAME TO old')
        db.execute('CREATE TABLE deliveries(repository,issue,task_id,delivery_id,backend_fingerprint,status,detail,receipt_id)')
        db.execute('INSERT INTO deliveries SELECT * FROM old'); db.execute('DROP TABLE old'); db.commit(); db.close()
        with self.assertRaises(ValueError): journal.rows()

    def test_submit_budget_race_loser_can_defer_lookup(self):
        journal=DeliveryJournal(self.path); journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        result=deliver(CANDIDATE,BACKEND,journal,lookup_existing=False,invoke=lambda *a:self.fail('unexpected lookup'))
        self.assertEqual(result['state'],'needs_input')
        self.assertEqual(result['reason'],'lookup_deferred')

    def test_corrupt_row_fails_closed(self):
        journal=DeliveryJournal(self.path); journal.reserve(CANDIDATE,backend_fingerprint(BACKEND))
        db=sqlite3.connect(self.path)
        db.execute("UPDATE deliveries SET backend_fingerprint='corrupt'"); db.commit(); db.close()
        with self.assertRaises(ValueError): journal.rows()

    def test_result_link_is_rejected(self):
        result=self.adapter("import pathlib,sys,os\np=pathlib.Path(sys.argv[2]); target=p.with_name('other'); target.write_text('{}'); os.link(target,p)")
        self.assertEqual(result['reason'],'invalid_result')

    def test_round_robin_survives_restart(self):
        journal = DeliveryJournal(self.path)
        for issue in range(1, 12): journal.reserve(dict(CANDIDATE, issue=issue), backend_fingerprint(BACKEND))
        first = journal.lookup_rows(8)
        second = DeliveryJournal(self.path).lookup_rows(8)
        self.assertEqual([r['issue'] for r in first], list(range(1,9)))
        self.assertEqual([r['issue'] for r in second][:3], [9,10,11])

    def test_readonly_missing_does_not_create_and_existing_unchanged(self):
        missing = self.root/'absent'/'journal'
        self.assertEqual(DeliveryJournal(missing, readonly=True).rows(), [])
        self.assertFalse(missing.parent.exists())
        journal=DeliveryJournal(self.path); journal.reserve(CANDIDATE, backend_fingerprint(BACKEND))
        before=self.path.read_bytes()
        self.assertEqual(len(DeliveryJournal(self.path, readonly=True).rows()), 1)
        self.assertEqual(before,self.path.read_bytes())

    def test_unrecognized_database_and_hardlink_fail_closed(self):
        db=sqlite3.connect(self.path)
        db.execute('CREATE TABLE other(value)'); db.commit(); db.close()
        with self.assertRaises(ValueError): DeliveryJournal(self.path).rows()
        self.path.unlink(); self.path.write_text('input')
        alias=self.root/'alias'; os.link(self.path,alias)
        with self.assertRaises(ValueError): DeliveryJournal(alias).rows()

    def adapter(self, code, operation='submit'):
        script=self.root/'adapter.py'; script.write_text(code,encoding='utf-8')
        backend=dict(argv=[sys.executable,str(script),'{request}','{result}','{checkout}'],cwd=str(self.root),timeout_seconds=1)
        request=dict(operation=operation,delivery_id='123',repository='owner/repo',issue=1,task_id='TT-ONE',runner_label='trusted')
        return run_backend(backend,request)

    def test_real_adapter_managed_files_and_sanitized_receipt(self):
        result=self.adapter("import json,sys,pathlib,os\nr=json.loads(pathlib.Path(sys.argv[1]).read_text()); assert len(r)==6; assert pathlib.Path(sys.argv[3])==pathlib.Path.cwd(); pathlib.Path(sys.argv[2]).write_text(json.dumps(dict(version=1,delivery_id=r['delivery_id'],status='accepted',receipt_id='ok:1')))\n")
        self.assertEqual(result,dict(status='accepted',receipt_id='ok:1'))

    def test_invalid_protocol_and_process_failures(self):
        payloads=['{}','{"version":true,"delivery_id":"123","status":"unknown"}', '{"version":1,"version":1,"delivery_id":"123","status":"unknown"}', '{"version":1,"delivery_id":"wrong","status":"unknown"}', '{"version":1,"delivery_id":"123","status":"accepted","receipt_id":"é"}', '{"version":1,"delivery_id":"123","status":"not_found"}', '{"version":1,"delivery_id":"123","status":"unknown","extra":1}', '{}{}']
        for payload in payloads:
            with self.subTest(payload=payload):
                result=self.adapter('import pathlib,sys\npathlib.Path(sys.argv[2]).write_bytes('+repr(payload.encode())+')')
                self.assertEqual(result['status'],'unknown')
                self.assertEqual(result['reason'],'invalid_result')
        for code in ['import sys;sys.exit(1)', 'import time;time.sleep(5)', 'import pathlib,sys;pathlib.Path(sys.argv[2]).write_bytes(b"x"*65537)', 'import pathlib,sys;pathlib.Path(sys.argv[2]).mkdir()', 'import pathlib,sys;pathlib.Path(sys.argv[2]).write_bytes(b"\\xff")']:
            self.assertEqual(self.adapter(code)['status'],'unknown')

    def test_cleanup_failure_and_unknown_templates_fail(self):
        with patch('task_tower.dispatch_delivery.processes.run_command', return_value=dict(status='cleanup_failed',exit_code=0)):
            self.assertEqual(self.adapter('')['status'],'unknown')
        with self.assertRaises(ValueError): backend_fingerprint(dict(BACKEND,argv=['{issue}']))

if __name__=='__main__': unittest.main()







