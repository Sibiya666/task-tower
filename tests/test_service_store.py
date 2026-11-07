from contextlib import closing
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tests.test_service_beads import NativeFixture, Beads
from task_tower.service.store import Store, plan_digest
from task_tower.service.beads import ServiceError

PLAN = {'tasks': [{'id':'pilot-a','title':'A','description':'First','depends_on':[]},
                  {'id':'pilot-b','title':'B','description':'Second','depends_on':['pilot-a']}]}
DIGEST = hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'journal.sqlite'
        self.native=NativeFixture()
        self.beads=Beads(Path(self.tmp.name)/'bd',{'p':Path(self.tmp.name)},runner=self.native)
        self.store=Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        self.addCleanup(lambda:self.store.close())

    def imported(self):
        return self.store.import_plan('import-1','p',DIGEST,PLAN)

    def test_duplicate_claims_and_request_return_same_attempt_intent_before_effect(self):
        self.imported()
        def inspect():
            with closing(sqlite3.connect(self.path)) as db:
                self.assertEqual(db.execute("select phase from attempts").fetchone()[0],'claim_pending')
        self.native.before_claim=inspect
        first=self.store.claim_request('r1','p','pilot-a','c1')
        self.assertEqual(first['phase'],'claimed')
        self.assertEqual(self.store.claim_request('r1','p','pilot-a','c1'),first)
        self.assertEqual(self.store.claim_request('r2','p','pilot-a','c1'),first)
        self.assertEqual(sum('--claim' in c for c in self.native.calls),1)
        with self.assertRaises(ServiceError): self.store.claim_request('r1','p','pilot-b','c1')
        with self.assertRaises(ServiceError): self.store.claim_request('r3','p','pilot-a','c2')

    def test_only_published_approved_plan_can_be_ready_or_claimed(self):
        self.native.rows['outside-a']=dict(id='outside-a',status='open')
        self.assertEqual(self.store.ready('p'),[])
        with self.assertRaises(ServiceError): self.store.claim_request('r1','p','outside-a','c1')
        with self.assertRaises(ServiceError): self.store.import_plan('i','p','0'*64,PLAN)
        self.imported()
        self.assertEqual([r['id'] for r in self.store.ready('p')],['pilot-a'])

    def test_import_digest_request_immutable_and_all_links_readback(self):
        first=self.imported()
        self.assertEqual(first['state'],'published')
        self.assertEqual(self.store.import_plan('import-1','p',DIGEST,PLAN),first)
        changed=json.loads(json.dumps(PLAN));changed['tasks'][0]['title']='changed'
        with self.assertRaises(ServiceError):self.store.import_plan('import-1','p',DIGEST,changed)
        self.assertEqual(self.native.rows['pilot-b']['requires'],['pilot-a'])

    def test_partial_import_stays_unpublished_and_restart_does_not_replay(self):
        self.native.fail_at='dep'
        result=self.imported()
        self.assertEqual(result['state'],'needs_reconciliation')
        self.assertTrue(all(r['status']=='deferred' for r in self.native.rows.values()))
        self.assertEqual(self.store.ready('p'),[])
        calls=len(self.native.calls)
        self.store.close();self.store=Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        self.assertEqual(self.store.import_plan('import-1','p',DIGEST,PLAN),result)
        self.assertEqual(len(self.native.calls),calls)

    def test_pending_claim_restart_fences_even_when_native_effect_happened(self):
        self.imported()
        def crash(): raise KeyboardInterrupt()
        self.native.before_claim=crash
        with self.assertRaises(KeyboardInterrupt):self.store.claim_request('r1','p','pilot-a','c1')
        self.store.close();self.store=Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        calls=len(self.native.calls)
        result=self.store.claim_request('r1','p','pilot-a','c1')
        self.assertEqual(result['phase'],'needs_reconciliation')
        self.assertEqual(len(self.native.calls),calls)

    def test_event_idempotency_and_state_are_one_transaction(self):
        self.imported();a=self.store.claim_request('r1','p','pilot-a','c1')
        event={'version':1,'event_id':'e1','attempt_id':a['attempt_id'],'connector_id':'c1',
               'phase':'executing','execution_state':'running','connection_state':'connected'}
        first=self.store.record_event(event)
        self.assertEqual(first['phase'],'executing')
        self.assertEqual(self.store.record_event(event),first)
        with self.assertRaises(ServiceError): self.store.record_event(dict(event,phase='accepted'))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('select count(*) from events').fetchone()[0],1)
            self.assertEqual(db.execute('select phase from attempts').fetchone()[0],'executing')

    def test_connector_cannot_report_acceptance_or_release_ownership(self):
        self.imported();a=self.store.claim_request('r1','p','pilot-a','c1')
        for phase in ['accepted','claimed','claim_pending']:
            with self.assertRaises(ServiceError):self.store.record_event({'version':1,'event_id':phase,
                'attempt_id':a['attempt_id'],'connector_id':'c1','phase':phase,
                'execution_state':'stopped','connection_state':'connected'})
        self.assertEqual(self.native.rows['pilot-a']['status'],'in_progress')

    def test_second_live_journal_owner_cannot_reconcile_first(self):
        with self.assertRaises((OSError,ValueError)):
            Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        self.imported()
        self.assertEqual(self.store.claim_request('r1','p','pilot-a','c1')['phase'],'claimed')

    def test_native_effect_then_lost_readback_is_fenced_without_reclaim(self):
        self.imported()
        def lose_readback():self.native.fail_at='show'
        self.native.before_claim=lose_readback
        first=self.store.claim_request('r1','p','pilot-a','c1')
        self.assertEqual(first['phase'],'needs_reconciliation')
        owner=self.native.rows['pilot-a']['assignee']
        self.assertTrue(owner.startswith('tower-'))
        self.store.close();self.store=Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        calls=len(self.native.calls)
        self.assertEqual(self.store.claim_request('r1','p','pilot-a','c1'),first)
        self.assertEqual(self.store.claim_request('r2','p','pilot-a','c1'),first)
        self.assertEqual(len(self.native.calls),calls)
        self.assertEqual(self.native.rows['pilot-a']['assignee'],owner)

    def test_task_changed_after_approval_cannot_be_claimed(self):
        self.imported();self.native.rows['pilot-a']['description']='unapproved scope'
        result=self.store.claim_request('r1','p','pilot-a','c1')
        self.assertEqual(result['phase'],'needs_reconciliation')
        self.assertFalse(any('--claim' in c for c in self.native.calls))

    def test_interrupted_publish_is_hidden_and_import_does_not_replay(self):
        count=[0]
        def interrupt(argv,cwd,timeout,env):
            result=self.native(argv,cwd,timeout,env)
            if 'update' in argv:
                count[0]+=1
                if count[0]==1:raise KeyboardInterrupt()
            return result
        self.beads.runner=interrupt
        with self.assertRaises(KeyboardInterrupt):self.imported()
        self.assertEqual(self.native.rows['pilot-a']['status'],'open')
        self.assertEqual(self.native.rows['pilot-b']['status'],'deferred')
        self.store.close();self.store=Store(self.path,self.beads,approved_plans={'p':{DIGEST}})
        self.assertEqual(self.store.ready('p'),[])
        calls=len(self.native.calls)
        self.assertEqual(self.imported()['state'],'needs_reconciliation')
        self.assertEqual(len(self.native.calls),calls)

    def test_event_state_failure_rolls_back_dedup_record(self):
        self.imported();a=self.store.claim_request('r1','p','pilot-a','c1')
        self.store.db.execute("CREATE TRIGGER fail_state BEFORE UPDATE ON attempts BEGIN SELECT RAISE(ABORT,'failure'); END")
        event=dict(version=1,event_id='e1',attempt_id=a['attempt_id'],connector_id='c1',
                   phase='executing',execution_state='running',connection_state='connected')
        with self.assertRaises(sqlite3.IntegrityError):self.store.record_event(event)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.store.attempt(a['attempt_id'])['phase'],'claimed')
        self.store.db.execute('DROP TRIGGER fail_state')
        self.assertEqual(self.store.record_event(event)['phase'],'executing')

    def test_concurrent_claim_requests_produce_one_native_owner(self):
        from concurrent.futures import ThreadPoolExecutor
        self.imported()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda i:self.store.claim_request('r'+str(i),'p','pilot-a','c1'),range(4)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(sum('--claim' in c for c in self.native.calls),1)

    def test_import_alias_request_id_remains_immutable(self):
        first=self.imported()
        self.assertEqual(self.store.import_plan('import-alias','p',DIGEST,PLAN),first)
        changed={'tasks':[dict(id='pilot-c',title='C',description='New batch',depends_on=[])]}
        other=plan_digest(changed);self.store.approved_plans['p']=frozenset({DIGEST,other})
        with self.assertRaises(ServiceError):self.store.import_plan('import-alias','p',other,changed)
        self.assertEqual(self.store.import_plan('import-alias','p',DIGEST,PLAN),first)
