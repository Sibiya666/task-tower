"""Deterministic harness fixture using actual installed Superpowers scripts."""
import argparse,json,subprocess,sys,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');p.add_argument('--server');p.add_argument('--bash');a=p.parse_args()
r=json.loads(Path(a.request).read_bytes());root=Path(r['checkout']);number=r['task']['issue']
def event(phase):
    data=json.dumps(dict(phase=phase,issue=number,pid=__import__('os').getpid(),worker=r['worker_name'])).encode()
    with urllib.request.urlopen(urllib.request.Request(a.server+'/test/executions',data=data,headers={'Content-Type':'application/json'}),timeout=5) as response:response.read()
def run(argv):return subprocess.check_output(argv,cwd=root,stderr=subprocess.STDOUT).decode()
event('start')
deadline=time.monotonic()+10
while True:
    with urllib.request.urlopen(a.server+'/test/start-count',timeout=5) as response:count=json.loads(response.read())['count']
    if count>=2:break
    if time.monotonic()>=deadline:raise RuntimeError('Second independent harness did not overlap')
    time.sleep(.02)
bash=a.bash;skills=Path(r['superpowers']['root']);plan=r['plan_path']
output=run([bash,str(skills/'executing-plans/scripts/task-start'),plan,'1'])
base=[line.split(': ',1)[1] for line in output.splitlines() if line.startswith('base: ')][0]
(root/'artifacts').mkdir(exist_ok=True);(root/'artifacts'/('issue-'+str(number)+'.txt')).write_text('Executed task '+str(number))
run(['git','add','artifacts'])
run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Execute prepared task '+str(number)])
check="from pathlib import Path; assert Path('artifacts/issue-%s.txt').read_text()=='Executed task %s'"%(number,number)
print(run([bash,str(skills/'executing-plans/scripts/task-done'),plan,'1',base,'--',sys.executable,'-c',check]))
Path(a.result).write_text(json.dumps(dict(version=1,status='execution_completed',summary='Actual prepared Superpowers task and test completed.')))
event('end')
