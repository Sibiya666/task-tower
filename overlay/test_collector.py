import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from collector import Journal, group_threads, snapshot


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'session.jsonl'
        self.path.touch()
        self.journal = Journal()

    def event(self, kind, complete=True):
        from datetime import datetime, timezone
        value = json.dumps({'type': 'event_msg', 'timestamp': datetime.now(timezone.utc).isoformat(), 'payload': {'type': kind}})
        with self.path.open('ab') as f:
            f.write(value.encode() + (b'\n' if complete else b''))

    def test_lifecycle_follows_last_event_instead_of_file_recency(self):
        self.event('task_started')
        self.assertEqual(self.journal.read(self.path)['status'], 'active')
        self.event('task_complete')
        self.assertEqual(self.journal.read(self.path)['status'], 'completed')
        self.event('task_started')
        self.assertEqual(self.journal.read(self.path)['status'], 'active')
        self.event('turn_aborted')
        self.assertEqual(self.journal.read(self.path)['status'], 'stopped')

    def test_partial_last_line_is_not_lost(self):
        self.event('task_started', complete=False)
        self.assertEqual(self.journal.read(self.path)['status'], 'unknown')
        with self.path.open('ab') as f:
            f.write(b'\n')
        self.assertEqual(self.journal.read(self.path)['status'], 'active')

    def test_explicit_decision_wait_survives_completion_until_user_reply(self):
        self.event('task_started')
        self.response({'type':'function_call','name':'functions.request_user_input_async','call_id':'q'})
        self.response({'type':'function_call_output','call_id':'q','output':'{"accepted":true}'})
        self.event('task_complete')
        self.assertEqual(self.journal.read(self.path)['status'],'waiting')
        self.event('task_started')
        self.assertEqual(self.journal.read(self.path)['status'],'waiting')
        self.event('user_message')
        self.assertEqual(self.journal.read(self.path)['status'],'idle')

    def response(self,payload):
        with self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps({'type':'response_item','payload':payload})+'\n')

    def test_sync_input_is_resolved_by_its_own_output_only(self):
        self.event('task_started')
        self.response({'type':'function_call','name':'functions.request_user_input','call_id':'q'})
        self.response({'type':'function_call_output','call_id':'other'})
        self.assertEqual(self.journal.read(self.path)['status'],'waiting')
        self.response({'type':'function_call_output','call_id':'q'})
        self.assertEqual(self.journal.read(self.path)['status'],'active')

    def test_restart_keeps_pending_input_before_large_tail(self):
        self.event('task_started')
        self.response({'type':'function_call','name':'functions.request_user_input_async','call_id':'q'})
        self.event('task_complete')
        self.event('task_started')
        with self.path.open('ab') as f:
            f.write(b'{"type":"noise"}\n' * 300000)
        self.event('task_complete')
        self.assertEqual(Journal().read(self.path)['status'],'waiting')

    def test_missing_or_stale_is_not_reported_as_working(self):
        self.assertEqual(self.journal.read(self.path)['status'], 'unknown')
        self.event('task_started')
        self.assertEqual(self.journal.read(self.path, now=time.time()+1000)['status'], 'stale')
        self.assertEqual(self.journal.read(self.path.with_name('missing'))['status'], 'unknown')

    def test_truncated_log_replaces_previous_state(self):
        self.event('task_started')
        self.journal.read(self.path)
        self.path.write_text('')
        self.assertEqual(self.journal.read(self.path)['status'], 'unknown')

    def test_restart_during_a_long_turn_keeps_original_start_event(self):
        self.event('task_started')
        with self.path.open('ab') as f:
            f.write(b'{"type":"noise"}\n' * 300000)
        self.assertEqual(Journal().read(self.path)['status'],'active')


class GroupTests(unittest.TestCase):
    def test_confirmed_assignment_survives_missing_worktree(self):
        projects=[{'id':'p','name':'Dialoid','roots':['C:/game']}]
        result=group_threads(projects,[{'id':'a','cwd':'C:/deleted-worktree'}],{}, {'a':'p'})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['rooms'][0]['id'],'a')
    def test_git_worktree_stays_in_its_original_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);repo=base/'dialoid';work=base/'worktrees'/'apostate-core'/'dialoid'
            metadata=repo/'.git'/'worktrees'/'apostate';metadata.mkdir(parents=True);work.mkdir(parents=True)
            (metadata/'commondir').write_text('../..')
            (work/'.git').write_text('gitdir: '+str(metadata))
            result=group_threads([{'id':'p','name':'Dialoid','roots':[str(repo)]}],
                [{'id':'active','cwd':str(work),'status':'active'}],{}, {})
            self.assertEqual(len(result),1,'Worktree must not create a separate unassigned tower')
            self.assertEqual(result[0]['rooms'][0]['id'],'active')

    def test_archived_intermediate_agent_does_not_duplicate_nested_agent(self):
        projects=[{'id':'p','name':'P','roots':['C:/game']}]
        threads=[{'id':'root','cwd':'C:/game'}, {'id':'middle','cwd':'C:/game','archived':1}, {'id':'leaf','cwd':'C:/game'}]
        result=group_threads(projects,threads,{'leaf':'middle','middle':'root'}, {})
        self.assertEqual([r['id'] for r in result[0]['rooms']],['root'])
        self.assertEqual([a['id'] for a in result[0]['rooms'][0]['agents']],['leaf'])

    def test_internal_approval_agents_are_not_task_rooms(self):
        result=group_threads([{'id':'p','name':'P','roots':['C:/game']}],
            [{'id':'internal','cwd':'C:/game','source':'{"subagent":{"other":"guardian"}}'}],{}, {})
        self.assertEqual(result[0]['rooms'],[])

    def test_children_inherit_room_and_worktree_uses_known_assignment(self):
        projects=[{'id':'game','name':'Game','roots':['C:/game']}]
        threads=[{'id':'room','cwd':'C:/other/worktree','title':'UI'}, {'id':'child','cwd':'C:/game','title':'Subagent'}]
        result=group_threads(projects,threads,{'child':'room'},{'room':'game'})
        self.assertEqual(len(result[0]['rooms']),1)
        self.assertEqual(result[0]['rooms'][0]['agents'][0]['id'],'child')

    def test_prefix_does_not_match_sibling_and_archives_are_excluded(self):
        projects=[{'id':'game','name':'Game','roots':['C:/game']}]
        threads=[{'id':'a','cwd':'C:/game-two','title':'Other'}, {'id':'b','cwd':'C:/game','title':'Old','archived':1}]
        result=group_threads(projects,threads,{}, {})
        self.assertEqual(result[0]['rooms'],[])
        self.assertEqual(result[1]['rooms'][0]['id'],'a')


class SnapshotTests(unittest.TestCase):
    def test_live_wal_titles_and_parent_agents_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            with closing(sqlite3.connect(home/'state_5.sqlite')) as db:
                db.executescript('''PRAGMA journal_mode=WAL;
                    CREATE TABLE projects(id TEXT,name TEXT,position INTEGER);
                    CREATE TABLE project_roots(project_id TEXT,path TEXT);
                    CREATE TABLE thread_spawn_edges(child_thread_id TEXT,parent_thread_id TEXT,status TEXT);
                    CREATE TABLE threads(id TEXT,title TEXT,name TEXT,cwd TEXT,project_id TEXT,
                    rollout_path TEXT,updated_at INTEGER,archived INTEGER,agent_nickname TEXT,
                    agent_role TEXT,attached_thread_parent_id TEXT,source TEXT);
                    INSERT INTO projects VALUES('p','Project',0);
                    INSERT INTO project_roots VALUES('p','C:/project');
                ''')
                for tid, parent in [('room',None),('child','room')]:
                    source=json.dumps({'subagent':{'thread_spawn':{'parent_thread_id':parent}}}) if parent else 'vscode'
                    db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (tid,'First message','Renamed task','C:/project','p',str(home/'missing'),1,0,None,None,None,source))
                db.commit()
                before=db.total_changes
                remembered={}
                data=snapshot(home,Journal(),remembered)
                self.assertIsNone(data['error'])
                self.assertEqual(data['projects'][0]['rooms'][0]['title'],'Renamed task')
                self.assertEqual(len(data['projects'][0]['rooms']),1)
                self.assertEqual(len(data['projects'][0]['rooms'][0]['agents']),1)
                self.assertEqual(db.total_changes,before)
                db.execute("UPDATE threads SET cwd='C:/missing-worktree',project_id=NULL WHERE id='room'")
                db.commit()
                recovered=snapshot(home,Journal(),remembered)
                self.assertEqual(len(recovered['projects']),1)
                self.assertEqual(recovered['projects'][0]['rooms'][0]['id'],'room')


if __name__ == '__main__':
    unittest.main()
