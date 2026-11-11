"""Version-one, loopback-only HTTP polling API with connector-scoped bearer auth."""
import hmac
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import sys
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit

from .beads import ServiceError, identity, strict_json
from ..preparing_recovery import parse_receipt

MAX_BODY=65536
READ_TIMEOUT=5


class _DeadlineReader(io.RawIOBase):
    """Refresh the remaining total read budget on every underlying recv.

    A socket timeout alone restarts after each successful trickle. BufferedReader
    may call readinto many times for a single header line or body read.
    """
    def __init__(self,connection,deadline):
        super().__init__()
        self.connection,self.deadline=connection,deadline

    def readable(self):return True

    def readinto(self,buffer):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('request_read_deadline')
        self.connection.settimeout(remaining)
        return self.connection.recv_into(buffer)


def make_server(store,connectors,*,host='127.0.0.1',port=8765,poll_seconds=2,container_network=False):
    # Docker bridge publishing cannot reach a namespace-local loopback socket.
    # The packaged deployment opts in; Compose restricts HOST publication to loopback.
    if type(container_network) is not bool:raise ValueError('invalid_container_network')
    if container_network and (sys.platform!='linux' or not Path('/.dockerenv').is_file()):
        raise ValueError('container_namespace_required')
    if host!='127.0.0.1' and not (container_network and host=='0.0.0.0'):
        raise ValueError('loopback_required')
    if type(port) is not int or not 0<=port<=65535:raise ValueError('invalid_port')
    if type(poll_seconds) not in (int,float) or not math.isfinite(poll_seconds) or not .1<=poll_seconds<=60:
        raise ValueError('invalid_poll_interval')
    auth={}
    for key,value in connectors.items():
        identity(key)
        if not isinstance(value,dict) or set(value)!={'token','projects'}:raise ValueError('invalid_connector')
        token=value['token'];projects=value['projects']
        if (not isinstance(token,str) or not 32<=len(token)<=256 or not token.isascii()
                or not token.isalnum() or not isinstance(projects,list) or not projects
                or len(set(projects))!=len(projects)):
            raise ValueError('invalid_connector')
        for project in projects:store.beads.project(project)
        if any(hmac.compare_digest(token,other['token']) for other in auth.values()):
            raise ValueError('duplicate_token')
        auth[key]={'token':token,'projects':frozenset(projects)}

    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        server_version='TaskTower/1'
        sys_version=''

        def setup(self):
            super().setup()
            self.connection.settimeout(READ_TIMEOUT)
            self.rfile.close()
            self.rfile=io.BufferedReader(_DeadlineReader(
                self.connection,time.monotonic()+READ_TIMEOUT))

        def log_message(self,*args):pass  # No paths, tokens, payloads or user prose in logs.

        def _send(self,status,value):
            # Drain only an explicitly bounded, fixed-length rejected POST body.
            # Closing with unread bytes can reset TCP and discard the JSON error.
            # Authenticated near-limit overflow may drain up to twice MAX_BODY;
            # accepted JSON and the original total read deadline stay unchanged.
            if self.command=='POST' and not getattr(self,'_body_consumed',False):
                lengths=self.headers.get_all('Content-Length',[])
                if (not self.headers.get('Transfer-Encoding') and len(lengths)==1
                        and lengths[0].isdigit() and len(lengths[0])<=6
                        and 0<int(lengths[0])<=MAX_BODY*(2 if status==413 else 1)):
                    try:self.rfile.read(int(lengths[0]))
                    except OSError:
                        self.close_connection=True
                        return
                self._body_consumed=True
            raw=json.dumps(dict(version=1,**value),ensure_ascii=True,allow_nan=False).encode('utf-8')
            try:
                self.send_response(status)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers();self.wfile.write(raw)
            except OSError:self.close_connection=True

        def _authenticate(self):
            values=self.headers.get_all('X-Connector-ID',[])
            tokens=self.headers.get_all('Authorization',[])
            if len(values)!=1 or len(tokens)!=1 or self.headers.get('Origin'):
                raise ServiceError('unauthorized',401)
            connector=values[0];entry=auth.get(connector)
            if entry is None or not hmac.compare_digest(tokens[0], 'Bearer '+entry['token']):
                raise ServiceError('unauthorized',401)
            return connector,entry

        def _project(self,entry,project):
            identity(project)
            if project not in entry['projects']:raise ServiceError('project_forbidden',403)

        def _body(self):
            lengths=self.headers.get_all('Content-Length',[])
            if self.headers.get('Transfer-Encoding') or len(lengths)!=1 or not lengths[0].isdigit():
                raise ServiceError('invalid_framing',400)
            count=int(lengths[0])
            if count>MAX_BODY:raise ServiceError('body_too_large',413)
            if count<=0 or self.headers.get_content_type()!='application/json':
                raise ServiceError('invalid_body',400)
            self._body_consumed=True
            raw=self.rfile.read(count)
            if len(raw)!=count:raise ServiceError('incomplete_body',400)
            try:value=strict_json(raw.decode('utf-8'))
            except (ValueError,UnicodeError,RecursionError):raise ServiceError('invalid_json',400) from None
            if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1:
                raise ServiceError('invalid_version',400)
            return value

        def _fields(self,body,fields):
            if set(body)!=set(fields)|{'version'}:raise ServiceError('invalid_fields',400)

        def _owned(self,attempt_id,connector,entry):
            attempt=store.attempt(attempt_id,connector)
            self._project(entry,attempt['project_id'])
            return attempt

        def _preparing_scope(self,value,connector,entry):
            self._project(entry,value['project_id'])
            attempt=self._owned(value['attempt_id'],connector,entry)
            if attempt['project_id']!=value['project_id']:
                raise ServiceError('preparing_project_forbidden',403)

        def _handle(self,method):
            request_id=None
            try:
                connector,entry=self._authenticate()
                uri=urlsplit(self.path)
                if uri.scheme or uri.netloc or uri.fragment or len(self.path)>2048:
                    raise ServiceError('invalid_route',400)
                if method=='GET':
                    query=parse_qs(uri.query,keep_blank_values=True)
                    if uri.path=='/v1/ready' and set(query)=={'project_id'} and len(query['project_id'])==1:
                        project=query['project_id'][0];self._project(entry,project)
                        self._send(200,dict(ready=store.ready(project),poll_seconds=poll_seconds));return
                    if uri.path.startswith('/v1/attempts/') and not query:
                        attempt=self._owned(uri.path[len('/v1/attempts/'):],connector,entry)
                        self._send(200,dict(attempt=attempt));return
                    if uri.path=='/v1/issues' and set(query)=={'project_id','issue_number'} and all(len(v)==1 for v in query.values()):
                        project=query['project_id'][0];self._project(entry,project)
                        number=query['issue_number'][0]
                        if not number.isdigit() or len(number)>12:raise ServiceError('invalid_issue_number',400)
                        self._send(200,dict(issue=store.issue_lookup(project,int(number),connector)));return
                    if uri.path=='/v1/commands' and not query:
                        self._send(200,dict(commands=[c for c in store.lifecycle_commands(connector) if c['project_id'] in entry['projects']],poll_seconds=poll_seconds));return
                    if uri.path=='/v1/decisions' and not query:
                        decisions=[d for d in store.decisions(connector)
                                   if store.attempt(d['attempt_id'],connector)['project_id'] in entry['projects']]
                        self._send(200,dict(decisions=decisions));return
                    if uri.path.startswith('/v1/preparing/') and not query:
                        operation=store.preparing_status(uri.path[len('/v1/preparing/'):],connector)
                        self._preparing_scope(operation,connector,entry)
                        self._send(200,dict(preparing=operation));return
                    raise ServiceError('route_not_found',404)
                if uri.query:raise ServiceError('invalid_route',400)
                body=self._body()
                candidate=body.get('request_id')
                if isinstance(candidate,str):
                    try:request_id=identity(candidate)
                    except ServiceError:pass
                if 'connector_id' in body and body['connector_id']!=connector:
                    raise ServiceError('connector_forbidden',403)
                if uri.path=='/v1/preparing':
                    self._fields(body,{'receipt'});receipt=parse_receipt(body['receipt'])
                    self._preparing_scope(receipt,connector,entry)
                    self._send(200,dict(preparing=store.admit_preparing(receipt,connector)));return
                if uri.path.startswith('/v1/attempts/') and uri.path.endswith('/accept'):
                    self._fields(body,{'request_id','merge','evidence'})
                    key=uri.path[len('/v1/attempts/'):-len('/accept')];self._owned(key,connector,entry)
                    self._send(200,dict(attempt=store.accept_delivery(body['request_id'],key,connector,body['merge'],body['evidence'])));return
                if uri.path.startswith('/v1/commands/') and uri.path.endswith('/validate'):
                    self._fields(body,set());key=uri.path[len('/v1/commands/'):-len('/validate')]
                    a=store.validate_lifecycle_command(key,connector);self._project(entry,a['project_id'])
                    self._send(200,dict(attempt=a));return
                if uri.path.startswith('/v1/attempts/') and uri.path.endswith(('/dispatch','/resume')):
                    dispatch=uri.path.endswith('/dispatch');suffix='/dispatch' if dispatch else '/resume'
                    self._fields(body,{'base_sha'} if dispatch else set())
                    key=uri.path[len('/v1/attempts/'):-len(suffix)];self._owned(key,connector,entry)
                    a=store.start_lifecycle(key,connector,body['base_sha']) if dispatch else store.resume_lifecycle(key,connector)
                    self._send(200,dict(attempt=a));return
                if uri.path.startswith('/v1/decisions/') and uri.path.endswith('/respond'):
                    self._fields(body,{'answer'});key=uri.path[len('/v1/decisions/'):-len('/respond')]
                    d=next((d for d in store.decisions(connector) if d['decision_id']==key),None)
                    if d is None:raise ServiceError('decision_not_found',404)
                    self._owned(d['attempt_id'],connector,entry)
                    self._send(200,dict(decision=store.respond_decision(key,connector,body['answer'])));return
                if uri.path.startswith('/v1/attempts/') and uri.path.endswith('/validate'):
                    self._fields(body,set())
                    key=uri.path[len('/v1/attempts/'):-len('/validate')]
                    self._owned(key,connector,entry)
                    self._send(200,dict(attempt=store.validate_execution(key,connector)));return
                if uri.path=='/v1/issues/admit':
                    self._fields(body,{'request_id','project_id','issue_number','source_revision'})
                    self._project(entry,body['project_id'])
                    result=store.admit_issue(body['request_id'],body['project_id'],body['issue_number'],body['source_revision'],connector)
                    self._send(200,dict(issue=result));return
                if uri.path=='/v1/claims':
                    self._fields(body,{'request_id','project_id','bead_id','connector_id'})
                    self._project(entry,body['project_id'])
                    result=store.claim_request(body['request_id'],body['project_id'],body['bead_id'],connector)
                    self._send(200,dict(attempt=result));return
                if uri.path in ('/v1/plans/import','/v1/plans/adopt'):
                    self._fields(body,{'request_id','project_id','digest','plan'})
                    self._project(entry,body['project_id'])
                    operation=store.adopt_plan if uri.path.endswith('/adopt') else store.import_plan
                    result=operation(body['request_id'],body['project_id'],body['digest'],body['plan'])
                    self._send(200,dict(batch=result));return
                if uri.path=='/v1/events':
                    if 'preparing' in body:fields={'event_id','attempt_id','connector_id','preparing'}
                    elif 'lifecycle' in body:fields={'event_id','attempt_id','connector_id','lifecycle'}
                    else:fields={'event_id','attempt_id','connector_id','phase','execution_state','connection_state'} | ({'execution'} if 'execution' in body else set())
                    self._fields(body,fields)
                    self._owned(body['attempt_id'],connector,entry)
                    self._send(200,dict(attempt=store.record_event(body)));return
                if uri.path=='/v1/decisions':
                    self._fields(body,{'decision_id','attempt_id','connector_id','question'})
                    self._owned(body['attempt_id'],connector,entry)
                    self._send(200,dict(decision=store.decision(body)));return
                raise ServiceError('route_not_found',404)
            except ServiceError as error:
                self._send(error.status,dict(error=dict(code=error.code,retryable=error.retryable,request_id=request_id)))
            except TimeoutError:
                self.close_connection=True
            except (ValueError,TypeError,KeyError,RecursionError):
                self._send(400,dict(error=dict(code='invalid_request',retryable=False,request_id=request_id)))
            except Exception:
                self._send(503,dict(error=dict(code='service_unavailable',retryable=False,request_id=request_id)))

        def do_GET(self):self._handle('GET')
        def do_POST(self):self._handle('POST')

    # One process/one serial owner; slow readers are bounded by per-connection timeout.
    return HTTPServer((host,port),Handler)
