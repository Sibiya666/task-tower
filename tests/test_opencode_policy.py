"""Synthetic private policy fixtures do not provision native authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from task_tower import opencode_adapter as adapter
from task_tower import opencode_files


def sha(data):
    return hashlib.sha256(data).hexdigest()


class OpenCodePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.checkout = self.root/'checkout'
        self.checkout.mkdir()
        self.runs = self.root/'runs'
        self.runs.mkdir()
        self.evidence_path = self.root/'policy.json'
        self.refs = {}
        for name in ('source_audit', 'fixture_report', 'tool_policy'):
            path = self.root/(name+'.md')
            path.write_text('SYNTHETIC protocol fixture; no installed native authority.\n', encoding='utf-8')
            self.refs[name] = dict(path=str(path), sha256=sha(path.read_bytes()))
        from task_tower.opencode_files import identity
        candidates=['.agents','.claude','.opencode','AGENTS.md','opencode.json','opencode.jsonc']
        self.inventory = [dict(kind='missing',path=str(self.runs/name),role='candidate',parent_identity=dict(
            path=str(self.runs),identity=identity(self.runs.stat()),missing_components=[name])) for name in candidates]
        self.inventory.append(dict(kind='worktree_template',version=1,path='{runs_root}/{run_id}/{attempt_id}/worktree',
            role='launch_worktree',source_sha='a'*40,entries=[],ancestor_missing=candidates))
        self.environment = dict(names=[], presence_sha256='1'*64, values_sha256='2'*64)
        self.evidence = dict(version=1, policy_id='fixture-policy', native_version=adapter.VERSION,
            source_revision=adapter.SOURCE_REVISION, executable_sha256='3'*64,
            collector_revision=adapter.COLLECTOR_REVISION,
            source_audit_sha256=self.refs['source_audit']['sha256'], reviewer_id='distinct-fixture-reviewer',
            reviewed_at='2026-11-03T00:00:00Z',
            scope=dict(platform='windows', home=str(self.root/'home'), global_config=str(self.root/'home/.config/opencode'),
                       system_config=str(self.root/'system'), runs_root=str(self.runs), source_sha='a'*40,
                       worktree_template='{runs_root}/{run_id}/{attempt_id}/worktree'),
            inventory=self.inventory, environment=self.environment,
            qualification=dict(**self.refs, supported_surface_id=adapter.SURFACE_ID,
                               native_probe_authorized=False, native_run_authorized=False))
        self.policy = dict(version=adapter.VERSION, source_revision=adapter.SOURCE_REVISION,
            executable_sha256='3'*64, policy_id='fixture-policy', config_scope='existing-user-approved',
            config_discovery_sha256=adapter.discovery_digest(self.inventory, self.environment),
            policy_evidence_path=str(self.evidence_path), policy_evidence_sha256='0'*64,
            native_launch_authorized=False)

    def validate(self):
        self.policy['config_discovery_sha256']=adapter.discovery_digest(self.evidence['inventory'],self.evidence['environment'])
        data=json.dumps(self.evidence, sort_keys=True).encode()
        self.evidence_path.write_bytes(data)
        self.policy['policy_evidence_path']=str(self.evidence_path)
        self.policy['policy_evidence_sha256']=sha(data)
        return adapter.validate_opencode_policy(self.policy, checkouts=[self.checkout])

    def test_registered_bytes_do_not_grant_native_permissions(self):
        result=self.validate()
        self.assertFalse(result['native_launch_authorized'])
        self.assertEqual(set(result), set(self.policy))

    def test_closed_policy_and_evidence_types(self):
        for key,value in [('version','1.19.5'), ('source_revision','b'*40), ('extra',True),
                          ('native_launch_authorized',1), ('config_scope','trust-me')]:
            before=copy.deepcopy(self.policy)
            self.policy[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            self.policy=before
        for key,value in [('version',True), ('extra',True), ('collector_revision','other'),
                          ('source_audit_sha256','9'*64), ('reviewed_at','yesterday')]:
            before=copy.deepcopy(self.evidence)
            self.evidence[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate()
            self.evidence=before

    def test_permission_bits_are_exact_and_run_requires_probe(self):
        q=self.evidence['qualification']
        for key in ('native_probe_authorized','native_run_authorized'):
            for value in (1,'true',None):
                q[key]=value
                with self.subTest(key=key,value=value), self.assertRaises(ValueError): self.validate()
            q[key]=False
        q['native_run_authorized']=True
        with self.assertRaises(ValueError): self.validate()

    def test_references_are_pinned_private_bounded_utf8_files(self):
        ref=self.evidence['qualification']['source_audit']
        original=dict(ref)
        for change in (dict(extra=True), dict(sha256='9'*64), dict(path=str(self.checkout/'report')),
                       dict(path=str(self.runs/'report')), dict(path='relative')):
            ref.clear();ref.update(original|change)
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate()
        ref.clear();ref.update(original)
        path=Path(ref['path'])
        for data in (b'\xff', b'x'*1048577):
            path.write_bytes(data);ref['sha256']=sha(data);self.evidence['source_audit_sha256']=ref['sha256']
            with self.subTest(size=len(data)), self.assertRaises(ValueError): self.validate()

    def test_duplicate_evidence_keys_and_unpinned_bytes_rejected(self):
        self.validate()
        self.evidence_path.write_bytes(self.evidence_path.read_bytes().replace(b'"version": 1',b'"version": 1, "version": 1'))
        self.policy['policy_evidence_sha256']=sha(self.evidence_path.read_bytes())
        with self.assertRaises(ValueError): adapter.validate_opencode_policy(self.policy,checkouts=[self.checkout])
        self.validate()
        self.evidence_path.write_bytes(self.evidence_path.read_bytes()+b' ')
        with self.assertRaises(ValueError): adapter.validate_opencode_policy(self.policy,checkouts=[self.checkout])

    def test_inventory_identity_and_reconstructible_missing_parent(self):
        info=self.root.stat()
        identity=dict(device=str(info.st_dev),file_id=str(info.st_ino),kind='directory',reparse=False)
        row=dict(kind='missing',path=str(self.root/'absent'/'opencode.json'),role='project_config',
                 parent_identity=dict(path=str(self.root),identity=identity,missing_components=['absent','opencode.json']))
        self.evidence['inventory'].append(row)
        self.validate()
        for parts in ([],['..','opencode.json'],['absent/opencode.json'],['wrong','opencode.json']):
            original=list(row['parent_identity']['missing_components'])
            row['parent_identity']['missing_components']=parts
            with self.subTest(parts=parts), self.assertRaises(ValueError): self.validate()
            row['parent_identity']['missing_components']=original
        for field,value in [('device','01'),('device',str(2**128)),('file_id',True),('kind','file'),('reparse',True)]:
            original=identity[field];identity[field]=value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError): self.validate()
            identity[field]=original

    def test_windows_environment_case_collision_is_rejected(self):
        self.evidence['environment']['names']=['PATH','path']
        with self.assertRaises(ValueError): self.validate()

    def test_hardlinked_private_artifact_rejected(self):
        path=Path(self.refs['source_audit']['path'])
        alias=self.root/'alias'
        os.link(path,alias)
        with self.assertRaises(ValueError): self.validate()

    def test_known_native_state_cannot_be_relabelled_as_review_artifact(self):
        self.validate()
        for name in ('opencode.db','opencode-v2.db-wal','auth.json','kv.json','accounts.json','storage/token.json'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
            data=b'SYNTHETIC native state; must not be opened'
            path.write_bytes(data)
            ref=self.evidence['qualification']['source_audit']
            ref.update(path=str(path),sha256=sha(data));self.evidence['source_audit_sha256']=sha(data)
            actual=opencode_files._open_readonly
            def opened(candidate):
                if Path(candidate)==path:raise AssertionError('native state opened')
                return actual(candidate)
            with self.subTest(name=name),patch.object(opencode_files,'_open_readonly',side_effect=opened):
                with self.assertRaises(ValueError):self.validate()

    def test_known_native_state_cannot_be_policy_evidence(self):
        self.validate()
        original=self.evidence_path
        self.evidence_path=self.root/'opencode.db'
        with patch.object(opencode_files,'_open_readonly',side_effect=AssertionError('native database opened')):
            with self.assertRaises(ValueError):self.validate()
        self.evidence_path=original

    def test_unknown_no_follow_capability_refuses_before_open(self):
        flags=vars(os).get('O_NOFOLLOW')
        with patch.object(os,'name','posix'),patch.object(os,'open',side_effect=AssertionError('unsafe open reached')):
            with patch.dict(vars(os),{},clear=False):
                if 'O_NOFOLLOW' in vars(os):delattr(os,'O_NOFOLLOW')
                try:
                    with self.assertRaisesRegex(ValueError,'unsupported_safe_open'):
                        opencode_files._open_readonly(str(self.evidence_path))
                finally:
                    if flags is not None:setattr(os,'O_NOFOLLOW',flags)
