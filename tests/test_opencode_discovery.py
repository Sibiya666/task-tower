import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from task_tower import opencode_discovery as discovery


class OpenCodeEnvironmentTests(unittest.TestCase):
    def test_child_environment_preserves_model_auth_and_host(self):
        host=dict(PATH='installed',PWD='wrong',MODEL='existing',OPENAI_API_KEY='opaque',
                  OPENCODE_PASSWORD='opaque-native',Gh_ToKeN='host-only',OPENCODE_DISABLE_AUTOUPDATE='false')
        original=copy.deepcopy(host)
        child=discovery.opencode_environment(host,'/exact/worktree')
        self.assertEqual(child['MODEL'],'existing')
        self.assertEqual(child['OPENAI_API_KEY'],'opaque')
        self.assertEqual(child['OPENCODE_PASSWORD'],'opaque-native')
        self.assertEqual(child['PWD'],'/exact/worktree')
        self.assertEqual(child['OPENCODE_DISABLE_AUTOUPDATE'],'1')
        self.assertNotIn('Gh_ToKeN',child)
        self.assertEqual(host,original)

    def test_environment_presence_and_value_changes_are_bound_without_values(self):
        env=dict(PATH='one',HOME='/home',OPENCODE_CLIENT='cli')
        first=discovery.environment_binding(env,'linux')
        self.assertEqual(set(first),{'names','presence_sha256','values_sha256'})
        self.assertNotIn('one',str(first))
        changed=discovery.environment_binding(dict(env,PATH='two'),'linux')
        self.assertEqual(first['presence_sha256'],changed['presence_sha256'])
        self.assertNotEqual(first['values_sha256'],changed['values_sha256'])
        added=discovery.environment_binding(dict(env,OPENCODE_NEW=''),'linux')
        self.assertNotEqual(first['presence_sha256'],added['presence_sha256'])
        self.assertIn('OPENCODE_NEW',added['names'])

    def test_auth_values_are_not_inspected(self):
        class Opaque:
            def __str__(self): raise AssertionError('auth inspected')
        result=discovery.environment_binding(dict(PATH='tool',OPENCODE_PASSWORD=Opaque(),
                                                 OPENAI_API_KEY=Opaque()),'linux')
        self.assertNotIn('OPENCODE_PASSWORD',result['names'])
        self.assertNotIn('OPENAI_API_KEY',result['names'])

    def test_startup_injection_unknown_and_empty_askpass_block(self):
        for key in ('OPENCODE_SSH_ASKPASS_PORT','OPENCODE_UNKNOWN','OPENCODE_CONFIG_CONTENT',
                    'OPENCODE_CLI_CONFIG_CONTENT','OTEL_EXPORTER_OTLP_ENDPOINT','NODE_OPTIONS',
                    'NODE_EXTRA_CA_CERTS','BUN_INSPECT','JSC_useJIT',
                    'BUN_OPTIONS','LD_PRELOAD','DYLD_INSERT_LIBRARIES','BASH_ENV','ENV'):
            with self.subTest(key=key):
                self.assertEqual(discovery.environment_reasons({key:''},'linux'),['unsupported_environment'])

    def test_windows_collisions_are_not_normalized_away(self):
        with self.assertRaises(ValueError): discovery.environment_binding({'PATH':'x','path':'x'},'windows')


class DiscoveryFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.home=self.root/'home';self.config=self.root/'config'/'opencode'
        self.data=self.root/'data'/'opencode';self.cache=self.root/'cache'/'opencode'
        self.state=self.root/'state'/'opencode';self.tmp=self.root/'tmp'/'opencode';self.runs=self.root/'runs'
        self.platform='windows' if os.name=='nt' else 'macos' if os.sys.platform=='darwin' else 'linux'
        self.env=dict(HOME=str(self.home),USERPROFILE=str(self.home),XDG_CONFIG_HOME=str(self.config.parent),
                      XDG_DATA_HOME=str(self.data.parent),XDG_CACHE_HOME=str(self.cache.parent),
                      XDG_STATE_HOME=str(self.state.parent),TMPDIR=str(self.tmp.parent),TMP=str(self.tmp.parent),TEMP=str(self.tmp.parent),
                      ProgramData=str(self.root/'programdata'),PATH='existing')
        self.system=self.root/'programdata'/'opencode' if self.platform=='windows' else Path('/Library/Application Support/opencode' if self.platform=='macos' else '/etc/opencode')
        self.worktree=self.runs/str(uuid.uuid4())/str(uuid.uuid4())/'worktree'
        for path in (self.home,self.config,self.data,self.cache,self.state,self.tmp,self.data/'log',self.data/'repos',self.cache/'bin',self.worktree):
            path.mkdir(parents=True,exist_ok=True)
        self.scope=dict(platform=self.platform,home=str(self.home),global_config=str(self.config),system_config=str(self.system),
                        runs_root=str(self.runs),source_sha='a'*40,worktree_template='{runs_root}/{run_id}/{attempt_id}/worktree')

    def collect(self):
        return discovery.collect_opencode_discovery(self.scope,worktree=str(self.worktree),environ=self.env)

    def test_absences_bind_actual_nearest_parent_chain(self):
        observed=self.collect()
        path=str(self.worktree/'opencode.json')
        entry=next(row for row in observed['inventory'] if row['path']==path)
        self.assertEqual(entry['kind'],'missing')
        self.assertEqual(entry['parent_identity']['path'],str(self.worktree))
        self.assertEqual(entry['parent_identity']['missing_components'],['opencode.json'])
        self.assertEqual(entry['parent_identity']['identity']['file_id'],str(self.worktree.stat().st_ino))

    def test_unqualified_present_config_is_metadata_only_and_not_complete(self):
        path=self.worktree/'opencode.json';path.write_text('{"provider":{"secret":"never-read"}}')
        with patch.object(discovery,'read_bound',side_effect=AssertionError('file content read')):
            observed=self.collect()
        self.assertFalse(observed['complete'])
        self.assertIn('unsupported_unqualified_config_file',observed['reasons'])
        self.assertNotIn('never-read',str(observed))

    def test_missing_startup_root_is_refused_without_creation(self):
        target=self.cache/'bin';target.rmdir()
        observed=self.collect()
        self.assertIn('unsupported_startup_directory_creation',observed['reasons'])
        self.assertFalse(target.exists())

    def test_credential_database_never_reads_even_if_listed_in_grants(self):
        path=self.data/'opencode.db';path.write_bytes(b'private database')
        grant=dict(kind='file',path=str(path),role='forged_config',identity=discovery.identity(path.stat()),
                   bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        with patch.object(discovery,'read_bound',side_effect=AssertionError('database opened')):
            observed=discovery._collect(self.scope,worktree=str(self.worktree),environ=self.env,_grants={str(path):grant})
        self.assertFalse(observed['complete'])
        self.assertIn('unsupported_credential_dependent_discovery',observed['reasons'])

    def test_directory_membership_and_absence_changes_are_detected(self):
        before=self.collect()
        (self.config/'unrelated-member').write_text('not read')
        after=self.collect()
        self.assertIn('inventory_changed',discovery.compare_opencode_discovery(before,after))
        (self.worktree/'.opencode').mkdir()
        self.assertIn('inventory_changed',discovery.compare_opencode_discovery(after,self.collect()))

    def test_caller_cannot_add_file_read_grant_to_public_scope(self):
        self.scope['approved_files']={str(self.worktree/'opencode.json'):'self-approved'}
        with patch.object(discovery,'read_bound',side_effect=AssertionError('file read')):
            observed=self.collect()
        self.assertFalse(observed['complete'])
        self.assertIn('invalid_scope',observed['reasons'])

    def test_private_grant_hash_checked_before_config_interpretation(self):
        path=self.worktree/'opencode.json';path.write_bytes(b'{}')
        grant=dict(kind='file',path=str(path),role='project_config',identity=discovery.identity(path.stat()),
                   bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())
        path.write_bytes(b'{"apiKey":"changed secret"}')
        observed=discovery._collect(self.scope,worktree=str(self.worktree),environ=self.env,_grants={str(path):grant})
        self.assertFalse(observed['complete'])
        self.assertIn('approved_file_changed',observed['reasons'])
        self.assertNotIn('changed secret',str(observed))

    def test_reviewed_model_and_permission_configuration_is_not_rewritten(self):
        path=self.worktree/'opencode.json'
        data=json.dumps(dict(model='provider/existing-model#existing-variant',permissions=[
            dict(action='read',resource='*',effect='allow'),
            dict(action='external_directory',resource='*',effect='deny')])).encode()
        path.write_bytes(data)
        grant=dict(kind='file',path=str(path),role='project_config',identity=discovery.identity(path.stat()),
                   bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        observed=discovery._collect(self.scope,worktree=str(self.worktree),environ=self.env,_grants={str(path):grant})
        self.assertNotIn('unsupported_config_semantics',observed['reasons'])
        self.assertEqual(path.read_bytes(),data)
        self.assertNotIn('existing-model',str(observed))

    def test_unqualified_mutable_startup_file_cannot_be_assumed_irrelevant(self):
        (self.cache/'models.json').write_bytes(b'unqualified startup influence')
        with patch.object(discovery,'read_bound',side_effect=AssertionError('unqualified cache read')):
            observed=self.collect()
        self.assertFalse(observed['complete'])
        self.assertIn('unsupported_unqualified_startup_file',observed['reasons'])

    def test_directory_limit_is_failure_not_truncated_success(self):
        for index in range(257):(self.config/f'member-{index:03d}').write_bytes(b'not read')
        with patch.object(discovery,'read_bound',side_effect=AssertionError('member content read')):
            observed=self.collect()
        self.assertFalse(observed['complete'])
        self.assertIn('directory_member_limit',observed['reasons'])

    def test_instruction_candidates_use_tagged_home_project_stop(self):
        project=self.worktree/'AGENTS.md';project.write_bytes(b'nonsecret fixture instructions')
        outside=self.root/'AGENTS.md';outside.write_bytes(b'outside native project stop')
        global_file=self.config/'AGENTS.md'
        with patch.object(discovery,'read_bound',side_effect=AssertionError('unqualified instruction read')):
            observed=self.collect()
        paths={row['path'] for row in observed['diagnostics']}
        self.assertIn(str(project),paths)
        self.assertNotIn(str(outside),paths)
        self.assertTrue(any(row['path']==str(global_file) for row in observed['inventory']))
        self.assertNotIn('unsupported_instruction_discovery',observed['reasons'])
        self.scope['home']=str(self.root);self.env['HOME']=str(self.root);self.env['USERPROFILE']=str(self.root)
        with patch.object(discovery,'read_bound',side_effect=AssertionError('unqualified instruction read')):
            observed=self.collect()
        self.assertIn(str(outside),{row['path'] for row in observed['diagnostics']})

    def test_generated_ancestors_have_six_missing_candidates_not_sibling_membership(self):
        observed=self.collect()
        names={row['path'] for row in observed['inventory'] if row['kind']=='missing' and
               row['parent_identity']['path']==str(self.runs) and len(row['parent_identity']['missing_components'])==1}
        expected={str(self.runs/name) for name in ('.agents','.claude','.opencode','AGENTS.md','opencode.json','opencode.jsonc')}
        self.assertEqual(names,expected)
        self.assertFalse(any(row['kind']=='directory' and row['path']==str(self.runs) for row in observed['inventory']))
        (self.runs/str(uuid.uuid4())).mkdir()
        self.assertNotIn('inventory_changed',discovery.compare_opencode_discovery(observed,self.collect()))

    def test_new_generated_ancestor_instruction_blocks_without_content_read(self):
        path=self.worktree.parent/'AGENTS.md';path.write_bytes(b'not approved')
        with patch.object(discovery,'read_bound',side_effect=AssertionError('generated ancestor read')):
            observed=self.collect()
        self.assertIn('unsupported_run_ancestor_candidate',observed['reasons'])

    def test_same_size_hash_drift_is_rejected_before_json_parser(self):
        from task_tower import opencode_adapter
        path=self.worktree/'opencode.json';path.write_bytes(b'{}')
        grant=dict(kind='file',path=str(path),role='project_config',identity=discovery.identity(path.stat()),
                   bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())
        path.write_bytes(b'[]')
        with patch.object(opencode_adapter,'_json',side_effect=AssertionError('changed bytes interpreted')):
            observed=discovery._collect(self.scope,worktree=str(self.worktree),environ=self.env,_grants={str(path):grant})
        self.assertIn('approved_file_changed',observed['reasons'])
