"""Trusted project-to-repository mapping. Git owns worktree creation."""
import os
from pathlib import Path
import re
import time
from ..processes import run_command
from ..project_connections import safe_config_path
from ..service.beads import identity
from .diagnostics import GitFailure,git_receipt,private_directory,capture_directory

class Worktrees:
    def __init__(self,projects,store):
        self.store=store;self.projects={}
        for key,value in projects.items():
            identity(key)
            if set(value)!={'repository','worktree_root'}:raise ValueError('invalid_project_mapping')
            repo=Path(value['repository']);root=Path(value['worktree_root'])
            if not repo.is_absolute() or not root.is_absolute():raise ValueError('absolute_path_required')
            safe_config_path(repo/'.tower-guard');safe_config_path(root/'.tower-guard')
            if not repo.is_dir():raise ValueError('invalid_repository')
            if root==repo or repo in root.parents:raise ValueError('worktree_root_inside_repository')
            self.projects[key]=(repo,root)
    @staticmethod
    def _git(repo,*args,timeout=10,raw=False):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        env['GIT_TERMINAL_PROMPT']='0'
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_NO_LAZY_FETCH='1',GIT_NO_REPLACE_OBJECTS='1')
        deadline=time.monotonic()+timeout
        with capture_directory() as tmp:
            if not private_directory(tmp):
                receipt=git_receipt(args,dict(status='unavailable',exit_code=None,cleanup_confirmed=True),tmp)
                receipt['reason']='git_capture_not_private';raise GitFailure(receipt)
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ValueError('git_capture_unavailable')
            result=run_command(['git','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',*args],repo,remaining,env=env,capture={'directory':Path(tmp),'max_bytes_per_stream':1048576})
            if result.get('exit_code')!=0 or result.get('status')!='passed' or not result.get('cleanup_confirmed') or any(result.get(k) for k in ('stdout_truncated','stderr_truncated','stdout_tail_unknown','stderr_tail_unknown')):
                raise GitFailure(git_receipt(args,result,tmp))
            text=(Path(tmp)/'stdout.log').read_text(encoding='utf-8')
            return text if raw else text.strip()
    def inspect_preparing(self,receipt,original_command):
        """Read-only observations, not approval, attach, resume or fence release."""
        from ..preparing_recovery import parse_receipt,fingerprint
        r=parse_receipt(receipt);attempt=r['attempt_id'];key=r['command_id']
        if (not isinstance(original_command,dict) or r['connector_id']!=self.store.connector_id or r['project_id'] not in self.projects
                or r['native_owner']!='tower-'+attempt or fingerprint(original_command)!=r['command_sha256']
                or any(original_command.get(k)!=r[k] for k in ('command_id','attempt_id','project_id','base_sha'))
                or original_command.get('kind')!='execute'):
            raise ValueError('preparing_command_changed')
        repo,root=self.projects[r['project_id']];target=root/attempt
        safe_config_path(target/'.tower-guard')
        expected=dict(project_id=r['project_id'],path=str(target),branch=r['branch'],
            base_sha=r['base_sha'],state='preparing',review=False)
        with self.store.lock:
            prior=self.store.worktree(attempt);old=self.store.command(key)
            known={'command','phase','thread_id','turn_id','resource_id','decision','execution','cleanup_resources','cleanup_confirmed'}
            if (set(old)-known or prior!=expected or prior.get('review') is not False or fingerprint(prior)!=r['worktree_sha256']
                    or old['command']!=original_command or old['phase']!='needs_reconciliation'
                    or any(old.get(k) is not None for k in ('thread_id','turn_id','resource_id','decision','execution'))
                    or old.get('cleanup_resources') not in (None,[])
                    or (old.get('cleanup_confirmed') is not None and old.get('cleanup_confirmed') is not True)
                    or any(d['command']['attempt_id']==attempt and d['command']['command_id']!=key for d in self.store.commands())
                    or any(e['attempt_id']==attempt for e in self.store.pending_events())):
                raise ValueError('preparing_history_uncertain')
        def exists(path):
            try:Path(path).lstat()
            except FileNotFoundError:return False
            except OSError:raise ValueError('preparing_filesystem_unverified') from None
            return True
        if exists(target):raise ValueError('preparing_target_present')
        deadline=time.monotonic()+10
        def git(*args,raw=False):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ValueError('preparing_observation_deadline')
            return self._git(repo,*args,timeout=remaining,raw=raw)
        try:
            safe_config_path(repo/'.tower-guard')
            repository_identity=repo.stat()
            if not os.path.samefile(repo,git('rev-parse','--show-toplevel')):
                raise ValueError('preparing_repository_changed')
            if git('status','--porcelain','--untracked-files=all'):
                raise ValueError('preparing_repository_dirty')
            entries=git('ls-files','-v','-z').split('\0')
            if (entries[-1]!='' or len(entries)<2
                    or any(not entry.startswith('H ') or len(entry)<=2 for entry in entries[:-1])):
                raise ValueError('preparing_repository_unverified')
            ref='refs/heads/'+r['branch']
            actual=git('for-each-ref','--format=%(refname)%00%(objectname)%00%(objecttype)%00%(symref)',ref)
            if actual.split('\0')!=[ref,r['branch_sha'],'commit','']:
                raise ValueError('preparing_branch_changed')
            markers=('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply',
                'sequencer','index.lock','HEAD.lock','packed-refs.lock',ref+'.lock')
            for marker in markers:
                path=Path(git('rev-parse','--git-path',marker))
                if not path.is_absolute():path=repo/path
                if exists(path):raise ValueError('preparing_repository_busy')
            registrations=git('worktree','list','--porcelain','-z',raw=True)
            if not registrations.endswith('\0\0'):
                raise ValueError('preparing_registration_unknown')
            seen=set()
            for block in registrations[:-2].split('\0\0'):
                fields=block.split('\0');keys=[field.partition(' ')[0] for field in fields]
                if (not fields[0].startswith('worktree ') or len(keys)!=len(set(keys))
                        or any(key not in ('worktree','HEAD','branch','detached','bare','locked','prunable') for key in keys)):
                    raise ValueError('preparing_registration_unknown')
                attrs={key:(field.partition(' ')[2] if ' ' in field else None) for key,field in zip(keys,fields)}
                if not Path(attrs['worktree']).is_absolute():
                    raise ValueError('preparing_registration_unknown')
                if 'bare' in attrs:
                    if attrs['bare'] is not None or any(key in attrs for key in ('HEAD','branch','detached')):
                        raise ValueError('preparing_registration_unknown')
                elif (re.fullmatch('[0-9a-f]{40}',attrs.get('HEAD') or '') is None
                        or ('branch' in attrs)==('detached' in attrs)
                        or ('detached' in attrs and attrs['detached'] is not None)
                        or ('branch' in attrs and (not (attrs['branch'] or '').startswith('refs/heads/')
                            or len(attrs['branch'] or '')<=len('refs/heads/')))):
                    raise ValueError('preparing_registration_unknown')
                registered=os.path.normcase(str(Path(attrs['worktree']).resolve()))
                if registered in seen:raise ValueError('preparing_registration_unknown')
                seen.add(registered)
                if registered==os.path.normcase(str(target.resolve())) or attrs.get('branch')==ref:
                    raise ValueError('preparing_registration_present')
            if os.path.normcase(str(repo.resolve())) not in seen:
                raise ValueError('preparing_registration_unknown')
            safe_config_path(repo/'.tower-guard')
            if not os.path.samestat(repository_identity,repo.stat()):
                raise ValueError('preparing_repository_changed')
            if time.monotonic()>deadline:raise ValueError('preparing_observation_deadline')
        except (OSError,RuntimeError):
            raise ValueError('preparing_filesystem_unverified') from None
        return dict(prior)


    def prepare(self,project_id,attempt_id,base_sha):return self._prepare(project_id,attempt_id,base_sha,False)
    def prepare_review(self,project_id,attempt_id,base_sha):return self._prepare(project_id,attempt_id,base_sha,True)
    def prepare_revision(self,project,attempt,base_sha,update_base=None):
        if update_base is not None:
            if set(update_base)!={'old_base_sha','new_base_sha'} or update_base['new_base_sha']!=base_sha:raise ValueError('invalid_base_update')
            old=update_base['old_base_sha'];tree=self.prepare(project,attempt,old);path=Path(tree['path']);repo=self.projects[project][0]
            self._git(repo,'fetch','origin','main',timeout=60)
            if self._git(repo,'rev-parse','FETCH_HEAD')!=base_sha:raise ValueError('base_moved_again')
            self._git(repo,'rev-parse',base_sha+'^{commit}')
            self.store.save_worktree(attempt,dict(tree,state='base_update_intent'))
            state='ready'
            try:
                self._git(path,'merge','--no-commit','--no-ff',base_sha)
                if self._git(path,'status','--porcelain'):
                    if self._git(path,'rev-parse','MERGE_HEAD')!=base_sha:raise ValueError('base_update_unknown')
                    state='merge_pending'
                else:self._git(path,'merge-base','--is-ancestor',base_sha,'HEAD')
            except ValueError:
                if self._git(path,'rev-parse','MERGE_HEAD')!=base_sha or not self._git(path,'diff','--name-only','--diff-filter=U'):raise ValueError('base_update_unknown') from None
                state='merge_pending'
            self.store.save_worktree(attempt,dict(tree,base_sha=base_sha,state=state))
        return self._prepare(project,attempt,base_sha,False,allow_conflict=True)

    def _prepare(self,project,attempt,sha,review,allow_conflict=False):
        if not isinstance(attempt,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',attempt) or attempt in ('.','..'):raise ValueError('invalid_attempt')
        if project not in self.projects:raise ValueError('project_forbidden')
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('exact_sha_required')
        repo,root=self.projects[project];target=root/attempt;safe_config_path(target/'.tower-guard')
        branch=None if review else 'codex/headless-'+attempt
        data=dict(project_id=project,path=str(target),branch=branch,base_sha=sha,state='ready',review=review)
        prior=self.store.worktree(attempt)
        if prior:
            conflict=prior.get('state')=='merge_pending' and not review
            if conflict:
                if dict(prior,state='ready')!=data:raise ValueError('worktree_unknown_or_conflict')
                if allow_conflict:
                    if self._git(target,'rev-parse','MERGE_HEAD')!=sha:raise ValueError('merge_conflict_identity_changed')
                else:
                    if self._git(target,'status','--porcelain'):raise ValueError('unresolved_merge')
                    self._git(target,'merge-base','--is-ancestor',sha,'HEAD')
                    prior=dict(prior,state='ready');self.store.save_worktree(attempt,prior);conflict=False
            if dict(prior,state='ready')!=data or prior['state'] not in ('ready','merge_pending'):raise ValueError('worktree_unknown_or_conflict')
            if not os.path.samefile(self._git(target,'rev-parse','--show-toplevel'),target):raise ValueError('foreign_worktree')
            if self._git(target,'rev-parse','--git-common-dir'):
                actual=Path(self._git(target,'rev-parse','--git-common-dir'))
                if not actual.is_absolute():actual=target/actual
                common=Path(self._git(repo,'rev-parse','--git-common-dir'))
                if not common.is_absolute():common=repo/common
                if actual.resolve()!=common.resolve():raise ValueError('foreign_repository')
            if not (conflict and allow_conflict) and self._git(target,'status','--porcelain'):raise ValueError('dirty_worktree')
            actual=self._git(target,'rev-parse','--abbrev-ref','HEAD')
            if actual!=(branch or 'HEAD'):raise ValueError('branch_changed')
            if review and self._git(target,'rev-parse','HEAD')!=sha:raise ValueError('review_sha_changed')
            return prior
        if target.exists():raise ValueError('unowned_worktree')
        if self._git(repo,'rev-parse',sha+'^{commit}')!=sha:raise ValueError('unknown_sha')
        root.mkdir(parents=True,exist_ok=True)
        self.store.save_worktree(attempt,dict(data,state='preparing'))
        args=['worktree','add','--detach',str(target),sha] if review else ['worktree','add','-b',branch,str(target),sha]
        self._git(repo,*args)
        self.store.save_worktree(attempt,data)
        return data

    def source(self,project,attempt,base_sha):
        from .briefs import validate_source
        tree=self.prepare(project,attempt,base_sha);path=Path(tree['path'])
        head=self._git(path,'rev-parse','HEAD')
        self._git(path,'merge-base','--is-ancestor',base_sha,head)
        diff=self._git(path,'diff','--no-ext-diff','--no-textconv','--binary',base_sha,head,'--',raw=True)
        return validate_source(dict(base_sha=base_sha,head_sha=head,diff=diff))
