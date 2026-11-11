"""App credentials remain scoped to the trusted host; all HTTP here is synthetic."""
import json
import unittest
from datetime import datetime, timezone
from task_tower.connector.github_app import AppCredentials, AppGitHubHost, child_environment

PERMISSIONS = dict(metadata="read", issues="write", pull_requests="write", contents="write", actions="read", checks="read", statuses="write", administration="read")

class GitHub:
    def __init__(self):
        self.calls=[]; self.mints=0; self.wrong=False; self.lost=False
    def __call__(self, method, url, headers, payload, limit):
        path=url.removeprefix("https://api.github.com")
        self.calls.append((method,path,payload))
        if path=="/app": value=dict(id=7,slug="tower-test")
        elif path=="/app/installations/8": value=dict(id=8,app_id=7,repository_selection="selected",suspended_at=None)
        elif path=="/app/installations/8/access_tokens":
            self.mints+=1
            if self.lost: raise TimeoutError("synthetic secret must not escape")
            value=dict(token="synthetic-installation-secret", expires_at="2030-01-01T0"+str(self.mints)+":00:00Z", permissions=PERMISSIONS)
        elif path=="/installation/repositories?per_page=100": value=dict(total_count=1,repositories=[dict(id=99 if self.wrong else 9,full_name="owner/repo")])
        elif path=="/users/tower-test%5Bbot%5D": value=dict(id=11,login="tower-test[bot]",type="Bot")
        else: raise AssertionError(path)
        return json.dumps(value).encode()

class CredentialsTests(unittest.TestCase):
    def credentials(self, api=None):
        api=api or GitHub(); claims=[]
        def sign(value): claims.append(value); return "synthetic-jwt"
        return AppCredentials(7,8,9,"owner/repo",signer=sign,transport=api),api,claims
    def test_scoped_token_cached_and_refreshed_before_expiry(self):
        c,api,claims=self.credentials(); now=datetime(2030,1,1,tzinfo=timezone.utc).timestamp()
        token=c.installation_token(9,now)
        self.assertNotIn("synthetic-installation-secret",repr(token))
        self.assertIs(c.installation_token(9,now+1),token)
        c.installation_token(9,now+3550)
        self.assertEqual(api.mints,2)
        self.assertEqual(claims[0],dict(iat=int(now)-60,exp=int(now)+540,iss="7"))
        self.assertEqual([v[2]["repository_ids"] for v in api.calls if v[0]=="POST"],[[9],[9]])
        self.assertNotIn("/user",[v[1] for v in api.calls])
    def test_wrong_repository_fails_before_auth_effect(self):
        c,api,_=self.credentials()
        with self.assertRaises(ValueError): c.installation_token(10,1)
        self.assertEqual(api.calls,[])
    def test_token_scope_mismatch_is_not_cached(self):
        api=GitHub(); api.wrong=True; c,_,_=self.credentials(api)
        with self.assertRaises(ValueError): c.installation_token(9,1893456000)
        self.assertIsNone(c._cached)
    def test_unknown_mint_is_fenced_without_retry_or_secret_exception(self):
        api=GitHub(); api.lost=True; c,_,_=self.credentials(api)
        for _ in range(2):
            with self.assertRaisesRegex(ValueError,"app_authentication_unavailable") as caught: c.installation_token(9,1893456000)
            self.assertNotIn("synthetic secret",str(caught.exception))
        self.assertEqual(api.mints,1)
    def test_bot_identity_verified_without_user_endpoint(self):
        c,api,_=self.credentials()
        self.assertEqual(c.bot_identity(),11)
        self.assertNotIn("/user",[v[1] for v in api.calls])
    def test_model_environment_strips_case_insensitive_secrets_and_git_helpers(self):
        env=child_environment(dict(gH_ToKeN="a",GITHUB_TOKEN="b",WEBHOOK_DATABASE_URL="c",TT_GITHUB_INSTALLATION_TOKEN="d",GITHUB_APP_PRIVATE_KEY="e",GIT_ASKPASS="f",PATH="ok"))
        self.assertEqual(env,dict(PATH="ok"))
    def test_app_host_does_not_expose_static_token(self):
        c,_,_=self.credentials(); h=AppGitHubHost(None,None,{"p":"owner/repo"},credentials=c)
        self.assertFalse(hasattr(h,"token"))
        self.assertEqual(h._creator(),11)
        with self.assertRaises(ValueError): h._client("other/repo")

    def test_existing_executor_policy_strips_new_credentials_too(self):
        from task_tower.executor_profiles import child_environment as existing
        self.assertEqual(existing(dict(PATH="ok",Webhook_Secret="s",GITHUB_APP_PRIVATE_KEY="k")),dict(PATH="ok"))

    def test_delivery_router_keeps_app_bot_identity_for_public_messages(self):
        from task_tower.issue_bootstrap import RoutedGitHubHost
        c,_,_=self.credentials();app=AppGitHubHost(None,None,{"p":"owner/repo"},credentials=c)
        routed=RoutedGitHubHost(None,None,{"p":"owner/repo"},{"p":app},None)
        self.assertEqual(routed._creator(),11)
