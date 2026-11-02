"""Native containment controls; Windows retains its existing Job tests."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from task_tower import processes, posix_scope


class ReceiptTests(unittest.TestCase):
    def test_completed_receipt_cannot_satisfy_fresh_stop_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            scope_id, nonce = str(uuid.uuid4()), str(uuid.uuid4())
            posix_scope.receipt_path(path).write_text(json.dumps(dict(
                version=1, scope_id=scope_id, pid=123, kind='completed', stop_nonce=None)))
            self.assertTrue(posix_scope.valid_receipt(path, scope_id, 123, 'completed'))
            self.assertFalse(posix_scope.valid_receipt(path, scope_id, 123, 'stopped', nonce))

    def test_stop_receipt_requires_exact_owner_and_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            scope_id, nonce = str(uuid.uuid4()), str(uuid.uuid4())
            receipt = dict(version=1, scope_id=scope_id, pid=123, kind='stopped', stop_nonce=nonce)
            posix_scope.receipt_path(path).write_text(json.dumps(receipt))
            self.assertTrue(posix_scope.valid_receipt(path, scope_id, 123, 'stopped', nonce))
            self.assertFalse(posix_scope.valid_receipt(path, scope_id, 124, 'stopped', nonce))
            self.assertFalse(posix_scope.valid_receipt(path, scope_id, 123, 'stopped', str(uuid.uuid4())))
            receipt['extra'] = 'untrusted'
            posix_scope.receipt_path(path).write_text(json.dumps(receipt))
            self.assertFalse(posix_scope.valid_receipt(path, scope_id, 123, 'stopped', nonce))


@unittest.skipUnless(os.name == 'posix', 'actual POSIX session controls')
class NativeScopeTests(unittest.TestCase):
    def run_helper(self, mode, cancel=True, expect_role_quiet=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope_id = str(uuid.uuid4())
            marker, result_path = root / 'role.json', root / 'result.json'
            fixture = Path(__file__).parent / 'fixtures' / 'posix_scope_helper.py'
            started = time.monotonic()
            outcome = processes.run_command(
                [sys.executable, str(fixture), str(root), scope_id, mode],
                Path(__file__).resolve().parents[1], 10,
                cancel_requested=lambda: cancel and marker.exists(),
                _cooperative=dict(scope_id=scope_id, result_path=result_path))
            elapsed = time.monotonic() - started
            if marker.exists():
                role = json.loads(marker.read_text())
                try:
                    self.assertFalse(role['term_blocked'])
                    from task_tower.executor_queue import _dead
                    if expect_role_quiet:
                        self.assertTrue(_dead(role['pid']), (outcome, role))
                    else:
                        self.assertFalse(outcome['cleanup_confirmed'])
                finally:
                    # Diagnostic rescue is never counted as production cleanup.
                    try:
                        current = subprocess.run(['/bin/ps', '-p', str(role['pid']), '-o', 'stat=,lstart='],
                            capture_output=True, text=True, timeout=.25)
                        fields = current.stdout.strip().split(None, 1)
                        if (len(fields) == 2 and not fields[0].startswith('Z')
                                and fields[1] == role['start'] and os.getpgid(role['pid']) == role['pid']):
                            os.killpg(role['pid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            else:
                role = None
            if outcome['started'] and outcome['cleanup_confirmed']:
                receipt = json.loads(posix_scope.receipt_path(result_path).read_text())
                nonce = None
                if cancel:
                    request = json.loads(posix_scope.request_path(result_path).read_text())
                    nonce = request['stop_nonce']
                    self.assertEqual(request['scope_id'], scope_id)
                    self.assertEqual(request['pid'], outcome['pid'])
                self.assertEqual(receipt, dict(version=1, scope_id=scope_id,
                    pid=outcome['pid'], kind='stopped' if cancel else 'completed', stop_nonce=nonce))
            if role is not None:
                time.sleep(.7)
            self.assertFalse((root / 'escaped').exists())
            self.assertFalse((root / 'unsafe-kill').exists())
            if cancel:
                self.assertFalse((root / 'after-role').exists())
            if (root / 'launched-pid').exists():
                from task_tower.executor_queue import _dead
                self.assertTrue(_dead(int((root / 'launched-pid').read_text())))
            if mode == 'worker-thread':
                self.assertTrue((root / 'worker-rejected').exists())
            if mode == 'ignored-child':
                self.assertTrue((root / 'ignored-child-rejected').exists())
            if mode == 'legacy-shape':
                legacy = json.loads((root / 'legacy-results.json').read_text())
                self.assertEqual(set(legacy['actual']), {'argv', 'status', 'exit_code',
                    'duration_seconds', 'stdout_sha256', 'stdout_bytes', 'stderr_sha256', 'stderr_bytes'})
                self.assertEqual(set(legacy['missing']), {'argv', 'status', 'exit_code', 'duration_seconds'})
                self.assertEqual(legacy['actual']['status'], 'passed')
                self.assertEqual(legacy['actual']['stdout_bytes'], len(b'private stream\n'))
                self.assertEqual(legacy['missing']['status'], 'unavailable')
            return outcome, elapsed, role

    def test_cancel_reaps_nested_capture_role_before_confirming_cleanup(self):
        outcome, elapsed, role = self.run_helper('capture')
        self.assertIsNotNone(role)
        self.assertEqual(outcome['status'], 'cancelled')
        self.assertTrue(outcome['cleanup_confirmed'])
        self.assertLess(elapsed, 5)

    def test_cancel_reaps_nested_legacy_role_before_confirming_cleanup(self):
        outcome, elapsed, role = self.run_helper('legacy')
        self.assertIsNotNone(role)
        self.assertTrue(outcome['cleanup_confirmed'])
        self.assertLess(elapsed, 5)

    def test_helper_crash_with_no_receipt_cannot_confirm_cleanup(self):
        outcome, elapsed, role = self.run_helper('crash', cancel=False)
        self.assertFalse(outcome['cleanup_confirmed'])
        self.assertEqual(outcome['status'], 'cleanup_failed')

    def test_normal_scoped_completion_has_own_receipt(self):
        outcome, elapsed, role = self.run_helper('normal', cancel=False)
        self.assertEqual(outcome['status'], 'passed')
        self.assertTrue(outcome['cleanup_confirmed'])

    def test_callback_exception_does_not_create_completion_receipt(self):
        outcome, elapsed, role = self.run_helper('callback-error', cancel=False)
        self.assertIsNotNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_stop_before_launch_does_not_invent_stop_receipt(self):
        outcome, elapsed, role = self.run_helper('before-launch', cancel=False)
        self.assertIsNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_pending_stop_after_popen_cannot_escape_registration(self):
        outcome, elapsed, role = self.run_helper('launch-signal', cancel=False)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_reaped_identity_is_never_signalled_as_owned_group(self):
        outcome, elapsed, role = self.run_helper('stolen-reap', cancel=False)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_wrong_stop_nonce_cannot_confirm_actual_quiet_child(self):
        outcome, elapsed, role = self.run_helper('wrong-stop-nonce')
        self.assertIsNotNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_crashed_helper_cannot_claim_cleanup_of_live_nested_session(self):
        outcome, elapsed, role = self.run_helper('crash-after-launch', cancel=False,
                                               expect_role_quiet=False)
        self.assertIsNotNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_helper_worker_thread_cannot_launch_unregistered_session(self):
        outcome, elapsed, role = self.run_helper('worker-thread', cancel=False)
        self.assertIsNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_ignored_sigchld_cannot_launch_without_unreaped_identity(self):
        outcome, elapsed, role = self.run_helper('ignored-child', cancel=False)
        self.assertIsNone(role)
        self.assertFalse(outcome['cleanup_confirmed'])

    def test_scoped_legacy_commands_preserve_original_public_result_shape(self):
        outcome, elapsed, role = self.run_helper('legacy-shape', cancel=False)
        self.assertTrue(outcome['cleanup_confirmed'])


if __name__ == '__main__':
    unittest.main()
