import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import ci_unittest as ci


def cases(size=9):
    class Example(unittest.TestCase):
        def runTest(self):
            pass

        def id(self):
            return 'example.Case.test_%02d' % self.number

    result = []
    for number in range(size):
        case = Example()
        case.number = number
        result.append(case)
    return result


class PartitionTests(unittest.TestCase):
    def test_measured_costs_reduce_imbalance_and_preserve_discovered_objects(self):
        leaves = cases()
        costs = {leaves[n].id(): value for n, value in enumerate([9, 8, 7, 6, 5])}
        suite = unittest.TestSuite(reversed(leaves))
        with patch.object(ci, 'load_costs', return_value=costs, create=True):
            groups = [ci.partition(suite, index, 2)[1] for index in range(2)]
        self.assertEqual(groups, [[leaves[n] for n in (0, 3, 4)],
                                  [leaves[n] for n in (1, 2, 5, 6, 7, 8)]])
        self.assertEqual({id(case) for group in groups for case in group},
                         {id(case) for case in leaves})
        self.assertEqual(sum(map(len, groups)), 9)
        actual = max(sum(costs.get(case.id(), 1) for case in group) for group in groups)
        old = max(sum(costs.get(case.id(), 1) for case in leaves[i::2]) for i in range(2))
        self.assertLess(actual, old)

    def test_nested_discovery_objects_are_preserved_exactly_once(self):
        leaves = cases()
        suite = unittest.TestSuite([unittest.TestSuite(leaves[:3]), unittest.TestSuite(leaves[3:])])
        groups = [ci.partition(suite, index, 4)[1] for index in range(4)]
        self.assertEqual([len(group) for group in groups], [3, 2, 2, 2])
        self.assertEqual({id(case) for group in groups for case in group}, {id(case) for case in leaves})
        self.assertEqual(sum(map(len, groups)), len(leaves))
        all_cases, selected = ci.partition(unittest.TestSuite(reversed(leaves)), 0, 4)
        self.assertEqual([case.id() for case in selected], [leaves[n].id() for n in (0, 4, 8)])
        self.assertEqual(all_cases, leaves)

    def test_invalid_indices_counts_and_members_fail_before_execution(self):
        for index, count in [(True, 4), (0, False), (0, 0), (-1, 4), (4, 4), ('0', 4), (0, 1.5)]:
            with self.subTest(index=index, count=count), self.assertRaises(ValueError):
                ci.partition(unittest.TestSuite(cases()), index, count)
        for suite in [unittest.TestSuite(), [object()], [cases(1)[0], cases(1)[0]]]:
            with self.assertRaises(ValueError):
                ci.partition(suite, 0, 4)

    def test_failed_discovery_is_rejected_even_outside_selected_partition(self):
        loader = unittest.TestLoader()
        broken = loader.loadTestsFromName('a_module_that_does_not_exist_ci_fixture')
        suite = unittest.TestSuite([unittest.TestSuite(cases()), broken])
        for index in range(4):
            with self.assertRaises(ValueError):
                ci.partition(suite, index, 4)

    def test_load_tests_exclusions_are_not_rediscovered_by_name(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test_ci_load_tests_fixture.py'
            path.write_text('import unittest\nclass Fixture(unittest.TestCase):\n def test_kept(self): pass\n def test_excluded(self): raise AssertionError("excluded")\ndef load_tests(loader, tests, pattern):\n return unittest.TestSuite([Fixture("test_kept")])\n', encoding='utf-8')
            discovered = ci.discover(folder)
            all_cases, _ = ci.partition(discovered, 0, 1)
            self.assertEqual(len(all_cases), 1)
            self.assertTrue(all_cases[0].id().endswith('.test_kept'))


class CostScheduleTests(unittest.TestCase):
    def test_unknown_tests_are_included_and_obsolete_hints_add_no_tests(self):
        self.assertEqual(ci.schedule(['d', 'b', 'a', 'c'], 2, {'a': 8, 'old': 999}),
                         [['a'], ['b', 'c', 'd']])

    def test_cost_and_shard_ties_are_deterministic(self):
        self.assertEqual(ci.schedule(['e', 'c', 'a', 'd', 'b'], 2, {}),
                         [['a', 'c', 'e'], ['b', 'd']])
        self.assertEqual(ci.schedule(['b', 'd', 'a', 'c', 'e'], 2,
                                     {'a': 1, 'b': 1}),
                         [['a', 'c', 'e'], ['b', 'd']])

    def test_invalid_costs_and_discovery_identities_fail_closed(self):
        for costs in [[], None, {'a': True}, {'a': 0}, {'a': -1}, {'a': 1.5},
                      {'a': float('nan')}, {'a': float('inf')}, {'a': 86401},
                      {'': 1}, {2: 1}, {'a': '3'}]:
            with self.subTest(costs=costs), self.assertRaises(ValueError):
                ci.schedule(['a', 'b'], 2, costs)
        for ids in [[], ['a', 'a'], ['a', 2], [''], 'ab']:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                ci.schedule(ids, 2, {})
        for count in [True, 0, 65, 1.5]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                ci.schedule(['a'], count, {})

    def test_fixed_json_loader_rejects_duplicate_keys_and_malformed_hints(self):
        for raw in ['{"a":1,"a":2}', '[]', '{"a":true}', '{"a":0}',
                    '{"a":86401}', '{"a":NaN}', '{"a":Infinity}', '{', '{"":3}']:
            with self.subTest(raw=raw), patch.object(ci.Path, 'read_text', return_value=raw):
                with self.assertRaises(ValueError):
                    ci.load_costs()
        with patch.object(ci.Path, 'read_text', return_value='{"a":86400}'):
            self.assertEqual(ci.load_costs(), {'a': 86400})


class ManifestTests(unittest.TestCase):
    def good(self):
        ids = [case.id() for case in cases()]
        return [dict(version=2, schedule='duration-balanced-v1', source_sha='a'*40, count=4, index=index,
                     all_ids=ids, selected_ids=ids[index::4], mode='execution', successful=True)
                for index in range(4)]

    def test_complete_successful_execution_manifests_are_required(self):
        values = self.good()
        ci.verify(values, 'a'*40, 4)
        variants = [values[:-1], values+[values[0]]]
        for key, value in [('source_sha', 'b'*40), ('index', 0), ('count', 3),
                           ('version', True), ('version', 1), ('schedule', 'round-robin'),
                           ('successful', False), ('successful', 1), ('mode', 'inventory'),
                           ('selected_ids', []), ('all_ids', ['different'])]:
            changed = copy.deepcopy(values)
            changed[1][key] = value
            variants.append(changed)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                ci.verify(variant, 'a'*40, 4)

    def test_complete_but_wrong_weighted_assignment_cannot_pass(self):
        ids = ['a', 'b', 'c', 'd']
        rows = [dict(version=2, schedule='duration-balanced-v1', source_sha='a'*40,
                     count=2, index=i, all_ids=ids, selected_ids=group,
                     mode='execution', successful=True)
                for i, group in enumerate([['a'], ['b', 'c', 'd']])]
        with patch.object(ci, 'load_costs', return_value={'a': 8}):
            ci.verify(rows, 'a'*40, 2)
            wrong = copy.deepcopy(rows)
            wrong[0]['selected_ids'], wrong[1]['selected_ids'] = ['a', 'c'], ['b', 'd']
            with self.assertRaises(ValueError):
                ci.verify(wrong, 'a'*40, 2)

    def test_duplicate_inventory_ids_and_malformed_revision_fail_closed(self):
        values = self.good()
        for row in values:
            row['all_ids'].append(row['all_ids'][0])
        with self.assertRaises(ValueError):
            ci.verify(values, 'a'*40, 4)
        with self.assertRaises(ValueError):
            ci.verify(self.good(), 'not-a-commit', 4)


class RunnerTests(unittest.TestCase):
    def invoke(self, folder, *args):
        with patch.object(ci, 'revision', return_value='a'*40), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return ci.main(['--start-directory', str(folder), '--count', '1', '--index', '0', *args])

    def test_fixture_lifecycle_and_inventory_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root/'executed'
            (root/'test_ci_lifecycle_fixture.py').write_text('import unittest\nfrom pathlib import Path\nclass Fixture(unittest.TestCase):\n @classmethod\n def setUpClass(cls): cls.calls=[]\n def setUp(self): self.calls.append("setup")\n def test_one(self): self.calls.append("method")\n def tearDown(self): self.calls.append("teardown")\n @classmethod\n def tearDownClass(cls): Path('+repr(str(marker))+').write_text(",".join(cls.calls))\n', encoding='utf-8')
            manifest = root/'result.json'
            self.assertEqual(self.invoke(folder, '--list', '--manifest', str(manifest)), 0)
            self.assertFalse(marker.exists())
            self.assertEqual(json.loads(manifest.read_text(encoding='utf-8'))['mode'], 'inventory')
            self.assertEqual(self.invoke(folder, '--manifest', str(manifest)), 0)
            self.assertEqual(marker.read_text(), 'setup,method,teardown')
            value = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(value['version'], 2)
            self.assertEqual(value['schedule'], 'duration-balanced-v1')
            self.assertIs(value['successful'], True)
            self.assertEqual(value['tests_run'], 1)
            self.assertEqual(len(value['durations']), 1)

    def test_balanced_multi_module_class_fixtures_skips_and_exclusions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root/'events'
            for suffix in ('a', 'b'):
                name = 'test_ci_balanced_fixture_' + suffix
                source = '''import unittest
from pathlib import Path
def record(value):
 with Path(MARKER).open('a', encoding='utf-8') as f: f.write(__name__+':'+value+'\\n')
def setUpModule(): record('module-setup')
def tearDownModule(): record('module-teardown')
class A(unittest.TestCase):
 @classmethod
 def setUpClass(cls): record(cls.__name__+'-setup')
 @classmethod
 def tearDownClass(cls): record(cls.__name__+'-teardown')
 def setUp(self): record(self.id()+':setup')
 def tearDown(self): record(self.id()+':teardown')
 def test_one(self): record(self.id()+':body')
 def test_two(self):
  record(self.id()+':body')
  if __name__.endswith('_b') and type(self).__name__=='B': self.skipTest('real skip')
 def test_excluded(self): raise AssertionError('excluded by load_tests')
class B(A): pass
def load_tests(loader, tests, pattern):
 return unittest.TestSuite(cls(method) for cls in (A,B) for method in ('test_one','test_two'))
'''.replace('MARKER', repr(str(marker)))
                (root/(name+'.py')).write_text(source, encoding='utf-8')
            costs = {f'test_ci_balanced_fixture_{module}.{cls}.test_one': cost
                     for module, cls, cost in [('a', 'A', 9), ('a', 'B', 8),
                                               ('b', 'A', 7), ('b', 'B', 6)]}
            rows = []
            for index in range(2):
                manifest = root/f'shard-{index}.json'
                with patch.object(ci, 'revision', return_value='a'*40), \
                        patch.object(ci, 'load_costs', return_value=costs), \
                        contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(ci.main(['--start-directory', folder, '--count', '2',
                                              '--index', str(index), '--manifest', str(manifest)]), 0)
                rows.append(json.loads(manifest.read_text(encoding='utf-8')))
            with patch.object(ci, 'load_costs', return_value=costs):
                ci.verify(rows, 'a'*40, 2)
            self.assertEqual(sum(row['tests_run'] for row in rows), 8)
            self.assertEqual(sum(row['skips'] for row in rows), 1)
            events = marker.read_text(encoding='utf-8').splitlines()
            for module in ('a', 'b'):
                prefix = 'test_ci_balanced_fixture_' + module
                self.assertEqual(events.count(prefix+':module-setup'), 2)
                self.assertEqual(events.count(prefix+':module-teardown'), 2)
                for cls in ('A', 'B'):
                    fixture_count = 1 if module == 'a' else 2
                    for phase in ('setup', 'teardown'):
                        self.assertEqual(events.count(prefix+':'+cls+'-'+phase), fixture_count)
                    for method in ('test_one', 'test_two'):
                        for phase in ('setup', 'body', 'teardown'):
                            self.assertEqual(events.count(prefix+':'+prefix+'.'+cls+'.'+method+':'+phase), 1)
            self.assertFalse(any('excluded' in identity for row in rows for identity in row['all_ids']))

    def test_failed_or_error_tests_propagate_nonzero_but_normal_skip_passes(self):
        for body, expected in [('self.fail("expected")', 1), ('raise RuntimeError("expected")', 1), ('self.skipTest("expected")', 0)]:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                name = 'test_ci_outcome_fixture_'+str(expected)+'_'+str(len(body))
                (root/(name+'.py')).write_text('import unittest\nclass Fixture(unittest.TestCase):\n def test_outcome(self): '+body+'\n', encoding='utf-8')
                self.assertEqual(self.invoke(folder), expected)

    def test_import_failure_is_not_hidden_by_a_partition(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'test_ci_import_error_fixture.py').write_text('raise RuntimeError("broken import")', encoding='utf-8')
            self.assertNotEqual(self.invoke(folder), 0)

    def test_aggregate_rejects_consistent_manifests_omitting_real_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'test_ci_full_inventory_fixture.py').write_text('import unittest\nclass Fixture(unittest.TestCase):\n def test_one(self): pass\n def test_two(self): pass\n', encoding='utf-8')
            directory = root/'manifests'
            directory.mkdir()
            ids = ['test_ci_full_inventory_fixture.Fixture.test_one']
            (directory/'shard-0.json').write_text(json.dumps(dict(version=2, schedule='duration-balanced-v1', source_sha='a'*40, count=1, index=0, all_ids=ids, selected_ids=ids, mode='execution', successful=True)), encoding='utf-8')
            with patch.object(ci, 'revision', return_value='a'*40), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(ci.main(['--start-directory', folder, '--count', '1', '--verify', str(directory)]), 0)


if __name__ == '__main__':
    unittest.main()
