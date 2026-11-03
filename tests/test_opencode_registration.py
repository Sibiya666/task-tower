import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from task_tower import executor_harness, executor_profiles
from task_tower import opencode_files
from tests import test_executor_profiles as legacy_fixture
from tests import test_opencode_policy as policy_fixture


class OpenCodeRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.legacy=legacy_fixture.ExecutorProfilesTests();self.legacy.setUp();self.addCleanup(self.legacy.doCleanups)
        self.policy=policy_fixture.OpenCodePolicyTests();self.policy.setUp();self.addCleanup(self.policy.doCleanups)
        p=self.policy
        self.executable=p.root/'opencode.exe'
        self.executable.write_bytes(b'SYNTHETIC registration artifact, never executed')
        digest=hashlib.sha256(self.executable.read_bytes()).hexdigest()
        p.policy['executable_sha256']=digest;p.evidence['executable_sha256']=digest
        p.validate()
        self.profile=self.legacy.profile
        self.profile.update(kind='opencode',argv=[str(self.executable)],log_max_bytes=67108864,
                            runs_dir=str(p.runs),opencode=p.policy,approve_for_me=False)

    def test_valid_registration_has_no_native_capability(self):
        profile=self.legacy.load()['profiles']['local']
        self.assertEqual(profile['kind'],'opencode')
        self.assertEqual(profile['opencode'],self.policy.policy)
        self.assertEqual(executor_harness.capabilities(profile),dict(configured=True,executable=True,
            probed=False,verified=False,events=False,resume=False))
        with self.assertRaises(ValueError): executor_harness.build_invocation({},profile)

    def test_wrapper_approval_log_and_artifact_mismatch_rejected(self):
        for change in (dict(argv=[str(self.executable),'fixed']),dict(approve_for_me=True),
                       dict(log_max_bytes=67108863),dict(opencode=dict(self.policy.policy,extra=True))):
            original=copy.deepcopy(self.profile);self.profile.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.legacy.load()
            self.profile.clear();self.profile.update(original)
        self.executable.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.legacy.load()

    def test_artifacts_cannot_reside_in_another_profile_output_root(self):
        other=copy.deepcopy(self.profile)
        other.update(kind='custom',argv=[str(Path(__file__).resolve())],runs_dir=str(self.policy.root),trusted=True)
        other.pop('opencode')
        self.legacy.config['profiles']['other']=other
        # The old overlapping-output restriction also applies before evidence.
        with self.assertRaises(ValueError):self.legacy.load()

    def test_legacy_profiles_do_not_accept_opencode_fields(self):
        self.profile['kind']='codex'
        with self.assertRaises(ValueError):self.legacy.load()

    def test_other_profile_output_is_rejected_before_artifact_read(self):
        root=self.policy.root/'other-output';root.mkdir()
        path=root/'source-audit.md';data=b'synthetic tainted output'
        path.write_bytes(data)
        ref=self.policy.evidence['qualification']['source_audit']
        ref.update(path=str(path),sha256=hashlib.sha256(data).hexdigest())
        self.policy.evidence['source_audit_sha256']=ref['sha256']
        self.policy.validate()
        other=copy.deepcopy(self.profile)
        other.update(kind='custom',argv=[str(self.executable)],runs_dir=str(root),trusted=True)
        other.pop('opencode')
        self.legacy.config['profiles']['other']=other
        original=opencode_files._open_readonly
        def opened(candidate):
            if Path(candidate)==path:raise AssertionError('other run output read')
            return original(candidate)
        with patch.object(opencode_files,'_open_readonly',side_effect=opened),self.assertRaises(ValueError):
            self.legacy.load()
