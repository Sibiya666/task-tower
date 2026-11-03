import copy
import hashlib
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from task_tower import opencode_adapter as adapter
from task_tower.opencode_files import identity
from tests import test_opencode_policy as policy_fixture
from tests import test_opencode_discovery as discovery_fixture
from task_tower import opencode_discovery as discovery


CANDIDATES=['.agents','.claude','.opencode','AGENTS.md','opencode.json','opencode.jsonc']


def template(scope):
    return dict(kind='worktree_template',version=1,path=scope['worktree_template'],role='launch_worktree',
        source_sha=scope['source_sha'],ancestor_missing=CANDIDATES.copy(),entries=[
            dict(kind='missing',path=name,role='candidate',parent_path='.',missing_components=[name]) for name in CANDIDATES])


def anchors(root):
    root.mkdir(parents=True,exist_ok=True)
    return [dict(kind='missing',path=str(root/name),role='candidate',parent_identity=dict(path=str(root),
        identity=identity(root.stat()),missing_components=[name])) for name in CANDIDATES]


class TemplateGrammarTests(unittest.TestCase):
    def setUp(self):
        self.f=policy_fixture.OpenCodePolicyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.t=template(self.f.evidence['scope'])
        self.f.evidence['inventory']=[*anchors(self.f.runs),self.t]

    def test_exact_template_and_existing_root_anchors_are_valid(self):
        self.f.validate()

    def test_zero_two_or_mismatched_source_templates_are_rejected(self):
        original=copy.deepcopy(self.f.evidence['inventory'])
        for inventory in (original[:-1],[*original,copy.deepcopy(self.t)]):
            self.f.evidence['inventory']=inventory
            with self.assertRaises(ValueError):self.f.validate()
        self.f.evidence['inventory']=original
        self.f.evidence['inventory'][-1]['source_sha']='b'*40
        with self.assertRaises(ValueError):self.f.validate()


    def test_template_never_accepts_old_or_fabricated_physical_identity(self):
        row=self.t['entries'][0]
        for field,value in [('identity',identity(self.f.root.stat())),('parent_identity',{}),('extra',False)]:
            row[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.f.validate()
            del row[field]

    def test_relative_aliases_and_nonreconstructible_missing_paths_rejected(self):
        row=self.t['entries'][0];old=row['path']
        for path in ('../secret','/absolute','C:/drive','a\\b','a/./b','a//b','a/'):
            row['path']=path
            with self.subTest(path=path),self.assertRaises(ValueError):self.f.validate()
        row['path']=old;row['parent_path']='other'
        with self.assertRaises(ValueError):self.f.validate()

    def test_six_root_anchor_identities_and_paths_must_agree(self):
        row=self.f.evidence['inventory'][0]
        parent=row['parent_identity'];original=copy.deepcopy(parent)
        parent['identity']['file_id']=str(int(parent['identity']['file_id'])+1)
        with self.assertRaises(ValueError):self.f.validate()
        row['parent_identity']=copy.deepcopy(original)
        row['parent_identity'].update(path=str(self.f.root),missing_components=[self.f.runs.name,CANDIDATES[0]])
        with self.assertRaises(ValueError):self.f.validate()

    def test_root_membership_and_future_concrete_ids_not_substituted_for_template(self):
        self.f.evidence['inventory'].append(dict(kind='directory',path=str(self.f.runs),role='bad_root',
            identity=identity(self.f.runs.stat()),members=[]))
        with self.assertRaises(ValueError):self.f.validate()

    def test_template_directory_members_are_closed_and_bounded(self):
        self.t['entries']=[dict(kind='directory',path='.opencode',role='project_directory',
            members=[dict(name='agent',kind='directory')])]
        self.f.validate()
        self.t['entries'][0]['members'][0]['identity']=identity(self.f.root.stat())
        with self.assertRaises(ValueError):self.f.validate()


class ActualTemplateObservationTests(unittest.TestCase):
    """Synthetic bounded source surface, real filesystem IDs, no native harness.

    Ancestor/system scope is isolated from the person's unqualified home. This
    proves the semantic/physical distinction, not installed source qualification.
    """
    def setUp(self):
        self.f=discovery_fixture.DiscoveryFixture();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.roots=discovery._roots(self.f.scope,self.f.env)
        self.f.scope['system_config']=str(self.f.root/'isolated-system')
        self.data=b'SYNTHETIC nonsecret source-pinned instructions\n'
        self.file=self.f.worktree/'AGENTS.md';self.file.write_bytes(self.data)

    def collect(self,tree):
        path=tree/'AGENTS.md'
        grant=dict(kind='file',path=str(path),role='instruction',identity=identity(path.stat()),
                   bytes=len(self.data),sha256=hashlib.sha256(self.data).hexdigest())
        parents=lambda current:[current,*[p for p in current.parents if p.is_relative_to(self.f.root)]]
        with patch.object(discovery,'_roots',return_value=self.roots),patch.object(discovery,'_ancestors',side_effect=parents):
            return discovery._collect(self.f.scope,worktree=str(tree),environ=self.f.env,_grants={str(path):grant})

    def expected(self,observation):
        tree=Path(observation['worktree']);generated={tree.parent,tree.parent.parent}
        external=[copy.deepcopy(row) for row in observation['inventory'] if
                  not Path(row['path']).is_relative_to(tree) and Path(row['path']).parent not in generated]
        t=template(self.f.scope)
        roles={'.agents':'compatibility_root','.claude':'compatibility_root','.opencode':'project_directory',
               'opencode.json':'project_config','opencode.jsonc':'project_config'}
        t['entries']=[dict(kind='missing',path=name,role=role,parent_path='.',missing_components=[name]) for name,role in roles.items()]
        t['entries'].append(dict(kind='file',path='AGENTS.md',role='instruction',bytes=len(self.data),sha256=hashlib.sha256(self.data).hexdigest()))
        return dict(scope=copy.deepcopy(self.f.scope),inventory=[*external,t],environment=observation['environment'])

    def test_two_distinct_uuid_worktrees_match_one_semantic_template(self):
        first=self.collect(self.f.worktree)
        self.assertTrue(first['complete'],first['reasons'])
        expected=self.expected(first)
        self.assertEqual(discovery.compare_opencode_discovery(expected,first),[])
        other=self.f.runs/str(uuid.uuid4())/str(uuid.uuid4())/'worktree';other.mkdir(parents=True)
        (other/'AGENTS.md').write_bytes(self.data)
        second=self.collect(other)
        self.assertTrue(second['complete'],second['reasons'])
        old=next(row['identity'] for row in first['inventory'] if row['path']==str(self.file))
        new=next(row['identity'] for row in second['inventory'] if row['path']==str(other/'AGENTS.md'))
        self.assertNotEqual(old,new)
        self.assertEqual(discovery.compare_opencode_discovery(expected,second),[])
        self.assertNotEqual(adapter.discovery_digest(first['inventory'],first['environment']),adapter.discovery_digest(second['inventory'],second['environment']))

    def test_new_ancestor_config_or_external_membership_is_not_ignored(self):
        before=self.collect(self.f.worktree);expected=self.expected(before)
        (self.f.config/'unrelated-member').write_bytes(b'new metadata')
        self.assertIn('inventory_changed',discovery.compare_opencode_discovery(expected,self.collect(self.f.worktree)))
        (self.f.worktree.parent/'AGENTS.md').write_bytes(b'unapproved')
        after=self.collect(self.f.worktree)
        self.assertIn('unsupported_run_ancestor_candidate',after['reasons'])
        self.assertTrue(discovery.compare_opencode_discovery(expected,after))

