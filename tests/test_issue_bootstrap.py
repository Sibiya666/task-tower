import unittest
from task_tower.issue_bootstrap import validate_connections
class BootstrapTests(unittest.TestCase):
    def test_unconfigured_installations_remain_opt_in(self):
        self.assertEqual(validate_connections({}, {"p":{}}),{})
    def test_private_bindings_cannot_select_model_or_arbitrary_executable_commands(self):
        for value in [{"p":{"model":"x"}},{"foreign":{}},{"p":{"command":"echo unsafe"}}]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_connections(value,{"p":{}})

    def test_core_policy_import_does_not_require_receiver_package_files(self):
        import os,subprocess,sys,tempfile
        from pathlib import Path
        from task_tower.child_environment import child_environment
        source=Path(__file__).resolve().parent.parent/"task_tower/issue_intake.py"
        with tempfile.TemporaryDirectory() as temp:
            copied=Path(temp)/"issue_intake.py";copied.write_bytes(source.read_bytes())
            result=subprocess.run([sys.executable,"-I","-B","-c","import runpy,sys; runpy.run_path(sys.argv[1])",str(copied)],capture_output=True,encoding="utf-8",timeout=10,env=child_environment(os.environ))
            self.assertEqual(result.returncode,0,result.stderr)
