"""Original-reporter confirmation of the exact published candidate; no prose inference."""
from datetime import datetime
import hashlib
import re
from .connector.issue_messages import source_identity
from .service.store import encoded


def _time(value):
    if not isinstance(value,str): raise ValueError("invalid_github_timestamp")
    date=datetime.fromisoformat(value.replace("Z","+00:00"))
    if date.tzinfo is None: raise ValueError("timezone_required")
    return date.timestamp()


def _pr(candidate,pr):
    if (pr.get("repository")!=candidate["source"]["repository"] or pr.get("head_repository")!=pr.get("repository") or pr.get("number")!=candidate["pr_number"] or pr.get("head_sha")!=candidate["head_sha"] or pr.get("base_sha")!=candidate["base_sha"] or pr.get("state")!="open" or pr.get("merged") is not False):
        raise ValueError("candidate_source_changed")


def candidate_receipt(issue,pr,reporter_id,test_instructions,created_at):
    source=source_identity(issue)
    if type(reporter_id) is not int or reporter_id!=source["reporter_id"] or not isinstance(test_instructions,str) or not 1<=len(test_instructions.encode())<=4096:
        raise ValueError("actionable_original_reporter_candidate_required")
    if any(not isinstance(pr.get(k),str) or not re.fullmatch(r"[0-9a-f]{40}",pr[k]) for k in ("head_sha","base_sha")) or type(pr.get("number")) is not int or pr["number"]<1:
        raise ValueError("exact_candidate_source_required")
    _time(created_at)
    candidate=dict(version=1,source=source,pr_number=pr["number"],head_sha=pr["head_sha"],base_sha=pr["base_sha"],reporter_id=reporter_id,instructions=test_instructions,created_at=created_at,url="https://github.com/"+source["repository"]+"/pull/"+str(pr["number"]))
    _pr(candidate,pr)
    candidate["candidate_sha256"]=hashlib.sha256(encoded(candidate).encode()).hexdigest()
    return candidate


def validate_verification(comment,candidate,fresh_pr):
    _pr(candidate,fresh_pr)
    source=candidate["source"]
    if (type(comment.get("id")) is not int or comment["id"]<1 or comment.get("user",{}).get("id")!=source["reporter_id"] or comment.get("user",{}).get("type")!="User" or comment.get("body")!="/task-tower verified "+candidate["head_sha"] or comment.get("updated_at")!=comment.get("created_at") or _time(comment.get("created_at"))<=_time(candidate["created_at"]) or comment.get("issue_url")!="https://api.github.com/repos/"+source["repository"]+"/issues/"+str(source["issue_number"])):
        raise ValueError("exact_original_reporter_confirmation_required")
    return dict(comment_id=comment["id"],reporter_id=source["reporter_id"],head_sha=candidate["head_sha"],base_sha=candidate["base_sha"],candidate_sha256=candidate["candidate_sha256"],created_at=comment["created_at"])


def reporter_ready(attempt,host):
    if not attempt.get("source_issue"): return True  # Existing manual task contract.
    c=attempt.get("candidate")
    if not c or c.get("source")!=attempt["source_issue"]: return False
    pr=host.read_pr(c["source"]["repository"],c["pr_number"])
    try:_pr(c,pr)
    except ValueError:return False
    rows=host._pages(c["source"]["repository"],"/issues/"+str(c["source"]["issue_number"])+"/comments")
    confirmations=[]; negatives=[]
    for row in rows:
        try:confirmations.append(validate_verification(row,c,pr))
        except (ValueError,TypeError,KeyError):pass
        try:
            if row.get("user",{}).get("id")==c["reporter_id"] and row.get("user",{}).get("type")=="User" and row.get("body")=="/task-tower changes "+c["head_sha"]:
                negatives.append(_time(row["updated_at"]))
        except (ValueError,TypeError,KeyError): return False
    return bool(confirmations) and max(_time(v["created_at"]) for v in confirmations)>max(negatives,default=float("-inf"))


def require_reporter_receipt(a):
    if not a.get('source_issue'):return
    c=a.get('candidate');v=a.get('reporter_verification')
    if not c or not v or c.get('source')!=a['source_issue'] or any(v.get(k)!=c.get(k) or c.get(k)!=a.get(k) for k in ('head_sha','base_sha')) or v.get('reporter_id')!=a['source_issue']['reporter_id'] or v.get('candidate_sha256')!=c.get('candidate_sha256'):
        raise ValueError('source_bound_reporter_receipt_required')
