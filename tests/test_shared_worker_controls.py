"""Host must inspect private Git controls before invoking Git after a harness."""
import subprocess
import tempfile
import unittest
from pathlib import Path


class GitControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.source=self.root/'source';self.source.mkdir()
        def git(root,*args):
            return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL)
        git(self.source,'init','-b','main')
        git(self.source,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-m','base')
        self.mirror=self.root/'repo.git';self.checkout=self.root/'work'
        git(self.root,'clone','--bare','--template=',str(self.source),str(self.mirror))
        git(self.mirror,'worktree','add','-b','worker',str(self.checkout),'main')

    def test_clean_controls_are_stable_without_running_git(self):
        from task_tower.shared_worker import git_controls,verify_git_controls
        before=git_controls(self.checkout,self.mirror)
        verify_git_controls(self.checkout,self.mirror,before)

    def test_changed_local_config_is_rejected_before_host_git(self):
        from task_tower.shared_worker import git_controls,verify_git_controls
        before=git_controls(self.checkout,self.mirror)
        with (self.mirror/'config').open('a') as stream:
            stream.write('\n[filter "unexpected"]\n\tclean = arbitrary-host-command\n')
        with self.assertRaises(ValueError):verify_git_controls(self.checkout,self.mirror,before)

    def test_worktree_pointer_cannot_move_to_another_repository(self):
        from task_tower.shared_worker import git_controls,verify_git_controls
        before=git_controls(self.checkout,self.mirror)
        (self.checkout/'.git').chmod(0o600)
        with (self.checkout/'.git').open('r+',encoding='utf-8') as stream:
            stream.write('gitdir: '+str(self.source/'.git')+'\n');stream.truncate()
        with self.assertRaises(ValueError):verify_git_controls(self.checkout,self.mirror,before)

    def test_added_alternate_objects_or_worktree_config_is_rejected(self):
        from task_tower.shared_worker import git_controls,verify_git_controls
        before=git_controls(self.checkout,self.mirror)
        for relative in ('objects/info/alternates','config.worktree','info/grafts'):
            with self.subTest(relative=relative):
                path=self.mirror/relative;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('unexpected\n')
                with self.assertRaises(ValueError):verify_git_controls(self.checkout,self.mirror,before)
                path.unlink()
