"""Current-main selection reads real source parsers over HTTP fixtures only."""
import json
import unittest
from types import SimpleNamespace
from task_tower.pr_source import PRSource
from tests import test_github_source as github_fixture
SHA=github_fixture.SHA


class MainBundleTests(unittest.TestCase):
    def source(self,main=None):
        values=iter(main or [SHA,SHA])
        def transport(method,url,headers,body,timeout,max_bytes):
            self.assertEqual(method,'GET')
            self.assertTrue(url.endswith('/git/ref/heads/main'))
            return dict(status=200,headers={},body=json.dumps(dict(object=dict(sha=next(values)))).encode())
        return PRSource(SimpleNamespace(repository='owner/repo'),{},transport=transport)

    def test_exact_current_main_and_verified_bundle_selected(self):
        from task_tower.pr_main import select_main_bundle
        github=github_fixture.GitHubSourceTests().source()
        task=dict(repository='owner/repo',pr_number=7,task_id='TT-ONE',required_platforms=['linux'])
        result=select_main_bundle(self.source(),github,task,SHA)
        self.assertEqual(result['merge_commit'],SHA)
        self.assertEqual(result['run_id'],'12')
        self.assertEqual(result['attempt'],'2')

    def test_missing_platform_or_failed_ci_never_selected(self):
        from task_tower.pr_main import select_main_bundle
        task=dict(repository='owner/repo',pr_number=7,task_id='TT-ONE',required_platforms=['windows'])
        self.assertIsNone(select_main_bundle(self.source(),github_fixture.GitHubSourceTests().source(),task,SHA))
        task['required_platforms']=['linux']
        failed=github_fixture.GitHubSourceTests().source(lambda p,r,e:e.update(checks='failed'))
        self.assertIsNone(select_main_bundle(self.source(),failed,task,SHA))

    def test_main_moving_during_poll_refuses_original_bundle(self):
        from task_tower.pr_main import select_main_bundle
        task=dict(repository='owner/repo',pr_number=7,task_id='TT-ONE',required_platforms=['linux'])
        with self.assertRaises(ValueError):select_main_bundle(self.source([SHA,'b'*40]),github_fixture.GitHubSourceTests().source(),task,SHA)

    def test_same_task_other_pr_is_not_a_completion_candidate(self):
        from task_tower.pr_main import select_main_bundle
        task=dict(repository='owner/repo',pr_number=8,task_id='TT-ONE',required_platforms=['linux'])
        with self.assertRaises(ValueError):select_main_bundle(self.source(),github_fixture.GitHubSourceTests().source(),task,SHA)
