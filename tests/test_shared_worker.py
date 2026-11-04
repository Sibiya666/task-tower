"""Native integration: real Superpowers helpers; fixture harness, not LLM pilot."""
import json,os,subprocess,sys,tempfile,threading,time,unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tests.test_shared_queue import Server
from task_tower.processes import run_command

SKILLS=Path.home()/'.codex/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills'
BASH=Path('C:/Program Files/Git/bin/bash.exe')

class WorkServer(Server):
    def __init__(self,sha,tree):
        self.base=sha;self.tree=tree;self.executions=[];super().__init__()
    def request(self,method,path,body):
        if method=='POST' and path=='/test/executions':
            self.executions.append(dict(body,at=time.monotonic()));return 200,dict(ok=True)
        if method=='GET' and path=='/test/start-count':return 200,dict(count=sum(e['phase']=='start' for e in self.executions))
        if method=='GET' and path.startswith('/issues?'):return 200,list(self.issues.values())
        if method=='GET' and path=='/git/ref/heads/main':return 200,dict(ref='refs/heads/main',object=dict(type='commit',sha=self.base))
        if method=='GET' and path=='/git/commits/'+self.base:return 200,dict(sha=self.base,tree=dict(sha=self.tree),message='actual source',parents=[])
        return super().request(method,path,body)

@unittest.skipUnless(os.name=='nt' and BASH.is_file() and (SKILLS/'executing-plans/scripts/task-start').is_file(),'Actual installed Superpowers/Git Bash Windows integration')
class NativeSharedWorkerTests(unittest.TestCase):
    def test_two_workers_execute_superpowers_tasks_and_refill_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();source=root/'source';source.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(source),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init','-b','main');git('remote','add','origin','https://github.com/owner/repo.git')
            (source/'.gitignore').write_text('.superpowers/\n')
            (source/'docs').mkdir()
            for n in (1,2,3):(source/'docs'/('plan-'+str(n)+'.md')).write_text('# Prepared plan\n\n### Task 1: Execute Issue '+str(n)+'\n\nWrite artifacts/issue-'+str(n)+'.txt and verify its actual content.\n')
            git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','prepared tasks')
            server=WorkServer(git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}'))
            self.addCleanup(server.close)
            def actor(index):
                settings=dict(worker_id=str(uuid.uuid4()),worker_name='worker-'+str(index),source_checkout=str(source),workspace_root=str(root/('worker-'+str(index))),
                    superpowers_root=str(SKILLS),plans={str(n):'docs/plan-'+str(n)+'.md' for n in (1,2,3)},
                    allowlist=[dict(repository='owner/repo',issue=n,task_id='TT-SHARED-'+str(n)) for n in (1,2,3)],
                    harness=dict(kind='custom',trusted=True,argv=[sys.executable,str(Path(__file__).with_name('shared_work_agent.py')),'--server',server.url,'--bash',str(BASH)],timeout_seconds=30,log_max_bytes=65536))
                config=root/('worker-'+str(index)+'.json');config.write_text(json.dumps(settings))
                capture=root/('capture-'+str(index));capture.mkdir()
                process=run_command([sys.executable,'-B','-m','tests.shared_work_actor',server.url,str(config)],Path(__file__).resolve().parents[1],120,
                    capture=dict(directory=capture,max_bytes_per_stream=1048576))
                self.assertEqual(process['status'],'passed',(capture/'stderr.log').read_text())
                self.assertTrue(process['cleanup_confirmed']);return json.loads((capture/'stdout.log').read_bytes())
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(actor,(0,1)))
            starts=[e for e in server.executions if e['phase']=='start'];ends=[e for e in server.executions if e['phase']=='end']
            self.assertEqual(sorted(e['issue'] for e in starts),[1,2,3]);self.assertEqual(len(ends),3)
            self.assertEqual(len({r['pid'] for r in results}),2)
            self.assertTrue(all(r['results'] for r in results))
            self.assertEqual(sum(len(r['results']) for r in results),3)
            diagnostics={str(p.relative_to(root)):p.read_text(encoding='utf-8',errors='replace')[-4096:] for p in root.glob('worker-*/*/capture/stderr.log')}
            self.assertTrue(all(row['state']=='awaiting_acceptance' for r in results for row in r['results']),dict(results=results,diagnostics=diagnostics))
            self.assertTrue(any(a['worker']!=b['worker']
                and a['at']<next(e['at'] for e in ends if e['issue']==b['issue'])
                and b['at']<next(e['at'] for e in ends if e['issue']==a['issue'])
                for a in starts for b in starts),dict(events=server.executions,results=results))
            self.assertTrue(all(issue['assignees']==[dict(login='operator')] for issue in server.issues.values()))
