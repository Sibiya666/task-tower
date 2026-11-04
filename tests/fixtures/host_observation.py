"""Bounded, passive diagnostics for synthetic parent pipeline hosts only.

Install before constructing hosts. No files are read here; parsed results are
copied before normal close. A callback's row comes from its original status
call, never a second database read. This helper owns no execution or cleanup.
"""
import builtins
import json
import math
from pathlib import Path
import re
import threading
import time
import uuid
from unittest.mock import patch

from task_tower import pipeline


_ENUMS = {
    'kind': {'_action', '_dispatch'},
    'state': pipeline.STATES,
    'status': pipeline.STATES | {'idle', 'unavailable', 'passed', 'failed', 'timeout', 'cleanup_failed'},
    'reason': pipeline.REASONS,
    'stage': {'spec', 'development', 'test'},
}
_BOOLS = {'cleanup_confirmed', 'started', 'cancel_requested', 'operational_failure', 'read_failure'}
_NUMBERS = {'exit_code', 'pid', 'owner_pid', 'generation', 'process_count', 'version'}
_UUIDS = {'run_id', 'owner_id'}
_TIMES = {'updated_at', 'deadline_at', 'started_at', 'finished_at', 'created_at'}
_HASHES = {'input_sha256', 'receipt_sha256', 'effect_sha256'}
_ERROR_TYPES = {getattr(builtins, name): name for name in (
    'ValueError', 'OSError', 'KeyError', 'TypeError', 'AttributeError',
    'RuntimeError', 'TimeoutError', 'PermissionError', 'FileNotFoundError',
    'AssertionError', 'KeyboardInterrupt', 'SystemExit')}


def _scalars(value):
    """Fixed fields and bounded values; never format arbitrary objects/prose."""
    if type(value) is not dict:
        return None
    result = {}
    for key in _ENUMS.keys() | _BOOLS | _NUMBERS | _UUIDS | _TIMES | _HASHES:
        if key not in value:
            continue
        item = value[key]
        if item is None:
            result[key] = None
        elif key in _ENUMS and type(item) is str and len(item) <= 64 and item in _ENUMS[key]:
            result[key] = item
        elif key in _BOOLS and type(item) is bool:
            result[key] = item
        elif key in _NUMBERS and type(item) is int and abs(item) <= 2**63 - 1:
            result[key] = item
        elif key in _UUIDS and type(item) is str and len(item) == 36:
            try:
                if str(uuid.UUID(item)) == item:
                    result[key] = item
            except ValueError:
                pass
        elif key in _HASHES and type(item) is str and len(item) == 64 and re.fullmatch('[a-f0-9]{64}', item):
            result[key] = item
        elif key in _TIMES and type(item) is str and len(item) <= 40 and re.fullmatch(
                r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)', item):
            result[key] = item
    return result


def _number(value):
    return value if type(value) in (float, int) and math.isfinite(value) and abs(value) < 1e15 else None


class _LazyMessage:
    def __init__(self, observation, journal):
        self.observation, self.journal = observation, journal

    def __str__(self):
        return self.observation.message(self.journal)


class HostObservation:
    def __init__(self, fixture_root):
        self.root = Path(fixture_root).resolve()
        self._lock = threading.Lock()
        self._local = threading.local()
        self._scope = object()
        self._hosts = {}  # At most 32 host objects, not an unbounded identity set.
        self._errors = []
        self._shutdowns = []
        self._omitted_hosts = self._omitted_errors = self._omitted_shutdowns = 0
        self._patches = []
        self._active = False
        self._observation_errors = 0

    def _within(self, path):
        return Path(path).resolve().is_relative_to(self.root)

    def _observe(self, function, *args):
        # Diagnostic bookkeeping must never replace a product return/exception.
        try:
            function(*args)
        except Exception:
            with self._lock:
                self._observation_errors += 1

    def _register(self, host, args, kind):
        if not self._active or not self._within(args.journal):
            return
        host._fixture_observation_scope = self._scope
        with self._lock:
            if len(self._hosts) >= 32:
                self._omitted_hosts += 1
                return
            self._hosts[host] = dict(kind=kind if kind in _ENUMS['kind'] else None,
                                     outcome=None, result=None, callback_count=0)

    def _snapshot(self, host):
        if not self._active or host not in self._hosts:
            return
        # Access host flags outside the storage lock, just as original methods do.
        values = dict(owner_id=_scalars({'owner_id': getattr(host, 'owner', None)}).get('owner_id'),
                      outcome=_scalars(getattr(host, 'outcome', None)),
                      result=_scalars(getattr(host, 'result', None)),
                      stop_requested=host.stop.is_set(),
                      done=host.done.is_set(),
                      budget_deadline=_number(getattr(host, '_budget_deadline', None)))
        with self._lock:
            if host in self._hosts:
                self._hosts[host].update(values)

    def _error(self, where, error):
        if not self._active:
            return
        record = dict(where=where, type=_ERROR_TYPES.get(type(error), 'Exception'))
        with self._lock:
            if len(self._errors) < 16:
                self._errors.append(record)
            else:
                self._omitted_errors += 1

    def _callback(self, host, started, result):
        if not self._active:
            return
        duration = _number(time.monotonic() - started)
        with self._lock:
            if host in self._hosts:
                record = self._hosts[host]
                record['callback_count'] += 1
                record['callback_duration_seconds'] = duration
                record['callback_result'] = result if type(result) is bool else None

    def _row(self, host, journal, returned):
        if not self._active or journal is not host.journal or type(returned) is not dict:
            return
        # This is the exact result from the ordinary validated callback read.
        rows = returned.get('runs')
        if type(rows) is not list:
            return
        for row in rows:
            if type(row) is dict and row.get('owner_id') == host.owner:
                saved = _scalars(row)
                with self._lock:
                    if host in self._hosts:
                        self._hosts[host]['owned_run'] = saved
                return

    def _shutdown_result(self, journal, result, started):
        if not self._active or not self._within(journal.path):
            return
        record = dict(result=result if type(result) is bool else None,
                      duration_seconds=_number(time.monotonic() - started))
        with self._lock:
            if len(self._shutdowns) < 16:
                self._shutdowns.append(record)
            else:
                self._omitted_shutdowns += 1

    def __enter__(self):
        if self._active or self._patches:
            raise RuntimeError('HostObservation contexts cannot be reentered')
        observer = self
        original_init, original_run = pipeline._Host.__init__, pipeline._Host.run
        original_cancel, original_close = pipeline._Host.cancelled, pipeline._Host.close
        original_status, original_shutdown = pipeline.PipelineJournal.status, pipeline._shutdown

        def initialize(host, args, kind, timeout, stop):
            observer._observe(observer._register, host, args, kind)
            return original_init(host, args, kind, timeout, stop)

        def run(host):
            try:
                return original_run(host)
            except BaseException as error:
                if getattr(host, '_fixture_observation_scope', None) is observer._scope:
                    observer._observe(observer._error, 'run', error)
                raise
            finally:
                observer._observe(observer._snapshot, host)

        def cancelled(host):
            previous = getattr(observer._local, 'host', None)
            observer._local.host = host
            started, result = time.monotonic(), None
            try:
                result = original_cancel(host)
                return result
            except BaseException as error:
                if getattr(host, '_fixture_observation_scope', None) is observer._scope:
                    observer._observe(observer._error, 'cancelled', error)
                raise
            finally:
                observer._local.host = previous
                observer._observe(observer._callback, host, started, result)
                observer._observe(observer._snapshot, host)

        def status(journal, *args, **kwargs):
            returned = original_status(journal, *args, **kwargs)
            host = getattr(observer._local, 'host', None)
            if host is not None:
                observer._observe(observer._row, host, journal, returned)
            return returned

        def close(host):
            observer._observe(observer._snapshot, host)
            return original_close(host)

        def shutdown(config, journal, state, **kwargs):
            started = time.monotonic()
            try:
                result = original_shutdown(config, journal, state, **kwargs)
            except BaseException as error:
                try:
                    scoped = observer._within(journal.path)
                except Exception:
                    scoped = False
                if scoped:
                    observer._observe(observer._error, 'shutdown', error)
                raise
            observer._observe(observer._shutdown_result, journal, result, started)
            return result

        self._active = True
        for target, name, replacement in (
                (pipeline._Host, '__init__', initialize), (pipeline._Host, 'run', run),
                (pipeline._Host, 'cancelled', cancelled), (pipeline._Host, 'close', close),
                (pipeline.PipelineJournal, 'status', status), (pipeline, '_shutdown', shutdown)):
            hook = patch.object(target, name, replacement)
            hook.start()
            self._patches.append(hook)
        return self

    def __exit__(self, *exception):
        self._active = False
        for hook in reversed(self._patches):
            hook.stop()
        self._patches.clear()
        # In-flight wrappers keep their saved original; never wait/cancel/join.
        return False

    def lazy_message(self, journal=None):
        return _LazyMessage(self, journal)

    def message(self, journal=None):
        """Render only on assertion failure; optional current rows are labelled."""
        with self._lock:
            report = dict(hosts=[dict(row) for row in self._hosts.values()],
                          errors=list(self._errors), shutdowns=list(self._shutdowns),
                          omitted_hosts=self._omitted_hosts, omitted_errors=self._omitted_errors,
                          omitted_shutdowns=self._omitted_shutdowns,
                          observation_errors=self._observation_errors, truncated=False)
        if journal is not None:
            try:
                if not self._within(journal.path):
                    report['failure_time_journal_refused'] = True
                else:
                    returned = journal.status()
                    rows = returned.get('runs', [])
                    report['failure_time_runs'] = [_scalars(row) for row in rows[:32]]
                    report['omitted_failure_time_runs'] = max(0, len(rows) - 32)
            except Exception as error:
                report['failure_time_error_type'] = _ERROR_TYPES.get(type(error), 'Exception')
        while True:
            rendered = json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True,
                                  separators=(',', ':'))
            if len(rendered) <= 16384:
                return rendered
            report['truncated'] = True
            for records, counter in (('hosts', 'omitted_hosts'),
                                     ('failure_time_runs', 'omitted_failure_time_runs'),
                                     ('errors', 'omitted_errors'), ('shutdowns', 'omitted_shutdowns')):
                if report.get(records):
                    report[records].pop()
                    report[counter] += 1
                    break
