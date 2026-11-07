"""Trusted project-to-repository mapping. Git owns worktree creation."""
import os
from pathlib import Path
import re
import tempfile
from ..processes import run_command
from ..project_connections import safe_config_path
from ..service.beads import identity

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
    def _git(self,repo,*args,timeout=10,raw=False):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
        env['GIT_TERMINAL_PROMPT']='0'
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_NO_LAZY_FETCH='1',GIT_NO_REPLACE_OBJECTS='1')
        with tempfile.TemporaryDirectory(prefix='tower-connector-git-') as tmp:
            result=run_command(['git','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',*args],repo,timeout,env=env,capture={'directory':Path(tmp),'max_bytes_per_stream':1048576})
            if result.get('exit_code')!=0 or result.get('status')!='passed' or not result.get('cleanup_confirmed') or any(result.get(k) for k in ('stdout_truncated','stderr_truncated','stdout_tail_unknown','stderr_tail_unknown')):raise ValueError('git_operation_unknown')
            text=(Path(tmp)/'stdout.log').read_text(encoding='utf-8')
            return text if raw else text.strip()
    def prepare(self,project_id,attempt_id,base_sha):return self._prepare(project_id,attempt_id,base_sha,False)
    def prepare_review(self,project_id,attempt_id,base_sha):return self._prepare(project_id,attempt_id,base_sha,True)
    def _prepare(self,project,attempt,sha,review):
        if not isinstance(attempt,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',attempt) or attempt in ('.','..'):raise ValueError('invalid_attempt')
        if project not in self.projects:raise ValueError('project_forbidden')
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('exact_sha_required')
        repo,root=self.projects[project];target=root/attempt;safe_config_path(target/'.tower-guard')
        branch=None if review else 'codex/headless-'+attempt
        data=dict(project_id=project,path=str(target),branch=branch,base_sha=sha,state='ready',review=review)
        prior=self.store.worktree(attempt)
        if prior:
            if prior!=data:raise ValueError('worktree_unknown_or_conflict')
            if not os.path.samefile(self._git(target,'rev-parse','--show-toplevel'),target):raise ValueError('foreign_worktree')
            if self._git(target,'rev-parse','--git-common-dir'):
                actual=Path(self._git(target,'rev-parse','--git-common-dir'))
                if not actual.is_absolute():actual=target/actual
                common=Path(self._git(repo,'rev-parse','--git-common-dir'))
                if not common.is_absolute():common=repo/common
                if actual.resolve()!=common.resolve():raise ValueError('foreign_repository')
            if self._git(target,'status','--porcelain'):raise ValueError('dirty_worktree')
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
