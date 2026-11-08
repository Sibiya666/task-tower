import copy
import tempfile
import unittest
from pathlib import Path
from task_tower.service.store import Store,plan_digest
from task_tower.service.beads import Beads,ServiceError
from tests.test_service_beads import NativeFixture

PLAN={'tasks':[{'id':'pilot-a','title':'A','description':'First','depends_on':[],'parents':['pilot-epic']}]}
class AdoptionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.native=NativeFixture();self.native.rows['pilot-a']=dict(id='pilot-a',title='A',description='First',status='open',assignee=None,dependencies=[dict(id='pilot-epic',dependency_type='parent-child')])
  def runner(argv,cwd,timeout,env):
   result=self.native(argv,cwd,timeout,env)
   if 'show' in argv:
    result[0]['dependencies'] += copy.deepcopy(self.native.rows[result[0]['id']].get('dependencies',[]))
   return result
  self.beads=Beads(Path(self.tmp.name)/'bd',{'p':Path(self.tmp.name)},runner=runner)
  self.path=Path(self.tmp.name)/'journal';self.digest=plan_digest(PLAN)
  self.store=Store(self.path,self.beads,approved_plans={'p':{self.digest}});self.addCleanup(lambda:self.store.close())
 def test_adoption_preserves_native_and_is_idempotent(self):
  before=copy.deepcopy(self.native.rows)
  first=self.store.adopt_plan('adopt-1','p',self.digest,PLAN)
  self.assertEqual(first['state'],'published');self.assertEqual(self.native.rows,before)
  self.assertEqual(self.store.adopt_plan('adopt-1','p',self.digest,PLAN),first)
  self.assertFalse(any('create' in c or 'update' in c for c in self.native.calls))
 def test_owner_and_parent_drift_rejected(self):
  self.native.rows['pilot-a']['assignee']='foreign'
  self.assertNotEqual(self.store.adopt_plan('adopt-1','p',self.digest,PLAN)['state'],'published')
 def test_blocking_dependency_and_parent_are_separate(self):
  plan=copy.deepcopy(PLAN)
  plan['tasks'].append(dict(id='pilot-b',title='B',description='Second',depends_on=['pilot-a'],parents=['pilot-epic']))
  self.native.rows['pilot-b']=dict(id='pilot-b',title='B',description='Second',status='open',requires=['pilot-a'],dependencies=[dict(id='pilot-epic',dependency_type='parent-child')])
  digest=plan_digest(plan);self.store.approved_plans['p']={digest}
  self.assertEqual(self.store.adopt_plan('deps','p',digest,plan)['state'],'published')
  self.assertEqual([r['id'] for r in self.store.ready('p')],['pilot-a'])
  self.assertNotIn('pilot-epic',self.store._published('p'))
  # Native closure makes the child ready; adoption itself never closes a parent.
  self.native.rows['pilot-a']['status']='closed'
  self.assertEqual([r['id'] for r in self.store.ready('p')],['pilot-b'])
 def test_approval_and_scope_required(self):
  with self.assertRaises(ServiceError):self.store.adopt_plan('a','p','0'*64,PLAN)
  with self.assertRaises(ServiceError):self.store.adopt_plan('b','other',self.digest,PLAN)

 def test_title_status_parent_and_blocker_drift_are_fenced(self):
  for field,value in [('title','Changed'),('status','blocked'),('dependencies',[]),('description','Changed'),('metadata',{'unknown':'fence'})]:
   with self.subTest(field=field):
    path=Path(self.tmp.name)/('journal-'+field)
    store=Store(path,self.beads,approved_plans={'p':{self.digest}})
    original=copy.deepcopy(self.native.rows['pilot-a'])
    try:
     self.native.rows['pilot-a'][field]=value
     self.assertEqual(store.adopt_plan('bad','p',self.digest,PLAN)['state'],'needs_reconciliation')
     self.native.rows['pilot-a']=original
     self.assertEqual(store.adopt_plan('later','p',self.digest,PLAN)['state'],'needs_reconciliation')
    finally:
     self.native.rows['pilot-a']=original;store.close()
 def test_owner_drift_between_readbacks_never_publishes(self):
  original=self.store._verify_import
  calls=[]
  def verify(*args):
   original(*args);calls.append(1)
   if len(calls)==1:self.native.rows['pilot-a']['assignee']='foreign'
  self.store._verify_import=verify
  self.assertEqual(self.store.adopt_plan('adopt-1','p',self.digest,PLAN)['state'],'needs_reconciliation')
 def test_alias_conflicts_and_legacy_import_do_not_mutate_adopted_task(self):
  result=self.store.adopt_plan('adopt-1','p',self.digest,PLAN)
  self.assertEqual(self.store.adopt_plan('alias','p',self.digest,PLAN),result)
  calls=list(self.native.calls)
  with self.assertRaises(ServiceError):self.store.import_plan('legacy','p',self.digest,PLAN)
  self.assertEqual(self.native.calls,calls)
 def test_fresh_claim_rechecks_approved_parent_and_restart(self):
  self.store.adopt_plan('adopt-1','p',self.digest,PLAN)
  self.store.close()
  self.store=Store(self.path,self.beads,approved_plans={'p':{self.digest}})
  self.native.rows['pilot-a']['dependencies']=[]
  result=self.store.claim_request('claim-1','p','pilot-a','c')
  self.assertEqual(result['phase'],'needs_reconciliation')
  self.assertFalse(any('--claim' in call for call in self.native.calls))
 def test_unknown_native_read_is_not_replayed(self):
  self.native.fail_at='show'
  result=self.store.adopt_plan('adopt-1','p',self.digest,PLAN)
  self.assertEqual(result['state'],'needs_reconciliation')
  count=len(self.native.calls);self.native.fail_at=None
  self.assertEqual(self.store.adopt_plan('adopt-1','p',self.digest,PLAN),result)
  self.assertEqual(len(self.native.calls),count)
 def test_claim_preserves_parent_and_uses_normal_native_ownership(self):
  self.store.adopt_plan('adopt-1','p',self.digest,PLAN)
  result=self.store.claim_request('claim-1','p','pilot-a','c')
  self.assertEqual(result['phase'],'claimed')
  self.assertEqual(self.native.rows['pilot-a']['dependencies'],[dict(id='pilot-epic',dependency_type='parent-child')])
  self.store.validate_execution(result['attempt_id'],'c')

 def external_plan(self):
  plan=copy.deepcopy(PLAN);plan['tasks'][0]['depends_on']=['pilot-done']
  self.native.rows['pilot-done']=dict(id='pilot-done',title='Previous work',status='closed')
  self.native.rows['pilot-a']['requires']=['pilot-done']
  digest=plan_digest(plan);self.store.approved_plans['p']={digest}
  return plan,digest

 def adopt_external(self,plan,digest):
  try:return self.store.adopt_plan('external','p',digest,plan)
  except ServiceError as error:self.fail('closed external blocker rejected: '+error.code)

 def test_closed_external_blocker_is_verified_without_adopting_or_mutating_it(self):
  plan,digest=self.external_plan();before=copy.deepcopy(self.native.rows)
  self.assertEqual(self.adopt_external(plan,digest)['state'],'published')
  self.assertEqual(self.store._published('p'),{'pilot-a'})
  self.assertEqual(self.native.rows,before)
  self.assertEqual(self.store.claim_request('claim','p','pilot-a','c')['phase'],'claimed')

 def test_external_blocker_reopened_between_readbacks_fences_publication(self):
  plan,digest=self.external_plan();original=self.store._verify_import
  def verify(*args):
   original(*args);self.native.rows['pilot-done']['status']='open'
  self.store._verify_import=verify
  self.assertEqual(self.adopt_external(plan,digest)['state'],'needs_reconciliation')
  self.assertFalse(any('--claim' in c for c in self.native.calls))

 def test_external_blocker_reopened_after_adoption_fences_claim(self):
  plan,digest=self.external_plan()
  self.assertEqual(self.adopt_external(plan,digest)['state'],'published')
  self.native.rows['pilot-done']['status']='open'
  self.assertEqual(self.store.claim_request('claim','p','pilot-a','c')['phase'],'needs_reconciliation')
  self.assertFalse(any('--claim' in c for c in self.native.calls))

class ReloadTests(unittest.TestCase):
 def test_changed_operator_document_revalidates_real_private_credentials(self):
  import json
  from unittest.mock import patch
  from task_tower.intake_reload import ConfigReloader
  from task_tower.service.cli import load_config,read_token
  from tests.test_service_api import private_token
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);token=root/'token';private_token(token,'a'*40)
   path=root/'operator.json'
   document=dict(version=1,executable=str(root/'bd'),projects={'p':tmp},journal=str(root/'journal'),
    connectors={'c':dict(token_file=str(token),projects=['p'])},approved_plans={'p':[]},port=0,poll_seconds=2)
   path.write_text(json.dumps(document),encoding='utf-8')
   old=load_config(path);reload=ConfigReloader(path,old,'approved_plans',load_config)
   with patch('task_tower.service.cli.read_token',wraps=read_token) as reads:
    reload();original=reload.document
    reload();self.assertEqual(reads.call_count,1)
    token.write_text('b'*40,encoding='ascii')
    document['approved_plans']['p']=['a'*64]
    path.write_text(json.dumps(document),encoding='utf-8')
    with self.assertRaises(ValueError):reload()
    self.assertEqual(reads.call_count,2)
    self.assertEqual(reload.current,old);self.assertEqual(reload.document,original)
    token.write_text('a'*40,encoding='ascii')
    self.assertEqual(reload()['approved_plans'],{'p':['a'*64]})

 def test_unchanged_document_does_not_repeat_credential_validation(self):
  from task_tower.intake_reload import ConfigReloader
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'operator.json';path.write_bytes(b'{"approved":1}')
   old={'projects':{'p':'root'},'approved_plans':{'p':[]}}
   loader=Mock(return_value=old)
   reload=ConfigReloader(path,old,'approved_plans',loader)
   self.assertEqual(reload(),old);self.assertEqual(reload(),old)
   self.assertEqual(loader.call_count,1)
   path.write_bytes(b'{"approved":2}')
   added=copy.deepcopy(old);added['approved_plans']['p']=['a']
   loader.return_value=added
   self.assertEqual(reload(),added);self.assertEqual(loader.call_count,2)
   loader.return_value={'projects':{'p':'foreign'},'approved_plans':{'p':['a']}}
   path.write_bytes(b'{"approved":3}')
   with self.assertRaises(ValueError):reload()
   self.assertEqual(reload.current,added)

 def test_assignments_append_only_and_scope_immutable(self):
  from task_tower.intake_reload import extend_config
  old={'projects':{'p':'trusted'},'assignments':[],'credential':'same'}
  new=copy.deepcopy(old);new['assignments']=[{'project_id':'p','bead_id':'pilot-a','base_sha':'a'*40}]
  self.assertEqual(extend_config(old,new,'assignments'),new)
  changed=copy.deepcopy(new);changed['assignments'][0]['base_sha']='b'*40
  with self.assertRaises(ValueError):extend_config(new,changed,'assignments')
  changed=copy.deepcopy(new);changed['projects']['p']='elsewhere'
  with self.assertRaises(ValueError):extend_config(new,changed,'assignments')
 def test_approvals_cannot_remove_or_expand_project_scope(self):
  from task_tower.intake_reload import extend_config
  old={'projects':{'p':'trusted'},'approved_plans':{'p':['a']}}
  new=copy.deepcopy(old);new['approved_plans']['p'].append('b')
  self.assertEqual(extend_config(old,new,'approved_plans'),new)
  with self.assertRaises(ValueError):extend_config(new,old,'approved_plans')
  new['approved_plans']['other']=['c']
  with self.assertRaises(ValueError):extend_config(old,new,'approved_plans')

class LiveReloadLoopTests(unittest.TestCase):
 def test_foreground_worker_picks_up_appended_assignment_without_restart(self):
  from unittest.mock import patch,MagicMock
  from task_tower.connector import cli
  cfg=dict(journal='unused',connector_id='host',projects={},endpoint='unused',token_file='unused',app_server='unused',assignments=[])
  added=copy.deepcopy(cfg);added['assignments']=[dict(project_id='p',bead_id='pilot-a',base_sha='a'*40,input={'text':'Approved'})]
  connector=MagicMock();connector.claim.return_value=None
  connector.tick.side_effect=[None,None,KeyboardInterrupt]
  with patch.object(cli,'ConnectorStore'),patch.object(cli,'Worktrees'),patch.object(cli,'APIClient'),patch.object(cli,'read_token'),patch.object(cli,'LifecycleConnector',return_value=connector),patch.object(cli,'load_config',side_effect=[cfg,added]),patch('task_tower.intake_reload.read_document',side_effect=[b'first',b'added']),patch.object(cli.time,'monotonic',side_effect=[0,0,3,3]),patch.object(cli.time,'sleep'):
   self.assertEqual(cli.work(cfg,config_path='operator-file'),4)
  connector.claim.assert_called_once_with('p','pilot-a')
 def test_service_loop_reloads_approvals_without_replacing_store(self):
  from unittest.mock import patch,MagicMock
  from threading import RLock
  from task_tower.service import cli
  cfg=dict(executable='unused',projects={'p':'root'},journal='unused',approved_plans={'p':[]},delivery_projects={},max_active_tasks=2,connectors={},port=0,poll_seconds=2)
  added=copy.deepcopy(cfg);added['approved_plans']['p']=['a'*64]
  store=MagicMock();store.lock=RLock();server=MagicMock()
  def handle():
   self.assertEqual(store.approved_plans,added['approved_plans']);raise KeyboardInterrupt
  server.handle_request.side_effect=handle
  with patch.object(cli,'load_config',side_effect=[cfg,added]),patch('task_tower.intake_reload.read_document',return_value=b'added'),patch.object(cli,'Beads'),patch.object(cli,'Store',return_value=store),patch.object(cli,'make_server',return_value=server):
   self.assertEqual(cli.main(['--config','operator-file']),0)
  store.close.assert_called_once()
