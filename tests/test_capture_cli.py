import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import capture_cli
from test_capture import envelope
from task_tower.project_connections import ProjectConnection


class CaptureCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.connection=ProjectConnection('p','o/r',self.root,'runner')
        self.base=['--connections',str(self.root/'connections.json'),'--project','p']

    def test_explicit_file_delegates_and_invalid_input_does_not(self):
        path=self.root/'input.json'; path.write_bytes(json.dumps(envelope()).encode())
        with patch.object(capture_cli,'load_connections',return_value=[self.connection]), patch.object(capture_cli,'capture',return_value={'status':'captured','issue_url':'https://github.com/o/r/issues/1'}) as call, patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(capture_cli.run(self.base+['submit','--input',str(path)]),0)
            self.assertEqual(call.call_args.args[1]['original_text'],'Original\r\nтекст')
            for data in (b'\xff', b'a'*65537, b'{"version":1}'):
                path.write_bytes(data)
                with patch('sys.stderr',new_callable=io.StringIO): self.assertEqual(capture_cli.run(self.base+['submit','--input',str(path)]),2)
            self.assertEqual(call.call_count,1)

    def test_only_explicit_stdin_is_read(self):
        with patch.object(capture_cli,'load_connections',return_value=[self.connection]), patch.object(capture_cli,'capture',return_value={'status':'captured'}), patch('sys.stdin',io.TextIOWrapper(io.BytesIO(json.dumps(envelope()).encode()))), patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(capture_cli.run(self.base+['submit','--input','-']),0)

    def test_hardlinked_input_rejected(self):
        import os
        path=self.root/'input.json'; path.write_text(json.dumps(envelope()))
        alias=self.root/'alias.json'; os.link(path,alias)
        with patch.object(capture_cli,'load_connections',return_value=[self.connection]), patch.object(capture_cli,'capture') as call, patch('sys.stderr',new_callable=io.StringIO):
            self.assertEqual(capture_cli.run(self.base+['submit','--input',str(alias)]),2)
            call.assert_not_called()
