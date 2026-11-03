"""Real private stage/review fixtures and HTTP-only controlled publication."""
import copy
import hashlib
import json
import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from task_tower import pr_effects
from task_tower.pr_policy import canonical
import test_pr_effects as gate_fixture


class _PublicationFixture:
    with_review=True
    setUpClass=classmethod(gate_fixture.PremergeGateTests.setUpClass.__func__)
    tearDownClass=classmethod(gate_fixture.PremergeGateTests.tearDownClass.__func__)
    context=gate_fixture.PremergeGateTests.context
    source=gate_fixture.PremergeGateTests.source
    current=gate_fixture.PremergeGateTests.current
    identity=gate_fixture.PremergeGateTests.identity
    fetch_transport=gate_fixture.PremergeGateTests.fetch_transport

    def publication(self,*,before_read=None,after_post=None):
        repository=self.request['repository']; number=self.request['pr_number']
        self.pr.transition(repository,number,self.owner_id,dict(state='reviewing',input_sha256=self.input_sha),
            dict(state='reviewed',pr_receipt_sha256=self.receipt['receipt_sha256'],
                reviewer_instance_id=self.receipt['reviewer_instance_id']))
        self.pr.transition(repository,number,self.owner_id,dict(state='reviewed',input_sha256=self.input_sha),
            dict(state='publishing_acceptance'))
        store=dict(posts=[],reports=[],statuses=[])
        def change(path,data,count):
            if path=='/pulls/1/reviews': return data+copy.deepcopy(store['reports'])
            if path.endswith('/statuses'): return data+copy.deepcopy(store['statuses'])
            return data
        source=self.host.source(self.ctx,change); backing=source.transport
        def transport(method,url,headers,body,timeout,max_bytes):
            if method=='POST' and url!='https://api.github.com/graphql':
                payload=json.loads(body); store['posts'].append((url,payload))
                publisher=self.fresh['task']['publisher_account']
                if url.endswith('/reviews'):
                    response=dict(id=9001,user=dict(id=8001,login=publisher),state='COMMENTED',
                        commit_id=payload['commit_id'],body=payload['body'])
                    store['reports'].append(response); code=200
                else:
                    response=dict(payload,id=9002,creator=dict(login=publisher))
                    store['statuses'].append(response); code=201
                if after_post is not None: after_post(store,response)
                return dict(status=code,headers={},body=canonical(response).encode())
            if before_read is not None: before_read(store)
            return backing(method,url,headers,body,timeout,max_bytes)
        source.transport=transport
        return pr_effects.PREffects(source,self.pr,self.fresh['task'],self.owner_id,context=self.ctx),store

    def report_intents(self):
        return [effect for effect in self.pr.effects(self.request['repository'],self.request['pr_number'])
            if effect['kind']=='acceptance_review']


class PublicationEffectsTests(_PublicationFixture,unittest.TestCase):

    def test_separate_report_status_and_repeat_are_one_write_each_without_replay(self):
        self.assertTrue(callable(getattr(pr_effects,'PREffects',None)),'Missing durable publication effects')
        repository=self.request['repository']; number=self.request['pr_number']
        self.pr.transition(repository,number,self.owner_id,dict(state='reviewing',input_sha256=self.input_sha),
            dict(state='reviewed',pr_receipt_sha256=self.receipt['receipt_sha256'],
                reviewer_instance_id=self.receipt['reviewer_instance_id']))
        self.pr.transition(repository,number,self.owner_id,dict(state='reviewed',input_sha256=self.input_sha),
            dict(state='publishing_acceptance'))
        posts=[]; reports=[]; statuses=[]
        def change(path,data,count):
            if path=='/pulls/1/reviews': return data+copy.deepcopy(reports)
            if path.endswith('/statuses'): return data+copy.deepcopy(statuses)
            return data
        source=self.host.source(self.ctx,change); backing=source.transport
        def transport(method,url,headers,body,timeout,max_bytes):
            if method=='POST' and url!='https://api.github.com/graphql':
                self.assertEqual(headers['Content-Type'],'application/json')
                payload=json.loads(body); posts.append((url,payload))
                publisher=self.fresh['task']['publisher_account']
                if url.endswith('/reviews'):
                    self.assertEqual(set(payload),{'commit_id','event','body'})
                    self.assertEqual(payload['event'],'COMMENT')
                    response=dict(id=9001,user=dict(id=8001,login=publisher),state='COMMENTED',
                        commit_id=payload['commit_id'],body=payload['body'])
                    reports.append(response); code=200
                else:
                    self.assertEqual(url,'https://api.github.com/repos/'+repository+'/statuses/'+self.request['head_sha'])
                    self.assertEqual(set(payload),{'state','context','description','target_url'})
                    response=dict(payload,id=9002,creator=dict(login=publisher))
                    statuses.append(response); code=201
                return dict(status=code,headers={},body=canonical(response).encode())
            return backing(method,url,headers,body,timeout,max_bytes)
        source.transport=transport
        # Caller annotations cannot select the authenticated publication actor;
        # the host must use the freshly loaded private task for that identity.
        supplied=dict(self.fresh['task'],publisher_account='caller-forged-annotation')
        effects=pr_effects.PREffects(source,self.pr,supplied,self.owner_id,context=self.ctx)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            first=effects.publish(self.receipt)
            self.assertEqual(first['kind'],'acceptance_review'); self.assertEqual(first['status'],'confirmed')
            self.assertEqual(len(posts),1)
            second=effects.publish(self.receipt)
            self.assertEqual(second['kind'],'acceptance_status'); self.assertEqual(second['status'],'confirmed')
            self.assertEqual(len(posts),2)
            third=effects.publish(self.receipt)
            self.assertEqual(third['effect_id'],second['effect_id']); self.assertEqual(len(posts),2)
        self.assertEqual(first['observation']['body_sha256'],hashlib.sha256(reports[0]['body'].encode()).hexdigest())


class LostPublicationTests(_PublicationFixture,unittest.TestCase):
    def test_lost_response_and_new_wrapper_never_repeat_and_inspection_survives_revocation(self):
        def lost(store,response): raise TimeoutError('Controlled lost response after remote acceptance')
        effects,store=self.publication(after_post=lost)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
            effects.publish(self.receipt)
        intent=self.report_intents()[0]; self.assertEqual(intent['status'],'unknown')
        restarted=pr_effects.PREffects(effects.source,self.pr,self.fresh['task'],self.owner_id,context=self.ctx)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
            restarted.publish(self.receipt)
        self.assertEqual(len(store['posts']),1)
        raw=self.policy.read_bytes()
        try:
            self.policy.write_bytes(raw+b' ')
            self.assertEqual(restarted.inspect_effect(intent['effect_id']),intent)
        finally: self.policy.write_bytes(raw)


class PostIntentRevocationTests(_PublicationFixture,unittest.TestCase):
    def test_actual_private_drift_after_intent_sends_nothing_and_consumes_intent(self):
        raw=self.policy.read_bytes(); changed=[]
        def revoke(store):
            if not changed and self.report_intents():
                changed.append(True); self.policy.write_bytes(raw+b' ')
        effects,store=self.publication(before_read=revoke)
        try:
            with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
                effects.publish(self.receipt)
            self.assertTrue(changed); self.assertEqual(store['posts'],[])
            self.assertEqual(self.report_intents()[0]['status'],'unknown')
        finally: self.policy.write_bytes(raw)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
            effects.publish(self.receipt)
        self.assertEqual(len(self.report_intents()),1); self.assertEqual(store['posts'],[])


class EditedPublicationTests(_PublicationFixture,unittest.TestCase):
    def test_edited_confirmed_comment_blocks_status_without_hiding_feedback(self):
        effects,store=self.publication()
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
            self.assertEqual(effects.publish(self.receipt)['status'],'confirmed')
            store['reports'][0]['body']+='Changed externally'
            with self.assertRaises(ValueError): effects.publish(self.receipt)
        self.assertEqual(len(store['posts']),1); self.assertEqual(store['statuses'],[])


class OwnerLossPublicationTests(_PublicationFixture,unittest.TestCase):
    def test_actual_owner_context_exit_after_intent_cannot_ack_or_send(self):
        stopped=[]
        def stop(store):
            if not stopped and self.report_intents():
                stopped.append(True); self.host.doCleanups()
        effects,store=self.publication(before_read=stop)
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
            effects.publish(self.receipt)
        self.assertTrue(stopped); self.assertEqual(store['posts'],[])
        self.assertEqual(self.report_intents()[0]['status'],'intent')


class DeadlinePublicationTests(_PublicationFixture,unittest.TestCase):
    def test_existing_admission_deadline_exhausted_during_second_audit_sends_nothing(self):
        clock=[]
        row=self.pr.get(self.request['repository'],self.request['pr_number'])
        expired=datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))+timedelta(seconds=1)
        def expire(store):
            if not clock and self.report_intents():
                override=patch('task_tower.pr_journal._now',return_value=expired)
                override.start(); clock.append(override)
        effects,store=self.publication(before_read=expire)
        try:
            with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),self.assertRaises(ValueError):
                effects.publish(self.receipt)
            self.assertTrue(clock); self.assertEqual(store['posts'],[])
            current=self.pr.get(self.request['repository'],self.request['pr_number'])
            self.assertEqual(current['state'],'timed_out'); self.assertEqual(current['deadline_utc'],row['deadline_utc'])
            self.assertEqual(self.report_intents()[0]['status'],'unknown')
        finally:
            for override in reversed(clock): override.stop()


class LivePrivatePublicationTests(_PublicationFixture,unittest.TestCase):
    def test_final_live_seam_reloads_raw_private_bytes_not_only_inode(self):
        effects,store=self.publication()
        payload=dict(commit_id=self.request['head_sha'],event='COMMENT',body='Host-only live-seam probe',
            receipt_sha256=self.receipt['receipt_sha256'])
        intent=self.pr.begin_effect(self.request['repository'],self.request['pr_number'],self.owner_id,
            'acceptance_review',payload)
        raw=self.policy.read_bytes(); inode=self.policy.stat().st_ino
        try:
            self.policy.write_bytes(raw+b' ')
            self.assertEqual(self.policy.stat().st_ino,inode)
            with self.assertRaises(ValueError): effects._live(intent)
            self.assertEqual(store['posts'],[])
        finally: self.policy.write_bytes(raw)
