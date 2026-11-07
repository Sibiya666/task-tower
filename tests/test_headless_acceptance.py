"""Acceptance persists evidence before owner-close; ambiguous effects are fenced."""
import unittest
from task_tower.service import acceptance
from tests.test_headless_delivery import attempt,H,B,M,REPO

class AcceptanceTests(unittest.TestCase):
    def test_plain_model_or_docs_evidence_cannot_accept_runtime(self):
        a=attempt();a.update(phase='postmerge',repository=REPO,pr_number=7,main_sha=M)
        for evidence in ({'verdict':'approve'}, {'kind':'documentation.validation','runtime_tests':'not_run','main_sha':M}, {}):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):acceptance.accept(a,evidence)


def evidence(a):
    return dict(version=1,kind='runtime.validation',repository=REPO,pr_number=7,head_sha=a['head_sha'],base_sha=a['base_sha'],main_sha=M,
        runtime_tests='passed',ci_run_id=42,artifact_digests=[c*64 for c in 'def01'],
        postmerge_review=dict(verdict='approve',findings=[],head_sha=M,base_sha=a['base_sha'],reviewer_thread_id='postmerge-review'),
        fetch=dict(successful=True,main_sha=M,seconds=1,local_seconds=.2),
        validation=dict(exact_once=True,fresh_discovery=True,matrix_successful=True))

class AcceptanceIntegration(unittest.TestCase):
    def setUp(self):
        from tests.test_service_lifecycle import LifecycleTests,SOURCE
        self.h=LifecycleTests('runTest');self.h.setUp();self.addCleanup(self.h.doCleanups)
        h=self.h;a=h.start();h.complete(a,'author',source=SOURCE)
        self.a=h.complete(a,'review',h.verdict('review','approve'));self.s=h.s;self.s.delivery_projects={'p':REPO}
        original=h.native.__call__
        def run(argv,cwd,timeout,env):
            args=argv[argv.index('--actor')+2:]
            if args[0]=='history':
                return [dict(id='close-event',issue_id='pilot-0',event_type='closed',actor=self.a['actor'],new_value=self.close_reason)]
            if args[0]=='close':self.close_reason=args[args.index('--reason')+1]
            return original(argv,cwd,timeout,env)
        h.beads.runner=run
    def test_review_approval_issues_delivery_command_and_acceptance_owner_closes_once(self):
        commands=self.h.commands(self.a)
        self.assertEqual(commands[-1]['kind'],'deliver')
        result=self.s.accept_delivery('receipt',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),evidence(self.a))
        self.assertEqual(result['phase'],'accepted')
        self.assertEqual(result['canonical_close']['event_id'],'close-event')
        self.assertEqual(self.h.native.rows['pilot-0']['status'],'closed')
        self.assertEqual(self.s.accept_delivery('receipt',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),evidence(self.a)),result)
        self.assertEqual(sum(c[c.index('--actor')+2]=='close' for c in self.h.native.calls),1)
    def test_evidence_persisted_before_close_and_lost_close_response_reads_back(self):
        original=self.h.beads.runner
        def run(argv,cwd,timeout,env):
            if 'close' in argv:
                row=self.s.db.execute('SELECT data FROM acceptance_effects').fetchone()
                self.assertIsNotNone(row)
                original(argv,cwd,timeout,env)
                raise TimeoutError('lost close')
            return original(argv,cwd,timeout,env)
        self.h.beads.runner=run
        r=self.s.accept_delivery('receipt',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),evidence(self.a))
        self.assertEqual(r['phase'],'accepted')
        self.assertEqual(sum(c[c.index('--actor')+2]=='close' for c in self.h.native.calls),1)
    def test_failed_postmerge_and_foreign_owner_leave_task_open(self):
        bad=evidence(self.a);bad['postmerge_review']['reviewer_thread_id']='author'
        from task_tower.service.beads import ServiceError
        with self.assertRaises(ServiceError):
            self.s.accept_delivery('bad',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),bad)
        self.assertEqual(self.h.native.rows['pilot-0']['status'],'in_progress')
        self.h.native.rows['pilot-0']['assignee']='someone-else'
        with self.assertRaises(ServiceError):self.s.accept_delivery('receipt',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),evidence(self.a))
        self.assertEqual(self.h.native.rows['pilot-0']['status'],'in_progress')

    def test_real_connector_delivery_consumes_command_and_closes_via_api(self):
        import tempfile,time,threading
        from pathlib import Path
        from task_tower.connector.client import LifecycleConnector,APIClient
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.delivery import Delivery
        from task_tower.service.api import make_server
        from tests.test_headless_delivery import Host
        test=self
        class TrustedHost(Host):
            def prepare_pr(host,a):
                host.pr['branch']='codex/headless-'+a['attempt_id']
                return super().prepare_pr(a)
            def verify_main(host,a,merge):
                test.assertEqual(test.s.attempt(a['attempt_id'])['phase'],'postmerge')
                return evidence(a)
        with tempfile.TemporaryDirectory() as temp:
            local=ConnectorStore(Path(temp)/'connector','host1')
            server=make_server(self.s,{'host1':dict(token='A'*32,projects=['p'])},port=0)
            t=threading.Thread(target=server.serve_forever);t.start()
            api=APIClient('http://127.0.0.1:'+str(server.server_port),'host1','A'*32)
            if getattr(self,'lose_accept_response',False):
                original_accept=api.accept
                def lost(*args):original_accept(*args);raise ConnectionError('lost HTTP response after native close')
                api.accept=lost
            d=Delivery(TrustedHost(),local,{'p':REPO})
            errors=[];original_run=d.run
            def traced(*args):
                try:return original_run(*args)
                except Exception as error:errors.append(str(error));raise
            d.run=traced
            c=None
            try:
                c=LifecycleConnector(local,api,None,lambda *args,**kw:self.fail('model launched for fixed host delivery'),delivery=d)
                # This boundary fixture owns the retained author process it closes.
                import queue
                author=dict(version=1,kind='execute',command_id='fixture-author',attempt_id=self.a['attempt_id'],project_id='p',base_sha=B,input={'text':'approved implementation'},source=self.a['source'])
                local.receive(author);local.update('fixture-author',phase='completed',thread_id='author',turn_id='fixture-turn')
                class OwnedAuthor:
                    closed=False
                    def close(author):author.closed=True
                owned=OwnedAuthor();worker=dict(queue=queue.Queue(4),apps={'fixture-author':owned},replies={},busy=False,reserved=0)
                c.workers[self.a['attempt_id']]=worker;worker['thread']=threading.Thread(target=c._work,args=(self.a['attempt_id'],worker),daemon=True);worker['thread'].start()
                end=time.monotonic()+5
                while time.monotonic()<end:
                    c.tick()
                    if self.s.attempt(self.a['attempt_id'])['phase']=='accepted' and any(d['command'].get('kind')=='deliver' and d['phase']=='completed' for d in local.commands()):break
                    time.sleep(.01)
                self.assertEqual(self.s.attempt(self.a['attempt_id'])['phase'],'accepted',errors)
                self.assertEqual(self.h.native.rows['pilot-0']['status'],'closed')
                result=next(d for d in local.commands() if d['command'].get('kind')=='deliver')
                self.assertEqual(result['phase'],'completed',errors);self.assertTrue(owned.closed);self.assertIs(result['cleanup_confirmed'],True)
                self.assertEqual(local.db.execute('SELECT count(*) FROM repository_delivery').fetchone()[0],0)
            finally:
                if c is not None:c.close()
                local.close();server.shutdown();server.server_close();t.join(2)

    def test_service_serializes_repository_delivery_and_rejects_unapproved_repository(self):
        from task_tower.service.beads import ServiceError
        from tests.test_service_lifecycle import SOURCE
        first=self.h.commands(self.a)[-1]
        self.s.validate_lifecycle_command(first['command_id'],'host1')
        a=self.h.start(1);self.h.complete(a,'second-author',source=SOURCE)
        second=self.h.complete(a,'second-review',self.h.verdict('second-review','approve'))
        command=self.h.commands(second)[-1]
        with self.assertRaises(ServiceError):self.s.validate_lifecycle_command(command['command_id'],'host1')
        wrong=dict(repository='other/repo',pr_number=7,head_sha=H,base_sha=B,main_sha=M)
        with self.assertRaises(ServiceError):self.s.accept_delivery('wrong',self.a['attempt_id'],'host1',wrong,evidence(self.a))
        self.assertEqual(self.h.native.rows['pilot-0']['status'],'in_progress')

    def test_busy_repository_does_not_consume_or_fence_connector_command(self):
        import tempfile
        from pathlib import Path
        from task_tower.connector.client import LifecycleConnector
        from task_tower.connector.store import ConnectorStore
        from tests.test_service_lifecycle import SOURCE
        first=self.h.commands(self.a)[-1];self.s.validate_lifecycle_command(first['command_id'],'host1')
        a=self.h.start(1);self.h.complete(a,'author2',source=SOURCE)
        second=self.h.complete(a,'review2',self.h.verdict('review2','approve'));command=self.h.commands(second)[-1]
        outer=self
        class API:
            def commands(api):return [command]
            def validate_command(api,key):return outer.s.validate_lifecycle_command(key,'host1')
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        local=ConnectorStore(Path(temp.name)/'connector','busy-fixture');self.addCleanup(local.close)
        c=LifecycleConnector(local,API(),None,None,delivery=object());self.addCleanup(c.close)
        c.tick()
        self.assertEqual(local.commands(),[])
        self.assertEqual(self.s.attempt(second['attempt_id'])['phase'],'awaiting_merge')

    def test_changed_base_invalidates_review_and_uses_same_executor_with_correction_bound(self):
        newbase='d'*40
        command=self.h.commands(self.a)[-1]
        changed=self.h.emit(self.a,'delivery_changed',command_id=command['command_id'],base_sha=newbase)
        self.assertEqual((changed['phase'],changed['base_sha'],changed['correction_count']),('revising',newbase,1))
        revise=self.h.commands(changed)[-1]
        self.assertEqual(revise['thread_id'],'author')
        self.assertEqual(revise['update_base'],dict(old_base_sha=B,new_base_sha=newbase))
        self.assertNotEqual(revise['kind'],'deliver')

    def test_docs_delivery_closes_with_typed_not_run_receipt_without_runtime_claim(self):
        proof=evidence(self.a);proof.update(kind='documentation.validation',runtime_tests='not_run',artifact_digests=['d'*64],validation=dict(scope='docs',fresh_validation=True,runtime_shards='skipped'))
        result=self.s.accept_delivery('docs-receipt',self.a['attempt_id'],'host1',dict(repository=REPO,pr_number=7,head_sha=H,base_sha=B,main_sha=M),proof)
        self.assertEqual(result['phase'],'accepted')
        self.assertEqual(result['accepted_evidence']['kind'],'documentation.validation')
        self.assertEqual(result['accepted_evidence']['runtime_tests'],'not_run')

    def test_lost_accept_http_response_reads_canonical_result_before_releasing_repository(self):
        self.lose_accept_response=True
        self.test_real_connector_delivery_consumes_command_and_closes_via_api()
        self.assertEqual(sum(c[c.index('--actor')+2]=='close' for c in self.h.native.calls),1)

    def test_runtime_receipt_cannot_omit_a_required_artifact_digest(self):
        a=dict(self.a,phase='postmerge',repository=REPO,pr_number=7,main_sha=M)
        proof=evidence(a);proof['artifact_digests']=proof['artifact_digests'][:2]
        with self.assertRaises(ValueError):acceptance.accept(a,proof)

    def test_trusted_delivery_changed_base_preserves_history_and_releases_only_premerge_lease(self):
        import tempfile,threading
        from pathlib import Path
        from task_tower.connector.delivery import Delivery
        from task_tower.connector.store import ConnectorStore
        from tests.test_headless_delivery import Host
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        store=ConnectorStore(Path(temp.name)/'connector','host1');self.addCleanup(store.close)
        command=self.h.commands(self.a)[-1];store.receive(command)
        host=Host();host.pr.update(base_sha='d'*40,branch='codex/headless-'+self.a['attempt_id'])
        d=Delivery(host,store,{'p':REPO});outer=self
        class API:
            def validate_command(self,key):return outer.s.validate_lifecycle_command(key,'host1')
        d.run(command,API(),threading.Event())
        events=store.pending_events();self.assertEqual(len(events),1)
        changed=self.s.record_event(events[0])
        self.assertEqual((changed['phase'],changed['base_sha']),('revising','d'*40))
        self.assertEqual(store.db.execute('SELECT count(*) FROM repository_delivery').fetchone()[0],0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM acceptance_repository').fetchone()[0],0)
        self.assertNotIn('merge',host.calls)
        self.assertEqual(self.h.commands(changed)[-1]['thread_id'],'author')
    def test_fourth_base_change_requires_input_and_quiescent_ack_without_fourth_revision(self):
        from task_tower.service.lifecycle import advance
        a=dict(self.a,correction_count=3)
        actions=advance(a,dict(kind='delivery_changed',base_sha='d'*40),{})
        self.assertEqual(actions[0]['changes']['phase'],'needs_input')
        self.assertFalse(actions[0]['changes']['quiescent'])
        self.assertEqual(actions[0]['changes']['correction_count'],3)
        self.assertEqual([x['kind'] for x in actions[1:]],['quiesce'])

    def test_unknown_resource_binding_stops_before_remote_acceptance_effect(self):
        import tempfile,threading
        from pathlib import Path
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.delivery import Delivery
        from tests.test_headless_delivery import Host
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        local=ConnectorStore(Path(temp.name)/'journal','host1');self.addCleanup(local.close)
        command=self.h.commands(self.a)[-1];local.receive(command);outer=self;accepted=[]
        class API:
            def validate_command(api,key):return outer.s.validate_lifecycle_command(key,'host1')
            def send_event(api,event):return outer.s.record_event(event)
            def accept(api,key,request_id,merge,proof):accepted.append(1);return outer.s.accept_delivery(request_id,key,'host1',merge,proof)
        class GitHub(Host):
            def prepare_pr(host,a):host.pr['branch']='codex/headless-'+a['attempt_id'];return super().prepare_pr(a)
            def verify_main(host,a,merge):return evidence(a)
        d=Delivery(GitHub(),local,{'p':REPO})
        with self.assertRaises(ValueError):d.run(command,API(),threading.Event())
        self.assertEqual(accepted,[]);self.assertEqual(self.h.native.rows['pilot-0']['status'],'in_progress')
        self.assertEqual(local.cleanup_reservations(),{self.a['attempt_id']})


class DeliveryCapacityTests(unittest.TestCase):
    def scenario(self,mode):
        import tempfile,threading,queue,time
        from pathlib import Path
        from task_tower.connector.client import LifecycleConnector
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.app_server import AppServer
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        store=ConnectorStore(root/'journal','delivery-capacity-'+mode);self.addCleanup(store.close)
        source=dict(head_sha=H,base_sha=B,diff='whole approved diff')
        author=dict(version=1,kind='execute',command_id='author-cmd',attempt_id='attempt',project_id='p',base_sha=B,input={'text':'approved'},source=source)
        deliver=dict(version=1,kind='deliver',command_id='deliver-cmd',attempt_id='attempt',project_id='p',base_sha=B,attempt=attempt())
        second=dict(version=1,kind='execute',command_id='next-cmd',attempt_id='second',project_id='p',base_sha=B,input={'text':'second approved'},source=dict(head_sha=B,base_sha=B,diff=''))
        store.receive(author);store.update('author-cmd',phase='completed',thread_id='author',turn_id='author-turn')
        class RetainedAuthor:
            closed=False
            allow_cleanup=False
            def close(self):
                if mode=='unknown-cleanup' and not self.allow_cleanup:raise RuntimeError('cleanup unknown')
                self.closed=True
        retained=RetainedAuthor();started=threading.Event()
        class Wire:
            def request(self,method,params):
                if method=='thread/start':return {'thread':{'id':'second-author'}}
                if method=='turn/start':started.set();return {'turn':{'id':'second-turn'}}
                raise AssertionError(method)
            def notifications(self):return []
            def close(self):pass
        commands=[deliver] if getattr(self,'known_restart_probe',False) else [deliver,second]
        class API:
            def commands(self):return list(commands)
            def validate_command(self,key):return {}
            def send_event(self,event):return {}
        class Trees:
            def prepare(self,*args):return dict(path=str(root))
        deliveries=[]
        class Delivered:
            def run(self,*args):
                deliveries.append(1)
                return None if mode=='superseded' else dict(phase='accepted',canonical_close={'event_id':'close','owner':'owner'})
        c=LifecycleConnector(store,API(),Trees(),lambda cwd,request_handler=None:AppServer(store,transport=Wire(),request_handler=request_handler),max_active_tasks=1,delivery=Delivered());self.addCleanup(c.close)
        worker=dict(queue=queue.Queue(4),apps={'author-cmd':retained},replies={},busy=False,reserved=0)
        c.workers['attempt']=worker;worker['thread']=threading.Thread(target=c._work,args=('attempt',worker),daemon=True);worker['thread'].start()
        end=time.monotonic()+2
        while time.monotonic()<end:
            c.tick()
            if started.is_set():break
            current=next((d for d in store.commands() if d['command']['command_id']=='deliver-cmd'),None)
            if getattr(self,'known_restart_probe',False) and current and current['phase']=='completed' and not worker['busy']:break
            if mode!='accepted' and current and current['phase'] in ('completed','needs_reconciliation') and not worker['busy']:
                for _ in range(3):c.tick();time.sleep(.01)
                break
            time.sleep(.01)
        if mode=='accepted':
            self.assertTrue(retained.closed)
            if not getattr(self,'known_restart_probe',False):self.assertTrue(started.is_set(),'confirmed accepted delivery must admit the next configured task')
            self.assertFalse(c._occupied(worker));self.assertEqual(store.command('deliver-cmd')['phase'],'completed')
        elif mode=='unknown-cleanup':
            self.assertFalse(retained.closed);self.assertFalse(started.is_set());self.assertTrue(c._occupied(worker))
            self.assertEqual(store.command('deliver-cmd')['phase'],'needs_reconciliation')
            self.assertIs(store.command('deliver-cmd')['cleanup_confirmed'],False)
        else:
            self.assertFalse(retained.closed);self.assertFalse(started.is_set());self.assertTrue(c._occupied(worker))
        if getattr(self,'known_quiesce_probe',False):
            retained.allow_cleanup=True
            control=dict(version=1,kind='quiesce',command_id='known-owned-stop',attempt_id='attempt',project_id='p',base_sha=B)
            commands.insert(0,control);end=time.monotonic()+2
            while time.monotonic()<end:
                c.tick();time.sleep(.01)
                if any(d['command']['command_id']=='known-owned-stop' and d['phase']=='completed' for d in store.commands()):break
            self.assertTrue(retained.closed);self.assertEqual(store.command('known-owned-stop')['phase'],'completed')
            self.assertIs(store.command('deliver-cmd')['cleanup_confirmed'],True)
            commands.remove(control);c.close();store.close()
            reopened=ConnectorStore(root/'journal','delivery-capacity-'+mode);self.addCleanup(reopened.close)
            new=LifecycleConnector(reopened,API(),Trees(),lambda cwd,request_handler=None:AppServer(reopened,transport=Wire(),request_handler=request_handler),max_active_tasks=1,delivery=Delivered());self.addCleanup(new.close)
            end=time.monotonic()+2
            while not started.is_set() and time.monotonic()<end:new.tick();time.sleep(.01)
            self.assertTrue(started.is_set());self.assertEqual(deliveries,[1])
        if getattr(self,'known_restart_probe',False):
            c.close();store.close()
            reopened=ConnectorStore(root/'journal','delivery-capacity-'+mode);self.addCleanup(reopened.close)
            self.assertIs(reopened.command('deliver-cmd')['cleanup_confirmed'],True)
            new=LifecycleConnector(reopened,API(),Trees(),lambda cwd,request_handler=None:AppServer(reopened,transport=Wire(),request_handler=request_handler),max_active_tasks=1,delivery=Delivered());self.addCleanup(new.close)
            commands.append(second);end=time.monotonic()+2
            while not started.is_set() and time.monotonic()<end:new.tick();time.sleep(.01)
            self.assertTrue(started.is_set());self.assertEqual(deliveries,[1])
        if getattr(self,'restart_probe',False):
            c.close();store.close()
            # Real close/reopen of the SAME SQLite journal, with a NEW connector.
            reopened=ConnectorStore(root/'journal','delivery-capacity-'+mode);self.addCleanup(reopened.close)
            new=LifecycleConnector(reopened,API(),Trees(),lambda cwd,request_handler=None:AppServer(reopened,transport=Wire(),request_handler=request_handler),max_active_tasks=1,delivery=Delivered());self.addCleanup(new.close)
            for _ in range(8):new.tick();time.sleep(.01)
            self.assertFalse(started.is_set(),'restart must retain the unknown-cleanup slot')
            self.assertEqual(deliveries,[1],'old delivery must never replay')
            self.assertIs(reopened.command('deliver-cmd')['cleanup_confirmed'],False)
            # An unbound quiesce cannot guess old process ownership or ACK cleanup.
            control=dict(version=1,kind='quiesce',command_id='unknown-stop',attempt_id='attempt',project_id='p',base_sha=B)
            commands.insert(0,control);new.tick();time.sleep(.02)
            self.assertNotIn('unknown-stop',{x['command']['command_id'] for x in reopened.commands()})
            commands.remove(control)
            # Explicit operator-confirmed fixture reconciliation, not restart,
            # a closed Bead, a PID guess, or an automatic recovery operation.
            reopened.update('deliver-cmd',cleanup_confirmed=True,reconciliation={'kind':'operator_confirmed_cleanup','receipt':'fixture-cleanup-proof'})
            end=time.monotonic()+2
            while not started.is_set() and time.monotonic()<end:new.tick();time.sleep(.01)
            self.assertTrue(started.is_set());self.assertEqual(deliveries,[1])
        if getattr(self,'other_slot_probe',False):
            c.max_active_tasks=2
            end=time.monotonic()+2
            while not started.is_set() and time.monotonic()<end:c.tick();time.sleep(.01)
            self.assertTrue(started.is_set(),'one durable and one live reservation for SAME attempt count only once')
            c.max_active_tasks=1;started.clear()
            third=dict(second,command_id='third-cmd',attempt_id='third')
            control=dict(version=1,kind='quiesce',command_id='stop-second',attempt_id='second',project_id='p',base_sha=B)
            commands.extend([control,third])
            end=time.monotonic()+2
            while time.monotonic()<end:
                c.tick();time.sleep(.01)
                if any(d['command']['command_id']=='stop-second' and d['phase']=='completed' for d in store.commands()):break
            self.assertEqual(store.command('stop-second')['phase'],'completed')
            self.assertNotIn('third-cmd',{d['command']['command_id'] for d in store.commands()})
            self.assertFalse(started.is_set());self.assertTrue(c._occupied(worker))
            c.max_active_tasks=2
            end=time.monotonic()+2
            while not started.is_set() and time.monotonic()<end:c.tick();time.sleep(.01)
            self.assertTrue(started.is_set());self.assertIs(store.command('deliver-cmd')['cleanup_confirmed'],False)
    def test_accepted_delivery_stops_retained_author_and_frees_actual_worker_capacity(self):self.scenario('accepted')
    def test_unknown_author_cleanup_preserves_local_fence_and_capacity(self):self.scenario('unknown-cleanup')
    def test_premerge_supersession_keeps_same_author_and_capacity_for_revision(self):self.scenario('superseded')


class DurableCleanupAdmissionTests(unittest.TestCase):
    scenario=DeliveryCapacityTests.scenario
    def test_actual_unknown_cleanup_survives_journal_reopen_until_explicit_reconciliation(self):
        self.restart_probe=True;self.scenario('unknown-cleanup')
    def test_durable_and_live_same_attempt_union_other_slot_lower_limit_and_quiesce(self):
        self.other_slot_probe=True;self.scenario('unknown-cleanup')

    def test_successful_known_cleanup_journal_reopen_admits_next_without_replaying_delivery(self):
        self.known_restart_probe=True;self.scenario('accepted')


class AcceptanceIntentFaultTests(unittest.TestCase):
    def scenario(self,mode,unrelated_unknown=False):
        import contextlib,tempfile,threading,time,json,queue
        from pathlib import Path
        from tests.test_service_lifecycle import LifecycleTests
        from tests.test_headless_delivery import Host
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.client import LifecycleConnector,APIClient
        from task_tower.connector.app_server import AppServer
        from task_tower.connector.delivery import Delivery
        from task_tower.service.api import make_server
        with contextlib.ExitStack() as cleanup:
            h=LifecycleTests('runTest');h.setUp();cleanup.callback(h.doCleanups);service=h.s;service.delivery_projects={'p':REPO}
            a=h.claim();aid=a['attempt_id'];service.start_lifecycle(aid,'host1',B)
            reason={};original_native=h.beads.runner
            def native(argv,cwd,timeout,env):
                args=argv[argv.index('--actor')+2:]
                if args[0]=='history':return [dict(id='close-event',issue_id=a['bead_id'],event_type='closed',actor=a['actor'],new_value=reason['value'])]
                if args[0]=='close':reason['value']=args[args.index('--reason')+1]
                return original_native(argv,cwd,timeout,env)
            h.beads.runner=native
            temp=tempfile.TemporaryDirectory();cleanup.callback(temp.cleanup);root=Path(temp.name)
            local=ConnectorStore(root/'connector','host1');cleanup.callback(local.close)
            if unrelated_unknown:
                old=dict(version=1,kind='quiesce',command_id='unrelated-fence',attempt_id='unrelated',project_id='p',base_sha=B)
                local.receive(old);local.update('unrelated-fence',phase='needs_reconciliation',cleanup_confirmed=False,cleanup_resources=['lost-owned-resource'])
            if mode=='confirmation-write-failure':
                local.db.execute("CREATE TRIGGER fail_confirmation BEFORE UPDATE ON inbox WHEN NEW.data LIKE '%\"cleanup_confirmed\":true%' AND OLD.data LIKE '%\"cleanup_confirmed\":false%' BEGIN SELECT RAISE(ABORT,'fixture confirmation failure'); END")
            server=make_server(service,{'host1':dict(token='A'*32,projects=['p'])},port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def stop_server():server.shutdown();server.server_close();thread.join(3)
            cleanup.callback(stop_server)
            accepting=threading.Event();allow_cleanup=threading.Event();next_started=threading.Event();second_id=[None];author_threads=[];wires=[];intents=[];accept_calls=[]
            healthy=mode in ('success','lost-reply-readback-ok')
            class Client(APIClient):
                def accept(api,key,request_id,merge,proof):
                    accept_calls.append(request_id);intents.append(local.command(request_id).get('cleanup_confirmed'));accepting.set()
                    if mode=='rejected-before-effect':raise ConnectionError('accept request unavailable before service effect')
                    result=super().accept(key,request_id,merge,proof)
                    if mode in ('lost-reply-readback-down','lost-reply-readback-ok'):raise ConnectionError('lost accept response')
                    return result
                def request(api,method,path,body=None):
                    if mode=='lost-reply-readback-down' and accepting.is_set() and method=='GET' and path.startswith('/v1/attempts/'):
                        raise ConnectionError('readback unavailable')
                    return super().request(method,path,body)
            api=Client('http://127.0.0.1:'+str(server.server_port),'host1','A'*32)
            class Trees:
                current=dict(base_sha=B,head_sha=H,diff='whole approved initial diff')
                def prepare(t,project,attempt,base):return dict(path=str(root/attempt))
                def prepare_revision(t,project,attempt,base,update):
                    t.current=dict(base_sha=base,head_sha='e'*40,diff='whole corrected diff after upstream change')
                    return t.prepare(project,attempt,base)
                def prepare_review(t,project,attempt,head):return dict(path=str(root/('review-'+attempt)))
                def source(t,*args):return dict(t.current)
            trees=Trees()
            class Wire:
                serial=0
                def __init__(wire,cwd):wire.cwd=Path(cwd);wire.pending=[];wire.thread=None;wire.closed=False;wires.append(wire)
                def request(wire,method,params):
                    if method=='thread/start':
                        Wire.serial+=1;wire.thread='actual-fixture-thread-'+str(Wire.serial);return {'thread':{'id':wire.thread}}
                    if method=='turn/start':
                        turn='turn-'+str(Wire.serial)+'-'+str(len(author_threads))
                        if wire.cwd.name==second_id[0]:next_started.set();return {'turn':{'id':turn}}
                        review=wire.cwd.name.startswith('review-')
                        if review:
                            output=json.dumps(dict(verdict='approve',findings=[],head_sha=trees.current['head_sha'],base_sha=trees.current['base_sha'],reviewer_thread_id=wire.thread))
                        else:author_threads.append(params['threadId']);output='Approved implementation and checks completed'
                        wire.pending.append(dict(method='turn/completed',params=dict(threadId=wire.thread,turn=dict(id=turn,status='completed',items=[dict(type='agentMessage',text=output)]))))
                        return {'turn':{'id':turn}}
                    raise AssertionError(method)
                def notifications(wire):result=wire.pending;wire.pending=[];return result
                def close(wire):
                    if wire.cwd.name==aid and accepting.is_set() and not healthy and mode!='confirmation-write-failure' and not allow_cleanup.is_set():raise RuntimeError('owned author cleanup unconfirmed')
                    wire.closed=True
            class GitHub(Host):
                prepares=0
                def prepare_pr(host,attempt):
                    host.prepares+=1;host.pr.update(branch='codex/headless-'+aid,head_sha=attempt['head_sha'],base_sha='d'*40 if host.prepares==1 else attempt['base_sha'])
                    for check in host.checks:check['head_sha']=attempt['head_sha']
                    return super().prepare_pr(attempt)
                def verify_main(host,attempt,merge):return evidence(attempt)
            host=GitHub();delivery=Delivery(host,local,{'p':REPO});production_run=delivery.run
            if mode=='after-run-interruption':
                def interrupted(*args):
                    result=production_run(*args)
                    if result is not None:raise ConnectionError('interruption after run before local cleanup')
                    return result
                delivery.run=interrupted
            c=LifecycleConnector(local,api,trees,lambda cwd,request_handler=None:AppServer(local,transport=Wire(cwd),request_handler=request_handler),max_active_tasks=2 if unrelated_unknown else 1,delivery=delivery);cleanup.callback(c.close)
            end=time.monotonic()+8;final=None
            while time.monotonic()<end:
                c.tick();time.sleep(.005)
                final=next((d for d in local.commands() if d['command'].get('kind')=='deliver' and d['command']['attempt']['base_sha']=='d'*40),None)
                if final and final['phase'] in ('completed','needs_reconciliation') and not c.workers[aid]['busy']:break
            self.assertIsNotNone(final);self.assertEqual(len(author_threads),2);self.assertEqual(author_threads[0],author_threads[1])
            current=service.attempt(aid);self.assertEqual(current['base_sha'],'d'*40);self.assertEqual(len(current['review_threads']),2)
            self.assertEqual(host.calls.count('merge'),1);self.assertEqual(host.prepares,2);self.assertEqual(len(accept_calls),1)
            if healthy:self.assertEqual(final['phase'],'completed')
            else:self.assertEqual(final['phase'],'needs_reconciliation')
            if mode=='rejected-before-effect':self.assertEqual(h.native.rows[a['bead_id']]['status'],'in_progress')
            else:self.assertEqual(h.native.rows[a['bead_id']]['status'],'closed')
            superseded=[d for d in local.commands() if d['command'].get('kind')=='deliver' and d['command']['attempt']['base_sha']==B]
            self.assertEqual(len(superseded),1);self.assertIsNot(superseded[0].get('cleanup_confirmed'),False)
            owner=next(d['command']['command_id'] for d in local.commands() if d['command'].get('kind')=='execute' and d['command']['attempt_id']==aid)
            self.assertEqual(final['cleanup_resources'],[owner]);self.assertEqual(superseded[0]['cleanup_resources'],[owner])
            c.close();local.close()
            reopened=ConnectorStore(root/'connector','host1');cleanup.callback(reopened.close)
            b=h.claim(1);second_id[0]=b['attempt_id'];service.start_lifecycle(b['attempt_id'],'host1',M)
            # New model process and connector after real SAME-journal reopen.
            new=LifecycleConnector(reopened,api,trees,lambda cwd,request_handler=None:AppServer(reopened,transport=Wire(cwd),request_handler=request_handler),max_active_tasks=1,delivery=Delivery(host,reopened,{'p':REPO}));cleanup.callback(new.close)
            for _ in range(12):new.tick();time.sleep(.01)
            if not healthy or unrelated_unknown:
                self.assertFalse(next_started.is_set(),'lost accept/readback/cleanup must retain durable capacity across restart')
            else:self.assertTrue(next_started.is_set())
            self.assertEqual(host.calls.count('merge'),1);self.assertEqual(len(accept_calls),1)
            self.assertEqual(intents,[False],'reservation must be durable BEFORE remote acceptance effect')
            if not healthy:
                self.assertIn(aid,reopened.cleanup_reservations())
                allow_cleanup.set()
                owned=[wire for wire in wires if wire.cwd.name==aid]
                for wire in owned:wire.close()
                self.assertTrue(all(wire.closed for wire in owned))
                if mode=='confirmation-write-failure':reopened.db.execute('DROP TRIGGER fail_confirmation')
                binding=reopened.command(final['command']['command_id'])['cleanup_resources']
                reopened.confirm_cleanup(aid,set(binding))  # Explicit known-owned cleanup evidence, no PID guess/replay.
            if unrelated_unknown:
                self.assertIs(reopened.command('unrelated-fence')['cleanup_confirmed'],False)
                new.max_active_tasks=2
            end=time.monotonic()+2
            while not next_started.is_set() and time.monotonic()<end:new.tick();time.sleep(.005)
            self.assertTrue(next_started.is_set());self.assertEqual(host.calls.count('merge'),1);self.assertEqual(len(accept_calls),1)
    def test_lost_accept_reply_and_unavailable_readback_reopen_retains_slot(self):self.scenario('lost-reply-readback-down')
    def test_fault_matrix_reject_interrupt_cleanup_and_confirmation_failure(self):
        for mode in ('rejected-before-effect','after-run-interruption','cleanup-failure','confirmation-write-failure'):
            with self.subTest(mode=mode):self.scenario(mode)
    def test_supersession_same_author_new_review_success_cleanup_reopen_admits_next(self):self.scenario('success')
    def test_lost_reply_verified_readback_confirms_owned_cleanup_and_next_admission(self):self.scenario('lost-reply-readback-ok')
    def test_successful_owned_cleanup_never_clears_unrelated_unknown_resource(self):self.scenario('success',unrelated_unknown=True)


class OwnedCleanupEvidenceTests(unittest.TestCase):
    scenario=DeliveryCapacityTests.scenario
    def test_known_live_quiesce_confirms_bound_cleanup_and_reopen_admits_next(self):
        self.known_quiesce_probe=True;self.scenario('unknown-cleanup')
    def test_confirmation_cannot_clear_unmatched_resource_on_same_attempt_or_empty_proof(self):
        import tempfile
        from pathlib import Path
        from task_tower.connector.store import ConnectorStore
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        store=ConnectorStore(Path(temp.name)/'journal','owned-cleanup-proof');self.addCleanup(store.close)
        for command,resource in [('old','lost-resource'),('current','known-resource')]:
            store.receive(dict(version=1,kind='quiesce',command_id=command,attempt_id='attempt',project_id='p',base_sha=B))
            store.update(command,phase='needs_reconciliation',cleanup_confirmed=False,cleanup_resources=[resource])
        store.confirm_cleanup('attempt',set())
        self.assertIs(store.command('old')['cleanup_confirmed'],False);self.assertIs(store.command('current')['cleanup_confirmed'],False)
        store.confirm_cleanup('attempt',{'known-resource'})
        self.assertIs(store.command('old')['cleanup_confirmed'],False);self.assertIs(store.command('current')['cleanup_confirmed'],True)
        self.assertEqual(store.cleanup_reservations(),{'attempt'})
