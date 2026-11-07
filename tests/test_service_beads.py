"""Native boundary fixtures; real store/HTTP tests consume this external double."""
import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

from task_tower.service.beads import Beads, ServiceError

class NativeFixture:
    def __init__(self):
        self.rows = {}
        self.calls = []
        self.before_claim = None
        self.fail_at = None

    def __call__(self, argv, cwd, timeout, env):
        self.calls.append(list(argv))
        args = argv[argv.index('--actor') + 2:]
        actor = argv[argv.index('--actor') + 1]
        op = args[0]
        if self.fail_at == op:
            raise RuntimeError('private failure')
        if op == 'ready':
            return copy.deepcopy([r for r in self.rows.values() if r['status'] == 'open'
                and not r.get('assignee') and not any(self.rows[d]['status'] != 'closed'
                for d in r.get('requires', []))])
        if op == 'show':
            r = copy.deepcopy(self.rows[args[1]])
            r['dependencies'] = [dict(self.rows[d], dependency_type='blocks') for d in r.get('requires', [])]
            return [r]
        if op == 'create':
            bead = args[args.index('--id')+1]
            if bead in self.rows: raise RuntimeError('already exists')
            r = dict(id=bead, title=args[args.index('--title')+1],
                     description=args[args.index('--description')+1], status='deferred',
                     defer_until='9999-12-31T00:00:00Z', requires=[])
            self.rows[bead] = r
            return copy.deepcopy(r)
        if op == 'dep':
            self.rows[args[2]]['requires'].append(args[3])
            return {'status': 'success'}
        r = self.rows[args[1]]
        if op == 'close':
            if r.get('assignee') != actor: raise RuntimeError('owner conflict')
            r['status'] = 'closed'
        elif '--claim' in args:
            if self.before_claim: self.before_claim()
            if r.get('assignee') and r['assignee'] != actor: raise RuntimeError('owner conflict')
            r.update(status='in_progress', assignee=actor)
        else:
            r.update(status='open', defer_until=None)
        return copy.deepcopy(r)


class BeadsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.native = NativeFixture()
        self.native.rows = {'pilot-a': dict(id='pilot-a', title='A', status='open'),
                            'pilot-b': dict(id='pilot-b', title='B', status='open', requires=['pilot-a'])}
        self.beads = Beads(Path(self.tmp.name)/'bd', {'p': Path(self.tmp.name)}, runner=self.native)

    def test_dependency_blocks_ready_and_native_claim_readback(self):
        self.assertEqual([r['id'] for r in self.beads.ready('p')], ['pilot-a'])
        with self.assertRaises(ServiceError): self.beads.claim('p', 'pilot-b', 'worker')
        r = self.beads.claim('p', 'pilot-a', 'worker')
        self.assertEqual((r['status'], r['assignee']), ('in_progress', 'worker'))
        self.assertEqual(self.beads.show('p', 'pilot-a')['assignee'], 'worker')

    def test_foreign_owner_preserved_without_claim_effect(self):
        self.native.rows['pilot-a'].update(status='in_progress', assignee='foreign')
        with self.assertRaises(ServiceError): self.beads.claim('p', 'pilot-a', 'worker')
        self.assertEqual(self.native.rows['pilot-a']['assignee'], 'foreign')
        self.assertFalse(any('--claim' in c for c in self.native.calls))

    def test_unknown_project_or_option_injection_stops_before_native(self):
        for project, bead, actor in [('other', 'pilot-a', 'worker'), ('p', '--force', 'worker'),
                                     ('p', 'pilot-a', '--force')]:
            with self.assertRaises(ServiceError): self.beads.claim(project, bead, actor)
        self.assertEqual(self.native.calls, [])

    def test_child_environment_strips_credentials_and_db_overrides(self):
        import os
        from unittest.mock import patch
        seen = {}
        def capture(argv,cwd,timeout,env): seen.update(env); return []
        with patch.dict(os.environ, {'gH_tOkEn':'secret','GitHub_Token':'secret','BD_DB':'elsewhere'}):
            Beads(Path(self.tmp.name)/'bd', {'p':Path(self.tmp.name)},runner=capture).ready('p')
        self.assertNotIn('BD_DB', seen)
        self.assertFalse(any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in seen))

    def test_close_requires_actual_owner_and_native_readback(self):
        with self.assertRaises(ServiceError): self.beads.close('p','pilot-a','worker','accepted')
        self.beads.claim('p','pilot-a','worker')
        self.assertEqual(self.beads.close('p','pilot-a','worker','accepted')['status'],'closed')

    def test_dependency_changes_during_claim_never_returns_execution_authority(self):
        self.native.rows['pilot-a']['requires']=['pilot-b']
        self.native.rows['pilot-b']['status']='closed'
        self.native.rows['pilot-b']['requires']=[]
        def race():self.native.rows['pilot-b']['status']='open'
        self.native.before_claim=race
        with self.assertRaises(ServiceError):self.beads.claim('p','pilot-a','worker')
        self.assertEqual(self.native.rows['pilot-a']['assignee'],'worker')

    def test_production_runner_bounds_json_and_cleanup(self):
        import sys
        from task_tower.service.beads import native_runner
        self.assertEqual(native_runner([sys.executable,'-I','-S','-c',
            'print("[{\\"id\\":\\"pilot-a\\"}]")'],Path(self.tmp.name),2,{}),[{'id':'pilot-a'}])
        for script in ['print("x"*1100000)','import time;time.sleep(5)','print("{bad json}")']:
            with self.assertRaises(ServiceError):native_runner([sys.executable,'-I','-S','-c',script],Path(self.tmp.name),.2,{})
