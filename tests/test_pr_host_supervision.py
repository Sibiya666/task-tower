"""Actual persistent host with HTTP-only fault transport, no model or GitHub writes."""
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_pr_context as fixture


class HostSupervisionTests(unittest.TestCase):
    setUp=fixture.ContextFactoryTests.setUp
    write=staticmethod(fixture.ContextFactoryTests.write)

    def test_idle_has_no_unbounded_private_reload_and_can_stop_cleanly(self):
        from task_tower.pr_supervision import supervise
        from task_tower.pr_context import PRPrivateInputs
        from task_tower.processes import run_command as actual_run
        self.raw.update(interval_seconds=60,reviewer_timeout_seconds=1);self.write(self.policy,self.raw)
        idle=self.root/'idle.txt';unbounded=self.root/'unbounded.txt';stop=threading.Event()
        script="import sys,time,pathlib\nfrom task_tower import pr_source,pr_supervision,pr_context\nstate={'active':False}\nsend=pr_supervision._Wire.send\n"
        script+="def observed(self,event,**kw):\n if event=='phase_start':state['active']=True\n if event=='phase_end':state['active']=False\n if event=='idle':pathlib.Path("+repr(str(idle))+").write_text('idle')\n return send(self,event,**kw)\npr_supervision._Wire.send=observed\nfresh=pr_context.PRHostContext._fresh_inputs\n"
        script+="def loaded(self):\n if pathlib.Path("+repr(str(idle))+").exists() and not state['active']:\n  pathlib.Path("+repr(str(unbounded))+").write_text('unbounded')\n  time.sleep(30)\n return fresh(self)\npr_context.PRHostContext._fresh_inputs=loaded\n"
        script+="pr_source.resolve_token=lambda:None\ndef unavailable(*args):raise OSError('HTTP fixture')\npr_source._transport=unavailable\nfrom task_tower._pr_host import main\nraise SystemExit(main(sys.argv[1:]))\n"
        def controlled(argv,*args,**kwargs):return actual_run([argv[0],'-B','-c',script,*argv[4:]],*args,**kwargs)
        def request_stop():
            deadline=time.monotonic()+20
            while not idle.exists() and time.monotonic()<deadline:time.sleep(.01)
            stop.set()
        thread=threading.Thread(target=request_stop,daemon=True);thread.start()
        with patch('task_tower.processes.run_command',side_effect=controlled):
            report=supervise(PRPrivateInputs(self.connections,self.policy,self.journal,self.pipeline),
                once=False,stop_requested=stop.is_set)
        thread.join(1)
        self.assertTrue(idle.exists());self.assertFalse(unbounded.exists())
        self.assertEqual(report['status'],'stopped');self.assertTrue(report['owner_retired'])

    def test_original_private_locator_is_required_before_host_or_journal_creation(self):
        from task_tower.pr_supervision import supervise
        from task_tower.pr_context import PRPrivateInputs
        with self.assertRaises(ValueError):
            supervise(PRPrivateInputs(self.connections,self.policy,self.journal,None),once=True)
        self.assertFalse(self.journal.exists())

    def test_actual_host_global_stop_kills_a_blocked_source_and_real_descendant(self):
        if getattr(self,'expire_source',False):
            self.raw['reviewer_timeout_seconds']=3;self.write(self.policy,self.raw)
        from task_tower.pr_supervision import supervise
        from task_tower.pr_context import PRPrivateInputs
        from task_tower.processes import run_command as actual_run
        entered=self.root/'entered.txt';escaped=self.root/'escaped.txt';stop=threading.Event()
        code="import os,sys,time,pathlib,subprocess\nfrom task_tower import pr_source\n"
        descendant_delay=5 if getattr(self,'expire_source',False) else 3
        code+="def blocked(*args):\n pathlib.Path("+repr(str(entered))+").write_text(str(time.monotonic()))\n subprocess.Popen([sys.executable,'-c',"+repr("import pathlib,time;time.sleep("+str(descendant_delay)+");pathlib.Path("+repr(str(escaped))+").write_text('escaped')")+"])\n time.sleep(30)\n raise OSError('fixture')\n"
        code+="pr_source._transport=blocked\npr_source.resolve_token=lambda:None\nfrom task_tower._pr_host import main\nraise SystemExit(main(sys.argv[1:]))\n"
        launches=[]
        def controlled(argv,*args,**kwargs):
            self.assertEqual(argv[1:4],['-B','-m','task_tower._pr_host'])
            launches.append(tuple(argv[:4]))
            return actual_run([argv[0],'-B','-c',code,*argv[4:]],*args,**kwargs)
        def request_stop():
            deadline=time.monotonic()+20
            while not entered.exists() and time.monotonic()<deadline:time.sleep(.02)
            if not getattr(self,'expire_source',False):stop.set()
        thread=threading.Thread(target=request_stop,daemon=True);thread.start()
        source_before=self.source.read_bytes()
        with patch('task_tower.processes.run_command',side_effect=controlled):
            report=supervise(PRPrivateInputs(self.connections,self.policy,self.journal,self.pipeline),
                once=False,stop_requested=stop.is_set)
        thread.join(1)
        self.assertTrue(entered.exists(),'Actual controller never reached the controlled HTTP read')
        if getattr(self,'expire_source',False):self.assertLess(time.monotonic()-float(entered.read_text()),4)
        self.assertEqual(len(launches),1)
        self.assertEqual(report['status'],'needs_input')
        self.assertTrue(report['cleanup_confirmed'])
        self.assertEqual(source_before,self.source.read_bytes())
        self.assertNotIn(str(self.root),json.dumps(report))
        time.sleep(3.2);self.assertFalse(escaped.exists())
        from task_tower.pr_journal import PRJournal
        self.assertEqual(PRJournal(self.journal).rows(),[])


class SourceDeadlineHostTests(HostSupervisionTests):
    expire_source=True
