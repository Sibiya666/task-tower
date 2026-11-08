"""Explicit project boundaries; model output cannot select delivery authority."""
import copy
import tempfile
import threading
import unittest
from pathlib import Path


class PolicyTests(unittest.TestCase):
    def test_explicit_modes_and_git_branch_restrictions(self):
        from task_tower.delivery_policy import policies
        configured={'p':dict(mode='owner_pr',repository='owner/project',base='codex/veyra-rpg')}
        self.assertEqual(policies({'p'}, {}, configured),configured)
        for base in ('--upload-pack=x','a..b','main.lock','test\nmain','refs/heads/test','a@{b'):
            with self.subTest(base=base), self.assertRaises(ValueError):
                policies({'p'}, {}, {'p':dict(mode='owner_pr',repository='owner/project',base=base)})
        with self.assertRaises(ValueError):policies({'p'}, {}, {'other':dict(mode='local')})
        with self.assertRaises(ValueError):policies({'p'}, {}, {'p':dict(mode='local',repository='owner/project')})

    def test_local_saved_result_never_calls_github_and_restart_cannot_expand_policy(self):
        from task_tower.connector.handoff import HandoffDelivery
        from task_tower.connector.store import ConnectorStore
        from tests.test_headless_delivery import attempt
        a=attempt();a['delivery_policy']={'mode':'local'}
        command=dict(command_id='deliver',attempt_id=a['attempt_id'],project_id='p',attempt=a)
        class Trees:
            def source(self,*args):return copy.deepcopy(a['source'])
        with tempfile.TemporaryDirectory() as temp:
            store=ConnectorStore(Path(temp)/'journal','host')
            try:
                delivery=HandoffDelivery(None,store,Trees(),{'p':{'mode':'local'}})
                result=delivery.run(command,None,threading.Event())
                self.assertEqual(result['phase'],'handoff')
                self.assertEqual(result['receipt'],dict(kind='reviewed.local',head_sha='b'*40,base_sha='a'*40,policy={'mode':'local'}))
                self.assertEqual(delivery.run(command,None,threading.Event()),result)
                expanded=HandoffDelivery(None,store,Trees(),{'p':dict(mode='owner_pr',repository='owner/project',base='test')})
                with self.assertRaises(ValueError):expanded.run(command,None,threading.Event())
            finally:store.close()

    def test_owner_pr_base_is_exact_and_merge_is_never_called(self):
        from task_tower.connector.handoff import HandoffDelivery
        from task_tower.connector.store import ConnectorStore
        from tests.test_headless_delivery import attempt
        policy=dict(mode='owner_pr',repository='owner/project',base='test')
        a=attempt();a['delivery_policy']=policy
        command=dict(command_id='deliver',attempt_id=a['attempt_id'],project_id='p',attempt=a)
        class Trees:
            def source(self,*args):return copy.deepcopy(a['source'])
        class Host:
            def prepare_pr(self,value,*,base_ref):
                if base_ref!='test':raise AssertionError('wrong PR base')
                return dict(repository='owner/project',number=12,head_repository='owner/project',head_sha='b'*40,
                            base_sha='a'*40,base_ref='test',branch='codex/headless-attempt',state='open',merged=False)
            def merge(self,*args):raise AssertionError('owner-only merge boundary violated')
        with tempfile.TemporaryDirectory() as temp:
            store=ConnectorStore(Path(temp)/'journal','host')
            try:
                result=HandoffDelivery(Host(),store,Trees(),{'p':policy}).run(command,None,threading.Event())
                self.assertEqual(result['receipt']['pr_number'],12)
                self.assertEqual(result['receipt']['policy'],policy)
                self.assertNotIn('canonical_close',result)
            finally:store.close()

    def test_saved_result_releases_capacity_without_native_close(self):
        from tests.test_service_lifecycle import LifecycleTests,SOURCE
        fixture=LifecycleTests();fixture.setUp()
        try:
            fixture.s.delivery_policies={'p':{'mode':'local'}}
            a=fixture.start();fixture.complete(a,'author',source=SOURCE)
            fixture.complete(a,'review',fixture.verdict('review','approve'))
            c=fixture.commands(a)[-1]
            receipt=dict(kind='reviewed.local',head_sha='b'*40,base_sha='a'*40,policy={'mode':'local'})
            result=fixture.emit(a,'saved_result',command_id=c['command_id'],receipt=receipt)
            self.assertEqual((result['phase'],result['quiescent']),('handoff',True))
            self.assertEqual(fixture.s.active_count('host1'),0)
            self.assertEqual(fixture.native.rows['pilot-0']['status'],'in_progress')
            self.assertFalse(any('close' in c for c in fixture.native.calls))
        finally:fixture.doCleanups()

    def test_real_http_local_review_saves_result_and_confirms_owned_cleanup(self):
        from tests.test_headless_e2e import HeadlessE2ETests
        from task_tower.connector.handoff import HandoffDelivery
        fixture=HeadlessE2ETests();fixture.setUp()
        try:
            fixture.service.delivery_policies={'p':{'mode':'local'}}
            fixture.connector.delivery=HandoffDelivery(None,fixture.local,fixture.trees,{'p':{'mode':'local'}})
            a=fixture.start(0)
            fixture.until(lambda:fixture.service.attempt(a['attempt_id'])['phase']=='handoff')
            final=fixture.service.attempt(a['attempt_id'])
            self.assertEqual(final['saved_result']['kind'],'reviewed.local')
            self.assertNotEqual(final['author_thread_id'],final['review']['reviewer_thread_id'])
            self.assertEqual(fixture.native.rows['pilot-0']['status'],'in_progress')
            self.assertTrue(all(w.closed for w in fixture.wires))
            self.assertEqual(fixture.local.cleanup_reservations(),set())
            self.assertEqual(fixture.service.active_count('e2e'),0)
        finally:fixture.doCleanups()

    def test_policy_change_after_claim_fences_dispatch_before_model_command(self):
        from tests.test_service_lifecycle import LifecycleTests,BASE
        from task_tower.service.beads import ServiceError
        fixture=LifecycleTests();fixture.setUp()
        try:
            fixture.s.delivery_policies={'p':{'mode':'local'}}
            a=fixture.claim()
            fixture.s.delivery_policies={'p':dict(mode='owner_pr',repository='owner/project',base='test')}
            with self.assertRaises(ServiceError):fixture.s.start_lifecycle(a['attempt_id'],'host1',BASE)
            self.assertEqual(fixture.commands(a),[])
        finally:fixture.doCleanups()

    def test_real_host_uses_configured_owner_pr_base_for_lookup_and_creation(self):
        from task_tower.connector.delivery import GitHubHost
        from tests.test_headless_delivery import attempt
        calls=[];a=attempt()
        class Trees:
            def prepare(self,*args):return dict(path='fixture',branch='codex/headless-attempt')
            def source(self,*args):return copy.deepcopy(a['source'])
        class Host(GitHubHost):
            def _remote(self,*args,**kwargs):pass
            def _push(self,*args,**kwargs):pass
            def _pages(self,r,path,key=None):calls.append(path);return []
            def _request(self,r,method,path,payload=None):calls.append(payload);return {'number':12}
            def read_pr(self,*args):return {'number':12}
        host=Host(Trees(),None,{'p':'owner/project'},token='fixture')
        host.prepare_pr(a,base_ref='codex/veyra-rpg')
        self.assertTrue(calls[0].endswith('&base=codex%2Fveyra-rpg'))
        self.assertEqual(calls[1]['base'],'codex/veyra-rpg')
