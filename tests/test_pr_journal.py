"""Real SQLite and OS ownership tests for single-use durable effects."""
import copy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from task_tower.pr_journal import PRJournal


def binding(repository='owner/repo',pr=44):
    return dict(repository=repository,issue=17,issue_id=1017,task_id='TT-PR-001',pr_number=pr,
        head_sha='a'*40,base_sha='b'*40,input_sha256='c'*64,policy_sha256='d'*64,task_timeout_seconds=60)


def finished_process():
    child=subprocess.Popen([sys.executable,'-c','pass'])
    return dict(pid=child.pid,exit_code=child.wait(),started=True,cleanup_confirmed=True)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'pr.sqlite3'; self.j=PRJournal(self.path)
        self.owner=str(uuid.uuid4())

    def advance(self,state):
        row=self.j.get('owner/repo',44)
        return self.j.transition('owner/repo',44,self.owner,
            dict(state=row['state'],input_sha256=row['input_sha256']),dict(state=state))

    def ready(self,repository='owner/repo',pr_number=44,admission=None):
        admission=binding(repository,pr_number) if admission is None else admission
        self.j.admit(admission)
        def step(state,**extra):
            row=self.j.get(repository,pr_number)
            return self.j.transition(repository,pr_number,self.owner,
                dict(state=row['state'],input_sha256=admission['input_sha256']),dict(state=state,**extra))
        step('validating'); step('reviewing')
        reviewer=str(uuid.uuid4())
        role=self.j.begin_effect(repository,pr_number,self.owner,'pr_review',
            dict(reviewer_instance_id=reviewer,request_sha256=admission['input_sha256']))
        self.j.observe(role['effect_id'],self.owner,dict(status='confirmed',result_sha256='1'*64,
            receipt_sha256='4'*64,reviewer_instance_id=reviewer,process=finished_process()))
        step('reviewed',pr_receipt_sha256='4'*64,reviewer_instance_id=reviewer)
        step('publishing_acceptance')
        for kind,payload in [('acceptance_status',dict(state='success',context='task-tower/pr-acceptance',
                sha=admission['head_sha'],target_url='https://github.com/owner/repo/pull/44',description='Accepted',receipt_sha256='4'*64)),
                ('acceptance_review',dict(commit_id=admission['head_sha'],event='COMMENT',body='Whole diff accepted',receipt_sha256='4'*64))]:
            effect=self.j.begin_effect(repository,pr_number,self.owner,kind,payload)
            self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',remote_id=42,
                body_sha256='7'*64,author='operator'))
        step('accepted')

    def publication_ready(self,repository='owner/repo',pr_number=44,admission=None):
        from task_tower.github_publication import canonical
        self.ready(repository,pr_number,admission)
        row=self.j.get(repository,pr_number)
        immutable={k:row[k] for k in ('repository','pr_number','issue','issue_id','task_id',
            'head_sha','base_sha','input_sha256','policy_sha256')}
        self.j.acquire_barrier(repository,pr_number,self.owner,immutable)
        merge=self.j.begin_effect(repository,pr_number,self.owner,'merge',dict(sha=row['head_sha'],
            merge_method='merge',merge_action='direct_merge',bypass_rules=False))
        self.j.observe(merge['effect_id'],self.owner,dict(status='confirmed',merge_commit='e'*40,
            main_sha='e'*40,parents=[row['base_sha'],row['head_sha']],result='merged'))
        self.j.transition(repository,pr_number,self.owner,dict(state='awaiting_main',input_sha256=row['input_sha256']),dict(state='awaiting_postmerge'))
        role=self.j.begin_effect(repository,pr_number,self.owner,'postmerge_review',dict(
            reviewer_instance_id=str(uuid.uuid4()),request_sha256='1'*64,merge_commit='e'*40))
        self.j.observe(role['effect_id'],self.owner,dict(status='confirmed',result_sha256='2'*64,
            receipt_sha256='3'*64,reviewer_instance_id=role['payload']['reviewer_instance_id'],process=finished_process()))
        self.j.transition(repository,pr_number,self.owner,dict(state='awaiting_postmerge',input_sha256=row['input_sha256']),
            dict(state='awaiting_closure',postmerge_receipt_sha256='3'*64))
        evidence={'postmerge':{'evidence':'review.json','reviewer':'independent','sha256':'5'*64}}
        receipt=dict(version=1,kind='local-postmerge',repository=repository,issue=17,issue_id=1017,
            task_id='TT-PR-001',commit='e'*40,bundle=dict(repository=repository,pr_number=pr_number,merge_commit='e'*40),
            required_platforms=['windows'],policy=dict(executor='executor',reviewer='independent'),
            input_snapshot='6'*64,evidence=evidence,evidence_digest=hashlib.sha256(canonical(evidence).encode()).hexdigest(),
            review=dict(task_id='TT-PR-001',commit='e'*40,verdict='approve',summary='Independent postmerge review approved',findings=[]))
        return self.j.prepare_publication(repository,pr_number,self.owner,receipt)

    def confirm_comment(self,publication):
        effect=self.j.begin_effect(publication['repository'],publication['pr_number'],self.owner,'comment_post',
            dict(publication_id=publication['publication_id'],body_sha256=publication['body_sha256']))
        self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',remote_id=9,
            body_sha256=publication['body_sha256'],author='operator'))
        return self.j.record_publication(publication['publication_id'],self.owner,'comment_intent',dict(phase='comment_confirmed',comment_id=9))

    def test_publication_intents_reject_foreign_repository_and_pr_without_mutation(self):
        with self.j.owner(self.owner):
            publication=self.publication_ready()
            other=self.publication_ready('other/repo',45)
            before=self.path.read_bytes()
            with self.assertRaises(ValueError): self.j.prepare_publication('other/repo',45,self.owner,publication['receipt'])
            self.assertEqual(self.path.read_bytes(),before)
            # Same repository PR45 remains premerge while PR44 owns its barrier.
            self.ready('owner/repo',45)
            for kind in ('comment_post','issue_close'):
                if kind=='issue_close': publication=self.confirm_comment(publication)
                for repository,pr in [('OTHER/REPO',45),('owner/repo',45)]:
                    before=self.path.read_bytes()
                    payload=dict(publication_id=publication['publication_id'],body_sha256=publication['body_sha256']) if kind=='comment_post' else dict(publication_id=publication['publication_id'],issue_id=1017,state='closed',state_reason='completed')
                    with self.subTest(kind=kind,repository=repository),self.assertRaises(ValueError):
                        self.j.begin_effect(repository,pr,self.owner,kind,payload)
                    self.assertEqual(self.path.read_bytes(),before)
                    self.assertEqual(self.j.publication(publication['publication_id']),publication)
            # A valid own target still acquires its individual comment intent.
            own=self.j.begin_effect('other/repo',45,self.owner,'comment_post',dict(
                publication_id=other['publication_id'],body_sha256=other['body_sha256']))
            self.assertEqual(own['binding'],other['binding'])

    def test_database_rejects_foreign_comment_and_close_references(self):
        with self.j.owner(self.owner):
            for kind in ('comment_post','issue_close'):
                if kind=='comment_post':
                    left=self.publication_ready(); right=self.publication_ready('other/repo',45)
                else:
                    # Restore the clean pre-corruption snapshot, then advance both.
                    self.path.write_bytes(clean)
                    left=self.confirm_comment(left); right=self.confirm_comment(right)
                clean=self.path.read_bytes()
                effects=[]
                for publication in (left,right):
                    payload=dict(publication_id=publication['publication_id'],body_sha256=publication['body_sha256']) if kind=='comment_post' else dict(publication_id=publication['publication_id'],issue_id=1017,state='closed',state_reason='completed')
                    effects.append(self.j.begin_effect(publication['repository'],publication['pr_number'],self.owner,kind,payload))
                valid=self.path.read_bytes()
                key='comment_effect_id' if kind=='comment_post' else 'close_effect_id'
                with closing(sqlite3.connect(self.path)) as db:
                    with db:
                        for index,publication in enumerate((left,right)):
                            foreign=effects[1-index]
                            current=json.loads(db.execute('SELECT body FROM publications WHERE publication_id=?',(publication['publication_id'],)).fetchone()[0])
                            current[key]=foreign['effect_id']
                            foreign['payload']['publication_id']=publication['publication_id']
                            db.execute('UPDATE publications SET body=? WHERE publication_id=?',(json.dumps(current),publication['publication_id']))
                            db.execute('UPDATE effects SET body=? WHERE effect_id=?',(json.dumps(foreign),foreign['effect_id']))
                corrupt=self.path.read_bytes()
                with self.subTest(kind=kind),self.assertRaises(ValueError): self.j.rows()
                self.assertEqual(self.path.read_bytes(),corrupt)
                self.path.write_bytes(valid)
                self.assertEqual(len(self.j.rows()),2)
                # Next loop needs prepared publications, not already-intended ones.
                self.path.write_bytes(clean)

    def test_database_rejects_stale_revision_publication_effect_and_keeps_history(self):
        with self.j.owner(self.owner):
            self.j.admit(binding()); self.advance('validating'); self.advance('needs_input')
            admission=dict(binding(),head_sha='f'*40,input_sha256='9'*64,policy_sha256='8'*64)
            publication=self.publication_ready(admission=admission)
            effect=self.j.begin_effect('owner/repo',44,self.owner,'comment_post',dict(
                publication_id=publication['publication_id'],body_sha256=publication['body_sha256']))
            valid=self.path.read_bytes()
            with closing(sqlite3.connect(self.path)) as db:
                old=json.loads(db.execute('SELECT body FROM revisions').fetchone()[0])
                effect['binding']={key:old[key] for key in publication['binding']}
                with db: db.execute('UPDATE effects SET body=? WHERE effect_id=?',(json.dumps(effect),effect['effect_id']))
            corrupt=self.path.read_bytes()
            with self.assertRaises(ValueError): self.j.publication(publication['publication_id'])
            self.assertEqual(self.path.read_bytes(),corrupt)
            self.path.write_bytes(valid)
            self.assertEqual(self.j.publication(publication['publication_id'])['phase'],'comment_intent')
            self.assertEqual(self.j.get('owner/repo',44)['head_sha'],'f'*40)

    def test_same_repository_foreign_pr_intents_reject_even_with_target_barrier(self):
        # Two independently valid host snapshots form an adversarial storage
        # fixture. This isolates the exact PR check from the normal merge barrier
        # that already prevents two same-repository PRs reaching this point.
        source=self.j
        target=PRJournal(Path(self.tmp.name)/'other.sqlite3')
        with source.owner(self.owner),target.owner(self.owner):
            publication=self.publication_ready()
            self.j=target
            try: self.publication_ready('owner/repo',45)
            finally: self.j=source
            for kind in ('comment_post','issue_close'):
                if kind=='issue_close': publication=self.confirm_comment(publication)
                with closing(sqlite3.connect(source.path)) as incoming,closing(sqlite3.connect(target.path)) as outgoing:
                    with outgoing:
                        for table,placeholders in [('prs','?,?,?'),('effects','?,?'),('publications','?,?')]:
                            for row in incoming.execute('SELECT * FROM '+table):
                                outgoing.execute('INSERT OR REPLACE INTO '+table+' VALUES('+placeholders+')',row)
                self.assertEqual(target.barrier('owner/repo')['pr_number'],45)
                before=target.path.read_bytes()
                payload=dict(publication_id=publication['publication_id'],body_sha256=publication['body_sha256']) if kind=='comment_post' else dict(publication_id=publication['publication_id'],issue_id=1017,state='closed',state_reason='completed')
                with self.subTest(kind=kind),self.assertRaises(ValueError): target.begin_effect('OWNER/REPO',45,self.owner,kind,payload)
                self.assertEqual(target.path.read_bytes(),before)
                self.assertEqual(target.publication(publication['publication_id']),publication)

    def test_deadline_restart_cannot_renew(self):
        first=self.j.admit(binding()); again=PRJournal(self.path).admit(binding())
        self.assertEqual(first['deadline_utc'],again['deadline_utc'])
        self.assertEqual(first['admitted_utc'],again['admitted_utc'])
        altered=binding(); altered['task_timeout_seconds']=600
        with self.assertRaises(ValueError): self.j.admit(altered)
        with self.j.owner(self.owner):
            self.advance('validating'); self.advance('reviewing')
            self.j.begin_effect('owner/repo',44,self.owner,'pr_review',dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='c'*64))
            row=self.j.get('owner/repo',44)
            self.assertEqual(row['review_attempts'],1)
        self.assertEqual(PRJournal(self.path).get('owner/repo',44)['review_attempts'],1)

    def test_same_repository_duplicate_owner_and_unknown_intent_fenced(self):
        with self.j.owner(self.owner):
            self.ready()
            with self.assertRaises(ValueError):
                with PRJournal(self.path).owner(str(uuid.uuid4())): pass
            code='from pathlib import Path; from task_tower.pr_journal import PRJournal; import uuid; j=PRJournal(Path('+repr(str(self.path))+'));\nwith j.owner(str(uuid.uuid4())): pass'
            result=subprocess.run([sys.executable,'-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8')
            self.assertNotEqual(result.returncode,0)
            barrier=self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            effect=self.j.begin_effect('owner/repo',44,self.owner,'merge',dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False))
            self.assertEqual(effect['status'],'intent')
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'merge',effect['payload'])
            self.j.admit(binding(pr=45))
            with self.assertRaises(ValueError): self.j.acquire_barrier('owner/repo',45,self.owner,binding(pr=45))
            self.j.admit(binding('other/repo',45))
            # Other repositories have independent barriers after their own acceptance.
            self.assertEqual(barrier['owner_id'],self.owner)
        with self.j.owner(str(uuid.uuid4())):
            with self.assertRaises(ValueError): self.j.observe(effect['effect_id'],str(uuid.uuid4()),dict(status='unknown'))
        self.assertIsNotNone(PRJournal(self.path).barrier('owner/repo'))

    def test_cancel_after_merge_keeps_barrier(self):
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            self.j.begin_effect('owner/repo',44,self.owner,'merge',dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False))
            self.j.cancel('owner/repo',44)
            self.assertTrue(self.j.get('owner/repo',44)['cancel_requested'])
            self.assertIsNotNone(self.j.barrier('owner/repo'))
            with self.assertRaises(ValueError): self.j.complete_barrier('owner/repo',self.owner,{'verified_done':True})

    def test_cas_closed_state_machine_and_schema_tampering(self):
        self.j.admit(binding())
        with self.assertRaises(ValueError): self.advance('validating')
        with self.j.owner(self.owner):
            with self.assertRaises(ValueError): self.advance('accepted')
            self.advance('validating')
            with self.assertRaises(ValueError): self.j.transition('owner/repo',44,self.owner,
                dict(state='discovered',input_sha256='c'*64),dict(state='reviewing'))
            with self.assertRaises(ValueError): self.j.transition('owner/repo',44,self.owner,
                dict(state='validating',input_sha256='c'*64),dict(state='reviewing',deadline_utc='later'))
        with closing(sqlite3.connect(self.path)) as db:
            with db: db.execute('CREATE TABLE injected(x)')
        with self.assertRaises(ValueError): self.j.rows()

    def test_backwards_clock_and_expired_deadline_block_new_action(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        with patch('task_tower.pr_journal._now',return_value=start): self.j.admit(binding())
        with self.j.owner(self.owner):
            with patch('task_tower.pr_journal._now',return_value=start-timedelta(seconds=1)):
                with self.assertRaises(ValueError): self.advance('validating')
            self.assertEqual(self.j.get('owner/repo',44)['state'],'unknown')
            with patch('task_tower.pr_journal._now',return_value=start+timedelta(seconds=1)):
                with self.assertRaises(ValueError): self.advance('validating')
        other=PRJournal(Path(self.tmp.name)/'expired.sqlite3')
        with patch('task_tower.pr_journal._now',return_value=start): other.admit(binding())
        with other.owner(str(uuid.uuid4())) as owner:
            with patch('task_tower.pr_journal._now',return_value=start+timedelta(seconds=60)):
                with self.assertRaises(ValueError): other.transition('owner/repo',44,owner,
                    dict(state='discovered',input_sha256='c'*64),dict(state='validating'))
            self.assertEqual(other.get('owner/repo',44)['state'],'timed_out')

    def test_postmerge_publication_individual_intents_exact_v1_body_and_full_completion(self):
        from task_tower.github_publication import canonical, publication_id, LIFECYCLE
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            merge=self.j.begin_effect('owner/repo',44,self.owner,'merge',
                dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False))
            self.j.observe(merge['effect_id'],self.owner,dict(status='confirmed',merge_commit='e'*40,
                main_sha='e'*40,parents=['b'*40,'a'*40],result='merged'))
            self.advance('awaiting_postmerge')
            post=self.j.begin_effect('owner/repo',44,self.owner,'postmerge_review',
                dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='1'*64,merge_commit='e'*40))
            self.j.observe(post['effect_id'],self.owner,dict(status='confirmed',result_sha256='2'*64,
                receipt_sha256='3'*64,reviewer_instance_id=post['payload']['reviewer_instance_id'],process=finished_process()))
            row=self.j.get('owner/repo',44)
            self.j.transition('owner/repo',44,self.owner,dict(state=row['state'],input_sha256='c'*64),
                dict(state='awaiting_closure',pr_receipt_sha256='4'*64,postmerge_receipt_sha256='3'*64))
            evidence={'postmerge':{'evidence':'review.json','reviewer':'independent','sha256':'5'*64}}
            receipt=dict(version=1,kind='local-postmerge',repository='owner/repo',issue=17,issue_id=1017,
                task_id='TT-PR-001',commit='e'*40,bundle=dict(repository='owner/repo',merge_commit='e'*40),
                required_platforms=['windows'],policy=dict(executor='executor',reviewer='independent'),
                input_snapshot='6'*64,evidence=evidence,evidence_digest=hashlib.sha256(canonical(evidence).encode()).hexdigest(),
                review=dict(task_id='TT-PR-001',commit='e'*40,verdict='approve',summary='Independent postmerge review approved',findings=[]))
            publication=self.j.prepare_publication('owner/repo',44,self.owner,receipt)
            identity=publication_id(receipt)
            expected={'remote_attempt':dict(kind='local-postmerge',status='done',commit='e'*40,
                publication_id=identity,receipt=receipt),'status':'done'}
            body=LIFECYCLE+canonical(expected)+'\n-->'
            self.assertEqual(publication['publication_id'],identity)
            self.assertEqual(publication['body_sha256'],hashlib.sha256(body.encode()).hexdigest())
            comment=self.j.begin_effect('owner/repo',44,self.owner,'comment_post',
                dict(publication_id=identity,body_sha256=publication['body_sha256']))
            self.assertEqual(self.j.publication(identity)['phase'],'comment_intent')
            with self.assertRaises(ValueError): self.j.record_publication(identity,self.owner,'comment_intent',dict(phase='comment_confirmed',comment_id=9))
            self.j.record_publication(identity,self.owner,'comment_intent',dict(phase='unknown'))
            self.j.observe(comment['effect_id'],self.owner,dict(status='confirmed',remote_id=9,
                body_sha256=publication['body_sha256'],author='operator'))
            self.j.record_publication(identity,self.owner,'unknown',dict(phase='comment_confirmed',comment_id=9))
            close=self.j.begin_effect('owner/repo',44,self.owner,'issue_close',dict(publication_id=identity,
                issue_id=1017,state='closed',state_reason='completed'))
            self.assertEqual(self.j.publication(identity)['phase'],'close_intent')
            self.j.record_publication(identity,self.owner,'close_intent',dict(phase='unknown'))
            self.j.observe(close['effect_id'],self.owner,dict(status='confirmed',issue_id=1017,state='closed',state_reason='completed'))
            self.j.record_publication(identity,self.owner,'unknown',dict(phase='closure_observed'))
            self.assertIsNotNone(self.j.barrier('owner/repo'))
            proof=dict(repository='owner/repo',pr_number=44,issue=17,issue_id=1017,task_id='TT-PR-001',
                head_sha='a'*40,base_sha='b'*40,merge_commit='e'*40,main_sha='e'*40,
                bundle_sha256=hashlib.sha256(canonical(receipt['bundle']).encode()).hexdigest(),
                pr_receipt_sha256='4'*64,postmerge_receipt_sha256='3'*64,publication_id=identity,
                verified_done=True,issue_state='closed',state_reason='completed')
            wrong=dict(proof,issue_id=999)
            with self.assertRaises(ValueError): self.j.record_publication(identity,self.owner,'closure_observed',dict(phase='published',completion_proof=wrong))
            self.j.record_publication(identity,self.owner,'closure_observed',dict(phase='published',completion_proof=proof))
            self.j.complete_barrier('owner/repo',self.owner,proof)
            self.assertIsNone(self.j.barrier('owner/repo'))
            self.assertEqual(self.j.get('owner/repo',44)['state'],'completed')

    def test_owner_loss_never_reuses_owner_or_effect_even_same_pid(self):
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            effect=self.j.begin_effect('owner/repo',44,self.owner,'merge',dict(sha='a'*40,
                merge_method='merge',merge_action='direct_merge',bypass_rules=False))
        restarted=PRJournal(self.path)
        with self.assertRaises(ValueError):
            with restarted.owner(self.owner): pass
        with restarted.owner(str(uuid.uuid4())) as fresh:
            with self.assertRaises(ValueError): restarted.observe(effect['effect_id'],fresh,dict(status='unknown'))
            with self.assertRaises(ValueError): restarted.begin_effect('owner/repo',44,fresh,'merge',effect['payload'])
        self.assertIsNotNone(restarted.barrier('owner/repo'))

    def test_readonly_effect_inspection_and_unknown_merge_request_retained(self):
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            payload=dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False)
            effect=self.j.begin_effect('owner/repo',44,self.owner,'merge',payload)
            self.j.observe(effect['effect_id'],self.owner,dict(status='unknown'))
            self.assertEqual(self.j.effect(effect['effect_id'])['status'],'unknown')
            self.assertEqual([e for e in self.j.effects('owner/repo',44) if e['kind']=='merge'][0]['payload'],payload)
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'merge',payload)
            self.assertEqual(self.j.get('owner/repo',44)['state'],'merge_intent')
        self.assertEqual(PRJournal(self.path).effect(effect['effect_id'])['status'],'unknown')

    def test_different_repositories_have_independent_barriers(self):
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            self.ready('other/repo',45)
            self.j.acquire_barrier('other/repo',45,self.owner,binding('other/repo',45))
            self.assertEqual(self.j.barrier('owner/repo')['pr_number'],44)
            self.assertEqual(self.j.barrier('other/repo')['pr_number'],45)

    def test_observation_wrong_head_parents_and_unknown_fields_block(self):
        with self.j.owner(self.owner):
            self.ready(); self.j.acquire_barrier('owner/repo',44,self.owner,binding())
            for payload in (dict(sha='f'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=False),
                    dict(sha='a'*40,merge_method='merge',merge_action='direct_merge',bypass_rules=True)):
                with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'merge',payload)
            effect=self.j.begin_effect('owner/repo',44,self.owner,'merge',dict(sha='a'*40,
                merge_method='merge',merge_action='direct_merge',bypass_rules=False))
            with self.assertRaises(ValueError): self.j.observe(effect['effect_id'],self.owner,
                dict(status='confirmed',merge_commit='e'*40,main_sha='e'*40,parents=['a'*40,'b'*40],result='merged'))
            with self.assertRaises(ValueError): self.j.observe(effect['effect_id'],self.owner,dict(status='unknown',extra=True))
            self.assertIsNotNone(self.j.barrier('owner/repo'))

    def test_fresh_revision_retains_deadline_counters_and_old_effects(self):
        with self.j.owner(self.owner):
            first=self.j.admit(binding()); self.advance('validating'); self.advance('reviewing')
            effect=self.j.begin_effect('owner/repo',44,self.owner,'pr_review',
                dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='c'*64))
            child=subprocess.Popen([sys.executable,'-c','pass']); pid=child.pid; result=child.wait()
            self.j.observe(effect['effect_id'],self.owner,dict(status='confirmed',result_sha256='1'*64,
                receipt_sha256='2'*64,reviewer_instance_id=effect['payload']['reviewer_instance_id'],
                process=dict(pid=pid,exit_code=result,started=True,cleanup_confirmed=True)))
            self.j.transition('owner/repo',44,self.owner,dict(state='reviewing',input_sha256='c'*64),
                dict(state='rejected',pr_receipt_sha256='2'*64))
            with self.assertRaises(ValueError): self.j.admit(dict(binding(),task_timeout_seconds=600))
            changed=dict(binding(),head_sha='f'*40,base_sha='0'*40,input_sha256='9'*64,policy_sha256='8'*64)
            fresh=self.j.admit(changed)
            self.assertEqual(fresh['state'],'discovered'); self.assertEqual(fresh['review_attempts'],1)
            self.assertEqual(fresh['deadline_utc'],first['deadline_utc'])
            self.assertIsNone(fresh['pr_receipt_sha256'])
            self.assertEqual(self.j.effect(effect['effect_id'])['binding']['head_sha'],'a'*40)
            for state in ('validating','reviewing'):
                row=self.j.get('owner/repo',44)
                self.j.transition('owner/repo',44,self.owner,dict(state=row['state'],input_sha256='9'*64),dict(state=state))
            with self.assertRaises(ValueError): self.j.transition('owner/repo',44,self.owner,
                dict(state='reviewing',input_sha256='9'*64),dict(state='reviewed',pr_receipt_sha256='2'*64))
            self.j.begin_effect('owner/repo',44,self.owner,'pr_review',dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='9'*64))
            self.assertEqual(self.j.get('owner/repo',44)['review_attempts'],2)
            with self.assertRaises(ValueError): self.j.admit(binding())

    def test_revision_unknown_intent_owner_loss_identity_and_barrier_fenced(self):
        with self.j.owner(self.owner):
            self.j.admit(binding()); self.advance('validating'); self.advance('reviewing')
            self.j.begin_effect('owner/repo',44,self.owner,'pr_review',dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='c'*64))
            self.advance('stale')
            changed=dict(binding(),input_sha256='9'*64,head_sha='f'*40)
            with self.assertRaises(ValueError): self.j.admit(changed)
            with self.assertRaises(ValueError): self.j.admit(dict(changed,issue_id=999))
            self.assertEqual(self.j.get('owner/repo',44)['head_sha'],'a'*40)
        with self.j.owner(str(uuid.uuid4())):
            with self.assertRaises(ValueError): self.j.admit(changed)

    def test_accepted_requires_bound_role_receipt_and_publication_observations(self):
        with self.j.owner(self.owner):
            self.j.admit(binding()); self.advance('validating'); self.advance('reviewing')
            with self.assertRaises(ValueError): self.advance('reviewed')

    def test_new_input_before_launch_and_after_clean_failed_process(self):
        with self.j.owner(self.owner):
            first=self.j.admit(binding()); self.advance('validating'); self.advance('needs_input')
            second=dict(binding(),input_sha256='9'*64,policy_sha256='8'*64)
            self.assertEqual(self.j.admit(second)['deadline_utc'],first['deadline_utc'])
            for state in ('validating','reviewing'):
                row=self.j.get('owner/repo',44)
                self.j.transition('owner/repo',44,self.owner,dict(state=row['state'],input_sha256='9'*64),dict(state=state))
            role=self.j.begin_effect('owner/repo',44,self.owner,'pr_review',dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='9'*64))
            child=subprocess.Popen([sys.executable,'-c','raise SystemExit(7)']); pid=child.pid; result=child.wait()
            self.j.observe(role['effect_id'],self.owner,dict(status='failed',process=dict(pid=pid,exit_code=result,started=True,cleanup_confirmed=True)))
            self.j.transition('owner/repo',44,self.owner,dict(state='reviewing',input_sha256='9'*64),dict(state='needs_input'))
            third=dict(binding(),input_sha256='7'*64,head_sha='6'*40)
            self.assertEqual(self.j.admit(third)['review_attempts'],1)
            with self.assertRaises(ValueError): self.j.observe(role['effect_id'],self.owner,dict(status='unknown',
                process=dict(pid=pid,exit_code=result,started=True,cleanup_confirmed=True)))
            for state in ('validating','reviewing'):
                row=self.j.get('owner/repo',44)
                self.j.transition('owner/repo',44,self.owner,dict(state=row['state'],input_sha256='7'*64),dict(state=state))
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'pr_review',
                dict(reviewer_instance_id=role['payload']['reviewer_instance_id'],request_sha256='7'*64))

    def test_success_before_review_and_any_unresolved_write_block_next_effect(self):
        with self.j.owner(self.owner):
            self.j.admit(binding()); self.advance('validating')
            status=dict(state='success',context='task-tower/pr-acceptance',sha='a'*40,
                target_url='https://github.com/owner/repo/pull/44',description='Accepted',receipt_sha256='c'*64)
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'acceptance_status',status)
            status.update(state='pending',description='Review pending')
            self.j.begin_effect('owner/repo',44,self.owner,'acceptance_status',status)
            self.advance('reviewing')
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'pr_review',
                dict(reviewer_instance_id=str(uuid.uuid4()),request_sha256='c'*64))

    def test_rejection_can_publish_failure_once(self):
        with self.j.owner(self.owner):
            self.j.admit(binding()); self.advance('validating'); self.advance('needs_input')
            payload=dict(state='failure',context='task-tower/pr-acceptance',sha='a'*40,
                target_url='https://github.com/owner/repo/pull/44',description='Source incomplete',receipt_sha256='c'*64)
            effect=self.j.begin_effect('owner/repo',44,self.owner,'acceptance_status',payload)
            self.assertEqual(effect['status'],'intent')
            with self.assertRaises(ValueError): self.j.begin_effect('owner/repo',44,self.owner,'acceptance_status',payload)

    def test_crashed_process_releases_os_lock_but_never_its_merge_intent(self):
        code=('from pathlib import Path; import os; from tests.test_pr_journal import JournalTests, binding; '
            'from task_tower.pr_journal import PRJournal; case=JournalTests(); '
            'case.j=PRJournal(Path('+repr(str(self.path))+')); case.owner='+repr(self.owner)+';\n'
            'with case.j.owner(case.owner):\n'
            ' case.ready(); case.j.acquire_barrier("owner/repo",44,case.owner,binding()); '
            'case.j.begin_effect("owner/repo",44,case.owner,"merge",dict(sha="a"*40,merge_method="merge",merge_action="direct_merge",bypass_rules=False)); '
            'os._exit(23)')
        result=subprocess.run([sys.executable,'-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,23,result.stderr)
        restarted=PRJournal(self.path)
        self.assertEqual(restarted.get('owner/repo',44)['state'],'merge_intent')
        with restarted.owner(str(uuid.uuid4())) as fresh:
            with self.assertRaises(ValueError): restarted.acquire_barrier('owner/repo',44,fresh,binding())
            effect=[e for e in restarted.effects('owner/repo',44) if e['kind']=='merge'][0]
            with self.assertRaises(ValueError): restarted.observe(effect['effect_id'],fresh,dict(status='unknown'))
        self.assertIsNotNone(restarted.barrier('owner/repo'))

    def test_private_paths_no_checkout_hardlink_sidecar_or_input_collision(self):
        root=Path(self.tmp.name); checkout=root/'checkout'; checkout.mkdir()
        with self.assertRaises(ValueError): PRJournal(checkout/'j',checkouts=(checkout,))
        with self.assertRaises(ValueError): PRJournal(self.path,forbidden_paths=(Path(str(self.path)+'-wal'),))
        self.j.admit(binding()); alias=root/'alias'; os.link(self.path,alias)
        with self.assertRaises(ValueError): self.j.rows()


if __name__=='__main__': unittest.main()
