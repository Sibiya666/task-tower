"""Independent shared-queue executor; harness success is not task acceptance."""
import configparser,hashlib,json,os,re,shutil,time
from pathlib import Path
from .shared_queue import SharedQueue,canonical,digest,_CLAIMS
from .project_connections import safe_config_path
from .executor_profiles import child_environment
from .processes import run_command


def write(path,value):
    path=safe_config_path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(canonical(value).encode());stream.flush();os.fsync(stream.fileno())


class WorkerCleanupUnknown(ValueError):
    pass


def native_execution_supported():
    return os.name=='nt'


def git(root,args,logs,*,fence=None):
    import uuid
    capture=logs/str(uuid.uuid4());capture.mkdir(parents=True)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GIT_NO_REPLACE_OBJECTS='1')
    with (capture/'process.json').open('xb') as facts:
        facts.flush();os.fsync(facts.fileno())
        if fence is not None:write(fence,dict(version=1,kind='git',state='launch_reserved'))
        result=run_command(['git','--no-optional-locks','-c','core.longpaths=true','-c','core.hooksPath='+str(logs/'no-hooks'),
            '-c','core.fsmonitor=false','-c','diff.external=',*args],root,60,env=env,capture=dict(directory=capture,max_bytes_per_stream=1048576))
        facts.write(canonical(result).encode());facts.flush();os.fsync(facts.fileno())
    if result.get('cleanup_confirmed') is not True:raise WorkerCleanupUnknown('Worker Git cleanup unresolved')
    if fence is not None:fence.unlink()
    if (result.get('status')!='passed' or result.get('cleanup_confirmed') is not True
            or result.get('stdout_tail_unknown') is not False or result.get('stdout_truncated') is not False):raise ValueError('Worker Git operation failed')
    return (capture/'stdout.log').read_bytes()


def git_controls(checkout,mirror):
    """Read controls directly: never invoke Git against unverified agent output."""
    checkout=Path(checkout);mirror=Path(mirror)
    pointer=safe_config_path(checkout/'.git').read_text(encoding='utf-8').strip()
    if not pointer.startswith('gitdir: '):raise ValueError('Worker Git pointer changed')
    workgit=Path(pointer[8:])
    if not workgit.is_absolute():workgit=checkout/workgit
    safe_config_path(workgit/'.control-path-check')
    workgit=workgit.resolve()
    if workgit.parent!=mirror.resolve()/'worktrees':raise ValueError('Foreign worker Git directory')
    paths=[checkout/'.git',mirror/'config',mirror/'config.worktree',mirror/'objects/info/alternates',
           mirror/'info/grafts',mirror/'shallow',workgit/'commondir',workgit/'gitdir',workgit/'config.worktree']
    result={}
    for candidate in paths:
        path=safe_config_path(candidate)
        if not path.exists():result[str(candidate)]=None;continue
        info=path.stat()
        if info.st_nlink!=1 or info.st_size>1048576:raise ValueError('Invalid worker Git control')
        result[str(candidate)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_git_controls(checkout,mirror,expected):
    if git_controls(checkout,mirror)!=expected:raise ValueError('Worker Git controls changed')


def validate_source_config(source):
    """Inspect local config in memory; rejected private values never enter logs."""
    def read(path):
        path=safe_config_path(path);info=path.stat()
        if info.st_nlink!=1 or info.st_size>1048576:raise ValueError('Invalid source Git control')
        return path.read_text(encoding='utf-8')
    gitdir=source/'.git'
    if gitdir.is_file():
        pointer=read(gitdir).strip()
        if not pointer.startswith('gitdir: '):raise ValueError('Invalid source Git pointer')
        gitdir=Path(pointer[8:]);gitdir=gitdir if gitdir.is_absolute() else source/gitdir
    safe_config_path(gitdir/'.control-path-check')
    if (gitdir/'commondir').exists():
        common=Path(read(gitdir/'commondir').strip());gitdir=common if common.is_absolute() else gitdir/common
    parser=configparser.RawConfigParser(allow_no_value=True,delimiters=('=',),strict=True)
    try:parser.read_string(read(gitdir/'config'))
    except (configparser.Error,UnicodeError):raise ValueError('Invalid source Git configuration') from None
    if parser.defaults():raise ValueError('Untrusted source Git defaults')
    from urllib.parse import urlsplit
    for section in parser.sections():
        if section=='core':allowed={'repositoryformatversion','filemode','bare','logallrefupdates','symlinks','ignorecase','precomposeunicode','protectntfs','protecthfs','autocrlf'}
        elif section=='user':allowed={'name','email'}
        elif re.fullmatch(r'remote "[A-Za-z0-9_.-]+"',section):allowed={'url','fetch','pushurl'}
        elif re.fullmatch(r'branch "[A-Za-z0-9_./-]+"',section):allowed={'remote','merge'}
        else:raise ValueError('Untrusted source Git configuration')
        for key,value in parser.items(section):
            if key not in allowed or not isinstance(value,str):raise ValueError('Untrusted source Git configuration')
            if key in ('url','pushurl'):
                url=value.strip().strip('"');parts=urlsplit(url)
                if (parts.password is not None or parts.query or parts.fragment
                        or parts.username is not None and not (parts.scheme=='ssh' and parts.username=='git')
                        or '@' in url and '://' not in url and not re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+',url)):
                    raise ValueError('Credential-bearing source URL')


def harness_environment():
    environment=child_environment({k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')})
    environment.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
    return environment

class SharedWorker:
    def __init__(self,queue,settings):
        if not native_execution_supported():raise ValueError('Unsupported native worker platform')
        if type(queue) is not SharedQueue:raise ValueError('Actual shared queue required')
        self.queue=queue;self.settings=json.loads(canonical(settings));self.name=settings['worker_name']
        self.source=safe_config_path(Path(settings['source_checkout'])/'.worker-path-check').parent.resolve()
        self.root=safe_config_path(Path(settings['workspace_root'])/'.worker-path-check').parent.resolve()
        self.skills=safe_config_path(Path(settings['superpowers_root'])/'.worker-path-check').parent.resolve();self.harness=settings['harness'];self.plans=settings['plans']
        if self.root==self.source or self.root.is_relative_to(self.source) or self.source.is_relative_to(self.root):raise ValueError('Worker output overlaps source checkout')
        if not (self.skills/'executing-plans/SKILL.md').is_file():raise ValueError('Installed Superpowers required')
        self.pipeline=self.harness.get('kind')=='pipeline'
        if self.pipeline:
            from .pipeline_shared import validate_installation
            self.pipeline_binding=validate_installation(self.harness,self.queue._client()[5],self.plans,settings['allowlist'])
        if self.harness.get('kind') not in ('custom','codex','pipeline') or self.harness.get('kind')=='custom' and self.harness.get('trusted') is not True:
            raise ValueError('Explicit trusted harness required')
        argv=self.harness.get('argv')
        if not self.pipeline and (not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a for a in argv)):raise ValueError('Invalid private harness argv')
        if not self.pipeline and (not shutil.which(argv[0]) or Path(shutil.which(argv[0])).suffix.lower() in ('.cmd','.bat')):raise ValueError('Native harness executable required')
        for key,low,high in [('timeout_seconds',1,7200),('log_max_bytes',1024,67108864)]:
            value=self.harness.get(key)
            if not self.pipeline and (type(value) is not int or not low<=value<=high):raise ValueError('Invalid harness budget')
        for path in self.plans.values():
            if not isinstance(path,str) or Path(path).is_absolute() or '..' in Path(path).parts or path.lower().startswith('.git'):raise ValueError('Invalid private plan path')
        self.root.mkdir(parents=True,exist_ok=True);self.bootstrap=self.root/'bootstrap';self.bootstrap.mkdir(exist_ok=True)
        self.fence=self.root/'execution-fence.json';self._check_fence()
        validate_source_config(self.source)
        self.pins=self._pins()
    def _check_fence(self):
        if safe_config_path(self.fence).exists():raise ValueError('Worker execution cleanup unresolved')
    def _git(self,root,args,logs):
        self._check_fence()
        return git(root,args,logs,fence=self.fence)
    def _pins(self):
        result={}
        files=list(self.skills.rglob('SKILL.md'))
        files += [self.skills/p for p in ('executing-plans/scripts/task-start','executing-plans/scripts/task-done','subagent-driven-development/scripts/task-brief','subagent-driven-development/scripts/sdd-workspace') if (self.skills/p).is_file()]
        for path in sorted(files):
            safe_config_path(path)
            if path.stat().st_nlink!=1:raise ValueError('Aliased Superpowers instruction')
            result[path.relative_to(self.skills).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        return result
    def _workspace(self,claim):
        record=_CLAIMS.get(id(claim))
        if record is None or record[0] is not claim or record[1] is not self.queue or record[2]!=os.getpid():raise ValueError('Actual claim required')
        body=json.loads(record[6]);directory=self.root/body['claim_id'][:24];directory.mkdir(exist_ok=False)
        logs=directory/'git-logs';logs.mkdir();mirror=directory/'repo.git';checkout=directory/'work'
        validate_source_config(self.source)
        self._git(directory,['-c','protocol.file.allow=always','clone','--bare','--no-local','--no-hardlinks','--template=',str(self.source),str(mirror)],logs)
        branch='task-tower/work-'+body['claim_id']
        self._git(mirror,['worktree','add','-b',branch,str(checkout),body['base_sha']],logs)
        common=Path(self._git(checkout,['rev-parse','--path-format=absolute','--git-common-dir'],logs).decode().strip()).resolve()
        if common!=mirror.resolve() or not (checkout/'.git').is_file():raise ValueError('Private worker worktree mismatch')
        plan=safe_config_path(checkout/self.plans[str(body['issue'])])
        if not plan.is_file():raise ValueError('Prepared repository plan missing')
        return body,directory,checkout,mirror,branch,logs
    def run_once(self):
        self._check_fence()
        client=self.queue._client();store=client[2];allowed=client[6]
        issues=sorted(store.list_issues(),key=lambda row:row['number'])
        for issue in issues:
            number=issue['number']
            if number not in allowed or str(number) not in self.plans or issue.get('state')!='open' or issue.get('assignees'):continue
            try:claim=self.queue.claim(number)
            except ValueError:continue
            if claim is None:continue
            if not self.queue.assign(claim):return dict(issue=number,state='needs_input',reason='assignment_unconfirmed')
            if self.pipeline:
                return self._handoff(claim,number)
            body,directory,checkout,mirror,branch,logs=self._workspace(claim)
            controls=git_controls(checkout,mirror)
            permit=self.queue.start(claim)
            if permit is None:return dict(issue=number,state='needs_input',reason='start_unconfirmed')
            task=self.queue.consume(permit)
            request=dict(version=1,kind='superpowers-task',worker_name=self.name,task=task,checkout=str(checkout),
                branch=branch,plan_path=self.plans[str(number)],superpowers=dict(root=str(self.skills),manifest=self.pins),
                instructions='Execute this approved repository plan through installed Superpowers. Preserve independent reviews and tests. Commit locally. Never close the Issue or claim accepted main; return execution_completed or needs_input. Do not read private installation settings or credentials. Do not publish remote changes.')
            request_path=directory/'request.json';result_path=directory/'result.json';write(request_path,request)
            if self.harness['kind']=='custom':argv=[*self.harness['argv'],'--request',str(request_path),'--result',str(result_path)]
            else:
                if len(self.harness['argv'])!=1:raise ValueError('Invalid Codex harness argv')
                schema=directory/'schema.json';write(schema,dict(type='object',additionalProperties=False,required=['version','status','summary'],properties=dict(version=dict(type='integer',const=1),status=dict(type='string',enum=['execution_completed','needs_input']),summary=dict(type='string'))))
                argv=[*self.harness['argv'],'exec','--json','--sandbox','workspace-write','--add-dir',str(mirror),'-C',str(checkout),
                    '--output-schema',str(schema),'--output-last-message',str(result_path),
                    'Read AGENTS.md, the pinned Superpowers instructions and immutable task request '+str(request_path)+
                    '. Execute the prepared plan through Superpowers. Work and commit only in this private worktree. Do not publish, merge or close Issues. Return only required result JSON.']
            capture=directory/'capture';capture.mkdir()
            environment=harness_environment()
            with (capture/'process.json').open('xb') as facts:
                facts.flush();os.fsync(facts.fileno())
                write(self.fence,dict(version=1,claim_id=task['claim_id'],state='launch_reserved'))
                process=run_command(argv,checkout,self.harness['timeout_seconds'],env=environment,capture=dict(directory=capture,max_bytes_per_stream=self.harness['log_max_bytes']))
                facts.write(canonical(process).encode());facts.flush();os.fsync(facts.fileno())
            if process.get('cleanup_confirmed') is not True:raise ValueError('Worker child cleanup unresolved')
            self.fence.unlink()
            state='needs_input';head=None
            if (process.get('status')=='passed' and process.get('cleanup_confirmed') is True
                    and all(process.get(s+'_tail_unknown') is False and process.get(s+'_truncated') is False for s in ('stdout','stderr'))):
                try:
                    verify_git_controls(checkout,mirror,controls)
                    safe_config_path(result_path)
                    if result_path.stat().st_size>65536 or result_path.stat().st_nlink!=1:raise ValueError('Invalid harness result')
                    result=json.loads(result_path.read_bytes())
                    if set(result)!={'version','status','summary'} or type(result['version']) is not int or result['version']!=1 or result['status']!='execution_completed':raise ValueError('Harness not completed')
                    if self._pins()!=self.pins:raise ValueError('Superpowers changed during task')
                    common=Path(self._git(checkout,['rev-parse','--path-format=absolute','--git-common-dir'],logs).decode().strip()).resolve()
                    if common!=mirror.resolve() or self._git(checkout,['symbolic-ref','--short','HEAD'],logs).decode().strip()!=branch:raise ValueError('Worker Git identity changed')
                    head=self._git(checkout,['rev-parse','HEAD'],logs).decode().strip()
                    if head==task['base_sha'] or self._git(checkout,['status','--porcelain=v1','--untracked-files=all'],logs):raise ValueError('Missing committed task result')
                    state='awaiting_acceptance'
                except WorkerCleanupUnknown:raise
                except (OSError,ValueError,KeyError,TypeError):state='needs_input'
            outcome=dict(issue=number,state=state,worker=self.name,head_sha=head,process=process)
            write(directory/'outcome.json',outcome)
            self.queue.finish(permit,state,digest(outcome))
            return {k:outcome[k] for k in ('issue','state','worker','head_sha')}
        return None

    def _handoff(self,claim,number):
        from .pipeline_shared import deliver
        permit=self.queue.start(claim)
        if permit is None:return dict(issue=number,state='needs_input',reason='start_unconfirmed')
        task=self.queue.consume(permit)
        directory=self.root/task['claim_id'][:24];directory.mkdir(exist_ok=False)
        write(directory/'handoff.json',dict(version=1,task=task))
        outcome=dict(issue=number,state='awaiting_acceptance',worker=self.name,head_sha=None)
        # No model launches until the original worker confirms this exact
        # consumer/run in GitHub. A lost response stays execution_intent and
        # fenced even if a queued identity was committed.
        write(self.fence,dict(version=1,kind='pipeline_handoff',claim_id=task['claim_id'],state='delivery_intent'))
        receipt=deliver(task,self.harness,expected=self.pipeline_binding)
        if (set(receipt)!={'version','delivery_id','status','receipt_id'} or receipt['version']!=1
                or receipt['delivery_id']!=task['claim_id'] or receipt['status']!='accepted'):
            raise ValueError('Pipeline handoff unconfirmed')
        import uuid
        if str(uuid.UUID(receipt['receipt_id']))!=receipt['receipt_id']:raise ValueError('Invalid pipeline receipt')
        write(directory/'handoff-result.json',receipt)
        outcome['pipeline_run_id']=receipt['receipt_id']
        write(directory/'outcome.json',outcome)
        self.queue.finish(permit,'awaiting_acceptance',digest(outcome),handoff=dict(version=1,kind='pipeline',
            consumer_sha256=self.pipeline_binding,run_id=receipt['receipt_id']))
        self.fence.unlink()
        return outcome


def main(argv=None):
    import argparse
    from .project_connections import load_connections
    from .github_tasks import GitHubTasks
    parser=argparse.ArgumentParser(prog='task-tower shared-worker')
    parser.add_argument('command',choices=('run','status'))
    parser.add_argument('--connections',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--once',action='store_true');parser.add_argument('--max-tasks',type=int)
    args=parser.parse_args(argv)
    if args.command=='run' and not native_execution_supported():
        print(canonical(dict(status='needs_input',reason='unsupported_platform')));return 2
    try:
        config_path=safe_config_path(args.config)
        from .dispatch_selection import _pairs
        config=json.loads(config_path.read_text(encoding='utf-8'),object_pairs_hook=_pairs)
        required={'version','repository','worker_id','worker_name','assignee','workspace_root','superpowers_root','harness','allowlist','plans'}
        if (not isinstance(config,dict) or not required<=set(config) or set(config)-required-{'interval_seconds'}
                or type(config['version']) is not int or config['version']!=1):raise ValueError('Invalid private worker configuration')
        connections=load_connections(args.connections)
        selected=[c for c in connections if c.repository.casefold()==config['repository'].casefold()]
        if len(selected)!=1:raise ValueError('Worker project is not connected')
        connection=selected[0]
        for path in (args.connections,config_path):
            if path.resolve().is_relative_to(connection.checkout.resolve()):raise ValueError('Worker configuration must be private')
        interval=config.get('interval_seconds',10)
        if type(interval) is not int or not 1<=interval<=3600 or args.max_tasks is not None and args.max_tasks<1:raise ValueError('Invalid worker bounds')
        settings=dict(config,source_checkout=str(connection.checkout))
        store=GitHubTasks(connection)
        queue=SharedQueue(store,config['worker_id'],allowlist=config['allowlist'],assignee=config['assignee'])
        if args.command=='status':
            rows=[]
            from .github_tasks import GitHubRequestError
            for item in config['allowlist']:
                issue=store.get(item['issue']);ref='heads/task-tower/claims/issue-'+str(issue['id'])
                try:
                    pointer=store.request('GET','/git/ref/'+ref)
                    commit=store.request('GET','/git/commits/'+pointer['object']['sha'])
                    from .shared_queue import _PREFIX
                    if not commit['message'].startswith(_PREFIX):raise ValueError('Foreign claim format')
                    body=json.loads(commit['message'][len(_PREFIX):]);rows.append({k:body[k] for k in ('repository','issue','task_id','worker_id','state')})
                except GitHubRequestError as error:
                    if error.http_status!=404:raise
                    rows.append(dict(repository=connection.repository,issue=issue['number'],state='unclaimed'))
            print(canonical(dict(tasks=rows)));return 0
        worker=SharedWorker(queue,settings)
        completed=0
        while True:
            outcome=worker.run_once()
            if outcome is not None:
                print(canonical(outcome),flush=True);completed+=1
            if args.once or args.max_tasks is not None and completed>=args.max_tasks:return 0
            if outcome is None:time.sleep(interval)
    except KeyboardInterrupt:return 130
    except Exception:
        # Private argv, tokens, arbitrary API errors and installation paths are
        # never copied into a public operational diagnostic.
        print(canonical(dict(status='needs_input',reason='shared_worker_unavailable')));return 2
