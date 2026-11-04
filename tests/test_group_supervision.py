"""Pure channel-state tests over actual private registration; no claim proof."""
import json
import os
import time
import unittest
import uuid
import sys
from pathlib import Path
from unittest.mock import patch
from tests import test_group_registration as registration


class GroupSupervisionTests(unittest.TestCase):
    setUp=registration.RegistrationContextTests.setUp
    load=registration.RegistrationContextTests.load
    seed=registration.RegistrationContextTests.seed

    def monitor(self):
        from task_tower.group_supervision import GroupMonitor
        if not getattr(self,'_seeded',False):self.seed();self._seeded=True
        with self.load() as ctx:
            self.j.register_groups(ctx)
            return GroupMonitor.from_registration(ctx,owner_id=str(uuid.uuid4()))

    def frame(self,monitor,sequence,event,**fields):
        return (json.dumps(dict(version=1,domain='groups',session_id=monitor.session_id,
            owner_id=monitor.owner_id,pid=os.getpid(),sequence=sequence,event=event,**fields))+'\n').encode()

    def test_original_source_phase_is_bounded_without_database_in_cancel(self):
        monitor=self.monitor();monitor.started(os.getpid())
        monitor.feed(self.frame(monitor,1,'hello'))
        phase=dict(phase_id=str(uuid.uuid4()),phase_kind='source',task_key=None,
            action_id=None,member='collect_source',member_sha256=None,profile_sha256=None)
        monitor.feed(self.frame(monitor,2,'phase_start',requested_seconds=1,**phase))
        before=self.j.path.read_bytes()
        self.assertFalse(monitor.cancelled())
        time.sleep(1.05)
        self.assertTrue(monitor.cancelled())
        self.assertEqual(monitor.reason,'phase_timeout')
        self.assertEqual(self.j.path.read_bytes(),before)

    def test_repeated_phase_uuid_cannot_renew_original_budget(self):
        monitor=self.monitor();monitor.started(os.getpid())
        monitor.feed(self.frame(monitor,1,'hello'))
        phase=dict(phase_id=str(uuid.uuid4()),phase_kind='source',task_key=None,
            action_id=None,member='collect_source',member_sha256=None,profile_sha256=None)
        monitor.feed(self.frame(monitor,2,'phase_start',requested_seconds=1,**phase))
        monitor.feed(self.frame(monitor,3,'phase_end',**phase))
        monitor.feed(self.frame(monitor,4,'phase_start',requested_seconds=60,**phase))
        self.assertTrue(monitor.cancelled())
        self.assertEqual(monitor.reason,'channel_unverified')

    def test_wrong_pid_and_incomplete_final_frame_never_confirm_session(self):
        monitor=self.monitor();monitor.started(os.getpid()+1)
        monitor.feed(self.frame(monitor,1,'hello'))
        self.assertTrue(monitor.cancelled())
        other=self.monitor();other.started(os.getpid())
        other.feed(self.frame(other,1,'hello')[:-1]);other.finished(0,True)
        self.assertEqual(other.reason,'channel_unverified')

    def test_silent_startup_and_silent_interphase_remain_bounded(self):
        for hello in (False,True):
            monitor=self.monitor();now=[100.0]
            with patch('task_tower.group_supervision.time.monotonic',side_effect=lambda:now[0]):
                monitor.started(os.getpid())
                if hello:monitor.feed(self.frame(monitor,1,'hello'))
                now[0]+=5 if hello else 10
                self.assertTrue(monitor.cancelled())
                self.assertEqual(monitor.reason,'phase_timeout')

    def test_malformed_or_foreign_channel_never_becomes_execution_authority(self):
        for kind in ('nonce','domain','sequence','oversized','utf8','task'):
            monitor=self.monitor();monitor.started(os.getpid())
            frame=json.loads(self.frame(monitor,1,'hello'))
            if kind=='nonce':frame['session_id']=str(uuid.uuid4())
            elif kind=='domain':frame['domain']='pr'
            elif kind=='sequence':frame['sequence']=True
            elif kind=='task':frame.update(event='task_begin',task_binding={})
            raw=(json.dumps(frame)+'\n').encode()
            if kind=='oversized':raw=b'a'*4096
            elif kind=='utf8':raw=b'\xff\n'
            monitor.feed(raw)
            self.assertTrue(monitor.cancelled(),kind)
            self.assertEqual(monitor.reason,'channel_unverified')

    def test_actual_hello_end_child_confirms_only_complete_session(self):
        from task_tower.processes import run_command
        for ended in (False,True):
            monitor=self.monitor();root=self.f.root.resolve()
            capture=root/('valid-channel-'+str(ended));capture.mkdir()
            common=dict(version=1,domain='groups',session_id=monitor.session_id,owner_id=monitor.owner_id)
            script="import os,json,sys\nos.set_inheritable(sys.stdout.fileno(),False)\nb="+repr(common)+"\nb['pid']=os.getpid()\nprint(json.dumps(dict(b,sequence=1,event='hello')),flush=True)\n"
            if ended:script+="print(json.dumps(dict(b,sequence=2,event='session_end')),flush=True)\n"
            result=run_command([sys.executable,'-c',script],root,None,cancel_requested=lambda:False,
                lifecycle_monitor=monitor,capture=dict(directory=capture,max_bytes_per_stream=4096))
            self.assertEqual(result['status'],'passed' if ended else 'unknown',result)
            self.assertTrue(result['cleanup_confirmed'])
            self.assertFalse(result['stdout_tail_unknown'])

    def test_actual_fixed_source_helper_reads_registered_empty_queue_without_journal_writes(self):
        from task_tower.group_supervision import observe_source
        self.seed();self._seeded=True
        with self.load() as ctx:
            self.j.register_groups(ctx);before=self.j.path.read_bytes()
            result=observe_source(ctx)
            self.assertEqual(result['status'],'source_observed',result)
            self.assertTrue(result['process']['started'])
            self.assertTrue(result['process']['cleanup_confirmed'])
            self.assertFalse(result['process']['stdout_tail_unknown'])
            self.assertEqual(self.j.path.read_bytes(),before)

    def test_revoked_private_input_refuses_before_source_child_launch(self):
        from task_tower.group_supervision import observe_source
        self.seed();self._seeded=True
        with self.load() as ctx:
            self.j.register_groups(ctx)
            raw=ctx.groups_path.read_bytes()
            try:
                ctx.groups_path.write_bytes(raw+b' ')
                with patch('task_tower.processes.run_command',side_effect=AssertionError('Revoked source launched')) as launch:
                    with self.assertRaises(ValueError):observe_source(ctx)
                    launch.assert_not_called()
            finally:ctx.groups_path.write_bytes(raw)

    def test_actual_source_child_and_descendant_are_killed_at_original_phase_deadline(self):
        from task_tower.processes import run_command
        monitor=self.monitor()
        root=self.f.root.resolve();capture=root/'supervision-capture';capture.mkdir()
        marker=root/'escaped-source-descendant'
        phase=dict(phase_id=str(uuid.uuid4()),phase_kind='source',task_key=None,
            action_id=None,member='collect_source',member_sha256=None,profile_sha256=None,requested_seconds=1)
        common=dict(version=1,domain='groups',session_id=monitor.session_id,owner_id=monitor.owner_id)
        descendant="import time,pathlib;time.sleep(2);pathlib.Path("+repr(str(marker))+").write_text('escaped')"
        script="import os,sys,json,subprocess,time\nos.set_inheritable(sys.stdout.fileno(),False)\nb="+repr(common)+"\nb['pid']=os.getpid()\nprint(json.dumps(dict(b,sequence=1,event='hello')),flush=True)\nprint(json.dumps(dict(b,sequence=2,event='phase_start',**"+repr(phase)+")),flush=True)\nsubprocess.Popen([sys.executable,'-c',"+repr(descendant)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\ntime.sleep(3)\n"
        before=self.j.path.read_bytes();start=time.monotonic()
        result=run_command([sys.executable,'-c',script],root,None,
            cancel_requested=lambda:False,lifecycle_monitor=monitor,
            capture=dict(directory=capture,max_bytes_per_stream=4096))
        self.assertEqual(result['status'],'cancelled',result)
        self.assertTrue(result['started']);self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(monitor.reason,'phase_timeout')
        self.assertLess(time.monotonic()-start,5)
        time.sleep(2.1);self.assertFalse(marker.exists())
        self.assertEqual(self.j.path.read_bytes(),before)
