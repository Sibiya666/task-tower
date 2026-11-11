"""Narrow per-thread permission profile; real model-free sandbox probe before intake."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from .issue_intake import allowed_path
from .project_connections import safe_config_path

PROFILE="task-tower-issue"


def network_denied(error):
    import errno
    return isinstance(error,PermissionError) or getattr(error,'errno',None) in (errno.EACCES,errno.EPERM) or getattr(error,'winerror',None)==10013


def runtime_config(root,paths):
    root=Path(root).absolute();safe_config_path(root/".scope-check")
    if len(paths)>20 or len(set(paths))!=len(paths):raise ValueError("invalid_issue_paths")
    prefix='permissions.'+PROFILE+'.filesystem.'
    config={"default_permissions":PROFILE,prefix+'":minimal"':"read",prefix+'":workspace_roots"."."':"read",'permissions.'+PROFILE+'.network.enabled':False}
    if os.name=="nt":config[prefix+'":root"']="read"  # Required by the installed Windows sandbox; private ACLs still apply.
    config[prefix+json.dumps(str(Path(sys.executable).parent))]="read"
    for hidden in (".task-tower",".beads",".codex",".agents",".env",".env.local",".env.production"):
        config[prefix+'":workspace_roots".'+json.dumps(hidden)]="deny"
    config[prefix+'":workspace_roots".".task-tower/issue-scratch"']="write"
    for relative in paths:
        path=safe_config_path(root/relative)
        if not allowed_path(relative) or not path.is_file() or path.stat().st_nlink!=1:raise ValueError("regular_declared_file_required")
        config[prefix+'":workspace_roots".'+json.dumps(relative)]="write"
    return config


def nested_config(flat):
    import tomllib
    result={}
    def merge(target,source):
        for key,value in source.items():
            if isinstance(value,dict):merge(target.setdefault(key,{}),value)
            else:target[key]=value
    for key,value in flat.items():merge(result,tomllib.loads(key+'='+json.dumps(value)))
    return result


def profile_arguments(flat):
    nested=nested_config(flat)
    def toml(value):
        if isinstance(value,dict):return '{'+', '.join(json.dumps(k)+' = '+toml(v) for k,v in value.items())+'}'
        return json.dumps(value)
    # Pass complete tables: CLI dotted-key parsing must never split a quoted file name.
    return ['-c','default_permissions='+toml(nested['default_permissions']),'-c','permissions='+toml(nested['permissions'])]


def validate_scope(scope):
    import math
    if not isinstance(scope,dict) or set(scope)!={"paths","deadline"} or not isinstance(scope["paths"],list) or not len(scope["paths"])<=20 or type(scope["deadline"]) not in (float,int) or not math.isfinite(scope["deadline"]) or scope["deadline"]<=0:
        raise ValueError("invalid_issue_scope")
    if len(set(scope["paths"]))!=len(scope["paths"]) or any(not allowed_path(p) for p in scope["paths"]):raise ValueError("invalid_issue_scope_paths")
    return scope


def scope_parameters(command,cwd):
    scope=command.get("issue_scope")
    if scope is None:return {}
    validate_scope(scope)
    if time.time()>scope["deadline"]:raise ValueError("issue_execution_deadline")
    paths=[] if command.get("kind") in ("review","main_review") else scope["paths"]
    return dict(config=nested_config(runtime_config(cwd,paths)))


PROBE = r'''import json, pathlib, socket, sys
root=pathlib.Path(sys.argv[1]);outside=pathlib.Path(sys.argv[2]);results={}
try:
 (root/'docs/example.md').write_text('allowed',encoding='utf-8');results['allowed']=True
except OSError:results['allowed']=False
for name,path in [('other_source',root/'task_tower/service/store.py'),('other_doc',root/'docs/other.md'),('outside',outside/'new.txt')]:
 try:path.write_text('forbidden',encoding='utf-8');results[name]=False
 except OSError:results[name]=True
try:(outside/'private.txt').read_text(encoding='utf-8');results['private_read']=False
except OSError:results['private_read']=True
s=socket.socket();s.settimeout(2);network_error=None
try:s.connect((sys.argv[3],443));results['network']=False
except OSError as e:
 results['network']=network_denied(e)
 network_error=dict(type=type(e).__name__,errno=e.errno,winerror=getattr(e,'winerror',None))
finally:s.close()
print(json.dumps(dict(checks=results,network_error=network_error),sort_keys=True))
'''


class RuntimeProbe:
    def __init__(self,executable):
        self.executable=Path(executable);self._receipt=None;self._failed=False;self.last_result=None
    def verify(self):
        import inspect,ipaddress,socket
        digest=hashlib.sha256(safe_config_path(self.executable).read_bytes()).hexdigest()
        if self._failed:raise ValueError("issue_runtime_probe_needs_input")
        if self._receipt and self._receipt["executable_sha256"]==digest and 0<=time.time()-self._receipt["verified_at"]<=60:return self._receipt
        self._failed=True  # No automatic retry after a failed/unknown fixed command.
        # A closed localhost port says nothing about outbound isolation. Use a
        # fixed approved external origin, with a successful trusted-host control.
        addresses=socket.getaddrinfo("api.github.com",443,socket.AF_INET,socket.SOCK_STREAM)
        address=next((a[4][0] for a in addresses if ipaddress.ip_address(a[4][0]).is_global),None)
        if address is None:raise ValueError("public_github_control_required")
        with socket.create_connection((address,443),timeout=3):pass
        from .connector.app_server import StdioTransport
        with tempfile.TemporaryDirectory(prefix="task-tower-issue-sandbox-") as temp:
            parent=Path(temp);root=parent/"workspace";outside=parent/"outside"
            (root/"docs").mkdir(parents=True);(root/"task_tower/service").mkdir(parents=True)
            from .connector.diagnostics import create_private_directory
            create_private_directory(outside)
            for path in (root/"docs/example.md",root/"docs/other.md",root/"task_tower/service/store.py",outside/"private.txt"):path.write_text("synthetic fixture",encoding="utf-8")
            script=root/"probe.py";script.write_text(inspect.getsource(network_denied)+"\n"+PROBE,encoding="utf-8")
            wire=StdioTransport(self.executable,root,timeout=20,profile_config=runtime_config(root,["docs/example.md"]))
            try:
                result=wire.request("command/exec",dict(command=[sys.executable,"-B",str(script),str(root),str(outside),address],cwd=str(root),timeoutMs=10000))
                report=json.loads(result.get("stdout",""));checks=report.get("checks",{})
                self.last_result=dict(exit_code=result.get("exitCode"),checks=checks,network_error=report.get("network_error"),control_origin="api.github.com:443",executable_sha256=digest)
                required={"allowed","other_source","other_doc","outside","private_read","network"}
                if result.get("exitCode")!=0 or set(checks)!=required or any(v is not True for v in checks.values()):raise ValueError("issue_sandbox_not_verified")
                self._receipt=dict(executable_sha256=digest,checks=checks,verified_at=time.time(),control_origin="api.github.com:443")
            finally:wire.close()
        self._failed=False
        return self._receipt


class IssueScopeInspector:
    def __init__(self,host,repository_root,repository,probe):
        self.host,self.root,self.repository,self.probe=host,Path(repository_root),repository,probe
    def __call__(self,paths):
        if not paths or len(paths)>20 or any(not allowed_path(p) for p in paths):return dict(regular_paths=[],runtime_scope_verified=False)
        self.host._remote(self.root,self.repository)
        self.host._trusted_git(self.root,"fetch","origin","main",timeout=60)
        base=self.host._trusted_git(self.root,"rev-parse","FETCH_HEAD",timeout=10)
        rows=self.host._trusted_git(self.root,"ls-tree",base,"--",*paths,timeout=10).splitlines() if paths else []
        regular=[row.split("\t",1)[1] for row in rows if row.startswith("100644 blob ") and "\t" in row]
        try:proof=self.probe.verify();verified=all(v is True for v in proof["checks"].values())
        except Exception:verified=False
        return dict(regular_paths=regular,runtime_scope_verified=verified,base_sha=base)
