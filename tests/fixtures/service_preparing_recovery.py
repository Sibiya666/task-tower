"""Preparing protocol contracts on disposable service SQLite/native fixtures."""
import tempfile
from pathlib import Path
from task_tower.preparing_recovery import fingerprint
from task_tower.service.store import Store,plan_digest
from tests.test_service_beads import NativeFixture,Beads
from tests.fixtures.preparing_recovery import receipt

PLAN={'tasks':[dict(id='pilot-dep',title='Dependency',description='Fixture prerequisite',depends_on=[]),dict(id='pilot-task',title='Work',description='Fixture scope',depends_on=['pilot-dep'])]}
BASE='a'*40

class PreparingServiceFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.path=self.root/'journal'
        self.native=NativeFixture();self.beads=Beads(self.root/'bd',{'p':self.root},runner=self.native)
        self.s=Store(self.path,self.beads,approved_plans={'p':{plan_digest(PLAN)}},approved_preparing={});self.addCleanup(lambda:self.s.close())
        self.s.import_plan('import','p',plan_digest(PLAN),PLAN);self.native.rows['pilot-dep']['status']='closed'
        a=self.s.claim_request('claim','p','pilot-task','host1');self.s.start_lifecycle(a['attempt_id'],'host1',BASE)
        self.command=self.s.lifecycle_commands('host1')[0]
        self.s.record_event(dict(version=1,event_id='failed',attempt_id=a['attempt_id'],connector_id='host1',lifecycle=dict(kind='failed',command_id=self.command['command_id'])))
        self.a=self.s.attempt(a['attempt_id']);self.r=dict(receipt(),project_id='p',bead_id='pilot-task',attempt_id=a['attempt_id'],native_owner=a['actor'],command_id=self.command['command_id'],branch='codex/headless-'+a['attempt_id'],command_sha256=fingerprint(self.command))
        self.approved={'p':frozenset({fingerprint(self.r)})};self.s.close();self.reopen()
    def reopen(self):self.s=Store(self.path,self.beads,approved_plans={'p':{plan_digest(PLAN)}},approved_preparing=self.approved)
    def admit(self,r=None,connector='host1'):return self.s.admit_preparing(self.r if r is None else r,connector)
    def status(self):return self.s.preparing_status(self.r['operation_id'],'host1')
    def ack(self,**changes):
        result=dict(version=1,state='prepared',receipt_sha256=fingerprint(self.r),**{k:self.r[k] for k in ('operation_id','connector_id','project_id','attempt_id','command_id','engine_sha')});result.update(changes)
        return dict(version=1,event_id='prepared-event',attempt_id=self.a['attempt_id'],connector_id='host1',preparing=result)
    def original(self):
        self.assertEqual(self.s.attempt(self.a['attempt_id']),self.a);self.assertEqual(self.s.active_count('host1'),1)
        self.assertEqual(self.native.rows['pilot-task']['assignee'],self.a['actor'])
