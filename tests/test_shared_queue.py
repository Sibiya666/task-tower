"""Two actual OS clients, one server-side ref store; not a GitHub pilot."""
import hashlib,json,sys,tempfile,threading,unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from task_tower.github_tasks import GitHubTasks,replace_metadata
from task_tower.processes import run_command

class Server:
    def __init__(self,race=False):
        self.lock=threading.Lock();self.refs={};self.commits={};self.posts=[];self.barrier=threading.Barrier(2) if race else None
        self.issues={n:dict(id=1000+n,number=n,title='Prepared task '+str(n),state='open',state_reason=None,
            body=replace_metadata('',dict(version=1,kind='task',mode='autonomous',status='open',task_id='TT-SHARED-'+str(n)))) for n in (1,2,3)}
        self.lose_claim=False;self.lose_intent=False
        parent=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.dispatch()
            def do_POST(self):self.dispatch()
            def do_PATCH(self):self.dispatch()
            def dispatch(self):
                value=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'null')
                if self.command=='POST' and self.path=='/git/refs' and parent.barrier:parent.barrier.wait(timeout=10)
                with parent.lock:
                    code,result=parent.request(self.command,self.path,value)
                if result=='DROP':self.connection.close();return
                raw=json.dumps(result).encode();self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.http.server_port)
    def close(self):self.http.shutdown();self.http.server_close();self.thread.join(5)
    def request(self,method,path,body):
        self.posts.append((method,path,body))
        if method=='GET' and path.startswith('/issues/'):return 200,self.issues[int(path.split('/')[-1])]
        if method=='POST' and path.startswith('/issues/') and path.endswith('/assignees'):
            issue=self.issues[int(path.split('/')[2])]
            issue['assignees']=[dict(login=login) for login in body['assignees']]
            return 201,issue
        if method=='GET' and path=='/git/ref/heads/main':return 200,dict(ref='refs/heads/main',object=dict(type='commit',sha='a'*40))
        if method=='GET' and path.startswith('/git/ref/'):
            ref='refs/'+path.removeprefix('/git/ref/')
            return (200,dict(ref=ref,object=dict(type='commit',sha=self.refs[ref]))) if ref in self.refs else (404,{})
        if method=='GET' and path.startswith('/git/commits/'):
            sha=path.split('/')[-1]
            return (200,dict(sha=sha,tree=dict(sha='b'*40),message='base',parents=[])) if sha=='a'*40 else (200,self.commits[sha])
        if method=='POST' and path=='/git/commits':
            sha=hashlib.sha1(json.dumps(body,sort_keys=True).encode()).hexdigest()
            self.commits[sha]=dict(sha=sha,message=body['message'],tree=dict(sha=body['tree']),parents=[dict(sha=p) for p in body['parents']])
            return 201,self.commits[sha]
        if method=='POST' and path=='/git/refs':
            if body['ref'] in self.refs:return 422,{}
            self.refs[body['ref']]=body['sha']
            if self.lose_claim:self.lose_claim=False;return 0,'DROP'
            return 201,dict(ref=body['ref'],object=dict(type='commit',sha=body['sha']))
        if method=='PATCH' and path.startswith('/git/refs/'):
            ref='refs/'+path.removeprefix('/git/refs/')
            if body.get('force') is not False or [p['sha'] for p in self.commits[body['sha']]['parents']]!=[self.refs[ref]]:return 422,{}
            self.refs[ref]=body['sha']
            if self.lose_intent:self.lose_intent=False;return 0,'DROP'
            return 200,dict(ref=ref,object=dict(type='commit',sha=body['sha']))
        raise AssertionError((method,path,body))
    def store(self):
        import urllib.request
        def transport(method,url,headers,payload,limit):
            path=url.removeprefix('https://api.github.com/repos/owner/repo')
            data=None if payload is None else json.dumps(payload).encode()
            with urllib.request.urlopen(urllib.request.Request(self.url+path,data=data,method=method,headers={'Content-Type':'application/json'}),timeout=10) as response:return response.read(limit+1)
        return GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)

class SharedQueueTests(unittest.TestCase):
    def setUp(self):self.server=Server();self.addCleanup(self.server.close)
    def queue(self):
        from task_tower.shared_queue import SharedQueue
        return SharedQueue(self.server.store(),str(uuid.uuid4()),allowlist=[dict(repository='owner/repo',issue=n,task_id='TT-SHARED-'+str(n)) for n in (1,2,3)],assignee='operator')
    def test_two_real_processes_racing_same_issue_receive_one_launch_permit(self):
        self.server.barrier=threading.Barrier(2)
        with tempfile.TemporaryDirectory() as directory:
            def actor(index):
                capture=Path(directory)/str(index);capture.mkdir()
                result=run_command([sys.executable,'-B','-m','tests.shared_claim_actor',self.server.url,str(uuid.uuid4()),'1'],Path(__file__).resolve().parents[1],30,capture=dict(directory=capture,max_bytes_per_stream=65536))
                self.assertEqual(result['status'],'passed',(capture/'stderr.log').read_text())
                self.assertTrue(result['cleanup_confirmed']);return json.loads((capture/'stdout.log').read_bytes())
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(actor,(0,1)))
        self.assertEqual(len({r['pid'] for r in results}),2)
        self.assertEqual(sum(r['permit'] for r in results),1)
        self.assertEqual(sum(r['assigned'] for r in results),1)
        self.assertEqual(self.server.issues[1]['assignees'],[dict(login='operator')])
        self.assertEqual(len(self.server.refs),1)
    def test_lost_claim_response_can_only_be_reconciled_before_execution(self):
        self.server.lose_claim=True;q=self.queue();claim=q.claim(1)
        self.assertIsNotNone(claim);self.assertTrue(q.assign(claim));permit=q.start(claim);self.assertIsNotNone(permit)
        q.consume(permit)
        with self.assertRaises(ValueError):q.consume(permit)
        self.assertIsNone(self.queue().claim(1))
    def test_lost_intent_response_never_returns_execution_permission(self):
        q=self.queue();claim=q.claim(1);self.assertTrue(q.assign(claim));self.server.lose_intent=True
        self.assertIsNone(q.start(claim));self.assertIsNone(q.start(claim))
        self.assertIsNone(self.queue().claim(1))
    def test_issue_changed_after_claim_cannot_start(self):
        q=self.queue();claim=q.claim(1);self.server.issues[1]['title']='Changed criteria'
        self.assertIsNone(q.start(claim))

    def test_already_assigned_issue_is_skipped_before_claim(self):
        self.server.issues[1]['assignees']=[dict(login='someone-else')]
        self.assertIsNone(self.queue().claim(1))
        self.assertEqual(self.server.refs,{})

    def test_assignee_is_published_only_after_atomic_claim(self):
        from task_tower.shared_queue import SharedQueue
        q=SharedQueue(self.server.store(),str(uuid.uuid4()),allowlist=[dict(repository='owner/repo',issue=1,task_id='TT-SHARED-1')],assignee='operator')
        claim=q.claim(1);self.assertIsNotNone(claim)
        self.assertTrue(q.assign(claim))
        self.assertEqual(self.server.issues[1]['assignees'],[dict(login='operator')])
        self.assertIsNotNone(q.start(claim))
