"""Opt-in trusted-host App authentication. No model-facing credentials."""
from dataclasses import dataclass, field
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import threading
import time
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .delivery import GitHubHost

PERMISSIONS = dict(metadata="read", issues="write", pull_requests="write", contents="write", actions="read", checks="read", statuses="write", administration="read")


from ..child_environment import child_environment


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("github_redirect_forbidden")


def github_http(method,url,headers,payload,limit):
    if not url.startswith("https://api.github.com/"):
        raise ValueError("github_origin_required")
    raw=None if payload is None else json.dumps(payload,ensure_ascii=True).encode()
    request=Request(url,data=raw,headers=headers,method=method)
    with build_opener(_NoRedirect()).open(request,timeout=30) as response:
        result=response.read(limit+1)
    if len(result)>limit: raise ValueError("github_response_limit")
    return result


def pem_signer(key_path):
    # Read a configured key only in this fixed host helper; optional library is lazy.
    path=Path(key_path)
    def sign(claims):
        import jwt
        from ..project_connections import safe_config_path
        import stat
        checked=safe_config_path(path);info=checked.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 1<=info.st_size<=65536:raise ValueError("invalid_private_app_key")
        if os.name=="nt":
            from ..service.cli import _windows_private
            _windows_private(checked)
        elif info.st_uid!=os.getuid() or info.st_mode & 0o077:raise ValueError("private_app_key_permissions_required")
        return jwt.encode(claims,checked.read_bytes(),algorithm="RS256")
    return sign


@dataclass(frozen=True)
class _InstallationToken:
    expires_at: float
    _value: str = field(repr=False)


class AppCredentials:
    def __init__(self,app_id,installation_id,repository_id,repository,*,signer,transport=None):
        if any(type(v) is not int or v<1 for v in (app_id,installation_id,repository_id)):
            raise ValueError("invalid_app_binding")
        if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+",repository):
            raise ValueError("invalid_repository")
        self.app_id,self.installation_id,self.repository_id=app_id,installation_id,repository_id
        self.repository=repository; self._signer=signer; self._transport=transport or github_http
        self._cached=None; self._fenced=False; self._bot=None; self._lock=threading.RLock()

    def _request(self,method,path,credential,payload=None):
        if not path.startswith("/") or ".." in path or ":" in path or "#" in path:
            raise ValueError("invalid_github_path")
        headers={"Authorization":"Bearer "+credential,"Accept":"application/vnd.github+json", "Content-Type":"application/json", "User-Agent":"Task-Tower", "X-GitHub-Api-Version":"2022-11-28"}
        from ..service.beads import strict_json
        value=strict_json(self._transport(method,"https://api.github.com"+path,headers,payload,2097152).decode("utf-8"))
        if not isinstance(value,dict): raise ValueError("invalid_github_response")
        return value

    def _jwt(self,now):
        return self._signer(dict(iat=int(now)-60,exp=int(now)+540,iss=str(self.app_id)))

    def _identity(self,now):
        jwt=self._jwt(now); app=self._request("GET","/app",jwt)
        if app.get("id")!=self.app_id or not re.fullmatch(r"[a-zA-Z0-9-]{1,100}",app.get("slug","")):
            raise ValueError("wrong_app_identity")
        login=app["slug"]+"[bot]"
        bot=self._request("GET","/users/"+quote(login,safe=""),jwt)
        if bot.get("type")!="Bot" or bot.get("login")!=login or type(bot.get("id")) is not int or bot["id"]<1:
            raise ValueError("wrong_bot_identity")
        self._bot=bot["id"]
        return jwt

    def bot_identity(self):
        with self._lock:
            try:
                self._identity(time.time())
                return self._bot
            except Exception:
                raise ValueError("app_authentication_unavailable") from None

    def installation_token(self,repository_id,now):
        if type(repository_id) is not int or repository_id!=self.repository_id or not math.isfinite(now):
            raise ValueError("repository_binding_mismatch")
        with self._lock:
            if self._fenced: raise ValueError("app_authentication_unavailable")
            if self._cached and self._cached.expires_at>now+120: return self._cached
            self._cached=None
            try:
                jwt=self._identity(now)
                installation=self._request("GET","/app/installations/"+str(self.installation_id),jwt)
                if (installation.get("id"),installation.get("app_id"),installation.get("suspended_at"))!=(self.installation_id,self.app_id,None):
                    raise ValueError("wrong_installation")
                # Set the fence BEFORE the non-idempotent mint. Only a validated reply clears it.
                self._fenced=True
                value=self._request("POST","/app/installations/"+str(self.installation_id)+"/access_tokens",jwt,dict(repository_ids=[repository_id],permissions=PERMISSIONS))
                token=value["token"]
                expiry=datetime.fromisoformat(value["expires_at"].replace("Z","+00:00"))
                if not isinstance(token,str) or not token or len(token)>4096 or expiry.tzinfo is None or expiry.timestamp()<=now+120:
                    raise ValueError("invalid_installation_token")
                if value.get("permissions")!=PERMISSIONS: raise ValueError("unexpected_permissions")
                repos=self._request("GET","/installation/repositories?per_page=100",token)
                rows=repos.get("repositories")
                if repos.get("total_count")!=1 or not isinstance(rows,list) or len(rows)!=1 or rows[0].get("id")!=repository_id or rows[0].get("full_name")!=self.repository:
                    raise ValueError("unexpected_token_scope")
                self._cached=_InstallationToken(expiry.timestamp(),token); self._fenced=False
                return self._cached
            except Exception:
                self._fenced=True
                raise ValueError("app_authentication_unavailable") from None


class AppGitHubHost(GitHubHost):
    def __init__(self,worktrees,store,projects,*,credentials,transport=None,reviewer=None):
        if set(projects.values())!={credentials.repository}: raise ValueError("app_repository_scope")
        self.trees,self.store,self.projects=worktrees,store,dict(projects)
        self._credentials=credentials; self.transport=transport or github_http
        self.reviewer=reviewer; self.clients={}; self.creator=None

    def _client(self,r):
        from types import SimpleNamespace
        from ..github_tasks import GitHubTasks
        if r not in self.projects.values(): raise ValueError("repository_forbidden")
        token=self._credentials.installation_token(self._credentials.repository_id,time.time())
        return GitHubTasks(SimpleNamespace(repository=r),token=token._value,transport=self.transport)

    def _creator(self): return self._credentials.bot_identity()

    def _global(self,path,payload=None):
        if path!="/graphql": raise ValueError("fixed_host_operation_required")
        token=self._credentials.installation_token(self._credentials.repository_id,time.time())
        return self._credentials._request("POST",path,token._value,payload)

    def _remote(self,path,r,env=None):
        super()._remote(path,r,env)
        allowed={"https://github.com/"+r,"https://github.com/"+r+".git"}
        if self._trusted_git(path,"remote","get-url","--all","origin",env=env) not in allowed or self._trusted_git(path,"remote","get-url","--push","--all","origin",env=env) not in allowed:
            raise ValueError("app_https_remote_required")

    def _push(self,path,branch,repository,env=None):
        env=self._git_environment(); self._remote(path,repository,env)
        credential=self._credentials.installation_token(self._credentials.repository_id,time.time())
        helper=Path(__file__).with_name("github_app_askpass.py")
        env.update(GIT_ASKPASS=shlex.join([Path(sys.executable).as_posix(),helper.as_posix()]),TT_GITHUB_INSTALLATION_TOKEN=credential._value)
        self._trusted_git(path,"-c","credential.helper=","push","origin",branch+":refs/heads/"+branch,timeout=60,env=env)
