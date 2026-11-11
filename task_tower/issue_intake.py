"""Fixed operator policy. Issue prose is untrusted context, never a command."""
from dataclasses import dataclass
import json
import math
from pathlib import PurePosixPath
import re

# Fixed trusted policy remains available in the stdlib-only core image.
INITIAL_POLICY={'allowed_paths': ['README.md', 'AGENTS.md', 'docs/**/*.md', 'task_tower/**/*.py', 'tests/**/*.py'], 'clarification_required_fields': ['reproduction', 'expected_behavior', 'acceptance_criteria'], 'eligible_reporter_roles': ['repository_owner', 'push_collaborator'], 'excluded_changes': ['workflows', 'dependencies_lockfiles', 'executables_bootstrap', 'credentials_auth_acl_protection', 'admission_policy', 'migrations', 'destructive', 'recovery', 'other_repositories'], 'initially_enabled': False, 'max_active_authors': 1, 'max_admissions_per_day': 2, 'max_author_turns': 3, 'max_changed_lines': 1000, 'max_execution_minutes': 120, 'max_files': 20, 'repository': 'Sibiya666/task-tower', 'verification': {'command': '/task-tower verified <40-lowercase-hex-sha>', 'fresh_head_base_required': True, 'reporter': 'original_numeric_reporter'}, 'version': 1}
FIELDS=("reproduction","expected_behavior","acceptance_criteria","files")
HEADINGS={"reproduction":"reproduction","expected behavior":"expected_behavior","acceptance criteria":"acceptance_criteria","files":"files", "\u0432\u043e\u0441\u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0435":"reproduction", "\u043e\u0436\u0438\u0434\u0430\u0435\u043c\u043e\u0435 \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u0435":"expected_behavior", "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a\u0438":"acceptance_criteria", "\u0444\u0430\u0439\u043b\u044b":"files"}
# Security/runtime/bootstrap files cannot authorize changes to their own boundary.
DENIED={"issue_intake","reporter_verification","issue_source","issue_runtime","issue_bootstrap","issue_operator","child_environment","processes","windows_process","windows_job","github_source","github_tasks","github_publication","delivery_policy","executor","executor_profiles","reviewer","shared_worker","beads_admission","project_connections","intake_reload","preparing_recovery","__main__","bootstrap"}

DENIED.update({"project_worker","postmerge_worker","postmerge_journal","pipeline_worker","pipeline_shared","pipeline_roles","pipeline_publish","pipeline_policy","pipeline_journal","pipeline_inputs","pipeline","merge_events","executor_worker","executor_queue","executor_harness","dispatch_selection","dispatch_delivery","dispatcher"})


def validate_policy(policy):
    if not isinstance(policy,dict) or set(policy)!=set(INITIAL_POLICY) or type(policy.get("initially_enabled")) is not bool:
        raise ValueError("invalid_issue_policy")
    expected=dict(INITIAL_POLICY,initially_enabled=policy["initially_enabled"])
    if json.dumps(policy,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):raise ValueError("unapproved_issue_policy")
    return policy


def parse_request(body):
    if not isinstance(body,str) or len(body.encode("utf-8"))>16384: return {}
    body=re.sub(r"<!--[\s\S]*?-->","",body)
    result={}; current=None
    for line in body.splitlines():
        heading=re.fullmatch(r"#{2,3}\s+(.+)",line)
        if heading:
            current=HEADINGS.get(heading[1].strip().lower())
            if current: result[current]=""
        elif current: result[current]+=("\n" if result[current] else "")+line
    return {k:v.strip() for k,v in result.items() if v.strip()}


def allowed_path(value):
    if not isinstance(value,str) or not value or len(value)>200 or "\\" in value or not re.fullmatch(r"[A-Za-z0-9_./-]+",value): return False
    parts=PurePosixPath(value).parts
    if value.startswith("/") or any(p.startswith(".") for p in parts) or str(PurePosixPath(value))!=value: return False
    if value in ("README.md","AGENTS.md"): return True
    if len(parts)<2: return False
    if parts[0]=="docs" and value.endswith(".md"): return True
    if parts[0] not in ("task_tower","tests") or not value.endswith(".py"): return False
    if parts[0]=="task_tower" and (len(parts)!=2 or PurePosixPath(value).stem in DENIED): return False
    return True


@dataclass(frozen=True)
class AdmissionDecision:
    state: str
    reason: str
    paths: tuple = ()
    request: dict | None = None


def evaluate_issue(snapshot,policy,counters,now):
    validate_policy(policy)
    def wait(reason): return AdmissionDecision("needs_input",reason)
    if not policy["initially_enabled"]: return wait("policy_disabled")
    if not math.isfinite(now) or type(snapshot.get("verified_at")) not in (float,int) or not 0<=now-snapshot["verified_at"]<=60: return wait("fresh_source_required")
    if snapshot.get("repository")!=policy["repository"] or snapshot.get("state")!="open" or snapshot.get("reporter_type")!="User": return wait("source_ineligible")
    if any(type(snapshot.get(k)) is not int or snapshot[k]<1 for k in ("repository_id","issue_number","reporter_id","owner_id")): return wait("numeric_identity_required")
    if snapshot["reporter_id"]!=snapshot["owner_id"] and snapshot.get("push_collaborator") is not True: return wait("owner_admission_required")
    for key,limit in (("active_authors",policy["max_active_authors"]),("admissions_today",policy["max_admissions_per_day"])):
        if type(counters.get(key)) is not int or counters[key]<0 or counters[key]>=limit: return wait("policy_budget_exhausted")
    request=parse_request(snapshot.get("body"))
    if any(not request.get(k) for k in FIELDS): return AdmissionDecision("clarify","reproduction_expected_behavior_acceptance_and_files_required")
    if any(len(request[k].encode())>4096 for k in FIELDS): return wait("request_too_large")
    if snapshot.get("runtime_scope_verified") is not True: return wait("runtime_scope_required")
    paths=tuple(line.strip().removeprefix("- ").strip("`") for line in request["files"].splitlines())
    regular=snapshot.get("existing_regular_paths",[])
    if not 1<=len(paths)<=policy["max_files"] or len(set(paths))!=len(paths) or any(not allowed_path(p) or p not in regular for p in paths): return wait("unsupported_source_scope")
    return AdmissionDecision("admit","fixed_policy",paths,request)


def validate_changes(changes,paths,policy):
    validate_policy(policy)
    if not isinstance(changes,list) or not 1<=len(changes)<=policy["max_files"] or len({v.get("path") for v in changes})!=len(changes): raise ValueError("invalid_issue_diff")
    lines=0
    for v in changes:
        if (v.get("path") not in paths or not allowed_path(v["path"]) or v.get("status")!="M" or v.get("old_mode")!="100644" or v.get("new_mode")!="100644" or any(type(v.get(k)) is not int or v[k]<0 for k in ("added","deleted"))): raise ValueError("issue_diff_outside_scope")
        lines+=v["added"]+v["deleted"]
    if lines>policy["max_changed_lines"]: raise ValueError("issue_diff_budget_exceeded")


def validate_issue_diff(text,paths,policy):
    if not isinstance(text,str) or not text.startswith('diff --git ') or any(token in text for token in ('GIT binary patch','Binary files ','new file mode ','deleted file mode ','old mode ','new mode ','rename from ','rename to ','copy from ','copy to ')):
        raise ValueError('unsupported_issue_diff')
    changes=[];current=None
    for line in text.splitlines():
        if line.startswith('diff --git '):
            match=re.fullmatch(r'diff --git a/([A-Za-z0-9_./-]+) b/([A-Za-z0-9_./-]+)',line)
            if not match or match[1]!=match[2]:raise ValueError('nonregular_issue_diff')
            current=dict(path=match[1],status='M',old_mode=None,new_mode=None,added=0,deleted=0);changes.append(current)
        elif line.startswith('index '):
            match=re.fullmatch(r'index [a-f0-9]+\.\.[a-f0-9]+ (100644)',line)
            if current is None or not match:raise ValueError('regular_issue_mode_required')
            current['old_mode']=current['new_mode']=match[1]
        elif current is not None and line.startswith('+') and not line.startswith('+++ '):current['added']+=1
        elif current is not None and line.startswith('-') and not line.startswith('--- '):current['deleted']+=1
    validate_changes(changes,paths,policy)
