"""Existing-only private registration boundaries; no execution authority."""
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_group_policy as policy_fixtures
from task_tower.pipeline_journal import PipelineJournal
from tests.test_pipeline_journal import request, policy

class RegistrationContextTests(unittest.TestCase):
    def setUp(self):
        f=policy_fixtures.GroupPolicyTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.c=f.root/'connections.json'
        self.c.write_text(json.dumps(dict(version=1,projects=[dict(id='r',repository='Owner/Repo',checkout=str(f.checkout),runner_label='local',trusted_publishers=['publisher'])])),encoding='utf-8')
        raw=json.loads(f.executor_path.read_text());raw['version']=2
        raw['harness_resources']={'local':dict(pool_id='local',cpu_millis=1000,memory_bytes=1048576,max_parallel=None)}
        f.executor_path.write_text(json.dumps(raw),encoding='utf-8')
        f.pipeline_path.write_text(json.dumps(dict(version=2,tasks=[f.task])),encoding='utf-8')
        f.value['version']=2;f.path.write_text(json.dumps(f.value),encoding='utf-8')
        self.j=PipelineJournal(Path(f.value['canonical_journal']))
    def load(self):
        module=importlib.import_module('task_tower.group_registration')
        return module.load_registration_context(self.f.path,self.c,self.f.pipeline_path,self.f.executor_path,self.j)
    def seed(self):
        self.j.submit(dict(request(),repository='owner/repo',runner_label='local'),policy());self.j.migrate_groups()
    def test_context_requires_existing_journal_without_initialization(self):
        with self.assertRaises(ValueError):self.load()
        self.assertFalse(self.j.path.exists())
    def test_context_uses_actual_loaders_and_retains_source_bytes(self):
        self.seed()
        with self.load() as ctx:
            self.assertIs(ctx.journal,self.j)
            self.assertEqual(ctx.policy['version'],2)
            self.assertEqual(ctx.policy['canonical_journal'],str(self.j.path))
            ctx.revalidate()
            self.f.executor_path.write_bytes(self.f.executor_path.read_bytes()+b' ')
            with self.assertRaises(ValueError):ctx.revalidate()
        with self.assertRaises(ValueError):ctx.revalidate()
    def test_context_rejects_source_aliases_and_wrong_journal(self):
        self.seed(); self.f.value['canonical_journal']=str(self.f.root/'other.sqlite3')
        self.f.path.write_text(json.dumps(self.f.value),encoding='utf-8')
        with self.assertRaises(ValueError):self.load()
    def test_context_rejects_unmigrated_v1_without_mutation(self):
        self.j.submit(request(),policy());before=self.j.path.read_bytes()
        with self.assertRaises(ValueError):self.load()
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_registration_is_atomic_idempotent_and_metadata_only(self):
        self.seed(); before=self.j.status()
        with self.load() as ctx:
            result=self.j.register_groups(ctx)
            self.assertEqual(result['status'],'registered')
            self.assertEqual(self.j.register_groups(ctx)['status'],'already_registered')
        metadata=self.j.registered_groups()
        self.assertEqual(metadata['installation_id'],self.f.value['installation_id'])
        self.assertEqual(metadata['current_capacity_epoch'],1)
        self.f.path.unlink()
        self.assertEqual(self.j.registered_groups(),metadata)
        self.assertEqual(self.j.status()['runs'],before['runs'])
        with self.assertRaises(ValueError):self.j.submit(request(2),policy())
        with self.assertRaises(ValueError):self.j.claim('00000000-0000-4000-8000-000000000002',2)

    def test_capacity_append_does_not_rewrite_prior_epoch(self):
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        with contextlib.closing(__import__('sqlite3').connect(self.j.path)) as db:
            original=db.execute('SELECT * FROM group_capacity_epochs').fetchall()
        self.f.value['capacity']=dict(mode='auto',max_executors=3,max_inflight=None,max_cpu_millis=None,max_memory_bytes=None,fallback=None)
        self.f.path.write_text(json.dumps(self.f.value),encoding='utf-8')
        with self.load() as ctx:self.assertEqual(self.j.register_groups(ctx)['status'],'capacity_only')
        with contextlib.closing(__import__('sqlite3').connect(self.j.path)) as db:
            self.assertEqual(db.execute('SELECT * FROM group_capacity_epochs WHERE epoch=1').fetchall(),original)
        self.assertEqual(self.j.registered_groups()['current_capacity_epoch'],2)
    def test_self_consistent_registration_event_tamper_is_refused(self):
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        from task_tower.pipeline_inputs import canonical_json,digest_manifest
        with contextlib.closing(__import__('sqlite3').connect(self.j.path)) as db:
            sequence,raw=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='binding'").fetchone()
            body=json.loads(raw);body['epoch']['effective_maximum']=999
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',(canonical_json(body).decode(),digest_manifest(body),sequence));db.commit()
        with self.assertRaises(ValueError):self.j.status()

    def test_known_binding_missing_j_never_initializes(self):
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        self.j.registered_groups()
        self.j.path.unlink()
        for operation in (self.j.status,lambda:self.j.submit(request(2),policy()),lambda:self.j.claim('00000000-0000-4000-8000-000000000002',2)):
            with self.assertRaises((ValueError,OSError)):operation()
            self.assertFalse(self.j.path.exists())

    def test_boolean_epoch_in_self_hashed_event_is_refused(self):
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        from task_tower.pipeline_inputs import canonical_json,digest_manifest
        with contextlib.closing(__import__('sqlite3').connect(self.j.path)) as db:
            sequence,raw=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='binding'").fetchone()
            body=json.loads(raw);body['epoch']['epoch']=True
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',(canonical_json(body).decode(),digest_manifest(body),sequence));db.commit()
        with self.assertRaises(ValueError):self.j.status()

    def test_cli_explicit_registration_and_status_are_sanitized(self):
        import io
        from task_tower import pipeline
        self.seed();output=io.StringIO()
        args=['register-groups','--connections',str(self.c),'--journal',str(self.j.path),'--config',str(self.f.pipeline_path),'--executor-config',str(self.f.executor_path),'--groups-config',str(self.f.path),'--apply']
        with contextlib.redirect_stdout(output),patch('subprocess.Popen',side_effect=AssertionError('Unexpected child')):
            self.assertEqual(pipeline.main(args),0)
        result=json.loads(output.getvalue());self.assertEqual(result['status'],'registered')
        self.assertNotIn(str(self.f.root),output.getvalue())
        self.f.path.unlink();self.f.executor_path.unlink();self.f.pipeline_path.unlink()
        output=io.StringIO()
        with contextlib.redirect_stdout(output):self.assertEqual(pipeline.main(['status','--connections',str(self.c),'--journal',str(self.j.path)]),0)
        result=json.loads(output.getvalue());self.assertEqual(result['registration']['installation_id'],self.f.value['installation_id'])
        self.assertNotIn(str(self.f.root),output.getvalue())

    def test_self_consistent_unknown_task_field_is_refused_offline(self):
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        from task_tower.pipeline_inputs import canonical_json,digest_manifest
        with contextlib.closing(__import__('sqlite3').connect(self.j.path)) as db:
            sequence,raw=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='binding'").fetchone();body=json.loads(raw)
            snapshot=body['policy_snapshot'];snapshot['authorization']['tasks'][0]['invented_authority']=True
            h=digest_manifest(snapshot['authorization']);snapshot['group']['authorization_sha256']=h
            body['epoch']['authorization_sha256']=h;body['installation']['current_authorization_sha256']=h
            db.execute('UPDATE group_capacity_epochs SET authorization_sha256=?',(h,));db.execute('UPDATE group_installation SET current_authorization_sha256=?',(h,))
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',(canonical_json(body).decode(),digest_manifest(body),sequence));db.commit()
        with self.assertRaises(ValueError):self.j.status()

    def test_registered_direct_v1_execution_entries_are_closed(self):
        from task_tower import pipeline,pipeline_roles,pipeline_publish,pipeline_worker
        from task_tower.group_registration import RegistrationUnavailable
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        config={'version':1}
        calls=[lambda:pipeline.work(config,self.j),lambda:pipeline.watch(config,self.j),
               lambda:pipeline._action(config,self.j),lambda:pipeline._dispatch(config,self.j),
               lambda:pipeline.watch_tick(config,self.j),lambda:pipeline_worker.step(config,self.j),
               lambda:pipeline_roles.run_role(config,{}, {},'spec_executor',self.j,'unused'),
               lambda:pipeline_roles.run_checks(config,{}, {},self.j,'unused'),
               lambda:pipeline_publish.publish_one(config,{},self.j,'unused')]
        with patch.object(pipeline,'_require_native_execution'),patch.object(self.j,'recover',side_effect=AssertionError('Recovery reached')),patch.object(self.j,'claim_controller',side_effect=AssertionError('Owner reached')):
            for call in calls:
                with self.subTest(call=call),self.assertRaises(RegistrationUnavailable):call()

    def test_registered_adapter_submit_returns_original_unknown_protocol(self):
        from task_tower import pipeline
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        req=dict(request(),version=1)
        # validate_request expects the existing operation protocol, not added policy authority.
        req.pop('version')
        result=pipeline.adapter(req,{'version':1},self.j)
        self.assertEqual(result,dict(version=1,delivery_id=req['delivery_id'],status='unknown'))

    def test_fresh_missing_v2_journal_never_falls_back_to_legacy(self):
        from task_tower.group_registration import guard_execution
        with self.assertRaises(ValueError):guard_execution(self.j,{'version':2})
        self.assertFalse(self.j.path.exists())

    def test_cli_work_explicit_and_discovered_binding_reloads_before_effects(self):
        import io
        from task_tower import pipeline
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        argv=['work','--connections',str(self.c),'--journal',str(self.j.path),'--config',str(self.f.pipeline_path),'--executor-config',str(self.f.executor_path),'--once']
        before=self.j.path.read_bytes()
        for flags in ([],['--groups-config',str(self.f.path)]):
            with self.subTest(flags=flags),contextlib.redirect_stdout(io.StringIO()) as output,patch.object(pipeline,'_require_native_execution'),patch.object(pipeline,'_Host',side_effect=AssertionError('Host reached')):
                self.assertEqual(pipeline.main(argv+flags),1)
                self.assertEqual(json.loads(output.getvalue())['reason'],'group_runtime_unavailable')
        self.f.pipeline_path.unlink()
        with contextlib.redirect_stdout(io.StringIO()) as output,patch.object(pipeline,'_require_native_execution'):
            self.assertEqual(pipeline.main(argv),1)
            self.assertEqual(json.loads(output.getvalue())['reason'],'group_policy_revoked')
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_context_mutated_loaded_authority_cannot_register(self):
        from task_tower.group_policy import policy_manifests
        from task_tower.pipeline_inputs import digest_manifest
        self.seed();before=self.j.path.read_bytes()
        with self.load() as ctx:
            next(iter(ctx.policy['_tasks'].values()))['checks'][0]['argv'].append('injected')
            ctx.policy['authorization_sha256']=digest_manifest(policy_manifests(ctx.policy)['authorization'])
            with self.assertRaises(ValueError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_registration_current_source_change_rolls_back_all_insertions(self):
        from task_tower import group_storage
        self.seed();before=self.j.path.read_bytes();original=group_storage._event
        def change(db,*args,**kwargs):
            original(db,*args,**kwargs)
            self.f.path.write_bytes(self.f.path.read_bytes()+b' ')
        with self.load() as ctx,patch.object(group_storage,'_event',side_effect=change):
            with self.assertRaises(ValueError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)
        self.assertIsNone(self.j.registered_groups())

    def test_registration_fault_after_epoch_insert_rolls_back(self):
        from task_tower import group_registration
        self.seed();before=self.j.path.read_bytes();insert=group_registration._insert
        def fail(db,table,row):
            insert(db,table,row)
            if table=='group_capacity_epochs':raise RuntimeError('fixture crash before commit')
        with self.load() as ctx,patch.object(group_registration,'_insert',side_effect=fail):
            with self.assertRaises(RuntimeError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)
        self.assertIsNone(self.j.registered_groups())

    def test_registration_refuses_active_controller_and_preserves_history(self):
        from tests.test_pipeline_journal import uid
        self.seed();owner=uid();self.j.claim_controller(owner,'a'*64)
        before=self.j.path.read_bytes()
        with self.load() as ctx:
            with self.assertRaises(ValueError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)
        self.j.release_controller(owner)
        with self.load() as ctx:self.j.register_groups(ctx)

    def legacy_holder(self,matching_profile):
        import subprocess,sys
        from task_tower import pipeline_journal as journal_module
        from task_tower.executor_profiles import load_executor_config,profile_fingerprint
        from task_tower.project_connections import load_connections
        from tests.test_pipeline_journal import uid
        config=load_executor_config(self.f.executor_path,load_connections(self.c))
        fingerprint=profile_fingerprint(config['profiles']['local']) if matching_profile else 'a'*64
        self.j.submit(dict(request(),repository='owner/repo',runner_label='local'),dict(policy(),profile_id='local',profile_fingerprint=fingerprint))
        pid=int(subprocess.run([sys.executable,'-c','import os;print(os.getpid())'],capture_output=True,text=True,check=True).stdout)
        owner=uid()
        with self.j.owner(owner),patch.object(journal_module.os,'getpid',return_value=pid):
            run=self.j.claim(owner,2)
            self.j.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},dict(state='unknown',reason='launch_unknown'))
        self.j.migrate_groups()
        return run

    def check_legacy_adoption(self,matching_profile):
        import sqlite3
        from tests.test_group_migration import legacy_dump
        self.legacy_holder(matching_profile);before=legacy_dump(self.j.path)
        with contextlib.closing(sqlite3.connect(self.j.path)) as db:
            actions=db.execute('SELECT * FROM group_actions').fetchall()
        with self.load() as ctx:self.j.register_groups(ctx)
        self.assertEqual(legacy_dump(self.j.path),before)
        with contextlib.closing(sqlite3.connect(self.j.path)) as db:
            self.assertEqual(db.execute('SELECT * FROM group_actions').fetchall(),actions)
            epoch,cpu,memory,pool,unknown,held=db.execute('SELECT capacity_epoch,cpu_millis,memory_bytes,harness_pool,unknown_estimate,held FROM group_resource_leases').fetchone()
            self.assertEqual((epoch,unknown,held),(1,int(not matching_profile),1))
            self.assertEqual((cpu,memory,pool),(1100,1048576+64*1024*1024,'local') if matching_profile else (None,None,None))
            for table in ('group_resource_observations','group_base_epochs','group_source_resolutions','group_main_proofs'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
            self.assertTrue(all(r[0] is None for r in db.execute('SELECT group_id FROM group_runs')))
        reopened=PipelineJournal(self.j.path)
        self.assertEqual(reopened.registered_groups()['current_capacity_epoch'],1)
        reopened.cancel(reopened.status()['runs'][0]['run_id'])
        with contextlib.closing(sqlite3.connect(self.j.path)) as db:
            self.assertEqual(db.execute('SELECT capacity_epoch,held FROM group_resource_leases').fetchone(),(1,1))

    def test_matching_original_profile_adopts_known_held_envelope(self):
        self.check_legacy_adoption(True)

    def test_unproven_original_profile_adopts_unknown_held_fence(self):
        self.check_legacy_adoption(False)

    def test_context_closes_all_sources_and_journal_on_success_or_error(self):
        self.seed()
        ctx=self.load();fds=[v[0] for v in ctx._sources.values()]
        ctx.close();ctx.close()
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)
        self.assertIsNone(getattr(self.j,'_operation_deadline',None))
        self.assertIsNone(getattr(self.j,'_existing_database_identity',None))
        with self.assertRaises(RuntimeError):
            with self.load() as ctx:
                fds=[v[0] for v in ctx._sources.values()]
                raise RuntimeError('fixture failure')
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)
        self.assertIsNone(getattr(self.j,'_operation_deadline',None))

    def test_registration_refuses_live_and_unprovable_legacy_owners(self):
        from tests.test_pipeline_journal import uid
        self.seed();owner=uid()
        with self.j.owner(owner):self.j.claim(owner,2)
        before=self.j.path.read_bytes()
        with self.load() as ctx:
            with self.assertRaises(ValueError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_registration_refuses_null_legacy_owner_pid(self):
        from tests.test_pipeline_journal import uid
        self.seed();self.j.claim(uid(),2);before=self.j.path.read_bytes()
        with self.load() as ctx:
            with self.assertRaises(ValueError):self.j.register_groups(ctx)
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_released_historical_lease_adopts_epoch_without_reacquisition(self):
        import sqlite3
        from tests import test_group_migration as migration_fixtures
        from tests.test_pipeline_journal import uid
        fixture=migration_fixtures.CleanupMigrationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.clean_ready();fixture.journal.migrate_groups();owner=uid()
        import subprocess,sys
        from task_tower import pipeline_journal as journal_module
        pid=int(subprocess.run([sys.executable,'-c','import os;print(os.getpid())'],capture_output=True,text=True,check=True).stdout)
        with fixture.journal.owner(owner),patch.object(journal_module.os,'getpid',return_value=pid):
            run=fixture.journal.claim(owner,2)
        fixture.move(owner,run,state='needs_input',evidence=dict(cleanup_confirmed=True))
        self.j=fixture.journal;self.f.value['canonical_journal']=str(self.j.path);self.f.path.write_text(json.dumps(self.f.value))
        with contextlib.closing(sqlite3.connect(self.j.path)) as db:
            original_actions=db.execute('SELECT * FROM group_actions').fetchall()
            self.assertEqual(db.execute('SELECT held FROM group_resource_leases').fetchone()[0],0)
        with self.load() as ctx:self.j.register_groups(ctx)
        with contextlib.closing(sqlite3.connect(self.j.path)) as db:
            self.assertEqual(db.execute('SELECT held,capacity_epoch,unknown_estimate,cpu_millis,memory_bytes,harness_pool FROM group_resource_leases').fetchone(),(0,1,1,None,None,None))
            self.assertEqual(db.execute('SELECT * FROM group_actions').fetchall(),original_actions)
        self.j.status()

    def test_registered_physical_copy_is_invalid_before_current_sources(self):
        import shutil
        from task_tower.group_registration import guard_execution
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        original=self.j.path.with_name('original.sqlite3');self.j.path.rename(original);shutil.copyfile(original,self.j.path)
        copied=self.j.path.read_bytes();self.f.path.unlink()
        with self.assertRaises(ValueError):guard_execution(PipelineJournal(self.j.path),{'version':1})
        self.assertEqual(self.j.path.read_bytes(),copied)

    def test_cli_error_precedence_wrong_uuid_revocation_and_missing_j(self):
        import io
        from task_tower import pipeline
        from tests.test_pipeline_journal import uid
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        argv=['work','--connections',str(self.c),'--journal',str(self.j.path),'--config',str(self.f.pipeline_path),'--executor-config',str(self.f.executor_path),'--once']
        original=self.f.path.read_bytes();self.f.value['installation_id']=uid();self.f.path.write_text(json.dumps(self.f.value))
        with patch.object(pipeline,'_require_native_execution'),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(pipeline.main(argv),1);self.assertEqual(json.loads(out.getvalue())['reason'],'group_binding_mismatch')
        self.f.path.write_bytes(original);self.f.executor_path.unlink()
        with patch.object(pipeline,'_require_native_execution'),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(pipeline.main(argv),1);self.assertEqual(json.loads(out.getvalue())['reason'],'group_policy_revoked')
        self.j.path.unlink()
        with patch.object(pipeline,'_require_native_execution'),contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(pipeline.main(argv),2);self.assertEqual(json.loads(err.getvalue())['error'],'invalid_or_unavailable_private_state')
        self.assertFalse(self.j.path.exists())

    def test_failed_context_enter_closes_retained_references(self):
        self.seed();ctx=self.load();fds=[value[0] for value in ctx._sources.values()]
        self.f.path.write_bytes(self.f.path.read_bytes()+b' ')
        try:
            with self.assertRaises(ValueError):
                with ctx:pass
            for fd in fds:
                with self.assertRaises(OSError):os.fstat(fd)
            self.assertIsNone(getattr(self.j,'_operation_deadline',None))
        finally:ctx.close()

    def test_actual_child_exit_before_registration_preserves_source_and_sidecar(self):
        import subprocess,sys
        self.seed();before=self.j.path.read_bytes()
        script="""
import os,sys
from pathlib import Path
from task_tower.pipeline_journal import PipelineJournal
from task_tower import group_registration as registration
j=PipelineJournal(Path(sys.argv[1]))
ctx=registration.load_registration_context(*[Path(x) for x in sys.argv[2:6]],j)
if sys.argv[6]=='before':
    insert=registration._insert
    def stop(db,table,row):
        insert(db,table,row)
        if table=='group_capacity_epochs':os._exit(23)
    registration._insert=stop
with ctx:j.register_groups(ctx)
os._exit(24)
"""
        args=[sys.executable,'-c',script,str(self.j.path),str(self.f.path),str(self.c),str(self.f.pipeline_path),str(self.f.executor_path)]
        stopped=subprocess.run([*args,'before'],capture_output=True,timeout=20)
        self.assertEqual(stopped.returncode,23,stopped.stderr)
        self.assertEqual(self.j.path.read_bytes(),before)
        self.assertIsNone(PipelineJournal(self.j.path).registered_groups())
        sidecar=Path(str(self.j.path)+'-journal')
        self.assertTrue(sidecar.exists());rollback=sidecar.read_bytes()
        with self.assertRaises(ValueError):self.load()
        self.assertEqual(self.j.path.read_bytes(),before)
        self.assertEqual(sidecar.read_bytes(),rollback)

    def test_actual_child_exit_after_registration_commit_reopens_exactly(self):
        import subprocess,sys
        self.seed()
        script="""
import os,sys
from pathlib import Path
from task_tower.pipeline_journal import PipelineJournal
from task_tower.group_registration import load_registration_context
j=PipelineJournal(Path(sys.argv[1]))
with load_registration_context(*[Path(x) for x in sys.argv[2:6]],j) as ctx:j.register_groups(ctx)
os._exit(24)
"""
        result=subprocess.run([sys.executable,'-c',script,str(self.j.path),str(self.f.path),str(self.c),str(self.f.pipeline_path),str(self.f.executor_path)],capture_output=True,timeout=20)
        self.assertEqual(result.returncode,24,result.stderr)
        self.assertEqual(PipelineJournal(self.j.path).registered_groups()['current_capacity_epoch'],1)
        with self.load() as ctx:self.assertEqual(self.j.register_groups(ctx)['status'],'already_registered')

    def test_missing_journal_action_helper_never_enters_recovery(self):
        from task_tower import pipeline
        with patch.object(pipeline,'_require_native_execution'),patch.object(self.j,'recover',side_effect=AssertionError('Recovery reached')):
            with self.assertRaises(ValueError):pipeline._action({'version':1},self.j)
        self.assertFalse(self.j.path.exists())

    def test_registered_v2_direct_entry_checks_binding_before_capacity_gate(self):
        from task_tower import pipeline
        from task_tower.group_registration import RegistrationUnavailable
        self.seed()
        with self.load() as ctx:self.j.register_groups(ctx)
        args=pipeline._parser().parse_args(['work','--connections',str(self.c),'--journal',str(self.j.path),'--config',str(self.f.pipeline_path),'--executor-config',str(self.f.executor_path),'--once'])
        self.f.path.unlink()
        with patch.object(pipeline,'_require_native_execution'),self.assertRaises(RegistrationUnavailable) as error:
            pipeline.work({'version':2,'_cli_args':args},self.j)
        self.assertEqual(error.exception.reason,'group_policy_revoked')
