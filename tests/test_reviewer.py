import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from task_tower.reviewer import ReviewRunner


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
