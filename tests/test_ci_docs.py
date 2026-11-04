"""Real Git-object regressions for the bounded prose CI route."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class DocsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.write('README.md', '# Readme\n')
        self.write('docs/guide.md', '# Guide\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=10).stdout.decode('utf-8')

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '--allow-empty', '-m', 'fixture')

    def merge(self, tree=None):
        tree = tree or self.git('write-tree').strip()
        second = self.git('commit-tree', tree, '-p', self.base, '-m', 'topic').strip()
        head = self.git('commit-tree', tree, '-p', self.base, '-p', second, '-m', 'merge').strip()
        self.git('update-ref', 'HEAD', head)
        return head

    def object(self, kind, data):
        return subprocess.run(['git', 'hash-object', '-t', kind, '-w', '--stdin'],
                              input=data, cwd=self.repo, check=True, timeout=10,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode('ascii').strip()

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('task_tower.ci_docs'), 'missing docs helper')
        return importlib.import_module('task_tower.ci_docs')

    def validate(self):
        return self.api().validate(self.repo, repository='owner/repo', pr_number=7, phase='pr')

    def test_docs_report_and_cli_fixed_output(self):
        self.write('README.md', '[guide](docs/guide.md)\n')
        self.git('add', '-A')
        head = self.merge()
        api = self.api()
        self.assertEqual(api.classify(self.repo)['mode'], 'docs')
        self.assertEqual(api.classify(os.path.relpath(self.repo))['mode'], 'docs')
        report = self.validate()
        self.assertEqual((report['head'], report['base']), (head, self.base))
        self.assertEqual((report['kind'], report['runtime_tests']), ('documentation.validation', 'not_run'))
        self.assertEqual((report['repository'], report['pr_number'], report['phase']), ('owner/repo', 7, 'pr'))
        out, report_path = self.repo/'output', self.repo/'report.json'
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        result = subprocess.run([sys.executable, '-m', 'task_tower.ci_docs', '--scope', '--report', str(report_path), '--github-output', str(out)], cwd=self.repo, env=env, timeout=30, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(out.read_text(encoding='utf-8'), 'mode=docs\n')
        self.assertEqual(json.loads(report_path.read_text(encoding='utf-8'))['head'], head)

    def test_single_parent_and_empty_merge_are_full(self):
        self.assertEqual(self.api().classify(self.repo)['mode'], 'full')
        self.merge()
        self.assertEqual(self.api().classify(self.repo)['mode'], 'full')

    def test_unsafe_paths_and_modes_are_full(self):
        api = self.api()
        for path in ('code.py', '.github/workflows/ci.yml', 'docs/templates/a.md', 'docs/.hidden.md'):
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.write(path, 'content\n')
                self.git('add', '-A')
                self.merge()
                self.assertEqual(api.classify(self.repo)['mode'], 'full')
        self.git('reset', '--hard', self.base)
        self.git('update-index', '--chmod=+x', 'README.md')
        self.merge()
        self.assertEqual(api.classify(self.repo)['mode'], 'full')

    def test_git_only_odd_filename_and_symlink_modes(self):
        api = self.api()
        oid = self.git('rev-parse', 'HEAD:README.md').strip()
        for mode, path in (('100644', 'docs/a\nb.md'), ('100644', 'docs/a\u0085b.md'), ('120000', 'docs/link.md')):
            subtree = self.object('tree', mode.encode('ascii') + b' ' + path.split('/')[1].encode('utf-8') + b'\0' + bytes.fromhex(oid))
            tree = self.object('tree', b'40000 docs\0' + bytes.fromhex(subtree))
            self.merge(tree)
            self.assertEqual(api.classify(self.repo)['mode'], 'full')
            self.git('update-ref', 'HEAD', self.base)

    def test_missing_parent_is_full(self):
        self.write('README.md', 'changed\n')
        self.git('add', '-A')
        self.merge()
        obj = self.repo/'.git'/'objects'/self.base[:2]/self.base[2:]
        obj.chmod(0o600)
        obj.unlink()
        self.assertEqual(self.api().classify(self.repo)['mode'], 'full')

    def test_symlink_ancestor_is_a_broken_target_without_filesystem_access(self):
        oid = self.git('rev-parse', 'HEAD:README.md').strip()
        self.git('update-index', '--add', '--cacheinfo', '120000', oid, 'alias')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.write('README.md', '[private](alias/anything.md)\n')
        self.git('add', 'README.md')
        self.merge()
        with self.assertRaises(ValueError):
            self.validate()

    def test_rename_into_prose_does_not_hide_code(self):
        self.write('source.py', 'pass\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('mv', 'source.py', 'docs/source.md')
        self.merge()
        self.assertEqual(self.api().classify(self.repo)['mode'], 'full')

    def test_new_broken_link_fails_but_historical_one_is_tolerated(self):
        self.write('README.md', '[old](missing.md)\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.write('docs/guide.md', '# Corrected\n')
        self.git('add', '-A')
        self.merge()
        self.assertEqual(self.validate()['checks'], 'passed')
        self.git('reset', '--hard', self.base)
        self.write('README.md', '[old](missing.md)\n[new](other.md)\n')
        self.git('add', '-A')
        self.merge()
        with self.assertRaises(ValueError):
            self.validate()

    def test_deleted_target_caught_in_unchanged_referrer(self):
        self.write('README.md', '[guide](docs/guide.md)\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('rm', 'docs/guide.md')
        self.merge()
        with self.assertRaises(ValueError):
            self.validate()

    def test_unchanged_markdown_outside_allowlist_still_checks_deleted_target(self):
        self.write('overlay/README.md', '[guide](../docs/guide.md)\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('rm', 'docs/guide.md')
        self.merge()
        self.assertEqual(self.api().classify(self.repo)['mode'], 'docs')
        with self.assertRaises(ValueError):
            self.validate()

    def test_supported_links_code_and_unicode(self):
        self.write('docs/space (\u00e9).md', '# Target\n')
        self.write('README.md', '[a](docs/space%20%28%C3%A9%29.md)\n[b](docs/space \\(\u00e9\\).md)\n[x][ref]\n[ref]: <docs/space (\u00e9).md>\n`[skip](missing)`\n```md\n[x](missing)\n```\n~~~\n[x](missing)\n~~~\n[a](#heading) [b](https://example.invalid/x) ![c](mailto:a@b)\n')
        self.git('add', '-A')
        self.merge()
        self.assertEqual(self.validate()['checks'], 'passed')

    def test_repository_root_directory_is_a_tracked_tree_target(self):
        self.write('README.md', '[root](.) [docs](docs/)\n')
        self.git('add', '-A')
        self.merge()
        self.assertEqual(self.validate()['checks'], 'passed')

    def test_root_escape_whitespace_and_invalid_utf8_refuse(self):
        for content in ('[x](../private)\n', 'trailing  \n'):
            self.git('reset', '--hard', self.base)
            self.write('README.md', content)
            self.git('add', '-A')
            self.merge()
            with self.assertRaises(ValueError):
                self.validate()
        self.git('reset', '--hard', self.base)
        (self.repo/'README.md').write_bytes(b'\xff\n')
        self.git('add', '-A')
        self.merge()
        with self.assertRaises(ValueError):
            self.validate()

    def test_limits_refuse_success(self):
        self.write('README.md', '# Changed\n')
        self.git('add', '-A')
        self.merge()
        api = self.api()
        with patch.object(api, 'MAX_PROSE_BYTES', 1):
            with self.assertRaises(ValueError):
                self.validate()
        with patch.object(api, 'MAX_CAPTURE_BYTES', 1):
            self.assertEqual(api.classify(self.repo)['mode'], 'full')
            with self.assertRaises(ValueError):
                self.validate()
        with patch.object(api, 'MAX_SECONDS', 0):
            self.assertEqual(api.classify(self.repo)['mode'], 'full')
            with self.assertRaises(ValueError):
                self.validate()

    def test_inherited_git_context_cannot_redirect_source(self):
        self.write('README.md', '# Changed\n')
        self.git('add', '-A')
        head = self.merge()
        with patch.dict(os.environ, {'GIT_DIR': str(self.repo/'unavailable'), 'GIT_WORK_TREE': str(self.repo/'other')}):
            report = self.api().classify(self.repo)
        self.assertEqual((report['mode'], report['head']), ('docs', head))

    def test_cli_creates_absent_nested_report_parent_for_both_modes(self):
        self.write('README.md', '# Changed\n')
        self.git('add', '-A')
        head = self.merge()
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        for mode in ('scope', 'validate'):
            with self.subTest(mode=mode):
                report = self.repo / mode / 'ci-docs' / 'report.json'
                self.assertFalse(report.parent.exists())
                args = ['--scope', '--github-output', str(self.repo/'output')] if mode == 'scope' else [
                    '--validate', '--repository', 'owner/repo', '--pr', '7', '--phase', 'postmerge']
                result = subprocess.run([sys.executable, '-m', 'task_tower.ci_docs', *args, '--report', str(report)],
                                        cwd=self.repo, env=env, timeout=30, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['head'], head)

    def test_relative_child_repository_is_resolved_once(self):
        parent = self.repo
        child = parent / 'child'
        child.mkdir()
        self.repo = child
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.write('README.md', '# Child\n')
        self.commit()
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.write('README.md', '# Child changed\n')
        self.git('add', '-A')
        head = self.merge()
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        result = subprocess.run([sys.executable, '-c',
                                 "import json; from task_tower.ci_docs import classify; print(json.dumps(classify('child')))"],
                                cwd=parent, env=env, timeout=30, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.decode('utf-8'))
        self.assertEqual((report['mode'], report['head']), ('docs', head))

    def test_local_git_children_strip_github_tokens_case_insensitively(self):
        self.write('README.md', '# Changed\n')
        self.git('add', '-A')
        self.merge()
        api = self.api()
        with patch.dict(os.environ, {'Gh_ToKeN': 'fixture-secret', 'github_token': 'fixture-secret',
                                     'CI_DOCS_TEST_MARKER': 'retained'}):
            with patch.object(api, 'run_command', wraps=api.run_command) as run:
                self.assertEqual(api.classify(self.repo)['mode'], 'docs')
        self.assertTrue(run.call_args_list)
        for call in run.call_args_list:
            env = call.kwargs['env']
            self.assertFalse({'GH_TOKEN', 'GITHUB_TOKEN'} & {key.upper() for key in env})
            self.assertEqual(env['CI_DOCS_TEST_MARKER'], 'retained')


class ParserResourceTests(unittest.TestCase):
    @staticmethod
    def source(text, remaining=lambda: None):
        return SimpleNamespace(
            git=lambda *args: b'100644 blob ' + b'a'*40 + b'\tREADME.md\0',
            blob=lambda oid: text, remaining=remaining)

    def test_deadline_interrupts_scans_even_when_no_links_are_yielded(self):
        from task_tower import ci_docs
        for text in ('[r]: <\n'*256, '`x` '*1024, 'plain text '*1024):
            with self.subTest(prefix=text[:12]):
                calls = 0

                def budget():
                    nonlocal calls
                    calls += 1
                    if calls >= 20:
                        raise ci_docs.DocumentationError('fake_deadline')

                with self.assertRaisesRegex(ci_docs.DocumentationError, 'fake_deadline'):
                    ci_docs._broken(self.source(text, budget), 'a'*40)
                self.assertEqual(calls, 20)

    def test_missing_deep_target_does_not_allocate_all_ancestor_prefixes(self):
        from task_tower import ci_docs
        destination = 'a/'*800 + 'missing.md'
        source = self.source('[missing](' + destination + ')\n')
        tracemalloc.start()
        try:
            broken, count = ci_docs._broken(source, 'a'*40)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual((broken, count), ({('README.md', destination)}, 1))
        self.assertLess(peak, 256*1024, 'missing target allocated quadratic ancestor prefixes')

    def test_deadline_is_checked_inside_an_unterminated_destination(self):
        from task_tower import ci_docs
        calls = 0

        def budget():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ci_docs.DocumentationError('scan_deadline')

        with self.assertRaisesRegex(ci_docs.DocumentationError, 'scan_deadline'):
            ci_docs._destination('<' + 'a'*2048, 0, False, budget)
        self.assertEqual(calls, 3)

    def test_explicit_parser_limits_refuse_instead_of_dropping_input(self):
        from task_tower import ci_docs
        cases = (('MAX_PARSER_ITEMS', 4, '`x` '*8),
                 ('MAX_MARKDOWN_LINE_CHARS', 32, 'a'*33),
                 ('MAX_DESTINATION_CHARS', 32, '[x](' + 'a'*33 + ')'),
                 ('MAX_PATH_CHARS', 32, '[x](a' + '/..'*12 + '/target)'))
        for name, limit, text in cases:
            with self.subTest(limit=name), patch.object(ci_docs, name, limit):
                with self.assertRaises(ci_docs.DocumentationError):
                    ci_docs._broken(self.source(text), 'a'*40)

    def test_existing_deep_target_refuses_before_ancestor_walk(self):
        from task_tower import ci_docs
        target = 'a/'*10 + 'target'
        source = self.source('[x](' + target + ')')
        original_git = source.git
        source.git = lambda *args: original_git(*args) + (
            b'100644 blob ' + b'b'*40 + b'\t' + target.encode('utf-8') + b'\0')
        with patch.object(ci_docs, 'MAX_ANCESTOR_DEPTH', 4):
            with self.assertRaisesRegex(ci_docs.DocumentationError, 'ancestor_depth_limit'):
                ci_docs._broken(source, 'a'*40)


if __name__ == '__main__':
    unittest.main()
