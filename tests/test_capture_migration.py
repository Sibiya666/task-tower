import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower.project_connections import ProjectConnection
from task_tower.capture_migration import migrate_card, migration_state, registry_path


class Store:
    def __init__(self): self.calls=[]; self.hook=None
    def import_card(self,path):
        self.calls.append((Path(path),Path(path).read_bytes()))
        if self.hook: self.hook()
        return dict(number=7,project_sync={'status':'synced'})


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.connection=ProjectConnection('p','owner/repo',self.root,'runner')
        self.path=self.root/'card.json'; self.raw=b'{"id":"legacy-1","title":"Old","evidence":{"snapshot_hash":"unchanged"}}\r\n'
        self.path.write_bytes(self.raw); self.store=Store()
        self.preflight=patch('task_tower.project_onboarding.preflight',return_value={'id':123})
        self.preflight.start(); self.addCleanup(self.preflight.stop)
    def migrate(self): return migrate_card(self.connection,self.path,store=self.store)
    def test_repeat_retains_source_and_private_snapshot(self):
        self.assertEqual(self.migrate()['status'],'migrated')
        self.assertEqual(self.migrate()['status'],'existing')
        self.assertEqual(len(self.store.calls),2)
        snapshot,raw=self.store.calls[0]
        self.assertNotEqual(snapshot,self.path); self.assertEqual(raw,self.raw)
        self.assertFalse(snapshot.exists()); self.assertEqual(self.path.read_bytes(),self.raw)
        state=migration_state(self.connection,self.path)
        self.assertEqual(state['status'],'current'); self.assertEqual(state['issue_url'],'https://github.com/owner/repo/issues/7')
        data=json.loads(registry_path(self.connection).read_text())
        self.assertNotIn('evidence',str(data)); self.assertNotIn('title',str(data))
    def test_source_drift_is_stale_and_never_reimported(self):
        self.migrate(); self.path.write_bytes(self.raw+b' ')
        self.assertEqual(migration_state(self.connection,self.path)['status'],'stale')
        self.assertEqual(self.migrate()['status'],'needs_input'); self.assertEqual(len(self.store.calls),1)
    def test_same_id_different_content_conflicts(self):
        self.migrate(); other=self.root/'other.json'; other.write_text('{"id":"legacy-1","title":"Different"}')
        self.assertEqual(migrate_card(self.connection,other,store=self.store)['status'],'needs_input')
        self.assertEqual(len(self.store.calls),1)
    def test_post_import_mutation_is_recoverable_without_publication(self):
        self.store.hook=lambda:self.path.write_bytes(self.raw+b' ')
        result=self.migrate(); self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['issue_url'],'https://github.com/owner/repo/issues/7')
        self.assertEqual(migration_state(self.connection,self.path)['status'],'stale')
        self.assertEqual(self.migrate()['status'],'needs_input'); self.assertEqual(len(self.store.calls),1)
    def test_hardlink_rejected_without_import(self):
        alias=self.root/'alias.json'; os.link(self.path,alias)
        with self.assertRaises(ValueError): self.migrate()
        self.assertEqual(self.store.calls,[])
    def test_registry_alias_rejected_without_overwrite(self):
        target=registry_path(self.connection); target.parent.mkdir(); os.link(self.path,target)
        with self.assertRaises(ValueError): self.migrate()
        self.assertEqual(self.path.read_bytes(),self.raw); self.assertEqual(self.store.calls,[])
    def test_registry_drift_during_import_does_not_clobber(self):
        def change(): registry_path(self.connection).write_bytes(b'foreign')
        self.store.hook=change
        result=self.migrate(); self.assertEqual(result['status'],'needs_input')
        self.assertEqual(registry_path(self.connection).read_bytes(),b'foreign')
    def test_descriptor_replacement_during_validation_rejected(self):
        import task_tower.capture_migration as module
        original=module._read_source
        def replace(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            alternate=self.root/'replacement'; alternate.write_bytes(self.raw); os.replace(alternate,self.path)
            return result
        with patch.object(module,'_read_source',side_effect=replace):
            with self.assertRaises(ValueError): self.migrate()
        self.assertEqual(self.store.calls,[])

    def test_cli_migrate_delegates_and_protects_config(self):
        import io
        from task_tower import capture_cli
        config=self.root/'connections.json'; config.write_bytes(self.raw)
        base=['--connections',str(config),'--project','p','migrate','--card']
        with patch.object(capture_cli,'load_connections',return_value=[self.connection]), patch.object(capture_cli,'migrate_card',return_value={'status':'migrated'}) as call, patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(capture_cli.run(base+[str(self.path)]),0)
            with patch('sys.stderr',new_callable=io.StringIO): self.assertEqual(capture_cli.run(base+[str(config)]),2)
            self.assertEqual(call.call_count,1)
    def test_books_projects_stale_without_private_paths_or_duplicate(self):
        from task_tower.books import aggregate,render_html
        self.migrate(); self.path.write_bytes(self.raw+b' ')
        store=Store(); store.list_issues=lambda:[dict(number=7,title='Canonical',body='',state='closed')]
        report=aggregate([self.connection],store_factory=lambda connection:store)
        self.assertEqual(len(report['entries']),1)
        self.assertEqual(report['entries'][0]['migrations'][0]['status'],'stale')
        self.assertNotIn(str(self.path),json.dumps(report))
        self.assertIn('stale',render_html(report))
        self.assertNotEqual(report['entries'][0]['status'],'done')

    def test_retry_repairs_project_and_revalidates_repository(self):
        self.store.hook=None
        original=self.store.import_card
        self.store.import_card=lambda path:dict(original(path),project_sync={'status':'unavailable'})
        self.assertEqual(self.migrate()['status'],'needs_input')
        self.store.import_card=original
        self.assertEqual(self.migrate()['status'],'existing')
        self.assertEqual(len(self.store.calls),2)
    def test_source_replacement_after_preflight_is_rejected(self):
        def replacement(*args):
            alternate=self.root/'other'; alternate.write_bytes(self.raw); os.replace(alternate,self.path)
            return {'id':123}
        with patch('task_tower.project_onboarding.preflight',side_effect=replacement):
            with self.assertRaises(ValueError): self.migrate()
        self.assertEqual(self.store.calls,[])
    def test_interrupted_publication_retry_uses_existing_import_identity(self):
        import task_tower.capture_migration as module
        original=module._publish
        count=[0]
        def interrupt(*args):
            count[0]+=1
            if count[0]==2: raise OSError('interrupted')
            return original(*args)
        with patch.object(module,'_publish',side_effect=interrupt):
            self.assertEqual(self.migrate()['status'],'needs_input')
        self.assertEqual(migration_state(self.connection,self.path)['status'],'pending')
        self.assertEqual(self.migrate()['status'],'migrated')
        self.assertEqual(self.store.calls[0][1],self.store.calls[1][1])

    def test_books_output_cannot_replace_registry(self):
        from task_tower.books import _output_path
        self.migrate(); target=registry_path(self.connection); before=target.read_bytes()
        with self.assertRaises(ValueError): _output_path(target,(),True,[self.root])
        self.assertEqual(target.read_bytes(),before)


class RealImportMigrationTests(unittest.TestCase):
    def test_existing_import_journal_recovers_one_post_with_historical_evidence(self):
        from test_project_onboarding import ImportTests
        fixture=ImportTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        fixture.unknown_post=True
        before=fixture.card.read_bytes()
        first=migrate_card(fixture.connection,fixture.card,store=fixture.store())
        second=migrate_card(fixture.connection,fixture.card,store=fixture.store())
        self.assertEqual(first['number'],24); self.assertEqual(second['number'],24)
        self.assertEqual(fixture.posts,1); self.assertEqual(fixture.card.read_bytes(),before)
        self.assertEqual(fixture.store().metadata(fixture.issues[0])['legacy_card'],json.loads(before))
    def test_active_worker_card_loader_and_evidence_hashes_survive(self):
        import hashlib
        from test_tasks import TaskTests
        from task_tower.tasks import load_task
        fixture=TaskTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        before=fixture.card.read_bytes(); evidence=fixture.evidence.read_bytes()
        loaded=load_task(fixture.card)
        connection=ProjectConnection('p','owner/repo',fixture.root,'runner')
        with patch('task_tower.project_onboarding.preflight',return_value={'id':123}):
            migrate_card(connection,fixture.card,store=Store())
        self.assertEqual(load_task(fixture.card),loaded)
        self.assertEqual(hashlib.sha256(fixture.card.read_bytes()).digest(),hashlib.sha256(before).digest())
        self.assertEqual(fixture.evidence.read_bytes(),evidence)

    def test_two_processes_preserve_independent_registry_records(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for identity in ('one','two'): (root/(identity+'.json')).write_text(json.dumps({'id':identity}))
            script='''import sys,time
from pathlib import Path
from unittest.mock import patch
from task_tower.project_connections import ProjectConnection
from task_tower.capture_migration import migrate_card
root=Path(sys.argv[1]); identity=sys.argv[2]
class Store:
 def import_card(self,path):
  time.sleep(.1)
  return dict(number=1 if identity=='one' else 2,project_sync={'status':'synced'})
with patch('task_tower.project_onboarding.preflight',return_value={'id':123}):
 result=migrate_card(ProjectConnection('p','owner/repo',root,'runner'),root/(identity+'.json'),store=Store())
 assert result['status']=='migrated',result
'''
            processes=[subprocess.Popen([sys.executable,'-c',script,str(root),identity],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for identity in ('one','two')]
            for process in processes:
                stdout,stderr=process.communicate(timeout=20)
                self.assertEqual(process.returncode,0,(stdout,stderr))
            connection=ProjectConnection('p','owner/repo',root,'runner')
            self.assertEqual(len(json.loads(registry_path(connection).read_text())['records']),2)

class PublicationGuardTests(unittest.TestCase):
    setUp=MigrationTests.setUp
    migrate=MigrationTests.migrate
    def test_mutation_during_final_publication_is_rejected(self):
        import task_tower.capture_migration as module
        original=module._publish
        count=[0]
        def mutate(*args):
            count[0]+=1
            if count[0]==2: self.path.write_bytes(self.raw+b' ')
            return original(*args)
        with patch.object(module,'_publish',side_effect=mutate): result=self.migrate()
        self.assertEqual(result['status'],'needs_input')
        self.assertIsNone(json.loads(registry_path(self.connection).read_text())['records'][0]['number'])

class MigrationRelationshipTests(unittest.TestCase):
    setUp=MigrationTests.setUp
    migrate=MigrationTests.migrate
    def test_mapped_issue_retains_native_parent_and_milestone_projection(self):
        from task_tower.books import aggregate
        from test_capture import Store as Remote
        self.migrate()
        store=Remote()
        store.issues=[dict(number=7,title='Canonical',body='',milestone=dict(number=2,title='Stage'))]
        def request(method,path,payload=None):
            if path.endswith('/parent'): return dict(number=3,html_url='https://github.com/owner/repo/issues/3')
            if '/sub_issues?' in path: return []
            raise ValueError()
        store.request=request
        entry=aggregate([self.connection],store_factory=lambda connection:store)['entries'][0]
        self.assertEqual(entry['relationships']['parent']['id'],'owner/repo#3')
        self.assertEqual(entry['relationships']['milestone']['number'],2)

    def test_missing_canonical_issue_is_visible_source_error(self):
        from task_tower.books import aggregate
        self.migrate()
        store=Store(); store.list_issues=lambda:[]
        report=aggregate([self.connection],store_factory=lambda connection:store)
        self.assertEqual(report['entries'],[])
        self.assertTrue(any('canonical' in row['error'].lower() for row in report['errors']))
