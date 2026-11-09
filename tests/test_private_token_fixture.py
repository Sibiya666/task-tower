import os
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(os.name=='nt','Windows native DACL fixture')
class PrivateTokenFixtureTests(unittest.TestCase):
    def test_new_file_is_owner_only_protected_and_never_overwrites(self):
        from tests.fixtures.private_token import provision,security,current_sid
        from task_tower.service.cli import read_token
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'token'
            provision(path,'a'*40)
            self.assertEqual(read_token(path),'a'*40)
            self.assertEqual(security(path),(current_sid(),True,[current_sid()]))
            with self.assertRaises(OSError):provision(path,'b'*40)
            self.assertEqual(path.read_text(encoding='ascii'),'a'*40)

    def test_failed_write_removes_only_its_new_disposable_file(self):
        from tests.fixtures.private_token import provision
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'token';other=Path(temp)/'other';other.write_text('retain',encoding='ascii')
            def failed(*args):raise OSError('write failed')
            with self.assertRaises(OSError):provision(path,'a'*40,write=failed)
            self.assertFalse(path.exists());self.assertEqual(other.read_text(encoding='ascii'),'retain')
