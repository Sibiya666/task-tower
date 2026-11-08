"""Fresh repository identity validation with bounded subprocess overhead."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from task_tower import pipeline_inputs as inputs


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'repo space \u044f\u2028x'
        self.root.mkdir()
        self.git(self.root, 'init', '-b', 'main')
        self.git(self.root, '-c', 'user.name=Fixture', '-c',
                 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-m', 'initial')
        self.head = self.git(self.root, 'rev-parse', 'HEAD').decode().strip()

    def git(self, root, *args):
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN') and not k.upper().startswith('GIT_')}
        return subprocess.check_output(['git', '-C', str(root), *args], env=env,
                                       stderr=subprocess.PIPE, timeout=10)

    def test_fresh_path_pair_uses_one_process_and_preserves_unicode(self):
        with patch.object(inputs, '_git', wraps=inputs._git) as calls:
            self.assertEqual(inputs._repository(self.root, {}), self.root)
            self.assertEqual(inputs._repository(self.root, {}), self.root)
        self.assertEqual([c.args[1:] for c in calls.call_args_list],
                         [('rev-parse', '--show-toplevel', '--absolute-git-dir')] * 2)

    def test_linked_worktree_requires_exact_explicit_git_directory(self):
        linked = self.root.parent / 'linked space \u044f'
        self.git(self.root, 'worktree', 'add', '-b', 'linked', str(linked), self.head)
        directory = self.git(linked, 'rev-parse', '--absolute-git-dir').decode().strip()
        for policy in ({}, {'git_dir': str(self.root / '.git')}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                inputs._repository(linked, policy)
        self.assertEqual(inputs._repository(linked, {'git_dir': directory}), linked)

    def test_nested_directory_and_wrong_git_directory_are_rejected(self):
        nested = self.root / 'nested'; nested.mkdir()
        with self.assertRaises(ValueError):
            inputs._repository(nested, {})
        with self.assertRaises(ValueError):
            inputs._repository(self.root, {'git_dir': str(nested)})

    def test_malformed_path_framing_is_rejected(self):
        original = inputs._git
        root = os.fsencode(self.root.as_posix())
        directory = os.fsencode((self.root / '.git').as_posix())
        for raw in (b'', root + b'\n', root + b'\n\n',
                    root + b'\n' + directory, root + b'\n' + directory + b'\nextra\n'):
            def query(path, *args, **kwargs):
                if args == ('rev-parse', '--show-toplevel', '--absolute-git-dir'):
                    return raw
                return original(path, *args, **kwargs)
            with self.subTest(raw=raw), patch.object(inputs, '_git', side_effect=query):
                with self.assertRaises(ValueError):
                    inputs._repository(self.root, {})

    def test_head_still_observed_after_git_directory_filesystem_checks(self):
        original = inputs.safe_config_path
        changed = []
        def guard(path):
            result = original(path)
            if Path(path) == self.root / '.git' / '.pipeline-path-check' and not changed:
                self.git(self.root, '-c', 'user.name=Fixture', '-c',
                         'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-m', 'changed')
                changed.append(True)
            return result
        with patch.object(inputs, 'safe_config_path', side_effect=guard):
            with self.assertRaisesRegex(ValueError, 'HEAD'):
                inputs._repository(self.root, {'expected_head': self.head})
        self.assertEqual(changed, [True])

    def test_detached_and_unborn_head_remain_policy_dependent(self):
        self.git(self.root, 'checkout', '--detach', self.head)
        self.assertEqual(inputs._repository(self.root, {'expected_head': self.head}), self.root)
        with self.assertRaises(ValueError):
            inputs._repository(self.root, {'branch': 'main'})
        with self.assertRaises(ValueError):
            inputs._repository(self.root, {'expected_head': 'a' * 40})
        unborn = self.root.parent / 'unborn'; unborn.mkdir()
        self.git(unborn, 'init', '-b', 'main')
        self.assertEqual(inputs._repository(unborn, {}), unborn)
        with self.assertRaises(ValueError):
            inputs._repository(unborn, {'expected_head': self.head})

    def test_branch_and_refs_guards_still_use_fresh_observations(self):
        refs = hashlib.sha256(self.git(self.root, 'show-ref')).hexdigest()
        policy = {'branch': 'main', 'refs_sha256': refs, 'expected_head': self.head}
        self.assertEqual(inputs._repository(self.root, policy), self.root)
        self.git(self.root, 'branch', 'new-ref')
        with self.assertRaises(ValueError):
            inputs._repository(self.root, policy)

    @unittest.skipIf(os.name == 'nt', 'LF paths are not supported by Windows')
    def test_lf_root_and_bound_git_directory_keep_separate_queries(self):
        parent = self.root.parent / 'line\nparent'; parent.mkdir()
        source = parent / 'source'
        self.git(self.root, 'clone', '--no-hardlinks', str(self.root), str(source))
        self.assertEqual(inputs._repository(source, {}), source)
        linked = self.root.parent / 'plain-linked'
        self.git(source, 'worktree', 'add', '-b', 'lf-linked', str(linked), self.head)
        directory = self.git(linked, 'rev-parse', '--absolute-git-dir').decode().strip()
        with patch.object(inputs, '_git', wraps=inputs._git) as calls:
            self.assertEqual(inputs._repository(linked, {'git_dir': directory}), linked)
        self.assertEqual([c.args[1:] for c in calls.call_args_list],
                         [('rev-parse', '--show-toplevel'), ('rev-parse', '--absolute-git-dir')])
