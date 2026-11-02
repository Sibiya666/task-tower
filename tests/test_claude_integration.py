"""Synthetic CLI transport; real adapter/queue/Git/auth guards/process runner.

These are not installed-Claude or authenticated-model execution evidence.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

from task_tower import executor, executor_worker as worker, claude_adapter as claude
from task_tower.dispatch_delivery import run_backend
from task_tower.executor_queue import ExecutionQueue
from task_tower.github_tasks import replace_metadata
from task_tower.processes import run_command as contained_command


FIXTURE_HELP = '''  -p, --print  Print
  --output-format <format> choices: "stream-json", "text"
  --verbose Verbose
  --json-schema <schema> Schema
  --safe-mode Safe
  --permission-mode <mode> choices: "manual"
  --permission-prompts <target> choices: "none"
  --tools <tools> Tools
  --allowedTools <tools> Allowed
  --strict-mcp-config Strict
  --mcp-config <file> MCP
  --no-chrome Chrome
  --session-id <uuid> UUID
  --max-budget-usd <budget> Budget
'''
FIXTURE = '''import json,os,pathlib,sys,time
a=sys.argv[1:]
assert not any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN','FORCE_AUTOUPDATE_PLUGINS') for k in os.environ)
assert os.environ.get('DISABLE_UPDATES')=='1'
if a==['--'+os.environ.get('TT_FIXTURE_SLOW_PROBE','')]:
 pathlib.Path('probe-ready').write_text('ready');time.sleep(30)
if a==['--version']:
 print(os.environ.get('TT_FIXTURE_VERSION','2.1.302')+' (Claude Code)');sys.exit(0)
if a==['--help']:
 print(HELP);sys.exit(0)
schema=json.loads(a[a.index('--json-schema')+1])
v={k:schema['properties'][k]['const'] for k in ('run_id','attempt_id','source_sha')}
prompt=a[-1]; marker='Execution request (task data, not invocation authority):\\n'
r=json.JSONDecoder().raw_decode(prompt.split(marker,1)[1])[0]
assert all(r[k]==v[k] for k in v)
if os.environ.get('TT_FIXTURE_REJECT_APPEND')=='1':
 print('fixture unknown append option',file=sys.stderr);sys.exit(2)
bundle=pathlib.Path(a[a.index('--append-system-prompt-file')+1]).read_bytes()
assert 'Pinned fixture instructions' not in prompt
for name,sha in r['instruction_manifest'].items():
 data=pathlib.Path.cwd().parent.joinpath('instructions',name).read_bytes()
 assert __import__('hashlib').sha256(data).hexdigest()==sha
 assert data in bundle and name.encode() in bundle and sha.encode() in bundle
assert 'Pinned fixture instructions' in bundle.decode('utf-8')
mode=r['task_data']['body'].splitlines()[0]
session=a[a.index('--session-id')+1]
def emit(value):print(json.dumps(value),flush=True)
emit(dict(type='system',subtype='init',session_id=session,model='fixture-reported-model'))
if mode=='wait':
 pathlib.Path('ready').write_text('ready');time.sleep(30)
if mode=='malformed':print('not-json',flush=True);time.sleep(30)
if mode=='wrong-source':v['source_sha']='0'*40
if mode=='missing':sys.exit(0)
if mode=='nonzero':sys.exit(7)
if mode=='result-collision':pathlib.Path.cwd().parent.joinpath('result.json').write_text('untrusted')
v.update(version=1,status='completed',summary='fixture-private-summary')
if a[a.index('--tools')+1]=='Read,Edit,Write,Glob,Grep':pathlib.Path('tracked.txt').write_text('fixture output')
emit(dict(type='result',subtype='success',session_id=session,is_error=False,
 permission_denials=['denied'] if mode=='denied' else [],structured_output=v))
if mode=='valid-nonzero':sys.exit(7)
if mode=='valid-timeout':time.sleep(30)
'''


class ClaudeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.source=self.root/'source';self.source.mkdir()
        self.git('init');self.git('config','user.email','fixture@example.test');self.git('config','user.name','Fixture')
        (self.source/'tracked.txt').write_text('source');self.git('add','.');self.git('commit','-m','source')
        self.git('branch','approved');self.sha=self.git('rev-parse','HEAD')
        pins=self.root/'pins';pins.mkdir();(pins/'SKILL.md').write_text('Pinned fixture instructions\n')
        manifest={'SKILL.md':hashlib.sha256(b'Pinned fixture instructions\n').hexdigest()}
        from task_tower.executor_profiles import profile_fingerprint
        self.profile=dict(kind='claude',repository='Owner/Repo',checkout=str(self.source),runner_label='local',
            argv=[str(Path(sys.executable).resolve())],source_ref='refs/heads/approved',timeout_seconds=3,
            log_max_bytes=64,max_attempts=2,runs_dir=str(self.root/'runs'),
            superpowers=dict(root=str(pins),revision='a'*40,manifest=manifest,manifest_sha256=profile_fingerprint(manifest)),
            claude=dict(version='2.1.302',role='implementer',max_budget_usd='0.25',stream_max_bytes=65536,line_max_bytes=4096))
        self.policy=self.root/'executor.json'
        self.policy.write_text(json.dumps(dict(version=1,profiles={'fixture':self.profile},allowlist=[dict(
            repository='Owner/Repo',issue=20,task_id='TT-FIXTURE-20',runner_label='local',profile='fixture')])))
        self.connections=self.root/'connections.json'
        self.connections.write_text(json.dumps(dict(version=1,projects=[dict(id='fixture',repository='Owner/Repo',
            checkout=str(self.source),runner_label='local')])))
        self.queue=ExecutionQueue(self.root/'queue.db',checkouts=[self.source])
        self.request=dict(operation='submit',delivery_id=str(uuid.uuid4()),repository='Owner/Repo',issue=20,
                          task_id='TT-FIXTURE-20',runner_label='local')
        self.backend=dict(argv=[sys.executable,'-m','task_tower','executor','adapter','--connections',str(self.connections),
            '--config',str(self.policy),'--queue',str(self.queue.path),'--request','{request}','--result','{result}'],
            cwd=str(Path(__file__).resolve().parents[1]),timeout_seconds=10)
        self.mode='normal';self.dependencies=False;self.calls=[];self.after_probe=None;self.after_model=None
        self.model_cleanup_fault=False;self.probe_cleanup_fault=False;self.model_unavailable=False
        self.post_model_active=False;self.during_binding=None
        self.config_dir=self.root/'claude-config';self.config_dir.mkdir()
        self.helper=self.root/'fixture.py';self.helper.write_text('HELP='+repr(FIXTURE_HELP)+'\n'+FIXTURE)
        self.addCleanup(self.remove_worktrees)

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.source,check=True,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout.decode().strip()

    def remove_worktrees(self):
        for path in (self.root/'runs').glob('*/*/worktree'):self.git('worktree','remove','--force',str(path))

    def submit(self):return run_backend(self.backend,self.request)['receipt_id']

    def transport(self,method,url,headers,payload,limit):
        self.assertEqual(method,'GET')
        if self.post_model_active and self.during_binding:
            hook=self.during_binding;self.during_binding=None;hook()
        metadata=dict(version=1,kind='task',mode='autonomous',status='open',task_id='TT-FIXTURE-20')
        if self.dependencies:metadata['blocked_by']=['Owner/Repo#19']
        rows=[dict(number=20,state='open',title='Fixture task',body=replace_metadata(self.mode,metadata))]
        if self.dependencies:
            rows.append(dict(number=19,state='closed',title='Unproved',body=replace_metadata('',dict(
                version=1,kind='task',mode='autonomous',status='done',task_id='TT-FIXTURE-19'))))
        if '/comments?' in url:return b'[]'
        if '/issues?' in url:return json.dumps(rows).encode()
        if '/issues/' in url:return json.dumps(next(row for row in rows if url.endswith('/'+str(row['number'])))).encode()
        raise AssertionError('Unexpected transport request')

    def cli_transport(self,argv,cwd,timeout_seconds,env,**kwargs):
        self.assertEqual(argv[0],self.profile['argv'][0]);self.assertEqual(Path(cwd).name,'worktree')
        self.assertEqual(env['DISABLE_UPDATES'],'1')
        self.assertFalse(any(key.upper() in ('GH_TOKEN','GITHUB_TOKEN','FORCE_AUTOUPDATE_PLUGINS') for key in env))
        self.calls.append(argv[1:])
        saved=self.queue.status(self.queue.lookup(self.request['delivery_id'])['receipt_id'])
        self.assertTrue(saved['evidence'].get('claude_probe_intent'))
        if argv[1:] not in (['--version'],['--help']):
            self.assertIn('--safe-mode',argv);self.assertIn('--json-schema',argv)
            self.assertNotIn('--model',argv[:-1]);self.assertIn('stdout_observer',kwargs)
        if self.model_unavailable and argv[1]=='-p':
            result=contained_command([str(self.root/'missing-fixture.exe'),*argv[1:]],cwd,timeout_seconds,env,**kwargs)
        elif ((self.model_cleanup_fault and argv[1]=='-p') or
              (self.probe_cleanup_fault and argv[1:] == ['--version'])) and os.name=='nt':
            with patch('task_tower.windows_job.WindowsJobProcess.close',side_effect=OSError):
                result=contained_command([sys.executable,str(self.helper),*argv[1:]],cwd,timeout_seconds,env,**kwargs)
        else:
            result=contained_command([sys.executable,str(self.helper),*argv[1:]],cwd,timeout_seconds,env,**kwargs)
        if argv[1:]==['--version'] and self.after_probe:self.after_probe()
        if argv[1]=='-p':
            self.post_model_active=True
            if self.after_model:self.after_model()
        return result

    def execute(self,extra_env=None,command_transport=None):
        output=io.StringIO()
        # Only network/CLI protocol transport is substituted. main builds the
        # production file authority guard; source selection/verified_done stay real.
        with patch.dict(os.environ,{'GH_TOKEN':'fixture-only','GITHUB_TOKEN':'fixture-only',
                'CLAUDE_CONFIG_DIR':str(self.config_dir),**(extra_env or {})}),\
             patch('task_tower.github_tasks._transport',side_effect=self.transport),\
             patch('task_tower.github_source._http_get',return_value=b'{"workflow_runs":[],"artifacts":[]}'),\
             patch.object(worker,'run_command',side_effect=command_transport or self.cli_transport),contextlib.redirect_stdout(output):
            code=executor.main(['work','--connections',str(self.connections),'--config',str(self.policy),
                                '--queue',str(self.queue.path),'--once'])
        self.assertEqual(code,0)
        return json.loads(output.getvalue())

    def directory(self):return next((self.root/'runs').glob('*/*/manifest.json')).parent

    def test_common_backend_validates_fixture_stream_beyond_prefix_and_deduplicates(self):
        run=self.submit();self.assertEqual(self.submit(),run)
        self.assertEqual(self.execute()['status'],'execution_completed')
        directory=self.directory();saved=self.queue.status(run)
        self.assertTrue(saved['evidence']['claude_protocol_validated'])
        self.assertEqual((self.source/'tracked.txt').read_text(),'source')
        self.assertEqual((directory/'worktree'/'tracked.txt').read_text(),'fixture output')
        for filename,key in [('claude-events.json','claude_events_sha256'),('result.json','result_sha256'),
                             ('claude-probes.json','claude_probes_sha256')]:
            self.assertEqual(hashlib.sha256((directory/filename).read_bytes()).hexdigest(),saved['evidence'][key])
        self.assertTrue(json.loads((directory/'process.json').read_text())['stdout_truncated'])
        self.assertNotIn('fixture-private-summary',repr(saved))
        self.assertEqual(self.execute()['status'],'idle');self.assertEqual(self.submit(),run)

    def test_denials_failures_and_wrong_bindings(self):
        for mode,status in [('denied','needs_input'),('wrong-source','failed'),('missing','failed'),
                            ('nonzero','failed'),('malformed','failed')]:
            with self.subTest(mode=mode):
                self.mode=mode;self.request['delivery_id']=str(uuid.uuid4());run=self.submit()
                self.assertEqual(self.execute()['status'],status)
                self.assertNotEqual(self.queue.status(run)['state'],'execution_completed')

    def test_probe_version_conflict_blocks_model(self):
        self.submit();self.assertEqual(self.execute({'TT_FIXTURE_VERSION':'2.1.303'})['status'],'needs_input')
        self.assertEqual(len(self.calls),1)

    def test_observed_local_update_override_blocks_all_probes(self):
        (self.config_dir/'settings.json').write_text('{"env":{"DISABLE_UPDATES":"0","secret":"never-output"}}')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input');self.assertEqual(self.calls,[])

    def test_changed_private_policy_after_probe_blocks_model(self):
        self.after_probe=lambda:self.policy.write_text(self.policy.read_text()+' ')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call and call[0]=='-p' for call in self.calls))

    def test_real_dependency_verifier_rejects_unproved_closed_issue(self):
        self.dependencies=True;self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertEqual(self.calls,[])

    def test_started_malformed_attempt_cannot_retry_or_reexecute(self):
        self.mode='malformed';run=self.submit();self.assertEqual(self.execute()['status'],'failed')
        before=len(self.calls);self.assertEqual(self.execute()['status'],'idle');self.assertEqual(len(self.calls),before)
        saved=self.queue.status(run)
        with self.assertRaises(ValueError):self.queue.retry_prelaunch(run,
            profile_fingerprint=saved['profile_fingerprint'],max_attempts=2)

    def test_reviewer_role_omits_edits(self):
        policy=json.loads(self.policy.read_text());policy['profiles']['fixture']['claude']['role']='reviewer'
        self.policy.write_text(json.dumps(policy));self.submit()
        self.assertEqual(self.execute()['status'],'execution_completed')
        model=next(call for call in self.calls if call[0]=='-p')
        self.assertEqual(model[model.index('--tools')+1],'Read,Glob,Grep')
        self.assertEqual((self.directory()/'worktree'/'tracked.txt').read_text(),'source')

    def test_large_inline_request_rejected_before_process_launch(self):
        self.mode='x'*40000;self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertEqual(self.calls,[])

    def test_nul_in_pinned_inline_context_is_rejected_before_probes(self):
        data=b'Pinned fixture instructions\x00\n';(self.root/'pins'/'SKILL.md').write_bytes(data)
        policy=json.loads(self.policy.read_text());pins=policy['profiles']['fixture']['superpowers']
        pins['manifest']['SKILL.md']=hashlib.sha256(data).hexdigest()
        from task_tower.executor_profiles import profile_fingerprint
        pins['manifest_sha256']=profile_fingerprint(pins['manifest']);self.policy.write_text(json.dumps(policy))
        self.submit();self.assertEqual(self.execute()['status'],'needs_input');self.assertEqual(self.calls,[])

    def test_changed_source_ref_after_probe_blocks_model(self):
        def change():
            (self.source/'tracked.txt').write_text('new source');self.git('add','.');self.git('commit','-m','new')
            self.git('branch','-f','approved','HEAD')
        self.after_probe=change;self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_changed_pin_after_probe_blocks_model(self):
        self.after_probe=lambda:(self.root/'pins'/'SKILL.md').write_text('drift')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_changed_local_settings_after_probe_blocks_model(self):
        self.after_probe=lambda:(self.config_dir/'settings.json').write_text('{}')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_changed_executable_bytes_after_probe_block_model(self):
        copied=self.root/'fixture-python.exe';shutil.copyfile(sys.executable,copied)
        self.profile['argv']=[str(copied)]
        policy=json.loads(self.policy.read_text());policy['profiles']['fixture']['argv']=[str(copied)]
        self.policy.write_text(json.dumps(policy))
        self.after_probe=lambda:copied.write_bytes(b'changed executable fixture')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_host_result_collision_never_completes_or_overwrites(self):
        self.mode='result-collision';run=self.submit();self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual((self.directory()/'result.json').read_text(),'untrusted')
        self.assertNotIn('result_sha256',self.queue.status(run)['evidence'])

    def test_running_cancel_preserves_process_cleanup(self):
        self.mode='wait';run=self.submit();reports=[]
        thread=threading.Thread(target=lambda:reports.append(self.execute()));thread.start()
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                if list((self.root/'runs').glob('*/*/worktree/ready')):break
                time.sleep(.025)
            else:self.fail('fixture never reached running boundary')
            self.queue.cancel(run)
        finally:
            self.queue.cancel(run);thread.join(8)
        self.assertFalse(thread.is_alive());self.assertEqual(reports[0]['status'],'cancelled')
        self.assertTrue(self.queue.status(run)['evidence']['cleanup_confirmed'])
        self.assertFalse((self.directory()/'result.json').exists())

    def test_running_timeout_cannot_write_success_result(self):
        self.mode='wait';run=self.submit();self.assertEqual(self.execute()['status'],'timed_out')
        self.assertTrue(self.queue.status(run)['evidence']['cleanup_confirmed'])
        self.assertFalse((self.directory()/'result.json').exists())

    @unittest.skipUnless(os.name=='nt','Windows Job cleanup fault')
    def test_unknown_cleanup_fences_and_never_reexecutes(self):
        self.model_cleanup_fault=True;run=self.submit();self.assertEqual(self.execute()['status'],'unknown')
        self.assertFalse(self.queue.status(run)['evidence']['cleanup_confirmed'])
        self.assertFalse((self.directory()/'result.json').exists())
        count=len(self.calls);self.assertEqual(self.execute()['status'],'idle');self.assertEqual(len(self.calls),count)
        self.assertEqual(self.submit(),run)

    def test_clean_probe_timeouts_use_legal_prelaunch_state_and_keep_actual_evidence(self):
        for probe in ('version','help'):
            with self.subTest(probe=probe):
                self.request['delivery_id']=str(uuid.uuid4());run=self.submit()
                self.assertEqual(self.execute({'TT_FIXTURE_SLOW_PROBE':probe})['status'],'needs_input')
                saved=self.queue.status(run);evidence=saved['evidence']
                self.assertTrue(evidence['claude_'+probe+'_probe_timed_out'])
                self.assertTrue(evidence['claude_'+probe+'_probe_cleanup_confirmed'])
                self.assertFalse(evidence['claude_model_started'])
                directory=next((self.root/'runs'/run).glob('*'))
                process=directory/'probes'/probe/'process.json'
                self.assertEqual(hashlib.sha256(process.read_bytes()).hexdigest(),
                                 evidence['claude_'+probe+'_probe_sha256'])
                self.assertEqual(json.loads(process.read_text())['status'],'timeout')
                self.assertFalse((directory/'result.json').exists())
                with self.assertRaises(ValueError):self.queue.retry_prelaunch(run,
                    profile_fingerprint=saved['profile_fingerprint'],max_attempts=2)

    def test_post_model_revocation_never_publishes_validated_protocol_or_result(self):
        self.after_model=lambda:self.policy.write_text(self.policy.read_text()+' ')
        run=self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        evidence=self.queue.status(run)['evidence'];self.assertFalse(evidence.get('claude_protocol_validated',False))
        self.assertFalse((self.directory()/'claude-events.json').exists())
        self.assertFalse((self.directory()/'result.json').exists())
        observation=json.loads((self.directory()/'claude-observations.json').read_text())
        self.assertFalse(observation['validated']);self.assertFalse(observation['evidence']['protocol_validated'])

    def test_failed_and_timed_out_model_cannot_publish_positive_protocol(self):
        for mode,state in [('valid-nonzero','failed'),('valid-timeout','timed_out')]:
            with self.subTest(mode=mode):
                self.mode=mode;self.request['delivery_id']=str(uuid.uuid4());run=self.submit()
                self.assertEqual(self.execute()['status'],state)
                directory=next((self.root/'runs'/run).glob('*'))
                self.assertFalse(self.queue.status(run)['evidence'].get('claude_protocol_validated',False))
                self.assertFalse((directory/'result.json').exists())

    def test_cancel_after_model_exit_precedes_positive_publication(self):
        run=self.submit();self.after_model=lambda:self.queue.cancel(run)
        self.assertEqual(self.execute()['status'],'cancelled')
        self.assertFalse(self.queue.status(run)['evidence'].get('claude_protocol_validated',False))
        self.assertFalse((self.directory()/'result.json').exists())

    def test_model_metadata_is_private_and_survives_one_byte_log_cap(self):
        policy=json.loads(self.policy.read_text());policy['profiles']['fixture']['log_max_bytes']=1
        self.policy.write_text(json.dumps(policy));run=self.submit()
        self.assertEqual(self.execute()['status'],'execution_completed')
        observation=json.loads((self.directory()/'claude-observations.json').read_text())
        self.assertEqual(observation['private_metadata']['reported_model'],'fixture-reported-model')
        self.assertNotIn('fixture-reported-model',repr(self.queue.status(run)))

    def test_unavailable_model_after_started_probes_does_not_grant_no_child_retry(self):
        self.model_unavailable=True;run=self.submit();self.assertEqual(self.execute()['status'],'failed')
        saved=self.queue.status(run);evidence=saved['evidence']
        self.assertTrue(evidence['claude_version_probe_started'])
        self.assertFalse(evidence['claude_model_started'])
        self.assertFalse(evidence.get('no_child_created',False))
        self.assertFalse(evidence.get('prelaunch_failure',False))
        with self.assertRaises(ValueError):self.queue.retry_prelaunch(run,
            profile_fingerprint=saved['profile_fingerprint'],max_attempts=2)

    @unittest.skipUnless(os.name=='nt','Windows Job cleanup fault')
    def test_probe_cleanup_unknown_precedes_failed_probe_policy(self):
        self.probe_cleanup_fault=True;run=self.submit();self.assertEqual(self.execute()['status'],'unknown')
        evidence=self.queue.status(run)['evidence']
        self.assertTrue(evidence['claude_version_probe_started'])
        self.assertFalse(evidence['claude_version_probe_cleanup_confirmed'])
        self.assertFalse(evidence['claude_model_started'])
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_running_probe_cancel_keeps_actual_start_and_cleanup_proof(self):
        run=self.submit();reports=[]
        thread=threading.Thread(target=lambda:reports.append(self.execute({'TT_FIXTURE_SLOW_PROBE':'version'})))
        thread.start()
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                if list((self.root/'runs').glob('*/*/worktree/probe-ready')):break
                time.sleep(.025)
            else:self.fail('probe fixture never reached started boundary')
            self.queue.cancel(run)
        finally:
            self.queue.cancel(run);thread.join(8)
        self.assertFalse(thread.is_alive());self.assertEqual(reports[0]['status'],'cancelled')
        evidence=self.queue.status(run)['evidence']
        self.assertTrue(evidence['claude_version_probe_started'])
        self.assertTrue(evidence['claude_version_probe_cancelled'])
        self.assertTrue(evidence['claude_version_probe_cleanup_confirmed'])
        self.assertFalse(evidence['claude_model_started'])

    def test_full_sixty_file_snapshot_reaches_explicit_file_and_argv_fits(self):
        policy=json.loads(self.policy.read_text());pins=policy['profiles']['fixture']['superpowers'];manifest={}
        for index in range(60):
            name='SKILL.md' if index==0 else f'full-{index:03}.md'
            data=f'Pinned fixture instructions FILE_SENTINEL_{index}\n'.encode()+b'x'*6100+b'\n'
            (self.root/'pins'/name).write_bytes(data);manifest[name]=hashlib.sha256(data).hexdigest()
        from task_tower.executor_profiles import profile_fingerprint
        pins.update(manifest=manifest,manifest_sha256=profile_fingerprint(manifest));self.policy.write_text(json.dumps(policy))
        run=self.submit();self.assertEqual(self.execute()['status'],'execution_completed')
        model=next(call for call in self.calls if call[0]=='-p')
        self.assertIn('--append-system-prompt-file',model)
        self.assertLess(len(subprocess.list2cmdline(model).encode('utf-16-le'))//2,30000)
        metadata=json.loads((self.directory()/'claude-instructions.json').read_text())
        self.assertEqual(metadata['instruction_bundle_file_count'],60)
        self.assertGreaterEqual(metadata['instruction_bundle_bytes'],360199)
        self.assertGreaterEqual(sum((self.root/'pins'/name).stat().st_size for name in manifest),360199)
        bundle=Path(metadata['instruction_bundle_path']).read_bytes()
        for index in range(60):self.assertIn(f'FILE_SENTINEL_{index}\n'.encode(),bundle)
        self.assertNotIn('FILE_SENTINEL',repr(self.queue.status(run)))

    def test_unknown_append_option_does_not_fallback_or_replay(self):
        run=self.submit();self.assertEqual(self.execute({'TT_FIXTURE_REJECT_APPEND':'1'})['status'],'failed')
        self.assertEqual(sum(call[0]=='-p' for call in self.calls),1)
        self.assertFalse((self.directory()/'result.json').exists())
        count=len(self.calls);self.assertEqual(self.execute()['status'],'idle');self.assertEqual(len(self.calls),count)

    def test_bundle_drift_after_probe_blocks_model(self):
        self.after_probe=lambda:(self.directory()/'claude-system-prompt.md').write_text('omitted instructions')
        self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_bundle_drift_after_model_blocks_positive_publication(self):
        self.after_model=lambda:(self.directory()/'claude-system-prompt.md').write_text('drift')
        run=self.submit();self.assertEqual(self.execute()['status'],'needs_input')
        self.assertFalse(self.queue.status(run)['evidence']['claude_protocol_validated'])
        self.assertTrue(self.queue.status(run)['evidence']['cleanup_confirmed'])
        self.assertFalse((self.directory()/'claude-events.json').exists())
        self.assertFalse((self.directory()/'result.json').exists())

    def test_bundle_metadata_drift_blocks_model_and_positive_post_model_evidence(self):
        for phase in ('probe','model'):
            with self.subTest(phase=phase):
                self.request['delivery_id']=str(uuid.uuid4());run=self.submit();self.calls=[]
                def drift():
                    directory=next((self.root/'runs'/run).glob('*'))
                    (directory/'claude-instructions.json').write_text('{"rebound":true}')
                self.after_probe=drift if phase=='probe' else None
                self.after_model=drift if phase=='model' else None
                self.assertEqual(self.execute()['status'],'needs_input')
                directory=next((self.root/'runs'/run).glob('*'))
                self.assertFalse((directory/'result.json').exists())
                self.assertFalse(self.queue.status(run)['evidence'].get('claude_protocol_validated',False))
                if phase=='probe':self.assertFalse(any(call[0]=='-p' for call in self.calls))

    def test_cancel_during_genuine_post_model_http_binding_prevents_publication(self):
        run=self.submit();self.during_binding=lambda:self.queue.cancel(run)
        self.assertEqual(self.execute()['status'],'cancelled')
        saved=self.queue.status(run);self.assertTrue(saved['cancel_requested'])
        self.assertFalse(saved['evidence']['claude_protocol_validated'])
        self.assertFalse((self.directory()/'claude-events.json').exists())
        self.assertFalse((self.directory()/'result.json').exists())

    def test_cancel_committed_at_completion_record_is_atomic_and_files_are_forensic(self):
        run=self.submit();original=ExecutionQueue.record
        def race(queue,run_id,owner,state,evidence):
            if state=='execution_completed':self.queue.cancel(run)
            return original(queue,run_id,owner,state,evidence)
        with patch.object(ExecutionQueue,'record',race):
            self.assertEqual(self.execute()['status'],'cancelled')
        saved=self.queue.status(run);self.assertEqual(saved['state'],'cancelled')
        self.assertFalse(saved['evidence']['claude_protocol_validated'])
        self.assertNotIn('result_sha256',saved['evidence']);self.assertNotIn('claude_events_sha256',saved['evidence'])
        # Staged private files remain unchanged; the committed cancelled queue
        # record makes them forensic observations, never completion authority.
        self.assertTrue((self.directory()/'result.json').exists())
        self.assertEqual(hashlib.sha256((self.directory()/'result.json').read_bytes()).hexdigest(),
                         saved['evidence']['uncommitted_result_sha256'])

    def test_cancel_committed_at_running_record_never_launches_model(self):
        run=self.submit();original=ExecutionQueue.record
        def race(queue,run_id,owner,state,evidence):
            if state=='running':self.queue.cancel(run)
            return original(queue,run_id,owner,state,evidence)
        with patch.object(ExecutionQueue,'record',race):
            self.assertEqual(self.execute()['status'],'cancelled')
        saved=self.queue.status(run)
        self.assertTrue(saved['evidence']['claude_version_probe_started'])
        self.assertFalse(saved['evidence']['claude_model_started'])
        self.assertFalse(saved['evidence'].get('no_child_created',False))
        self.assertFalse(any(call[0]=='-p' for call in self.calls))

    @unittest.skipUnless(os.name=='nt','Windows Job cleanup fault')
    def test_unknown_model_cleanup_is_stronger_than_late_committed_cancel(self):
        self.model_cleanup_fault=True;run=self.submit();self.after_model=lambda:self.queue.cancel(run)
        self.assertEqual(self.execute()['status'],'unknown')
        saved=self.queue.status(run);self.assertTrue(saved['cancel_requested'])
        self.assertFalse(saved['evidence']['cleanup_confirmed'])
        self.assertFalse(saved['evidence']['claude_protocol_validated'])

    def test_model_timeout_then_committed_cancel_keeps_process_timeout_but_cancels_task(self):
        self.mode='valid-timeout';run=self.submit();self.after_model=lambda:self.queue.cancel(run)
        self.assertEqual(self.execute()['status'],'cancelled')
        process=json.loads((self.directory()/'process.json').read_text())
        self.assertEqual(process['status'],'timeout');self.assertTrue(process['cleanup_confirmed'])
        saved=self.queue.status(run);self.assertTrue(saved['cancel_requested'])
        self.assertFalse(saved['evidence']['claude_protocol_validated'])
        self.assertFalse((self.directory()/'result.json').exists())

    def test_legacy_custom_completion_record_obeys_same_committed_cancel_fence(self):
        helper=self.root/'custom-fixture.py'
        helper.write_text('''import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--result');a=p.parse_args()
r=json.loads(pathlib.Path(a.request).read_text());v={k:r[k] for k in ('run_id','attempt_id','source_sha')}
v.update(version=1,status='completed',summary='custom fixture');pathlib.Path(a.result).write_text(json.dumps(v))
''')
        policy=json.loads(self.policy.read_text());profile=policy['profiles']['fixture']
        profile.pop('claude');profile.update(kind='custom',trusted=True,argv=[str(Path(sys.executable).resolve()),str(helper)])
        self.policy.write_text(json.dumps(policy));run=self.submit();original=ExecutionQueue.record
        def race(queue,run_id,owner,state,evidence):
            if state=='execution_completed':self.queue.cancel(run)
            return original(queue,run_id,owner,state,evidence)
        with patch.object(ExecutionQueue,'record',race):
            self.assertEqual(self.execute(command_transport=contained_command)['status'],'cancelled')
        saved=self.queue.status(run)
        self.assertTrue(saved['evidence']['cleanup_confirmed'])
        self.assertNotIn('result_sha256',saved['evidence'])
        self.assertNotIn('claude_protocol_validated',saved['evidence'])
        self.assertTrue((self.directory()/'result.json').exists())


class LocalUpdatePreflightTests(unittest.TestCase):
    def test_relevant_keys_only_and_fingerprint_detects_change(self):
        self.assertTrue(hasattr(claude,'snapshot_local_settings'),'Local update preflight missing')
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw).resolve()/'settings.json'
            path.write_text('{"env":{"DISABLE_UPDATES":"1","secret":"never-output"}}')
            snapshot=claude.snapshot_local_settings([path])
            self.assertNotIn('never-output',repr(snapshot))
            self.assertEqual(snapshot,claude.snapshot_local_settings([path]))
            path.write_text('{"env":{"FORCE_AUTOUPDATE_PLUGINS":"1"}}')
            with self.assertRaises(ValueError):claude.snapshot_local_settings([path])

    def test_unreadable_unsafe_malformed_local_sources_block(self):
        self.assertTrue(hasattr(claude,'snapshot_local_settings'),'Local update preflight missing')
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw).resolve()/'settings.json'
            for data in [b'\xff',b'{',b'{"env":{"DISABLE_UPDATES":"0"}}',b'{"env":[]}']:
                path.write_bytes(data)
                with self.assertRaises(ValueError):claude.snapshot_local_settings([path])
            path.write_text('{}');os.link(path,path.parent/'alias')
            with self.assertRaises(ValueError):claude.snapshot_local_settings([path])
