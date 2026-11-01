import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

from task_tower.dispatch_selection import collect_snapshot, select_ready, load_dispatch_config


def issue(n, **fields):
    meta = dict(version=1, kind='task', mode='autonomous', status='open', task_id=f'TT-{n}')
    meta.update(fields)
    return dict(number=n, state='open', body='private prose', meta=meta)


class Store:
    def __init__(self, rows): self.rows = rows
    def list_issues(self): return copy.deepcopy(self.rows)
    def metadata(self, row):
        if row.get('malformed'): raise ValueError('secret')
        return row['meta']
    def get(self, n): return copy.deepcopy(next(r for r in self.rows if r['number'] == n))
    def request(self, method, path): return []


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.checkout = Path(self.temp.name).resolve() / 'checkout'
        self.checkout.mkdir()
        self.a = SimpleNamespace(repository='Owner/Repo', checkout=self.checkout, runner_label='trusted')
        self.b = SimpleNamespace(repository='Other/Repo', checkout=self.checkout, runner_label='other')
    def snapshot(self, rows, other=None):
        stores = {'owner/repo': Store(rows), 'other/repo': Store(other or [])}
        return collect_snapshot([self.a, self.b], store_factory=lambda c: stores[c.repository.casefold()], source_factory=lambda c: object())
    def select(self, rows, other=None, verify=lambda *args: True):
        allow = [dict(repository='owner/repo', issue=r['number'], task_id=f"TT-{r['number']}") for r in rows if type(r.get('number')) is int]
        return select_ready(self.snapshot(rows, other), allow, verify_done=verify)
    def test_ready_order_defaults_and_no_prose(self):
        result = self.select([issue(3), issue(2, priority='P0'), issue(1, priority='P1')])
        self.assertEqual([r['issue'] for r in result['ready']], [2, 1, 3])
        self.assertEqual(result['ready'][-1]['priority'], 'P3')
        self.assertNotIn('private prose', json.dumps(result))
    def test_strict_metadata_gates_and_aliases(self):
        changes = [dict(mode='manual'), dict(kind='idea'), dict(status='blocked'), dict(priority='P4'), dict(id='TT-OTHER'), dict(task_id=None), dict(legacy_id=True)]
        for change in changes:
            with self.subTest(change=change): self.assertEqual(self.select([issue(1, **change)])['ready'], [])
        row = issue(1); row['state'] = 'closed'
        self.assertEqual(self.select([row])['ready'], [])
    def test_lifecycle_and_individual_malformed_isolation(self):
        bad=issue(1); bad['malformed']=True
        self.assertEqual([r['issue'] for r in self.select([bad, issue(2)])['ready']], [2])
        snapshot=self.snapshot([issue(1)])
        snapshot['owner/repo']['store'].request=lambda *a: [{'id':1,'body':'<!-- task-tower:lifecycle:v1\n{"status":"in_progress"}\n-->'}]
        self.assertFalse(select_ready(snapshot,[dict(repository='owner/repo',issue=1,task_id='TT-1')],verify_done=lambda *a:True)['ready'])
    def test_remote_attempt_in_body_or_comment_prevents_stale_open_dispatch(self):
        attempts=[{'status':status} for status in ('queued','running','reviewed','done','needs_input')]
        attempts += [None, [], {}, {'status':True}, {'status':'unexpected'}]
        auth=[dict(repository='owner/repo',issue=1,task_id='TT-1')]
        for attempt in attempts:
            with self.subTest(attempt=attempt,source='body'):
                self.assertFalse(self.select([issue(1,remote_attempt=attempt)])['ready'])
            with self.subTest(attempt=attempt,source='comment'):
                snapshot=self.snapshot([issue(1)])
                body='<!-- task-tower:lifecycle:v1\n'+json.dumps({'remote_attempt':attempt})+'\n-->'
                snapshot['owner/repo']['store'].request=lambda *a: [{'id':1,'body':body}]
                self.assertFalse(select_ready(snapshot,auth,verify_done=lambda *a:True)['ready'])

    def test_dependencies_both_forms_and_fresh_proofs(self):
        rows=[issue(1,blocked_by=['Other/Repo#9']), issue(2,blocked_by=['owner/repo#3'],blocked_by_task_ids=['TT-3']),issue(3,status='done')]
        calls=[]
        result=self.select(rows,[issue(9,status='done')],verify=lambda c,s,src,i: calls.append((c.repository,i['number'])) or True)
        self.assertEqual([r['issue'] for r in result['ready']],[1,2])
        self.assertEqual(set(calls),{('Other/Repo',9),('Owner/Repo',3)})
        self.assertFalse(self.select([issue(1,blocked_by=['other/repo#9'])],[issue(9,status='done')],verify=lambda *a:False)['ready'])
        self.select(rows,[issue(9,status='done')],verify=lambda *a: calls.append(1) or True)
        self.assertEqual(len(calls),4)
    def test_invalid_dependencies(self):
        for fields in [dict(blocked_by=['owner/repo#1']),dict(blocked_by=['TT-2']),dict(blocked_by=['missing/repo#2']),dict(blocked_by=['owner/repo#2']*2),dict(blocked_by_task_ids=['TT-MISSING']),dict(blocked_by=['owner/repo#2'],blocked_by_task_ids=[]),dict(blocked_by=True)]:
            with self.subTest(fields=fields): self.assertFalse(self.select([issue(1,**fields),issue(2,status='done')])['ready'])
    def test_duplicate_identity_blocks_source_not_other_project(self):
        snapshot=self.snapshot([issue(1),issue(1)],[issue(7)])
        result=select_ready(snapshot,[dict(repository='owner/repo',issue=1,task_id='TT-1'),dict(repository='other/repo',issue=7,task_id='TT-7')],verify_done=lambda *a:True)
        self.assertEqual([r['repository'] for r in result['ready']],['other/repo'])
    def test_duplicate_task_ids_cannot_resolve(self):
        self.assertFalse(self.select([issue(1,blocked_by_task_ids=['TT-2']),issue(2,status='done'),issue(3,task_id='TT-2')])['ready'])
    def test_source_failure_and_cross_project_consumers_isolated(self):
        snapshot=self.snapshot([issue(1,blocked_by=['other/repo#9']),issue(2)],[issue(9)])
        snapshot['other/repo'].update(error='source_unavailable',index={})
        result=select_ready(snapshot,[dict(repository='owner/repo',issue=n,task_id=f'TT-{n}') for n in (1,2)],verify_done=lambda *a:True)
        self.assertEqual([r['issue'] for r in result['ready']],[2])
    def test_fresh_dependency_malformed_metadata_cannot_prove(self):
        snapshot=self.snapshot([issue(1,blocked_by=['owner/repo#2']),issue(2,status='done')])
        snapshot['owner/repo']['store'].get=lambda n: dict(issue(n),malformed=True)
        result=select_ready(snapshot,[dict(repository='owner/repo',issue=1,task_id='TT-1')],verify_done=lambda *a:True)
        self.assertFalse(result['ready'])
    def test_config_rejects_ambiguous_task_authority(self):
        path=Path(self.temp.name)/'private.json'
        path.write_text(json.dumps(dict(version=1,allowlist=[dict(repository='owner/repo',issue=n,task_id='TT-SAME') for n in (1,2)])))
        with self.assertRaises(ValueError): load_dispatch_config(path,[self.a])
    def test_config_defaults_and_strict_validation(self):
        path=Path(self.temp.name)/'private.json'
        def load(value):
            path.write_text(json.dumps(value),encoding='utf-8')
            return load_dispatch_config(path,[self.a])
        self.assertEqual(load({'version':1})['allowlist'],[])
        valid=dict(repository='OWNER/REPO',issue=1,task_id='TT-1')
        self.assertEqual(load(dict(version=1,allowlist=[valid]))['allowlist'][0]['repository'],'owner/repo')
        for value in [dict(version=True),dict(version=1,extra=1),dict(version=1,allowlist=[dict(valid,issue=True)]),dict(version=1,allowlist=[valid,valid]),dict(version=1,allowlist=[dict(valid,repository='x/y')]),dict(version=1,interval_seconds=4)]:
            with self.subTest(value=value),self.assertRaises(ValueError): load(value)
        with self.assertRaises(ValueError):
            load({'version':1,'backend':{'argv':['cmd.bat'],'cwd':str(self.checkout),'timeout_seconds':2}})
        unsafe=self.checkout/'config.json'; unsafe.write_text('{"version":1}')
        with self.assertRaises(ValueError): load_dispatch_config(unsafe,[self.a])

if __name__ == '__main__': unittest.main()
