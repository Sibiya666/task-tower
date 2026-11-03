import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from task_tower.reviewer import ReviewRunner


def loaded_postmerge_profile(installation,checkout,task_id,*,issue=9,issue_id=900,pr_number=1,counter=None):
    """Real Task1 loaders; writer remains unasserted, no runtime admission."""
    from types import SimpleNamespace
    import uuid
    from task_tower.executor_profiles import load_executor_config,profile_fingerprint
    from task_tower.pr_policy import load_pr_policy,authorized_task
    installation=Path(installation).resolve(); installation.mkdir(parents=True,exist_ok=True)
    pins=installation/'pins'; pins.mkdir()
    manifest={}
    for name,raw in [('using-superpowers/SKILL.md',b'entry\r\n'),('verification/SKILL.md',b'independent verification\n')]:
        path=pins/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        manifest[name]=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
    script=installation/'review.py'
    script.write_text("import argparse,json,os\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args()\nr=json.loads(Path(a.request).read_text(encoding='utf-8'))\nassert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)\nm=json.loads(Path(a.request).with_name('instructions.json').read_text(encoding='utf-8'))\nassert m['source_sha256']==r['binding']['instructions_sha256']\nassert (Path(m['pins']['root'])/'verification/SKILL.md').read_bytes()==b'independent verification\\n'\nassert (Path(m['pins']['root'])/'using-superpowers/SKILL.md').read_bytes()==b'entry\\r\\n'\n"+
        ("p=Path("+repr(str(counter))+");p.write_text(p.read_text()+'x' if p.exists() else 'x')\n" if counter else '')+
        "Path(a.result).write_text(json.dumps(dict(task_id=r['task']['id'],commit=r['bundle']['merge_commit'],verdict='approve',summary='checked',findings=[])),encoding='utf-8')\n",encoding='utf-8')
    connection=SimpleNamespace(repository='owner/repo',checkout=Path(checkout).resolve(),runner_label='local',trusted_publishers=['bot'])
    profile=dict(kind='custom',repository='owner/repo',checkout=str(connection.checkout),runner_label='local',argv=[str(Path(sys.executable).resolve()),str(script)],
        source_ref='refs/heads/main',timeout_seconds=5,log_max_bytes=4096,max_attempts=1,trusted=True,runs_dir=str(installation/'runs'),
        superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)))
    executor_path=installation/'executor.json'
    executor_path.write_text(json.dumps(dict(version=1,profiles={'postmerge':profile},allowlist=[dict(repository='owner/repo',issue=issue,task_id=task_id,runner_label='local',profile='postmerge')])),encoding='utf-8')
    executor=load_executor_config(executor_path,[connection])
    policy_path=installation/'pr.json'
    policy_path.write_text(json.dumps(dict(version=1,executor_config=str(executor_path),pipeline_journal=str(installation/'pipeline.sqlite'),legacy_provenance=None,
        projects=[dict(repository='owner/repo',base_ref='refs/heads/main',publisher_account='bot',merge_enabled=True,
            exclusive_writer=dict(enabled=False,boundary_id='unasserted-fixture',asserted_by='bot'),tasks=[dict(issue=issue,issue_id=issue_id,task_id=task_id,pr_number=pr_number,
            source='pipeline',pipeline_run_id=str(uuid.uuid4()),legacy_card=None,reviewer_profile='postmerge',postmerge_profile='postmerge',required_checks=[dict(context='test',app_id=15368)],required_platforms=['windows'])])])),encoding='utf-8')
    policy=load_pr_policy(policy_path,[connection],executor)
    task=authorized_task(policy,'owner/repo',pr_number)
    return executor['profiles'][task['postmerge_profile']],task


class LoadedBoundReviewerTests(unittest.TestCase):
    def test_task1_loaded_profile_and_full_manifest_drive_real_bound_process(self):
        from task_tower.pr_evidence import PostmergeReviewBinding
        from task_tower.pr_policy import policy_fingerprint
        from task_tower.executor_profiles import profile_fingerprint
        from task_tower import tasks
        import uuid
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); checkout=root/'checkout';checkout.mkdir()
            profile,task=loaded_postmerge_profile(root/'install-\u0442\u0435\u0441\u0442',checkout,'TT-LOADED-1')
            self.assertEqual(task['readiness_reason'],'writer_boundary_required')
            card=dict(id='TT-LOADED-1',executor='executor',stages={},status='in_progress')
            bundle=dict(repository='owner/repo',task_ids=['TT-LOADED-1'],merge_commit='a'*40)
            values=dict(pr_binding=dict(repository='owner/repo',pr_number=1,issue=9,issue_id=900,task_id='TT-LOADED-1',head_sha='b'*40,base_sha='c'*40,input_sha256='d'*64,policy_sha256='e'*64),
                merge_commit='a'*40,bundle_sha256=policy_fingerprint(bundle),snapshot_sha256=tasks.task_snapshot(card),reviewer_instance_id=str(uuid.uuid4()),excluded_instances=(),profile_sha256=profile_fingerprint(profile),instructions_sha256=profile_fingerprint(profile['superpowers']))
            material=dict(values,excluded_instances=[])
            binding=PostmergeReviewBinding(**values,request_sha256=policy_fingerprint(dict(binding=material,task=card,bundle=bundle)),effect_id=str(uuid.uuid4()))
            result=ReviewRunner(profile).review_bound(checkout,card,bundle,root/'output',binding=binding,executor_profile=profile)
            self.assertEqual(result['result']['verdict'],'approve')
            self.assertTrue(result['process']['cleanup_confirmed'])
            self.assertGreater(result['process']['pid'],0)


class BoundReviewerTests(unittest.TestCase):
    def setUp(self):
        import uuid
        from task_tower.pr_policy import policy_fingerprint
        from task_tower.executor_profiles import profile_fingerprint
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.checkout=self.root/'checkout';self.checkout.mkdir()
        self.config,self.selected=loaded_postmerge_profile(self.root/'install',self.checkout,'TT-BOUND-1')
        self.task=dict(id='TT-BOUND-1',executor='implementer',version=1,project_root='../..',stages={},status='in_progress')
        self.bundle=dict(repository='owner/repo',task_ids=['TT-BOUND-1'],merge_commit='a'*40,run_id='1',attempt='1',platforms={'windows':'passed'})
        self.values=dict(pr_binding=dict(repository='owner/repo',pr_number=1,issue=9,issue_id=900,task_id='TT-BOUND-1',head_sha='b'*40,base_sha='c'*40,input_sha256='d'*64,policy_sha256='e'*64),
            merge_commit='a'*40,bundle_sha256=policy_fingerprint(self.bundle),snapshot_sha256=__import__('task_tower.tasks',fromlist=['task_snapshot']).task_snapshot(self.task),
            request_sha256=None,effect_id=None,reviewer_instance_id=str(uuid.uuid4()),excluded_instances=(),profile_sha256=profile_fingerprint(self.config),instructions_sha256=profile_fingerprint(self.config['superpowers']))
        import copy
        binding=copy.deepcopy(self.values); binding.pop('request_sha256'); binding.pop('effect_id'); binding['excluded_instances']=[]
        self.values['request_sha256']=policy_fingerprint(dict(binding=binding,task=self.task,bundle=self.bundle))
        self.values['effect_id']=str(uuid.uuid4())

    def binding_for(self,profile):
        from task_tower.pr_evidence import PostmergeReviewBinding
        from task_tower.pr_policy import policy_fingerprint
        from task_tower.executor_profiles import profile_fingerprint
        values=dict(self.values,profile_sha256=profile_fingerprint(profile),instructions_sha256=profile_fingerprint(profile['superpowers']))
        material={k:v for k,v in values.items() if k not in ('request_sha256','effect_id')};material['excluded_instances']=list(material['excluded_instances'])
        values['request_sha256']=policy_fingerprint(dict(binding=material,task=self.task,bundle=self.bundle))
        return PostmergeReviewBinding(**values)

    def test_bound_review_returns_actual_process_and_immutable_request(self):
        from task_tower.pr_evidence import PostmergeReviewBinding
        from task_tower.pr_policy import policy_fingerprint
        with patch.dict(os.environ,{'gH_ToKeN':'private','GiThUb_ToKeN':'private'}):
            envelope=ReviewRunner(self.config).review_bound(self.checkout,self.task,self.bundle,self.root/'out',binding=PostmergeReviewBinding(**self.values),executor_profile=self.config)
        self.assertEqual(envelope['result']['verdict'],'approve')
        self.assertTrue(envelope['process']['started'])
        self.assertTrue(envelope['process']['cleanup_confirmed'])
        self.assertGreater(envelope['process']['pid'],0)
        self.assertEqual(envelope['process']['exit_code'],0)
        self.assertEqual(envelope['reviewer_instance_id'],self.values['reviewer_instance_id'])
        self.assertEqual(envelope['request']['binding']['effect_id'],self.values['effect_id'])
        self.assertEqual(envelope['receipt_sha256'],policy_fingerprint({k:v for k,v in envelope.items() if k!='receipt_sha256'}))

    def test_excluded_instance_and_changed_request_refuse_before_launch(self):
        from task_tower.pr_evidence import PostmergeReviewBinding
        for changed in (dict(excluded_instances=(self.values['reviewer_instance_id'],)),dict(request_sha256='0'*64),dict(profile_sha256='0'*64)):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                ReviewRunner(self.config).review_bound(self.checkout,self.task,self.bundle,self.root/'out',binding=PostmergeReviewBinding(**dict(self.values,**changed)),executor_profile=self.config)
        self.assertFalse((self.root/'out').exists())

    def test_bound_review_rejects_child_changes_to_request_or_instruction_pin(self):
        from task_tower.pr_evidence import PostmergeReviewBinding
        script=Path(self.config['argv'][1]); original=script.read_text()
        pin=Path(self.config['superpowers']['root'])/'verification/SKILL.md'; pin_raw=pin.read_bytes()
        for index,mutation in enumerate(("Path(a.request).write_text('{}')",f"Path({str(pin)!r}).write_text('changed')", "(Path(m['pins']['root'])/'verification/SKILL.md').write_text('changed')", "Path(a.request).with_name('instructions.json').write_text('{}')", "Path(a.request).with_name('schema.json').write_text('{}')",
                "(Path(m['pins']['root'])/'using-superpowers/SKILL.md').write_bytes(b'entry\\n')",
                "q=Path(m['pins']['root'])/'verification/SKILL.md';q.unlink();os.link("+repr(str(pin))+",q)")):
            script.write_text(original+'\n'+mutation+'\n'); pin.write_bytes(pin_raw)
            with self.subTest(index=index),self.assertRaises(ValueError):
                ReviewRunner(self.config).review_bound(self.checkout,self.task,self.bundle,self.root/('out-'+str(index)),binding=PostmergeReviewBinding(**self.values),executor_profile=self.config)

    def test_full_profile_kind_trust_argv_and_approve_for_me_refuse(self):
        import copy
        for index,changes in enumerate((dict(kind='opencode'),dict(trusted=False),dict(approve_for_me=True),dict(approve_for_me=0),
                dict(argv=[]),dict(kind='codex',argv=[self.config['argv'][0],'--model','unapproved']),dict(repository='other/repo'))):
            profile=copy.deepcopy(self.config);profile.update(changes)
            output=self.root/('rejected-'+str(index))
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                ReviewRunner(profile).review_bound(self.checkout,self.task,self.bundle,output,binding=self.binding_for(profile),executor_profile=profile)
            self.assertFalse(output.exists())

    def test_non_entrypoint_source_pin_drift_refuses_before_launch(self):
        pin=Path(self.config['superpowers']['root'])/'verification/SKILL.md'
        pin.write_bytes(b'drift')
        with self.assertRaises(ValueError):
            ReviewRunner(self.config).review_bound(self.checkout,self.task,self.bundle,self.root/'out',binding=self.binding_for(self.config),executor_profile=self.config)
        self.assertFalse((self.root/'out').exists())

    def test_codex_bound_argv_is_readonly_with_full_snapshot_without_native_launch(self):
        from task_tower.processes import run_command as actual_runner
        profile=dict(self.config,kind='codex',argv=[self.config['argv'][0]],trusted=False)
        seen=[]
        def controlled(command,cwd,timeout,**kwargs):
            seen.append(command)
            result=command[command.index('--output-last-message')+1]
            code="import json;from pathlib import Path;Path("+repr(result)+").write_text(json.dumps(dict(task_id='TT-BOUND-1',commit='a'*40,verdict='approve',summary='checked',findings=[])))"
            return actual_runner([sys.executable,'-c',code],cwd,timeout,**kwargs)
        with patch('task_tower.reviewer.run_command',controlled):
            envelope=ReviewRunner(profile).review_bound(self.checkout,self.task,self.bundle,self.root/'out',binding=self.binding_for(profile),executor_profile=profile)
        self.assertEqual(envelope['result']['verdict'],'approve')
        self.assertEqual(seen[0][:5],[profile['argv'][0],'exec','--json','--sandbox','read-only'])
        self.assertNotIn('--approve-for-me',seen[0]);self.assertNotIn('--model',seen[0])
        self.assertIn('instructions.json',seen[0][-1]);self.assertIn('--output-schema',seen[0])


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'SKILL.md'
        self.skill.write_text('verification instructions', encoding='utf-8')
        self.task = {'id': 'T1', 'criteria': ['works']}
        self.bundle = {'merge_commit': 'a' * 40, 'platforms': {'linux': 'passed'}}
        self.config = {'kind': 'custom', 'timeout_seconds': 5,
                       'superpowers': {'path': str(self.skill), 'sha256': hashlib.sha256(self.skill.read_bytes()).hexdigest()}}

    def run_fixture(self, source, **changes):
        fixture = self.root / 'fixture.py'
        fixture.write_text(source, encoding='utf-8')
        config = dict(self.config, review_argv=[sys.executable, str(fixture), '{request}', '{result}', '{checkout}'])
        config.update(changes)
        return ReviewRunner(config).review(self.root, self.task, self.bundle, self.root / 'out')

    def test_real_custom_process_receives_request_and_returns_validated_result(self):
        result = self.run_fixture("""import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text())
assert r['task']['criteria']==['works'] and r['bundle']['platforms']=={'linux':'passed'}
assert r['checkout']==sys.argv[3] and r['superpowers']['sha256']
Path(sys.argv[2]).write_text(json.dumps({'task_id':'T1','commit':'a'*40,'verdict':'approve','summary':'checked','findings':[]}))
""")
        self.assertEqual(result, {'task_id': 'T1', 'commit': 'a'*40, 'verdict': 'approve', 'summary': 'checked', 'findings': []})

    def test_github_tokens_removed_but_model_auth_preserved(self):
        with patch.dict(os.environ, {'GH_TOKEN':'private-gh', 'GITHUB_TOKEN':'private-github', 'OPENAI_API_KEY':'model-auth'}):
            result = self.run_fixture("""import os,json,sys
from pathlib import Path
assert 'GH_TOKEN' not in os.environ and 'GITHUB_TOKEN' not in os.environ
assert os.environ['OPENAI_API_KEY']=='model-auth'
Path(sys.argv[2]).write_text(json.dumps({'task_id':'T1','commit':'a'*40,'verdict':'approve','summary':'checked','findings':[]}))
""")
        self.assertEqual(result['verdict'], 'approve')

    def test_timeout_and_nonzero_are_needs_input_without_provider_output(self):
        for source, timeout in [("import time; time.sleep(30)", .1), ("print('private-provider'); raise SystemExit(7)", 5)]:
            with self.subTest(source=source):
                result = self.run_fixture(source, timeout_seconds=timeout)
                self.assertEqual(result['verdict'], 'needs_input')
                self.assertNotIn('private-provider', str(result))

    def test_invalid_mismatched_or_extra_response_refuses_approval(self):
        valid = {'task_id':'T1','commit':'a'*40,'verdict':'approve','summary':'checked','findings':[]}
        for changes in [{'task_id':'other'}, {'commit':'b'*40}, {'verdict':'yes'}, {'findings':[{}]}, {'summary':None}, {'extra':True}]:
            with self.subTest(changes=changes):
                data = dict(valid, **changes)
                result = self.run_fixture('from pathlib import Path; import sys; Path(sys.argv[2]).write_text('+repr(json.dumps(data))+')')
                self.assertEqual(result['verdict'], 'needs_input')

    def test_skill_pin_and_unsupported_configuration_refused_before_launch(self):
        cases = [{'kind':'other'}, {'timeout_seconds':float('inf')}, {'timeout_seconds':0}, {'timeout_seconds':3601}, {'superpowers':{}}, {'superpowers':{'path':str(self.skill),'sha256':'0'*64}}]
        for changes in cases:
            with self.subTest(changes=changes):
                result = self.run_fixture("raise RuntimeError('must not launch')", **changes)
                self.assertEqual(result['verdict'], 'needs_input')

    def test_codex_argv_uses_read_only_schema_and_no_model_override(self):
        fixture = self.root / 'codex-fixture.py'
        fixture.write_text("""import json,sys
from pathlib import Path
a=sys.argv[1:]
assert a[0:4]==['exec','--json','--sandbox','read-only']
assert '--model' not in a and not any('bypass' in x for x in a)
s=json.loads(Path(a[a.index('--output-schema')+1]).read_text())
assert s['additionalProperties'] is False
assert 'AGENTS.md' in a[-1] and 'do not implement' in a[-1].lower()
Path(a[a.index('--output-last-message')+1]).write_text(json.dumps({'task_id':'T1','commit':'a'*40,'verdict':'reject','summary':'reviewed','findings':['issue']}))
""", encoding='utf-8')
        # A real Python executable wrapper exercises the command builder without calling a model.
        with patch('task_tower.reviewer.run_command') as command:
            from task_tower.processes import run_command
            command.side_effect = lambda argv,cwd,timeout_seconds,env: run_command([sys.executable,str(fixture),*argv[1:]],cwd,timeout_seconds,env=env)
            result = ReviewRunner(dict(self.config, kind='codex', executable='codex-fixture')).review(self.root,self.task,self.bundle,self.root/'out')
        self.assertEqual(result['verdict'], 'reject')
    def test_duplicate_json_keys_are_invalid(self):
        payload = '{"task_id":"wrong","task_id":"T1","commit":"' + 'a'*40 + '","verdict":"approve","summary":"ok","findings":[]}'
        result = self.run_fixture('from pathlib import Path; import sys; Path(sys.argv[2]).write_text('+repr(payload)+')')
        self.assertEqual(result['verdict'], 'needs_input')
