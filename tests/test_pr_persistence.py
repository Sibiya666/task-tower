"""Actual controller intake persists a real private preparation before review."""
import importlib.util
import copy
import json
import sys
from pathlib import Path
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
import test_pr_context_current as fixture
from task_tower.pr_journal import PRJournal


class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=fixture.installed_load
        def install(f):
            if getattr(cls,'pr_verdict',None):
                script=f.root/'controller-reviewer.py'
                script.write_text("import argparse,json,pathlib,os\np=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args();r=json.loads(pathlib.Path(a.request).read_text())\nassert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)\nv={k:r[k] for k in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')}\nv.update(verdict="+repr(cls.pr_verdict)+",summary='Actual controller reviewer fixture.',findings=[],whole_diff_reviewed=True)\n"+("pathlib.Path('unexpected-review-write.txt').write_text('changed')\n" if getattr(cls,'mutate_checkout',False) else '')+"pathlib.Path(a.result).write_text(json.dumps(v))\n",encoding='utf-8')
                profile=copy.deepcopy(f.profile);profile.update(argv=[str(Path(sys.executable).resolve()),str(script)],max_attempts=1,runs_dir=str(f.root/'controller-review-runs'))
                f.executor['profiles']['controller-review']=profile
            return original(f)
        with patch.object(fixture,'installed_load',install):fixture.CurrentAuthorityTests.setUpClass.__func__(cls)
    tearDownClass=classmethod(fixture.CurrentAuthorityTests.tearDownClass.__func__)
    def context(self):
        if getattr(self,'pr_verdict',None):
            value=json.loads(self.policy.read_text());value['projects'][0]['tasks'][0]['reviewer_profile']='controller-review'
            self.policy.write_text(json.dumps(value),encoding='utf-8')
        return fixture.CurrentAuthorityTests.context(self)
    source=fixture.CurrentAuthorityTests.source
    current=fixture.CurrentAuthorityTests.current
    identity=fixture.CurrentAuthorityTests.identity
    fetch_transport=fixture.CurrentAuthorityTests.fetch_transport

    def test_actual_intake_persists_genuine_record_before_any_role_intent(self):
        self.assertIsNotNone(importlib.util.find_spec('task_tower.pr_persistence'),'Missing actual intake persistence')
        from task_tower.pr_persistence import prepare_admission
        journal=PRJournal(self.journal);owner=str(uuid.uuid4())
        with journal.owner(owner):
            ctx=self.context();source=self.source(ctx)
            with patch('task_tower.pr_context._fetch',side_effect=self.fetch_transport),patch('task_tower.pr_source._fetch',side_effect=self.fetch_transport):
                prepared=prepare_admission(ctx,source,journal,self.identity())
            row=journal.get('owner/repo',7)
            self.assertEqual(row['state'],'discovered');self.assertEqual(row['review_attempts'],0)
            self.assertEqual(journal.effects('owner/repo',7),[])
            record=ctx.prepared_record(row['input_sha256'])
            self.assertEqual(record['request'],prepared['request'])
            self.assertEqual(record['private_input_provenance'],ctx.private_input_provenance)
            from task_tower import pr_persistence
            self.assertTrue(callable(getattr(pr_persistence,'run_review',None)),'Missing actual review persistence')
            with patch('task_tower.pr_context._fetch',side_effect=self.fetch_transport):
                if getattr(self,'mutate_checkout',False):
                    with self.assertRaises(ValueError):pr_persistence.run_review(ctx,source,journal,self.identity(),owner)
                    effects=journal.effects('owner/repo',7);self.assertEqual(len(effects),1)
                    self.assertEqual(effects[0]['status'],'unknown')
                    namespace=Path(ctx.private_input_provenance['artifact_namespace'])
                    raw=json.loads((namespace/'unverified-records'/(effects[0]['effect_id']+'.json')).read_text())
                    self.assertEqual(raw['envelope']['result']['verdict'],'approve')
                    with self.assertRaises(ValueError):ctx.review_record(row['input_sha256'])
                    with self.assertRaises(ValueError):pr_persistence.run_review(ctx,source,journal,self.identity(),owner)
                    self.assertEqual(journal.get('owner/repo',7)['review_attempts'],1)
                    return
                first=pr_persistence.run_review(ctx,source,journal,self.identity(),owner)
                repeat=pr_persistence.run_review(ctx,source,journal,self.identity(),owner)
            # The actual installed fixture primary harness implements pipeline
            # ABI, not PR ABI. Its real process fails cleanly; never invent a
            # successful review or relaunch it under a new effect.
            expected='confirmed' if getattr(self,'pr_verdict',None) else 'failed'
            self.assertEqual(first['status'],expected);self.assertEqual(first['effect_id'],repeat['effect_id'])
            saved=ctx.review_record(row['input_sha256']) if expected=='confirmed' else ctx.failure_record(row['input_sha256'])
            self.assertTrue(saved['envelope']['process']['started'])
            self.assertEqual(saved['review_effect_id'],first['effect_id'])
            self.assertEqual(journal.get('owner/repo',7)['review_attempts'],1)
            if expected=='confirmed':
                self.assertIsNotNone(importlib.util.find_spec('task_tower.pr_worker'),'Missing real PR controller')
                from task_tower.pr_worker import Controller,step
                from test_pr_diagnostic_effects import diagnostic
                effects,store=diagnostic(SimpleNamespace(host=self,ctx=ctx,pr=journal,request=prepared['request']),owner)
                controller=Controller.from_context(ctx,journal,owner,sources={'owner/repo':effects.source})
                with patch('task_tower.pr_context._fetch',side_effect=self.fetch_transport):
                    for _ in range(5):
                        before=len(store['posts'])
                        step(controller.config,journal,owner_id=owner)
                        self.assertLessEqual(len(store['posts'])-before,1)
                self.assertEqual(journal.get('owner/repo',7)['state'],'accepted')
                self.assertEqual(len(store['posts']),2)
                self.assertFalse(any(payload.get('state')=='pending' for _,payload in store['posts']))
                self.assertIsNone(journal.barrier('owner/repo'))  # actual private merge policy is false
                self.assertEqual(journal.get('owner/repo',7)['review_attempts'],1)


class SuccessfulPersistenceTests(PersistenceTests):
    pr_verdict='approve'


class MutatingPersistenceTests(PersistenceTests):
    pr_verdict='approve'
    mutate_checkout=True
