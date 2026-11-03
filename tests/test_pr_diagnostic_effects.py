"""Explicit diagnostic writes through genuine preparation and HTTP-only fixtures."""
import copy
import json
import unittest
import uuid
from unittest.mock import patch
import test_pr_retained_records as fixtures
from task_tower.pr_effects import PREffects
from task_tower.pr_policy import canonical


def diagnostic(f,owner):
    store=dict(posts=[],statuses=[],reports=[])
    def change(path,data,count):
        if path.endswith('/statuses'):return data+copy.deepcopy(store['statuses'])
        if path=='/pulls/1/reviews':return data+copy.deepcopy(store['reports'])
        if path=='/pulls/1' and store.get('changed_title'):
            data=copy.deepcopy(data);data['title']='Actual changed PR title'
        return data
    source=f.host.source(f.ctx,change);backing=source.transport
    def transport(method,url,headers,body,timeout,max_bytes):
        if method=='POST' and url!='https://api.github.com/graphql':
            payload=json.loads(body);store['posts'].append((url,payload))
            if url.endswith('/reviews'):
                response=dict(id=9901,user=dict(id=8001,login='owner'),state='COMMENTED',commit_id=payload['commit_id'],body=payload['body'])
                store['reports'].append(response);code=200
            else:
                if not url.endswith('/statuses/'+f.request['head_sha']):raise AssertionError('Unexpected diagnostic endpoint')
                response=dict(payload,id=9902,creator=dict(login='owner'));store['statuses'].append(response);code=201
            if store.get('lose_response'):raise TimeoutError('Lost actual transport acknowledgement')
            return dict(status=code,headers={},body=canonical(response).encode())
        return backing(method,url,headers,body,timeout,max_bytes)
    source.transport=transport
    return PREffects(source,f.pr,f.host.identity(),owner,context=f.ctx),store


class PendingEffectsTests(unittest.TestCase):
    with_review=False
    setUpClass=classmethod(fixtures.PreparedRecordTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PreparedRecordTests.tearDownClass.__func__)
    context=fixtures.PreparedRecordTests.context
    source=fixtures.PreparedRecordTests.source
    current=fixtures.PreparedRecordTests.current
    identity=fixtures.PreparedRecordTests.identity
    fetch_transport=fixtures.PreparedRecordTests.fetch_transport

    def test_explicit_pending_uses_input_hash_once_without_a_review_receipt(self):
        self.assertTrue(callable(getattr(PREffects,'publish_pending',None)),'Missing explicit pending')
        owner=str(uuid.uuid4())
        with self.pr.owner(owner):
            self.pr.transition(self.request['repository'],self.request['pr_number'],owner,
                dict(state='discovered',input_sha256=self.input_sha),dict(state='validating'))
            effects,store=diagnostic(self,owner)
            with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
                first=effects.publish_pending();second=effects.publish_pending()
            self.assertEqual(first['status'],'confirmed');self.assertEqual(first['effect_id'],second['effect_id'])
            self.assertEqual(first['payload']['receipt_sha256'],self.input_sha)
            self.assertEqual(store['posts'][0][1]['state'],'pending');self.assertEqual(len(store['posts']),1)
            self.assertEqual(self.pr.get(self.request['repository'],self.request['pr_number'])['review_attempts'],0)
            # Genuine current stale source permits old-head invalidation, but
            # a lost response consumes that distinct failure phase forever.
            store.update(changed_title=True,lose_response=True)
            with patch('task_tower.pr_context._fetch',side_effect=self.host.fetch_transport):
                with self.assertRaises(ValueError):effects.publish_failure()
                with self.assertRaises(ValueError):effects.publish_failure()
            self.assertEqual(len(store['posts']),2)
            self.assertEqual(store['posts'][-1][1]['state'],'failure')
