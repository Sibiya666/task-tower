"""Bounded authenticated loopback transport and explicit assignment execution.

No role scheduler, review approval, merge or task closure is implemented here.
"""
import http.client
import io
import json
import time
from urllib.parse import urlsplit,quote
from ..service.beads import strict_json,identity
from .app_server import DecisionRequired

class _ResponseReader(io.RawIOBase):
    def __init__(self,sock,deadline):
        super().__init__();self.sock=sock;self.deadline=deadline;self.raw=sock.makefile('rb',buffering=0)
    def readable(self):return True
    def readinto(self,buffer):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('http_response_deadline')
        self.sock.settimeout(remaining);return self.raw.readinto(buffer)
    def close(self):
        try:self.raw.close()
        finally:super().close()

class _ResponseSocket:
    def __init__(self,sock,deadline):self.sock,self.deadline=sock,deadline
    def __getattr__(self,key):return getattr(self.sock,key)
    def makefile(self,*args,**kwargs):return io.BufferedReader(_ResponseReader(self.sock,self.deadline))

class APIClient:
    def __init__(self,endpoint,connector_id,token,*,timeout=5):
        u=urlsplit(endpoint)
        if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/') or u.query or u.fragment or u.username or u.password or not u.port:raise ValueError('loopback_endpoint_required')
        identity(connector_id)
        if not isinstance(token,str) or not 32<=len(token)<=256 or not token.isascii() or not token.isalnum():raise ValueError('invalid_token')
        self.port=u.port;self.connector_id=connector_id;self.token=token;self.timeout=timeout
    def request(self,method,path,body=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=self.timeout)
        try:
            raw=None if body is None else json.dumps(body,ensure_ascii=True,allow_nan=False).encode('utf-8')
            if raw is not None and len(raw)>65536:raise ValueError('body_limit')
            connection.connect()
            connection.sock=_ResponseSocket(connection.sock,time.monotonic()+self.timeout)
            connection.request(method,path,raw,{'X-Connector-ID':self.connector_id,'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
            deadline=time.monotonic()+self.timeout
            response=connection.getresponse();parts=[];total=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('http_deadline')
                data=response.read1(min(8192,1048577-total))
                if not data:break
                parts.append(data);total+=len(data)
                if total>1048576:raise ValueError('response_limit')
            value=strict_json(b''.join(parts).decode('utf-8'))
            if response.status!=200 or value.get('version')!=1 or 'error' in value:raise ConnectionError('api_request_rejected')
            return value
        finally:connection.close()
    def ready(self,project):return self.request('GET','/v1/ready?project_id='+quote(identity(project),safe=''))['ready']
    def claim(self,body):return self.request('POST','/v1/claims',body)['attempt']
    def validate(self,attempt):return self.request('POST','/v1/attempts/'+quote(identity(attempt),safe='')+'/validate',{'version':1})['attempt']
    def send_event(self,event):return self.request('POST','/v1/events',event)

class Connector:
    def __init__(self,store,api,app,worktrees):self.store,self.api,self.app,self.worktrees=store,api,app,worktrees
    def flush(self):
        for event in self.store.pending_events():
            try:self.api.send_event(event)
            except Exception:return False
            self.store.ack(event['event_id'])
        return True
    def claim(self,project,bead):
        if not self.flush():return None
        try:
            ready=self.api.ready(project)
            prior=self.store.existing_claim(project,bead)
            if prior is None and bead not in {r['id'] for r in ready}:return None
            return self.api.claim(prior or self.store.claim_intent(project,bead))
        except Exception:return None
    def _validate(self,command):
        a=self.api.validate(command['attempt_id'])
        if a['connector_id']!=self.store.connector_id or a['project_id']!=command['project_id'] or a['phase']!='claimed':raise ValueError('assignment_not_authorized')
        return a
    def execute(self,command):
        data=self.store.receive(command)
        if data['phase']!='queued':return data
        key=command['command_id']
        try:
            self._validate(command)
            self.store.update(key,phase='preparing')
            tree=self.worktrees.prepare(command['project_id'],command['attempt_id'],command['base_sha'])
            self.store.update(key,worktree_ref=tree)
            self._validate(command)
            thread=self.app.create_thread(tree['path'],command_id=key)
            self._validate(command)
            result=self.app.start_turn(thread,key,command['input'])
            phase=result['phase']
            self.store.event(command['attempt_id'],'executing' if phase=='executing' else phase,'running' if phase=='executing' else 'unknown')
            return result
        except DecisionRequired as error:
            result=self.store.update(key,phase='needs_input',decision=error.decision)
            self.store.event(command['attempt_id'],'needs_input','unknown');return result
        except Exception:
            result=self.store.update(key,phase='needs_reconciliation')
            self.store.event(command['attempt_id'],'needs_reconciliation','unknown');return result
    def poll(self):
        for msg in self.app.notifications():
            params=msg.get('params',{});method=msg.get('method')
            for data in self.store.commands():
                if data['phase'] not in ('executing','needs_input'):continue
                key=data['command']['command_id'];attempt=data['command']['attempt_id']
                if method=='connector/interrupted':
                    self.store.transition(key,'needs_reconciliation','unknown')
                elif 'id' in msg and 'method' in msg and (params.get('threadId') is None or params.get('threadId')==data['thread_id']):
                    self.store.transition(key,'needs_input','unknown',decision=dict(method=method,request_id=msg['id']))
                elif method=='turn/completed' and params.get('threadId')==data['thread_id'] and params.get('turn',{}).get('id')==data['turn_id']:
                    complete=params['turn'].get('status')=='completed'
                    execution=None
                    if complete:
                        items=params['turn'].get('items',[])
                        text='\n'.join(item['text'] for item in items if isinstance(item,dict) and item.get('type')=='agentMessage' and isinstance(item.get('text'),str))
                        execution=dict(command_id=key,thread_id=data['thread_id'],turn_id=data['turn_id'],result=text)
                        if len(text.encode('utf-8'))>32768:complete=False;execution=None
                    try:self.store.transition(key,'completed' if complete else 'needs_reconciliation','completed' if complete else 'unknown',execution=execution,completion=params['turn'])
                    except ValueError:self.store.transition(key,'needs_reconciliation','unknown')
        return self.flush()
