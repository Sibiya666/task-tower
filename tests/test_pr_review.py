import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from task_tower.pr_policy import canonical
from task_tower.executor_profiles import profile_fingerprint
try:
    from task_tower.pr_review import PRReviewRunner, validate_pr_review
except ImportError:
    PRReviewRunner = validate_pr_review = None


def request():
    data = {'diff': 'complete binary diff', 'authority': {'executor_instances': [], 'reviewer_instances': []}}
    value=dict(version=1, repository='owner/repo', pr_number=1, issue=2, issue_id=123,
        task_id='TT-TEST-001', head_sha='a'*40, base_sha='b'*40,
        input_sha256=hashlib.sha256(canonical(data).encode()).hexdigest(), policy_sha256='c'*64,
        reviewer_instance_id=str(uuid.uuid4()), attempt=1, input=data)
    data.update({k:value[k] for k in ('version','repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','policy_sha256','reviewer_instance_id','attempt')})
    value['input_sha256']=hashlib.sha256(canonical(data).encode()).hexdigest()
    return value


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.checkout=self.root/'checkout'; self.checkout.mkdir()
        pins=self.root/'pins'; pins.mkdir(); (pins/'SKILL.md').write_text('readonly\n',encoding='utf-8')
        manifest={'SKILL.md':hashlib.sha256(b'readonly\n').hexdigest()}
        self.profile=dict(kind='custom',trusted=True,repository='owner/repo',argv=[sys.executable,str(self.root/'child.py')],
            timeout_seconds=10,log_max_bytes=128,superpowers=dict(root=str(pins),revision='e'*40,
            manifest=manifest,manifest_sha256=profile_fingerprint(manifest)))
        self.req=request()
        self.req['input']['instructions_sha256']=profile_fingerprint(self.profile['superpowers'])
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()

    def child(self, suffix=''):
        (self.root/'child.py').write_text('''import argparse,json,os,pathlib
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args()
r=json.loads(pathlib.Path(a.request).read_text(encoding='utf-8'))
assert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ)
assert r['input']['diff']=='complete binary diff'
v={k:r[k] for k in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')}
v.update(verdict='approve',summary='Reviewed all changes.',findings=[],whole_diff_reviewed=True)
'''+suffix+'''\npathlib.Path(a.result).write_text(json.dumps(v),encoding='utf-8')\n''',encoding='utf-8')

    def run_review(self):
        self.assertIsNotNone(PRReviewRunner,'PR reviewer implementation missing')
        return PRReviewRunner(self.profile).review(self.checkout,self.req,self.root/'out')

    def test_fresh_readonly_instance_token_env_removed(self):
        self.child()
        with patch.dict(os.environ,{'gh_token':'SECRET','GitHub_Token':'SECRET'}): result=self.run_review()
        receipt=validate_pr_review(result,self.req,())
        self.assertEqual(receipt['verdict'],'approve'); self.assertEqual(receipt['head_sha'],'a'*40)
        self.assertTrue(result['process']['cleanup_confirmed'])
        self.assertNotIn('argv',result['process'])
        self.assertEqual(validate_pr_review(result,self.req,(self.req['reviewer_instance_id'],))['reason'],'reviewer_not_independent')
        with self.assertRaises(ValueError): PRReviewRunner(self.profile).review(self.checkout,self.req,self.root/'out')

    def test_result_binding_malformed_duplicate_keys_and_blocking_findings(self):
        self.child("v['findings']=[{'id':'P1','blocking':True,'summary':'Missing validation'}]")
        envelope=self.run_review()
        self.assertEqual(validate_pr_review(envelope,self.req,())['reason'],'blocking_findings')
        for key,value in [('head_sha','d'*40),('whole_diff_reviewed',False),('version',True),('extra','x')]:
            with self.subTest(key=key):
                bad=copy.deepcopy(envelope); bad['result'][key]=value
                self.assertEqual(validate_pr_review(bad,self.req,())['verdict'],'needs_input')

    def test_reviewer_timeout_descendant_cleanup_and_output_cap(self):
        (self.root/'child.py').write_text('import time\ntime.sleep(30)\n',encoding='utf-8')
        self.profile['timeout_seconds']=.2
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        result=self.run_review()
        self.assertEqual(result['process']['status'],'timeout')
        self.assertTrue(result['process']['cleanup_confirmed'])
        self.assertEqual(validate_pr_review(result,self.req,())['verdict'],'needs_input')

    def test_failed_process_and_tampered_host_hash_cannot_approve(self):
        self.child(); envelope=self.run_review()
        for change in ('process','request','result_sha256'):
            bad=copy.deepcopy(envelope)
            if change=='process': bad['process']['cleanup_confirmed']=False
            elif change=='request': bad['request']['base_sha']='d'*40
            else: bad[change]='0'*64
            self.assertEqual(validate_pr_review(bad,self.req,())['verdict'],'needs_input')

    def test_input_hash_mismatch_and_pin_drift_prevent_launch(self):
        self.child(); self.req['input']['diff']='changed'
        with self.assertRaises(ValueError): self.run_review()
        self.req=request()
        self.req['input']['instructions_sha256']=profile_fingerprint(self.profile['superpowers'])
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest(); (self.root/'pins'/'SKILL.md').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError): self.run_review()




class ReviewHostileOutputTests(unittest.TestCase):
    setUp=ReviewTests.setUp
    child=ReviewTests.child
    run_review=ReviewTests.run_review
    def raw_child(self, code):
        (self.root/'child.py').write_text('import argparse,pathlib,json,sys,subprocess,time\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--result");a=p.parse_args()\n'+code,encoding='utf-8')

    def test_duplicate_json_result_is_rejected(self):
        self.raw_child("pathlib.Path(a.result).write_text('{\"version\":1,\"version\":1}',encoding='utf-8')\n")
        self.assertIsNone(self.run_review()['result'])

    def test_result_over_one_mib_is_rejected_and_logs_are_bounded(self):
        self.raw_child("pathlib.Path(a.result).write_bytes(b' '*(1048576+1));print('X'*10000)\n")
        value=self.run_review()
        self.assertIsNone(value['result']); self.assertEqual((self.root/'out'/'stdout.log').stat().st_size,128)
        self.assertGreater(value['process']['stdout_bytes'],10000)
        self.assertFalse(value['process']['stdout_tail_unknown'])

    def test_deep_json_cannot_crash_host(self):
        self.raw_child("pathlib.Path(a.result).write_text('['*200000+'0'+']'*200000,encoding='utf-8')\n")
        self.assertIsNone(self.run_review()['result'])

    def test_cancelled_prelaunch_has_no_child_and_no_approval(self):
        self.child()
        self.assertIsNotNone(PRReviewRunner)
        value=PRReviewRunner(self.profile).review(self.checkout,self.req,self.root/'out',cancel_requested=lambda:True)
        self.assertFalse(value['process']['started'])
        self.assertEqual(validate_pr_review(value,self.req,())['verdict'],'needs_input')

    def test_result_cannot_survive_nonzero_process(self):
        self.child()
        with (self.root/'child.py').open('a',encoding='utf-8') as stream: stream.write('\nraise SystemExit(7)\n')
        envelope=self.run_review()
        self.assertEqual(envelope['process']['exit_code'],7)
        self.assertEqual(validate_pr_review(envelope,self.req,())['reason'],'review_process_unconfirmed')

    def test_mutated_request_after_launch_is_rejected(self):
        self.child()
        with (self.root/'child.py').open('a',encoding='utf-8') as stream:
            stream.write("\npathlib.Path(a.request).write_text('{}',encoding='utf-8')\n")
        self.assertIsNone(self.run_review()['result'])

    def test_blocking_findings_duplicate_ids_and_wrong_types_fail(self):
        self.child(); envelope=self.run_review()
        cases=[dict(id='P1',blocking=1,summary='fail'),dict(id='P1',blocking=False,summary='')]
        for item in cases:
            bad=copy.deepcopy(envelope); bad['result']['findings']=[item]
            self.assertEqual(validate_pr_review(bad,self.req,())['reason'],'invalid_pr_review')
        bad=copy.deepcopy(envelope); bad['result']['findings']=[dict(id='P1',blocking=False,summary='same')]*2
        self.assertEqual(validate_pr_review(bad,self.req,())['reason'],'invalid_pr_review')

    def test_prior_stage_instance_and_nested_identity_drift_prevent_launch(self):
        self.child(); self.req['input']['authority']['executor_instances']=[self.req['reviewer_instance_id']]
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        with self.assertRaises(ValueError): self.run_review()
        self.req=request()
        self.req['input']['instructions_sha256']=profile_fingerprint(self.profile['superpowers'])
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest(); self.req['input']['issue_id']=124
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        with self.assertRaises(ValueError): self.run_review()

    def test_pinned_request_hash_drift_prevents_launch(self):
        self.child()
        self.req['input']['instructions_sha256']='0'*64
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        with self.assertRaises(ValueError): self.run_review()

    def test_timeout_kills_actual_descendant(self):
        marker=self.root/'descendant-survived'
        child_code='import pathlib,time;time.sleep(1);pathlib.Path('+repr(str(marker))+').write_text("alive")'
        self.raw_child('subprocess.Popen([sys.executable,"-c",'+repr(child_code)+']);time.sleep(30)\n')
        self.profile['timeout_seconds']=.3
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        envelope=self.run_review()
        import time
        time.sleep(1.1)
        self.assertFalse(marker.exists());self.assertTrue(envelope['process']['cleanup_confirmed'])
        self.assertEqual(envelope['process']['status'],'timeout')

    def test_private_pinned_instructions_are_available_to_actual_child(self):
        self.child("pin=json.loads((pathlib.Path(a.request).parent/'instructions.json').read_text(encoding='utf-8'));assert (pathlib.Path(pin['root'])/'SKILL.md').read_text(encoding='utf-8')=='readonly\\n'")
        envelope=self.run_review()
        self.assertEqual(validate_pr_review(envelope,self.req,())['verdict'],'approve')

    def test_nested_reviewer_attempt_and_uuid_drift_prevent_launch(self):
        self.child()
        for key,value in [('reviewer_instance_id',str(uuid.uuid4())),('attempt',2)]:
            with self.subTest(key=key):
                data=copy.deepcopy(self.req)
                data['input'][key]=value
                data['input_sha256']=hashlib.sha256(canonical(data['input']).encode()).hexdigest()
                with self.assertRaises(ValueError):
                    PRReviewRunner(self.profile).review(self.checkout,data,self.root/('out-'+key))

    def test_profile_argv_kind_trust_timeout_drift_prevents_launch(self):
        self.child()
        for field,value in [('timeout_seconds',9),('argv',[sys.executable,'other.py']),('trusted',False)]:
            profile=copy.deepcopy(self.profile);profile[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                PRReviewRunner(profile).review(self.checkout,self.req,self.root/('drift-'+field))

    def test_host_observed_actual_child_pid_is_retained(self):
        self.child("(pathlib.Path(a.request).parent/'actual-pid.txt').write_text(str(os.getpid()),encoding='utf-8')")
        envelope=self.run_review()
        actual=int((self.root/'out'/'actual-pid.txt').read_text(encoding='utf-8'))
        self.assertGreater(envelope['process']['pid'],0)
        self.assertEqual(envelope['process']['pid'],actual)

    def test_actual_source_to_role_complete_binary_diff_and_host_binding(self):
        """Real Git objects + bare transport; authority is a host-bound fixture.

        This proves the source/role seam, not deferred Task3 provenance trust.
        """
        import base64
        import subprocess
        from types import SimpleNamespace
        from task_tower.pr_source import prepare_review
        from task_tower.pr_policy import policy_fingerprint
        repo=self.checkout
        def git(*args):
            return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True).stdout.decode().strip()
        git('init');git('config','user.email','test@example.invalid');git('config','user.name','Test')
        git('remote','add','origin','https://github.com/owner/repo.git')
        (repo/'AGENTS.md').write_text('Read-only independent acceptance.\n',encoding='utf-8')
        (repo/'before.txt').write_text('before\n',encoding='utf-8')
        git('add','.');git('commit','-m','base');base=git('rev-parse','HEAD')
        git('mv','before.txt','after.txt');(repo/'asset.bin').write_bytes(b'\x00\xff\x01'*100)
        git('add','.');git('commit','-m','head');head=git('rev-parse','HEAD')
        bare=self.root/'transport.git'
        subprocess.run(['git','clone','--bare',str(repo),str(bare)],check=True,capture_output=True)
        self.profile.update(checkout=str(repo),runner_label='local',source_ref=head,runs_dir=str(self.root/'runs'),max_attempts=1,approve_for_me=False)
        task=dict(repository='owner/repo',pr_number=1,issue=2,issue_id=123,task_id='TT-TEST-001',
            _review_profile=self.profile,instructions_sha256=profile_fingerprint(self.profile['superpowers']))
        snapshot={key:task[key] for key in ('repository','pr_number','issue','issue_id','task_id')}
        snapshot.update(head_sha=head,base_sha=base,policy_sha256='c'*64,pr={},commits=[{'sha':head}],
            files=[{'patch':'TRUNCATED'}],reviews=[],threads={'nodes':[],'review_decision':None},
            ci=dict(sha256='4'*64,ready=True,reasons=[],acceptance_statuses=[]),
            protection=dict(sha256='5'*64,ready=True,reasons=[]),acceptance_statuses=[],ready=True,reasons=[],
            issue_payload=dict(id=123,number=2,title='Task',body='Review binary and rename',state='open',state_reason=None))
        snapshot['issue_sha256']=policy_fingerprint(snapshot['issue_payload'])
        authority=dict(source='legacy',run_id=None,criteria_sha256='1'*64,head_sha=head,base_sha=base,
            receipts=[],artifacts=[],executor_instances=['11111111-1111-4111-8111-111111111111'],
            reviewer_instances=['22222222-2222-4222-8222-222222222222'])
        authority['authority_sha256']=policy_fingerprint(authority)
        def fetch(mirror,url,base_arg,head_arg,logdir):
            if url!='https://github.com/owner/repo.git':raise AssertionError('foreign transport')
            subprocess.run(['git','-C',str(mirror),'fetch',str(bare),base_arg,head_arg],check=True,capture_output=True)
        with patch('task_tower.pr_source._fetch',fetch):
            prepared=prepare_review(SimpleNamespace(repository='owner/repo',checkout=repo),task,snapshot,authority,self.root/'prepared')
        self.raw_child('''import base64,os
r=json.loads(pathlib.Path(a.request).read_text(encoding='utf-8'))
diff=base64.b64decode(r['input']['diff']['content_base64'])
assert b'GIT binary patch' in diff and b'rename from before.txt' in diff
assert b'TRUNCATED' not in diff
assert not any(key.upper() in ('GH_TOKEN','GITHUB_TOKEN') for key in os.environ)
v={key:r[key] for key in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')}
v.update(verdict='approve',summary='Whole binary diff and rename reviewed; binary/UI limits acknowledged.',findings=[],whole_diff_reviewed=True)
pathlib.Path(a.result).write_text(json.dumps(v),encoding='utf-8')
''')
        with patch.dict(os.environ,{'GH_TOKEN':'secret','gItHuB_tOkEn':'secret'}):
            envelope=PRReviewRunner(self.profile).review(Path(prepared['checkout']),prepared['request'],self.root/'joint-role')
        receipt=validate_pr_review(envelope,prepared['request'],())
        self.assertEqual(receipt['verdict'],'approve');self.assertEqual(receipt['head_sha'],head)
        self.assertEqual(receipt['base_sha'],base);self.assertGreater(envelope['process']['pid'],0)
        self.assertEqual(git('rev-parse','HEAD'),head)
        self.assertNotIn(str(self.root),canonical(receipt))

    def test_actual_codex_cli_protocol_is_readonly_without_model_override(self):
        # Python executes the local `exec` fixture as a fake CLI transport.
        # The role's actual argument construction/process runner remain real.
        self.profile.update(kind='codex',argv=[sys.executable],trusted=False)
        self.req['input']['profile_sha256']=profile_fingerprint(self.profile)
        self.req['input_sha256']=hashlib.sha256(canonical(self.req['input']).encode()).hexdigest()
        (self.checkout/'exec').write_text('''import json,pathlib,sys
args=sys.argv[1:]
assert '--json' in args and args[args.index('--sandbox')+1]=='read-only'
assert not any(arg in args for arg in ('--model','-m','--approve-for-me','--dangerously-bypass-approvals-and-sandbox','resume','fork'))
assert pathlib.Path(args[args.index('-C')+1]).resolve()==pathlib.Path.cwd()
result=pathlib.Path(args[args.index('--output-last-message')+1])
r=json.loads((result.parent/'request.json').read_text(encoding='utf-8'))
schema=json.loads(pathlib.Path(args[args.index('--output-schema')+1]).read_text(encoding='utf-8'))
assert schema['additionalProperties'] is False
v={key:r[key] for key in ('version','repository','pr_number','task_id','head_sha','base_sha','input_sha256','reviewer_instance_id')}
v.update(verdict='approve',summary='Whole diff reviewed in readonly role.',findings=[],whole_diff_reviewed=True)
result.write_text(json.dumps(v),encoding='utf-8')
''',encoding='utf-8')
        envelope=self.run_review()
        self.assertEqual(validate_pr_review(envelope,self.req,())['verdict'],'approve')
