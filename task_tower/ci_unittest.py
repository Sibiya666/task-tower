"""Complete, deterministic unittest shards with fail-closed aggregation.

The serial unittest entry point remains supported. This helper changes only
CI scheduling; manifests supplement actual job outcomes, never replace them.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest


def _coordinates(index, count):
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError('Invalid shard count')
    if type(index) is not int or not 0 <= index < count:
        raise ValueError('Invalid shard index')


def _ids(values):
    if (not isinstance(values, list) or not values
            or any(not isinstance(value, str) or not value for value in values)
            or len(set(values)) != len(values) or values != sorted(values)):
        raise ValueError('Malformed or duplicate discovery identities')
    return values


def _costs(values):
    if (not isinstance(values, dict)
            or any(not isinstance(key, str) or not key
                   or type(cost) is not int or not 1 <= cost <= 86400
                   for key, cost in values.items())):
        raise ValueError('Invalid unittest cost hints')
    return values


def load_costs():
    def unique_keys(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError('Duplicate unittest cost identity')
            values[key] = value
        return values

    path = Path(__file__).with_name('ci_unittest_costs.json')
    return _costs(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_keys))


def schedule(ids, count, costs):
    _coordinates(0, count)
    if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
        raise ValueError('Malformed discovery identities')
    _ids(sorted(ids))
    _costs(costs)
    groups, loads = [[] for _ in range(count)], [0] * count
    for identity in sorted(ids, key=lambda value: (-costs.get(value, 1), value)):
        index = min(range(count), key=lambda value: (loads[value], value))
        groups[index].append(identity)
        loads[index] += costs.get(identity, 1)
    return [sorted(group) for group in groups]


def discover(start_directory):
    loader = unittest.TestLoader()
    suite = loader.discover(str(start_directory))
    if loader.errors:
        raise ValueError('Test discovery failed: ' + '\n'.join(loader.errors))
    return suite


def partition(suite, index, count):
    _coordinates(index, count)
    leaves = []

    def visit(value):
        if isinstance(value, unittest.TestSuite):
            for member in value:
                visit(member)
        elif isinstance(value, unittest.TestCase):
            if isinstance(value, unittest.loader._FailedTest):
                raise ValueError('Failed discovery cannot be partitioned')
            leaves.append(value)
        else:
            raise ValueError('Unsupported discovery member')

    # TestSuite is deliberately required: arbitrary iterables or reconstructed
    # dotted names could bypass load_tests exclusions and fixture semantics.
    if not isinstance(suite, unittest.TestSuite):
        raise ValueError('Expected a discovered unittest suite')
    visit(suite)
    if any(not isinstance(case.id(), str) or not case.id() for case in leaves):
        raise ValueError('Malformed discovery identity')
    leaves.sort(key=lambda case: case.id())
    ids = _ids([case.id() for case in leaves])
    selected = set(schedule(ids, count, load_costs())[index])
    return leaves, [case for case in leaves if case.id() in selected]


def verify(manifests, source_sha, count):
    _coordinates(0, count)
    if not isinstance(source_sha, str) or not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('Invalid source revision')
    if not isinstance(manifests, list) or len(manifests) != count:
        raise ValueError('Missing or extra shard manifests')
    inventory, indices, selected = None, set(), []
    costs, prescribed = load_costs(), None
    for row in manifests:
        if not isinstance(row, dict):
            raise ValueError('Malformed shard manifest')
        index = row.get('index')
        _coordinates(index, count)
        if (type(row.get('version')) is not int or row['version'] != 2
                or row.get('schedule') != 'duration-balanced-v1' or type(row.get('count')) is not int
                or row['count'] != count or row.get('source_sha') != source_sha
                or row.get('mode') != 'execution' or row.get('successful') is not True
                or index in indices):
            raise ValueError('Failed, repeated, stale or inventory-only shard')
        ids = _ids(row.get('all_ids'))
        if inventory is None:
            inventory = ids
            prescribed = schedule(ids, count, costs)
        if ids != inventory or row.get('selected_ids') != prescribed[index]:
            raise ValueError('Shard discovery or selection drift')
        indices.add(index)
        selected.extend(row['selected_ids'])
    if indices != set(range(count)) or sorted(selected) != inventory:
        raise ValueError('Incomplete test coverage')


def revision():
    value = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                    stderr=subprocess.PIPE, timeout=10).decode('ascii').strip()
    if not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('Invalid checkout revision')
    return value


class _TimedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations = []

    def startTest(self, test):
        self._case_started = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.durations.append(dict(id=test.id(), seconds=time.perf_counter()-self._case_started))
        super().stopTest(test)


def _write(path, value):
    if path is not None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-directory', default='tests')
    parser.add_argument('--count', type=int, default=4)
    parser.add_argument('--index', type=int)
    parser.add_argument('--manifest')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--verify', metavar='MANIFEST_DIRECTORY')
    args = parser.parse_args(argv)
    try:
        sha = revision()
        if args.verify:
            if args.index is not None or args.list or args.manifest:
                raise ValueError('Verification cannot execute or inventory a shard')
            files = sorted(Path(args.verify).glob('shard-*.json'))
            manifests = [json.loads(path.read_text(encoding='utf-8')) for path in files]
            verify(manifests, sha, args.count)
            all_cases, _ = partition(discover(args.start_directory), 0, 1)
            if manifests[0]['all_ids'] != [case.id() for case in all_cases]:
                raise ValueError('Manifests omit tests from the actual checkout discovery')
            print('All shard inventories and execution results match the exact checkout')
            return 0
        suite = discover(args.start_directory)
        all_cases, selected = partition(suite, args.index, args.count)
        ids = [case.id() for case in all_cases]
        manifest = dict(version=2, schedule='duration-balanced-v1', source_sha=sha,
                        count=args.count, index=args.index,
                        all_ids=ids, selected_ids=[case.id() for case in selected],
                        inventory_sha256=hashlib.sha256(json.dumps(ids).encode('utf-8')).hexdigest(),
                        mode='inventory' if args.list else 'execution', successful=None)
        _write(args.manifest, manifest)
        if args.list:
            print(json.dumps(manifest))
            return 0
        result = unittest.TextTestRunner(verbosity=2, resultclass=_TimedResult).run(unittest.TestSuite(selected))
        manifest.update(successful=result.wasSuccessful(), tests_run=result.testsRun,
                        failures=len(result.failures), errors=len(result.errors),
                        skips=len(result.skipped), durations=result.durations)
        _write(args.manifest, manifest)
        return 0 if result.wasSuccessful() else 1
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('CI unittest verification failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
