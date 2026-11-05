"""Synthetic mechanics only: never an installed six-role qualification."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from task_tower.processes import run_command

if importlib.util.find_spec('task_tower.beads_stage_roles'):
    from task_tower import beads_stage_roles as roles
else:
    roles = None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def binding():
    return dict(task='example:beads:project:task', session_id='session-1', run_id='run-1',
                attempt_id='attempt-1', instance_id='instance-1', actor='actor-1', stage='spec',
                policy_digest='1'*64, input_digest=digest(dict.fromkeys(
                    ('title', 'description', 'design', 'acceptance_criteria', 'notes'), '')),
                superpowers_digest='2'*64, base='a'*40, head='a'*40, tree='b'*40,
                diff_digest='3'*64, accepted_artifacts=[])


class RoleTests(unittest.TestCase):
    def test_phase_prefix_matching_uses_windows_casefold_without_rewriting_files(self):
        base=self.repository();before=roles.snapshot_source(self.root,base)
        (self.root/'owned.txt').write_bytes(b'case-matched DEV change')
        result=roles.verify_stage_source(self.root,before,role='dev_implementer',owned_paths=['OWNED.TXT'])
        self.assertEqual(result['outcome'],'ok')
        self.assertEqual(result['source']['files'][0]['name'],'owned.txt')
    def test_hash_cancels_between_real_file_chunks(self):
        event=threading.Event();path=self.root/'large.bin';path.write_bytes(b'x'*1048576)
        reads=[];original=roles._file
        class Stream:
            def __enter__(self):self.stream=path.open('rb');return self
            def __exit__(self,*a):self.stream.close()
            def read(self,size):
                data=self.stream.read(size);reads.append(len(data));event.set();return data
        class File:
            def open(self,*a):return Stream()
        with patch.object(roles,'_file',side_effect=lambda p,*a:File() if p==path else original(p,*a)):
            with self.assertRaises(ValueError):roles._hash_file(path,cancel_requested=event)
        self.assertEqual(reads,[65536])

    def test_git_actual_surrogate_observes_memory_cancellation_and_reaps(self):
        event=threading.Event();ready=self.root/'git-ready';facts=[]
        original=roles.run_command
        program='import sys,time;from pathlib import Path;Path(sys.argv[1]).write_bytes(b"ready");time.sleep(3)'
        def surrogate(argv,cwd,timeout,**kwargs):
            receipt=original([sys.executable,'-c',program,str(ready)],cwd,timeout,**kwargs)
            facts.append(receipt);return receipt
        def stop():
            deadline=time.monotonic()+3
            while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
            event.set()
        stopper=threading.Thread(target=stop,daemon=False);stopper.start()
        began=time.monotonic()
        with patch.object(roles,'run_command',side_effect=surrogate):
            with self.assertRaises(ValueError):roles._git(self.root,'status',cancel_requested=event)
        stopper.join(4)
        self.assertFalse(stopper.is_alive());self.assertLess(time.monotonic()-began,5)
        self.assertEqual(facts[0]['status'],'cancelled')
        self.assertTrue(facts[0]['cleanup_confirmed'])
        self.assertFalse(facts[0]['stdout_tail_unknown']);self.assertFalse(facts[0]['stderr_tail_unknown'])
    def test_phase_scope_is_live_immutable_and_cannot_be_replaced(self):
        authority=roles.RoleAuthority(approvals={},qualifications={},containment_verifier=lambda *a:None)
        record=authority.register_phase_scope('phase-instance',('tests/test_new.py',))
        self.assertIs(authority.get_phase_scope('phase-instance'),record)
        self.assertEqual(record.owned_paths,('tests/test_new.py',))
        with self.assertRaises(ValueError): authority.register_phase_scope('phase-instance',('src',))
        with self.assertRaises(ValueError): authority.register_phase_scope('bad-instance',('src','SRC/a'))
    def test_optional_cancellation_prevents_hash_git_and_snapshot_effects(self):
        event=threading.Event(); event.set()
        path=self.root/'cancelled'; path.write_bytes(b'payload')
        for action in (lambda:roles._hash_file(path,cancel_requested=event),
                       lambda:roles._git(self.root,'init',cancel_requested=event),
                       lambda:roles.snapshot_source(self.root,'a'*40,cancel_requested=event)):
            with self.assertRaises(ValueError): action()
        self.assertFalse((self.root/'.git').exists())

    def test_cancel_event_override_never_executes_in_source_helpers(self):
        event=threading.Event()
        event.is_set=lambda: (_ for _ in ()).throw(AssertionError('dynamic override'))
        path=self.root/'cancelled'; path.write_bytes(b'payload')
        self.assertEqual(roles._hash_file(path,cancel_requested=event),hashlib.sha256(b'payload').hexdigest())
        class BadEvent(threading.Event): pass
        with self.assertRaises(ValueError): roles._hash_file(path,cancel_requested=BadEvent())
    def setUp(self):
        self.assertIsNotNone(roles, 'independent stage-role wrapper is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def result(self, reviewer=False):
        value = dict(schema=1, kind='beads.role.result', binding=binding(), artifacts=[], findings=[])
        if reviewer:
            value.update(verdict='approve', reviewed=[])
        return value

    def write(self, value):
        path = self.root / 'result.json'
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def test_forged_copied_stale_cross_task_and_unknown_result_fields_refuse(self):
        for key in binding():
            value = self.result()
            value['binding'][key] = [] if key == 'accepted_artifacts' else 'forged'
            if key == 'accepted_artifacts':
                value['binding'][key] = [dict(name='earlier.md', sha256='a'*64)]
            with self.subTest(key=key), self.assertRaises(ValueError):
                roles.validate_role_result(self.write(value), binding(), reviewer=False)
        value = self.result(); value['accepted'] = True
        with self.assertRaises(ValueError):
            roles.validate_role_result(self.write(value), binding(), reviewer=False)

    def test_duplicate_keys_and_64k_overflow_refuse(self):
        path = self.write(self.result())
        path.write_text('{"schema":1,"schema":1}', encoding='utf-8')
        with self.assertRaises(ValueError):
            roles.validate_role_result(path, binding(), reviewer=False)
        path.write_bytes(b' ' * 65537)
        with self.assertRaises(ValueError):
            roles.validate_role_result(path, binding(), reviewer=False)

    def test_artifact_is_independently_hashed_and_reviewed_set_exact(self):
        (self.root / 'design.md').write_bytes(b'actual')
        value = self.result(True)
        value['artifacts'] = [dict(name='design.md', sha256=hashlib.sha256(b'actual').hexdigest())]
        self.assertEqual(roles.validate_role_result(self.write(value), binding(), reviewer=True)['verdict'], 'approve')
        (self.root / 'design.md').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            roles.validate_role_result(self.write(value), binding(), reviewer=True)
        value = self.result(True); value['reviewed'] = [dict(name='unknown', sha256='a'*64)]
        with self.assertRaises(ValueError):
            roles.validate_role_result(self.write(value), binding(), reviewer=True)

    def test_traversal_absolute_and_case_colliding_artifacts_refuse(self):
        for name in ('../escape', '/absolute', 'C:/absolute', 'a\\b', 'a/../b', 'a:stream', '.git/config'):
            value = self.result(); value['artifacts'] = [dict(name=name, sha256='a'*64)]
            with self.subTest(name=name), self.assertRaises(ValueError):
                roles.validate_role_result(self.write(value), binding(), reviewer=False)

    def test_hardlinked_artifact_refuses(self):
        original = self.root / 'original'; original.write_bytes(b'actual')
        os.link(original, self.root / 'linked')
        value = self.result(); value['artifacts'] = [dict(name='linked', sha256=hashlib.sha256(b'actual').hexdigest())]
        with self.assertRaises(ValueError):
            roles.validate_role_result(self.write(value), binding(), reviewer=False)


    def profile(self):
        exe = Path(sys.executable).resolve()
        instruction = self.root / 'instructions.md'; instruction.write_bytes(b'pinned instructions')
        return dict(schema=1, executable=str(exe), executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                    request_schema=1, result_schema=1, superpowers=[dict(path=str(instruction), sha256=hashlib.sha256(instruction.read_bytes()).hexdigest())],
                    variants={name: dict(argv=['{request}', '{result}', '{source}', '{output}'], containment_contract='qualified-backend-v1', prerequisite_sha256='a'*64)
                              for name in ('spec_output', 'dev_owned', 'review_readonly', 'test_sandbox')},
                    roles={key: dict(variant=variant, write_contract=contract) for key, variant, contract in (
                        ('spec_author', 'spec_output', 'spec_artifacts_only'), ('spec_acceptor', 'review_readonly', 'review_result_only'),
                        ('dev_implementer', 'dev_owned', 'owned_source_and_result'), ('dev_acceptor', 'review_readonly', 'review_result_only'),
                        ('test_executor', 'test_sandbox', 'disposable_test_and_result'), ('test_acceptor', 'review_readonly', 'review_result_only'))},
                    qualification_approval_reference='approval-1', production_qualification_sha256=None)

    def test_json_boolean_or_standalone_receipt_never_authorizes_profile(self):
        profile = self.profile()
        for authority in (True, dict(approved=True), dict(host_verified=True, independently_accepted=True)):
            with self.assertRaises(ValueError):
                roles.load_role_profile(self.write(profile), mode='qualification', authority=authority)

    def test_role_variant_remap_or_extra_role_refuses(self):
        for mutate in (lambda p: p['roles']['spec_acceptor'].update(variant='dev_owned'),
                       lambda p: p['roles'].update(extra=p['roles']['spec_author']),
                       lambda p: p['variants']['spec_output']['argv'].append('--approve_for_me')):
            profile = self.profile(); mutate(profile)
            with self.assertRaises(ValueError):
                roles.load_role_profile(self.write(profile), mode='qualification', authority=self.authority(profile))

    def authority(self, profile, **changes):
        approval = dict(schema=1, purpose='six_role_qualification_only', bundle_sha256=digest({k:v for k,v in profile.items() if k not in {'qualification_approval_reference', 'production_qualification_sha256'}}),
                        task=binding()['task'], source_manifest_sha256='b'*64, native_contract_sha256='c'*64,
                        roles=list(profile['roles']), max_calls=1, expires_at='2099-01-01T00:00:00+00:00')
        approval.update(changes)
        return roles.RoleAuthority(approvals={'approval-1': approval}, qualifications={},
            containment_verifier=lambda p, r, s, o, e: roles.ContainmentGrant(
                roles.bundle_digest(p), p['variants'][p['roles'][r['role']]['variant']]['prerequisite_sha256'], s, o, e, r['role']))

    def test_bootstrap_is_exact_bounded_not_production_qualification(self):
        profile = self.profile(); authority = self.authority(profile)
        path = self.write(profile)
        self.assertEqual(roles.load_role_profile(path, mode='qualification', authority=authority), profile)
        with self.assertRaises(ValueError):
            roles.load_role_profile(path, mode='production', authority=authority)
        for changes in (dict(expires_at='2000-01-01T00:00:00+00:00'), dict(bundle_sha256='0'*64)):
            with self.assertRaises(ValueError):
                roles.load_role_profile(path, mode='qualification', authority=self.authority(profile, **changes))
        request = dict(binding=binding(), role='spec_author', source_manifest=dict(manifest_sha256='b'*64))
        authority.reserve(profile, 'qualification', request, self.root, self.root, self.root)
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', request, self.root, self.root, self.root)

    def test_production_requires_separate_accepted_bundle_reference(self):
        profile = self.profile(); profile['production_qualification_sha256'] = 'd'*64
        authority = roles.RoleAuthority(approvals={}, qualifications={'d'*64: roles.bundle_digest(profile)}, containment_verifier=lambda *args: None)
        self.assertEqual(roles.load_role_profile(self.write(profile), mode='production', authority=authority), profile)
        profile['variants']['review_readonly']['argv'].append('--changed')
        with self.assertRaises(ValueError):
            roles.load_role_profile(self.write(profile), mode='production', authority=authority)

    def test_prior_artifacts_require_actual_host_file_rehash(self):
        profile = self.profile(); authority = self.authority(profile)
        request = dict(binding=binding(), role='spec_acceptor', source_manifest=dict(manifest_sha256='b'*64))
        request['binding']['accepted_artifacts'] = [dict(name='design.md', sha256='d'*64)]
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', request, self.root, self.root, self.root)
        artifact = self.root / 'host-design.md'; artifact.write_bytes(b'accepted design')
        authority = roles.RoleAuthority(approvals={}, qualifications={'d'*64: roles.bundle_digest(profile)},
                                        containment_verifier=lambda *args: None,
                                        accepted_artifact_paths={'design.md': artifact})
        profile['production_qualification_sha256'] = 'd'*64
        request['binding']['accepted_artifacts'][0]['sha256'] = hashlib.sha256(b'accepted design').hexdigest()
        authority._check(profile, 'production', request)
        artifact.write_bytes(b'changed upstream')
        with self.assertRaises(ValueError):
            authority._check(profile, 'production', request)

    def artifact_api(self, authority):
        self.assertTrue(callable(getattr(authority, 'register_accepted_artifact', None)),
                        'same live authority needs immutable accepted-artifact registration')
        self.assertTrue(callable(getattr(authority, 'get_accepted_artifact', None)),
                        'qualified verifier needs pure memory artifact lookup')

    def test_artifact_registration_preserves_live_instance_and_call_guards(self):
        from dataclasses import FrozenInstanceError
        from unittest.mock import patch
        profile = self.profile(); authority = self.authority(profile, max_calls=2)
        self.artifact_api(authority)
        old_verifier = authority._verifier

        def verifier(p, r, s, o, e):
            from dataclasses import replace
            return replace(old_verifier(p, r, s, o, e), accepted_artifacts=tuple(
                authority.get_accepted_artifact(item['name']) for item in r['binding']['accepted_artifacts']))

        authority._verifier = verifier
        request = dict(binding=binding(), role='spec_author', source_manifest=dict(manifest_sha256='b'*64))
        source, output, evidence = (self.root / name for name in ('source', 'output', 'evidence'))
        for path in (source, output, evidence): path.mkdir()
        authority.reserve(profile, 'qualification', request, source, output, evidence)
        path = self.root / 'accepted-design.md'; path.write_bytes(b'independently accepted fixture')
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        extra = self.root / 'extra'; extra.mkdir()
        entry = authority.register_accepted_artifact('spec/design.md', extra / '..' / path.name, expected)
        self.assertEqual((entry.name, entry.path, entry.sha256), ('spec/design.md', path, expected))
        with patch('task_tower.beads_stage_roles._read_artifact_input', side_effect=AssertionError('getter did filesystem work')):
            self.assertIs(authority.get_accepted_artifact('spec/design.md'), entry)
        with self.assertRaises(FrozenInstanceError): entry.sha256 = '0'*64
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', request, source, output, evidence)
        request['binding'].update(attempt_id='second-attempt', instance_id='second-instance',
                                  accepted_artifacts=[dict(name=entry.name, sha256=entry.sha256)])
        grant = authority.reserve(profile, 'qualification', request, source, output, evidence)
        self.assertIs(grant.accepted_artifacts[0], entry)
        request['binding'].update(attempt_id='third-attempt', instance_id='third-instance')
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', request, source, output, evidence)

    def test_artifact_registration_rejects_replacement_wrong_hash_unsafe_linked_and_oversized(self):
        profile = self.profile(); authority = self.authority(profile)
        self.artifact_api(authority)
        path = self.root / 'accepted.md'; path.write_bytes(b'accepted fixture')
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        authority.register_accepted_artifact('design.md', path, expected)
        for name in ('design.md', 'DESIGN.MD', '../escape', '/absolute', 'C:/absolute', 'a:stream', 'COM1', 'space name.md', '[output].md'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                authority.register_accepted_artifact(name, path, expected)
        with self.assertRaises(ValueError): authority.register_accepted_artifact('wrong-hash.md', path, '0'*64)
        with self.assertRaises(ValueError): authority.register_accepted_artifact('directory.md', self.root, expected)
        with self.assertRaises(ValueError): authority.register_accepted_artifact('relative.md', Path('relative.md'), expected)
        linked = self.root / 'linked.md'; os.link(path, linked)
        with self.assertRaises(ValueError): authority.register_accepted_artifact('linked.md', linked, expected)
        large = self.root / 'oversized.md'; large.write_bytes(b'a'*(16*1024*1024+1))
        with self.assertRaises(ValueError):
            authority.register_accepted_artifact('oversized.md', large, hashlib.sha256(large.read_bytes()).hexdigest())

    def test_constructor_artifact_pin_cannot_be_replaced_by_changed_request_digest(self):
        profile = self.profile(); profile['production_qualification_sha256'] = 'd'*64
        path = self.root / 'design.md'; path.write_bytes(b'original accepted artifact')
        authority = roles.RoleAuthority(approvals={}, qualifications={'d'*64:roles.bundle_digest(profile)},
            containment_verifier=lambda *args: None, accepted_artifact_paths={'design.md':path})
        request = dict(binding=binding())
        path.write_bytes(b'changed without independent acceptance')
        request['binding']['accepted_artifacts'] = [dict(name='design.md', sha256=hashlib.sha256(path.read_bytes()).hexdigest())]
        with self.assertRaises(ValueError):
            authority._check(profile, 'production', request)

    def test_artifact_in_current_evidence_refuses_before_containment_verifier(self):
        profile = self.profile(); approval = self.authority(profile)._approvals
        source, output, evidence = (self.root / name for name in ('source', 'output', 'evidence'))
        for directory in (source, output, evidence): directory.mkdir()
        path = evidence / 'accepted.md'; path.write_bytes(b'private evidence must not become input')
        calls = []

        def verifier(p, r, s, o, e):
            calls.append('exposure attempted')
            return roles.ContainmentGrant(roles.bundle_digest(p), 'a'*64, s, o, e, r['role'])

        authority = roles.RoleAuthority(approvals=approval, qualifications={}, containment_verifier=verifier,
                                        accepted_artifact_paths={'design.md':path})
        request = dict(binding=binding(), role='spec_author', source_manifest=dict(manifest_sha256='b'*64))
        request['binding']['accepted_artifacts'] = [dict(name='design.md', sha256=hashlib.sha256(path.read_bytes()).hexdigest())]
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', request, source, output, evidence)
        self.assertEqual(calls, [])

    def artifact_invocation(self, *, mode='role'):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        self.artifact_api(authority)
        inputs = workspace / 'accepted'; inputs.mkdir()
        entries = []
        for name, content in (('design.md', b'accepted design fixture'), ('plan.md', b'accepted plan fixture')):
            path = inputs / name; path.write_bytes(content)
            entries.append(authority.register_accepted_artifact(name, path, hashlib.sha256(content).hexdigest()))
        if mode != 'role':
            for variant in profile['variants'].values():
                variant['argv'][1] = mode; variant['argv'].append(str(entries[0].path))
            authority._approvals['approval-1']['bundle_sha256'] = roles.bundle_digest(profile)
        request['binding']['accepted_artifacts'] = [dict(name=e.name, sha256=e.sha256) for e in entries]
        verifier = authority._verifier

        def expose(p, r, s, o, e):
            from dataclasses import replace
            return replace(verifier(p, r, s, o, e), accepted_artifacts=tuple(
                authority.get_accepted_artifact(a['name']) for a in r['binding']['accepted_artifacts']))

        authority._verifier = expose
        return workspace, profile, authority, request, output, evidence, entries

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_explicit_exact_artifact_exposure_completes_with_hash_recheck(self):
        workspace, profile, authority, request, output, evidence, entries = self.artifact_invocation()
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertTrue(result['process']['cleanup_confirmed'])
        self.assertTrue(result['process']['eof_confirmed'])

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_missing_incomplete_extra_reordered_or_copied_artifact_exposure_refuses(self):
        from dataclasses import replace
        original = self.root
        for case in ('missing', 'incomplete', 'extra', 'reordered', 'copied', 'list'):
            with self.subTest(case=case):
                self.root = original / case; self.root.mkdir()
                workspace, profile, authority, request, output, evidence, entries = self.artifact_invocation()
                verifier = authority._verifier

                def invalid(p, r, s, o, e):
                    grant = verifier(p, r, s, o, e); actual = grant.accepted_artifacts
                    values = {'missing': (), 'incomplete': actual[:1], 'extra': actual+actual[:1],
                              'reordered': actual[::-1], 'copied': (replace(actual[0]), actual[1]), 'list': list(actual)}
                    return replace(grant, accepted_artifacts=values[case])

                authority._verifier = invalid
                result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                        source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
                self.assertEqual(result['outcome'], 'refused', result)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_changed_accepted_artifact_after_process_is_not_accepted(self):
        workspace, profile, authority, request, output, evidence, entries = self.artifact_invocation(mode='role-change-accepted-artifact')
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'unknown', result)
        self.assertEqual(entries[0].path.read_bytes(), b'changed accepted artifact')

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_artifact_change_during_containment_preparation_refuses_before_launch(self):
        workspace, profile, authority, request, output, evidence, entries = self.artifact_invocation()
        verifier = authority._verifier

        def changed(p, r, s, o, e):
            grant = verifier(p, r, s, o, e)
            entries[0].path.write_bytes(b'changed while preparing containment')
            return grant

        authority._verifier = changed
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'refused', result)
        self.assertFalse((output / 'result.json').exists())

    def test_all_six_role_grants_preserve_fixed_permissions_and_fresh_instances(self):
        profile = self.profile(); authority = self.authority(profile, max_calls=12)
        for i, role in enumerate(('spec_author', 'spec_acceptor', 'dev_implementer', 'dev_acceptor', 'test_executor', 'test_acceptor')):
            b = binding(); b.update(actor='actor-%d' % i, attempt_id='attempt-%d' % i, instance_id='instance-%d' % i)
            request = dict(binding=b, role=role, source_manifest=dict(manifest_sha256='b'*64))
            grant = authority.reserve(profile, 'qualification', request, self.root, self.root, self.root)
            self.assertEqual(grant.role, role)
        b = binding(); b.update(actor='actor-0', attempt_id='new', instance_id='new')
        with self.assertRaises(ValueError):
            authority.reserve(profile, 'qualification', dict(binding=b, role='spec_acceptor', source_manifest=dict(manifest_sha256='b'*64)), self.root, self.root, self.root)

    def test_case_insensitive_credentials_and_private_environment_are_absent(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'gH_ToKeN':'private', 'Github_token':'private', 'BEADS_DIR':'private',
                                    'CODEX_HOME':'private', 'TASK_TOWER_BEADS':'private', 'CUSTOM_SECRET':'private'}):
            self.assertNotIn('private', roles._environment().values())

    def test_unknown_containment_refuses_without_launch(self):
        request = dict(schema=1, kind='beads.role.request', binding=binding(), role='spec_author',
                       criteria=dict.fromkeys(('title', 'description', 'design', 'acceptance_criteria', 'notes'), ''),
                       source_manifest={}, output_names=['design.md'])
        result = roles.run_role(self.profile(), request, mode='production', authority=object(),
                                source=self.root, output=self.root, evidence=self.root, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'refused')
        self.assertNotIn('argv', result)

    def git(self, *args):
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='NUL')
        return subprocess.check_output(['git', '-c', 'core.hooksPath=NUL', '-c', 'core.excludesFile=NUL', *args], cwd=self.root, env=env).decode().strip()

    def repository(self):
        self.git('init', '-q'); self.git('config', 'user.name', 'Fixture'); self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'owned.txt').write_bytes(b'base')
        self.git('add', 'owned.txt'); self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def test_authorized_dev_delta_becomes_new_checkpoint(self):
        base = self.repository(); before = roles.snapshot_source(self.root, base)
        (self.root / 'owned.txt').write_bytes(b'changed')
        result = roles.verify_stage_source(self.root, before, role='dev_implementer', owned_paths=['owned.txt'])
        self.assertEqual(result['outcome'], 'ok')
        self.assertNotEqual(result['source']['manifest_sha256'], before['manifest_sha256'])
        self.assertEqual(roles.verify_stage_source(self.root, result['source'], role='test_executor', owned_paths=[])['outcome'], 'ok')

    def test_real_public_unicode_space_and_bracket_source_paths_are_supported(self):
        self.repository()
        paths = [
            'overlay/vendor/webview2/sdk/[Content_Types].xml',
            'reports/Пробелы архитектуры агентной разработки.md',
            'research_notes/Пробелы архитектуры агентной разработки/evaluation.md',
            'research_notes/Пробелы архитектуры агентной разработки/products.md',
            'research_notes/Пробелы архитектуры агентной разработки/runtime.md',
        ]
        for name in paths:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'public source fixture')
        self.git('add', '--all'); self.git('commit', '-qm', 'public source path fixture')
        base = self.git('rev-parse', 'HEAD')
        try:
            before = roles.snapshot_source(self.root, base)
        except ValueError:
            self.fail('valid tracked public Unicode/space/bracket source paths were refused')
        self.assertEqual({item['name'] for item in before['files']}, {'owned.txt', *paths})
        (self.root / paths[4]).write_bytes(b'owned DEV change')
        owned = ['research_notes/Пробелы архитектуры агентной разработки']
        result = roles.verify_stage_source(self.root, before, role='dev_implementer', owned_paths=owned)
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertNotEqual(result['source']['manifest_sha256'], before['manifest_sha256'])
        self.assertEqual(roles.verify_stage_source(self.root, result['source'], role='test_executor', owned_paths=[])['outcome'], 'ok')
        for role, prefixes in (('test_executor', []), ('spec_author', owned), ('dev_implementer', ['reports'])):
            with self.subTest(role=role, owned=prefixes):
                self.assertEqual(roles.verify_stage_source(self.root, before, role=role, owned_paths=prefixes)['outcome'], 'refused')

    def test_source_validator_preserves_windows_path_guards(self):
        validator = getattr(roles, '_source_name', None)
        self.assertIsNotNone(validator, 'source paths need a separate Windows-safe validator')
        unsafe = ['', '.', '..', 'a/../b', 'a/./b', 'a//b', '/absolute', '//server/share',
                  'C:/absolute', 'C:relative', 'a\\b', '\\\\server\\share', 'a:stream',
                  'bad<name', 'bad>name', 'bad|name', 'bad?name', 'bad*name', 'bad"name',
                  'bad\x00name', 'bad\nname', 'bad\x7fname', 'bad\x85name', 'a./file', 'a /file',
                  '.git/config', 'a/.GiT/config', 'CON', 'prn.txt', 'AUX.md', 'NUL',
                  'COM1.txt', 'COM9', 'LPT1', 'lpt9.txt', 'COM¹', 'COM².txt', 'COM³',
                  'LPT¹', 'LPT².txt', 'lpt³', 'CON .txt', 'a'*241]
        for name in unsafe:
            with self.subTest(name=ascii(name)), self.assertRaises(ValueError):
                validator(name)

    def test_source_permissions_and_generated_artifact_names_remain_distinct(self):
        profile = self.profile()
        authority = self.authority(profile)
        # Grant validation is a separate ownership-prefix call site from source
        # enumeration; it must accept exactly the same safe source vocabulary.
        authority._verifier = lambda p, r, s, o, e: roles.ContainmentGrant(
            roles.bundle_digest(p), 'a'*64, s, o, e, r['role'],
            ('research_notes/Пробелы архитектуры агентной разработки', 'sdk/[Content_Types].xml'))
        request = dict(binding=binding(), role='dev_implementer', source_manifest=dict(manifest_sha256='b'*64))
        try:
            grant = authority.reserve(profile, 'qualification', request, self.root, self.root, self.root)
        except ValueError:
            self.fail('valid Unicode/space/bracket ownership grant was refused')
        self.assertEqual(len(grant.owned_paths), 2)
        for name in ('reports/Пробелы архитектуры агентной разработки.md', 'space name.md', '[Content_Types].xml',
                     '../escape', 'a:stream', 'COM¹.txt', '.git/config'):
            with self.subTest(name=ascii(name)), self.assertRaises(ValueError):
                roles._name(name)

    def test_nondev_outside_owned_mutation_and_stale_base_refuse(self):
        base = self.repository(); before = roles.snapshot_source(self.root, base)
        (self.root / 'owned.txt').write_bytes(b'changed')
        for role, owned in (('spec_author', ['owned.txt']), ('dev_acceptor', []), ('test_executor', []), ('dev_implementer', ['other'])):
            self.assertEqual(roles.verify_stage_source(self.root, before, role=role, owned_paths=owned)['outcome'], 'refused')
        bad = copy.deepcopy(before); bad['base'] = '0'*40
        self.assertEqual(roles.verify_stage_source(self.root, bad, role='dev_implementer', owned_paths=['owned.txt'])['outcome'], 'refused')

    def test_source_configuration_changes_invalidate_checkpoint(self):
        base = self.repository(); before = roles.snapshot_source(self.root, base)
        self.git('config', 'user.name', 'Changed')
        self.assertEqual(roles.verify_stage_source(self.root, before, role='test_executor', owned_paths=[])['outcome'], 'refused')

    def test_unreadable_nested_untracked_subtree_refuses_source_enumeration(self):
        from unittest.mock import patch
        base = self.repository(); before = roles.snapshot_source(self.root, base)
        nested = self.root / 'untracked' / 'nested'; nested.mkdir(parents=True)
        (nested / 'hidden-by-enumeration-error.txt').write_bytes(b'changed source')
        original = os.scandir
        attempted = []

        def fail_nested(path):
            if Path(path) == nested:
                attempted.append(True)
                raise OSError('synthetic enumeration failure; no ACL modification')
            return original(path)

        with patch('task_tower.beads_stage_roles.os.scandir', side_effect=fail_nested):
            with self.subTest(operation='snapshot'), self.assertRaises(OSError):
                roles.snapshot_source(self.root, base)
            with self.subTest(operation='verification'):
                result = roles.verify_stage_source(self.root, before, role='test_executor', owned_paths=[])
                self.assertEqual(result['outcome'], 'refused')
        self.assertTrue(attempted)

    def synthetic_invocation(self):
        workspace = self.root
        self.root = workspace / 'source'; self.root.mkdir()
        output, evidence = workspace / 'output', workspace / 'evidence'
        output.mkdir(); evidence.mkdir()
        base = self.repository()
        profile = self.profile()
        fixture = Path(__file__).parent / 'fixtures' / 'beads_stages' / 'role_child.py'
        profile['superpowers'].append(dict(path=str(fixture.resolve()), sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
        for variant in profile['variants'].values():
            variant['argv'] = [str(fixture.resolve()), 'role', '{request}', '{result}', '{source}', '{output}']
        snapshot = roles.snapshot_source(self.root, base)
        b = binding(); b.update({k:snapshot[k] for k in ('base', 'head', 'tree', 'diff_digest')})
        b['superpowers_digest'] = digest(profile['superpowers'])
        authority = self.authority(profile, source_manifest_sha256=snapshot['manifest_sha256'])
        request = dict(schema=1, kind='beads.role.request', binding=b, role='spec_author',
                       criteria=dict.fromkeys(('title','description','design','acceptance_criteria','notes'), ''),
                       source_manifest=snapshot, output_names=[])
        request['criteria']['notes'] = 'UNTRUSTED --approve_for_me shell command'
        request['binding']['input_digest'] = digest(request['criteria'])
        return workspace, profile, authority, request, output, evidence

    def referenced_invocation(self, *, large=False, mode='role', qualified=True):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        if large:
            directory = self.root / 'complete-inventory'; directory.mkdir()
            for index in range(640):
                (directory / ('source-%04d-with-public-name-and-content.txt' % index)).write_bytes(b'complete source')
        snapshot = roles.snapshot_source(self.root, request['binding']['base'])
        inputs = workspace / 'inputs'; inputs.mkdir()
        input_path = inputs / 'source.json'
        raw = json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        input_path.write_bytes(raw)
        reference = dict(name='source-checkpoint-1', sha256=hashlib.sha256(raw).hexdigest())
        if mode != 'role':
            for variant in profile['variants'].values():
                variant['argv'][1] = mode
                if mode == 'role-change-source-input':
                    variant['argv'].append(str(input_path))
        if mode == 'role-dev-delta':
            request['role'] = 'dev_implementer'; request['binding']['stage'] = 'development'
        request['source_manifest'] = reference
        request['binding'].update({key:snapshot[key] for key in ('base','head','tree','diff_digest')})
        approval = self.authority(profile, source_manifest_sha256=snapshot['manifest_sha256'])._approvals

        def verify(p, r, s, o, e):
            return roles.ContainmentGrant(roles.bundle_digest(p), 'a'*64, s, o, e, r['role'],
                ('owned.txt',) if mode == 'role-dev-delta' else (),
                source_input=authority.get_source_input(r['source_manifest']['name']) if qualified else None)

        try:
            authority = roles.RoleAuthority(approvals=approval, qualifications={}, containment_verifier=verify,
                                             source_input_paths={reference['name']:input_path})
        except TypeError:
            self.fail('coordinator-held source input registration is unavailable')
        return workspace, profile, authority, request, output, evidence, snapshot, input_path

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_complete_large_source_manifest_uses_small_reference_and_exact_bootstrap_pin(self):
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation(large=True)
        self.assertGreater(len(input_path.read_bytes()), 65536)
        self.assertLess(len(json.dumps(request).encode('utf-8')), 65536)
        self.assertEqual(len(snapshot['files']), 642)
        self.assertNotEqual(snapshot['manifest_sha256'], request['source_manifest']['sha256'])
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertEqual(result['source'], snapshot)
        self.assertEqual(result['event']['source_input'], request['source_manifest'])
        # Qualification binds the internal complete source digest, not file SHA.
        authority._approvals['approval-1']['source_manifest_sha256'] = request['source_manifest']['sha256']
        with self.assertRaises(ValueError):
            authority._check(profile, 'qualification', request)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_source_input_change_after_role_is_not_accepted(self):
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation(mode='role-change-source-input')
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'unknown')
        self.assertNotEqual(input_path.read_bytes(), json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_source_input_preserves_legitimate_owned_dev_delta(self):
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation(mode='role-dev-delta')
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertNotEqual(result['source']['manifest_sha256'], snapshot['manifest_sha256'])
        self.assertEqual(hashlib.sha256(input_path.read_bytes()).hexdigest(), request['source_manifest']['sha256'])

    def test_host_input_registration_is_canonical_immutable_and_memory_getter_is_pure(self):
        from unittest.mock import patch
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation()
        extra = input_path.parent / 'extra'; extra.mkdir()
        alias = extra / '..' / input_path.name
        entry = authority.register_source_input('next-checkpoint', alias)
        self.assertEqual(entry.path, input_path)
        with patch('task_tower.beads_stage_roles._read_snapshot_input', side_effect=AssertionError('getter performed filesystem IO')):
            self.assertIs(authority.get_source_input('next-checkpoint'), entry)
        with self.assertRaises(ValueError):
            authority.register_source_input('next-checkpoint', input_path)
        with self.assertRaises(ValueError):
            authority.register_source_input('NEXT-CHECKPOINT', input_path)

    def test_source_input_registration_rejects_noncanonical_duplicate_oversized_and_invalid_snapshots(self):
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation()
        raw = input_path.read_bytes()
        for name, invalid in (
                ('noncanonical', json.dumps(snapshot, indent=2).encode('utf-8')),
                ('duplicate', raw.replace(b'{', b'{"base":"duplicate",', 1)),
                ('oversized', b' '*(16*1024*1024+1)),
                ('invalid-schema', b'{}')):
            input_path.write_bytes(invalid)
            with self.subTest(case=name), self.assertRaises(ValueError):
                authority.register_source_input(name, input_path)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_copied_readonly_source_record_is_not_the_registered_live_exposure(self):
        from dataclasses import replace
        workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation()
        verifier = authority._verifier

        def copied(p, r, s, o, e):
            grant = verifier(p, r, s, o, e)
            entry = grant.source_input
            return replace(grant, source_input=roles.ReadOnlySourceInput(entry.name, entry.sha256, entry.path))

        authority._verifier = copied
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'refused', result)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_missing_forged_stale_noncanonical_unsafe_and_unqualified_source_refs_refuse(self):
        original = self.root
        for case in ('missing', 'forged', 'stale', 'modified', 'noncanonical', 'duplicate', 'traversal',
                     'slash-name', 'oversized', 'hardlink', 'candidate', 'output', 'evidence', 'unqualified'):
            with self.subTest(case=case):
                self.root = original / case; self.root.mkdir()
                workspace, profile, authority, request, output, evidence, snapshot, input_path = self.referenced_invocation(qualified=case != 'unqualified')
                ref = request['source_manifest']
                if case == 'missing':
                    ref['name'] = 'not-registered'
                elif case == 'forged':
                    ref['sha256'] = '0'*64
                elif case == 'stale':
                    snapshot['files'] = []
                    snapshot['manifest_sha256'] = digest({k:v for k,v in snapshot.items() if k != 'manifest_sha256'})
                    input_path.write_bytes(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
                    ref['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()
                    authority._approvals['approval-1']['source_manifest_sha256'] = snapshot['manifest_sha256']
                    entry = authority.register_source_input('stale-source', input_path)
                    ref.update(name=entry.name, sha256=entry.sha256)
                elif case == 'modified':
                    input_path.write_bytes(b'changed')
                elif case == 'noncanonical':
                    input_path.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
                    ref['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()
                elif case == 'duplicate':
                    raw = input_path.read_bytes().replace(b'{', b'{"base":"duplicate",', 1)
                    input_path.write_bytes(raw); ref['sha256'] = hashlib.sha256(raw).hexdigest()
                elif case in ('traversal', 'slash-name'):
                    ref['name'] = '../source' if case == 'traversal' else 'inputs/source'
                elif case == 'oversized':
                    input_path.write_bytes(b' ' * (16*1024*1024+1))
                    ref['sha256'] = hashlib.sha256(input_path.read_bytes()).hexdigest()
                elif case == 'hardlink':
                    os.link(input_path, workspace / 'linked-input')
                elif case in ('candidate', 'output', 'evidence'):
                    target = {'candidate':self.root, 'output':output, 'evidence':evidence}[case] / 'input.json'
                    target.write_bytes(input_path.read_bytes())
                    entry = authority.register_source_input('unsafe-root-source', target)
                    ref.update(name=entry.name, sha256=entry.sha256)
                result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                        source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
                self.assertEqual(result['outcome'], 'refused', result)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_synthetic_role_process_requires_host_completion_and_rejects_reuse(self):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=threading.Event())
        self.assertEqual(result['outcome'], 'ok', result)
        self.assertEqual(result['reason'], 'execution_completed')
        self.assertNotIn('UNTRUSTED', json.dumps(result['event']))
        self.assertTrue(result['process']['eof_confirmed'])
        self.assertEqual(result['process'].get('stdout_sha256'), hashlib.sha256(b'').hexdigest())
        self.assertEqual(result['process'].get('stdout_captured_bytes'), 0)
        self.assertNotIn('accepted', result)
        # A second fresh output directory still cannot revive an old context.
        output2, evidence2 = workspace / 'output2', workspace / 'evidence2'
        output2.mkdir(); evidence2.mkdir()
        result2 = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output2, evidence=evidence2, cancel_requested=threading.Event())
        self.assertEqual(result2['outcome'], 'refused')

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_event_subclass_is_refused_without_calling_override(self):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        calls = []

        class ExternalEvent(threading.Event):
            def is_set(self):
                calls.append('external callback')
                return True

        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=ExternalEvent())
        self.assertEqual(calls, [])
        self.assertEqual(result['outcome'], 'refused')

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_exact_event_instance_override_is_ignored(self):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        calls = []
        event = threading.Event()
        event.is_set = lambda: calls.append('external callback') or True
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=event)
        self.assertEqual(calls, [])
        self.assertEqual(result['outcome'], 'ok', result)

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_corrupted_event_flag_never_invokes_arbitrary_truthiness(self):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        calls = []

        class ExternalTruth:
            def __bool__(self):
                calls.append('external truthiness')
                return True

        event = threading.Event(); event._flag = ExternalTruth()
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=event)
        self.assertEqual(calls, [])
        self.assertEqual(result['outcome'], 'refused')

    @unittest.skipUnless(os.name == 'nt', 'synthetic actual Windows invocation')
    def test_standard_set_event_cancels_without_launch(self):
        workspace, profile, authority, request, output, evidence = self.synthetic_invocation()
        event = threading.Event(); event.set()
        result = roles.run_role(profile, request, mode='qualification', authority=authority,
                                source=self.root, output=output, evidence=evidence, cancel_requested=event)
        self.assertNotEqual(result['outcome'], 'ok')
        self.assertEqual(result['process']['status'], 'cancelled')
        self.assertIsNone(result['process']['pid'])


@unittest.skipUnless(os.name == 'nt', 'actual Windows Job mechanics')
class NativeRoleMechanicsTests(unittest.TestCase):
    """Actual harmless processes. These do not qualify a model/containment profile."""
    fixture = Path(__file__).parent / 'fixtures' / 'beads_stages' / 'role_child.py'

    def setUp(self):
        self.assertTrue(self.fixture.is_file(), 'bounded native fixture missing')

    def run_tree(self, mode, cancelled=False):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve(); capture = root / 'capture'; capture.mkdir()
            start = time.monotonic()
            result = run_command([sys.executable, str(self.fixture), mode, str(root)], root, .5,
                capture=dict(directory=capture, max_bytes_per_stream=1024),
                cancel_requested=lambda: cancelled and time.monotonic()-start > .4)
            self.assertEqual(result['status'], 'cancelled' if cancelled else 'timeout')
            self.assertTrue(result['cleanup_confirmed'])
            self.assertTrue((root / 'grandchild-ready').is_file())
            for stream in ('stdout', 'stderr'):
                self.assertFalse(result[stream+'_tail_unknown'])
            time.sleep(1.2)
            self.assertFalse((root / 'child-escaped').exists())
            self.assertFalse((root / 'grandchild-escaped').exists())

    def test_timeout_kills_child_and_grandchild_and_reaches_eof(self):
        self.run_tree('tree')

    def test_cancel_reaps_owned_tree(self):
        self.run_tree('tree', cancelled=True)

    def test_saturated_output_preserves_bounds_and_eof(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve()
            result = run_command([sys.executable, str(self.fixture), 'flood', str(root)], root, 5,
                capture=dict(directory=root, max_bytes_per_stream=1024), cancel_requested=lambda: False)
            self.assertEqual(result['status'], 'passed')
            self.assertTrue(result['cleanup_confirmed'])
            for stream, byte in (('stdout', b'a'), ('stderr', b'b')):
                self.assertEqual(result[stream+'_bytes'], 200000)
                self.assertEqual(result[stream+'_sha256'], hashlib.sha256(byte*200000).hexdigest())
                self.assertEqual((root / (stream+'.log')).read_bytes(), byte*1024)
                self.assertFalse(result[stream+'_tail_unknown'])

    def test_abrupt_supervisor_death_closes_job_tree(self):
        # Own only the Popen handle created here; descendants self-exit <= 2 s
        # even if containment fails. Never kill/adopt a PID from child output.
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve()
            process = subprocess.Popen([sys.executable, str(self.fixture), 'supervisor', str(root)],
                cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                stdout, stderr = process.communicate(timeout=1.5)
                self.assertEqual(process.returncode, 23)
                self.assertEqual(stderr, b'')
                self.assertTrue((root / 'grandchild-ready').is_file())
                time.sleep(1.2)
                self.assertFalse((root / 'grandchild-escaped').exists())
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=4)

    def test_only_stream_handles_inherited(self):
        import ctypes
        import msvcrt
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve()
            with (root / 'private').open('wb') as private:
                handle = msvcrt.get_osfhandle(private.fileno())
                os.set_handle_inheritable(handle, True)
                result = run_command([sys.executable, str(self.fixture), 'handle', str(root), str(handle)], root, 5,
                    capture=dict(directory=root, max_bytes_per_stream=1024), cancel_requested=lambda: False)
                self.assertEqual(result['status'], 'passed')
                self.assertEqual((root / 'private').read_bytes(), b'')

    def test_reader_cannot_write_candidate_or_host_evidence(self):
        self.skipTest('no independently qualified installed read-only containment backend; not native isolation proof')
