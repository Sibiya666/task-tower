import subprocess
import tempfile
import unittest
from pathlib import Path
from task_tower.connector.store import ConnectorStore
from task_tower.connector.worktrees import Worktrees

class WorktreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init');self.git('config','user.email','fixture@example.invalid');self.git('config','user.name','Fixture')
        (self.repo/'a').write_text('one',encoding='utf-8');self.git('add','a');self.git('commit','-m','fixture')
        self.sha=self.git('rev-parse','HEAD')
        self.store=ConnectorStore(self.root/'journal','host1');self.addCleanup(self.store.close)
        self.w=Worktrees({'p':{'repository':self.repo,'worktree_root':self.root/'trees'}},self.store)
    def git(self,*a):
        return subprocess.run(['git',*a],cwd=self.repo,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',timeout=10).stdout.strip()
    def test_prepare_and_restart_preserves_tree(self):
        first=self.w.prepare('p','attempt1',self.sha)
        self.assertEqual(self.w.prepare('p','attempt1',self.sha),first)
        self.assertTrue(Path(first['path']).is_dir())
    def test_dirty_existing_rejected_preserved(self):
        first=self.w.prepare('p','attempt1',self.sha);p=Path(first['path'])/'foreign';p.write_text('keep',encoding='utf-8')
        with self.assertRaises(ValueError):self.w.prepare('p','attempt1',self.sha)
        self.assertEqual(p.read_text(encoding='utf-8'),'keep')
    def test_foreign_project_path_and_sha_rejected(self):
        for project,attempt,sha in [('foreign','a',self.sha),('p','../escape',self.sha),('p','a','HEAD')]:
            with self.subTest(project=project,attempt=attempt,sha=sha),self.assertRaises(ValueError):self.w.prepare(project,attempt,sha)
    def test_preexisting_unowned_target_rejected(self):
        target=self.root/'trees'/'attempt1';target.mkdir(parents=True)
        with self.assertRaises(ValueError):self.w.prepare('p','attempt1',self.sha)
    def test_reviewer_detached_separate_checkout(self):
        writer=self.w.prepare('p','attempt1',self.sha)
        reviewer=self.w.prepare_review('p','review1',self.sha)
        self.assertNotEqual(writer['path'],reviewer['path']);self.assertIsNone(reviewer['branch'])
