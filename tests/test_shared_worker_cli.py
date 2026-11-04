"""CLI bounds and visible ownership without executing a harness."""
import contextlib
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_shared_queue import Server
from task_tower.shared_queue import SharedQueue
from task_tower.shared_worker import main


class SharedWorkerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.source=self.root/'source';self.source.mkdir()
        self.server=Server();self.addCleanup(self.server.close);self.store=self.server.store()
        self.config=self.root/'worker.json';self.connections=self.root/'connections.json'
        self.connections.write_text('{}')
        self.settings=dict(version=1,repository='owner/repo',worker_id=str(uuid.uuid4()),worker_name='worker-1',
            assignee='operator',workspace_root=str(self.root/'worker'),superpowers_root=str(self.root/'skills'),
            harness={},allowlist=[dict(repository='owner/repo',issue=1,task_id='TT-SHARED-1')],plans={'1':'docs/plan.md'})
        self.config.write_text(json.dumps(self.settings))
        self.connection=SimpleNamespace(repository='owner/repo',checkout=self.source)

    def invoke(self,command,*extra):
        output=io.StringIO()
        with patch('task_tower.project_connections.load_connections',return_value=[self.connection]),\
                patch('task_tower.github_tasks.GitHubTasks',return_value=self.store),\
                patch('task_tower.shared_worker.native_execution_supported',return_value=True),contextlib.redirect_stdout(output):
            status=main([command,'--connections',str(self.connections),'--config',str(self.config),*extra])
        return status,[json.loads(line) for line in output.getvalue().splitlines()]

    def test_status_reports_unclaimed_then_actual_claim_owner(self):
        status,rows=self.invoke('status');self.assertEqual(status,0)
        self.assertEqual(rows[0]['tasks'][0]['state'],'unclaimed')
        queue=SharedQueue(self.store,self.settings['worker_id'],allowlist=self.settings['allowlist'],assignee='operator')
        self.assertIsNotNone(queue.claim(1))
        status,rows=self.invoke('status');self.assertEqual(status,0)
        self.assertEqual(rows[0]['tasks'][0]['worker_id'],self.settings['worker_id'])
        self.assertEqual(rows[0]['tasks'][0]['state'],'claimed')

    def test_duplicate_keys_fail_without_disclosing_private_settings(self):
        self.config.write_text('{"version":1,"version":1,"private":"sensitive-value"}')
        status,rows=self.invoke('status');self.assertEqual(status,2)
        self.assertEqual(rows,[dict(status='needs_input',reason='shared_worker_unavailable')])

    def test_once_processes_one_result_without_refill(self):
        with patch('task_tower.shared_worker.SharedWorker') as worker:
            worker.return_value.run_once.return_value=dict(issue=1,state='awaiting_acceptance')
            status,rows=self.invoke('run','--once')
            self.assertEqual(status,0);self.assertEqual(len(rows),1)
            self.assertEqual(worker.return_value.run_once.call_count,1)

    def test_private_config_inside_checkout_is_rejected(self):
        config=self.source/'worker.json';config.write_bytes(self.config.read_bytes());self.config=config
        status,rows=self.invoke('status');self.assertEqual(status,2)
        self.assertEqual(rows[0]['status'],'needs_input')

    def test_unsupported_run_rejects_before_loading_connections(self):
        output=io.StringIO()
        with patch('task_tower.shared_worker.native_execution_supported',return_value=False,create=True),\
                patch('task_tower.project_connections.load_connections') as load,contextlib.redirect_stdout(output):
            status=main(['run','--connections','missing.json','--config','missing-worker.json'])
        self.assertEqual(status,2);load.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['reason'],'unsupported_platform')
