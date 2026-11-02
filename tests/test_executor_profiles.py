import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from task_tower import executor_profiles as profiles


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


class ExecutorProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.checkout = self.root / 'checkout'
        self.checkout.mkdir()
        self.instructions = self.root / 'instructions'
        self.instructions.mkdir()
        (self.instructions / 'SKILL.md').write_bytes(b'instructions\r\n')
        manifest = {'SKILL.md': hashlib.sha256(b'instructions\n').hexdigest()}
        self.profile = dict(kind='custom', repository='Owner/Repo', checkout=str(self.checkout),
            runner_label='local', argv=[str(Path(os.sys.executable).resolve())], source_ref='refs/heads/main',
            timeout_seconds=60, log_max_bytes=4096, max_attempts=1, trusted=True,
            runs_dir=str(self.root / 'runs'), superpowers=dict(root=str(self.instructions),
                revision='a'*40, manifest=manifest, manifest_sha256=digest(manifest)))
        self.config = dict(version=1, profiles={'local': self.profile}, allowlist=[dict(
            repository='Owner/Repo', issue=15, task_id='TT-EXECUTOR-001', runner_label='local', profile='local')])
        self.path = self.root / 'executor.json'
        self.connections = [SimpleNamespace(repository='Owner/Repo', checkout=self.checkout, runner_label='local')]

    def load(self):
        self.path.write_text(json.dumps(self.config), encoding='utf-8')
        return profiles.load_executor_config(self.path, self.connections)

    def test_normalized_policy_and_canonical_fingerprint(self):
        loaded = self.load()
        self.assertEqual(loaded['max_active'], 2)
        self.assertFalse(loaded['profiles']['local']['approve_for_me'])
        policy = loaded['profiles']['local']
        self.assertEqual(profiles.profile_fingerprint(policy), digest(policy))
        self.assertEqual(profiles.profile_fingerprint(dict(reversed(list(policy.items())))), digest(policy))

    def test_child_environment_removes_tokens_case_insensitively_without_mutating_host(self):
        host = {'GH_TOKEN':'secret', 'github_token':'secret2', 'Gh_ToKeN':'secret3', 'PATH':'installed'}
        self.assertEqual(profiles.child_environment(host), {'PATH':'installed'})
        self.assertEqual(len(host), 4)

    def test_custom_requires_explicit_trust(self):
        del self.profile['trusted']
        with self.assertRaises(ValueError): self.load()

    def test_invalid_limits_and_unknown_policy_rejected(self):
        for field, value in [('timeout_seconds',0),('timeout_seconds',True),('log_max_bytes',0),('max_attempts',0),('model','chosen')]:
            with self.subTest(field=field, value=value):
                original = dict(self.profile)
                self.profile[field] = value
                with self.assertRaises(ValueError): self.load()
                self.profile.clear(); self.profile.update(original)
        for value in [0,3,True]:
            self.config['max_active'] = value
            with self.assertRaises(ValueError): self.load()

    def test_authority_identity_and_checkout_must_match(self):
        for field, value in [('repository','Other/Repo'),('runner_label','remote'),('checkout',str(self.root))]:
            original=self.profile[field]; self.profile[field]=value
            with self.assertRaises(ValueError): self.load()
            self.profile[field]=original
        self.config['allowlist'][0]['profile']='missing'
        with self.assertRaises(ValueError): self.load()

    def test_private_paths_and_aliases_rejected(self):
        self.profile['runs_dir']=str(self.checkout/'private')
        with self.assertRaises(ValueError): self.load()
        self.profile['runs_dir']=str(self.root/'runs')
        self.path=self.checkout/'executor.json'
        with self.assertRaises(ValueError): self.load()

    def test_hardlinked_configuration_rejected(self):
        self.load()
        alias=self.root/'alias.json'
        os.link(self.path,alias)
        with self.assertRaises(ValueError): profiles.load_executor_config(alias,self.connections)

    def test_pin_drift_and_unsafe_manifest_paths_rejected(self):
        (self.instructions/'SKILL.md').write_text('drift',encoding='utf-8')
        with self.assertRaises(ValueError): self.load()
        self.profile['superpowers']['manifest']={'../outside':'a'*64}
        with self.assertRaises(ValueError): self.load()

    def test_source_and_argv_cannot_supply_model_or_unsafe_source(self):
        self.profile['kind']='codex'
        for argv in [[],['relative'],[str(Path(os.sys.executable).resolve()),'--model','automatic']]:
            self.profile['argv']=argv
            with self.assertRaises(ValueError): self.load()
        self.profile['argv']=[str(Path(os.sys.executable).resolve())]
        self.profile['source_ref']='--upload-pack=bad'
        with self.assertRaises(ValueError): self.load()

    def test_symlinked_instruction_file_rejected(self):
        target=self.instructions/'SKILL.md'
        alias=self.instructions/'ALIAS.md'
        try: alias.symlink_to(target)
        except OSError: self.skipTest('symlink privilege unavailable')
        manifest={'ALIAS.md':hashlib.sha256(b'instructions\n').hexdigest()}
        self.profile['superpowers'].update(manifest=manifest,manifest_sha256=digest(manifest))
        with self.assertRaises(ValueError): self.load()

    def test_allowlist_duplicate_and_type_confusion_rejected(self):
        self.config['allowlist'].append(dict(self.config['allowlist'][0]))
        with self.assertRaises(ValueError): self.load()
        self.config['allowlist'].pop()
        self.config['allowlist'][0]['issue']=True
        with self.assertRaises(ValueError): self.load()

    def test_missing_manifest_and_wrong_manifest_hash_rejected(self):
        self.profile['superpowers']['manifest_sha256']='0'*64
        with self.assertRaises(ValueError): self.load()
        self.profile['superpowers']['manifest_sha256']=digest(self.profile['superpowers']['manifest'])
        (self.instructions/'SKILL.md').unlink()
        with self.assertRaises(ValueError): self.load()

    def test_codex_defaults_do_not_select_model(self):
        self.profile['kind']='codex'
        del self.profile['trusted']
        loaded=self.load()['profiles']['local']
        self.assertFalse(loaded['trusted'])
        self.assertNotIn('model',loaded)
        self.assertEqual(loaded['argv'],[str(Path(os.sys.executable).resolve())])

    def test_codex_argv_is_only_the_executable(self):
        self.profile['kind']='codex'
        executable=str(Path(os.sys.executable).resolve())
        for arguments in [
                ['--sandbox','danger-full-access'], ['-s','danger-full-access'],
                ['--approve-for-me'], ['-mchosen'], ['-c','model=chosen'],
                ['--dangerously-bypass-approvals-and-sandbox=true']]:
            with self.subTest(arguments=arguments):
                self.profile['argv']=[executable,*arguments]
                with self.assertRaises(ValueError): self.load()

    def test_kind_and_boolean_policies_have_strict_types(self):
        for field,value in [('kind',True),('kind',[]),('trusted',1),('approve_for_me','false')]:
            with self.subTest(field=field,value=value):
                old=self.profile.get(field)
                self.profile[field]=value
                with self.assertRaises(ValueError): self.load()
                if old is None: self.profile.pop(field)
                else: self.profile[field]=old

    def test_trusted_custom_arguments_are_arbitrary_owner_policy(self):
        arguments=['--sandbox','danger-full-access','--model','chosen','-mchosen','-c','model=chosen']
        self.profile['argv'].extend(arguments)
        self.assertEqual(self.load()['profiles']['local']['argv'][1:],arguments)

    def claude_profile(self):
        self.profile.update(kind='claude', trusted=False, claude=dict(version='2.1.302',
            role='implementer', max_budget_usd='0.25', stream_max_bytes=65536, line_max_bytes=4096))

    def test_claude_policy_is_fingerprinted_and_role_is_explicit(self):
        self.claude_profile()
        first=self.load()['profiles']['local']
        self.assertEqual(first['claude'],self.profile['claude'])
        self.profile['claude']['role']='reviewer'
        second=self.load()['profiles']['local']
        self.assertNotEqual(profiles.profile_fingerprint(first),profiles.profile_fingerprint(second))

    def test_claude_rejects_missing_unknown_and_confused_policy(self):
        self.claude_profile()
        original=dict(self.profile['claude'])
        for field,values in {
            'version':['2.1.303',True,None], 'role':['executor',[],True],
            'max_budget_usd':[1,True,'0','100.01','0.001','NaN','Infinity','1e1','-1',' 1','1.'],
            'stream_max_bytes':[True,65535,67108865],
            'line_max_bytes':[True,4095,1048577,65537], 'extra':['ignored']}.items():
            for value in values:
                with self.subTest(field=field,value=value):
                    self.profile['claude']=original|{field:value}
                    with self.assertRaises(ValueError): self.load()
        for field in original:
            self.profile['claude']={k:v for k,v in original.items() if k!=field}
            with self.assertRaises(ValueError): self.load()
        for policy in [None,[],True]:
            self.profile['claude']=policy
            with self.assertRaises(ValueError): self.load()
        self.profile.pop('claude')
        with self.assertRaises(ValueError): self.load()

    def test_claude_cannot_add_arguments_or_approval_policy(self):
        self.claude_profile()
        for update in [dict(trusted=True),dict(approve_for_me=True),
                       dict(argv=[self.profile['argv'][0],'--model','chosen'])]:
            original=dict(self.profile); self.profile.update(update)
            with self.assertRaises(ValueError): self.load()
            self.profile.clear(); self.profile.update(original)

    def test_other_kinds_reject_claude_options(self):
        self.profile['claude']={}
        with self.assertRaises(ValueError): self.load()
        self.profile['kind']='codex'
        with self.assertRaises(ValueError): self.load()

    def test_claude_budget_and_stream_boundary_values(self):
        self.claude_profile()
        for budget in ['0.01','1','100','100.00']:
            self.profile['claude']['max_budget_usd']=budget
            self.assertEqual(self.load()['profiles']['local']['claude']['max_budget_usd'],budget)
        self.profile['claude'].update(stream_max_bytes=67108864,line_max_bytes=1048576)
        self.load()

    def test_claude_shell_script_executable_is_not_native(self):
        self.claude_profile()
        for suffix in ['.cmd','.bat','.CMD']:
            path=self.root/('claude'+suffix); path.write_text('echo fixture')
            self.profile['argv']=[str(path)]
            with self.assertRaises(ValueError): self.load()
