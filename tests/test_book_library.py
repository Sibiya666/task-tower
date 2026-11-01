import unittest
import base64
import json
import urllib.error
from types import SimpleNamespace


class LibraryTests(unittest.TestCase):
    def project(self, index, exists=True, connected=None):
        from task_tower.book_library import project_library
        commit='a'*40
        store=SimpleNamespace(library=lambda:[dict(title='docs/a.md',path='docs/a.md',commit=commit,repository='a/b',source='https://github.com/a/b/blob/'+commit+'/docs/a.md')], library_index=lambda c:index,markdown_exists=lambda c,p:exists)
        return project_library(SimpleNamespace(id='p',repository='a/b'),store,connected_repositories=connected)
    def declaration(self, **fields):
        return dict(path='docs/a.md',commit='a'*40,state='accepted',**fields)
    def test_current_and_old_versions_and_explicit_state(self):
        rows, errors=self.project(dict(version=1,artifacts=[self.declaration(),dict(path='docs/a.md',commit='b'*40,state='superseded')]))
        self.assertEqual(len(rows),2); self.assertEqual(errors,[])
        self.assertEqual(rows[0]['id'],'a/b:docs/a.md@'+'a'*40)
        self.assertEqual(rows[0]['artifact_state'],'accepted')
        self.assertNotEqual(rows[0]['status'],'done')
    def test_missing_index_and_missing_blob(self):
        rows,errors=self.project(None)
        self.assertEqual(rows[0]['artifact_state'],'unknown'); self.assertEqual(errors,[])
        rows,errors=self.project(dict(version=1,artifacts=[self.declaration()]),False)
        self.assertFalse(rows[0]['available']); self.assertTrue(errors)
    def test_invalid_index_leaves_tree_visible(self):
        bad_rows=[dict(path='../bad.md',commit='a'*40,state='accepted'),self.declaration(issues=['other/repo#1'])]
        for row in bad_rows:
            rows,errors=self.project(dict(version=1,artifacts=[row]))
            self.assertEqual(len(rows),1); self.assertEqual(rows[0]['artifact_state'],'unknown'); self.assertTrue(errors)
        rows,errors=self.project(dict(version=1,artifacts=[self.declaration(),dict(path='docs/a.md',commit='a'*40,state='working')]))
        self.assertTrue(errors); self.assertEqual(rows[0]['artifact_state'],'unknown')
    def test_connected_associations_only(self):
        rows,errors=self.project(dict(version=1,artifacts=[self.declaration(issues=['c/d#2'],milestone=dict(repository='c/d',number=3))]),connected={'a/b','c/d'})
        self.assertEqual(errors,[]); self.assertEqual(rows[0]['issues'],['c/d#2'])

    def test_manifest_strict_schema_budgets_and_paths(self):
        indices=[dict(version=True,artifacts=[]),dict(version=2,artifacts=[]),dict(version=1,artifacts=[],extra=True),
                 dict(version=1,artifacts=[self.declaration()]*1001),
                 dict(version=1,artifacts=[dict(path='docs/a.md',commit='a'*40,state='accepted',issues=['a/b#1']*30000)])]
        for path in ('/a.md','a//b.md','a/./b.md','a/../b.md','a\\b.md','a\x00.md','C:/a.md','a.txt'):
            indices.append(dict(version=1,artifacts=[dict(path=path,commit='a'*40,state='accepted')]))
        for index in indices:
            with self.subTest(index=str(index)[:90]):
                rows,errors=self.project(index)
                self.assertTrue(errors); self.assertEqual(rows[0]['artifact_state'],'unknown')

    def test_identical_duplicates_and_no_title_inference(self):
        rows,errors=self.project(dict(version=1,artifacts=[self.declaration(),self.declaration()]))
        self.assertEqual(errors,[]); self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['issues'],[]); self.assertIsNone(rows[0]['milestone'])

    def test_authenticated_immutable_transport_and_known_404_only(self):
        from task_tower.github_tasks import GitHubTasks, GitHubRequestError
        calls=[]; commit='c'*40; content=json.dumps(dict(version=1,artifacts=[])).encode()
        def transport(method,url,headers,payload,limit):
            calls.append((url,headers))
            if 'task-tower-library.json' in url:
                return json.dumps(dict(type='file',size=len(content),encoding='base64',content=base64.b64encode(content).decode())).encode()
            return json.dumps(dict(type='file',path='docs/a.md',sha='d'*40)).encode()
        store=GitHubTasks(SimpleNamespace(repository='a/b'),token='TEST_TOKEN',transport=transport)
        self.assertEqual(store.library_index(commit),dict(version=1,artifacts=[]))
        self.assertTrue(store.markdown_exists(commit,'docs/a.md'))
        self.assertTrue(all(url.endswith('?ref='+commit) for url,headers in calls))
        self.assertTrue(all(headers['Authorization']=='Bearer TEST_TOKEN' for url,headers in calls))
        for code in (404,403,500):
            def unavailable(*args): raise urllib.error.HTTPError('PRIVATE',code,'PRIVATE',{},None)
            store.transport=unavailable
            if code==404:
                self.assertIsNone(store.library_index(commit)); self.assertFalse(store.markdown_exists(commit,'docs/a.md'))
            else:
                with self.assertRaises(GitHubRequestError): store.library_index(commit)

    def test_duplicate_json_keys_and_oversized_index_rejected(self):
        from task_tower.github_tasks import GitHubTasks
        from task_tower.github_source import GitHubSourceError
        for content in (b'{"version":1,"version":1,"artifacts":[]}', b' '*262145):
            def transport(*args):
                return json.dumps(dict(type='file',size=len(content),encoding='base64',content=base64.b64encode(content).decode())).encode()
            store=GitHubTasks(SimpleNamespace(repository='a/b'),transport=transport)
            with self.assertRaises(GitHubSourceError): store.library_index('a'*40)

