"""Pure asynchronous response consistency, never merge authority/completion."""
import copy
import json
import unittest
from task_tower import pr_effects


class MergeResponseTests(unittest.TestCase):
    def setUp(self):
        self.effect=dict(kind='merge',binding=dict(head_sha='a'*40),payload=dict(sha='a'*40,
            merge_method='merge',merge_action='direct_merge',bypass_rules=False))
        self.uuid='630b9d5e-3f2a-4f7e-8b0c-2d5f9a8c1e42'
        self.pending=dict(status='pending',details=dict(message='Merge request enqueued.',uuid=self.uuid,
            merge_method='merge',merge_action='direct_merge',expected_head_sha='a'*40))

    def response(self,value=None,*,status=202):
        return dict(status=status,headers={},body=json.dumps(self.pending if value is None else value).encode())

    def parse(self,response):
        fn=getattr(pr_effects,'_merge_response',None)
        self.assertTrue(callable(fn),'Missing strict asynchronous merge response parser')
        return fn(self.effect,response,4096)

    def test_202_records_only_uuid_and_unknown_so_immutable_pending_result_cannot_block_completion(self):
        before=copy.deepcopy(self.pending)
        self.assertEqual(self.parse(self.response()),dict(status='unknown',request_uuid=self.uuid))
        self.assertEqual(before,self.pending); self.assertNotIn('bypass_rules',self.pending['details'])
        explicit=copy.deepcopy(self.pending); explicit['details']['bypass_rules']=False
        self.assertEqual(self.parse(self.response(explicit)),dict(status='unknown',request_uuid=self.uuid))

    def test_200_merged_and_enqueued_remain_unconfirmed(self):
        merged=dict(status='merged',details=dict(message='Already merged.',sha='c'*40))
        self.assertEqual(self.parse(self.response(merged,status=200)),dict(status='unknown',merge_commit='c'*40))
        queue=dict(status='enqueued',details=dict(message='Already enqueued.'))
        self.assertEqual(self.parse(self.response(queue,status=200)),dict(status='unknown',result='enqueued'))

    def test_wrong_pending_options_head_bypass_uuid_or_extra_fields_refuse(self):
        for field,value in (('uuid','not-uuid'),('merge_method','squash'),('merge_action','default'),
                ('expected_head_sha','b'*40),('bypass_rules',True),('bypass_rules',0),('bypass_rules',None),('extra',True)):
            changed=copy.deepcopy(self.pending); changed['details'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError): self.parse(self.response(changed))

    def test_lost_409_redirect_invalid_json_size_and_wrong_state_refuse(self):
        bad=[self.response(status=409),self.response(status=302),self.response(status=True),
            dict(status=202,headers={},body=b'{"status":"pending","status":"merged"}'),
            dict(status=202,headers={},body=b' '*4097),self.response(dict(status='merged',details=dict(message='x',sha='c'*40))),
            self.response(status=200)]
        for response in bad:
            with self.subTest(response=response),self.assertRaises(ValueError): self.parse(response)

    def test_parser_cannot_accept_non_explicit_false_or_foreign_saved_intent(self):
        for change in (dict(bypass_rules=True),dict(bypass_rules=0),dict(sha='b'*40),dict(merge_action='default')):
            self.effect['payload']=dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False)
            self.effect['payload'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError): self.parse(self.response())
