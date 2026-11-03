"""A genuine invalid image must return without an interactive OS error box."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from task_tower.processes import run_command
from task_tower.executor_profiles import child_environment


@unittest.skipUnless(os.name=='nt','Windows native image-launch behavior')
class WindowsImageLaunchTests(unittest.TestCase):
    def test_invalid_image_has_confirmed_no_launch_without_a_system_dialog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();image=root/'invalid-image.exe';image.write_bytes(b'Not an executable.\n')
            capture=root/'capture';capture.mkdir()
            code='import json;from task_tower.processes import run_command;print(json.dumps(run_command(['+repr(str(image))+'],'+repr(str(root))+',2,capture=dict(directory='+repr(str(root))+',max_bytes_per_stream=4096))))'
            env=child_environment(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
            # Outer deadline contains even an OS call blocked before inner
            # process creation. Neither probe changes the process error mode.
            result=run_command([sys.executable,'-B','-c',code],root,5,env=env,
                capture=dict(directory=capture,max_bytes_per_stream=4096))
            self.assertTrue(result['cleanup_confirmed']);self.assertEqual(result['status'],'passed')
            value=json.loads((capture/'stdout.log').read_text())
            self.assertEqual(value['status'],'unavailable');self.assertFalse(value['started'])
            self.assertIsNone(value['pid']);self.assertIsNone(value['exit_code']);self.assertTrue(value['cleanup_confirmed'])
