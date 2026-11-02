"""Diagnostic only: inspect fixed fixture-owned PIDs without argv/environment."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_pipeline_watch import WatchTests


def state(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o',
                             'pid=,ppid=,stat=,lstart='],
                            capture_output=True, text=True, timeout=2)
    if result.returncode not in (0, 1):
        raise RuntimeError('bounded PID observation unavailable')
    fields = result.stdout.split()
    if not fields:
        return None
    observed = dict(pid=int(fields[0]), ppid=int(fields[1]),
                    state=fields[2], start=' '.join(fields[3:]))
    try:
        observed.update(pgid=os.getpgid(pid), sid=os.getsid(pid))
    except ProcessLookupError:
        observed['disappeared_during_observation'] = True
    if sys.platform.startswith('linux'):
        try:
            # starttime in kernel clock ticks supplies a stronger Linux identity.
            stat = Path('/proc') / str(pid) / 'stat'
            observed['start_ticks'] = stat.read_text().rsplit(')', 1)[1].split()[19]
        except FileNotFoundError:
            observed['disappeared_during_observation'] = True
    return observed


def identity(observed):
    return None if observed is None else (
        observed['pid'], observed['start'], observed.get('start_ticks'))


original = WatchTests.owned_role_with_delayed_cancel_read


def observe(self, *args, **kwargs):
    values = original(self, *args, **kwargs)
    result, run, history, outcomes, elapsed, marker = values
    pid = int(marker.read_text())
    before = state(pid)
    self.observation = dict(role_pid=pid, role_state=before,
                            host_states=[state(o['pid']) for o in outcomes if o.get('pid')],
                            outcomes=outcomes, elapsed=elapsed,
                            result=result, run=run, history=history)

    def cleanup():
        # Recheck full observed start identity before touching this fixture PID.
        current = state(pid)
        if current and before and identity(current) == identity(before):
            if current.get('pgid') == pid and current.get('sid') == pid:
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            current = state(pid)
            if not current or 'Z' in current['state']:
                return
            time.sleep(.05)
        raise AssertionError('Owned diagnostic role remains executable: ' + json.dumps(current))
    self.addCleanup(cleanup)
    return values


WatchTests.owned_role_with_delayed_cancel_read = observe


class Result(unittest.TextTestResult):
    def addFailure(self, test, err):
        def private_fixture(value):
            if isinstance(value, dict):
                return {key: private_fixture(item) for key, item in value.items()
                        if key.lower() not in ('argv', 'env', 'environment', 'gh_token', 'github_token')}
            if isinstance(value, list):
                return [private_fixture(item) for item in value]
            return value
        observation = json.dumps(private_fixture(getattr(test, 'observation', {})), sort_keys=True)
        print('FAILURE_ONLY_PRIVATE_OBSERVATION ' +
              observation.replace('fixture-env-only-private-value', '[fixture-redacted]'), flush=True)
        super().addFailure(test, err)


names = ['test_owned_role_read_beyond_one_second_retains_unknown_intent',
         'test_stop_during_validated_cancel_read_remains_bounded']
suite = unittest.TestSuite(WatchTests(name) for name in names)
result = unittest.TextTestRunner(verbosity=2, failfast=True, resultclass=Result).run(suite)
raise SystemExit(not result.wasSuccessful())
