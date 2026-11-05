"""One contained synthetic Windows experiment; never runtime acceptance.

Only this file's bounded JSON may be uploaded. Original native assertions and
deadlines remain in the fixed test. Wall minus thread CPU cannot distinguish
blocked I/O from descheduling/GIL contention; process CPU is context only.
"""
import argparse
from contextlib import contextmanager, ExitStack
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from task_tower import pipeline, pipeline_journal, processes
from task_tower.executor_profiles import child_environment

CASE = 'tests.test_pipeline_watch.WatchTests.test_real_dispatch_adapter_to_six_roles_and_host_tests'
LIMIT = 65536
LIMITATION = 'Wrapper clocks include overhead; wall minus thread CPU does not identify I/O versus descheduling or GIL contention; process CPU is context only.'
_NUMBERS = ('sequence', 'wall', 'thread_cpu', 'process_cpu', 'safe_count',
            'safe_wall', 'safe_thread_cpu', 'safe_process_cpu', 'lstat_count',
            'lstat_wall', 'lstat_thread_cpu', 'lstat_process_cpu',
            'lstat_max_wall', 'lstat_max_thread_cpu', 'lstat_max_process_cpu',
            'preconnect_wall', 'preconnect_thread_cpu', 'preconnect_process_cpu',
            'outside_safe_preconnect_wall', 'outside_safe_preconnect_thread_cpu',
            'outside_safe_preconnect_process_cpu', 'remaining_before_safe',
            'remaining_after_safe', 'remaining_preconnect')
_BOOLS = ('failed', 'connected', 'wait_failed_before_connect')


def _clock():
    # High-resolution elapsed clock; original deadline calculations still use
    # their untouched monotonic clock, sampled independently by _remaining.
    return time.perf_counter(), time.thread_time(), time.process_time()


def _delta(start):
    return tuple(max(0, end - begin) for begin, end in zip(start, _clock()))


def _owner(value):
    if type(value) is str and len(value) == 36:
        try:
            if str(uuid.UUID(value)) == value:
                return value
        except ValueError:
            pass
    return None


class PreconnectObservation:
    """Passive same-thread phases; no lock is held over an original call."""
    def __init__(self, fixture_root=None):
        self.root = Path(fixture_root).absolute() if fixture_root is not None else None
        self.local = threading.local()
        self.lock = threading.Lock()
        self.sequences = {}
        self.records = []
        self.omitted_records = self.omitted_hosts = self.observation_errors = 0
        self.callbacks = 0

    def _observe(self, function, *args):
        try:
            return function(*args)
        except Exception:
            with self.lock:
                self.observation_errors += 1

    def _begin(self, host):
        if self.root is not None and not Path(host.journal.path).absolute().is_relative_to(self.root):
            return None
        identity = id(host)
        with self.lock:
            if identity not in self.sequences and len(self.sequences) >= 32:
                self.omitted_hosts += 1
                return None
            sequence = self.sequences[identity] = self.sequences.get(identity, 0) + 1
            self.callbacks += 1
        record = dict.fromkeys(_NUMBERS, 0)
        for key in ('preconnect_wall', 'preconnect_thread_cpu', 'preconnect_process_cpu',
                    'outside_safe_preconnect_wall', 'outside_safe_preconnect_thread_cpu',
                    'outside_safe_preconnect_process_cpu', 'remaining_before_safe',
                    'remaining_after_safe', 'remaining_preconnect'):
            record[key] = None
        record.update(dict.fromkeys(_BOOLS, False))
        record.update(owner_id=_owner(host.owner), sequence=sequence)
        return dict(record=record, journal=host.journal, start=_clock(), in_safe=False)

    def callback(self, original, host):
        previous = getattr(self.local, 'context', None)
        context = self._observe(self._begin, host)
        self.local.context = context
        try:
            return original(host)
        except BaseException:
            if context is not None:
                context['record']['failed'] = True
            raise
        finally:
            if context is not None:
                self._observe(self._finish, context)
            self.local.context = previous

    def _finish(self, context):
        record = context['record']
        for key, value in zip(('wall', 'thread_cpu', 'process_cpu'), _delta(context['start'])):
            record[key] = value
        with self.lock:
            self.records.append(record)
            if len(self.records) > 64:
                # Keep failing calls first, then the slowest calls, in bounded space.
                loser = min(range(len(self.records)), key=lambda i: (
                    self.records[i]['failed'], self.records[i]['wall']))
                self.records.pop(loser)
                self.omitted_records += 1

    def _context(self, journal=None):
        context = getattr(self.local, 'context', None)
        if context is not None and (journal is None or context['journal'] is journal):
            return context
        return None

    @staticmethod
    def _remaining(journal):
        deadline = getattr(journal, '_operation_deadline', None)
        return deadline - time.monotonic() if type(deadline) in (int, float) else None

    def safe(self, original, journal, *args, **kwargs):
        context = self._context(journal)
        if context is None:
            return original(journal, *args, **kwargs)
        record, started = context['record'], _clock()
        record['safe_count'] += 1
        record['remaining_before_safe'] = self._remaining(journal)
        previous = context['in_safe']
        context['in_safe'] = True
        try:
            return original(journal, *args, **kwargs)
        finally:
            context['in_safe'] = previous
            self._observe(self._safe_end, context, started)

    def _safe_end(self, context, started):
        for key, value in zip(('safe_wall', 'safe_thread_cpu', 'safe_process_cpu'), _delta(started)):
            context['record'][key] += value
        context['record']['remaining_after_safe'] = self._remaining(context['journal'])

    def preconnect(self, journal, failed_wait=False):
        context = self._context(journal)
        if context is None or context['in_safe'] or context['record']['connected']:
            return
        record = context['record']
        for suffix, value in zip(('wall', 'thread_cpu', 'process_cpu'), _delta(context['start'])):
            record['preconnect_' + suffix] = value
            record['outside_safe_preconnect_' + suffix] = max(0, value - record['safe_' + suffix])
        record['remaining_preconnect'] = self._remaining(journal)
        record['wait_failed_before_connect'] = failed_wait
        record['connected'] = not failed_wait

    def _lstat_end(self, context, started):
        record = context['record']
        record['lstat_count'] += 1
        for suffix, value in zip(('wall', 'thread_cpu', 'process_cpu'), _delta(started)):
            record['lstat_' + suffix] += value
            record['lstat_max_' + suffix] = max(record['lstat_max_' + suffix], value)

    @contextmanager
    def installed(self):
        original_cancel = pipeline._Host.cancelled
        original_safe = pipeline_journal.PipelineJournal._safe
        original_wait = pipeline_journal.PipelineJournal._wait_seconds
        original_connect = pipeline_journal.sqlite3.connect
        original_lstat = Path.lstat
        def cancelled(host):
            return self.callback(original_cancel, host)
        def safe(journal, *args, **kwargs):
            return self.safe(original_safe, journal, *args, **kwargs)
        def wait(journal, *args, **kwargs):
            try:
                return original_wait(journal, *args, **kwargs)
            except BaseException:
                self._observe(self.preconnect, journal, True)
                raise
        def connect(*args, **kwargs):
            context = self._context()
            if context is not None:
                self._observe(self.preconnect, context['journal'])
            return original_connect(*args, **kwargs)
        def lstat(path, *args, **kwargs):
            context = self._context()
            if context is None:
                return original_lstat(path, *args, **kwargs)
            started = _clock()
            try:
                return original_lstat(path, *args, **kwargs)
            finally:
                self._observe(self._lstat_end, context, started)
        with ExitStack() as stack:
            for target, name, replacement in (
                    (pipeline._Host, 'cancelled', cancelled),
                    (pipeline_journal.PipelineJournal, '_safe', safe),
                    (pipeline_journal.PipelineJournal, '_wait_seconds', wait),
                    (pipeline_journal.sqlite3, 'connect', connect), (Path, 'lstat', lstat)):
                stack.enter_context(patch.object(target, name, replacement))
            yield self

    def report(self):
        with self.lock:
            report = dict(records=sorted((dict(r) for r in self.records), key=lambda r: r['sequence']),
                          callbacks=self.callbacks, omitted_records=self.omitted_records,
                          omitted_hosts=self.omitted_hosts, observation_errors=self.observation_errors)
        # Byte bound as well as count bound; prioritize slow/failing calls here too.
        while len(encode_report(report)) > LIMIT - 4096:
            loser = min(range(len(report['records'])), key=lambda i: (
                report['records'][i]['failed'], report['records'][i]['wall']))
            report['records'].pop(loser)
            report['omitted_records'] += 1
        return report


def encode_report(report):
    return json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('ascii')


class ScalarResult(unittest.TestResult):
    """Do not call unittest's traceback/exception/skip prose formatter."""
    def __init__(self):
        super().__init__()
        self.counts = dict(failures=0, errors=0, skipped=0, unexpected_successes=0)
    def addError(self, test, err):
        self.counts['errors'] += 1
    def addFailure(self, test, err):
        self.counts['failures'] += 1
    def addSkip(self, test, reason):
        self.counts['skipped'] += 1
    def addUnexpectedSuccess(self, test):
        self.counts['unexpected_successes'] += 1
    def addExpectedFailure(self, test, err):
        self.counts['failures'] += 1
    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.counts['failures' if issubclass(err[0], test.failureException) else 'errors'] += 1
    def scalars(self):
        return dict(tests_run=self.testsRun, **self.counts)


def _valid_child(child):
    if type(child) is not dict or set(child) != {
            'case', 'tests_run', 'failures', 'errors', 'skipped', 'unexpected_successes', 'observation'}:
        return False
    if child['case'] != CASE or any(type(child[k]) is not int or not 0 <= child[k] <= 1000
                                  for k in ('tests_run', 'failures', 'errors', 'skipped', 'unexpected_successes')):
        return False
    observation = child['observation']
    if type(observation) is not dict or set(observation) != {
            'records', 'callbacks', 'omitted_records', 'omitted_hosts', 'observation_errors'}:
        return False
    if any(type(observation[k]) is not int or not 0 <= observation[k] < 2**53
           for k in ('callbacks', 'omitted_records', 'omitted_hosts', 'observation_errors')):
        return False
    records = observation['records']
    if type(records) is not list or len(records) > 64:
        return False
    for record in records:
        if type(record) is not dict or set(record) != set(_NUMBERS + _BOOLS + ('owner_id',)):
            return False
        if record['owner_id'] is not None and _owner(record['owner_id']) is None:
            return False
        if any(type(record[k]) is not bool for k in _BOOLS):
            return False
        if any(record[k] is not None and (type(record[k]) not in (int, float)
               or not math.isfinite(record[k]) or abs(record[k]) >= 2**53) for k in _NUMBERS):
            return False
    return len(encode_report(child)) <= LIMIT - 2048


def receipt_passed(process, child):
    if not _valid_child(child):
        return False
    return (process.get('status') == 'passed' and process.get('exit_code') == 0
            and process.get('started') is True and process.get('cleanup_confirmed') is True
            and process.get('stdout_tail_unknown') is False and process.get('stderr_tail_unknown') is False
            and child['tests_run'] == 1 and not any(child[k] for k in (
                'failures', 'errors', 'skipped', 'unexpected_successes'))
            and child['observation']['callbacks'] > 0 and bool(child['observation']['records'])
            and any(r['owner_id'] is not None and r['preconnect_wall'] is not None
                    for r in child['observation']['records'])
            and child['observation']['observation_errors'] == 0)


def _child(output):
    from tests.test_pipeline_watch import WatchTests
    original_setup = WatchTests.setUp
    observer = PreconnectObservation()
    def setup(case):
        original_setup(case)
        observer.root = Path(case.root).absolute()
        context = observer.installed()
        context.__enter__()
        case.addCleanup(context.__exit__, None, None, None)
    result = ScalarResult()
    with patch.object(WatchTests, 'setUp', setup):
        unittest.TestSuite([WatchTests(CASE.rsplit('.', 1)[1])]).run(result)
    child = dict(case=CASE, observation=observer.report(), **result.scalars())
    output.write_bytes(encode_report(child))
    return 0 if child['tests_run'] == 1 and not any(result.counts.values()) else 1


def _process_facts(process):
    facts = {}
    status = process.get('status')
    facts['status'] = status if status in {'passed', 'failed', 'timeout', 'unavailable', 'unknown', 'cancelled', 'cleanup_failed'} else 'unknown'
    for key in ('started', 'cleanup_confirmed', 'stdout_tail_unknown', 'stderr_tail_unknown'):
        facts[key] = process.get(key) if type(process.get(key)) is bool else None
    for key in ('exit_code', 'duration_seconds', 'stdout_bytes', 'stderr_bytes'):
        value = process.get(key)
        facts[key] = value if type(value) in (int, float) and math.isfinite(value) and abs(value) < 2**53 else None
    return facts


def _source_sha():
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                timeout=10, encoding='utf-8', errors='strict')
        sha = result.stdout.strip()
        return sha if result.returncode == 0 and re.fullmatch('[0-9a-f]{40}', sha) else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def _output_path(value):
    root = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())).resolve()
    output = Path(value).absolute()
    if not output.resolve().is_relative_to(root) or output.resolve().is_relative_to(ROOT):
        raise ValueError('output_outside_runner_temp')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise ValueError('output_exists')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        output = _output_path(args.output)
        if args.child:
            # Internal child receipt is never an acceptance report.
            if os.environ.get('_TT_PRECONNECT_PARENT_PID') != str(os.getppid()):
                return 1
            return _child(output)
        sha = _source_sha()
        with tempfile.TemporaryDirectory(prefix='tt-preconnect-', dir=output.parent) as directory:
            child_path = Path(directory) / 'child.json'
            environment = child_environment(dict(os.environ))
            environment['_TT_PRECONNECT_PARENT_PID'] = str(os.getpid())
            try:
                process = processes.run_command(
                    [sys.executable, str(Path(__file__).resolve()), '--child', '--output', str(child_path)],
                    ROOT, 240, env=environment, cancel_requested=lambda: False)
            except Exception:
                # An absent supervisor receipt cannot prove execution/cleanup.
                process = dict(status='unknown', cleanup_confirmed=False)
            child = None
            try:
                with child_path.open('rb') as stream:
                    raw = stream.read(LIMIT + 1)
                candidate = json.loads(raw) if len(raw) <= LIMIT else None
                if _valid_child(candidate):
                    child = candidate
            except (OSError, ValueError, UnicodeError):
                pass
            facts = _process_facts(process)
            passed = sha is not None and receipt_passed(facts, child)
            report = dict(version=1, kind='synthetic.preconnect_diagnostic', source_sha=sha,
                          passed=passed, process=facts, child=child, limitation=LIMITATION)
            output.write_bytes(encode_report(report))
            return 0 if passed else 1
    except Exception:
        # Never print exception prose, paths, environment or native output.
        return 1


if __name__ == '__main__':
    sys.exit(main())
