import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import dispatcher


class DispatcherTests(unittest.TestCase):
    def test_disabled_never_constructs_sources_or_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / 'absent' / 'journal.db'
            report = dispatcher.tick([], {'allowlist': [], 'backend': None}, path,
                store_factory=lambda c: self.fail('source called'))
            self.assertEqual(report['disabled'], 'empty_allowlist')
            self.assertFalse(path.parent.exists())

    def test_status_missing_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            connections = root / 'connections.json'
            config = root / 'dispatcher.json'
            connections.write_text(json.dumps({'version': 1, 'projects': []}))
            config.write_text('{"version":1}')
            before = {p.name:p.read_bytes() for p in root.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()):
                code = dispatcher.main(['--connections', str(connections), '--config', str(config),
                    '--journal', str(root / 'missing' / 'journal.db'), '--status'])
            self.assertEqual(code, 0)
            self.assertEqual(before, {p.name:p.read_bytes() for p in root.iterdir()})

    def test_corrupt_status_journal_is_operational_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            (root/'connections').write_text('{"version":1,"projects":[]}')
            (root/'config').write_text('{"version":1}')
            (root/'journal').write_bytes(b'corrupt database')
            with contextlib.redirect_stderr(io.StringIO()):
                code=dispatcher.main(['--connections',str(root/'connections'),'--config',str(root/'config'),
                    '--journal',str(root/'journal'),'--status'])
            self.assertEqual(code,1)

    def test_private_paths_cannot_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / 'input.json'
            path.write_text('{}')
            with self.assertRaises(ValueError):
                dispatcher.validate_paths(path, path, path.with_name('journal'), [])

    def test_loop_reloads_config_and_stops_on_interrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root/'connections').write_text('{"version":1,"projects":[]}')
            (root/'config').write_text('{"version":1,"interval_seconds":5}')
            calls = []
            def sleep(interval):
                calls.append(interval)
                raise KeyboardInterrupt
            with contextlib.redirect_stdout(io.StringIO()), patch.object(dispatcher, "tick", return_value={"operational_failure":False}):
                code = dispatcher.main(['--connections',str(root/'connections'),'--config',str(root/'config'),
                    '--journal',str(root/'journal')], sleep=sleep)
            self.assertEqual(code, 0)
            self.assertEqual(calls, [5])


class TickIntegrationTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        self.connection = SimpleNamespace(repository='o/r', checkout=self.checkout, runner_label='local')
        self.backend = {'argv':[__import__('sys').executable], 'cwd':str(self.root), 'timeout_seconds':1}
        self.config = {'allowlist':[{'repository':'o/r','issue':1,'task_id':'TT-ONE'}], 'backend':self.backend}
        self.calls=[]
        self.changed=False
        owner=self
        class Store:
            def list_issues(self): return [{'number':1,'state':'open','body':''}]
            def metadata(self,row): return {'task_id':'TT-ONE','kind':'task','mode':'autonomous','status':'open'}
            def get(self,number):
                return {'number':number,'state':'closed' if owner.changed else 'open','body':''}
        self.store=Store()
    def tearDown(self): self.temporary.cleanup()
    def invoke(self,backend,request):
        self.calls.append(request)
        return {'status':'accepted','receipt_id':'private-receipt'}
    def run_tick(self,**kwargs):
        with patch('task_tower.dispatch_selection.issue_lifecycle',return_value={'status':'open'}):
            return dispatcher.tick([self.connection],self.config,self.root/'journal',
                store_factory=lambda c:self.store,source_factory=lambda c:object(),invoke=self.invoke,**kwargs)
    def test_dry_run_does_not_create_journal_or_call_backend(self):
        before=set(self.root.iterdir())
        report=self.run_tick(dry_run=True)
        self.assertEqual(report['deliveries'][0]['state'],'planned')
        self.assertEqual(self.calls,[])
        self.assertEqual(before,set(self.root.iterdir()))
    def test_latest_issue_closure_prevents_submit(self):
        self.changed=True
        self.run_tick()
        self.assertEqual(self.calls,[])
    def test_accepted_delivery_is_not_invoked_on_second_tick(self):
        self.run_tick(); self.run_tick()
        self.assertEqual([r['operation'] for r in self.calls],['submit'])

    def test_private_revocation_before_adapter_prevents_submit(self):
        self.run_tick(authority_check=lambda:False)
        self.assertEqual(self.calls,[])

    def test_unknown_lookup_reconciles_closed_task_without_resubmit(self):
        self.invoke=lambda backend,request: {'status':'unknown'}
        self.run_tick()
        self.changed=True
        self.invoke=lambda backend,request: self.calls.append(request) or {'status':'accepted','receipt_id':'receipt'}
        self.run_tick()
        self.assertEqual([r['operation'] for r in self.calls],['lookup'])

    def test_removed_authorization_never_looks_up_unknown(self):
        self.invoke=lambda backend,request: {'status':'unknown'}
        self.run_tick()
        self.config['allowlist']=[]
        self.invoke=lambda backend,request: self.fail('revoked backend call')
        self.assertEqual(self.run_tick()['disabled'],'empty_allowlist')

    def test_final_source_failure_sets_operational_failure(self):
        original=self.store.list_issues
        calls=[]
        def listing():
            calls.append(1)
            if len(calls)>1: raise OSError('private source detail')
            return original()
        self.store.list_issues=listing
        report=self.run_tick()
        self.assertTrue(report['operational_failure'])
        self.assertEqual(self.calls,[])

    def test_separate_eight_lookup_and_submit_budgets_progress_next_tick(self):
        from task_tower.dispatch_delivery import DeliveryJournal, backend_fingerprint
        rows=[{'number':n,'state':'open','body':''} for n in range(1,19)]
        self.store.list_issues=lambda:rows
        self.store.get=lambda n:rows[n-1]
        self.store.metadata=lambda row: {'task_id':f"TT-{row['number']}",'kind':'task','mode':'autonomous','status':'open'}
        self.config['allowlist']=[{'repository':'o/r','issue':n,'task_id':f'TT-{n}'} for n in range(1,19)]
        journal=DeliveryJournal(self.root/'journal')
        for n in range(1,10):
            journal.reserve({'repository':'o/r','issue':n,'task_id':f'TT-{n}'},backend_fingerprint(self.backend))
        report=self.run_tick()
        self.assertEqual([r['issue'] for r in self.calls if r['operation']=='lookup'],list(range(1,9)))
        self.assertEqual([r['issue'] for r in self.calls if r['operation']=='submit'],list(range(10,18)))
        self.assertTrue(report['operational_failure'])
        deferred={r['issue'] for r in report['deliveries'] if r['state']=='deferred'}
        self.assertEqual(deferred,{9,18})
        self.calls.clear()
        report=self.run_tick()
        self.assertEqual([(r['operation'],r['issue']) for r in self.calls],[('lookup',9),('submit',18)])
        self.assertFalse(report['operational_failure'])
