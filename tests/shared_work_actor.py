import json,sys,urllib.request
from types import SimpleNamespace
from task_tower.github_tasks import GitHubTasks
from task_tower.shared_queue import SharedQueue
from task_tower.shared_worker import SharedWorker
base,config=sys.argv[1:];settings=json.loads(open(config).read())
def transport(method,url,headers,payload,limit):
    path=url.removeprefix('https://api.github.com/repos/owner/repo')
    data=None if payload is None else json.dumps(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'}),timeout=10) as response:return response.read(limit+1)
store=GitHubTasks(SimpleNamespace(repository='owner/repo'),transport=transport)
queue=SharedQueue(store,settings['worker_id'],allowlist=settings['allowlist'],assignee='operator')
worker=SharedWorker(queue,settings)
results=[]
for _ in range(10):
    result=worker.run_once()
    if result is None:break
    results.append(result)
print(json.dumps(dict(pid=__import__('os').getpid(),results=results)))
