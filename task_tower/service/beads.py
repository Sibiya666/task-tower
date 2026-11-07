"""Fixed, bounded native Beads operations against trusted project configuration."""
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

from ..processes import run_command

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
BEAD = re.compile(r'[a-z0-9][a-z0-9.-]{0,127}\Z')
LIMIT = 1024 * 1024


class ServiceError(Exception):
    def __init__(self, code, status=409, retryable=False):
        super().__init__(code)
        self.code, self.status, self.retryable = code, status, retryable


def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ServiceError('invalid_identity', 400)
    return value


def bead_id(value):
    if not isinstance(value, str) or not BEAD.fullmatch(value) or '-' not in value:
        raise ServiceError('invalid_bead', 400)
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate_key')
            result[key] = value
        return result
    def constant(_): raise ValueError('invalid_constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def environment(directory):
    env = {k:v for k,v in os.environ.items()
           if not k.upper().startswith(('BD_', 'BEADS_', 'DOLT_', 'GIT_'))
           and k.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN')}
    env.update(BEADS_DIR=str(directory / '.beads'), BD_EVENTS_JOURNAL='1',
               BD_LAST_TOUCHED_FALLBACK='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
               GIT_NO_LAZY_FETCH='1', GIT_NO_REPLACE_OBJECTS='1', PYTHONUTF8='1')
    return env


def native_runner(argv, cwd, timeout, env):
    # The established supervisor bounds output and terminates descendants.
    with tempfile.TemporaryDirectory(prefix='tower-service-native-') as temp:
        result = run_command(argv, cwd, timeout, env=env,
                             capture={'directory': Path(temp), 'max_bytes_per_stream': LIMIT})
        if (result.get('exit_code') != 0 or result.get('status') != 'passed'
                or not result.get('cleanup_confirmed')
                or any(result.get(k) for k in ('stdout_truncated','stderr_truncated',
                                               'stdout_tail_unknown','stderr_tail_unknown'))):
            raise ServiceError('native_outcome_unknown')
        try:
            return strict_json((Path(temp)/'stdout.log').read_text(encoding='utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            raise ServiceError('native_invalid_output') from None


class Beads:
    def __init__(self, executable, projects, *, runner=None, timeout=10):
        self.executable = Path(executable)
        if not self.executable.is_absolute() or not 0 < timeout <= 30:
            raise ValueError('invalid_native_configuration')
        self.projects = {identity(k):Path(v) for k,v in projects.items()}
        if not self.projects or any(not p.is_absolute() or not p.is_dir() for p in self.projects.values()):
            raise ValueError('invalid_project_configuration')
        self.runner, self.timeout = runner or native_runner, timeout

    def project(self, project):
        identity(project)
        if project not in self.projects: raise ServiceError('project_forbidden',403)
        return self.projects[project]

    def _run(self, project, actor, args, deadline=None):
        directory = self.project(project)
        identity(actor)
        remaining = self.timeout if deadline is None else min(self.timeout,deadline-time.monotonic())
        if remaining <= 0: raise ServiceError('native_deadline')
        try:
            return self.runner([str(self.executable),'--sandbox','--actor',actor,*args,'--json'],
                               directory, remaining, environment(directory))
        except ServiceError: raise
        except Exception: raise ServiceError('native_outcome_unknown') from None

    def ready(self, project, *, deadline=None):
        rows = self._run(project, 'task-tower-service', ['ready','--limit','1000'],deadline)
        if not isinstance(rows,list) or len(rows)>1000: raise ServiceError('native_invalid_output')
        seen=set()
        for row in rows:
            if not isinstance(row,dict): raise ServiceError('native_invalid_output')
            key=bead_id(row.get('id'))
            if key in seen or row.get('status')!='open' or row.get('assignee'):
                raise ServiceError('native_inconsistent_ready')
            seen.add(key)
        return rows

    def show(self, project, bead, *, deadline=None):
        bead_id(bead)
        value=self._run(project,'task-tower-service',['show',bead],deadline)
        if isinstance(value,list) and len(value)==1: value=value[0]
        if not isinstance(value,dict) or value.get('id')!=bead or not isinstance(value.get('status'),str):
            raise ServiceError('native_invalid_output')
        return value

    def claim(self, project, bead, actor):
        self.project(project);bead_id(bead);identity(actor)
        deadline=time.monotonic()+30
        row=self.show(project,bead,deadline=deadline)
        if row.get('assignee'): raise ServiceError('owner_conflict')
        if row.get('status')!='open' or bead not in {r['id'] for r in self.ready(project,deadline=deadline)}:
            raise ServiceError('not_ready')
        self._run(project,actor,['update',bead,'--claim'],deadline)
        row=self.show(project,bead,deadline=deadline)
        dependencies=row.get('dependencies',[])
        if not isinstance(dependencies,list) or any(not isinstance(d,dict) or
                (d.get('dependency_type')=='blocks' and d.get('status')!='closed') for d in dependencies):
            raise ServiceError('claim_dependency_changed')
        if row.get('status')!='in_progress' or row.get('assignee')!=actor:
            raise ServiceError('claim_readback_mismatch')
        return row

    def history(self,project,bead):
        bead_id(bead)
        rows=self._run(project,'task-tower-service',['history',bead,'--events','--limit','100'])
        if not isinstance(rows,list) or len(rows)>100 or any(not isinstance(r,dict) for r in rows):raise ServiceError('native_invalid_history')
        return rows

    def close(self, project, bead, actor, reason):
        # Caller supplies separately verified acceptance; this primitive grants none.
        self.project(project);bead_id(bead);identity(actor)
        if not isinstance(reason,str) or not 1<=len(reason)<=4096 or '\x00' in reason:
            raise ServiceError('invalid_reason',400)
        deadline=time.monotonic()+30
        row=self.show(project,bead,deadline=deadline)
        if row.get('assignee')!=actor: raise ServiceError('owner_conflict')
        self._run(project,actor,['close',bead,'--reason',reason],deadline)
        row=self.show(project,bead,deadline=deadline)
        if row.get('status')!='closed' or row.get('assignee')!=actor:
            raise ServiceError('close_readback_mismatch')
        return row

    def create_deferred(self, project, task, actor, deadline):
        return self._run(project,actor,['create','--id',bead_id(task['id']),
            '--title',task['title'],'--description',task['description'],
            '--type','task','--status','deferred','--defer','9999-12-31T00:00:00Z'],deadline)

    def add_dependency(self, project, bead, dependency, actor, deadline):
        return self._run(project,actor,['dep','add',bead_id(bead),bead_id(dependency)],deadline)

    def publish(self, project, bead, actor, deadline):
        return self._run(project,actor,['update',bead_id(bead),'--status','open','--defer',''],deadline)
