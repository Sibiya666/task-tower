"""Actual private stage/review/publication history; HTTP-only merge fixture."""
import copy
import json
import unittest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import patch
from task_tower import pr_effects
from task_tower.pr_policy import canonical
import test_pr_publication_effects as publication_fixture
import test_pr_effects as gate_fixture


class AsyncMergeEffectsTests(publication_fixture._PublicationFixture,unittest.TestCase):
    def test_single_async_put_pending_then_exact_fact_keeps_main_barrier(self):
        self.assertTrue(callable(getattr(pr_effects.PREffects,'request_merge',None)),'Missing durable async merge')
        self.assertTrue(callable(getattr(pr_effects.PREffects,'observe_merge',None)),'Missing readonly merge proof')
        effects,store=self.publication(); source=effects.source; backing=source.transport
        done=[]; fault=[]; puts=[]; merge='c'*40; request_uuid='630b9d5e-3f2a-4f7e-8b0c-2d5f9a8c1e42'
        pending=dict(status='pending',details=dict(message='Merge request enqueued.',uuid=request_uuid,
            merge_method='merge',merge_action='direct_merge',expected_head_sha=self.request['head_sha']))
        repository=self.request['repository']; number=self.request['pr_number']
        prefix='https://api.github.com/repos/'+repository
        def transport(method,url,headers,body,timeout,max_bytes):
            if method=='PUT':
                self.assertEqual(url,prefix+'/pulls/'+str(number)+'/merge-async')
                payload=json.loads(body)
                self.assertEqual(payload,dict(sha=self.request['head_sha'],merge_method='merge',merge_action='direct_merge',bypass_rules=False))
                puts.append(payload); code=202; value=pending
            elif method=='GET' and url==prefix+'/pulls/'+str(number)+'/merge-async/'+request_uuid:
                code=200; value=dict(status='merged',details=dict(message='Merged.',sha=merge)) if done else pending
            elif done and method=='GET' and url==prefix+'/pulls/'+str(number):
                value=copy.deepcopy(self.fresh['snapshot']['pr'])
                value.update(state='closed',merged=True,merge_commit_sha=merge,
                    merged_by=dict(login=self.fresh['task']['publisher_account']),mergeable=None,mergeable_state='unknown')
                value['base']['sha']=merge; code=200
                if fault==['actor']: value['merged_by']['login']='foreign'
                if fault==['marker']: value['body']='Task-Tower: TT-FOREIGN-001'
                if fault==['title']: value['title']='Edited after merge'
                if fault==['head']: value['head']['sha']='d'*40
            elif done and method=='GET' and url==prefix+'/git/commits/'+merge:
                value=dict(sha=merge,parents=[dict(sha=self.request['base_sha']),dict(sha=self.request['head_sha'])]); code=200
                if fault==['parents']: value['parents'][0]['sha']='d'*40
            elif done and method=='GET' and url==prefix+'/git/ref/heads/main':
                value=dict(object=dict(sha=merge)); code=200
                if fault==['main']: value['object']['sha']='d'*40
            else: return backing(method,url,headers,body,timeout,max_bytes)
            return dict(status=code,headers={},body=canonical(value).encode())
        source.transport=transport
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            effects.publish(self.receipt); effects.publish(self.receipt)
            self.pr.transition(repository,number,self.owner_id,dict(state='publishing_acceptance',input_sha256=self.input_sha),
                dict(state='accepted'))
            first=effects.request_merge(self.receipt)
            self.assertEqual(first['observation'],dict(status='unknown',request_uuid=request_uuid))
            self.assertEqual(self.pr.get(repository,number)['state'],'merge_pending')
            self.assertEqual(effects.request_merge(self.receipt)['effect_id'],first['effect_id'])
            self.assertEqual(effects.observe_merge()['status'],'unknown'); self.assertEqual(len(puts),1)
            original_path=self.pr.path; foreign=original_path.with_name('foreign-merge-fact.sqlite')
            foreign.write_bytes(original_path.read_bytes())
            try:
                self.pr.path=foreign
                with self.assertRaises(ValueError): effects._observe_live(first)
            finally: self.pr.path=original_path
            done.append(True)
            for mutation in ('parents','actor','main','marker','title','head'):
                fault[:]=[mutation]
                with self.subTest(mutation=mutation),self.assertRaises(ValueError): effects.observe_merge()
                self.assertEqual(self.pr.get(repository,number)['state'],'merge_pending')
                self.assertEqual(len(puts),1)
            fault.clear()
            confirmed=effects.observe_merge()
            self.assertEqual(confirmed['status'],'confirmed')
            self.assertEqual(confirmed['observation']['parents'],[self.request['base_sha'],self.request['head_sha']])
            self.assertEqual(self.pr.get(repository,number)['state'],'awaiting_main')
            self.assertFalse(self.pr.barrier(repository)['completed'])
            self.assertEqual(effects.request_merge(self.receipt)['effect_id'],first['effect_id'])
            self.assertEqual(len(puts),1); self.assertEqual(len(store['posts']),2)


class DisabledMergeEffectsTests(publication_fixture._PublicationFixture,unittest.TestCase):
    def context(self):
        value=json.loads(self.policy.read_text(encoding='utf-8'))
        value['projects'][0]['merge_enabled']=False; value['projects'][0]['exclusive_writer']['enabled']=False
        self.policy.write_text(json.dumps(value),encoding='utf-8')
        return gate_fixture.record_fixtures.PreparedRecordTests.context(self)

    def test_caller_flags_cannot_grant_merge_or_acquire_barrier_when_private_policy_disables_it(self):
        self.assertTrue(callable(getattr(pr_effects.PREffects,'request_merge',None)),'Missing actual private merge gate')
        effects,store=self.publication(); effects.task['merge_enabled']=True; effects.task['exclusive_writer']['enabled']=True
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            effects.publish(self.receipt); effects.publish(self.receipt)
            repository=self.request['repository']; number=self.request['pr_number']
            self.pr.transition(repository,number,self.owner_id,dict(state='publishing_acceptance',input_sha256=self.input_sha),
                dict(state='accepted'))
            with self.assertRaises(ValueError): effects.request_merge(self.receipt)
        self.assertIsNone(self.pr.barrier(repository)); self.assertEqual(len(store['posts']),2)
        self.assertFalse(any(effect['kind']=='merge' for effect in self.pr.effects(repository,number)))


class LateFactDeadlineTests(publication_fixture._PublicationFixture,unittest.TestCase):
    def test_deadline_expires_during_final_real_private_reload_and_never_advances_fact(self):
        effects,store=self.publication(); backing=effects.source.transport; puts=[]
        uuid='630b9d5e-3f2a-4f7e-8b0c-2d5f9a8c1e42'
        def transport(method,url,headers,body,timeout,max_bytes):
            if method=='PUT':
                puts.append(url)
                value=dict(status='pending',details=dict(message='Pending.',uuid=uuid,merge_method='merge',
                    merge_action='direct_merge',expected_head_sha=self.request['head_sha']))
                return dict(status=202,headers={},body=canonical(value).encode())
            return backing(method,url,headers,body,timeout,max_bytes)
        effects.source.transport=transport
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            effects.publish(self.receipt); effects.publish(self.receipt)
            repository=self.request['repository']; number=self.request['pr_number']
            self.pr.transition(repository,number,self.owner_id,dict(state='publishing_acceptance',input_sha256=self.input_sha),dict(state='accepted'))
            effect=effects.request_merge(self.receipt)
        row=self.pr.get(repository,number)
        expired=datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))+timedelta(seconds=1)
        real=effects.context._fresh_inputs; calls=[]; overrides=[]
        def load_actual_then_clock_fault():
            value=real(); calls.append(True)
            if len(calls)==2:
                overrides.extend([patch('task_tower.pr_journal._now',return_value=expired),
                    patch('task_tower.pr_effects.datetime',SimpleNamespace(now=lambda tz:expired,fromisoformat=datetime.fromisoformat))])
                for override in overrides: override.start()
            return value
        try:
            # Every returned authority value is from the real loader; this
            # fault changes only the clock after its second completed read.
            with patch.object(effects.context,'_fresh_inputs',side_effect=load_actual_then_clock_fault),self.assertRaises(ValueError):
                effects._observe_live(effect)
            self.assertEqual(self.pr.get(repository,number)['state'],'timed_out')
            self.assertEqual(self.pr.get(repository,number)['deadline_utc'],row['deadline_utc'])
            self.assertEqual(len(puts),1); self.assertFalse(self.pr.barrier(repository)['completed'])
        finally:
            for override in reversed(overrides): override.stop()
