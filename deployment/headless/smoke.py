"""Explicit disposable Linux smoke; never discovers/mounts canonical host state.

Run after build. Writes sanitized evidence, stops only its own container and
retains its named volumes. No Codex, model authorization or GitHub credentials.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid


def run(image, receipt, docker='docker'):
    name='task-tower-headless-smoke-'+uuid.uuid4().hex[:12]
    beads=name+'-beads';runtime=name+'-runtime'
    token=secrets.token_hex(24)
    plan={'tasks':[dict(id='pilot-smoke',title='Disposable service smoke',
                       description='Verify native claim and persisted service identity',depends_on=[])]}
    digest=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
    env={k:v for k,v in os.environ.items() if k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
    def call(*args,input=None,timeout=60):
        r=subprocess.run([docker,*args],input=input,capture_output=True,encoding='utf-8',
                         errors='strict',timeout=timeout,env=env)
        if r.returncode:raise RuntimeError('docker_operation_failed: '+args[0])
        return r.stdout.strip()
    evidence=dict(version=1,kind='headless.container.smoke',container=name,volumes=[beads,runtime],passed=False)
    created=False
    try:
        evidence['image_id']=call('image','inspect',image,'--format','{{.Id}}')
        call('volume','create',beads);call('volume','create',runtime)
        # No host bind mounts; ephemeral input provisions a secret with mode0600.
        script="""import json,os,subprocess
from pathlib import Path
os.umask(0o077)
p=Path('/data/beads/pilot');p.mkdir()
env={k:v for k,v in os.environ.items() if not k.upper().startswith(('BD_','BEADS_','DOLT_','GIT_'))}
env.update(BD_EVENTS_JOURNAL='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0')
subprocess.run(['/usr/local/bin/bd','--sandbox','--actor','headless-smoke','init','--prefix','pilot','--non-interactive','--skip-agents','--skip-hooks'],cwd=p,env=env,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
Path('/data/runtime/token').write_text(TOKEN,encoding='ascii')
config=dict(version=1,executable='/usr/local/bin/bd',projects={'pilot':str(p)},journal='/data/runtime/service.sqlite3',connectors={'smoke':dict(token_file='/data/runtime/token',projects=['pilot'])},approved_plans={'pilot':[DIGEST]},port=8765,poll_seconds=2)
Path('/data/runtime/service.json').write_text(json.dumps(config),encoding='utf-8')
print('initialized')
""".replace('TOKEN',repr(token)).replace('DIGEST',repr(digest))
        call('run','--rm','-i','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges',
             '-v',beads+':/data/beads','-v',runtime+':/data/runtime','--entrypoint','python3',image,'-',input=script)
        call('create','--name',name,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
             '--pids-limit','128','--tmpfs','/tmp:mode=1777,size=128m','-p','127.0.0.1::8765',
             '-v',beads+':/data/beads','-v',runtime+':/data/runtime',image)
        created=True;call('start',name)
        def port():
            text=call('port',name,'8765/tcp')
            if not text.startswith('127.0.0.1:'):raise RuntimeError('non_loopback_publication')
            return int(text.rsplit(':',1)[1])
        endpoint_port=port()
        def request(method,path,body=None):
            c=http.client.HTTPConnection('127.0.0.1',endpoint_port,timeout=10)
            try:
                c.request(method,path,None if body is None else json.dumps(body),
                          {'X-Connector-ID':'smoke','Authorization':'Bearer '+token,'Content-Type':'application/json'})
                r=c.getresponse();value=json.loads(r.read(65537))
                if r.status!=200:raise RuntimeError('api_status_'+str(r.status)+':'+str(value.get('error',{}).get('code')))
                return value
            finally:c.close()
        end=time.monotonic()+30
        while True:
            try:request('GET','/v1/ready?project_id=pilot');break
            except (OSError,http.client.HTTPException):
                if time.monotonic()>=end:raise
                time.sleep(.1)
        batch=request('POST','/v1/plans/import',dict(version=1,request_id='smoke-import',project_id='pilot',digest=digest,plan=plan))['batch']
        if batch['state']!='published':raise RuntimeError('native_import_not_published')
        if [r['id'] for r in request('GET','/v1/ready?project_id=pilot')['ready']]!=['pilot-smoke']:raise RuntimeError('native_ready_mismatch')
        claim=dict(version=1,request_id='smoke-claim',project_id='pilot',bead_id='pilot-smoke',connector_id='smoke')
        a=request('POST','/v1/claims',claim)['attempt']
        if a['phase']!='claimed':raise RuntimeError('claim_not_confirmed')
        if request('POST','/v1/claims',claim)['attempt']!=a:raise RuntimeError('claim_not_idempotent')
        if request('GET','/v1/ready?project_id=pilot')['ready']:raise RuntimeError('claimed_still_ready')
        inspect=json.loads(call('inspect',name))[0]
        if (any(m['Type']!='volume' for m in inspect['Mounts']) or len(inspect['Mounts'])!=2
                or inspect['HostConfig']['CapDrop']!=['ALL'] or not inspect['HostConfig']['ReadonlyRootfs']):raise RuntimeError('container_boundary_mismatch')
        if any(v.split('=',1)[0].upper() in ('GH_TOKEN','GITHUB_TOKEN') for v in inspect['Config']['Env']):raise RuntimeError('unexpected_auth')
        call('stop','--time','20',name);call('start',name);endpoint_port=port()
        end=time.monotonic()+30
        while True:
            try:after=request('GET','/v1/attempts/'+a['attempt_id'])['attempt'];break
            except (OSError,http.client.HTTPException):
                if time.monotonic()>=end:raise
                time.sleep(.1)
        if after!=a:raise RuntimeError('volume_attempt_identity_changed')
        if request('POST','/v1/claims',claim)['attempt']!=a:raise RuntimeError('restart_claim_changed')
        native_script="""import json,os,subprocess
from pathlib import Path
from task_tower.service.beads import environment
p=Path('/data/beads/pilot')
def bd(*args):
 r=subprocess.run(['/usr/local/bin/bd','--sandbox','--actor','headless-smoke','--readonly',*args,'--json'],cwd=p,env=environment(p),capture_output=True,encoding='utf-8',check=True,timeout=30)
 return json.loads(r.stdout)
print(json.dumps({'show':bd('show','pilot-smoke'),'history':bd('history','pilot-smoke','--events','--limit','0')}))
"""
        # Service idle; read-only native readback is scoped to this disposable DB.
        fact=json.loads(call('exec','-i',name,'python3','-',input=native_script))
        row=fact['show'][0]
        if (row['status'],row['assignee'])!=('in_progress',a['actor']):raise RuntimeError('native_owner_mismatch')
        events=fact['history']
        if len([e for e in events if e['event_type']=='claimed' and e['actor']==a['actor']])!=1:raise RuntimeError('native_claim_history_mismatch')
        evidence.update(passed=True,bead_id='pilot-smoke',attempt_id=a['attempt_id'],actor=a['actor'],
                        plan_digest=digest,native_events=events,persistent_restart=True,host_bind='127.0.0.1')
    finally:
        if created:
            call('stop','--time','20',name)
            stopped=json.loads(call('inspect',name))[0]
            evidence['stopped']=stopped['State']['Running'] is False
        receipt=Path(receipt);receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(evidence,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    if not evidence.get('stopped'):raise RuntimeError('cleanup_unknown')
    print(json.dumps({k:evidence[k] for k in ('kind','passed','stopped','image_id','container','attempt_id')},ensure_ascii=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True);parser.add_argument('--receipt',required=True)
    parser.add_argument('--docker',default='docker')
    args=parser.parse_args();run(args.image,args.receipt,args.docker)
