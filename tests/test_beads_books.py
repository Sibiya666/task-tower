import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class BeadsBooksTests(unittest.TestCase):
    def test_missing_or_partial_history_keeps_tasks_and_reports_coverage(self):
        from task_tower.beads_books import read_projects
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve();exe=p/'bd.exe';exe.write_bytes(b'fixture')
            config=p/'config.json';config.write_text(json.dumps(dict(version=1,executable=str(exe),projects=[dict(id='p',repository='owner/repo',directory=str(p))])),encoding='utf-8')
            row=dict(id='tt-a',title='Task',issue_type='task',status='open')
            event=dict(seq=1,ts='2026-11-04T18:00:00Z',op='create',actor='planner',issue_id=dict(row)['id'],issue=dict(row))
            for events in ([],[dict(event,seq=200)],[dict(event,op='update')]):
                def read(executable,directory,args,remaining):
                    if 'config' in args:return {'value':'true'}
                    return events if 'events' in args else [row]
                with self.subTest(events=events):
                    result=read_projects(config,reader=read)
                    self.assertEqual(len(result['entries']),1)
                    self.assertTrue(result['errors'])
            def complete(executable,directory,args,remaining):
                if 'config' in args:return {'value':'true'}
                return [event] if 'events' in args else [row]
            self.assertFalse(read_projects(config,reader=complete)['errors'])
            def empty(executable,directory,args,remaining):return {'value':'true'} if 'config' in args else []
            self.assertFalse(read_projects(config,reader=empty)['errors'])
            def disabled(executable,directory,args,remaining):
                if 'config' in args:return {'value':'false'}
                return [event] if 'events' in args else [dict(row,status='closed')]
            result=read_projects(config,reader=disabled)
            self.assertEqual(result['entries'][0]['status'],'closed')
            self.assertTrue(result['errors'])
            def enabled_after_gap(executable,directory,args,remaining):
                if 'config' in args:return {'value':'true'}
                return [event] if 'events' in args else [dict(row,status='closed')]
            self.assertTrue(read_projects(config,reader=enabled_after_gap)['errors'])

    def test_local_tasks_and_chronology_are_projected_without_private_fields(self):
        from task_tower.beads_books import project_rows
        rows=[dict(id='tt-a',title='Epic',issue_type='epic',status='open'),dict(id='tt-a.1',title='Task',issue_type='task',status='closed',assignee='worker-a',parent='tt-a',description='Actual prose',metadata={'secret':'PRIVATE'},dependencies=[dict(type='blocks',depends_on_id='tt-b')])]
        events=[dict(seq=1,ts='2026-11-04T18:00:00Z',op='update',actor='worker-a',issue_id='tt-a.1',issue=dict(status='closed',metadata={'secret':'PRIVATE'}))]
        result=project_rows('p','owner/repo',rows,events)
        task=result[1]
        self.assertEqual(task['id'],'owner/repo:beads:p:tt-a.1')
        self.assertIsNone(task['source'])
        self.assertEqual(task['status'],'closed')
        self.assertEqual(task['verification'],'not_required')
        self.assertEqual(task['assignee'],'worker-a')
        self.assertEqual(task['relationships']['parent']['id'],result[0]['id'])
        self.assertEqual(task['history'][0]['actor'],'worker-a')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_duplicate_or_malformed_identity_is_rejected(self):
        from task_tower.beads_books import project_rows
        row=dict(id='tt-a',title='Task',issue_type='task',status='open')
        for rows in ([row,row],[dict(row,id='../escape')]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                project_rows('p','owner/repo',rows,[])

    def test_local_source_uses_fixed_readonly_commands_and_survives_missing_history(self):
        from task_tower.beads_books import read_projects
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve(); exe=p/'bd.exe';exe.write_bytes(b'fixture')
            config=p/'config.json';config.write_text(json.dumps(dict(version=1,executable=str(exe),projects=[dict(id='p',repository='owner/repo',directory=str(p))])),encoding='utf-8')
            calls=[]
            def read(executable,directory,args,remaining):
                calls.append(args)
                if 'events' in args:raise ValueError('PRIVATE backend error')
                return [dict(id='tt-a',title='Task',issue_type='task',status='open')]
            report=read_projects(config,reader=read)
            self.assertEqual(len(report['entries']),1)
            self.assertTrue(report['errors'])
            self.assertNotIn('PRIVATE',json.dumps(report))
            self.assertTrue(all('--readonly' in args and '--sandbox' in args for args in calls))

    def test_overlay_accepts_local_only_configuration_without_github(self):
        from task_tower.overlay_books import snapshot
        with patch('task_tower.beads_books.read_projects',return_value=dict(entries=[],errors=[],fetched_at=None,repositories={'owner/repo'})),patch('task_tower.overlay_books.aggregate',side_effect=AssertionError('GitHub invoked')):
            self.assertEqual(snapshot(None,beads_path=Path('private.json'))['state'],'ready')

    def test_mixed_sources_stream_remote_identity_and_retain_it_after_failure(self):
        from types import SimpleNamespace
        from task_tower.overlay_books import snapshot
        local=dict(entries=[dict(id='owner/local:beads:p:tt-a')],errors=[],fetched_at=None,repositories=['owner/local'])
        updates=[]
        def remote(connections,include_library,on_update):
            on_update(dict(entries=[dict(id='owner/remote#1')],errors=[],fetched_at=None))
            self.assertEqual({e['id'] for e in updates[-1]['entries']},{'owner/local:beads:p:tt-a','owner/remote#1'})
            raise ValueError('PRIVATE remote failure')
        with patch('task_tower.beads_books.read_projects',return_value=local),patch('task_tower.overlay_books.load_connections',return_value=[SimpleNamespace(repository='owner/remote')]),patch('task_tower.overlay_books.aggregate',side_effect=remote):
            result=snapshot(Path('connections.json'),beads_path=Path('beads.json'),on_update=updates.append)
        self.assertEqual(len(result['entries']),2)
        self.assertEqual(result['state'],'partial')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_invalid_local_source_does_not_hide_valid_github_books(self):
        from types import SimpleNamespace
        from task_tower.overlay_books import snapshot
        with patch('task_tower.beads_books.read_projects',side_effect=ValueError('SECRET local config')),patch('task_tower.overlay_books.load_connections',return_value=[SimpleNamespace(repository='owner/remote')]),patch('task_tower.overlay_books.aggregate',return_value=dict(entries=[dict(id='owner/remote#1')],errors=[],fetched_at=None)):
            result=snapshot(Path('connections.json'),beads_path=Path('beads.json'))
        self.assertEqual(len(result['entries']),1)
        self.assertEqual(result['state'],'partial')
        self.assertNotIn('SECRET',json.dumps(result))
