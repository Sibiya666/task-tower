import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from task_tower.executor_profiles import profile_fingerprint
from task_tower.github_tasks import replace_metadata
from task_tower.pipeline_policy import load_pipeline_config, criteria_snapshot, admission_authorized, continuation_authorized

class PipelinePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); checkout=self.root/'checkout'; checkout.mkdir()
        pins=self.root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('rules',encoding='utf-8')
        import hashlib
        manifest={'SKILL.md':hashlib.sha256(b'rules').hexdigest()}
        self.profile=dict(kind='codex',repository='Owner/Repo',checkout=str(checkout),runner_label='local',superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)),timeout_seconds=60,log_max_bytes=4096)
        self.connections=[SimpleNamespace(repository='Owner/Repo',checkout=checkout,runner_label='local',trusted_publishers=['owner'])]
        self.executor=dict(profiles={'local':self.profile},allowlist=[dict(repository='Owner/Repo',issue=16,task_id='TT-PIPELINE-001',runner_label='local',profile='local')])
        self.row=dict(repository='Owner/Repo',issue=16,task_id='TT-PIPELINE-001',runner_label='local',executor_profile='local',components=['core'],allowed_paths=['src/','docs/'],spec_path='docs/spec.md',plan_path='docs/plan.md',evidence_dir='docs/evidence/',checks=[dict(id='unit',argv=[str(Path(sys.executable).resolve()),'-m','unittest'],timeout_seconds=60)],ci_substitution=dict(enabled=False,required_platforms=[]),publish=dict(enabled=False,remote='origin',base_ref='refs/heads/main',publisher_account='owner'))
        self.value=dict(version=1,tasks=[self.row]); self.path=self.root/'pipeline.json'
        import subprocess
        def git(*args): return subprocess.check_output(['git',*args],cwd=checkout,stderr=subprocess.DEVNULL).decode().strip()
        git('init','-b','main'); git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','fixture')
        self.sha=git('rev-parse','HEAD'); self.profile['source_ref']='refs/heads/main'
    def load(self):
        self.path.write_text(json.dumps(self.value),encoding='utf-8')
        result=load_pipeline_config(self.path,self.connections,self.executor)
        result['_authority_check']=lambda:True
        return result
    def test_defaults_and_strict_bounds(self):
        result=self.load()
        for key,value in dict(max_active=2,interval_seconds=5,task_timeout_seconds=7200,role_timeout_seconds=900,max_reworks=2,max_processes=36,log_max_bytes=1048576).items(): self.assertEqual(result[key],value)
        for key,value in [('max_active',True),('max_active',3),('max_processes',5),('max_reworks',6),('extra',1)]:
            self.value[key]=value
            with self.assertRaises(ValueError): self.load()
            del self.value[key]
    def test_alias_and_policy_escalation_rejected(self):
        for key,value in [('allowed_paths',['../src/']),('allowed_paths',['docs/','docs/spec.md']),('components',['core','core']),('components',['*','core']),('publisher_account','attacker'),('issue',17),('spec_path','outside.md')]:
            target=self.row['publish'] if key=='publisher_account' else self.row
            old=target[key]; target[key]=value
            with self.assertRaises(ValueError): self.load()
            target[key]=old
        self.path.write_text('{"version":1,"version":1,"tasks":[]}',encoding='utf-8')
        with self.assertRaises(ValueError): load_pipeline_config(self.path,self.connections,self.executor)
    def test_criteria_excludes_only_mutable_metadata(self):
        meta=dict(version=1,kind='task',mode='autonomous',task_id='TT-PIPELINE-001',status='open',blocked_by=['O/R#2','O/R#1'])
        issue=dict(number=16,id=123,title='Title\r\n',body=replace_metadata('Actual\rprose',meta))
        original=criteria_snapshot(issue,meta,'Owner/Repo')
        changed=dict(meta,status='running',phase='development',blocked_by=list(reversed(meta['blocked_by'])))
        self.assertEqual(original,criteria_snapshot(dict(issue,body=replace_metadata('Actual\nprose',changed)),changed,'Owner/Repo'))
        for key,value in [('title','changed'),('id',124),('body',replace_metadata('changed',meta))]:
            self.assertNotEqual(original,criteria_snapshot(dict(issue,**{key:value}),meta,'Owner/Repo'))
        for malformed in [dict(issue,body=issue['body']+issue['body']),dict(issue,body='no metadata')]:
            with self.assertRaises(ValueError): criteria_snapshot(malformed,meta,'Owner/Repo')
    def test_strict_paths_checks_profiles_and_duplicate_mappings(self):
        for key,value in [('allowed_paths',['docs//']),('allowed_paths',['.git/config']),('allowed_paths',['C:/source/']),('allowed_paths',['src\\file']),('components',[]),('checks',[dict(id='unit',argv=['python'],timeout_seconds=1)]),('ci_substitution',dict(enabled=True,required_platforms=[])),('evidence_dir','docs/spec.md/')]:
            old=self.row[key]; self.row[key]=value
            with self.assertRaises(ValueError): self.load()
            self.row[key]=old
        self.value['tasks'].append(dict(self.row))
        with self.assertRaises(ValueError): self.load()
        self.value['tasks'].pop()
        (self.root/'pins'/'SKILL.md').write_text('drift',encoding='utf-8')
        with self.assertRaises(ValueError): self.load()
    def test_criteria_dependency_presence_and_metadata_duplicates(self):
        meta=dict(version=1,kind='task',mode='autonomous',task_id='TT-PIPELINE-001',status='open')
        issue=dict(number=16,id=123,title='Title',body=replace_metadata('Text\ufeff\r\n',meta))
        a=criteria_snapshot(issue,meta,'Owner/Repo')
        other=dict(meta,blocked_by=[])
        self.assertNotEqual(a,criteria_snapshot(dict(issue,body=replace_metadata('Text\ufeff\n',other)),other,'Owner/Repo'))
        duplicate=issue['body'].replace('"version": 1','"version": 1, "version": 1')
        with self.assertRaises(ValueError): criteria_snapshot(dict(issue,body=duplicate),meta,'Owner/Repo')
    def snapshot(self,status='open',comments=None):
        meta=dict(version=1,kind='task',mode='autonomous',task_id='TT-PIPELINE-001',status=status)
        issue=dict(number=16,id=123,state='open',title='Build pipeline',body=replace_metadata('Actual task',meta))
        class Store:
            def metadata(self,row):
                from task_tower.github_tasks import parse_metadata
                return parse_metadata(row['body'])
            def request(store,method,path): return dict(object=dict(sha=self.sha)) if path=='/git/ref/heads/main' else (comments or [])
            def get(self,number): return issue
        return {'owner/repo':dict(connection=self.connections[0],store=Store(),source=object(),issues={16:issue},index={'TT-PIPELINE-001':[16]},metadata={16:meta},error=None)}
    def test_initial_ready_requires_genuine_selection_and_fresh_private_policy(self):
        config=self.load(); task=config['tasks'][0]
        evidence=admission_authorized(config,task,self.snapshot())
        self.assertEqual(evidence['issue_id'],123)
        self.assertIsNone(admission_authorized(config,task,self.snapshot('running')))
        self.assertIsNone(admission_authorized(config,task,self.snapshot(comments=[dict(id=1,user=dict(login='owner'),body='<!-- task-tower:lifecycle:v1\n'+json.dumps(dict(status='running',remote_attempt=dict(run_id='other')))+'\n-->')])))
        changed=self.snapshot(); changed['owner/repo']['index']['TT-PIPELINE-001'].append(17)
        self.assertIsNone(admission_authorized(config,task,changed))
        self.path.write_text(self.path.read_text(encoding='utf-8')+' ',encoding='utf-8')
        self.assertIsNone(admission_authorized(config,task,self.snapshot()))
    def test_limits_reject_every_boolean_and_boundary(self):
        from task_tower.pipeline_policy import LIMITS
        for key,(default,low,high) in LIMITS.items():
            for invalid in (False,True,low-1,high+1,1.0,'1'):
                self.value[key]=invalid
                with self.subTest(key=key,value=invalid),self.assertRaises(ValueError): self.load()
            for valid in (low,high):
                self.value[key]=valid
                self.assertEqual(self.load()[key],valid)
            del self.value[key]
    def test_private_pipeline_alias_and_pin_revocation(self):
        import os
        source=self.path; self.load()
        alias=self.root/'alias.json'
        os.link(source,alias)
        with self.assertRaises(ValueError): load_pipeline_config(source,self.connections,self.executor)
        alias.unlink()
        config=self.load(); task=config['tasks'][0]
        (self.root/'pins'/'SKILL.md').write_text('revoked',encoding='utf-8')
        self.assertIsNone(admission_authorized(config,task,self.snapshot()))
    def test_admission_requires_host_authority_and_current_main(self):
        config=self.load(); task=config['tasks'][0]
        del config['_authority_check']
        self.assertIsNone(admission_authorized(config,task,self.snapshot()))
        config['_authority_check']=lambda:True
        snapshot=self.snapshot(); snapshot['owner/repo']['store'].request=lambda method,path: dict(object=dict(sha='b'*40)) if path=='/git/ref/heads/main' else []
        self.assertIsNone(admission_authorized(config,task,snapshot))
    def owned_run(self,snapshot=None):
        from task_tower.pipeline_journal import PipelineJournal
        import uuid
        config=self.load(); task=config['tasks'][0]
        admission=admission_authorized(config,task,snapshot or self.snapshot())
        journal=PipelineJournal(self.root/'journal.sqlite3',checkouts=(self.connections[0].checkout,))
        envelope=dict(profile_id='local',profile_fingerprint=admission['profile_fingerprint'],policy_sha256=config['policy_sha256'],component_keys=['core'],limits={key:config[key] for key in ('task_timeout_seconds','max_processes','max_reworks','role_timeout_seconds','log_max_bytes')})
        journal.submit(dict(operation='submit',delivery_id=str(uuid.uuid4()),**{key:(task[key].casefold() if key=='repository' else task[key]) for key in ('repository','issue','task_id','runner_label')}),envelope)
        owner=str(uuid.uuid4()); run=journal.claim(owner,2)
        expected={key:run[key] for key in ('state','stage','generation','input_sha256')}
        transition=dict(state='preparing',admission=admission,issue_id=admission['issue_id'],criteria_sha256=admission['criteria_sha256'],source_sha=admission['source_sha'],base_sha=admission['base_sha'])
        journal.record(run['run_id'],owner,expected,transition)
        config['_journal']=journal; config['_owner_id']=owner
        return config,journal.status(run['run_id'])
    def test_initial_ready_and_owned_continuation_are_distinct(self):
        config,run=self.owned_run()
        self.assertTrue(continuation_authorized(config,run,self.snapshot('running')))
        self.assertIsNone(admission_authorized(config,run,self.snapshot('running')))
        import copy
        forged=copy.deepcopy(run); forged['delivery_id']='00000000-0000-0000-0000-000000000000'
        self.assertFalse(continuation_authorized(config,forged,self.snapshot('running')))
        config['_owner_id']='00000000-0000-0000-0000-000000000000'
        self.assertFalse(continuation_authorized(config,run,self.snapshot('running')))
    def test_foreign_lifecycle_revocation_and_dependency_loss_block(self):
        config,run=self.owned_run()
        self.assertTrue(continuation_authorized(config,run,self.snapshot()))
        comments=[dict(id=1,user=dict(login='owner'),body='<!-- task-tower:lifecycle:v1\n'+json.dumps(dict(status='running',remote_attempt=dict(run_id=run['run_id'])))+'\n-->')]
        self.assertFalse(continuation_authorized(config,run,self.snapshot(comments=comments)))
        for status in ('done','cancelled','needs_input','blocked'):
            self.assertFalse(continuation_authorized(config,run,self.snapshot(status)))
        changed=self.snapshot(); changed['owner/repo']['issues'][16]['state']='closed'
        self.assertFalse(continuation_authorized(config,run,changed))
        changed=self.snapshot(); meta=changed['owner/repo']['metadata'][16]; meta['blocked_by']=['Other/Repo#1']; changed['owner/repo']['issues'][16]['body']=replace_metadata('Actual task',meta)
        self.assertFalse(continuation_authorized(config,run,changed))
        config['_authority_check']=lambda:False
        self.assertFalse(continuation_authorized(config,run,self.snapshot()))
    def dependency_snapshot(self):
        import hashlib,io,zipfile
        from task_tower.github_tasks import parse_metadata
        snapshot=self.snapshot(); project=snapshot['owner/repo']; original=project['store']
        meta=project['metadata'][16]; meta['blocked_by']=['Owner/Repo#15']
        project['issues'][16]['body']=replace_metadata('Actual task',meta)
        depmeta=dict(version=1,kind='task',task_id='TT-DEPENDENCY-001',status='done',remote_attempt=dict(status='done',run_id='41'))
        dependency=dict(number=15,id=122,state='closed',title='Dependency',body=replace_metadata('Done',depmeta))
        project['issues'][15]=dependency; project['metadata'][15]=depmeta; project['index']['TT-DEPENDENCY-001']=[15]
        bundle=dict(merge_commit='a'*40,task_ids=['TT-DEPENDENCY-001'],platforms=dict(linux='passed'))
        receipt=dict(repository='Owner/Repo',issue=15,run_id='41',run_attempt='1',bundle=bundle,review=dict(verdict='approve',commit='a'*40,task_id='TT-DEPENDENCY-001'),required_platforms=['linux'],policy=dict(reviewer='postmerge-agent',executor='dev',superpowers_sha256='c'*64))
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as archive: archive.writestr('15.json',json.dumps(receipt))
        packed=raw.getvalue(); artifact=dict(id=1,name='task-tower-review-15-1',expired=False,digest='sha256:'+hashlib.sha256(packed).hexdigest(),workflow_run=dict(id=41,head_sha='b'*40))
        source=SimpleNamespace(_pages=lambda *a:[artifact],_get=lambda *a,**k:packed,_id=lambda n:n,poll=lambda:[bundle])
        class Store:
            def metadata(store,row): return parse_metadata(row['body'])
            def get(store,number): return project['issues'][number]
            def request(store,method,path):
                if path=='/git/ref/heads/main': return original.request(method,path)
                if '/comments?' in path: return []
                if '/compare/' in path: return dict(status='ahead')
                if '/actions/runs/' in path: return dict(status='completed',run_attempt=1,event='workflow_dispatch',head_branch='main',path='.github/workflows/task-tower-project.yml',repository=dict(full_name='Owner/Repo'),head_sha='b'*40)
                raise AssertionError(path)
        project['store']=Store(); project['source']=source
        return snapshot,artifact
    def test_fresh_real_dependency_receipt_loss_blocks_owned_run(self):
        snapshot,artifact=self.dependency_snapshot()
        config,run=self.owned_run(snapshot)
        self.assertTrue(continuation_authorized(config,run,snapshot))
        artifact['digest']='sha256:forged'
        self.assertFalse(continuation_authorized(config,run,snapshot))
        self.assertIsNone(admission_authorized(config,run,snapshot))
    def test_owned_continuation_rechecks_source_main_criteria_and_cancel(self):
        config,run=self.owned_run()
        snapshot=self.snapshot(); store=snapshot['owner/repo']['store']; request=store.request
        store.request=lambda method,path: dict(object=dict(sha='f'*40)) if path=='/git/ref/heads/main' else request(method,path)
        self.assertFalse(continuation_authorized(config,run,snapshot))
        for field,value in [('title','changed'),('id',124),('body',replace_metadata('changed',self.snapshot()['owner/repo']['metadata'][16]))]:
            snapshot=self.snapshot(); snapshot['owner/repo']['issues'][16][field]=value
            self.assertFalse(continuation_authorized(config,run,snapshot))
        config['_journal'].cancel(run['run_id'])
        current=config['_journal'].status(run['run_id'])
        self.assertFalse(continuation_authorized(config,current,self.snapshot()))
    def test_active_policy_mutation_and_forged_task_cannot_reuse_digest(self):
        import copy
        for mutate in (lambda c:c['tasks'][0]['publish'].update(enabled=True),lambda c:c['tasks'][0].update(allowed_paths=['outside/']),lambda c:c.update(max_processes=1000000)):
            config=self.load(); trusted=copy.deepcopy(config['tasks'][0]); mutate(config)
            self.assertIsNone(admission_authorized(config,trusted,self.snapshot()))
        config=self.load(); forged=copy.deepcopy(config['tasks'][0]); forged['publish']['enabled']=True
        self.assertIsNone(admission_authorized(config,forged,self.snapshot()))
    def test_windows_aliases_and_reserved_components_are_rejected_everywhere(self):
        for path in ('docs./','docs /','docs/file.','docs/file ','docs/aux','docs/COM1.txt','docs/lpt9','docs/NUL','docs/conin$','docs/x\x01y'):
            from task_tower.pipeline_policy import _relative
            with self.subTest(path=path),self.assertRaises(ValueError): _relative(path)
            original=self.row['allowed_paths']; self.row['allowed_paths']=['src/','docs/',path]
            with self.subTest(path=path),self.assertRaises(ValueError): self.load()
            self.row['allowed_paths']=original
    def test_valid_unicode_paths_and_active_continuation_binding(self):
        self.row.update(allowed_paths=['src/','документы/'],spec_path='документы/спецификация.md',plan_path='документы/план.md',evidence_dir='документы/свидетельства/')
        config,run=self.owned_run()
        self.assertTrue(continuation_authorized(config,run,self.snapshot()))
        config['tasks'][0]['publish']['enabled']=True
        self.assertFalse(continuation_authorized(config,run,self.snapshot()))
    def test_active_profile_connection_and_private_binding_mutations_block(self):
        for kind in ('profile','connection','executor','extra'):
            config=self.load(); trusted=config['tasks'][0]
            if kind=='profile': config['profiles']['local']['checkout']=str(self.root)
            elif kind=='connection': self.connections[0].trusted_publishers.append('foreign')
            elif kind=='executor': config['_executor_config']['allowlist'].clear()
            else: config['outside_authority']=True
            self.assertIsNone(admission_authorized(config,trusted,self.snapshot()))
            if kind=='connection': self.connections[0].trusted_publishers.pop()
