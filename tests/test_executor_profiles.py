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

    def v2(self):
        self.config['version']=2
        self.config['harness_resources']={'local':dict(pool_id='local',cpu_millis=1000,memory_bytes=1048576,max_parallel=None)}

    def test_v2_actual_file_defaults_and_caps_do_not_change_profiles(self):
        legacy=self.load()
        self.v2()
        loaded=self.load()
        self.assertEqual(set(loaded),{'version','profiles','allowlist','capacity','harness_resources'})
        self.assertEqual(loaded['capacity'],dict(max_executors=None,max_inflight=None))
        self.assertEqual(loaded['profiles'],legacy['profiles'])
        for cap in (1,3,2**63-1):
            self.config['capacity']=dict(max_executors=cap,max_inflight=cap)
            self.assertEqual(self.load()['capacity'],self.config['capacity'])

    def test_v2_grants_caps_aliases_and_duplicate_json_are_closed(self):
        import copy
        self.v2();valid=copy.deepcopy(self.config)
        for field in ('max_executors','max_inflight'):
            for invalid in (True,0,-1,2**63,1.5):
                self.config=copy.deepcopy(valid);self.config['capacity']=dict(max_executors=None,max_inflight=None)
                self.config['capacity'][field]=invalid
                with self.subTest(field=field,invalid=invalid),self.assertRaises(ValueError):self.load()
        for grants in ({},{'foreign':valid['harness_resources']['local']},
                       {'local':dict(valid['harness_resources']['local'],cpu_millis=True)},
                       {'local':dict(valid['harness_resources']['local'],memory_bytes=2**63)},
                       {'local':dict(valid['harness_resources']['local'],max_parallel=0)},
                       {'local':dict(valid['harness_resources']['local'],extra=1)}):
            self.config=copy.deepcopy(valid);self.config['harness_resources']=grants
            with self.assertRaises(ValueError):self.load()
        self.config=copy.deepcopy(valid)
        self.config['profiles']['alias']=dict(self.profile,runs_dir=str(self.root/'other-runs'))
        self.config['harness_resources']['alias']=dict(valid['harness_resources']['local'],pool_id='split')
        with self.assertRaises(ValueError):self.load()
        self.config=valid;self.config['max_active']=1
        with self.assertRaises(ValueError):self.load()
        del self.config['max_active']
        for text in (json.dumps(self.config).replace('"version": 2','"version": 2, "version": 2'),
                     json.dumps(self.config).replace('"cpu_millis": 1000','"cpu_millis": 1000, "cpu_millis": 1000')):
            self.path.write_text(text,encoding='utf-8')
            with self.assertRaises(ValueError):profiles.load_executor_config(self.path,self.connections)

    def test_v1_duplicate_last_wins_and_normalized_shape_stay_legacy(self):
        expected=self.load()
        raw=json.dumps(self.config).replace('"version": 1','"version": 2, "version": 1')
        self.path.write_text(raw,encoding='utf-8')
        self.assertEqual(profiles.load_executor_config(self.path,self.connections),expected)

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
