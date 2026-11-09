"""Safe receipts preserve failure boundaries without exporting private exception text."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import io
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
from task_tower.connector.store import ConnectorStore
from task_tower.connector.worktrees import Worktrees
from task_tower.connector.client import LifecycleConnector
from task_tower.connector import diagnostics,cli

B='a'*40

class FailureReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=ConnectorStore(self.root/'journal','host1');self.addCleanup(self.store.close)
        self.command=dict(version=1,kind='execute',command_id='cmd',attempt_id='attempt',project_id='p',base_sha=B,
                          input={'text':'approved task'},source=dict(base_sha=B,head_sha=B,diff=''))
        self.store.receive(self.command)

    def test_git_disk_full_retains_typed_process_receipt_without_exception_paths(self):
        trees=object.__new__(Worktrees)
        def failed(argv,cwd,timeout,env=None,*,capture):
            p=Path(capture['directory'])
            (p/'stdout.log').write_bytes(b'')
            (p/'stderr.log').write_bytes(b'fatal: cannot create /private/secret: No space left on device\n')
            return dict(status='failed',exit_code=128,cleanup_confirmed=True,stdout_tail_unknown=False,
                        stderr_tail_unknown=False,stdout_truncated=False,stderr_truncated=False)
        with patch('task_tower.connector.worktrees.run_command',side_effect=failed):
            with self.assertRaises(ValueError) as caught:trees._git(self.root,'worktree','add','private-target')
        receipt=getattr(caught.exception,'receipt',None)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt['reason'],'git_disk_full')
        self.assertEqual(receipt['operation'],'worktree_add')
        self.assertEqual(receipt['process']['exit_code'],128)
        self.assertTrue(receipt['process']['cleanup_confirmed'])
        self.assertNotIn('/private/secret',json.dumps(receipt))

    def test_prepare_failure_is_durable_without_registering_a_start(self):
        class API:
            def validate_command(self,key):return {}
        class Trees:
            def prepare(self,*args):raise ValueError('secret-token /private/path')
        c=LifecycleConnector(self.store,API(),Trees(),lambda *a,**kw:self.fail('executor must not start'))
        c._execute_lifecycle(self.command,dict(apps={},replies={}))
        data=self.store.command('cmd')
        self.assertEqual(data['phase'],'needs_reconciliation')
        receipt=data.get('failure_receipt')
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt['stage'],'prepare')
        self.assertEqual(receipt['reason'],'unclassified')
        self.assertNotIn('secret-token',json.dumps(data))
        events=self.store.pending_events()
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['lifecycle']['kind'],'failed')
        self.assertEqual(set(events[0]['lifecycle']),{'kind','command_id'})

    def test_source_capture_failure_keeps_the_specific_boundary(self):
        self.store.update('cmd',phase='executing',thread_id='t',turn_id='v')
        class App:
            def notifications(self):return [dict(method='turn/completed',params=dict(threadId='t',turn=dict(id='v',status='completed',items=[])))]
        class Trees:
            def source(self,*args):raise ValueError('dirty_worktree')
        c=LifecycleConnector(self.store,None,Trees(),None)
        c._poll_lifecycle('cmd',App(),dict(apps={}))
        receipt=self.store.command('cmd').get('failure_receipt')
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt['stage'],'source_capture')
        self.assertEqual(receipt['reason'],'dirty_worktree')

    def test_turn_start_failure_never_claims_that_an_unknown_turn_did_not_start(self):
        class API:
            def validate_command(self,key):return {}
        class Trees:
            def prepare(self,*args):return dict(path=str(self.root))
        Trees.root=self.root
        class App:
            def create_thread(self,*a,**kw):return 'thread'
            def start_turn(self,*a,**kw):raise TimeoutError('token should stay private')
        c=LifecycleConnector(self.store,API(),Trees(),lambda *a,**kw:App())
        c._execute_lifecycle(self.command,dict(apps={},replies={}))
        receipt=self.store.command('cmd').get('failure_receipt')
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt['stage'],'turn_start')
        self.assertEqual(receipt['reason'],'unclassified')
        self.assertNotIn('not_started',json.dumps(receipt))

    def test_inspect_reads_a_live_writer_without_recovery_or_private_payload(self):
        self.store.update('cmd',phase='executing',thread_id='t',turn_id='v')
        self.store.save_worktree('attempt',dict(project_id='p',path=str(self.root/'private-worktree'),state='preparing',base_sha=B))
        self.store.lifecycle_event('attempt','started',command_id='cmd',thread_id='t',turn_id='v')
        before=(self.store.commands(),self.store.pending_events())
        reader=getattr(diagnostics,'inspect_attempt',None)
        self.assertTrue(callable(reader),'supported read-only inspection is missing')
        result=reader(self.store.path,'host1','attempt',{'p'})
        self.assertEqual(result['pending_outbox_count'],1)
        self.assertEqual(result['commands'][0]['phase'],'executing')
        self.assertTrue(result['commands'][0]['thread_registered'])
        self.assertIsNone(result['commands'][0]['failure_receipt'])
        self.assertEqual(result['worktree']['state'],'preparing')
        self.assertEqual((self.store.commands(),self.store.pending_events()),before)
        for secret in ('approved task','private-worktree',str(self.root)):
            self.assertNotIn(secret,json.dumps(result))

    def test_inspect_refuses_foreign_connector_project_missing_or_linked_journal(self):
        reader=getattr(diagnostics,'inspect_attempt',None)
        self.assertTrue(callable(reader),'supported read-only inspection is missing')
        for connector,attempt,projects in [('foreign','attempt',{'p'}),('host1','attempt',{'other'}),('host1','absent',{'p'})]:
            with self.subTest(connector=connector,attempt=attempt),self.assertRaises(ValueError):
                reader(self.store.path,connector,attempt,projects)
        missing=self.root/'missing'
        with self.assertRaises(ValueError):reader(missing,'host1','attempt',{'p'})
        self.assertFalse(missing.exists())
        link=self.root/'linked'
        try:link.hardlink_to(self.store.path)
        except OSError:pass
        else:
            with self.assertRaises(ValueError):reader(link,'host1','attempt',{'p'})

    def test_cli_inspect_needs_neither_api_token_nor_store_constructor(self):
        cfg=dict(version=1,connector_id='host1',endpoint='http://127.0.0.1:1',
                 token_file=str(self.root/'not-read-token'),journal=str(self.store.path),app_server=str(self.root/'not-started'),
                 projects={'p':dict(repository=str(self.root),worktree_root=str(self.root/'trees'))},assignments=[])
        path=self.root/'config.json';path.write_text(json.dumps(cfg),encoding='utf-8')
        out=io.StringIO()
        with (patch.object(cli,'ConnectorStore',side_effect=AssertionError('must not open writer')),
                patch.object(cli,'read_token',side_effect=AssertionError('must not read credential'))):
            with redirect_stdout(out),redirect_stderr(io.StringIO()):
                try:status=cli.main(['inspect','attempt','--config',str(path)])
                except SystemExit as error:status=error.code
        self.assertEqual(status,0)
        self.assertEqual(json.loads(out.getvalue())['commands'][0]['phase'],'queued')

    def test_receipt_rejects_untrusted_extra_fields_without_mutating_command(self):
        good=diagnostics.failure_receipt('prepare',ValueError('dirty_worktree'))
        bad=[dict(good,private_path='secret'),dict(good,stage=['private']),dict(good,reason='token')]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.store.lifecycle_transition('cmd','needs_reconciliation','failed',failure_receipt=value)
            self.assertEqual(self.store.command('cmd')['phase'],'queued')
            self.assertEqual(self.store.pending_events(),[])

    def test_inspect_snapshot_stays_consistent_while_writer_commits(self):
        failures=[]
        def write():
            try:
                for n in range(1,31):
                    self.store.lifecycle_transition('cmd','executing' if n%2 else 'queued','started')
                    time.sleep(.001)
            except Exception as error:failures.append(error)
        writer=threading.Thread(target=write);writer.start()
        try:
            for _ in range(8):
                result=diagnostics.inspect_attempt(self.store.path,'host1','attempt',{'p'})
                phase=result['commands'][0]['phase'];count=result['pending_outbox_count']
                self.assertEqual(phase,'executing' if count%2 else 'queued')
        finally:writer.join(5)
        self.assertFalse(writer.is_alive());self.assertEqual(failures,[])

    def test_invalid_git_receipt_does_not_enter_durable_failure_state(self):
        git=dict(reason='git_operation_unknown',operation=[],process={},artifact={})
        value=dict(version=1,stage='prepare',reason='git_operation_unknown',git=git)
        with self.assertRaises(ValueError):
            self.store.lifecycle_transition('cmd','needs_reconciliation','failed',failure_receipt=value)
        self.assertEqual(self.store.command('cmd')['phase'],'queued')

    def test_inspect_stops_an_over_budget_sql_read_without_acknowledging_events(self):
        with self.store.lock,self.store.db:
            self.store.db.executemany('INSERT INTO outbox(event_id,data) VALUES (?,?)',[(str(i),'{}') for i in range(2000)])
        with patch.object(diagnostics,'time',create=True) as clock:
            clock.monotonic.side_effect=[0]+[3]*100
            with self.assertRaises(ValueError):diagnostics.inspect_attempt(self.store.path,'host1','attempt',{'p'})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM outbox WHERE acked=0').fetchone()[0],2000)

    def test_unverified_artifact_permissions_never_retain_private_raw(self):
        (self.root/'stdout.log').write_bytes(b'private output')
        (self.root/'stderr.log').write_bytes(b'private error')
        with patch.object(diagnostics,'private_directory',return_value=False,create=True):
            receipt=diagnostics.git_receipt(('worktree','add'),dict(exit_code=128,status='failed',cleanup_confirmed=True),self.root)
        self.assertFalse(receipt['artifact']['retained'])
        self.assertIsNone(receipt['artifact']['id'])

    def test_inspect_does_not_count_events_owned_by_another_attempt(self):
        event=self.store.lifecycle_event('other-attempt','started',command_id='foreign')
        event.update(attempt_id='attempt',connector_id='other-host')
        with self.store.lock,self.store.db:
            self.store.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',('foreign-event',json.dumps(event)))
        result=diagnostics.inspect_attempt(self.store.path,'host1','attempt',{'p'})
        self.assertEqual(result['pending_outbox_count'],0)
        self.assertEqual(len(self.store.pending_events()),2)

    def test_unverified_initial_capture_never_launches_git_or_writes_raw(self):
        launches=[]
        def launch(argv,cwd,timeout,env=None,*,capture):
            launches.append(True)
            (Path(capture['directory'])/'stdout.log').write_bytes(b'private output')
            return dict(status='passed',exit_code=0,cleanup_confirmed=True)
        with (patch('task_tower.connector.worktrees.private_directory',return_value=False,create=True),
              patch('task_tower.connector.worktrees.run_command',side_effect=launch)):
            with self.assertRaises(ValueError) as caught:object.__new__(Worktrees)._git(self.root,'status','--porcelain')
        self.assertEqual(launches,[])
        self.assertEqual(caught.exception.receipt['reason'],'git_capture_not_private')

    def test_private_directory_creation_is_exclusive_and_private_on_this_host(self):
        create=getattr(diagnostics,'create_private_directory',None)
        self.assertTrue(callable(create),'private capture creation is missing')
        target=self.root/'private-capture';create(target)
        self.assertTrue(diagnostics.private_directory(target))
        marker=target/'keep';marker.write_text('owned',encoding='utf-8')
        with self.assertRaises(OSError):create(target)
        self.assertEqual(marker.read_text(encoding='utf-8'),'owned')

    def test_private_directory_verification_never_starts_a_subprocess(self):
        target=self.root/'native-private';diagnostics.create_private_directory(target)
        with patch('subprocess.run',side_effect=AssertionError('no verifier subprocess')):
            self.assertTrue(diagnostics.private_directory(target))

    @unittest.skipUnless(os.name=='nt','Windows ACL contract')
    def test_native_acl_check_rejects_public_null_empty_and_foreign_owner_descriptors(self):
        c,w,adv,kernel,_=diagnostics._windows_api();sid=diagnostics._current_sid()
        adv.GetSecurityDescriptorOwner.argtypes=[w.LPVOID,c.POINTER(w.LPVOID),c.POINTER(w.BOOL)]
        adv.GetSecurityDescriptorOwner.restype=w.BOOL
        adv.GetSecurityDescriptorDacl.argtypes=[w.LPVOID,c.POINTER(w.BOOL),c.POINTER(w.LPVOID),c.POINTER(w.BOOL)]
        adv.GetSecurityDescriptorDacl.restype=w.BOOL
        allows='(A;;FA;;;'+sid+')(A;;FA;;;SY)(A;;FA;;;BA)'
        cases=[('O:'+sid+'D:P'+allows,True),('O:'+sid+'D:P'+allows+'(A;;FR;;;WD)',False),
               ('O:SYD:P'+allows,False),('O:'+sid,False),('O:'+sid+'D:',False),
               ('O:'+sid+'D:P(D;;FA;;;WD)'+allows,True)]
        for sddl,want in cases:
            def query(path,object_type,information,owner_out,group_out,acl_out,sacl_out,descriptor_out):
                descriptor=w.LPVOID();owner=w.LPVOID();acl=w.LPVOID();default=w.BOOL();present=w.BOOL()
                self.assertTrue(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,c.byref(descriptor),None))
                self.assertTrue(adv.GetSecurityDescriptorOwner(descriptor,c.byref(owner),c.byref(default)))
                self.assertTrue(adv.GetSecurityDescriptorDacl(descriptor,c.byref(present),c.byref(acl),c.byref(default)))
                c.cast(owner_out,c.POINTER(w.LPVOID))[0]=owner.value
                c.cast(acl_out,c.POINTER(w.LPVOID))[0]=acl.value
                c.cast(descriptor_out,c.POINTER(w.LPVOID))[0]=descriptor.value
                return 0
            with self.subTest(sddl=sddl),patch.object(adv,'GetNamedSecurityInfoW',side_effect=query):
                self.assertEqual(diagnostics.private_directory(self.root),want)
