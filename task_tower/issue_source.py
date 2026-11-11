"""Fresh trusted GitHub reads; webhook payloads never attest reporter rights."""
import hashlib
import time
from urllib.parse import quote
from .issue_intake import parse_request,FIELDS
from .service.store import encoded


class GitHubIssueSource:
    def __init__(self,host,repository,repository_id,scope_inspector):
        self.host,self.repository,self.repository_id,self.scope_inspector=host,repository,repository_id,scope_inspector

    def snapshot(self,number,*,inspect_scope=True):
        if type(number) is not int or number<1:raise ValueError("invalid_issue_number")
        r=self.repository; repo=self.host._request(r,"GET","/")
        if repo.get("id")!=self.repository_id:raise ValueError("repository_identity_changed")
        issue=self.host._request(r,"GET","/issues/"+str(number));user=issue.get("user",{})
        if issue.get("number")!=number or issue.get("pull_request") or type(user.get("id")) is not int or user["id"]<1 or not isinstance(user.get("login"),str):raise ValueError("invalid_source_issue")
        original=issue.get("body") or ""; request=parse_request(original); material=[]
        comments=self.host._pages(r,"/issues/"+str(number)+"/comments")
        for row in sorted(comments,key=lambda v:v.get("id",0)):
            if row.get("user",{}).get("id")==user["id"] and row.get("user",{}).get("type")=="User":
                fields=parse_request(row.get("body"))
                if fields:request.update(fields);material.append(dict(id=row.get("id"),body=row.get("body")))
        body="\n".join("## "+dict(reproduction="Reproduction",expected_behavior="Expected behavior",acceptance_criteria="Acceptance criteria",files="Files")[k]+"\n"+request[k] for k in FIELDS if k in request)
        push=False
        if user["id"]!=repo.get("owner",{}).get("id") and user.get("type")=="User":
            try:
                permissions=self.host._request(r,"GET","/collaborators/"+quote(user["login"],safe="")+"/permission")
                push=permissions.get("user",{}).get("id")==user["id"] and permissions.get("user",{}).get("permissions",{}).get("push") is True
            except Exception:push=False
        verified_at=time.time()
        paths=tuple(line.strip().removeprefix("- ").strip("`") for line in request.get("files","").splitlines())
        eligible=user.get("type")=="User" and (user["id"]==repo.get("owner",{}).get("id") or push)
        scope=self.scope_inspector(paths) if inspect_scope and eligible and all(request.get(k) for k in FIELDS) else dict(regular_paths=[],runtime_scope_verified=False)
        revision=hashlib.sha256(encoded(dict(repository_id=self.repository_id,issue_number=number,reporter_id=user["id"],original_body=original,clarifications=material)).encode()).hexdigest()
        return dict(repository=r,repository_id=self.repository_id,issue_number=number,reporter_id=user["id"],owner_id=repo["owner"]["id"],reporter_type=user.get("type"),push_collaborator=push,verified_at=verified_at,state=issue.get("state"),body=body,source_revision=revision,existing_regular_paths=scope.get("regular_paths",[]),runtime_scope_verified=scope.get("runtime_scope_verified") is True,base_sha=scope.get("base_sha"))
