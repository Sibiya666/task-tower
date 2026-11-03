"""Pure HTTP observation parsing; fixture JSON grants no publication authority."""
import copy
import json
import unittest
from task_tower import pr_effects


class PublicationResponseTests(unittest.TestCase):
    def setUp(self):
        self.effect=dict(kind='acceptance_review',payload=dict(commit_id='a'*40,event='COMMENT',body='Host report'))
        self.observed=dict(id=1,user=dict(login='operator'),commit_id='a'*40,state='COMMENTED',body='Host report')

    def decode(self,response):
        fn=getattr(pr_effects,'_publication_observation',None)
        self.assertTrue(callable(fn),'Missing closed publication response parser')
        return fn(self.effect,response,'operator',1024)

    def response(self,value=None,**overrides):
        return dict(dict(status=200,headers={},body=json.dumps(self.observed if value is None else value).encode()),**overrides)

    def test_exact_comment_and_status_observations_have_host_body_hash(self):
        self.assertEqual(self.decode(self.response())['status'],'confirmed')
        self.effect=dict(kind='acceptance_status',payload=dict(state='success',context='task-tower/pr-acceptance',
            description='approve receipt',target_url='https://github.com/owner/repo/pull/1'))
        status=dict(self.effect['payload'],id=2,creator=dict(login='operator'))
        self.assertEqual(self.decode(self.response(status,status=201))['remote_id'],2)

    def test_wrong_codes_redirects_duplicate_json_oversize_and_lengths_refuse(self):
        for response in (self.response(status=True),self.response(status=201),self.response(status=302),
                self.response(body=b'{"id":1,"id":2}'),self.response(body=b' '*1025),
                self.response(headers={'Content-Length':'1'}),
                self.response(headers={'Content-Length':'1','content-length':'1'}),
                self.response(body=b'[]'),self.response(body=b'\xff'),self.response(headers=[])):
            with self.subTest(response=response),self.assertRaises(ValueError): self.decode(response)

    def test_changed_actor_commit_state_body_and_boolean_id_refuse(self):
        for field,value in (('id',True),('user',dict(login='foreign')),('commit_id','b'*40),
                ('state','APPROVED'),('body','Edited response')):
            changed=copy.deepcopy(self.observed); changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): self.decode(self.response(changed))
