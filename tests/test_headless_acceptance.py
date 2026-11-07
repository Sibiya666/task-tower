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
                end=time.monotonic()+5
                while time.monotonic()<end:
                    c.tick()
                    if self.s.attempt(self.a['attempt_id'])['phase']=='accepted' and local.commands() and local.commands()[0]['phase']=='completed':break
                    time.sleep(.01)
                self.assertEqual(self.s.attempt(self.a['attempt_id'])['phase'],'accepted',errors)
                self.assertEqual(self.h.native.rows['pilot-0']['status'],'closed')
                self.assertEqual(local.commands()[0]['phase'],'completed',errors)
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
