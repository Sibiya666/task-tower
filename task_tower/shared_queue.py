"""Shared GitHub ownership, not assignee-based locking or task acceptance."""
import hashlib,json,os,re,uuid
from .github_tasks import GitHubTasks,GitHubRequestError,parse_metadata

_PREFIX='Task-Tower shared claim v1\n'
_CLIENTS={};_CLAIMS={};_PERMITS={};_ATTEMPTED=set();_CONSUMED=set()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{40}',value):raise ValueError('Invalid shared Git object')
    return value

def _ref(value,ref):
    if not isinstance(value,dict) or value.get('ref')!=ref or value.get('object',{}).get('type')!='commit':raise ValueError('Unknown shared reference')
    return sha(value['object']['sha'])

class Claim:
    def __init__(self):raise TypeError('Claims come from atomic acquisition')
class ExecutionPermit:
    def __init__(self):raise TypeError('Execution requires a confirmed intent')

class SharedQueue:
    def __init__(self,store,worker_id,*,allowlist,assignee=None):
        if type(store) is not GitHubTasks:raise ValueError('Actual configured GitHub store required')
        uuid.UUID(worker_id)
        if assignee is not None and (not isinstance(assignee,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]{0,38}',assignee)):
            raise ValueError('Invalid configured GitHub assignee')
        repo=store.repository.casefold();allowed={}
        for row in allowlist:
            if (set(row)!={'repository','issue','task_id'} or row['repository'].casefold()!=repo
                    or type(row['issue']) is not int or row['issue']<1
                    or not isinstance(row['task_id'],str) or not re.fullmatch('TT-[A-Z0-9]+(?:-[A-Z0-9]+)*',row['task_id'])
                    or row['issue'] in allowed):raise ValueError('Invalid private shared scope')
            allowed[row['issue']]=row['task_id']
        _CLIENTS[id(self)]=(self,os.getpid(),store,worker_id,str(uuid.uuid4()),repo,allowed,assignee)
    def _client(self):
        value=_CLIENTS.get(id(self))
        if value is None or value[0] is not self or value[1]!=os.getpid():raise ValueError('Original worker process required')
        return value
    def _issue(self,number,*,initial=False,require_assigned=False):
        _,_,store,_,_,repo,allowed=self._client()[:7]
        if type(number) is not int or number not in allowed:raise ValueError('Issue outside private worker scope')
        issue=store.get(number);meta=parse_metadata(issue.get('body'))
        if (type(issue.get('id')) is not int or issue['id']<1 or issue.get('number')!=number or issue.get('state')!='open'
                or 'pull_request' in issue or not isinstance(meta,dict) or meta.get('kind')!='task'
                or meta.get('task_id')!=allowed[number] or meta.get('mode')!='autonomous' or meta.get('status')!='open'):
            raise ValueError('Shared task is not ready')
        if meta.get('blocked_by') or meta.get('blocked_by_task_ids'):raise ValueError('Verified dependency selection required')
        identity=dict(repository=repo,issue=number,issue_id=issue['id'],task_id=allowed[number])
        criteria=digest({k:issue.get(k) for k in ('id','number','title','body','state')})
        people=issue.get('assignees',[])
        if not isinstance(people,list) or any(not isinstance(p,dict) or not isinstance(p.get('login'),str) for p in people):
            raise ValueError('Unknown Issue assignees')
        if initial and people:return identity,None
        if require_assigned and (self._client()[7] is None or not people):raise ValueError('Confirmed executor assignment required')
        if people and {p['login'].casefold() for p in people}!={str(self._client()[7]).casefold()}:
            raise ValueError('Issue assigned to another executor')
        return identity,criteria
    def _commit(self,body,tree,parent):
        store=self._client()[2]
        value=store.request('POST','/git/commits',dict(message=_PREFIX+canonical(body),tree=tree,parents=[parent]))
        result=sha(value.get('sha'))
        if (value.get('message')!=_PREFIX+canonical(body) or value.get('tree',{}).get('sha')!=tree
                or [p.get('sha') for p in value.get('parents',[])]!=[parent]):raise ValueError('Shared commit not confirmed')
        return result
    def _current(self,ref,expected,body):
        store=self._client()[2]
        actual=_ref(store.request('GET','/git/ref/'+ref.removeprefix('refs/')),ref)
        if actual!=expected:return False
        commit=store.request('GET','/git/commits/'+actual)
        return commit.get('sha')==actual and commit.get('message')==_PREFIX+canonical(body)
    def claim(self,number):
        client=self._client();store=client[2]
        identity,criteria=self._issue(number,initial=True)
        if criteria is None:return None
        main=_ref(store.request('GET','/git/ref/heads/main'),'refs/heads/main')
        tree=sha(store.request('GET','/git/commits/'+main)['tree']['sha'])
        body=dict(version=1,kind='shared-task-claim',**identity,criteria_sha256=criteria,
            worker_id=client[3],worker_session=client[4],claim_id=str(uuid.uuid4()),state='claimed',base_sha=main,assignee=client[7])
        ref='refs/heads/task-tower/claims/issue-'+str(identity['issue_id'])
        proposed=self._commit(body,tree,main)
        try:
            response=store.request('POST','/git/refs',dict(ref=ref,sha=proposed))
            if _ref(response,ref)!=proposed:raise ValueError('Claim response disagrees')
        except GitHubRequestError:
            # A claim itself launches nothing. Only this live proposal can be
            # reconciled; another process never reconstructs its ownership.
            try:
                if not self._current(ref,proposed,body):return None
            except (GitHubRequestError,ValueError):return None
        if not self._current(ref,proposed,body):return None
        token=object.__new__(Claim)
        _CLAIMS[id(token)]=(token,self,os.getpid(),ref,proposed,tree,canonical(body))
        return token
    def assign(self,claim):
        value=_CLAIMS.get(id(claim))
        if value is None or value[0] is not claim or value[1] is not self or value[2]!=os.getpid():raise ValueError('Actual claim required')
        body=json.loads(value[6]);login=self._client()[7]
        if not self._current(value[3],value[4],body):return False
        if login is None:return False
        try:
            self._issue(body['issue'])
            result=self._client()[2].request('POST','/issues/'+str(body['issue'])+'/assignees',dict(assignees=[login]))
            return (result.get('id')==body['issue_id'] and result.get('number')==body['issue']
                and {p['login'].casefold() for p in result.get('assignees',[])}=={login.casefold()})
        except (GitHubRequestError,ValueError,KeyError,TypeError):return False
    def start(self,claim):
        value=_CLAIMS.get(id(claim))
        if type(claim) is not Claim or value is None or value[0] is not claim or value[1] is not self or value[2]!=os.getpid():
            raise ValueError('Actual original shared claim required')
        if id(claim) in _ATTEMPTED:return None
        _ATTEMPTED.add(id(claim));_,_,_,ref,previous,tree,raw=value;body=json.loads(raw)
        try:
            identity,criteria=self._issue(body['issue'],require_assigned=True)
            if any(identity[k]!=body[k] for k in identity) or criteria!=body['criteria_sha256'] or not self._current(ref,previous,body):return None
            started=dict(body,state='execution_intent');proposed=self._commit(started,tree,previous)
            result=self._client()[2].request('PATCH','/git/refs/'+ref.removeprefix('refs/'),dict(sha=proposed,force=False))
            if _ref(result,ref)!=proposed or not self._current(ref,proposed,started):return None
        except (GitHubRequestError,ValueError):return None
        permit=object.__new__(ExecutionPermit)
        _PERMITS[id(permit)]=(permit,self,os.getpid(),ref,proposed,tree,canonical(started))
        return permit
    def consume(self,permit):
        value=_PERMITS.get(id(permit))
        if (type(permit) is not ExecutionPermit or value is None or value[0] is not permit
                or value[1] is not self or value[2]!=os.getpid() or id(permit) in _CONSUMED):
            raise ValueError('Original unconsumed execution permit required')
        _CONSUMED.add(id(permit));body=json.loads(value[6])
        identity,criteria=self._issue(body['issue'],require_assigned=True)
        if criteria!=body['criteria_sha256'] or not self._current(value[3],value[4],body):raise ValueError('Execution intent/source changed')
        return body
    def finish(self,permit,state,result_sha256):
        if state not in ('awaiting_acceptance','needs_input') or not re.fullmatch('[a-f0-9]{64}',result_sha256):raise ValueError('Invalid execution outcome')
        value=_PERMITS.get(id(permit))
        if value is None or value[0] is not permit or value[1] is not self or value[2]!=os.getpid() or id(permit) not in _CONSUMED:
            raise ValueError('Actual consumed execution permit required')
        old=json.loads(value[6])
        if not self._current(value[3],value[4],old):raise ValueError('Shared execution already advanced')
        body=dict(old,state=state,result_sha256=result_sha256)
        proposed=self._commit(body,value[5],value[4])
        response=self._client()[2].request('PATCH','/git/refs/'+value[3].removeprefix('refs/'),dict(sha=proposed,force=False))
        if _ref(response,value[3])!=proposed or not self._current(value[3],proposed,body):raise ValueError('Execution outcome unconfirmed')
        return body
