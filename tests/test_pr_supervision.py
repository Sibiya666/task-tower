"""Private channel timing tests; telemetry never grants task authority."""
import json
import os
import unittest
import uuid
import sys
import time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from tests import test_pr_context as fixture
from tests.test_pr_journal import binding


class SupervisionTests(unittest.TestCase):
    setUp=fixture.ContextFactoryTests.setUp
    write=staticmethod(fixture.ContextFactoryTests.write)
    make=fixture.ContextFactoryTests.make

    def monitor(self,*,started=True):
        from task_tower.pr_supervision import PRMonitor
        self.raw['task_timeout_seconds']=60;self.write(self.policy,self.raw)
        from task_tower.pr_journal import PRJournal
        self.j=PRJournal(self.journal);self.row=self.j.admit(binding())
        self.ctx=self.make();self.owner=str(uuid.uuid4())
        self.m=PRMonitor.from_context(self.ctx,owner_id=self.owner)
        self.seq=0;self.pid=os.getpid()
        if started:self.m.started(self.pid)
        return self.m

    def send(self,event,**fields):
        self.seq+=1
        packet=dict(version=1,session_id=self.m.session_id,owner_id=self.owner,pid=self.pid,
            sequence=self.seq,event=event,**fields)
        self.m.feed(json.dumps(packet).encode()+b'\n')

    def start(self):
        self.send('hello');self.action=str(uuid.uuid4())
        self.send('phase_start',action_id=self.action,kind='source',repository='owner/repo',
            pr_number=44,input_sha256=None)

    def task(self,**overrides):
        fields={key:self.row[key] for key in ('repository','pr_number','input_sha256','admitted_utc','deadline_utc')}
        self.send('task',**dict(fields,**overrides))

    def test_actual_factory_only_and_polling_never_reloads_private_files(self):
        from task_tower.pr_supervision import PRMonitor
        with self.assertRaises(ValueError):PRMonitor.from_context({},owner_id=str(uuid.uuid4()))
        self.monitor();self.start();self.task()
        with patch.object(self.ctx,'_fresh_inputs',side_effect=AssertionError('Blocking callback')):
            self.assertFalse(self.m.cancelled())
        self.send('phase_end',action_id=self.action);self.send('end');self.m.finished(0)
        self.assertIsNone(self.m.reason)

    def test_idle_cannot_complete_or_extend_an_active_action(self):
        self.monitor();self.start();self.task();self.send('idle')
        self.assertTrue(self.m.cancelled())

    def test_repeated_admission_and_new_input_never_renew_original_budget(self):
        self.monitor();self.start();self.task()
        original=self.m._tasks[('owner/repo',44)]['monotonic_deadline']
        self.task(input_sha256='e'*64)
        self.assertEqual(self.m._tasks[('owner/repo',44)]['monotonic_deadline'],original)
        later=(datetime.fromisoformat(self.row['deadline_utc'].replace('Z','+00:00'))+timedelta(seconds=1)).isoformat()
        self.task(deadline_utc=later)
        self.assertTrue(self.m.cancelled())

    def test_private_role_profile_and_original_task_deadlines_narrow_phase(self):
        self.monitor();self.start();self.task()
        from task_tower.executor_profiles import profile_fingerprint
        profile=self.ctx._fresh_inputs()['executor']['profiles']['local']
        self.send('role_start',action_id=self.action,profile_id='local',profile_sha256=profile_fingerprint(profile))
        deadline=self.m._deadline
        with patch('task_tower.pr_supervision.time.monotonic',return_value=deadline+.01):
            self.assertTrue(self.m.cancelled())

    def test_wrong_pid_duplicate_key_partial_eof_and_nonzero_exit_fail_closed(self):
        self.monitor();self.send('hello');self.pid+=1;self.send('idle')
        self.assertTrue(self.m.cancelled())
        self.monitor();self.m.feed(b'{"version":1,"version":1}\n');self.assertTrue(self.m.cancelled())
        self.monitor();self.send('hello');self.m.feed(b'{');self.m.finished(0);self.assertTrue(self.m.cancelled())
        self.monitor();self.send('hello');self.send('end');self.m.finished(1);self.assertTrue(self.m.cancelled())

    def test_role_requires_actual_admission_and_known_configured_profile(self):
        self.monitor();self.start()
        self.send('role_start',action_id=self.action,profile_id='local',profile_sha256='a'*64)
        self.assertTrue(self.m.cancelled())

    def test_actual_outer_guard_kills_hung_host_and_descendant_even_when_callback_is_false(self):
        self.raw['reviewer_timeout_seconds']=1
        self.monitor(started=False)
        capture=self.root/'native-capture';capture.mkdir();marker=self.root/'escaped.txt'
        script="import os,json,time,subprocess,sys\nseq=0\n"
        script+="def send(event,**kw):\n global seq;seq+=1;print(json.dumps(dict(version=1,session_id="+repr(self.m.session_id)+",owner_id="+repr(self.owner)+",pid=os.getpid(),sequence=seq,event=event,**kw)),flush=True)\n"
        script+="send('hello')\nsend('phase_start',action_id="+repr(str(uuid.uuid4()))+",kind='source',repository='owner/repo',pr_number=44,input_sha256=None)\n"
        descendant="import pathlib,time;time.sleep(3);pathlib.Path("+repr(str(marker))+").write_text('escaped')"
        script+="subprocess.Popen([sys.executable,'-c',"+repr(descendant)+"])\ntime.sleep(30)\n"
        from task_tower.processes import run_command
        from task_tower.executor_profiles import child_environment
        started=time.monotonic()
        result=run_command([sys.executable,'-u','-c',script],self.root,None,env=child_environment(os.environ),
            cancel_requested=lambda:False,lifecycle_monitor=self.m,capture=dict(directory=capture,max_bytes_per_stream=65536))
        self.assertLess(time.monotonic()-started,5)
        self.assertTrue(result['started']);self.assertTrue(result['cleanup_confirmed'])
        self.assertIn(result['status'],('cancelled','unknown'))
        self.assertIsNotNone(self.m.reason)
        self.assertFalse(result['stdout_tail_unknown']);self.assertFalse(result['stderr_tail_unknown'])
        time.sleep(3.2)
        self.assertFalse(marker.exists(),'A real descendant escaped the containment tree')
