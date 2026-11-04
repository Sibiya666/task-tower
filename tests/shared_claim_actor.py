import json,sys,urllib.request
from types import SimpleNamespace
from task_tower.github_tasks import GitHubTasks
from task_tower.shared_queue import SharedQueue
base,worker,number=sys.argv[1:];number=int(number)
def transport(method,url,headers,payload,limit):
    path=url.removeprefix('https://api.github.com/repos/owner/repo')
    data=None if payload is None else json.dumps(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'}),timeout=10) as response:
        return response.read(limit+1)
store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
queue=SharedQueue(store,worker,allowlist=[dict(repository='owner/repo',issue=number,task_id='TT-SHARED-'+str(number))],assignee='operator')
claim=queue.claim(number)
assigned=False if claim is None else queue.assign(claim)
permit=None if not assigned else queue.start(claim)
if permit is not None:queue.consume(permit)
print(json.dumps(dict(pid=__import__('os').getpid(),claimed=claim is not None,assigned=assigned,permit=permit is not None)))
