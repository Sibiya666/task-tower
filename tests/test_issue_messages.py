import json
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from task_tower.connector.issue_messages import IssueMessenger

SOURCE=dict(repository="owner/repo",repository_id=9,issue_number=12,reporter_id=21)
class Host:
    def __init__(self): self.comments=[]; self.posts=0; self.closes=0; self.lost=False; self.visible=True; self.closed=False
    def _creator(self): return 11
    def _pages(self,r,path): return self.comments if self.visible else []
    def _request(self,r,method,path,payload=None):
        if path=="/": return dict(id=9)
        if method=="GET": return dict(number=12,user=dict(id=21),state="closed" if self.closed else "open",html_url="https://github.com/owner/repo/issues/12")
        if path.endswith("/comments"):
            self.posts+=1; row=dict(id=44,body=payload["body"],user=dict(id=11,type="Bot"),html_url="https://github.com/owner/repo/issues/12#issuecomment-44"); self.comments.append(row)
            if self.lost: raise TimeoutError()
            return row
        self.closes+=1; self.closed=True
        if self.lost: raise TimeoutError()
        return dict(state="closed")
class MessageTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:"); self.addCleanup(self.db.close)
        self.host=Host(); self.store=SimpleNamespace(db=self.db,lock=threading.RLock())
        self.m=IssueMessenger(self.host,self.store,SOURCE)
    def test_duplicate_comment_has_one_remote_effect(self):
        a=self.m.ensure_comment("clarification",12,"Please provide reproduction steps.")
        self.assertEqual(self.m.ensure_comment("clarification",12,"Please provide reproduction steps."),a)
        self.assertEqual(self.host.posts,1)
        self.assertNotIn("clarification",self.host.comments[0]["body"].split("<!--")[1])
    def test_lost_response_uses_factual_bot_readback(self):
        self.host.lost=True
        self.assertEqual(self.m.ensure_comment("x",12,"Details needed")["comment_id"],44)
        self.assertEqual(self.host.posts,1)
    def test_unknown_comment_is_fenced_across_new_messenger(self):
        self.host.lost=True; self.host.visible=False
        with self.assertRaises(ValueError): self.m.ensure_comment("x",12,"Details needed")
        m=IssueMessenger(self.host,self.store,SOURCE)
        with self.assertRaises(ValueError): m.ensure_comment("x",12,"Details needed")
        self.assertEqual(self.host.posts,1)
    def test_effect_content_conflict_does_not_post_twice(self):
        self.m.ensure_comment("x",12,"first")
        with self.assertRaises(ValueError): self.m.ensure_comment("x",12,"second")
        self.assertEqual(self.host.posts,1)
    def test_wrong_issue_or_repository_has_no_public_effect(self):
        with self.assertRaises(ValueError): self.m.ensure_comment("x",13,"details")
        self.host._request=lambda *a: dict(id=999)
        with self.assertRaises(ValueError): self.m.ensure_comment("x",12,"details")
        self.assertEqual(self.host.posts,0)
    def test_issue_closure_requires_canonical_acceptance_and_lost_reply_readback(self):
        with self.assertRaises(ValueError): self.m.finalize_issue(dict(phase="postmerge"),"done")
        self.assertEqual(self.host.closes,0)
        a=dict(phase="accepted",canonical_close=dict(history_verified=True),accepted_evidence=dict(kind="runtime.acceptance"),repository="owner/repo",source_issue=SOURCE,main_sha="a"*40)
        self.host.lost=True
        receipt=self.m.finalize_issue(a,"done")
        self.assertEqual(receipt["state"],"closed")
        self.assertEqual(self.m.finalize_issue(a,"done"),receipt)
        self.assertEqual(self.host.closes,1)
