"""Fixed trusted-host delivery. Remote prose never selects an operation or endpoint.

The connector's single-owner journal fences every merge intent across restarts.
A repository lease spans merge AND exact-main acceptance, including failures.
"""
import copy
import json
import re
from ..service.store import encoded
from ..service.lifecycle import validate_review
from ..service.beads import ServiceError,identity

class Pending(ValueError):
    """Known incomplete remote validation; bounded polling may continue."""

class SourceChanged(ValueError):
    def __init__(self,base):self.base_sha=sha(base);super().__init__('source_changed')

def sha(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{40}',value) is None:raise ValueError('invalid_sha')
    return value

def independent(a):
    try:
        r=validate_review(encoded(a['review']),a['source'],a['review']['reviewer_thread_id'])
        if (r['verdict']!='approve' or r['reviewer_thread_id']==a['author_thread_id']
                or r['reviewer_thread_id'] not in a['review_threads']
                or a['head_sha']!=r['head_sha'] or a['base_sha']!=r['base_sha']):raise ValueError()
        return r
    except (KeyError,TypeError,ServiceError,ValueError):raise ValueError('independent_review_required') from None

class Delivery:
    def __init__(self,host,store,projects):
        self.host,self.store=host,store;self.projects=dict(projects)
        if not self.projects or any(not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',v) for v in self.projects.values()):raise ValueError('invalid_repository_allowlist')
        with store.lock,store.db:
            store.db.executescript("""
CREATE TABLE IF NOT EXISTS deliveries (attempt_id TEXT PRIMARY KEY,repository TEXT NOT NULL,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repository_delivery (repository TEXT PRIMARY KEY,attempt_id TEXT NOT NULL);
""")
    def _repository(self,r):
        if r not in self.projects.values():raise ValueError('repository_forbidden')
        return r
    def _save(self,d):
        with self.store.lock,self.store.db:
            self.store.db.execute('INSERT INTO deliveries VALUES (?,?,?) ON CONFLICT(attempt_id) DO UPDATE SET data=excluded.data',
                (d['attempt']['attempt_id'],d['repository'],encoded(d)))
        return d
    def _load(self,r,p=None,attempt=None):
        self._repository(r)
        with self.store.lock:
            rows=[json.loads(row[0]) for row in self.store.db.execute('SELECT data FROM deliveries WHERE repository=?',(r,))]
        matches=[d for d in rows if (attempt is None or d['attempt']['attempt_id']==attempt) and (p is None or d.get('pr_number')==p)]
        if len(matches)!=1:raise ValueError('delivery_identity_unknown')
        return matches[0]
    def _lease(self,d):
        with self.store.lock,self.store.db:
            row=self.store.db.execute('SELECT attempt_id FROM repository_delivery WHERE repository=?',(d['repository'],)).fetchone()
            if row and row[0]!=d['attempt']['attempt_id']:raise Pending('repository_busy')
            self.store.db.execute('INSERT OR IGNORE INTO repository_delivery VALUES (?,?)',(d['repository'],d['attempt']['attempt_id']))
    def release(self,attempt):
        # Only after the service returns canonical accepted + owner-close readback.
        if attempt.get('phase')!='accepted' or not attempt.get('canonical_close'):raise ValueError('acceptance_required')
        d=self._load(attempt['repository'],attempt['pr_number'])
        if d['attempt']['attempt_id']!=attempt['attempt_id'] or d.get('evidence')!=attempt.get('accepted_evidence'):raise ValueError('acceptance_mismatch')
        with self.store.lock,self.store.db:self.store.db.execute('DELETE FROM repository_delivery WHERE repository=? AND attempt_id=?',(d['repository'],attempt['attempt_id']))
    def prepare_pr(self,a):
        if a.get('phase')!='awaiting_merge' or a.get('project_id') not in self.projects:raise ValueError('delivery_not_authorized')
        independent(a);identity(a['attempt_id']);sha(a['head_sha']);sha(a['base_sha'])
        r=self.projects[a['project_id']]
        with self.store.lock:
            row=self.store.db.execute('SELECT data FROM deliveries WHERE attempt_id=?',(a['attempt_id'],)).fetchone()
        if row:
            d=json.loads(row[0])
            if d['attempt']!=a and d['phase']!='superseded':raise ValueError('delivery_source_changed')
            if d['phase']=='superseded':
                if d['attempt']['base_sha']==a['base_sha'] or d.get('merge_result'):raise ValueError('delivery_source_changed')
                prior=d.get('previous',[])+[{k:v for k,v in d.items() if k!='previous'}]
                d=self._save(dict(attempt=copy.deepcopy(a),repository=r,phase='preparing',previous=prior))
                pr=self.host.prepare_pr(a);self._pr(pr,r,pr.get('number'),a['head_sha'],a['base_sha'],a)
                d.update(pr_number=pr['number'],phase='prepared');self._save(d)
                return dict(repository=r,pr_number=pr['number'])
            if d.get('pr_number'):return dict(repository=r,pr_number=d['pr_number'])
            # A lost push/PR response is never blindly repeated.
            raise ValueError('prepare_needs_reconciliation')
        d=self._save(dict(attempt=copy.deepcopy(a),repository=r,phase='preparing'))
        pr=self.host.prepare_pr(a)
        try:self._pr(pr,r,pr.get('number'),a['head_sha'],a['base_sha'],a)
        except SourceChanged:
            d.update(pr_number=pr['number'],phase='prepared');self._save(d);raise
        d.update(pr_number=pr['number'],phase='prepared');self._save(d)
        return dict(repository=r,pr_number=pr['number'])
    def _pr(self,pr,r,p,h,b,a,*,merged=False):
        if (type(p) is not int or p<1 or not isinstance(pr,dict) or pr.get('repository')!=r or pr.get('number')!=p
                or pr.get('head_repository')!=r or pr.get('base_ref')!='main' or pr.get('branch')!='codex/headless-'+a['attempt_id']):raise ValueError('foreign_pr')
        if pr.get('head_sha')!=h:raise ValueError('head_changed')
        if not merged and pr.get('base_sha')!=b:raise SourceChanged(pr.get('base_sha'))
        if not merged and (pr.get('state')!='open' or pr.get('merged') is not False):raise ValueError('pr_not_open')
    def verify_pr(self,repository,pr,head,base):
        d=self._load(repository,pr);a=d['attempt']
        if (head,base)!=(a['head_sha'],a['base_sha']):raise ValueError('review_source_mismatch')
        review=independent(a);row=self.host.read_pr(repository,pr);self._pr(row,repository,pr,head,base,a)
        protection=self.host.protection(repository)
        required={'scope','unittest (windows-latest)','task-tower/pr-acceptance'}
        if (any(protection.get(k) is not True for k in ('enforce_admins','strict','required_conversation_resolution'))
                or protection.get('allow_force_pushes') is not False or protection.get('allow_deletions') is not False
                or not required.issubset(set(protection.get('required_checks',[])))):raise ValueError('protection_required')
        if row.get('conversations_resolved') is not True:raise ValueError('unresolved_conversations')
        checks=self.host.read_checks(repository,head)
        if any(c.get('head_sha')!=head or c.get('app')!='github-actions' for c in checks):raise ValueError('foreign_ci_source')
        if any(c.get('conclusion') is None for c in checks):raise Pending('ci_pending')
        shards={'unittest shard (windows-latest, '+str(i)+')' for i in range(4)}
        for name in required-{'task-tower/pr-acceptance'}|shards:
            matches=[c for c in checks if c.get('name')==name]
            if not matches:raise Pending('ci_pending')
            if len(matches)!=1 or matches[0]['conclusion'] not in (('success','skipped') if name in shards else ('success',)):raise ValueError('required_ci_not_successful')
        shard_results={c['conclusion'] for c in checks if c['name'] in shards}
        if len(shard_results)!=1:raise ValueError('mixed_runtime_shards')
        # Only the complete expected docs matrix may skip. Every other current
        # job must succeed; cancelled/neutral/timed-out are never acceptance.
        if any(c['conclusion']!='success' and not (c['name'] in shards and c['conclusion']=='skipped') for c in checks):raise ValueError('current_ci_not_successful')
        status=d.get('acceptance_status')
        if status is None:
            if not d.get('status_intent'):
                d['status_intent']=True;self._save(d)
                try:status=self.host.publish_acceptance(repository,head,review)
                except Exception:status=self.host.read_acceptance(repository,head)
            else:status=self.host.read_acceptance(repository,head)
            if status is None:raise ValueError('status_needs_reconciliation')
            d['acceptance_status']=status;self._save(d)
        actual=self.host.read_acceptance(repository,head)
        if (actual!=status or not isinstance(actual,dict) or type(actual.get('id')) is not int or actual['id']<1
                or actual.get('head_sha')!=head or actual.get('context')!='task-tower/pr-acceptance' or actual.get('state')!='success'
                or actual.get('review')!=review):raise ValueError('genuine_acceptance_required')
        # Re-read H/B after every status/CI/protection read, immediately before intent.
        row=self.host.read_pr(repository,pr);self._pr(row,repository,pr,head,base,a)
        if row.get('mergeable') is None or row.get('mergeable_state') in ('unknown','blocked'):raise Pending('mergeability_pending')
        if row.get('mergeable') is not True or row.get('mergeable_state')!='clean':raise ValueError('not_mergeable')
        return dict(repository=repository,pr_number=pr,head_sha=head,base_sha=base,status_id=status['id'])
    def merge_expected(self,repository,pr,head,base):
        d=self._load(repository,pr);self._lease(d)
        if (head,base)!=(d['attempt']['head_sha'],d['attempt']['base_sha']):raise ValueError('merge_source_mismatch')
        if d.get('merge_result'):return d['merge_result']
        if d['phase']=='merge_intent':return self._merge_readback(d)
        if d['phase']!='prepared':raise ValueError('merge_fenced')
        self.verify_pr(repository,pr,head,base)
        d=self._load(repository,pr);d['phase']='merge_intent';self._save(d)
        try:self.host.merge(repository,pr,head)
        except Exception:pass  # Read the fact, including when the response was lost.
        return self._merge_readback(d)
    def _merge_readback(self,d):
        try:
            row=self.host.read_pr(d['repository'],d['pr_number']);a=d['attempt']
            self._pr(row,d['repository'],d['pr_number'],a['head_sha'],a['base_sha'],a,merged=True)
            if row.get('merged') is not True or row.get('state')!='closed':raise ValueError()
            result=dict(repository=d['repository'],pr_number=d['pr_number'],head_sha=a['head_sha'],base_sha=a['base_sha'],main_sha=sha(row.get('merge_commit_sha')))
        except Exception:raise ValueError('merge_needs_reconciliation') from None
        d.update(phase='postmerge',merge_result=result);self._save(d);return result
    def run(self,command,api,stop):
        a=command['attempt'];key=command['command_id']
        if (a['attempt_id'],a['project_id'])!=(command['attempt_id'],command['project_id']):raise ValueError('delivery_assignment_mismatch')
        api.validate_command(key)
        try:prepared=self.prepare_pr(a)
        except SourceChanged as error:return self._changed(command,error)
        r=prepared['repository'];p=prepared['pr_number']
        while not stop.is_set():
            api.validate_command(key)
            try:
                merge=self.merge_expected(r,p,a['head_sha'],a['base_sha'])
                self._notify_merge(command,api,merge)
                evidence=self.verify_main(r,p,merge['main_sha'])
                try:accepted=api.accept(a['attempt_id'],key,merge,evidence)
                except Exception:
                    current=api.request('GET','/v1/attempts/'+a['attempt_id'])['attempt']
                    if current.get('accepted_evidence')!=evidence:raise ValueError('acceptance_needs_reconciliation') from None
                    if current['phase']=='accepted':accepted=current
                    else:accepted=api.accept(a['attempt_id'],key,merge,evidence)  # Existing durable intent: readback only.
                self.release(accepted);return accepted
            except SourceChanged as error:return self._changed(command,error)
            except Pending:
                stop.wait(2)
        raise ValueError('delivery_interrupted')

    def _notify_merge(self,command,api,merge):
        import uuid
        d=self._load(merge['repository'],merge['pr_number'])
        with self.store.lock,self.store.db:
            event=d.get('merge_event')
            if event is None:
                event=dict(version=1,event_id=str(uuid.uuid4()),attempt_id=command['attempt_id'],connector_id=self.store.connector_id,
                           lifecycle=dict(kind='merged',command_id=command['command_id'],merge=merge))
                d['merge_event']=event
                self.store.db.execute('INSERT INTO outbox(event_id,data) VALUES (?,?)',(event['event_id'],encoded(event)))
                self.store.db.execute('UPDATE deliveries SET data=? WHERE attempt_id=?',(encoded(d),command['attempt_id']))
        api.send_event(event);self.store.ack(event['event_id'])

    def _changed(self,command,error):
        d=self._load(self.projects[command['project_id']],attempt=command['attempt_id'])
        if d['phase'] not in ('prepared','preparing') or d.get('merge_result'):raise ValueError('merge_fenced')
        d['phase']='superseded';self._save(d)
        with self.store.lock,self.store.db:self.store.db.execute('DELETE FROM repository_delivery WHERE repository=? AND attempt_id=?',(d['repository'],command['attempt_id']))
        self.store.lifecycle_transition(command['command_id'],'completed','delivery_changed',base_sha=error.base_sha)
        return None

    def verify_main(self,repository,pr,main_sha):
        d=self._load(repository,pr);self._lease(d)
        if d.get('merge_result',{}).get('main_sha')!=sha(main_sha):raise ValueError('main_identity_mismatch')
        if d.get('evidence'):return d['evidence']
        # The host must fresh-fetch before source reads, discovery or reviewer.
        evidence=self.host.verify_main(d['attempt'],d['merge_result'])
        from ..service.acceptance import accept
        a=dict(d['attempt'],phase='postmerge',validation_kind=evidence.get('kind'),**d['merge_result'])
        accept(a,evidence)
        d.update(evidence=evidence,phase='verified');self._save(d);return evidence


def artifact_json(raw,digest,member):
    import hashlib,io,zipfile
    from ..service.beads import strict_json
    if not isinstance(raw,bytes) or len(raw)>2097152 or digest!='sha256:'+hashlib.sha256(raw).hexdigest():raise ValueError('artifact_digest_mismatch')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries=z.infolist()
            if len(entries)!=1 or entries[0].filename!=member or entries[0].file_size>2097152 or entries[0].flag_bits&1:raise ValueError()
            with z.open(entries[0]) as f:data=f.read(2097153)
            if len(data)>2097152:raise ValueError()
            value=strict_json(data.decode('utf-8'))
            if not isinstance(value,dict):raise ValueError()
            return value
    except Exception:raise ValueError('invalid_artifact_zip') from None


def verify_manifest_bundle(manifests,source_sha,inventory):
    from ..ci_unittest import verify
    verify(manifests,source_sha,4)
    if manifests[0]['all_ids']!=inventory:raise ValueError('fresh_inventory_mismatch')
    for m in manifests:
        if (type(m.get('tests_run')) is not int or m['tests_run']!=len(m['selected_ids'])
                or m.get('failures')!=0 or m.get('errors')!=0):raise ValueError('manifest_execution_incomplete')


def bounded_http(method,url,headers,payload,limit):
    """Total deadline and byte budget, no credentials on artifact redirects."""
    import http.client,time
    from .client import _ResponseSocket
    from urllib.parse import urlsplit
    deadline=time.monotonic()+30
    body=None if payload is None else json.dumps(payload,ensure_ascii=True).encode('utf-8')
    for redirects in range(4):
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):raise ValueError('unsafe_http_target')
        c=http.client.HTTPSConnection(u.hostname,443,timeout=max(.001,deadline-time.monotonic()))
        try:
            c.connect()
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('github_deadline')
            c.sock.settimeout(remaining);c.sock=_ResponseSocket(c.sock,deadline)
            c.request(method,u.path+('?' +u.query if u.query else ''),body,headers)
            r=c.getresponse()
            if r.status in (301,302,303,307,308):
                if method!='GET':raise ValueError('mutation_redirect_forbidden')
                url=r.getheader('Location','');headers={k:v for k,v in headers.items() if k.lower()!='authorization'};continue
            if not 200<=r.status<300:raise ValueError('github_request_rejected')
            parts=[];size=0
            while True:
                left=deadline-time.monotonic()
                if left<=0:raise ValueError('github_deadline')
                if c.sock:c.sock.settimeout(left)
                data=r.read1(min(8192,limit+1-size))
                if not data:break
                size+=len(data)
                if size>limit:raise ValueError('github_response_limit')
                parts.append(data)
            return b''.join(parts)
        finally:c.close()
    raise ValueError('github_redirect_limit')


class GitHubHost:
    """Host-only fixed operations; GitHubTasks is used ONLY for its JSON transport.

    No Issue methods, metadata lifecycle, old workers or arbitrary task endpoints.
    Local paths come exclusively from the existing Worktrees mapping/journal.
    """
    def __init__(self,worktrees,store,projects,*,token=None,transport=None,reviewer=None):
        from ..github_source import resolve_token
        self.trees,self.store,self.projects=worktrees,store,dict(projects)
        self.token=token if token is not None else resolve_token()
        self.transport=transport or bounded_http;self.reviewer=reviewer;self.clients={};self.creator=None
        if not self.token:raise ValueError('existing_github_credentials_required')
    def _client(self,r):
        from types import SimpleNamespace
        from ..github_tasks import GitHubTasks
        if r not in self.projects.values():raise ValueError('repository_forbidden')
        if r not in self.clients:self.clients[r]=GitHubTasks(SimpleNamespace(repository=r),token=self.token,transport=self.transport)
        return self.clients[r]
    def _request(self,r,method,path,payload=None):return self._client(r).request(method,path,payload)
    def _pages(self,r,path,key=None):
        rows=[]
        for page in range(1,21):
            v=self._request(r,'GET',path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))
            items=v.get(key) if key else v
            if not isinstance(items,list) or len(items)>100 or any(not isinstance(x,dict) for x in items):raise ValueError('invalid_github_page')
            rows.extend(items)
            if len(items)<100:
                if key and v.get('total_count',len(rows))>len(rows):raise ValueError('truncated_github_page')
                return rows
        raise ValueError('github_page_limit')
    def _global(self,path,payload=None):
        from ..service.beads import strict_json
        if path not in ('/user','/graphql'):raise ValueError('fixed_host_operation_required')
        raw=self.transport('GET' if payload is None else 'POST','https://api.github.com'+path,
            {'Authorization':'Bearer '+self.token,'User-Agent':'Task-Tower','Content-Type':'application/json'},payload,2097152)
        return strict_json(raw.decode('utf-8'))
    def _creator(self):
        if self.creator is None:
            self.creator=self._global('/user').get('id')
            if type(self.creator) is not int or self.creator<1:raise ValueError('status_creator_unknown')
        return self.creator
    def _conversations(self,r,p):
        owner,name=r.split('/')
        query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved} pageInfo{hasNextPage}}}}}'
        value=self._global('/graphql',dict(query=query,variables=dict(owner=owner,name=name,number=p)))
        if value.get('errors'):raise ValueError('conversation_query_failed')
        threads=value['data']['repository']['pullRequest']['reviewThreads']
        return threads['pageInfo']['hasNextPage'] is False and all(t.get('isResolved') is True for t in threads['nodes'])
    def read_pr(self,r,p):
        if type(p) is not int or p<1:raise ValueError('invalid_pr')
        row=self._request(r,'GET','/pulls/'+str(p))
        return dict(repository=row['base']['repo']['full_name'],number=row['number'],head_sha=row['head']['sha'],base_sha=row['base']['sha'],
            base_ref=row['base']['ref'],branch=row['head']['ref'],head_repository=row['head']['repo']['full_name'],merged_at=row.get('merged_at'),
            state=row['state'],merged=row['merged'],merge_commit_sha=row.get('merge_commit_sha'),mergeable=row.get('mergeable'),
            mergeable_state=row.get('mergeable_state'),conversations_resolved=self._conversations(r,p))
    def _remote(self,path,r):
        remote=self.trees._git(path,'remote','get-url','--all','origin')
        push=self.trees._git(path,'remote','get-url','--push','--all','origin')
        allowed={'https://github.com/'+r,'https://github.com/'+r+'.git','git@github.com:'+r+'.git'}
        if remote not in allowed or push not in allowed:raise ValueError('remote_repository_mismatch')
    def prepare_pr(self,a):
        from pathlib import Path
        from urllib.parse import quote
        r=self.projects[a['project_id']];tree=self.trees.prepare(a['project_id'],a['attempt_id'],a['base_sha']);path=Path(tree['path'])
        self._remote(path,r)
        if tree['branch']!='codex/headless-'+a['attempt_id'] or self.trees.source(a['project_id'],a['attempt_id'],a['base_sha'])!=a['source']:raise ValueError('source_changed_before_push')
        self._push(path,tree['branch'])
        owner=r.split('/')[0];branch=tree['branch']
        existing=self._pages(r,'/pulls?state=open&head='+quote(owner+':'+branch,safe='')+'&base=main')
        if len(existing)>1:raise ValueError('duplicate_pr')
        if existing:p=existing[0]['number']
        else:
            row=self._request(r,'POST','/pulls',dict(title='Headless delivery '+a['bead_id'],head=branch,base='main',body='Beads task: '+a['bead_id']+'; attempt: '+a['attempt_id']+'\nIndependent review is recorded by the trusted connector.'))
            p=row['number']
        return self.read_pr(r,p)
    def _push(self,path,branch):
        # Only this fixed trusted host operation inherits GitHub authentication.
        import os,tempfile
        from pathlib import Path
        from ..processes import run_command
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GH_PROMPT_DISABLED='1')
        with tempfile.TemporaryDirectory(prefix='headless-push-') as temp:
            result=run_command(['git','-c','safe.directory='+path.as_posix(),'-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',
                'push','origin',branch+':refs/heads/'+branch],path,60,env=env,capture={'directory':Path(temp),'max_bytes_per_stream':1048576})
            if result.get('status')!='passed' or not result.get('cleanup_confirmed') or any(result.get(k) for k in ('stdout_truncated','stderr_truncated','stdout_tail_unknown','stderr_tail_unknown')):raise ValueError('push_needs_reconciliation')
    def protection(self,r):
        p=self._request(r,'GET','/branches/main/protection');checks=p.get('required_status_checks') or {}
        return dict(enforce_admins=p.get('enforce_admins',{}).get('enabled'),strict=checks.get('strict'),
            required_checks=list(checks.get('contexts',[]))+[c['context'] for c in checks.get('checks',[])],
            allow_force_pushes=p.get('allow_force_pushes',{}).get('enabled'),allow_deletions=p.get('allow_deletions',{}).get('enabled'),
            required_conversation_resolution=p.get('required_conversation_resolution',{}).get('enabled'))
    def read_checks(self,r,h):
        sha(h);rows=self._pages(r,'/commits/'+h+'/check-runs?filter=latest','check_runs')
        return [dict(name=c['name'],head_sha=c['head_sha'],app=c.get('app',{}).get('slug'),conclusion=c.get('conclusion') if c.get('status')=='completed' else None) for c in rows]
    def publish_acceptance(self,r,h,review):
        import hashlib
        digest=hashlib.sha256(encoded(review).encode('utf-8')).hexdigest()
        row=self._request(r,'POST','/statuses/'+sha(h),dict(state='success',context='task-tower/pr-acceptance',description='Independent review '+digest[:40]))
        return self._status(row,h,review)
    def _status(self,row,h,review):
        import hashlib
        expected='Independent review '+hashlib.sha256(encoded(review).encode('utf-8')).hexdigest()[:40]
        if row.get('creator',{}).get('id')!=self._creator() or row.get('description')!=expected:raise ValueError('foreign_acceptance_status')
        return dict(id=row['id'],head_sha=h,context=row['context'],state=row['state'],review=copy.deepcopy(review))
    def read_acceptance(self,r,h):
        # Bind readback to the already durably recorded independent review.
        rows=self._pages(r,'/commits/'+sha(h)+'/statuses')
        current=next((s for s in rows if s.get('context')=='task-tower/pr-acceptance'),None)
        if current is None:return None
        with self.store.lock:
            ds=[json.loads(x[0]) for x in self.store.db.execute('SELECT data FROM deliveries WHERE repository=?',(r,))]
        matches=[d for d in ds if d['attempt']['head_sha']==h]
        if len(matches)!=1:raise ValueError('status_review_unknown')
        return self._status(current,h,matches[0]['attempt']['review'])
    def merge(self,r,p,h):return self._request(r,'PUT','/pulls/'+str(p)+'/merge',dict(sha=sha(h),merge_method='merge'))
    def _artifact(self,r,a,name):
        import hashlib
        if a.get('name')!=name or a.get('expired') is not False or type(a.get('id')) is not int:raise ValueError('artifact_identity_mismatch')
        raw=self.transport('GET','https://api.github.com/repos/'+r+'/actions/artifacts/'+str(a['id'])+'/zip',
            dict(self._client(r).headers),None,2097152)
        member='merge-event.json' if name.startswith('task-tower-merge-') else 'validation.json' if name.startswith('task-tower-docs-') else 'shard-'+name.rsplit('-',1)[1]+'.json'
        return artifact_json(raw,a.get('digest'),member),hashlib.sha256(raw).hexdigest()
    def verify_main(self,a,merge):
        import time,tempfile
        from pathlib import Path
        r=merge['repository'];m=sha(merge['main_sha']);p=merge['pr_number'];repo=self.trees.projects[a['project_id']][0]
        started=time.monotonic()
        self.trees._git(repo,'fetch','origin','main',timeout=60)
        fetch_seconds=time.monotonic()-started
        if fetch_seconds>60:raise ValueError('fetch_deadline')
        started=time.monotonic()
        if self.trees._git(repo,'rev-parse','FETCH_HEAD',timeout=10)!=m:raise ValueError('main_moved')
        remaining=10-(time.monotonic()-started)
        if remaining<=0:raise ValueError('local_git_deadline')
        parents=self.trees._git(repo,'rev-list','--parents','-n','1',m,timeout=remaining).split()
        if parents!=[m,a['base_sha'],a['head_sha']]:raise ValueError('merge_parents_mismatch')
        local_seconds=time.monotonic()-started
        if local_seconds>10:raise ValueError('local_git_deadline')
        # Fetch failure above stops BEFORE any source polling or new reviewer.
        row=self.read_pr(r,p)
        if row.get('merged') is not True or row.get('merge_commit_sha')!=m or row.get('head_sha')!=a['head_sha']:raise ValueError('merge_fact_mismatch')
        runs=self._pages(r,'/actions/workflows/postmerge.yml/runs?event=pull_request','workflow_runs')
        run=select_main_run(runs,r,p,a['head_sha'],row['merged_at'])
        if run.get('status')!='completed':raise Pending('postmerge_ci_pending')
        if run.get('conclusion')!='success' or run.get('event')!='pull_request' or run.get('path')!='.github/workflows/postmerge.yml':raise ValueError('postmerge_ci_failed')
        run_id=run['id'];jobs=self._pages(r,'/actions/runs/'+str(run_id)+'/jobs?filter=latest','jobs')
        artifacts=self._pages(r,'/actions/runs/'+str(run_id)+'/artifacts','artifacts')
        def artifact(name):
            matches=[v for v in artifacts if v.get('name')==name]
            if len(matches)!=1:raise ValueError('artifact_missing_or_duplicate')
            provenance=matches[0].get('workflow_run',{})
            if provenance.get('id')!=run_id or provenance.get('head_sha')!=run['head_sha']:raise ValueError('artifact_provenance_mismatch')
            return self._artifact(r,matches[0],name)
        tree=self.trees.prepare_review(a['project_id'],a['attempt_id']+'-main',m);path=Path(tree['path'])
        # Run source-bound discovery/validators with the model/custom-check token scrub.
        docs=any(v.get('name')=='task-tower-docs-'+str(p)+'-windows' for v in artifacts)
        expected={'scope':'success','verify-merge (windows-latest, windows)':'success'}
        expected.update({'merge unittest shard (windows-latest, '+str(i)+')':'skipped' if docs else 'success' for i in range(4)})
        if len(jobs)!=len(expected) or any(j.get('status')!='completed' or expected.get(j.get('name'))!=j.get('conclusion') for j in jobs):raise ValueError('postmerge_jobs_incomplete')
        digests=[]
        if docs:
            report,digest=artifact('task-tower-docs-'+str(p)+'-windows');digests.append(digest)
            with tempfile.TemporaryDirectory(prefix='headless-docs-') as temp:
                out=Path(temp)/'validation.json'
                self._python(path,['-m','task_tower.ci_docs','--validate','--report',str(out),'--repository',r,'--pr',str(p),'--phase','postmerge'])
                actual=json.loads(out.read_text(encoding='utf-8'))
            if report!=actual or actual.get('head')!=m or actual.get('base')!=a['base_sha'] or actual.get('runtime_tests')!='not_run':raise ValueError('docs_validation_mismatch')
            kind='documentation.validation';runtime='not_run';validation=dict(scope='docs',fresh_validation=True,runtime_shards='skipped')
        else:
            event,digest=artifact('task-tower-merge-'+str(p)+'-windows');digests.append(digest)
            from ..merge_events import build_merge_event
            raw_pr=self._request(r,'GET','/pulls/'+str(p))
            expected_event=build_merge_event(dict(action='closed',repository=dict(full_name=r),pull_request=raw_pr),r,'windows','passed',run_id,run['run_attempt'])
            if event!=expected_event or event['merge_commit']!=m:raise ValueError('runtime_event_mismatch')
            with tempfile.TemporaryDirectory(prefix='headless-manifests-') as temp:
                manifests=[]
                for i in range(4):
                    manifest,digest=artifact('ci-unittest-'+str(run_id)+'-'+str(i));digests.append(digest);manifests.append(manifest)
                    (Path(temp)/('shard-'+str(i)+'.json')).write_text(encoded(manifest),encoding='utf-8')
                self._python(path,['-m','task_tower.ci_unittest','--verify',temp,'--count','4'])
                for manifest in manifests:
                    if (type(manifest.get('tests_run')) is not int or manifest['tests_run']!=len(manifest['selected_ids'])
                            or manifest.get('failures')!=0 or manifest.get('errors')!=0):raise ValueError('manifest_execution_incomplete')
            kind='runtime.validation';runtime='passed';validation=dict(exact_once=True,fresh_discovery=True,matrix_successful=True)
        if self.reviewer is None:raise ValueError('independent_postmerge_reviewer_required')
        review=self.reviewer(a,merge,path,dict(kind=kind,ci_run_id=run_id,artifact_digests=digests))
        return dict(version=1,kind=kind,repository=r,pr_number=p,head_sha=a['head_sha'],base_sha=a['base_sha'],main_sha=m,runtime_tests=runtime,
            ci_run_id=run_id,artifact_digests=digests,postmerge_review=review,validation=validation,
            fetch=dict(successful=True,main_sha=m,seconds=fetch_seconds,local_seconds=local_seconds))
    def _python(self,path,args):
        import os,sys,tempfile
        from pathlib import Path
        from ..processes import run_command
        env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN') and not k.upper().startswith(('GIT_','PYTHON'))}
        env['PYTHONUTF8']='1'
        with tempfile.TemporaryDirectory(prefix='headless-validation-') as temp:
            result=run_command([sys.executable,'-B',*args],path,120,env=env,capture={'directory':Path(temp),'max_bytes_per_stream':2097152})
            if result.get('status')!='passed' or not result.get('cleanup_confirmed') or any(result.get(k) for k in ('stdout_truncated','stderr_truncated','stdout_tail_unknown','stderr_tail_unknown')):raise ValueError('source_validation_failed')


class MainReviewer:
    """A fresh owned app-server and immutable detached main checkout per receipt.

    Local-only review journal entries never become service lifecycle events.
    Unknown start, explicit approval or interrupted review stops delivery.
    """
    def __init__(self,trees,store,app_factory,stop,*,timeout=900):
        self.trees,self.store,self.app_factory,self.stop=trees,store,app_factory,stop
        self.timeout=timeout
    def __call__(self,a,merge,path,proof):
        import hashlib,time
        from .briefs import build_brief,validate_source
        m=sha(merge['main_sha']);key=hashlib.sha256(encoded([a['attempt_id'],m,'postmerge']).encode('utf-8')).hexdigest()
        prior=next((d for d in self.store.commands() if d['command']['command_id']==key),None)
        if prior:
            if prior['phase']=='completed' and prior.get('review'):return prior['review']
            raise ValueError('postmerge_review_needs_reconciliation')
        source=validate_source(dict(head_sha=m,base_sha=a['base_sha'],diff=self.trees._git(path,'diff','--no-ext-diff','--no-textconv','--binary',a['base_sha'],m,'--',raw=True)))
        brief=build_brief(a['approved_task'],'reviewer',source)
        brief['input']['text']+='\nExact-main acceptance evidence (trusted data):\n'+encoded(proof)
        command=dict(version=1,kind='main_review',command_id=key,attempt_id=a['attempt_id']+'-postmerge',project_id=a['project_id'],base_sha=a['base_sha'],source=source,input=brief['input'])
        self.store.receive(command);app=None;result=None
        try:
            app=self.app_factory(path);thread=app.create_thread(path,command_id=key)
            if thread in [a['author_thread_id'],*a['review_threads']]:raise ValueError('postmerge_reviewer_not_independent')
            for d in self.store.commands():
                if d['command']['command_id']!=key and d.get('thread_id')==thread:raise ValueError('postmerge_reviewer_not_fresh')
            state=app.start_turn(thread,key,command['input'])
            if state['phase']!='executing':raise ValueError('postmerge_start_unknown_or_decision_required')
            end=time.monotonic()+self.timeout
            while not self.stop.is_set() and time.monotonic()<end:
                for msg in app.notifications():
                    if 'id' in msg or msg.get('method')=='connector/interrupted':raise ValueError('postmerge_review_interrupted_or_approval_required')
                    p=msg.get('params',{})
                    if msg.get('method')=='turn/completed' and p.get('threadId')==thread and p.get('turn',{}).get('id')==state['turn_id']:
                        turn=p['turn']
                        if turn.get('status')!='completed':raise ValueError('postmerge_review_failed')
                        text='\n'.join(i['text'] for i in turn.get('items',[]) if isinstance(i,dict) and i.get('type')=='agentMessage' and isinstance(i.get('text'),str))
                        if len(text.encode('utf-8'))>32768:raise ValueError('review_limit')
                        result=validate_review(text,source,thread)
                        if result['verdict']!='approve':raise ValueError('postmerge_findings')
                        break
                if result is not None:break
                self.stop.wait(.02)
            if result is None:raise ValueError('postmerge_review_interrupted')
            self.trees.prepare_review(a['project_id'],a['attempt_id']+'-main',m)
            if self.trees._git(path,'rev-parse','HEAD')!=m:raise ValueError('main_review_source_changed')
            app.close();app=None
            self.store.update(key,phase='completed',review=result)
            return result
        except Exception:
            self.store.update(key,phase='needs_reconciliation');raise
        finally:
            if app is not None:app.close()


def select_main_run(runs,repository,pr,head,merged_at):
    from datetime import datetime
    try:
        merged=datetime.fromisoformat(merged_at.replace('Z','+00:00'))
        if merged.utcoffset() is None:raise ValueError()
    except Exception:raise ValueError('merge_chronology_unknown') from None
    matches=[]
    for run in runs:
        if (run.get('head_sha')!=head or run.get('repository',{}).get('full_name')!=repository
                or run.get('path')!='.github/workflows/postmerge.yml' or run.get('event')!='pull_request'):continue
        refs=run.get('pull_requests')
        if not isinstance(refs,list) or (refs and not any(v.get('number')==pr for v in refs)):continue
        try:
            created=datetime.fromisoformat(run['created_at'].replace('Z','+00:00'))
            if created.utcoffset() is None or created<merged:continue
            if type(run['id']) is not int or run['id']<1 or type(run['run_attempt']) is not int or run['run_attempt']<1:continue
        except Exception:continue
        matches.append(run)
    if not matches:raise Pending('postmerge_ci_pending')
    return max(matches,key=lambda v:(v['id'],v['run_attempt']))
