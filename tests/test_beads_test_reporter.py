"""Runner observations retain real unittest discovery/fixture behavior."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from task_tower import beads_test_reporter as reporter
from task_tower.processes import run_command


class ReporterTests(unittest.TestCase):
    def test_isolated_passing_and_skipped_subtests_are_not_all_skipped(self):
        result,value=self.run_fixture('''import unittest
class Real(unittest.TestCase):
 def test_subtest(self):
  with self.subTest(part=1): self.skipTest('synthetic')
  with self.subTest(part=2): self.assertTrue(True)
''')
        self.assertEqual(result['exit_code'],0)
        reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])
        self.assertEqual(value['tests_run'],1)
        self.assertIn(dict(kind='subtest_success',id='test_observed.Real.test_subtest'),value['outcomes'])

    def run_fixture(self, source):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); project=root/'project';project.mkdir()
            (project/'tests').mkdir();(project/'tests'/'__init__.py').write_bytes(b'')
            (project/'tests'/'test_observed.py').write_text(source,encoding='utf-8')
            capture=root/'capture';capture.mkdir();output=root/'report.json'
            result=run_command([sys.executable,'-I','-B',reporter.__file__,str(output),'fixed-invocation','a'*64,
                json.dumps(['discover','-s','tests','-v'])],project,30,
                cancel_requested=threading.Event().is_set,capture=dict(directory=capture,max_bytes_per_stream=1048576))
            self.assertTrue(result['cleanup_confirmed'])
            self.assertFalse(result['stdout_tail_unknown']);self.assertFalse(result['stderr_tail_unknown'])
            value=json.loads(output.read_bytes())
            return result,value

    def test_original_load_tests_objects_and_exclusions_are_preserved(self):
        result,value=self.run_fixture('''import unittest
class Real(unittest.TestCase):
 def test_included(self): self.assertEqual(2+2,4)
 def test_excluded(self): self.fail('load_tests excludes this')
def load_tests(loader,suite,pattern): return unittest.TestSuite([Real('test_included')])
''')
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(value['discovered_ids'],['test_observed.Real.test_included'])
        self.assertEqual(value['tests_run'],1)
        self.assertEqual(reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])['excluded_ids'],[])

    def test_setup_class_skip_has_explicit_fixture_exclusion(self):
        result,value=self.run_fixture('''import unittest
class Ready(unittest.TestCase):
 def test_real(self): self.assertTrue(True)
class Skipped(unittest.TestCase):
 @classmethod
 def setUpClass(cls): raise unittest.SkipTest('synthetic fixture exclusion')
 def test_not_started(self): self.fail('must skip')
''')
        self.assertEqual(result['exit_code'],0)
        excluded=reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])
        self.assertEqual(value['tests_run'],1);self.assertEqual(value['skips'],1)
        self.assertEqual(excluded['excluded_ids'],['test_observed.Skipped.test_not_started'])

    def test_setup_error_and_subtest_failure_remain_failure_evidence(self):
        result,value=self.run_fixture('''import unittest
class Failed(unittest.TestCase):
 def test_subtest(self):
  with self.subTest(number=1): self.assertEqual(1,2)
class Broken(unittest.TestCase):
 @classmethod
 def setUpClass(cls): raise ValueError('synthetic fixture')
 def test_not_started(self): pass
''')
        self.assertEqual(result['exit_code'],1)
        reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])
        self.assertEqual((value['failures'],value['errors']),(1,1))

    def test_missing_duplicate_unknown_or_inconsistent_coverage_is_refused(self):
        _,value=self.run_fixture('import unittest\nclass Real(unittest.TestCase):\n def test_ok(self): pass\n')
        variants=[]
        for key,replacement in [('started_ids',[]),('stopped_ids',[]),('tests_run',0),
            ('discovered_ids',value['discovered_ids']*2),('outcomes',[dict(kind='success',id='unknown')]),
            ('invocation','another'),('source_manifest_sha256','b'*64),('selection',[])]:
            wrong=copy.deepcopy(value);wrong[key]=replacement;variants.append(wrong)
        for wrong in variants:
            with self.subTest(changed=wrong),self.assertRaises(ValueError):
                reporter.validate(wrong,'fixed-invocation','a'*64,['discover','-s','tests','-v'])

    def test_expected_failure_and_subtest_skip_are_retained(self):
        result,value=self.run_fixture('''import unittest
class Real(unittest.TestCase):
 @unittest.expectedFailure
 def test_expected(self): self.assertEqual(1,2)
 def test_subtest(self):
  with self.subTest(part=1): self.skipTest('synthetic')
  with self.subTest(part=2): self.assertTrue(True)
''')
        self.assertEqual(result['exit_code'],0)
        reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])
        self.assertEqual((value['skips'],value['expected_failures']),(1,1))

    def test_all_skips_do_not_supply_meaningful_test_coverage(self):
        result,value=self.run_fixture('import unittest\n@unittest.skip("synthetic")\nclass Real(unittest.TestCase):\n def test_skip(self): pass\n')
        self.assertEqual(result['exit_code'],0)
        with self.assertRaises(ValueError):reporter.validate(value,'fixed-invocation','a'*64,['discover','-s','tests','-v'])


if __name__=='__main__':
    unittest.main()
