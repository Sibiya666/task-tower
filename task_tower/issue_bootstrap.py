"""Startup-only bot bindings for the existing service/connector, never model packets."""
import hashlib
import json
from pathlib import Path
import re
from .project_connections import safe_config_path
from .issue_intake import INITIAL_POLICY,validate_policy
from .connector.github_app import AppCredentials,AppGitHubHost,pem_signer
from .issue_runtime import RuntimeProbe,IssueScopeInspector
from .issue_source import GitHubIssueSource

FIELDS={"app_id","installation_id","repository_id","repository","connector_id","app_server","source_repository","private_key_file","policy_file","policy_sha256","consumer_id","consumer_token_file","transport_url"}


def validate_connections(value,projects):
    if not isinstance(value,dict) or set(value)-set(projects) or len(value)>1:raise ValueError("invalid_issue_connections")
    result={}
    for project,c in value.items():
        if not isinstance(c,dict) or set(c)!=FIELDS or c["repository"]!=INITIAL_POLICY["repository"]:raise ValueError("fixed_issue_binding_required")
        if any(type(c[k]) is not int or c[k]<1 for k in ("app_id","installation_id","repository_id")):raise ValueError("numeric_app_binding_required")
        for k in ("app_server","source_repository","private_key_file","policy_file","consumer_token_file"):
            if not isinstance(c[k],str) or not Path(c[k]).is_absolute():raise ValueError("absolute_issue_binding_path_required")
            safe_config_path(Path(c[k])/".scope-check" if k=="source_repository" else Path(c[k]))
        if len({c[k] for k in ("app_server","private_key_file","policy_file","consumer_token_file")})!=4 or not re.fullmatch(r"[a-f0-9]{64}",c["policy_sha256"]):raise ValueError("issue_binding_collision")
        from .service.beads import identity
        identity(c["connector_id"]);identity(c["consumer_id"])
        from .connector.issue_transport import ConsumerHTTP
        ConsumerHTTP(c["transport_url"],c["consumer_id"],lambda:"")
        result[project]=dict(c)
    return result


def _policy(c):
    from .service.beads import strict_json
    raw=safe_config_path(Path(c["policy_file"])).read_bytes()
    if len(raw)>16384 or hashlib.sha256(raw).hexdigest()!=c["policy_sha256"]:raise ValueError("issue_policy_bytes_changed")
    return validate_policy(strict_json(raw.decode("utf-8")))


def app_host(project,c,trees=None,store=None,reviewer=None):
    credentials=AppCredentials(c["app_id"],c["installation_id"],c["repository_id"],c["repository"],signer=pem_signer(c["private_key_file"]))
    return AppGitHubHost(trees,store,{project:c["repository"]},credentials=credentials,reviewer=reviewer)


def issue_source(c,host):
    inspector=IssueScopeInspector(host,c["source_repository"],c["repository"],RuntimeProbe(c["app_server"]))
    return GitHubIssueSource(host,c["repository"],c["repository_id"],inspector)


def build_issue_bindings(config):
    from .service.issue_admission import IssueBinding
    result={}
    for project,c in config.get("issue_connections",{}).items():
        connector=config["connectors"].get(c["connector_id"])
        if connector is None or project not in connector["projects"]:raise ValueError("issue_connector_not_registered")
        host=app_host(project,c)
        result[project]=IssueBinding(_policy(c),issue_source(c,host),c["connector_id"],c["repository_id"])
    return result


def build_connector_transports(config,store,api,connector,hosts):
    from .connector.issue_transport import ConsumerHTTP,IssueTransport,IssueEventHandler
    from .connector.issue_messages import IssueMessenger
    from .service.cli import read_token
    transports=[]
    for project,c in config.get("issue_connections",{}).items():
        if c["connector_id"]!=config["connector_id"] or Path(c["app_server"])!=Path(config["app_server"]):raise ValueError("issue_connector_identity_changed")
        if not _policy(c)["initially_enabled"]:continue
        host=hosts[project];source=issue_source(c,host)
        handler=IssueEventHandler(project,source,api,connector,lambda s,h=host:IssueMessenger(h,store,s))
        remote=ConsumerHTTP(c["transport_url"],c["consumer_id"],lambda p=c["consumer_token_file"]:read_token(p))
        binding={k:c[k] for k in ("app_id","installation_id","repository_id")}
        transports.append(IssueTransport(store,remote,binding,handler))
    return transports


class RoutedGitHubHost:
    def __new__(cls,trees,store,projects,issue_hosts,reviewer):
        from .connector.delivery import GitHubHost,bounded_http
        remaining={p:r for p,r in projects.items() if p not in issue_hosts}
        legacy=GitHubHost(trees,store,remaining,reviewer=reviewer) if remaining else None
        by_repo={h._credentials.repository:h for h in issue_hosts.values()}
        if legacy:
            for r in remaining.values():
                if r in by_repo:raise ValueError("ambiguous_github_authority")
                by_repo[r]=legacy
        class Router(GitHubHost):
            def __init__(self):
                self.trees,self.store,self.projects=trees,store,dict(projects)
                self.reviewer=reviewer;self.clients={};self.creator=None;self.transport=bounded_http
            def _creator(self):
                if len(issue_hosts)!=1:raise ValueError("ambiguous_public_bot_identity")
                return next(iter(issue_hosts.values()))._creator()
            def _client(self,r):return by_repo[r]._client(r)
            def _conversations(self,r,p):return by_repo[r]._conversations(r,p)
            def _push(self,path,branch,r,env=None):return by_repo[r]._push(path,branch,r,env)
            def publish_acceptance(self,r,h,review):return by_repo[r].publish_acceptance(r,h,review)
            def read_acceptance(self,r,h):return by_repo[r].read_acceptance(r,h)
        return Router()
