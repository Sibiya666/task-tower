"""Disposable Git/receipt data shared by the approved preparing slices."""
from pathlib import Path
import tempfile
import unittest

ENGINE='b'*40
PRIOR='3d096092621b931af2618eea1fba78bad4315491'


def receipt():
    return dict(version=1,action='attach_existing_preparing_v1',operation_id='op-1',
        connector_id='host1',project_id='project1',attempt_id='attempt1',command_id='command1',
        bead_id='task-one',native_owner='tower-attempt1',base_sha='a'*40,branch_sha='a'*40,
        engine_sha=ENGINE,prior_engine_sha=PRIOR,branch='codex/headless-attempt1',
        command_sha256='1'*64,worktree_sha256='2'*64,cleanup_sha256='3'*64)


class GitCase(unittest.TestCase):
    def setUp(self):
        from task_tower.connector.worktrees import Worktrees
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.git=Worktrees._git
        self.git(self.root,'init','-q')
        self.git(self.root,'config','user.email','fixture@example.invalid')
        self.git(self.root,'config','user.name','Fixture')
        self.module=self.root/'task_tower'/'preparing_recovery.py'
        self.module.parent.mkdir();self.module.write_text('# disposable source\n',encoding='utf-8')
        self.git(self.root,'add','task_tower/preparing_recovery.py')
        self.git(self.root,'-c','commit.gpgsign=false','commit','-qm','fixture')
        self.head=self.git(self.root,'rev-parse','HEAD')
