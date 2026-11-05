"""Fixed unittest runner observations; host supervision supplies process facts.

This file is exposed read-only by the qualified execution capability. Candidate
Python shares its interpreter: observations are reviewed evidence, not a proof
against arbitrary monkeypatching. No commands are accepted from task prose.
"""
import json
from pathlib import Path
import sys
import unittest

MAX_REPORT = 16 * 1024 * 1024
MAX_CASES = 100000


def validate(value, invocation, source_pin, selection, check_cancel=lambda: None):
    """Validate observations, not the semantics of candidate Python."""
    import re
    fields = {'schema', 'kind', 'invocation', 'source_manifest_sha256', 'selection',
        'discovered_ids', 'started_ids', 'stopped_ids', 'outcomes', 'tests_run',
        'failures', 'errors', 'skips', 'expected_failures', 'unexpected_successes', 'successful'}
    def require(ok):
        if not ok:
            raise ValueError('invalid_runtime_observations')
    check_cancel()
    require(type(value) is dict and set(value) == fields)
    require(type(value['schema']) is int and value['schema'] == 1
        and value['kind'] == 'runner.observations' and value['invocation'] == invocation
        and value['source_manifest_sha256'] == source_pin and value['selection'] == list(selection))
    for key in ('discovered_ids', 'started_ids', 'stopped_ids'):
        ids = value[key]
        require(type(ids) is list and len(ids) <= MAX_CASES
            and all(type(i) is str and 0 < len(i) <= 2048 for i in ids)
            and len(set(ids)) == len(ids))
    discovered, started = value['discovered_ids'], value['started_ids']
    discovered_set, started_set = set(discovered), set(started)
    require(bool(discovered) and bool(started) and value['stopped_ids'] == started
        and started_set <= discovered_set)
    for key in ('tests_run', 'failures', 'errors', 'skips', 'expected_failures', 'unexpected_successes'):
        require(type(value[key]) is int and 0 <= value[key] <= MAX_CASES)
    require(value['tests_run'] == len(started) and type(value['successful']) is bool)
    outcomes = value['outcomes']
    require(type(outcomes) is list and len(outcomes) <= MAX_CASES)
    kinds = {'success', 'failure', 'error', 'skip', 'expected_failure',
        'unexpected_success', 'subtest_failure', 'subtest_error', 'subtest_skip', 'subtest_success'}
    excluded = discovered_set - started_set
    fixture_owners, observed, primary_counts = set(), set(), {}
    substantive = False
    for row in outcomes:
        check_cancel()
        require(type(row) is dict and set(row) == {'kind', 'id'}
            and type(row['kind']) is str and row['kind'] in kinds
            and type(row['id']) is str and len(row['id']) <= 2048)
        if row['id'] in started_set:
            observed.add(row['id'])
            if row['kind'] not in {'skip', 'subtest_skip'}:
                substantive = True
            if not row['kind'].startswith('subtest_'):
                primary_counts[row['id']] = primary_counts.get(row['id'], 0)+1
                require(primary_counts[row['id']]<=1)
        else:
            fixture = re.fullmatch(r'(setUpClass|tearDownClass|setUpModule|tearDownModule) \(([A-Za-z_][A-Za-z0-9_.]*)\)', row['id'])
            require(fixture is not None and row['kind'] in {'error', 'skip'})
            if fixture.group(1) in {'setUpClass', 'setUpModule'}:
                fixture_owners.add(fixture.group(2))
    for identity in excluded:
        check_cancel()
        parts=identity.split('.')
        require(len(parts)<=128 and any('.'.join(parts[:i]) in fixture_owners for i in range(1,len(parts))))
    require(observed == started_set and substantive)
    counts = lambda *ks: sum(row['kind'] in ks for row in outcomes)
    require(value['failures'] == counts('failure', 'subtest_failure')
        and value['errors'] == counts('error', 'subtest_error')
        and value['skips'] == counts('skip', 'subtest_skip') and value['expected_failures'] == counts('expected_failure')
        and value['unexpected_successes'] == counts('unexpected_success')
        and value['successful'] == (value['failures'] == value['errors'] == value['unexpected_successes'] == 0))
    check_cancel()
    return dict(excluded_ids=sorted(excluded), exclusion_basis='observed unittest setup fixture error/skip')


def inventory(suite):
    values = []
    def visit(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                visit(child)
        elif isinstance(item, unittest.TestCase):
            name = item.id()
            if not isinstance(name, str) or not 0 < len(name) <= 2048:
                raise ValueError('invalid_test_identity')
            values.append(name)
            if len(values) > MAX_CASES:
                raise ValueError('test_inventory_overflow')
        else:
            raise ValueError('unsupported_test_object')
    visit(suite)
    if len(set(values)) != len(values):
        raise ValueError('duplicate_test_identity')
    return values


class ObservedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids, self.stopped_ids, self.outcomes = [], [], []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.stopped_ids.append(test.id())
        super().stopTest(test)

    def _observe(self, kind, test):
        self.outcomes.append(dict(kind=kind, id=test.id()))
        if len(self.outcomes) > MAX_CASES:
            raise ValueError('test_outcomes_overflow')

    def addSuccess(self, test):
        self._observe('success', test)
        super().addSuccess(test)

    def addFailure(self, test, error):
        self._observe('failure', test)
        super().addFailure(test, error)

    def addError(self, test, error):
        self._observe('error', test)
        super().addError(test, error)

    def addSkip(self, test, reason):
        if isinstance(test, unittest.case._SubTest):
            self._observe('subtest_skip', test.test_case)
        else:
            self._observe('skip', test)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, error):
        self._observe('expected_failure', test)
        super().addExpectedFailure(test, error)

    def addUnexpectedSuccess(self, test):
        self._observe('unexpected_success', test)
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, error):
        if error is not None:
            self._observe('subtest_failure' if issubclass(error[0], test.failureException) else 'subtest_error', test)
        else:
            self._observe('subtest_success', test)
        super().addSubTest(test, subtest, error)


def main(argv=None):
    output, invocation, source_pin, raw_selection = sys.argv[1:] if argv is None else argv
    selection = json.loads(raw_selection)
    # -I keeps ambient Python startup paths out; explicitly expose this exact
    # disposable checkout for standard unittest imports/discovery.
    sys.path.insert(0, str(Path.cwd()))
    observed = {}
    class Runner(unittest.TextTestRunner):
        def __init__(self, **kwargs):
            super().__init__(resultclass=ObservedResult, **kwargs)
        def run(self, suite):
            ids = inventory(suite)
            result = super().run(suite)  # Execute original objects/load_tests.
            observed.update(schema=1, kind='runner.observations', invocation=invocation,
                source_manifest_sha256=source_pin, selection=selection,
                discovered_ids=ids, started_ids=result.started_ids,
                stopped_ids=result.stopped_ids, outcomes=result.outcomes,
                tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skips=len(result.skipped), expected_failures=len(result.expectedFailures),
                unexpected_successes=len(result.unexpectedSuccesses), successful=result.wasSuccessful())
            return result
    program = unittest.TestProgram(module=None, argv=['unittest', *selection],
        testLoader=unittest.TestLoader(), testRunner=Runner, exit=False)
    raw = json.dumps(observed, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > MAX_REPORT:
        raise ValueError('test_report_overflow')
    with Path(output).open('xb') as stream:
        stream.write(raw)
    if not program.result.wasSuccessful():
        return 1
    return 0 if program.result.testsRun else 5


if __name__ == '__main__':
    raise SystemExit(main())
