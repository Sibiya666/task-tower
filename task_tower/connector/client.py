"""Bounded authenticated loopback transport and explicit assignment execution.

Managed commands use fixed role workers and an optional trusted delivery adapter.
"""
import http.client
import io
import json
import time
import threading
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
    def accept(self,key,request_id,merge,evidence):return self.request('POST','/v1/attempts/'+quote(identity(key),safe='')+'/accept',dict(version=1,request_id=request_id,merge=merge,evidence=evidence))['attempt']
    def ready(self,project):return self.request('GET','/v1/ready?project_id='+quote(identity(project),safe=''))['ready']
    def claim(self,body):return self.request('POST','/v1/claims',body)['attempt']
    def validate(self,attempt):return self.request('POST','/v1/attempts/'+quote(identity(attempt),safe='')+'/validate',{'version':1})['attempt']
    def send_event(self,event):return self.request('POST','/v1/events',event)
    def commands(self):return self.request('GET','/v1/commands')['commands']
    def validate_command(self,key):return self.request('POST','/v1/commands/'+quote(identity(key),safe='')+'/validate',{'version':1})['attempt']
    def dispatch(self,key,base):return self.request('POST','/v1/attempts/'+quote(identity(key),safe='')+'/dispatch',dict(version=1,base_sha=base))['attempt']
    def resume(self,key):return self.request('POST','/v1/attempts/'+quote(identity(key),safe='')+'/resume',dict(version=1))['attempt']
    def decisions(self):return self.request('GET','/v1/decisions')['decisions']
    def respond(self,key,answer):return self.request('POST','/v1/decisions/'+quote(identity(key),safe='')+'/respond',dict(version=1,answer=answer))['decision']

class Connector:
    def __init__(self,store,api,app,worktrees):
        self.store,self.api,self.app,self.worktrees=store,api,app,worktrees
        self.delivery_lock=threading.Lock();self.worker_lock=threading.Lock()
        self.delivery_stop=threading.Event();self.delivery_worker=None
    def flush(self):
        # Serialize delivery so event order and stable event IDs survive retries.
        # Never called synchronously by the active RPC polling loop.
        with self.delivery_lock:
            for event in self.store.pending_events():
                if self.delivery_stop.is_set():return False
                try:self.api.send_event(event)
                except Exception:return False
                self.store.ack(event['event_id'])
            return True
    def _deliver_async(self):
        with self.worker_lock:
            if self.delivery_stop.is_set() or (self.delivery_worker and self.delivery_worker.is_alive()):return
            if not self.store.pending_events():return
            def deliver():
                try:self.flush()
                except Exception:pass  # Unacknowledged durable events remain pending.
            self.delivery_worker=threading.Thread(target=deliver,daemon=True)
            self.delivery_worker.start()
    def close(self):
        self.delivery_stop.set()
        if self.delivery_worker:
            # APIClient bounds connect/write/response independently. Only this
            # owner's delivery worker is joined; its journal stays open until then.
            self.delivery_worker.join(3*getattr(self.api,'timeout',5)+1)
            if self.delivery_worker.is_alive():raise RuntimeError('delivery_cleanup_unconfirmed')
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
        self._deliver_async()
        return True


class LifecycleConnector(Connector):
    """At most the configured number of active attempts, each with its own RPC worker.

    Control-plane HTTP and delivery never run on a live RPC polling thread. These
    fixed workers are transport owners, not model-selected assistants/schedulers.
    """
    def __init__(self,store,api,worktrees,app_factory,*,max_active_tasks=2,delivery=None):
        super().__init__(store,api,None,worktrees)
        if type(max_active_tasks) is not int or not 1<=max_active_tasks<=32:raise ValueError('invalid_capacity')
        self.max_active_tasks=max_active_tasks;self.app_factory=app_factory;self.delivery=delivery
        self.workers={};self.worker_guard=threading.RLock();self.stop=threading.Event();self.seen=set()

    @staticmethod
    def _occupied(worker):
        return bool(worker['apps']) or worker['busy'] or worker.get('reserved',0)>0

    def tick(self):
        self._deliver_async()
        try:commands=self.api.commands()
        except Exception:return False
        import queue
        for command in commands:
            key=command['command_id'];attempt=command['attempt_id']
            if key in self.seen:continue
            if command['kind']=='deliver':
                if self.delivery is None:continue
                try:self.api.validate_command(key)
                except Exception:continue  # No host effect or local consumption before repo admission.
            # Replay returns durable local outcome; no second start/response.
            prior=next((d for d in self.store.commands() if d['command']['command_id']==key),None)
            if prior is not None:
                self.seen.add(key);continue
            with self.worker_guard:
                worker=self.workers.get(attempt)
                execution=command['kind'] in ('execute','review','revise','deliver')
                cleanup=self.store.cleanup_reservations()
                # Count each attempt once across live workers AND durable fences.
                # A restart supplies no process identity for an unknown cleanup;
                # it cannot start more work there or fabricate a stop ACK.
                active={a for a,w in self.workers.items() if self._occupied(w)}|cleanup
                if attempt in cleanup and (execution or worker is None or not worker['apps']):continue
                if execution and (worker is None or not self._occupied(worker)) and len(active)>=self.max_active_tasks:
                    continue
                self.store.receive(command);self.seen.add(key)
                new_worker=worker is None
                if new_worker:
                    worker=dict(queue=queue.Queue(4),apps={},replies={},busy=False,reserved=0)
                    self.workers[attempt]=worker
                    worker['thread']=threading.Thread(target=self._work,args=(attempt,worker),daemon=True)
                # Reserve before enqueueing, including reactivation of a quiescent
                # existing worker. A dequeue cannot open a gap before busy=True.
                if execution:worker['reserved']=worker.get('reserved',0)+1
                if command['kind']!='respond':worker['queue'].put_nowait(command)
                if new_worker:worker['thread'].start()
            if command['kind']=='respond':
                # Do not hold admission's lock during bounded HTTP/RPC. Other live
                # workers must keep draining notifications while a reply is sent.
                self._execute_lifecycle(command,worker)
        return True

    def _work(self,attempt,worker):
        import queue
        try:
            while not self.stop.is_set():
                try:command=worker['queue'].get(timeout=.02)
                except queue.Empty:command=None
                if command is not None:
                    with self.worker_guard:
                        worker['busy']=True
                        if command['kind'] in ('execute','review','revise','deliver'):
                            worker['reserved']=max(0,worker.get('reserved',0)-1)
                    try:self._execute_lifecycle(command,worker)
                    finally:
                        with self.worker_guard:worker['busy']=False
                for key,app in list(worker['apps'].items()):
                    data=self.store.command(key)
                    if data['phase'] in ('executing','needs_input'):
                        self._poll_lifecycle(key,app,worker)
        finally:
            for key,app in list(worker['apps'].items()):
                try:
                    app.close()
                    if self.store.command(key)['phase'] in ('executing','needs_input','starting'):
                        self.store.lifecycle_transition(key,'needs_reconciliation','failed')
                except Exception:
                    self.store.lifecycle_transition(key,'needs_reconciliation','failed')
            worker['apps'].clear()

    def _execute_lifecycle(self,command,worker):
        key=command['command_id'];kind=command['kind'];attempt=command['attempt_id']
        try:
            self.api.validate_command(key)
            if kind=='deliver':
                self.store.update(key,phase='starting')
                result=self.delivery.run(command,self.api,self.stop)
                if result is not None:
                    if result.get('phase')!='accepted' or not result.get('canonical_close'):raise ValueError('confirmed_delivery_required')
                    self.store.update(key,cleanup_confirmed=False)
                    for previous,app in list(worker['apps'].items()):
                        # close() verifies this owned transport's containment/readers;
                        # failure retains its app and occupancy plus the durable fence.
                        app.close();worker['apps'].pop(previous);worker['replies'].pop(previous,None)
                    self.store.update(key,cleanup_confirmed=True)
                self.store.update(key,phase='completed')
                return
            if kind=='quiesce':
                self.store.update(key,phase='starting')
                for previous,app in list(worker['apps'].items()):
                    app.close();worker['apps'].pop(previous)
                    if self.store.command(previous)['phase'] in ('executing','needs_input'):
                        self.store.update(previous,phase='stopped')
                self.store.lifecycle_transition(key,'completed','quiescent');return
            if kind=='respond':
                target=command['target_command_id'];app=worker['apps'].get(target);reply=worker['replies'].get(target)
                if (app is None and reply is None) or self.store.command(target)['phase']!='needs_input':raise ValueError('approval_process_missing')
                original=self.store.command(target).get('decision')
                if original!=command['request']:raise ValueError('approval_identity_mismatch')
                # A fast RPC ACK must not enqueue started/completed ahead of the
                # response outcome. Hold only the local journal lock, never HTTP.
                with self.store.lock:
                    self.store.update(key,phase='starting')
                    if reply is not None:reply(command['request']['request_id'],{'decision':'accept' if command['answer']=='approve' else 'decline'})
                    else:app.respond(command['request'],command['answer'])
                    self.store.update(target,phase='executing')
                    self.store.lifecycle_transition(key,'completed','responded')
                return
            def on_request(message,reply):
                import uuid
                method=message.get('method');p=message.get('params',{})
                current=self.store.command(key)
                if (method not in ('item/commandExecution/requestApproval','item/fileChange/requestApproval')
                        or (current.get('thread_id') is not None and p.get('threadId',current['thread_id'])!=current['thread_id'])):
                    raise ValueError('unsupported_or_foreign_request')
                request=dict(method=method,request_id=message['id'],question=p.get('reason') or 'Explicit '+method)
                worker['replies'][key]=reply
                self.store.update(key,phase='needs_input',decision=request)
                self.store.lifecycle_event(attempt,'approval',command_id=key,decision_id=str(uuid.uuid4()),request=request)
            if kind=='review':
                # Author worktree must still have exactly the complete source reviewed.
                source=self.worktrees.source(command['project_id'],attempt,command['base_sha'])
                if source!=command['source']:raise ValueError('source_changed_before_review')
                tree=self.worktrees.prepare_review(command['project_id'],attempt+'-r-'+key[:12],source['head_sha'])
            elif kind=='revise' and command.get('update_base'):
                tree=self.worktrees.prepare_revision(command['project_id'],attempt,command['base_sha'],command['update_base'])
            else:tree=self.worktrees.prepare(command['project_id'],attempt,command['base_sha'])
            self.api.validate_command(key)
            if kind=='revise':
                prior=next((d for d in reversed(self.store.commands()) if d['command']['attempt_id']==attempt and d['command'].get('kind') in ('execute','revise') and d['thread_id']==command['thread_id'] and d['command']['command_id'] in worker['apps']),None)
                if prior is None:prior=next((d for d in reversed(self.store.commands()) if d['command']['attempt_id']==attempt and d['command'].get('kind') in ('execute','revise') and d['thread_id']==command['thread_id']),None)
                if prior is None:raise ValueError('author_thread_unknown')
                app=worker['apps'].pop(prior['command']['command_id'],None)
                resumed=app is None
                if app is None:app=self.app_factory(tree['path'],request_handler=on_request)
                worker['apps'][key]=app
                app.transport.request_handler=on_request
                self.api.validate_command(key)
                thread=app.attach_thread(command['thread_id'],key,tree['path'],resume=resumed)
            else:
                app=self.app_factory(tree['path'],request_handler=on_request);worker['apps'][key]=app
                self.api.validate_command(key)
                thread=app.create_thread(tree['path'],command_id=key)
            self.api.validate_command(key)
            result=app.start_turn(thread,key,command['input'])
            if result['phase']!='executing':raise ValueError('turn_start_unknown')
            self.store.lifecycle_event(attempt,'started',command_id=key,thread_id=thread,turn_id=result['turn_id'])
        except Exception:
            self.store.lifecycle_transition(key,'needs_reconciliation','failed')

    def _poll_lifecycle(self,key,app,worker):
        import uuid
        data=self.store.command(key);command=data['command'];attempt=command['attempt_id']
        try:
            for message in app.notifications():
                p=message.get('params',{});method=message.get('method')
                if method=='connector/interrupted':raise ValueError('owned_app_interrupted')
                if 'id' in message and 'method' in message:
                    if method not in ('item/commandExecution/requestApproval','item/fileChange/requestApproval') or p.get('threadId')!=data['thread_id']:
                        raise ValueError('unsupported_or_foreign_request')
                    decision=dict(method=method,request_id=message['id'],question=p.get('reason') or 'Explicit '+method)
                    self.store.update(key,phase='needs_input',decision=decision)
                    self.store.lifecycle_event(attempt,'approval',command_id=key,decision_id=str(uuid.uuid4()),request=decision)
                elif method=='turn/completed' and p.get('threadId')==data['thread_id'] and p.get('turn',{}).get('id')==data['turn_id']:
                    turn=p['turn']
                    if turn.get('status')!='completed':raise ValueError('turn_not_completed')
                    text='\n'.join(i['text'] for i in turn.get('items',[]) if isinstance(i,dict) and i.get('type')=='agentMessage' and isinstance(i.get('text'),str))
                    payload=dict(thread_id=data['thread_id'],turn_id=data['turn_id'],result=text)
                    source=self.worktrees.source(command['project_id'],attempt,command['base_sha'])
                    if command['kind']=='review':
                        self.worktrees.prepare_review(command['project_id'],attempt+'-r-'+key[:12],command['source']['head_sha'])
                        if source!=command['source']:raise ValueError('source_changed_during_review')
                        from ..service.lifecycle import validate_review
                        validate_review(text,source,data['thread_id'])
                        app.close();worker['apps'].pop(key)
                    else:payload['source']=source
                    self.store.lifecycle_transition(key,'completed','completed',**payload)
        except Exception:
            self.store.lifecycle_transition(key,'needs_reconciliation','failed')

    def close(self):
        self.stop.set()
        for worker in self.workers.values():
            worker['thread'].join(110)
            if worker['thread'].is_alive():raise RuntimeError('lifecycle_cleanup_unconfirmed')
        super().close()
