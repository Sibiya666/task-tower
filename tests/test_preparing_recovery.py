"""Receipt/source component only; preparing preflight is preserved for B2."""
import unittest
from unittest.mock import patch
from task_tower import preparing_recovery as recovery
from tests.fixtures.preparing_recovery import GitCase,ENGINE,PRIOR,receipt

class ReceiptTests(unittest.TestCase):
    def approve(self,value):
        return {'project1':frozenset({recovery.fingerprint(value)})}

    def validate(self,value,approved=None,**changes):
        options=dict(connector_id='host1',source_sha=ENGINE)
        options.update(changes)
        return recovery.validate_receipt(value,self.approve(value) if approved is None else approved,**options)

    def test_explicit_exact_digest_returns_independent_snapshot(self):
        value=receipt();result=self.validate(value)
        self.assertEqual(result,value)
        self.assertIsNot(result,value)
        value['operation_id']='different'
        self.assertEqual(result['operation_id'],'op-1')

    def test_canonical_fingerprint_matches_existing_encoding(self):
        import hashlib
        from task_tower.service.store import encoded
        value=receipt()
        self.assertEqual(recovery.fingerprint(value),hashlib.sha256(encoded(value).encode('utf-8')).hexdigest())
        self.assertEqual(recovery.fingerprint(value),recovery.fingerprint(dict(reversed(list(value.items())))))

    def test_missing_foreign_project_or_mutated_approval_denies(self):
        value=receipt();approved=self.approve(value)
        for registry in ({},{'foreign':approved['project1']},{'project1':frozenset({'0'*64})}):
            with self.subTest(registry=registry),self.assertRaises(ValueError):self.validate(value,registry)
        changed=dict(value,command_id='different')
        with self.assertRaises(ValueError):self.validate(changed,approved)

    def test_connector_and_actual_engine_source_must_match(self):
        for changes in (dict(connector_id='other'),dict(source_sha='c'*40),dict(source_sha=None)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.validate(receipt(),**changes)

    def test_malformed_or_widened_envelopes_deny_even_with_matching_digest(self):
        value=receipt();cases=[]
        for field in value:
            missing=dict(value);del missing[field];cases.append(missing)
        cases.extend([dict(value,approved=True),dict(value,version=True),dict(value,action='resume'),
            dict(value,branch='main'),dict(value,branch_sha='c'*40),dict(value,prior_engine_sha='d'*40),
            dict(value,attempt_id='../attempt1'),dict(value,bead_id='nothyphenated')])
        for field in ('base_sha','engine_sha','prior_engine_sha','branch_sha','command_sha256','worktree_sha256','cleanup_sha256'):
            cases.extend([dict(value,**{field:None}),dict(value,**{field:'F'*len(value[field])})])
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):self.validate(case)

    def test_unknown_and_mutated_old_command_or_worktree_fingerprints_deny(self):
        value=receipt();approved=self.approve(value)
        for field in ('command_sha256','worktree_sha256','cleanup_sha256','native_owner','base_sha'):
            other='4'*64 if field.endswith('sha256') else 'c'*40 if field=='base_sha' else 'another-owner'
            with self.subTest(field=field),self.assertRaises(ValueError):self.validate(dict(value,**{field:other}),approved)

    def test_non_mapping_or_non_scalar_content_fails_without_native_effects(self):
        for value in (None,[],True,'receipt',dict(receipt(),operation_id={'nested':'value'})):
            with self.subTest(value=value),self.assertRaises(ValueError):
                recovery.validate_receipt(value,{},connector_id='host1',source_sha=ENGINE)

    def test_non_set_or_malformed_approval_registry_denies(self):
        value=receipt();digest=recovery.fingerprint(value)
        for registry in (None,[],{'project1':digest},{'project1':[digest]},
                         {'project1':frozenset({digest,'not-a-digest'})}):
            with self.subTest(registry=registry),self.assertRaises(ValueError):
                recovery.validate_receipt(value,registry,connector_id='host1',source_sha=ENGINE)


class SourceTests(GitCase):
    def setUp(self):
        super().setUp()
        self.location=patch.object(recovery,'__file__',str(self.module));self.location.start()
        self.addCleanup(self.location.stop)

    def test_clean_fixed_package_root_returns_actual_commit(self):
        self.assertEqual(recovery.code_source(),self.head)

    def test_dirty_or_untracked_source_denies(self):
        self.module.write_text('# changed source\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):recovery.code_source()
        self.module.write_text('# disposable source\n',encoding='utf-8')
        (self.root/'untracked.py').write_text('pass\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):recovery.code_source()

    def test_index_flags_cannot_hide_changed_engine_bytes(self):
        for flag in ('--assume-unchanged','--skip-worktree'):
            with self.subTest(flag=flag):
                self.git(self.root,'update-index',flag,'task_tower/preparing_recovery.py')
                self.module.write_text('# changed but hidden from status\n',encoding='utf-8')
                try:
                    self.assertEqual(self.git(self.root,'status','--porcelain'),'')
                    with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):recovery.code_source()
                finally:
                    self.module.write_text('# disposable source\n',encoding='utf-8')
                    self.git(self.root,'update-index','--no-assume-unchanged','--no-skip-worktree','task_tower/preparing_recovery.py')

    def test_nested_package_cannot_claim_ancestor_repository_identity(self):
        nested=self.root/'nested'/'task_tower'/'preparing_recovery.py'
        nested.parent.mkdir(parents=True);nested.write_text('# nested\n',encoding='utf-8')
        with patch.object(recovery,'__file__',str(nested)),self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):
            recovery.code_source()

    def test_missing_or_incomplete_index_observation_denies(self):
        from task_tower.connector.worktrees import Worktrees
        actual=Worktrees._git
        for report in ('','H task_tower/preparing_recovery.py','H \0','H file\0\0'):
            def observe(root,*args,**kwargs):
                return report if args==('ls-files','-v','-z') else actual(root,*args,**kwargs)
            with self.subTest(report=report),patch.object(Worktrees,'_git',side_effect=observe):
                with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):recovery.code_source()

    def test_git_failure_never_exposes_exception_text(self):
        from task_tower.connector.worktrees import Worktrees
        with patch.object(Worktrees,'_git',side_effect=ValueError('PRIVATE fixture detail')):
            with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$') as caught:recovery.code_source()
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_all_source_observations_share_the_deadline(self):
        from task_tower.connector.worktrees import Worktrees
        with patch.object(recovery.time,'monotonic',side_effect=[100,100.1,111]),patch.object(Worktrees,'_git',return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError,'^preparing_source_unverified$'):recovery.code_source()



if __name__=='__main__':unittest.main()
