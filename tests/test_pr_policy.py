"""Strict installation policy: public task content cannot enlarge authority."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from task_tower.pr_policy import load_pr_policy, policy_fingerprint, authorized_task


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.checkout = self.root / 'checkout'; self.checkout.mkdir()
        self.path = self.root / 'policy.json'
        self.connections = (SimpleNamespace(repository='owner/repo', checkout=self.checkout,
            trusted_publishers=['operator']),)
        self.executor = {'profiles': {'review': {'repository': 'owner/repo'}},
            'allowlist': [{'repository': 'owner/repo', 'issue': 17, 'task_id': 'TT-PR-001'}]}
        self.raw = dict(version=1, executor_config=str(self.root/'executor.json'),
            pipeline_journal=str(self.root/'pipeline.sqlite3'), legacy_provenance=None,
            projects=[dict(repository='owner/repo', base_ref='refs/heads/main', publisher_account='operator',
                merge_enabled=True, exclusive_writer=dict(enabled=False, boundary_id='local-install', asserted_by='operator'),
                tasks=[dict(issue=17, issue_id=1017, task_id='TT-PR-001', pr_number=44, source='pipeline',
                    pipeline_run_id='00000000-0000-4000-8000-000000000001', legacy_card=None,
                    reviewer_profile='review', postmerge_profile='review',
                    required_checks=[dict(context='test', app_id=15368)], required_platforms=['windows'])])])

    def load(self, value=None):
        self.path.write_text(json.dumps(self.raw if value is None else value), encoding='utf-8')
        return load_pr_policy(self.path, self.connections, self.executor)

    def test_missing_actual_writer_attestation_blocks_merge(self):
        policy = self.load(); task = authorized_task(policy, 'OWNER/REPO', 44)
        self.assertEqual(task['readiness_reason'], 'writer_boundary_required')
        self.assertFalse(task['exclusive_writer']['enabled'])
        self.assertEqual(policy['interval_seconds'], 10)
        self.assertEqual(policy_fingerprint(policy), policy_fingerprint(copy.deepcopy(policy)))

    def test_policy_rejects_alias_unknown_keys_bool_limits_foreign_mapping(self):
        bad=[]
        v=copy.deepcopy(self.raw); v['surprise']=1; bad.append(v)
        v=copy.deepcopy(self.raw); v['max_pages']=True; bad.append(v)
        v=copy.deepcopy(self.raw); v['version']=True; bad.append(v)
        v=copy.deepcopy(self.raw); v['pipeline_journal']=v['executor_config']; bad.append(v)
        v=copy.deepcopy(self.raw); v['projects'][0]['repository']='foreign/repo'; bad.append(v)
        v=copy.deepcopy(self.raw); v['projects'][0]['tasks'][0]['issue_id']=True; bad.append(v)
        v=copy.deepcopy(self.raw); v['projects'][0]['tasks'].append(copy.deepcopy(v['projects'][0]['tasks'][0])); bad.append(v)
        v=copy.deepcopy(self.raw); v['projects'][0]['tasks'][0]['required_checks'][0]['app_id']=None; v['projects'][0]['publisher_account']='other'; bad.append(v)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError): self.load(value)
        with self.assertRaises(ValueError): authorized_task(self.load(), 'other/repo', 44)
        with self.assertRaises(ValueError): authorized_task(self.load(), 'owner/repo', True)

    def test_duplicate_json_keys_and_each_limit_boundary(self):
        self.path.write_text('{"version":1,"version":1}', encoding='utf-8')
        with self.assertRaises(ValueError): load_pr_policy(self.path,self.connections,self.executor)
        limits={'interval_seconds':(1,60),'max_prs_per_tick':(1,100),'max_pages':(1,100),
            'request_timeout_seconds':(1,120),'max_response_bytes':(1,67108864),
            'reviewer_timeout_seconds':(1,3600),'max_review_attempts':(1,5),
            'log_max_bytes':(1,67108864),'task_timeout_seconds':(60,604800)}
        for key,(low,high) in limits.items():
            for value in (low,high):
                raw=copy.deepcopy(self.raw); raw[key]=value; self.assertEqual(self.load(raw)[key],value)
            for value in (low-1,high+1,True,1.5):
                raw=copy.deepcopy(self.raw); raw[key]=value
                with self.subTest(key=key,value=value), self.assertRaises(ValueError): self.load(raw)

    def test_private_checkout_sidecar_hardlink_and_symlink_paths(self):
        for target in (self.checkout/'policy.json', self.root/'executor.json-wal'):
            raw=copy.deepcopy(self.raw)
            if target.parent==self.checkout:
                old=self.path; self.path=target
                try:
                    with self.assertRaises(ValueError): self.load(raw)
                finally: self.path=old
            else:
                raw['pipeline_journal']=str(target)
                with self.assertRaises(ValueError): self.load(raw)
        source=self.root/'executor.json'; source.write_text('{}',encoding='utf-8')
        alias=self.root/'alias'; os.link(source,alias)
        with self.assertRaises(ValueError): self.load()
        alias.unlink()
        try: alias.symlink_to(source)
        except OSError: return
        raw=copy.deepcopy(self.raw); raw['pipeline_journal']=str(alias)
        with self.assertRaises(ValueError): self.load(raw)

    def test_profiles_and_source_exclusivity(self):
        for field,value in [('reviewer_profile','missing'),('legacy_card','docs/tasks/TT-PR-001.json'),
                ('pipeline_run_id',None),('required_platforms',['windows','windows']),
                ('required_checks',[{'context':'test','app_id':True}])]:
            raw=copy.deepcopy(self.raw); raw['projects'][0]['tasks'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): self.load(raw)

    def test_legacy_recovery_and_trusted_commit_status_are_explicit(self):
        raw=copy.deepcopy(self.raw); raw['pipeline_journal']=None
        raw['legacy_provenance']=str(self.root/'legacy.json')
        task=raw['projects'][0]['tasks'][0]
        task.update(source='legacy',pipeline_run_id=None,legacy_card='docs/tasks/TT-PR-001.json',
            required_checks=[dict(context='trusted-status',app_id=None)],
            recovery_of=dict(pr_number=43,merge_commit='a'*40,event_sha256='b'*64,baseline_receipt_sha256='c'*64))
        policy=self.load(raw)
        self.assertEqual(authorized_task(policy,'owner/repo',44)['recovery_of']['pr_number'],43)
        for key,value in [('pr_number',True),('merge_commit','main'),('event_sha256','unknown'),('extra',1)]:
            bad=copy.deepcopy(raw); bad['projects'][0]['tasks'][0]['recovery_of'][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): self.load(bad)


if __name__=='__main__': unittest.main()
