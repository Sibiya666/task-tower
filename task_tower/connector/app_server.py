"""Owned bidirectional stdio JSON-RPC. Correlation IDs grant no replay safety."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from ..service.beads import strict_json

TRANSPORT_FAILURES=frozenset({'rpc_read_queue_full','rpc_line_limit','rpc_invalid_utf8',
    'rpc_invalid_message','rpc_stdout_read_failed','rpc_stdout_eof','owned_app_interrupted'})

class RpcError(RuntimeError):pass
class DecisionRequired(RuntimeError):
    def __init__(self,request):
        super().__init__('explicit_app_server_decision_required')
        self.decision=dict(method=request.get('method','unknown_callback'),request_id=request.get('id')) if isinstance(request,dict) else dict(method='unknown_callback')

class StdioTransport:
    MAX_LINE=1048576
    def __init__(self,executable,cwd,*,timeout=30,capacity=256,request_handler=None):
        if not Path(executable).is_absolute() or not Path(cwd).is_absolute():raise ValueError('absolute_path_required')
        self.request_handler=request_handler
        self.timeout=timeout;self.q=queue.Queue(capacity);self.events=queue.Queue(capacity)
        self.failure_reason=None
        self.failed=threading.Event();self.serial=threading.RLock();self.counter=0;self.stderr_tail=bytearray()
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN') and not k.upper().startswith(('BD_','BEADS_','DOLT_','TOWER_','TASK_TOWER_'))}
        self.process=subprocess.Popen([str(executable),'app-server','--listen','stdio://'],cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
        self.job=None
        if os.name=='nt':
            import ctypes
            from ..windows_job import _kernel,_ExtendedLimit
            self.kernel=_kernel();self.job=self.kernel.CreateJobObjectW(None,None)
            limits=_ExtendedLimit();limits.basic.flags=0x2000
            if not self.job or not self.kernel.SetInformationJobObject(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(self.job,int(self.process._handle)):
                self.process.terminate();self.process.wait(timeout=5)
                if self.job:self.kernel.CloseHandle(self.job);self.job=None
                raise RpcError('process_containment_unavailable')
        self._start_writer()
        self.readers=[threading.Thread(target=self._read,daemon=True),threading.Thread(target=self._stderr,daemon=True)]
        for t in self.readers:t.start()
        try:
            self.request('initialize',{'clientInfo':{'name':'task_tower_connector','title':'Task Tower connector','version':'1'}})
            self._send({'method':'initialized'})
        except BaseException:self.close();raise
    def _read(self):
        try:
            while True:
                line=self.process.stdout.readline(self.MAX_LINE+1)
                if not line:self.failure_reason='rpc_stdout_eof';return
                if len(line)>self.MAX_LINE or not line.endswith(b'\n'):
                    self.failure_reason='rpc_line_limit';raise ValueError('rpc_line_limit')
                msg=strict_json(line.decode('utf-8'))
                if not isinstance(msg,dict):raise ValueError('invalid_rpc')
                # Tool display output is not consumed by this headless lifecycle.
                # Keep every response, callback and completion; never let unused
                # output deltas exhaust their bounded control queue.
                if msg.get('method')=='item/commandExecution/outputDelta' and 'id' not in msg:continue
                self.q.put_nowait(msg)
        except queue.Full:self.failure_reason='rpc_read_queue_full'
        except UnicodeError:self.failure_reason='rpc_invalid_utf8'
        except (ValueError,RecursionError):
            if self.failure_reason is None:self.failure_reason='rpc_invalid_message'
        except Exception:self.failure_reason='rpc_stdout_read_failed'
        finally:self.failed.set()
    def _stderr(self):
        try:
            while True:
                raw=self.process.stderr.read(4096)
                if not raw:return
                self.stderr_tail.extend(raw);del self.stderr_tail[:-65536]
        except OSError:self.failed.set()
    def _start_writer(self):
        self.writes=queue.Queue(1)
        def write():
            while not self.failed.is_set():
                try:raw,done=self.writes.get(timeout=.1)
                except queue.Empty:continue
                try:self.process.stdin.write(raw);self.process.stdin.flush()
                except (OSError,ValueError):self.failed.set()
                finally:done.set()
        self.writer=threading.Thread(target=write,daemon=True);self.writer.start()
    def _send(self,msg):
        raw=(json.dumps(msg,ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
        if len(raw)>self.MAX_LINE:raise ValueError('rpc_input_limit')
        done=threading.Event()
        try:self.writes.put_nowait((raw,done))
        except queue.Full:raise RpcError('rpc_write_queue_full') from None
        if not done.wait(self.timeout):
            self.failed.set();raise TimeoutError('rpc_write_outcome_unknown')
        if self.failed.is_set():raise RpcError('rpc_write_failed')
    def _event(self,msg):
        if 'id' in msg and 'method' in msg and self.request_handler is not None:
            self.request_handler(msg,self.respond);return
        try:self.events.put_nowait(msg)
        except queue.Full:self.failed.set();raise RpcError('notification_limit') from None
        if 'id' in msg and 'method' in msg:raise DecisionRequired(msg)
    def request(self,method,params):
        with self.serial:
            if self.failed.is_set():raise RpcError('app_server_unavailable')
            self.counter+=1;key=self.counter;self._send(dict(id=key,method=method,params=params))
            deadline=time.monotonic()+self.timeout
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('rpc_response_unknown')
                try:msg=self.q.get(timeout=min(.1,remaining))
                except queue.Empty:
                    if self.failed.is_set():raise RpcError('app_server_interrupted')
                    continue
                if msg.get('id')==key and 'method' not in msg:
                    if 'error' in msg:raise RpcError('rpc_rejected')
                    if not isinstance(msg.get('result'),dict):raise RpcError('invalid_rpc_result')
                    return msg['result']
                self._event(msg)
    def respond(self,key,result):
        self._send(dict(id=key,result=result))
    def notifications(self):
        with self.serial:
            result=[]
            while True:
                try:result.append(self.events.get_nowait())
                except queue.Empty:break
            while True:
                try:msg=self.q.get_nowait()
                except queue.Empty:break
                result.append(msg)
            if self.failed.is_set():result.append({'method':'connector/interrupted',
                'params':{'reason':getattr(self,'failure_reason',None) or 'owned_app_interrupted'}})
            return result
    def close(self):
        p=self.process
        # Stop writer before closing its pipe. Closing a pipe under a stalled write
        # can itself block, so containment is terminated first in that case.
        self.failed.set();self.writer.join(.25)
        try:
            if self.writer.is_alive():raise subprocess.TimeoutExpired('rpc_writer',.25)
            if p.stdin and not p.stdin.closed:p.stdin.close()
            p.wait(timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            if os.name=='nt':
                if not self.kernel.TerminateJobObject(self.job,1):raise RpcError('process_cleanup_unknown')
            else:
                import signal
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            p.wait(timeout=10)
        finally:
            if os.name=='nt' and self.job:
                if not self.kernel.CloseHandle(self.job):raise RpcError('process_cleanup_unknown')
                self.job=None
            elif os.name!='nt':
                import signal
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        self.writer.join(2)
        if self.writer.is_alive():raise RpcError('writer_cleanup_unknown')
        if p.stdin and not p.stdin.closed:p.stdin.close()
        for t in self.readers:t.join(2)
        for stream in (p.stdout,p.stderr):
            if stream:stream.close()
        if any(t.is_alive() for t in self.readers):raise RpcError('reader_cleanup_unknown')

class AppServer:
    def __init__(self,store,*,transport=None,executable=None,cwd=None,request_handler=None):
        self.store=store;self.transport=transport or StdioTransport(executable,cwd,request_handler=request_handler)
        if request_handler is not None:self.transport.request_handler=request_handler
    def create_thread(self,cwd,command_id=None):
        if command_id is None:raise ValueError('durable_command_required')
        data=self.store.command(command_id)
        if data['thread_id']:return data['thread_id']
        if data['phase'] not in ('queued','preparing'):raise ValueError('thread_creation_fenced')
        self.store.update(command_id,phase='creating_thread')
        try:
            result=self.transport.request('thread/start',{'cwd':str(cwd)})
            key=result['thread']['id']
            if not isinstance(key,str) or not key:raise RpcError('invalid_thread')
            self.store.update(command_id,thread_id=key,phase='prepared')
            return key
        except DecisionRequired as error:
            self.store.update(command_id,phase='needs_input',decision=error.decision);raise
        except Exception:
            self.store.update(command_id,phase='needs_reconciliation');raise
    def start_turn(self,thread_id,command_id,input):
        data=self.store.command(command_id)
        if input!=data['command']['input'] or thread_id!=data['thread_id']:raise ValueError('command_conflict')
        if data['phase'] in ('executing','completed','needs_reconciliation','needs_input'):return data
        if data['phase']!='prepared':raise ValueError('turn_start_fenced')
        self.store.update(command_id,phase='starting')
        try:
            text=input['text']
            if data['command'].get('kind') in ('review','main_review'):text+='\nYour actual reviewer_thread_id: '+thread_id
            result=self.transport.request('turn/start',{'threadId':thread_id,'input':[dict(type='text',text=text)]})
            key=result['turn']['id']
            if not isinstance(key,str) or not key:raise RpcError('invalid_turn')
            return self.store.update(command_id,phase='executing',turn_id=key)
        except DecisionRequired as error:
            return self.store.update(command_id,phase='needs_input',decision=error.decision)
        except Exception:
            return self.store.update(command_id,phase='needs_reconciliation')
    def attach_thread(self,thread_id,command_id,cwd,*,resume=False):
        data=self.store.command(command_id)
        if data['phase']!='queued':raise ValueError('existing_thread_fenced')
        self.store.update(command_id,phase='creating_thread')
        if resume:
            result=self.transport.request('thread/resume',{'threadId':thread_id,'cwd':str(cwd)})
            if result.get('thread',{}).get('id')!=thread_id:raise RpcError('resume_identity_mismatch')
        self.store.update(command_id,phase='prepared',thread_id=thread_id)
        return thread_id
    def respond(self,request,answer):
        if answer not in ('approve','decline'):raise ValueError('invalid_answer')
        if not hasattr(self.transport,'respond'):raise RpcError('response_transport_unavailable')
        self.transport.respond(request['request_id'],{'decision':'accept' if answer=='approve' else 'decline'})
    def inspect(self,thread_id):
        metadata=self.transport.request('thread/read',{'threadId':thread_id,'includeTurns':False})
        try:return dict(metadata=metadata,history=self.transport.request('thread/read',{'threadId':thread_id,'includeTurns':True}),history_state='complete')
        except Exception:return dict(metadata=metadata,history=None,history_state='partial')
    def notifications(self):return self.transport.notifications()
    def close(self):
        if hasattr(self.transport,'close'):self.transport.close()
