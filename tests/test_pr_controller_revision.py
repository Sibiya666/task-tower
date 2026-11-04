"""Actual retained review and source drift; no renewed owner/task budgets."""
import json
from unittest.mock import patch
import unittest
from tests import test_pr_publication_effects as publication


class ControllerRevisionTests(publication._PublicationFixture,unittest.TestCase):
    def test_new_feedback_parks_old_acceptance_then_prepares_fresh_input(self):
        from task_tower.pr_worker import Controller,step
        effects,store=self.publication();source=effects.source
        self._tamper_old_status=False
        self._feedback_present=True
        repository=self.request['repository'];number=self.request['pr_number']
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),patch('task_tower.pr_source._fetch',side_effect=self.host.fetch_transport):
            effects.publish(self.receipt);effects.publish(self.receipt)
        original=self.pr.transition(repository,number,self.owner_id,
            dict(state='publishing_acceptance',input_sha256=self.input_sha),dict(state='accepted'))
        transport=source.transport;puts=[]
        def changed(method,url,headers,body,timeout,max_bytes):
            if method=='PUT':puts.append(url);raise AssertionError('Stale input merged')
            response=transport(method,url,headers,body,timeout,max_bytes)
            if method=='POST' and url.endswith('/reviews'):
                value=json.loads(response['body']);value['id']=9001+100*len(store['reports'])
                store['reports'][-1]['id']=value['id']
                response=dict(response,body=json.dumps(value).encode())
            if method=='POST' and '/statuses/' in url:
                value=json.loads(response['body']);value['id']=9002+len(store['statuses'])
                store['statuses'][-1]['id']=value['id']
                response=dict(response,body=json.dumps(value).encode())
            if self._feedback_present and method=='GET' and '/reviews?' in url:
                value=json.loads(response['body'])
                value.append(dict(id=100003,user=dict(id=100004,login='independent-commenter'),
                    state='COMMENTED',commit_id=self.request['head_sha'],body='Please re-check the supplied evidence.'))
                response=dict(response,body=json.dumps(value).encode())
            if self._tamper_old_status and method=='GET' and '/statuses?' in url:
                value=json.loads(response['body'])
                for status in value:
                    if status.get('id')==9002:status['description']='Changed old acknowledgment.'
                response=dict(response,body=json.dumps(value).encode())
            return response
        source.transport=changed
        controller=Controller.from_context(self.ctx,self.pr,self.owner_id,sources={repository:source})
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),patch('task_tower.pr_source._fetch',side_effect=self.host.fetch_transport):
            report=step(controller.config,self.pr,owner_id=self.owner_id)
            self.assertEqual(report['status'],'stale',report)
            self.assertEqual(puts,[])
            self.assertIsNone(self.pr.barrier(repository))
            before=len(store['posts'])
            report=step(controller.config,self.pr,owner_id=self.owner_id)
            self.assertEqual(len(store['posts'])-before,1)
            self.assertEqual(store['posts'][-1][1]['state'],'failure')
            if getattr(self,'withdraw_feedback',False):self._feedback_present=False
            fresh=self.ctx.current(source,self.fresh['task'])
            self.assertIsNone(fresh['authority_error'])
            self.assertTrue(fresh['snapshot']['ready'])
            report=step(controller.config,self.pr,owner_id=self.owner_id)
            if getattr(self,'withdraw_feedback',False):
                self.assertEqual((report['status'],report['action']),('stale','none'))
                unchanged=self.pr.get(repository,number)
                self.assertEqual(unchanged['input_sha256'],original['input_sha256'])
                self.assertEqual(unchanged['review_attempts'],original['review_attempts'])
                self.assertEqual(unchanged['deadline_utc'],original['deadline_utc'])
                return
        self.assertEqual(report['action'],'prepared',report)
        revised=self.pr.get(repository,number)
        self.assertNotEqual(revised['input_sha256'],original['input_sha256'])
        for key in ('admitted_utc','deadline_utc','task_timeout_seconds','max_review_attempts','review_attempts','owner_id','owner_pid'):
            self.assertEqual(revised[key],original[key])
        self.assertEqual(revised['state'],'discovered')
        self.assertEqual(puts,[])
        if getattr(self,'tamper_prior_status',False):
            self._tamper_old_status=True
            from task_tower import pr_review
            with patch('task_tower.pr_review.run_command',wraps=pr_review.run_command) as launches,patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
                report=step(controller.config,self.pr,owner_id=self.owner_id)
            self.assertEqual(launches.call_count,0)
            self.assertEqual(report['status'],'discovered')
            self.assertEqual(self.pr.get(repository,number)['review_attempts'],original['review_attempts'])
            return
        with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport),patch('task_tower.pr_source._fetch',side_effect=self.host.fetch_transport):
            report=step(controller.config,self.pr,owner_id=self.owner_id)
            self.assertEqual(report['status'],'reviewed',report)
            for _ in range(2):
                before=len(store['posts'])
                report=step(controller.config,self.pr,owner_id=self.owner_id)
                self.assertEqual(len(store['posts'])-before,1,report)
        self.assertEqual(report['status'],'accepted',report)
        self.assertEqual(self.pr.get(repository,number)['review_attempts'],original['review_attempts']+1)
        self.assertEqual(puts,[])


class ChangedPriorPublicationRevisionTests(ControllerRevisionTests):
    tamper_prior_status=True


class UnchangedSourceRevisionTests(ControllerRevisionTests):
    withdraw_feedback=True
