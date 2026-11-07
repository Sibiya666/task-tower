"""Real stdio bursts must not turn display output into unknown execution."""
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from task_tower.connector.app_server import StdioTransport


class StreamingTransportTests(unittest.TestCase):
    @contextlib.contextmanager
    def transport(self,capacity=256):
        script="""import json,sys
from pathlib import Path
responses=0
for line in sys.stdin:
 m=json.loads(line)
 if 'method' not in m:
  responses+=1;continue
 if 'id' not in m:continue
 op=m['method'];print(json.dumps({'id':m['id'],'result':{'responses':responses}}),flush=True)
 if op=='burst':
  for i in range(600):print(json.dumps({'method':'item/commandExecution/outputDelta','params':{'delta':'public fixture output','threadId':'t1'}}),flush=True)
  print(json.dumps({'method':'turn/completed','params':{'threadId':'t1','turn':{'id':'turn1','status':'completed','items':[{'type':'agentMessage','text':'complete untruncated result'}]}}}),flush=True)
  print(json.dumps({'id':73,'method':'item/commandExecution/requestApproval','params':{'threadId':'t1','reason':'fixture decision'}}),flush=True)
  print(json.dumps({'id':74,'method':'item/commandExecution/outputDelta','params':{'threadId':'t1'}}),flush=True)
  Path('producer-done').write_text('done',encoding='utf-8')
 elif op=='critical-burst':
  for i in range(600):print(json.dumps({'method':'test/control','params':{'n':i}}),flush=True)
 elif op=='oversize':
  print('x'*1048577,flush=True)
"""
        original=subprocess.Popen
        def launch(argv,**kwargs):return original([sys.executable,'-u','-c',script],**kwargs)
        with tempfile.TemporaryDirectory() as temp,patch('task_tower.connector.app_server.subprocess.Popen',side_effect=launch):
            wire=StdioTransport(Path(sys.executable),Path(temp),timeout=2,capacity=capacity)
            try:yield wire,Path(temp)
            finally:wire.close()

    def test_tool_output_burst_preserves_completion_and_explicit_approvals(self):
        # Break: a finite public tool read fills the control queue and kills a live turn.
        with self.transport() as (wire,root):
            try:wire.request('burst',{})
            except Exception as e:self.fail('display output interrupted RPC: '+type(e).__name__)
            end=time.monotonic()+3
            while not wire.failed.is_set() and not (root/'producer-done').exists() and time.monotonic()<end:time.sleep(.01)
            self.assertFalse(wire.failed.is_set(),'display output burst exhausted the control queue')
            self.assertTrue((root/'producer-done').exists())
            messages=wire.notifications()
            done=[m for m in messages if m.get('method')=='turn/completed']
            self.assertEqual(len(done),1)
            self.assertEqual(done[0]['params']['turn']['items'][0]['text'],'complete untruncated result')
            self.assertEqual([m['id'] for m in messages if 'id' in m],[73,74])
            self.assertEqual(wire.request('check',{})['responses'],0)

    def test_critical_queue_overflow_stays_fail_closed_with_fixed_reason(self):
        # Break: solving telemetry pressure by unbounding/dropping control messages.
        with self.transport() as (wire,_):
            try:wire.request('critical-burst',{})
            except Exception:pass
            self.assertTrue(wire.failed.wait(3))
            notice=[m for m in wire.notifications() if m.get('method')=='connector/interrupted']
            self.assertEqual(notice[-1].get('params',{}).get('reason'),'rpc_read_queue_full')

    def test_oversize_line_limit_still_fails_without_payload_in_reason(self):
        with self.transport() as (wire,_):
            try:wire.request('oversize',{})
            except Exception:pass
            self.assertTrue(wire.failed.wait(3))
            notice=[m for m in wire.notifications() if m.get('method')=='connector/interrupted']
            self.assertEqual(notice[-1].get('params',{}),{'reason':'rpc_line_limit'})

    def test_transport_failure_reason_is_durable_and_untrusted_text_is_not_copied(self):
        from types import SimpleNamespace
        from task_tower.connector.store import ConnectorStore
        from task_tower.connector.client import LifecycleConnector
        for supplied,want in [('rpc_read_queue_full','rpc_read_queue_full'),('untrusted/private-path','owned_app_interrupted')]:
            with self.subTest(supplied=supplied),tempfile.TemporaryDirectory() as temp:
                local=ConnectorStore(Path(temp)/'journal','reason-fixture')
                connector=LifecycleConnector(local,None,None,None)
                try:
                    command=dict(version=1,kind='execute',command_id='c',attempt_id='a',project_id='p',base_sha='a'*40,input={'text':'approved'},source=dict(base_sha='a'*40,head_sha='a'*40,diff=''))
                    local.receive(command);local.update('c',phase='executing',thread_id='t1',turn_id='turn1')
                    app=SimpleNamespace(notifications=lambda:[dict(method='connector/interrupted',params={'reason':supplied})])
                    connector._poll_lifecycle('c',app,{})
                    data=local.command('c');self.assertEqual(data['phase'],'needs_reconciliation')
                    self.assertEqual(data.get('failure_reason'),want)
                    self.assertEqual(local.pending_events()[0]['lifecycle']['kind'],'failed')
                    self.assertNotIn('untrusted/private-path',str(local.commands()))
                finally:connector.close();local.close()
