import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from task_tower import pipeline_journal as storage
from task_tower.pipeline_inputs import digest_manifest
from test_pipeline_journal import JournalFixture, AttemptFixture, request, policy, uid


def legacy_dump(path):
    with contextlib.closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return {**{name: [dict(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')]
                   for name in storage.SCHEMAS},
                'sqlite_sequence': [dict(row) for row in db.execute("SELECT * FROM sqlite_sequence WHERE name='events'")]}


class MigrationTests(JournalFixture, unittest.TestCase):
    def seed(self):
        return self.journal.submit(request(), policy())

    def dead_unknown(self):
        self.seed()
        result = subprocess.run([sys.executable, '-c', 'import os;print(os.getpid())'],
                                capture_output=True, text=True, check=True)
        pid = int(result.stdout)
        owner = uid()
        with self.journal.owner(owner), patch.object(storage.os, 'getpid', return_value=pid):
            run = self.journal.claim(owner, 2)
            run = self.journal.record(run['run_id'], owner,
                {k: run[k] for k in ('state', 'stage', 'generation', 'input_sha256')},
                dict(state='unknown', reason='launch_unknown'))
        return run

    def test_inspect_missing_never_creates_directory_or_database(self):
        report = self.journal.inspect_group_migration()
        self.assertEqual(report['status'], 'missing')
        self.assertFalse(self.path.parent.exists())
        with self.assertRaises(ValueError):
            self.journal.migrate_groups()
        self.assertFalse(self.path.parent.exists())

    def test_inspect_v1_is_readonly_and_never_backs_up(self):
        self.seed()
        before = self.path.read_bytes()
        names = set(self.path.parent.iterdir())
        report = self.journal.inspect_group_migration()
        self.assertEqual(report['status'], 'migration_required')
        self.assertEqual(report['version'], 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(set(self.path.parent.iterdir()), names)

    def test_cli_migration_requires_explicit_mode_without_profile_pin_or_process(self):
        from task_tower import pipeline
        connections=Path(self.tmp.name).resolve()/'connections.json'
        connections.write_text('{"version":1,"projects":[]}',encoding='utf-8')
        common=['migrate','--connections',str(connections),'--journal',str(self.path)]
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):pipeline.main(common)
        self.seed()
        with patch('subprocess.Popen',side_effect=AssertionError('Migration launched child')),patch.object(pipeline,'load_pipeline_config',side_effect=AssertionError('Migration loaded execution profile')):
            for flag,expected in (('--inspect','migration_required'),('--apply','migrated'),('--inspect','migrated')):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):self.assertEqual(pipeline.main([*common,flag]),0)
                self.assertEqual(json.loads(output.getvalue())['status'],expected)

    def test_exact_additive_migration_preserves_all_rows_sequence_and_backup(self):
        self.seed()
        before = legacy_dump(self.path)
        result = self.journal.migrate_groups()
        self.assertEqual(result['version'], 2)
        self.assertEqual(legacy_dump(self.path), before)
        backup = Path(result['backup_path'])
        self.assertEqual(legacy_dump(backup), before)
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), result['backup_sha256'])
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(db.execute('PRAGMA application_id').fetchone()[0], storage.APP_ID)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE 'group_%'").fetchone()[0], 17)
            self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND name LIKE 'group_%'").fetchone()[0], 3)
            for name in ('group_installation', 'group_capacity_epochs', 'group_resource_observations',
                         'group_source_resolutions', 'group_base_epochs', 'group_main_proofs'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+name).fetchone()[0], 0)
            for name, sql in storage.SCHEMAS.items():
                self.assertEqual(db.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0], sql)

    def test_dead_unknown_migrates_without_g_owner_epoch_or_cleanup(self):
        run = self.dead_unknown()
        before = legacy_dump(self.path)
        result = self.journal.migrate_groups()
        self.assertEqual(legacy_dump(self.path), before)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            action = dict(db.execute('SELECT * FROM group_actions').fetchone())
            self.assertEqual((action['origin'], action['action_kind'], action['state']), ('legacy_fence', 'legacy_fence', 'unknown'))
            for key in ('owner_id', 'owner_pid', 'input_sha256', 'capacity_epoch', 'completion_json', 'completion_sha256', 'finished_at'):
                self.assertIsNone(action[key])
            origin = json.loads(action['origin_json'])
            self.assertEqual(origin['original_owner_id'], run['owner_id'])
            self.assertEqual(origin['original_owner_pid'], run['owner_pid'])
            self.assertEqual(origin['migration_id'], result['migration_id'])
            self.assertEqual(origin['original_run_row_sha256'], digest_manifest(before['runs'][0]))
            lease = dict(db.execute('SELECT * FROM group_resource_leases').fetchone())
            self.assertEqual((lease['held'], lease['unknown_estimate']), (1, 1))
            for key in ('capacity_epoch', 'observation_id', 'harness_pool', 'cpu_millis', 'memory_bytes', 'cleanup_sha256'):
                self.assertIsNone(lease[key])
        self.assertEqual(self.journal.status(run['run_id'])['state'], 'unknown')
        self.journal.submit(dict(request(2), repository='other/repo'), policy())
        self.assertIsNone(self.journal.claim(uid(), 2))

    def test_pre_g_new_legacy_claim_creates_atomic_fence_and_global_exclusion(self):
        self.seed()
        self.journal.migrate_groups()
        owner = uid()
        with self.journal.owner(owner):
            claimed = self.journal.claim(owner, 2)
        self.assertIsNotNone(claimed)
        self.journal.submit(dict(request(2), repository='other/repo'), policy())
        self.assertIsNone(self.journal.claim(uid(), 2))
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM group_actions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM group_resource_leases WHERE held=1').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM group_capacity_epochs').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            self.journal.claim(uid(), 3)

    def test_reopen_cancel_inspect_preserves_original_origin_and_unknown_fence(self):
        run = self.dead_unknown()
        self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            before = db.execute('SELECT origin_json,origin_sha256 FROM group_actions').fetchall()
        reopened = storage.PipelineJournal(self.path)
        reopened.cancel(run['run_id'])
        self.assertEqual(reopened.status(run['run_id'])['owner_id'], run['owner_id'])
        self.assertEqual(reopened.status(run['run_id'])['state'], 'unknown')
        self.assertEqual(reopened.inspect_group_migration()['version'], 2)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT origin_json,origin_sha256 FROM group_actions').fetchall(), before)
            self.assertEqual(db.execute('SELECT held FROM group_resource_leases').fetchone()[0], 1)

    def test_idempotent_apply_does_not_create_backup_or_duplicate_fences(self):
        self.dead_unknown()
        first = self.journal.migrate_groups()
        names = set(self.path.parent.iterdir())
        before = self.path.read_bytes()
        second = storage.PipelineJournal(self.path).migrate_groups()
        self.assertEqual(second['migration_id'], first['migration_id'])
        self.assertEqual(second['status'], 'already_migrated')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(set(self.path.parent.iterdir()), names)

    def test_live_or_unprovable_owner_and_unreleased_controller_refuse_without_backup(self):
        self.seed()
        owner = uid()
        with self.journal.owner(owner):
            self.journal.claim(owner, 2)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.journal.migrate_groups()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_stopped_controller_preserved_but_active_controller_refused(self):
        self.seed()
        owner = uid()
        self.journal.claim_controller(owner, 'a'*64)
        with self.assertRaises(ValueError):
            self.journal.migrate_groups()
        self.journal.release_controller(owner)
        before = legacy_dump(self.path)
        self.journal.migrate_groups()
        self.assertEqual(legacy_dump(self.path), before)

    def test_two_legacy_holders_of_same_component_are_not_deduplicated(self):
        pid=int(subprocess.run([sys.executable,'-c','import os;print(os.getpid())'],capture_output=True,text=True,check=True).stdout)
        for issue in (1,2):
            self.journal.submit(request(issue),policy())
            owner=uid()
            with self.journal.owner(owner),patch.object(storage.os,'getpid',return_value=pid):
                run=self.journal.claim(owner,2)
                self.journal.record(run['run_id'],owner,{k:run[k] for k in ('state','stage','generation','input_sha256')},
                                    dict(state='needs_input',reason='environment_unavailable',evidence=dict(cleanup_confirmed=True)))
        before=legacy_dump(self.path);self.journal.migrate_groups()
        self.assertEqual(legacy_dump(self.path),before)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM group_component_locks WHERE repository='example/repo' AND component='core'").fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM group_resource_leases WHERE held=1').fetchone()[0],2)

    def test_foreign_catalog_refused_without_write_or_backup(self):
        self.seed()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE VIEW unexpected AS SELECT 1')
            db.commit()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.journal.migrate_groups()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_migration_metadata_digest_tamper_is_not_an_arbitrary_valid_hash(self):
        self.dead_unknown()
        self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            saved = db.execute('SELECT action_id,origin_json FROM group_actions').fetchone()
            origin = json.loads(saved[1]); origin['migration_id'] = 'f'*64
            body = json.dumps(origin, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            db.execute('UPDATE group_actions SET origin_json=?,origin_sha256=? WHERE action_id=?',
                       (body, digest_manifest(origin), saved[0])); db.commit()
        with self.assertRaises(ValueError):
            storage.PipelineJournal(self.path).status()

    def rewrite_origin(self,change):
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            action=db.execute('SELECT action_id,origin_json FROM group_actions ORDER BY ordinal LIMIT 1').fetchone()
            event=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='observation' ORDER BY sequence LIMIT 1").fetchone()
            origin=json.loads(action[1]);body=json.loads(event[1])
            change(origin,body,db,action[0])
            body['origin_sha256']=digest_manifest(origin)
            db.execute('UPDATE group_actions SET origin_json=?,origin_sha256=? WHERE action_id=?',
                (json.dumps(origin,sort_keys=True,separators=(',',':')),digest_manifest(origin),action[0]))
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',
                (json.dumps(body,sort_keys=True,separators=(',',':')),digest_manifest(body),event[0]));db.commit()

    def test_migration_origin_pid_must_match_immutable_migration_snapshot(self):
        self.dead_unknown();self.journal.migrate_groups()
        def change(origin,body,db,action_id):
            body['run_row']['owner_pid']+=100000
            origin['original_owner_pid']=body['run_row']['owner_pid']
            origin['original_run_row_sha256']=digest_manifest(body['run_row'])
        self.rewrite_origin(change)
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_postmigration_claim_cannot_relabel_itself_as_initial_migration(self):
        self.seed();self.journal.migrate_groups()
        with self.journal.owner(uid()) as owner:self.journal.claim(owner,2)
        self.rewrite_origin(lambda origin,body,db,key:origin.update(observation_kind='migration'))
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_required_migration_origin_cannot_relabel_itself_as_legacy_claim(self):
        self.dead_unknown();self.journal.migrate_groups()
        self.rewrite_origin(lambda origin,body,db,key:origin.update(observation_kind='legacy_claim'))
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_required_migration_origin_cannot_relabel_itself_as_reconcile(self):
        self.dead_unknown();self.journal.migrate_groups()
        self.rewrite_origin(lambda origin,body,db,key:origin.update(observation_kind='reconcile'))
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_invalid_origin_timestamp_not_self_attested_by_matching_action_string(self):
        self.dead_unknown();self.journal.migrate_groups()
        def change(origin,body,db,key):
            origin['observed_at']='not-a-time'
            db.execute('UPDATE group_actions SET started_at=? WHERE action_id=?',('not-a-time',key))
        self.rewrite_origin(change)
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_origin_action_and_observation_must_share_actual_utc_boundary_time(self):
        self.dead_unknown();self.journal.migrate_groups()
        def change(origin,body,db,key):
            later=(datetime.datetime.fromisoformat(origin['observed_at'])+datetime.timedelta(seconds=1)).isoformat()
            origin['observed_at']=later;db.execute('UPDATE group_actions SET started_at=? WHERE action_id=?',(later,key))
        self.rewrite_origin(change)
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_actual_legacy_claim_cannot_relabel_itself_as_reconciliation(self):
        self.seed();self.journal.migrate_groups()
        with self.journal.owner(uid()) as owner:self.journal.claim(owner,2)
        self.rewrite_origin(lambda origin,body,db,key:origin.update(observation_kind='reconcile'))
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_later_marker_missing_duplicate_foreign_time_and_tip_fail_closed(self):
        self.seed();self.journal.migrate_groups()
        with self.journal.owner(uid()) as owner:self.journal.claim(owner,2)
        original=self.path.read_bytes()
        for change in ('missing','duplicate','foreign','time','tip','operation'):
            with self.subTest(change=change):
                self.path.write_bytes(original)
                with contextlib.closing(sqlite3.connect(self.path)) as db:
                    row=db.execute("SELECT sequence,run_id,kind,body_json,body_sha256,recorded_at FROM group_events WHERE kind='action'").fetchone()
                    if change=='missing':db.execute('DELETE FROM group_events WHERE sequence=?',(row[0],))
                    elif change=='duplicate':db.execute('INSERT INTO group_events(run_id,kind,body_json,body_sha256,recorded_at) VALUES(?,?,?,?,?)',row[1:])
                    elif change=='time':
                        later=(datetime.datetime.fromisoformat(row[5])+datetime.timedelta(seconds=1)).isoformat()
                        db.execute('UPDATE group_events SET recorded_at=? WHERE sequence=?',(later,row[0]))
                    elif change=='operation':db.execute("UPDATE group_events SET kind='reservation' WHERE sequence=?",(row[0],))
                    else:
                        body=json.loads(row[3])
                        if change=='foreign':body['action_id']=uid()
                        else:body['history_tip']['sha256']='f'*64
                        db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',
                                   (json.dumps(body,sort_keys=True,separators=(',',':')),digest_manifest(body),row[0]))
                    db.commit()
                with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_relabelled_marker_and_origin_still_cannot_contradict_original_claim_event(self):
        self.seed();self.journal.migrate_groups()
        with self.journal.owner(uid()) as owner:self.journal.claim(owner,2)
        def change(origin,body,db,key):
            origin['observation_kind']='reconcile'
            event=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='action'").fetchone()
            marker=json.loads(event[1]);marker['origin_sha256']=digest_manifest(origin)
            db.execute("UPDATE group_events SET kind='reservation',body_json=?,body_sha256=? WHERE sequence=?",
                       (json.dumps(marker,sort_keys=True,separators=(',',':')),digest_manifest(marker),event[0]))
        self.rewrite_origin(change)
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_future_run_after_migration_preserves_original_snapshot_and_sequence777(self):
        self.seed()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE sqlite_sequence SET seq=777 WHERE name='events'");db.commit()
        self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            original=db.execute("SELECT body_json,body_sha256 FROM group_events WHERE kind='migration'").fetchone()
        receipt=self.journal.submit(dict(request(2),repository='other/repo'),policy())
        with self.journal.owner(uid()) as owner:
            run=self.journal.claim(owner,2,queued_order=[dict(repository='other/repo',issue=2,priority='P0')])
        self.assertEqual(run['run_id'],receipt['receipt_id'])
        self.assertEqual(self.journal.status(run['run_id'])['state'],'preparing')
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT body_json,body_sha256 FROM group_events WHERE kind='migration'").fetchone(),original)
            marker=json.loads(db.execute("SELECT body_json FROM group_events WHERE kind='action'").fetchone()[0])
            self.assertGreater(marker['history_tip']['sequence'],777)

    def test_reconciliation_marker_cannot_relabel_an_unstarted_queued_boundary(self):
        self.seed();self.journal.migrate_groups()
        receipt=self.journal.submit(dict(request(2),repository='other/repo'),policy())
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            queued=dict(db.execute('SELECT * FROM runs WHERE run_id=?',(receipt['receipt_id'],)).fetchone())
            history={name:[dict(row) for row in db.execute('SELECT * FROM '+name+' WHERE run_id=? ORDER BY '+('sequence' if name=='events' else 'ordinal' if name=='effects' else 'rowid'),(receipt['receipt_id'],))] for name in ('attempts','verdicts','effects','events')}
        with self.journal.owner(uid()) as owner:
            self.journal.claim(owner,2,queued_order=[dict(repository='other/repo',issue=2,priority='P0')])
        def change(origin,body,db,key):
            origin.update(observation_kind='reconcile',original_owner_id=queued['owner_id'],original_owner_pid=queued['owner_pid'],original_state=queued['state'],original_input_sha256=queued['input_sha256'],original_run_row_sha256=digest_manifest(queued),original_history_sha256=digest_manifest(history))
            body.update(run_row=queued,history=history)
            event=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='action'").fetchone()
            marker=json.loads(event[1]);marker.update(origin_sha256=digest_manifest(origin),run_row_sha256=digest_manifest(queued),history_sha256=digest_manifest(history),history_tip=dict(sequence=history['events'][-1]['sequence'],sha256=digest_manifest(history['events'][-1])))
            db.execute("UPDATE group_events SET kind='reservation',body_json=?,body_sha256=? WHERE sequence=?",(json.dumps(marker,sort_keys=True,separators=(',',':')),digest_manifest(marker),event[0]))
        self.rewrite_origin(change)
        with self.assertRaises(ValueError):self.journal.status()

    def test_marker_failure_rolls_back_entire_actual_legacy_claim(self):
        self.seed();self.journal.migrate_groups();before=legacy_dump(self.path)
        from task_tower import group_storage
        actual_event=group_storage._event
        def fail(db,kind,*args,**kwargs):
            if kind=='action':raise ValueError('Injected marker failure')
            return actual_event(db,kind,*args,**kwargs)
        with patch.object(group_storage,'_event',side_effect=fail),self.journal.owner(uid()) as owner:
            with self.assertRaisesRegex(ValueError,'Injected marker failure'):self.journal.claim(owner,2)
        self.assertEqual(legacy_dump(self.path),before)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            for name in ('group_actions','group_resource_leases','group_reservations'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+name).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM group_events').fetchone()[0],1)

    def test_genuine_legacy_reconciliation_has_its_own_marker_and_survives_later_cancel(self):
        receipt=self.seed();self.journal.migrate_groups();owner=uid()
        pid=int(subprocess.run([sys.executable,'-c','import os;print(os.getpid())'],capture_output=True,text=True,check=True).stdout)
        # A trusted compatibility transaction records real legacy claim/recovery
        # history before its host reconciliation; no process/role is launched.
        with self.journal._db(True) as db:
            now=storage._now()
            db.execute("UPDATE runs SET state='preparing',owner_id=?,owner_pid=?,updated_at=? WHERE run_id=?",(owner,pid,now,receipt['receipt_id']))
            storage.PipelineJournal._event(db,receipt['receipt_id'],'claimed','queued','preparing')
            db.execute("UPDATE runs SET state='unknown',reason='owner_dead',updated_at=? WHERE run_id=?",(storage._now(),receipt['receipt_id']))
            storage.PipelineJournal._event(db,receipt['receipt_id'],'recovered','preparing','unknown','owner_dead')
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')
        self.journal.cancel(receipt['receipt_id'])
        self.assertEqual(self.journal.status(receipt['receipt_id'])['state'],'unknown')
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM group_events WHERE kind='reservation'").fetchone()[0],1)
            self.assertEqual(json.loads(db.execute('SELECT origin_json FROM group_actions').fetchone()[0])['observation_kind'],'reconcile')

    def test_old_binary_contract_refuses_exact_v2_catalog(self):
        self.seed()
        self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            objects = {(r[0],r[1],r[2]) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            self.assertNotEqual(objects, {('table', name, sql) for name, sql in storage.SCHEMAS.items()})
            self.assertNotEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)

    def test_deleted_origin_snapshot_and_duplicate_or_swapped_snapshot_refused(self):
        self.dead_unknown(); self.journal.migrate_groups()
        original=self.path.read_bytes()
        for change in ('missing','duplicate','swapped'):
            with self.subTest(change=change):
                self.path.write_bytes(original)
                with contextlib.closing(sqlite3.connect(self.path)) as db:
                    row=db.execute("SELECT sequence,run_id,kind,body_json,body_sha256,recorded_at FROM group_events WHERE kind='observation'").fetchone()
                    if change=='missing':db.execute('DELETE FROM group_events WHERE sequence=?',(row[0],))
                    elif change=='duplicate':db.execute('INSERT INTO group_events(run_id,kind,body_json,body_sha256,recorded_at) VALUES(?,?,?,?,?)',row[1:])
                    else:
                        body=json.loads(row[3]);body['run_row']['delivery_id']=uid()
                        db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',
                                   (json.dumps(body,sort_keys=True,separators=(',',':')),digest_manifest(body),row[0]))
                    db.commit()
                with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_removed_unknown_fence_cannot_silently_release_execution(self):
        self.dead_unknown();self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            db.execute('DELETE FROM group_resource_leases');db.execute('DELETE FROM group_actions')
            db.execute("DELETE FROM group_events WHERE kind='observation'")
            db.execute('UPDATE group_reservations SET slot_held=0');db.commit()
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_reordered_boundary_history_rejected_even_when_all_hashes_recomputed(self):
        self.dead_unknown();self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            saved=db.execute('SELECT action_id,origin_json FROM group_actions').fetchone()
            event=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='observation'").fetchone()
            body=json.loads(event[1]);body['history']['events'].reverse()
            origin=json.loads(saved[1]);origin['original_history_sha256']=digest_manifest(body['history'])
            body['origin_sha256']=digest_manifest(origin)
            db.execute('UPDATE group_actions SET origin_json=?,origin_sha256=? WHERE action_id=?',
                       (json.dumps(origin,sort_keys=True,separators=(',',':')),digest_manifest(origin),saved[0]))
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',
                       (json.dumps(body,sort_keys=True,separators=(',',':')),digest_manifest(body),event[0]));db.commit()
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def crash_migration(self,phase):
        code="""from pathlib import Path
import os,sys,sqlite3
from task_tower import group_storage
from task_tower.pipeline_journal import PipelineJournal
real_connect=sqlite3.connect
def connect(*args,**kwargs):
 db=real_connect(*args,**kwargs);db.execute('PRAGMA cache_size=1');return db
sqlite3.connect=connect
def crash(phase):
 if phase==sys.argv[2]:os._exit(88)
group_storage._checkpoint=crash
PipelineJournal(Path(sys.argv[1])).migrate_groups()
"""
        completed=subprocess.run([sys.executable,'-c',code,str(self.path),phase],capture_output=True,text=True,timeout=30)
        self.assertEqual(completed.returncode,88,completed.stderr)

    def pair_bytes(self,path=None):
        path=path or self.path
        return {str(path)+suffix:(Path(str(path)+suffix).read_bytes() if Path(str(path)+suffix).exists() else None)
                for suffix in ('','-journal','-wal','-shm')}

    @contextlib.contextmanager
    def no_original_writer(self):
        from task_tower import group_storage
        real_db=storage.PipelineJournal._db
        real_connect=sqlite3.connect
        def checked_db(journal,write=False,*,initialize=True):
            if write:raise AssertionError('Original source writer attempted')
            return real_db(journal,write,initialize=initialize)
        def checked_connect(path,*args,**kwargs):
            if str(path)!=':memory:' and not (kwargs.get('uri') is True and str(path).endswith('?mode=ro')):
                raise AssertionError('Non-readonly SQLite connection attempted')
            return real_connect(path,*args,**kwargs)
        with patch.object(storage.PipelineJournal,'_db',new=checked_db),patch.object(sqlite3,'connect',side_effect=checked_connect),\
             patch.object(group_storage,'_backup',side_effect=AssertionError('Backup attempted')),\
             patch.object(storage.PipelineJournal,'_legacy_claim_fence',side_effect=AssertionError('Claim attempted')),\
             patch.object(storage.PipelineJournal,'_recover_existing',side_effect=AssertionError('Runtime recovery attempted')):
            yield

    def assert_hot_refusal(self,journal=None):
        journal=journal or self.journal
        before=self.pair_bytes(journal.path);names=set(journal.path.parent.iterdir())
        with self.no_original_writer():
            for operation in (journal.inspect_group_migration,journal.migrate_groups):
                self.assertEqual(operation(),dict(status='recovery_required',version=None))
                self.assertEqual(self.pair_bytes(journal.path),before)
                self.assertEqual(set(journal.path.parent.iterdir()),names)

    def test_real_crash_before_commit_reports_neutral_recovery_required_without_mutation(self):
        self.seed();self.crash_migration('before_commit')
        self.assert_hot_refusal()

    def test_real_crash_after_commit_reopens_complete_v2_without_recovery_write(self):
        self.seed();before=legacy_dump(self.path);self.crash_migration('after_commit')
        self.assertEqual(storage.PipelineJournal(self.path).inspect_group_migration()['version'],2)
        self.assertEqual(legacy_dump(self.path),before)

    def foreign_hot(self,appid,version=7,own_schema=False,path=None):
        path=path or self.path
        path.parent.mkdir(parents=True,exist_ok=True)
        if own_schema:storage.PipelineJournal(path).submit(request(),policy())
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.execute('PRAGMA application_id='+str(appid));db.execute('PRAGMA user_version='+str(version))
            if not own_schema:db.execute('CREATE TABLE foreign_data(value TEXT)')
            db.commit()
        code="import sqlite3,os,sys;d=sqlite3.connect(sys.argv[1]);d.execute('PRAGMA cache_size=1');d.execute('BEGIN IMMEDIATE');d.execute('CREATE TABLE spill(value BLOB)');d.execute('INSERT INTO spill VALUES(zeroblob(262144))');os._exit(88)"
        self.assertEqual(subprocess.run([sys.executable,'-c',code,str(path)],timeout=30).returncode,88)

    def test_foreign_appid_hot_is_neutral_without_version_or_owner_approval(self):
        self.foreign_hot(9999)
        self.assert_hot_refusal()

    def test_same_appid_foreign_schema_hot_is_neutral_without_schema_approval(self):
        self.foreign_hot(storage.APP_ID,1)
        self.assert_hot_refusal()

    def test_newer_version_hot_is_neutral_and_never_recognized_as_v1(self):
        self.foreign_hot(storage.APP_ID,3,own_schema=True)
        self.assert_hot_refusal()

    def test_mismatched_valid_journal_never_qualifies_source_or_authorizes_repair(self):
        self.seed();donor=self.path.with_name('foreign-donor.db')
        self.foreign_hot(9999,path=donor)
        donor_before=self.pair_bytes(donor)
        shutil.copyfile(Path(str(donor)+'-journal'),Path(str(self.path)+'-journal'))
        self.assert_hot_refusal()
        self.assertEqual(self.pair_bytes(donor),donor_before)

    def test_hot_cli_emits_exact_neutral_report_and_nonzero_without_profiles(self):
        from task_tower import pipeline
        self.seed();self.crash_migration('before_commit')
        connections=Path(self.tmp.name).resolve()/'connections.json'
        connections.write_text('{"version":1,"projects":[]}',encoding='utf-8')
        before=self.pair_bytes();names=set(self.path.parent.iterdir())
        with self.no_original_writer(),patch.object(pipeline,'load_pipeline_config',side_effect=AssertionError('Execution policy loaded')):
            for flag in ('--inspect','--apply'):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(pipeline.main(['migrate','--connections',str(connections),'--journal',str(self.path),flag]),1)
                self.assertEqual(json.loads(output.getvalue()),dict(status='recovery_required',version=None))
                self.assertEqual(self.pair_bytes(),before);self.assertEqual(set(self.path.parent.iterdir()),names)

    def test_non776_and_generic_errors_never_become_recovery_required(self):
        self.seed();before=self.pair_bytes()
        for error in (ValueError('generic'),sqlite3.OperationalError('not a rollback code')):
            if isinstance(error,ValueError):error.sqlite_errorcode=776
            with patch.object(storage.PipelineJournal,'_db',side_effect=error):
                for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                    with self.assertRaises((ValueError,sqlite3.Error)):operation()
            self.assertEqual(self.pair_bytes(),before)

    def test_corrupt_database_and_ignored_rollback_sidecar_are_not_cold_qualified(self):
        self.seed();base=self.path.read_bytes()
        for corrupt_database,sidecar in ((True,None),(False,b'not a valid journal'),(False,b'\0'*512)):
            self.path.write_bytes(b'not sqlite' if corrupt_database else base)
            rollback=Path(str(self.path)+'-journal')
            if sidecar is not None:rollback.write_bytes(sidecar)
            before=self.pair_bytes();names=set(self.path.parent.iterdir())
            with self.no_original_writer():
                for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                    with self.assertRaises(ValueError):operation()
                    self.assertEqual(self.pair_bytes(),before)
                    self.assertEqual(set(self.path.parent.iterdir()),names)
            if rollback.exists():rollback.unlink()

    def test_valid_magic_but_nonhot_rollback_ro_success_still_refuses_migration(self):
        self.seed();rollback=Path(str(self.path)+'-journal')
        # An external RESERVED holder makes the rollback file non-hot to SQLite
        # while still allowing real RO access. It is not a migration writer.
        with contextlib.closing(sqlite3.connect(self.path)) as external:
            external.execute('BEGIN IMMEDIATE')
            rollback.write_bytes(bytes.fromhex('d9d505f920a163d7')+b'\0'*20)
            before=self.pair_bytes();entered=[];real_db=storage.PipelineJournal._db
            @contextlib.contextmanager
            def observed_read(journal,write=False,*,initialize=True):
                self.assertFalse(write,'Source writer attempted')
                with real_db(journal,False,initialize=initialize) as db:
                    entered.append(True);yield db
            with self.no_original_writer(),patch.object(storage.PipelineJournal,'_db',new=observed_read):
                for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                    with self.assertRaisesRegex(ValueError,'Unqualified migration rollback sidecar'):operation()
            self.assertEqual(entered,[True,True])
            self.assertEqual(self.pair_bytes(),before)
            external.rollback()

    def test_migration_only_sidecar_refusal_does_not_change_legacy_read_status(self):
        self.seed();Path(str(self.path)+'-journal').write_bytes(b'\0'*512)
        before=self.pair_bytes()
        self.assertEqual(self.journal.status()['runs'][0]['state'],'queued')
        for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
            with self.assertRaises(ValueError):operation()
        self.assertEqual(self.pair_bytes(),before)

    def test_wal_header_refuses_before_sqlite_or_recovery_classification(self):
        self.seed();header=bytearray(self.path.read_bytes());header[18:20]=b'\2\2';self.path.write_bytes(header)
        before=self.pair_bytes()
        with patch.object(sqlite3,'connect',side_effect=AssertionError('WAL header opened SQLite')):
            for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                with self.assertRaises(ValueError):operation()
        self.assertEqual(self.pair_bytes(),before)

    def test_wal_shm_and_superjournal_are_rejected_before_sqlite(self):
        self.seed()
        for suffix in ('-wal','-shm','-mjunsafe','-MJunsafe'):
            sidecar=Path(str(self.path)+suffix);sidecar.write_bytes(b'unsupported')
            before=self.pair_bytes();extra=sidecar.read_bytes()
            with patch.object(sqlite3,'connect',side_effect=AssertionError('Unsupported sidecar opened SQLite')):
                for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                    with self.assertRaises(ValueError):operation()
            self.assertEqual(self.pair_bytes(),before);self.assertEqual(sidecar.read_bytes(),extra);sidecar.unlink()
        rollback=Path(str(self.path)+'-journal')
        rollback.write_bytes(bytes.fromhex('d9d505f920a163d7')+b'unsafe-super-journal-name'+b'\0'*8+bytes.fromhex('d9d505f920a163d7'))
        before=self.pair_bytes()
        with patch.object(sqlite3,'connect',side_effect=AssertionError('Superjournal footer opened SQLite')):
            for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                with self.assertRaises(ValueError):operation()
        self.assertEqual(self.pair_bytes(),before)

    def test_hot_hardlink_alias_refuses_without_recovery_classification(self):
        self.seed();self.crash_migration('before_commit')
        alias=self.path.with_name('aliased.db')
        try:os.link(self.path,alias)
        except OSError:self.skipTest('Hardlink creation unavailable')
        before=self.pair_bytes()
        with patch.object(sqlite3,'connect',side_effect=AssertionError('Aliased source opened SQLite')):
            for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                with self.assertRaises(ValueError):operation()
        self.assertEqual(self.pair_bytes(),before)

    def test_hot_rollback_sidecar_hardlink_is_rejected_before_sqlite(self):
        self.seed();self.crash_migration('before_commit')
        rollback=Path(str(self.path)+'-journal');alias=rollback.with_name('aliased-journal')
        try:os.link(rollback,alias)
        except OSError:self.skipTest('Hardlink creation unavailable')
        before=self.pair_bytes()
        with patch.object(sqlite3,'connect',side_effect=AssertionError('Aliased rollback opened SQLite')):
            for operation in (self.journal.inspect_group_migration,self.journal.migrate_groups):
                with self.assertRaises(ValueError):operation()
        self.assertEqual(self.pair_bytes(),before)

    def test_new_hot_pair_after_successful_first_read_refuses_before_writer(self):
        self.seed();from task_tower import group_storage
        reached=[]
        def spill(phase):
            if phase!='after_inspection':return
            reached.append(phase)
            code="import sqlite3,os,sys;d=sqlite3.connect(sys.argv[1]);d.execute('PRAGMA cache_size=1');d.execute('BEGIN IMMEDIATE');d.execute('CREATE TABLE unexpected_spill(value BLOB)');d.execute('INSERT INTO unexpected_spill VALUES(zeroblob(262144))');os._exit(88)"
            self.assertEqual(subprocess.run([sys.executable,'-c',code,str(self.path)],timeout=30).returncode,88)
        with self.no_original_writer(),patch.object(group_storage,'_checkpoint',side_effect=spill):
            with self.assertRaises(ValueError):self.journal.migrate_groups()
        self.assertEqual(reached,['after_inspection'])

    def test_deadline_expired_after_backup_rolls_back_and_preserves_failed_backup(self):
        self.seed();before=self.path.read_bytes()
        from task_tower import group_storage
        def expire(phase):
            if phase=='after_backup':self.journal._operation_deadline=0
        with patch.object(group_storage,'_checkpoint',side_effect=expire):
            with self.assertRaises(ValueError) as failure:self.journal.migrate_groups()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(len(list(self.path.parent.glob('*.backup'))),1)
        self.assertEqual(failure.exception.backup_path,str(next(self.path.parent.glob('*.backup'))))
        self.assertEqual(storage.PipelineJournal(self.path).inspect_group_migration()['version'],1)

    def test_pinned_journal_deleted_before_writer_open_is_not_recreated(self):
        self.seed()
        from task_tower import group_storage
        def remove(phase):
            if phase=='after_inspection':self.path.unlink()
        with patch.object(group_storage,'_checkpoint',side_effect=remove):
            with self.assertRaises((ValueError,OSError)):self.journal.migrate_groups()
        self.assertFalse(self.path.exists())

    def test_backup_creation_never_overwrites_existing_file(self):
        self.seed();before=self.path.read_bytes()
        fixed=uid();existing=self.path.with_name(self.path.name+'.groups-v2-'+fixed+'.backup')
        existing.write_bytes(b'preserve existing diagnostic backup')
        from task_tower import group_storage
        with patch.object(group_storage.uuid,'uuid4',return_value=fixed):
            with self.assertRaises(FileExistsError):self.journal.migrate_groups()
        self.assertEqual(existing.read_bytes(),b'preserve existing diagnostic backup')
        self.assertEqual(self.path.read_bytes(),before)

    def test_busy_writer_wait_is_capped_and_never_creates_backup(self):
        self.exercise_busy_writer()

    def exercise_busy_writer(self,delay_before_pragma=0):
        from task_tower import group_storage
        self.seed();before=self.path.read_bytes();waits=[];preflight={};operation={}
        operation['outer_deadline']=getattr(self.journal,'_operation_deadline',None)
        original_deadline=self.journal.operation_deadline
        @contextlib.contextmanager
        def observe_deadline(deadline):
            with original_deadline(deadline):
                operation.update(deadline=journal._operation_deadline,started=time.monotonic())
                yield
        actual_connect=sqlite3.connect;checkpoint=group_storage._checkpoint
        journal=self.journal;budgets=[]
        original_wait=journal._wait_seconds
        def observe_wait():
            sample=dict(started=time.monotonic(),deadline=journal._operation_deadline)
            sample['budget_seconds']=original_wait()
            budgets.append(sample)
            return sample['budget_seconds']
        with contextlib.closing(actual_connect(self.path)) as writer:
            writer.execute('BEGIN IMMEDIATE')
            class ObservedConnection(sqlite3.Connection):
                def execute(connection,sql,*args,**kwargs):
                    if sql.startswith('PRAGMA busy_timeout='):
                        time.sleep(delay_before_pragma)
                        connection.busy_budget=dict(budgets[-1])
                    if sql!='BEGIN IMMEDIATE':return super().execute(sql,*args,**kwargs)
                    # Observe the actual SQLite setting and blocking statement;
                    # never replace the lock attempt or approve a mocked result.
                    timeout=super().execute('PRAGMA busy_timeout').fetchone()[0]
                    sample=dict(timeout_ms=timeout,deadline=journal._operation_deadline,
                                writer_held=writer.in_transaction,budget=connection.busy_budget)
                    waits.append(sample);started=time.monotonic()
                    try:return super().execute(sql,*args,**kwargs)
                    finally:
                        sample.update(seconds=time.monotonic()-started,writer_still_held=writer.in_transaction)
            def connect(*args,**kwargs):
                return actual_connect(*args,**dict(kwargs,factory=ObservedConnection))
            def observe_checkpoint(phase):
                checkpoint(phase)
                if phase=='after_inspection':
                    preflight.update(deadline=journal._operation_deadline,finished=time.monotonic())
            start=time.monotonic()
            with patch.object(sqlite3,'connect',side_effect=connect),patch.object(group_storage,'_checkpoint',side_effect=observe_checkpoint),patch.object(journal,'operation_deadline',side_effect=observe_deadline),patch.object(journal,'_wait_seconds',side_effect=observe_wait):
                with self.assertRaises(ValueError) as failure:self.journal.migrate_groups()
            total=time.monotonic()-start
            writer.rollback()
        self.assertEqual(len(waits),1)
        wait=waits[0];timing=dict(total_seconds=total,preflight_and_other_seconds=total-wait['seconds'],**wait)
        self._busy_timing=timing
        self.assertEqual(getattr(failure.exception.__cause__,'sqlite_errorcode',None),sqlite3.SQLITE_BUSY)
        self.assertTrue(wait['writer_held'] and wait['writer_still_held'])
        self.assert_busy_budget(wait,operation['deadline'])
        # SQLite counts requested sleep, not a strict elapsed-time upper bound.
        # Preserve genuine contention and the single shared operation deadline.
        self.assertEqual(wait['deadline'],preflight['deadline'],timing)
        self.assertGreater(operation['deadline']-operation['started'],0,timing)
        self.assertLessEqual(operation['deadline']-operation['started'],60,timing)
        self.assertGreater(preflight['deadline']-preflight['finished'],0,timing)
        self.assertLessEqual(preflight['deadline']-preflight['finished'],60,timing)
        self.assertLess(total,60,timing)
        self.assertEqual(getattr(self.journal,'_operation_deadline',None),operation.get('outer_deadline'))
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.path.parent.glob('*.backup')),[])

    def test_busy_writer_accepts_delay_after_budget_calculation(self):
        with self.journal.operation_deadline(time.monotonic()+4):
            self.exercise_busy_writer(delay_before_pragma=.02)

    def test_busy_writer_uses_remaining_outer_deadline(self):
        with self.journal.operation_deadline(time.monotonic()+4):
            self.test_busy_writer_wait_is_capped_and_never_creates_backup()

    def assert_busy_budget(self,wait,original_deadline):
        self.assertGreater(wait['timeout_ms'],0)
        self.assertLessEqual(wait['timeout_ms'],5000)
        self.assertEqual(wait['deadline'],original_deadline)
        budget=wait['budget']
        self.assertEqual(budget['deadline'],original_deadline)
        self.assertLessEqual(budget['budget_seconds'],min(5,original_deadline-budget['started']))
        self.assertEqual(wait['timeout_ms'],max(0,int(budget['budget_seconds']*1000)))

    def test_busy_budget_observation_rejects_excess_and_renewal(self):
        sample=dict(timeout_ms=5000,deadline=60.,budget=dict(started=1.,deadline=60.,budget_seconds=5.))
        self.assert_busy_budget(sample,60.)
        for changed in (dict(timeout_ms=5001),dict(deadline=61.),dict(budget=dict(started=59.,deadline=60.,budget_seconds=5.))):
            with self.subTest(changed=changed),self.assertRaises(AssertionError):
                self.assert_busy_budget(dict(sample,**changed),60.)

    def test_reader_blocking_commit_leaves_exact_v1_and_retained_backup(self):
        self.seed();before=legacy_dump(self.path)
        with contextlib.closing(sqlite3.connect(self.path)) as reader:
            reader.execute('BEGIN');reader.execute('SELECT * FROM runs').fetchall()
            with self.assertRaises(ValueError):self.journal.migrate_groups()
            reader.rollback()
        self.assertEqual(legacy_dump(self.path),before)
        self.assertEqual(storage.PipelineJournal(self.path).inspect_group_migration()['version'],1)
        self.assertEqual(len(list(self.path.parent.glob('*.backup'))),1)

    def test_replaced_journal_before_writer_open_is_rejected_without_touching_replacement(self):
        self.seed();replacement=self.path.with_name('replacement.sqlite3')
        other=storage.PipelineJournal(replacement);other.submit(request(99),policy())
        original=self.path.with_name('original.sqlite3')
        from task_tower import group_storage
        def replace(phase):
            if phase=='after_inspection':
                self.path.rename(original);replacement.rename(self.path)
        with patch.object(group_storage,'_checkpoint',side_effect=replace):
            with self.assertRaises(ValueError):self.journal.migrate_groups()
        self.assertEqual(storage.PipelineJournal(self.path).status()['runs'][0]['issue'],99)
        self.assertEqual(storage.PipelineJournal(original).inspect_group_migration()['version'],1)

    def test_sql_nullable_caps_above_two_and_deferred_installation_keys(self):
        self.seed();self.journal.migrate_groups()
        # These are schema fixtures in a disposable memory copy, never authority
        # accepted by the Task3A host (which rejects registered-G rows).
        with contextlib.closing(sqlite3.connect(self.path)) as source,contextlib.closing(sqlite3.connect(':memory:')) as db:
            source.backup(db);db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN')
            installation=uid();now='2026-11-03T00:00:00+00:00'
            db.execute('INSERT INTO group_installation VALUES(1,?,?,?,?,?,?,?,?)',
                (installation,str(self.path),'{}',str(self.path.with_name('groups.json')),1,'a'*64,'b'*64,now))
            db.execute('INSERT INTO group_capacity_epochs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (1,installation,'initial','a'*64,'b'*64,None,5,3,3,None,'{}','{}','c'*64,now))
            db.commit()
            self.assertEqual(db.execute('SELECT group_maximum,pipeline_maximum,executor_maximum,effective_maximum FROM group_capacity_epochs').fetchone(),(None,5,3,3))
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            with self.assertRaises(sqlite3.IntegrityError):db.execute('UPDATE group_capacity_epochs SET group_maximum=0')

    def test_sql_same_proof_hash_is_per_run_and_cannot_be_borrowed(self):
        first=self.seed()['receipt_id'];second=self.journal.submit(request(2),policy())['receipt_id'];self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as source,contextlib.closing(sqlite3.connect(':memory:')) as db:
            source.backup(db);db.execute('PRAGMA foreign_keys=ON')
            db.execute('INSERT INTO group_main_proofs VALUES(?,?,?,?,?,?,?)',('e'*64,second,'initial_source','a'*64,'b'*64,'{}','2026-11-03T00:00:00+00:00'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO group_source_resolutions VALUES(?,?,?,?,?,?,?,?)',(first,'accepted_main','{}','f'*64,'a'*40,'a'*40,'b'*64,'e'*64))
            db.execute('INSERT INTO group_main_proofs VALUES(?,?,?,?,?,?,?)',('e'*64,first,'initial_source','a'*64,'b'*64,'{}','2026-11-03T00:00:00+00:00'))
            self.assertEqual(db.execute('SELECT count(*) FROM group_main_proofs').fetchone()[0],2)

    def test_sql_resource_action_fk_is_deferred_but_no_fake_epoch_required(self):
        self.dead_unknown();self.journal.migrate_groups()
        with contextlib.closing(sqlite3.connect(self.path)) as source,contextlib.closing(sqlite3.connect(':memory:')) as db:
            source.backup(db);db.execute('PRAGMA foreign_keys=ON')
            action=db.execute('SELECT * FROM group_actions').fetchone();lease=db.execute('SELECT * FROM group_resource_leases').fetchone()
            db.execute('BEGIN');db.execute('DELETE FROM group_resource_leases');db.execute('DELETE FROM group_actions')
            db.execute('INSERT INTO group_resource_leases VALUES(?,?,?,?,?,?,?,?,?,?)',lease)
            db.execute('INSERT INTO group_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',action);db.commit()
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(db.execute('SELECT count(*) FROM group_capacity_epochs').fetchone()[0],0)


class CleanupMigrationTests(AttemptFixture,unittest.TestCase):
    def clean_ready(self):
        pid=int(subprocess.run([sys.executable,'-c','import os;print(os.getpid())'],capture_output=True,text=True,check=True).stdout)
        owner=uid()
        with self.journal.owner(owner),patch.object(storage.os,'getpid',return_value=pid):
            owner,run,manifest=self.bound_run(owner)
            executor=self.journal.begin_attempt(run['run_id'],owner,dict(role='spec_executor',manifest=manifest,artifact_names={}))
            self.journal.finish_attempt(executor['attempt_id'],owner,dict(status='completed',started=True,cleanup_confirmed=True,exit_code=0,result_sha256='f'*64))
            run,manifest=self.freeze_output(owner,run,manifest,executor)
        return owner,run,manifest

    def test_clean_product_component_stays_locked_without_execution_slot(self):
        owner,run,manifest=self.clean_ready()
        run=self.move(owner,run,state='needs_input',evidence=dict(cleanup_confirmed=True))
        self.journal.migrate_groups()
        self.journal.submit(request(2),policy())
        self.assertIsNone(self.journal.claim(uid(),2))
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT slot_held,component_held FROM group_reservations').fetchone(),(0,1))

    def test_real_cleanup_releases_lease_but_retains_origin_and_components(self):
        old_owner,run,manifest=self.clean_ready()
        self.journal.migrate_groups()
        owner=uid()
        with self.journal.owner(owner):run=self.journal.claim(owner,2)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            origin=db.execute('SELECT origin_json FROM group_actions').fetchone()[0]
            self.assertEqual(db.execute('SELECT held FROM group_resource_leases').fetchone()[0],1)
        self.move(owner,run,state='needs_input',evidence=dict(cleanup_confirmed=True))
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT origin_json FROM group_actions').fetchone()[0],origin)
            self.assertEqual(db.execute('SELECT held FROM group_resource_leases').fetchone()[0],0)
            self.assertIsNotNone(db.execute('SELECT cleanup_sha256 FROM group_resource_leases').fetchone()[0])
            self.assertEqual(db.execute('SELECT slot_held,component_held FROM group_reservations').fetchone(),(0,1))
        self.assertEqual(self.journal.status(run['run_id'])['state'],'needs_input')

    def test_cleanup_snapshot_cannot_borrow_edited_attempt_history(self):
        old_owner,run,manifest=self.clean_ready();self.journal.migrate_groups()
        owner=uid()
        with self.journal.owner(owner):run=self.journal.claim(owner,2)
        self.move(owner,run,state='needs_input',evidence=dict(cleanup_confirmed=True))
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            event=db.execute("SELECT sequence,body_json FROM group_events WHERE kind='resource_release'").fetchone()
            body=json.loads(event[1]);body['history']['attempts'][0]['result_sha256']='e'*64
            body['cleanup_sha256']=digest_manifest(body['history'])
            db.execute('UPDATE group_resource_leases SET cleanup_sha256=?',(body['cleanup_sha256'],))
            db.execute('UPDATE group_events SET body_json=?,body_sha256=? WHERE sequence=?',
                       (json.dumps(body,sort_keys=True,separators=(',',':')),digest_manifest(body),event[0]));db.commit()
        with self.assertRaises(ValueError):storage.PipelineJournal(self.path).status()

    def test_own_ready_reclaim_has_fresh_marker_without_mutating_original_legacy_history(self):
        old_owner,run,manifest=self.clean_ready();self.journal.migrate_groups();owner=uid()
        with self.journal.owner(owner):run=self.journal.claim(owner,2)
        run=self.move(owner,run,state='ready')
        before=legacy_dump(self.path)
        with self.journal.owner(owner):again=self.journal.claim(owner,2)
        self.assertEqual(again['run_id'],run['run_id'])
        self.assertEqual(legacy_dump(self.path),before)
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM group_events WHERE kind='action'").fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM group_resource_leases WHERE held=1').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM group_resource_leases WHERE held=0').fetchone()[0],1)
