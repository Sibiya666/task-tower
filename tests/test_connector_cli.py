"""Operator commands use real bounded HTTP; native effects stay disposable."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from task_tower.connector import cli
from task_tower.service.api import make_server
from task_tower.service.store import Store, plan_digest
from tests.test_service_api import private_token
from tests.test_service_beads import Beads, NativeFixture
from tests.test_service_store import PLAN, DIGEST


class OperatorCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.native = NativeFixture()
        beads = Beads(self.root/'bd', {'p': self.root}, runner=self.native)
        self.store = Store(self.root/'service-journal', beads, approved_plans={'p': {DIGEST}})
        self.addCleanup(self.store.close)
        self.server = make_server(self.store, {'host1': dict(token='a'*40, projects=['p'])}, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        def stop():
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(2)
        self.addCleanup(stop)
        self.token = self.root/'token'
        private_token(self.token, 'a'*40)
        self.cfg = dict(version=1, connector_id='host1',
            endpoint='http://127.0.0.1:'+str(self.server.server_port),
            token_file=str(self.token), journal=str(self.root/'unused-journal'),
            app_server=str(self.root/'absent-codex'), assignments=[],
            projects={'p': dict(repository=str(self.root), worktree_root=str(self.root/'trees'))})
        self.config = self.root/'connector.json'
        self.config.write_text(json.dumps(self.cfg), encoding='utf-8')
        self.plan = self.root/'plan.json'
        # Pretty JSON deliberately differs from the canonical bytes being hashed.
        self.plan.write_text(json.dumps(PLAN, indent=2), encoding='utf-8')

    def invoke(self, *args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                status = cli.main([*args, '--config', str(self.config)])
            except SystemExit as error:
                status = error.code
        self.assertNotIn('a'*40, out.getvalue()+err.getvalue())
        self.assertFalse((self.root/'unused-journal').exists())
        self.assertFalse((self.root/'trees').exists())
        return status, out.getvalue()

    def import_args(self, **overrides):
        fields = dict(project_id='p', request_id='import-1', digest=DIGEST, plan_file=str(self.plan))
        fields.update(overrides)
        args = ['plan', 'import']
        for key, value in fields.items():
            args.extend(['--'+key.replace('_', '-'), value])
        return args

    def test_import_prints_canonical_published_batch_and_repeat_has_no_duplicate_effects(self):
        status, out = self.invoke(*self.import_args())
        self.assertEqual(status, 0)
        batch = json.loads(out)
        self.assertEqual(batch, dict(request_id='import-1', project_id='p', digest=DIGEST, state='published'))
        calls = list(self.native.calls)
        self.assertEqual(len(self.native.rows), 2)
        self.assertEqual(self.invoke(*self.import_args()), (status, out))
        self.assertEqual(self.native.calls, calls)
        self.assertFalse(any('--claim' in c or 'close' in c for c in calls))

    def test_ready_prints_only_published_dependency_ready_view_without_claim(self):
        self.store.import_plan('setup', 'p', DIGEST, PLAN)
        self.native.rows['outside-a'] = dict(id='outside-a', status='open')
        status, out = self.invoke('ready', '--project-id', 'p')
        self.assertEqual(status, 0)
        self.assertEqual([row['id'] for row in json.loads(out)], ['pilot-a'])
        self.assertFalse(any('--claim' in c for c in self.native.calls))

    def test_unapproved_matching_digest_and_foreign_service_project_fail_before_native(self):
        unapproved = copy.deepcopy(PLAN)
        unapproved['tasks'][0]['title'] = 'Not approved'
        self.plan.write_text(json.dumps(unapproved), encoding='utf-8')
        self.assertNotEqual(self.invoke(*self.import_args(digest=plan_digest(unapproved)))[0], 0)
        self.cfg['projects']['foreign'] = self.cfg['projects']['p']
        self.config.write_text(json.dumps(self.cfg), encoding='utf-8')
        self.plan.write_text(json.dumps(PLAN), encoding='utf-8')
        self.assertNotEqual(self.invoke(*self.import_args(project_id='foreign'))[0], 0)
        self.assertNotEqual(self.invoke('ready', '--project-id', 'foreign')[0], 0)
        self.assertEqual(self.native.calls, [])

    def test_bad_plan_digest_identity_and_local_project_never_send_http(self):
        cases = [self.import_args(digest='0'*64), self.import_args(digest='not-sha256'),
                 self.import_args(), self.import_args(project_id='other')]
        # '=' keeps an option-like identity a value for argparse.
        index = cases[2].index('--request-id')
        cases[2][index:index+2] = ['--request-id=--invalid']
        with patch.object(cli.APIClient, 'request', side_effect=AssertionError('unexpected HTTP')) as request:
            for args in cases:
                with self.subTest(args=args):
                    self.assertNotEqual(self.invoke(*args)[0], 0)
            self.assertNotEqual(self.invoke('ready', '--project-id', 'other')[0], 0)
            request.assert_not_called()
        self.assertEqual(self.native.calls, [])

    def test_strict_utf8_json_and_file_bound_reject_locally(self):
        valid = json.dumps(PLAN).encode('utf-8')
        duplicate = b'{"tasks":[],"tasks":'+json.dumps(PLAN['tasks']).encode('utf-8')+b'}'
        for raw in (b'\xff', b'\xef\xbb\xbf'+valid, duplicate,
                    b'{"tasks":NaN}', b'{"tasks":Infinity}', valid+b' trailing',
                    valid+b' '*(65537-len(valid))):
            with self.subTest(raw=raw[:30]):
                self.plan.write_bytes(raw)
                with patch.object(cli.APIClient, 'request', side_effect=AssertionError('unexpected HTTP')) as request:
                    self.assertNotEqual(self.invoke(*self.import_args())[0], 0)
                    request.assert_not_called()
        self.assertEqual(self.native.calls, [])

    def test_encoded_body_bound_is_preserved(self):
        plan = copy.deepcopy(PLAN)
        for task in plan['tasks']:
            task['description'] = '\u0416'*6000
        raw = json.dumps(plan, ensure_ascii=False).encode('utf-8')
        self.assertLess(len(raw), 65536)
        self.plan.write_bytes(raw)
        with patch('http.client.HTTPConnection.connect', side_effect=AssertionError('oversized HTTP')) as connect:
            self.assertNotEqual(self.invoke(*self.import_args(digest=plan_digest(plan)))[0], 0)
            connect.assert_not_called()
        self.assertEqual(self.native.calls, [])

    def test_import_reconciliation_is_nonzero_and_retry_preserves_fence(self):
        self.native.fail_at = 'create'
        status, out = self.invoke(*self.import_args())
        self.assertNotEqual(status, 0)
        self.assertEqual(json.loads(out)['state'], 'needs_reconciliation')
        calls = list(self.native.calls)
        self.assertEqual(self.invoke(*self.import_args()), (status, out))
        self.assertEqual(self.native.calls, calls)

    def test_rejected_unavailable_and_nonprivate_credentials_return_nonzero(self):
        for token in ('b'*40, 'short'):
            self.token.write_text(token, encoding='ascii')
            self.assertNotEqual(self.invoke(*self.import_args())[0], 0)
            self.assertNotEqual(self.invoke('ready', '--project-id', 'p')[0], 0)
        self.token.write_text('a'*40, encoding='ascii')
        with patch.object(cli, 'read_token', side_effect=ValueError('token_not_private')):
            self.assertNotEqual(self.invoke(*self.import_args())[0], 0)
        with patch.object(cli.APIClient, 'request', side_effect=ConnectionError('unavailable')):
            self.assertNotEqual(self.invoke(*self.import_args())[0], 0)
        self.assertEqual(self.native.calls, [])
