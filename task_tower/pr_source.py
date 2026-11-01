"""Bounded read-only PR observations and complete local Git review material.

No status, review, merge or policy writes live here. REST patches are audit
metadata only. Unknown server gates remain blocking, never assumed satisfied.
Transport contract: (method,url,headers,body,timeout,max_bytes) ->
{status:int,headers:dict,body:bytes}. POST is used only for a fixed GraphQL query.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request
import uuid

from .github_source import resolve_token
from .executor_profiles import _pins, profile_fingerprint
from .pr_policy import (LIMITS, SHA, HASH, REPOSITORY, canonical, exact, identifier,
                        integer, policy_fingerprint, private_paths, strict_json, text)
from .processes import run_command


class PRSourceError(RuntimeError):
    pass


def _fail(reason='source_incomplete'):
    raise PRSourceError(reason)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        _fail()


def _transport(method, url, headers, body, timeout, max_bytes):
    request=urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            return dict(status=response.status, headers=dict(response.headers), body=response.read(max_bytes+1))
    except (OSError, urllib.error.URLError):
        _fail()


def current_ci(checks, statuses, task, head):
    """Choose the latest observation per app/context, retaining all audit rows.

    Check-run ids are monotonic across reruns; checks API has no run_attempt
    field. Include all filter=all runs and use id, not a guessed workflow name.
    """
    latest={}; names={}; acceptance=[]; kept_status=[]; kept_checks=[]
    for run in checks:
        try:
            integer(run['id']); name=text(run['name']); app=integer(run['app']['id'])
            if run['head_sha']!=head: _fail()
            if name=='task-tower/pr-acceptance': _fail('untrusted_acceptance_context')
            key=('check',name,app); names.setdefault(name,set()).add(('check',app))
            if key not in latest or run['id']>latest[key]['id']: latest[key]=run
            kept_checks.append(run)
        except (ValueError,KeyError,TypeError): _fail()
    for status in statuses:
        try:
            integer(status['id']); name=text(status['context']); actor=text(status['creator']['login']).casefold()
            if name=='task-tower/pr-acceptance':
                if actor!=task['publisher_account'].casefold(): _fail('untrusted_acceptance_context')
                acceptance.append(status); continue
            key=('status',name,actor); names.setdefault(name,set()).add(('status',actor))
            if key not in latest or status['id']>latest[key]['id']: latest[key]=status
            kept_status.append(status)
        except (ValueError,KeyError,TypeError): _fail()
    reasons=[]
    for name, identities in names.items():
        if len(identities)!=1: reasons.append('ambiguous_check_publisher')
    for key,row in latest.items():
        success=(row.get('status')=='completed' and row.get('conclusion')=='success') if key[0]=='check' else row.get('state')=='success'
        if not success: reasons.append('ci_not_success')
    for required in task['required_checks']:
        key=(('check',required['context'],required['app_id']) if required['app_id'] is not None
             else ('status',required['context'],task['publisher_account'].casefold()))
        if key not in latest or names.get(required['context'])!={key[:1]+key[2:]}:
            reasons.append('required_check_missing_or_untrusted')
    bundle=dict(checks=kept_checks,statuses=kept_status,latest=[dict(identity=list(k),observation=v) for k,v in sorted(latest.items())])
    return dict(bundle, ready=not reasons,reasons=sorted(set(reasons)),
                acceptance_statuses=acceptance,sha256=policy_fingerprint(bundle))


class PRSource:
    def __init__(self, connection, policy, *, transport=None):
        self.connection=connection; self.repository=text(connection.repository, REPOSITORY).casefold()
        self.policy=policy; self.transport=transport or _transport
        self.limits={k:integer(policy.get(k,v[0]),v[1],v[2]) for k,v in LIMITS.items()}
        self.headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','User-Agent':'Task-Tower'}
        # Fixture transports never resolve real credentials.
        if transport is None:
            token=resolve_token()
            if token: self.headers['Authorization']='Bearer '+token

    def _request(self, method, url, body=None):
        try:
            if not isinstance(url,str) or not url.startswith('https://api.github.com/'): _fail()
            if method=='GET':
                if body is not None: _fail()
            elif method=='POST':
                if url!='https://api.github.com/graphql' or not isinstance(body,dict) or not isinstance(body.get('query'),str) or not body['query'].startswith('query(') or re.search(r'\bmutation\b',body['query']): _fail()
            else: _fail()
            response=self.transport(method,url,dict(self.headers),None if body is None else canonical(body).encode('utf-8'),
                                    self.limits['request_timeout_seconds'],self.limits['max_response_bytes'])
            exact(response,{'status','headers','body'})
            if type(response['status']) is not int or response['status']!=200 or not isinstance(response['headers'],dict): _fail()
            raw=response['body']
            if not isinstance(raw,bytes) or len(raw)>self.limits['max_response_bytes']: _fail()
            headers={k.lower():v for k,v in response['headers'].items()}
            if 'content-length' in headers and int(headers['content-length'])!=len(raw): _fail()
            return strict_json(raw.decode('utf-8'))
        except PRSourceError: raise
        except Exception: _fail()

    def _get(self,path):
        if (path and not path.startswith('/')) or '..' in path or '#' in path: _fail()
        return self._request('GET','https://api.github.com/repos/'+self.repository+path)

    def _pages(self,path,key=None):
        result=[]; total=None; seen=set()
        for page in range(1,self.limits['max_pages']+1):
            payload=self._get(path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
            rows=payload.get(key) if key is not None and isinstance(payload,dict) else payload
            if not isinstance(rows,list) or len(rows)>100: _fail()
            if key is not None:
                try: count=integer(payload['total_count'],0)
                except (ValueError,KeyError): _fail()
                if total is not None and count!=total: _fail()
                total=count
            for row in rows:
                if not isinstance(row,dict): _fail()
                identity=row.get('id',row.get('sha'))
                if identity is not None:
                    if identity in seen: _fail()
                    seen.add(identity)
            result.extend(rows)
            if len(rows)<100:
                if total is not None and total!=len(result): _fail()
                return result
        _fail()

    def main_sha(self):
        try: return text(self._get('/git/ref/heads/main')['object']['sha'],SHA)
        except (ValueError,KeyError,TypeError): _fail()

    def _threads(self,number):
        owner,name=self.repository.split('/'); cursor=None; rows=[]; total=None
        query='query($owner:String!,$name:String!,$number:Int!,$after:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewDecision reviewThreads(first:100,after:$after){totalCount pageInfo{hasNextPage endCursor} nodes{id isResolved isOutdated}}}}}'
        for _ in range(self.limits['max_pages']):
            payload=self._request('POST','https://api.github.com/graphql',dict(query=query,variables=dict(owner=owner,name=name,number=number,after=cursor)))
            try:
                if payload.get('errors'): _fail()
                pr=payload['data']['repository']['pullRequest']; page=pr['reviewThreads']
                count=integer(page['totalCount'],0); nodes=page['nodes']; info=page['pageInfo']
                if total is not None and total!=count: _fail()
                total=count
                if not isinstance(nodes,list) or len(nodes)>100: _fail()
                for node in nodes:
                    if type(node['isResolved']) is not bool or type(node['isOutdated']) is not bool or not isinstance(node['id'],str): _fail()
                    if node['id'] in {r['id'] for r in rows}: _fail()
                    rows.append(node)
                if type(info['hasNextPage']) is not bool: _fail()
                if not info['hasNextPage']:
                    if len(rows)!=count: _fail()
                    return dict(nodes=rows,review_decision=pr['reviewDecision'])
                next_cursor=text(info['endCursor'])
                if next_cursor==cursor: _fail()
                cursor=next_cursor
            except (KeyError,TypeError,ValueError): _fail()
        _fail()

    def _platforms(self,task,head,base,ci):
        """API-proven current Actions jobs, never job-name OS heuristics.

        Supported labels are a conservative explicit subset of GitHub's
        standard hosted runner table. Larger/self-hosted/custom labels require
        a future trusted provider. Specific-attempt jobs bind rerun identity;
        re-read the current run/check after collecting the jobs.
        """
        labels={
            'linux': {'ubuntu-latest','ubuntu-22.04','ubuntu-24.04','ubuntu-26.04','ubuntu-22.04-arm','ubuntu-24.04-arm','ubuntu-26.04-arm','ubuntu-slim'},
            'windows': {'windows-latest','windows-2022','windows-2025','windows-2025-vs2026','windows-11-arm','windows-11-vs2026-arm'},
            'macos': {'macos-latest','macos-14','macos-15','macos-26','macos-15-intel','macos-26-intel','xcode-27'},
        }
        api='https://api.github.com/repos/'+self.repository
        proof=[]; platforms=set(); cache={}
        try:
            def refs(rows):
                if not isinstance(rows,list) or len(rows)!=1: return False
                row=rows[0]
                return (row['number']==task['pr_number'] and row['head']['sha']==head and row['base']['sha']==base
                        and row['head']['repo']['url'].casefold()==api and row['base']['repo']['url'].casefold()==api)
            for required in task['required_checks']:
                if required['app_id'] is None: continue
                candidates=[item['observation'] for item in ci['latest']
                            if item['identity']==['check',required['context'],required['app_id']]]
                if len(candidates)!=1: _fail('platform_proof_required')
                check=candidates[0]
                # A non-Actions required check can remain required CI, but it
                # cannot supply Actions platform authority.
                if check['app'].get('slug')!='github-actions': continue
                suite_id=integer(check['check_suite']['id'])
                if suite_id not in cache:
                    suite=self._get('/check-suites/'+str(suite_id))
                    if suite['id']!=suite_id or suite['head_sha']!=head or suite['app']['id']!=required['app_id'] or suite['app']['slug']!='github-actions' or suite['status']!='completed' or suite['conclusion']!='success' or not refs(suite['pull_requests']): _fail('platform_proof_required')
                    runs=self._pages('/actions/runs?check_suite_id='+str(suite_id),'workflow_runs')
                    if len(runs)!=1: _fail('platform_proof_required')
                    run=runs[0]; run_id=integer(run['id']); attempt=integer(run['run_attempt'])
                    if run['check_suite_id']!=suite_id or run['head_sha']!=head or run['event']!='pull_request' or run['status']!='completed' or run['conclusion']!='success' or run['repository']['full_name'].casefold()!=self.repository or run['head_repository']['full_name'].casefold()!=self.repository or not refs(run['pull_requests']): _fail('platform_proof_required')
                    jobs=self._pages(f'/actions/runs/{run_id}/attempts/{attempt}/jobs','jobs')
                    fresh=self._get('/actions/runs/'+str(run_id))
                    fields=('id','check_suite_id','head_sha','event','status','conclusion','run_attempt','repository','head_repository','pull_requests')
                    if any(fresh[k]!=run[k] for k in fields): _fail('platform_proof_required')
                    cache[suite_id]=(suite,run,jobs)
                suite,run,jobs=cache[suite_id]
                if suite['app']['id']!=check['app']['id']: _fail('platform_proof_required')
                matches=[job for job in jobs if job.get('check_run_url')==api+'/check-runs/'+str(check['id'])]
                if len(matches)!=1: _fail('platform_proof_required')
                job=matches[0]; integer(job['id']); integer(job['runner_id']); integer(job['runner_group_id'],0)
                if (job['run_id']!=run['id'] or job['run_url']!=api+'/actions/runs/'+str(run['id']) or job['head_sha']!=head
                    or job['status']!='completed' or job['conclusion']!='success'
                    or ('run_attempt' in job and job['run_attempt']!=run['run_attempt'])
                    or job['runner_group_id']!=0 or job['runner_group_name']!='GitHub Actions' or not isinstance(job['runner_name'],str) or not job['runner_name']): _fail('platform_proof_required')
                actual=job['labels']
                if not isinstance(actual,list) or len(actual)!=1 or not isinstance(actual[0],str): _fail('platform_proof_required')
                oses=[platform for platform,known in labels.items() if actual[0] in known]
                if len(oses)!=1: _fail('platform_proof_required')
                observed=self._get('/check-runs/'+str(check['id']))
                for field in ('id','name','app','status','conclusion','head_sha','check_suite'):
                    if observed[field]!=check[field]: _fail('platform_proof_required')
                platforms.add(oses[0]); proof.append(dict(platform=oses[0],check=check,suite=suite,run=run,job=job))
            missing=set(task.get('required_platforms',[]))-platforms
            return dict(ready=not missing,reasons=['platform_proof_required'] if missing else [],
                        platforms=sorted(platforms),observations=proof,sha256=policy_fingerprint(proof))
        except PRSourceError as exc:
            if str(exc)!='platform_proof_required': raise
        except (KeyError,ValueError,TypeError,AttributeError): pass
        return dict(ready=False,reasons=['platform_proof_required'],platforms=sorted(platforms),observations=proof,sha256=policy_fingerprint(proof))

    def protection(self,task):
        """Conservatively support classic strict protection plus known rules.

        The effective branch rules endpoint includes inherited rules. Resolve
        every supplying ruleset and reject any bypass list, including User,
        role/team/integration and unknown future types. No permission guessing.
        """
        reasons=[]
        try:
            repo=self._get(''); actor=self._request('GET','https://api.github.com/user')
            classic=self._get('/branches/main/protection')
            rules=self._pages('/rules/branches/main')
            details=[]; ids=set()
            for rule in rules:
                rid=integer(rule['ruleset_id'])
                if rid not in ids:
                    ids.add(rid); url=rule['ruleset_source_type']; source=rule['ruleset_source']
                    if url=='Repository' and source.casefold()==self.repository.casefold():
                        detail=self._get('/rulesets/'+str(rid))
                    elif url=='Organization' and source.casefold()==self.repository.split('/')[0].casefold():
                        detail=self._request('GET',f'https://api.github.com/orgs/{source}/rulesets/{rid}')
                    else: _fail('protection_unverified')
                    if detail['id']!=rid or detail['enforcement']!='active' or detail['bypass_actors']!=[]: reasons.append('actor_bypass_or_unknown')
                    details.append(detail)
                if rule['type'] not in {'deletion','non_fast_forward','required_status_checks','pull_request','required_signatures','required_linear_history'}:
                    reasons.append('unsupported_server_rule')
                if rule['type']=='required_linear_history': reasons.append('merge_commit_forbidden')
                if rule['type']=='required_status_checks' and rule['parameters'].get('strict_required_status_checks_policy') is not True: reasons.append('strict_checks_required')
            checks=classic['required_status_checks']
            if checks['strict'] is not True or not checks['checks']: reasons.append('strict_checks_required')
            if classic['enforce_admins']['enabled'] is not True: reasons.append('actor_bypass_or_unknown')
            if classic['allow_force_pushes']['enabled'] is not False or classic['allow_deletions']['enabled'] is not False: reasons.append('unsafe_branch_mutation')
            if classic.get('lock_branch',{}).get('enabled') is not False or classic.get('restrictions') is not None: reasons.append('unsupported_actor_restriction')
            if classic.get('required_linear_history',{}).get('enabled') is True: reasons.append('merge_commit_forbidden')
            review=classic.get('required_pull_request_reviews')
            if review and (review.get('bypass_pull_request_allowances',{}) not in ({},{'users':[],'teams':[],'apps':[]})): reasons.append('actor_bypass_or_unknown')
            if repo['allow_merge_commit'] is not True or actor['login'].casefold()!=task['publisher_account'].casefold(): reasons.append('merge_actor_or_method_mismatch')
            # All explicit policy checks must also be server enforced with app binding.
            server={(r['context'],r['app_id']) for r in checks['checks']}
            if any((r['context'],r['app_id']) not in server for r in task['required_checks']): reasons.append('required_server_check_missing')
            effective=list(server)
            for rule in rules:
                if rule['type']=='required_status_checks':
                    effective.extend((r['context'],r.get('integration_id')) for r in rule['parameters']['required_status_checks'])
            policy_checks={r['context']:r['app_id'] for r in task['required_checks']}
            for context,app in effective:
                text(context)
                if app is not None: integer(app)
                if context=='task-tower/pr-acceptance':
                    if app is not None: reasons.append('untrusted_acceptance_context')
                    continue  # Owned status/receipt must be verified separately.
                if context not in policy_checks or (app is not None and policy_checks[context]!=app): reasons.append('server_check_not_policy_bound')
            bundle=dict(classic=classic,rules=rules,rulesets=details,actor=actor['login'],allow_merge_commit=repo['allow_merge_commit'])
            return dict(bundle,ready=not reasons,reasons=sorted(set(reasons)),sha256=policy_fingerprint(bundle))
        except PRSourceError: raise
        except (KeyError,ValueError,TypeError,AttributeError): _fail('protection_unverified')

    def snapshot(self,task):
        try:
            number=integer(task['pr_number']); prefix='/pulls/'+str(number)
            pr=self._get(prefix); base=self.main_sha(); head=text(pr['head']['sha'],SHA)
            issue_payload=self._issue(task)
            reasons=[]
            if pr['number']!=number or pr['state']!='open' or pr['draft'] is not False or pr['merged'] is not False: reasons.append('pr_not_open_ready')
            if pr['head']['repo']['full_name'].casefold()!=self.repository.casefold() or pr['base']['repo']['full_name'].casefold()!=self.repository.casefold() or pr['base']['ref']!='main': reasons.append('foreign_or_stacked_pr')
            if pr['base']['sha']!=base: reasons.append('base_changed')
            if pr['mergeable'] is not True or pr['mergeable_state']!='clean': reasons.append('mergeability_unknown_or_blocked')
            body=pr.get('body') or ''
            markers=re.findall(r'^Task-Tower: (TT-[A-Z0-9]+(?:-[A-Z0-9]+)*)\s*$',body,re.M)
            if markers!=[task['task_id']]: reasons.append('task_marker_mismatch')
            if re.search(r'\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:(?:https://github\.com/[^\s]+/issues/)|(?:[\w.-]+/[\w.-]+)?#)'+str(task['issue'])+r'\b',body,re.I): reasons.append('closing_keyword_forbidden')
            commits=self._pages(prefix+'/commits'); files=self._pages(prefix+'/files')
            if len(commits)!=pr['commits'] or len(files)!=pr['changed_files'] or not commits or commits[-1]['sha']!=head: _fail()
            reviews=self._pages(prefix+'/reviews'); threads=self._threads(number)
            if any(not t['isResolved'] for t in threads['nodes']): reasons.append('unresolved_review_thread')
            latest={}
            for review in reviews:
                actor=review['user']['id']; integer(review['id']); state=review['state']
                if state not in {'APPROVED','CHANGES_REQUESTED','COMMENTED','DISMISSED','PENDING'}: _fail()
                if state in {'APPROVED','CHANGES_REQUESTED','DISMISSED'} and (actor not in latest or review['id']>latest[actor]['id']): latest[actor]=review
            if any(r['state']=='CHANGES_REQUESTED' for r in latest.values()): reasons.append('changes_requested')
            if threads['review_decision'] not in (None,'APPROVED'): reasons.append('human_review_required')
            ci=self._ci(task,head,base); protection=self.protection(task)
            reasons+=ci['reasons']+protection['reasons']
            if protection['classic'].get('required_pull_request_reviews') and threads['review_decision']!='APPROVED': reasons.append('human_review_required')
            for rule in protection.get('rules',[]):
                if rule['type']=='pull_request':
                    parameters=rule.get('parameters',{})
                    if parameters.get('required_approving_review_count',0)>0 or parameters.get('require_code_owner_review') is True or parameters.get('require_last_push_approval') is True:
                        if threads['review_decision']!='APPROVED': reasons.append('human_review_required')
                    if 'allowed_merge_methods' in parameters and 'merge' not in parameters['allowed_merge_methods']: reasons.append('merge_commit_forbidden')
            # GitHub offers no atomic multi-endpoint read transaction. Refuse
            # mixed observations: collect each mutable acceptance gate again,
            # including the aggregate check list (a new rerun has a new id and
            # cannot be discovered by rereading only the previously known id).
            if canonical(self._pages(prefix+'/reviews'))!=canonical(reviews): _fail()
            if canonical(self._threads(number))!=canonical(threads): _fail()
            if canonical(self.protection(task))!=canonical(protection): _fail()
            fresh_ci=self._ci(task,head,base)
            if canonical({k:v for k,v in fresh_ci.items() if k!='acceptance_statuses'})!=canonical({k:v for k,v in ci.items() if k!='acceptance_statuses'}): _fail()
            # Own acceptance remains a separate current observation; it never
            # enters the nonacceptance input digest or supplies approval here.
            ci['acceptance_statuses']=fresh_ci['acceptance_statuses']
            again=self._get(prefix)
            gate_fields=('number','head','base','body','state','draft','merged','mergeable','mergeable_state','commits','changed_files')
            if canonical({k:again[k] for k in gate_fields})!=canonical({k:pr[k] for k in gate_fields}) or self.main_sha()!=base or self._issue(task)!=issue_payload: _fail()
            result={k:task[k] for k in ('pr_number','issue','issue_id','task_id')}
            result.update(repository=self.repository,head_sha=head,base_sha=base,policy_sha256=policy_fingerprint(self.policy),
                          pr=pr,commits=commits,files=files,reviews=reviews,threads=threads,ci=ci,protection=protection,
                          issue_payload=issue_payload,issue_sha256=policy_fingerprint(issue_payload),
                          acceptance_statuses=ci['acceptance_statuses'],ready=not reasons,reasons=sorted(set(reasons)))
            return result
        except PRSourceError: raise
        except (ValueError,KeyError,TypeError,AttributeError): _fail()

    def _ci(self,task,head,base):
        checks=self._pages('/commits/'+head+'/check-runs?filter=all','check_runs')
        statuses=self._pages('/commits/'+head+'/statuses')
        ci=current_ci(checks,statuses,task,head)
        if task.get('required_platforms'):
            ci['platforms']=self._platforms(task,head,base,ci)
            ci['reasons']=sorted(set(ci['reasons']+ci['platforms']['reasons']))
            ci['ready']=not ci['reasons']
            ci['sha256']=policy_fingerprint({k:ci[k] for k in ('checks','statuses','latest','platforms')})
        return ci

    def _issue(self,task):
        issue=self._get('/issues/'+str(integer(task['issue'])))
        try:
            if issue['id']!=task['issue_id'] or issue['number']!=task['issue'] or 'pull_request' in issue or issue['state']!='open': _fail('issue_binding_mismatch')
            result={k:issue[k] for k in ('id','number','title','body','state','state_reason')}
            if not isinstance(result['title'],str) or not (result['body'] is None or isinstance(result['body'],str)): _fail()
            return result
        except (KeyError,TypeError): _fail()

    def merge_result(self,pr_number,request_uuid):
        integer(pr_number); identifier(request_uuid)
        result=self._get(f'/pulls/{pr_number}/merge-async/{request_uuid}')
        try:
            exact(result,{'status','details'}); details=result['details']
            if not isinstance(details,dict): _fail('merge_result_unknown')
            state=result['status']
            if state=='pending':
                exact(details,{'message','uuid','merge_method','merge_action','expected_head_sha','bypass_rules'})
                if details['uuid']!=request_uuid or details['merge_method']!='merge' or details['merge_action']!='direct_merge' or details['bypass_rules'] is not False: _fail('merge_result_unknown')
                text(details['expected_head_sha'],SHA)
            elif state=='merged': text(details['sha'],SHA)
            elif state not in ('failed','enqueued'): _fail('merge_result_unknown')
            if not isinstance(details.get('message'),str) or not details['message'] or len(details['message'].encode('utf-8'))>8192: _fail('merge_result_unknown')
            return result
        except (KeyError,TypeError,ValueError): _fail('merge_result_unknown')

    def merge_observation(self,pr_number):
        integer(pr_number); pr=self._get(f'/pulls/{pr_number}')
        try:
            if pr['number']!=pr_number or type(pr['merged']) is not bool: _fail('merge_proof_mismatch')
            if pr['merged'] is False: return dict(status='pending')
            if pr['state']!='closed': _fail('merge_proof_mismatch')
            commit=text(pr['merge_commit_sha'],SHA); head=text(pr['head']['sha'],SHA)
            obj=self._get('/git/commits/'+commit)
            parents=[text(p['sha'],SHA) for p in obj['parents']]
            if obj['sha']!=commit or len(parents)!=2 or self.main_sha()!=commit or parents[1]!=head: _fail('merge_proof_mismatch')
            if pr['base']['ref']!='main' or any(pr[side]['repo']['full_name'].casefold()!=self.repository.casefold() for side in ('base','head')): _fail('merge_proof_mismatch')
            return dict(status='confirmed',repository=self.repository,pr_number=pr_number,head_sha=head,
                        merge_commit=commit,parents=parents,actor=pr['merged_by']['login'])
        except (KeyError,ValueError,TypeError): _fail('merge_proof_mismatch')


_DIFF_LIMIT=64*1024*1024
_BLOB_LIMIT=16*1024*1024


def _git(cwd,args,logdir,limit=_DIFF_LIMIT):
    """Fixed host argv only. Fresh mirror config cannot execute repo hooks.

    Use the shared process containment/capped capture runner, not an unbounded
    subprocess pipe. A captured prefix never qualifies as complete material.
    """
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
               GCM_INTERACTIVE='Never',GIT_NO_REPLACE_OBJECTS='1',GIT_LFS_SKIP_SMUDGE='1')
    logs=Path(tempfile.mkdtemp(prefix='git-',dir=logdir))
    argv=['git','--no-optional-locks','-c','core.hooksPath='+str(Path(logdir)/'disabled-hooks'),
          '-c','core.fsmonitor=false','-c','core.untrackedCache=false','-c','protocol.allow=never',
          '-c','protocol.https.allow=always','-c','credential.interactive=false',
          '-c','diff.external=','-c','core.pager=cat',*args]
    result=run_command(argv,Path(cwd),120,env=env,capture=dict(directory=logs,max_bytes_per_stream=limit))
    if result.get('status')!='passed' or result.get('exit_code')!=0 or result.get('cleanup_confirmed') is not True or result.get('stdout_truncated') or result.get('stdout_tail_unknown'):
        _fail('git_source_unverified')
    return (logs/'stdout.log').read_bytes()


def _fetch(mirror,url,base,head,logdir):
    # No pull_request ref or untrusted branch string enters Git argv.
    _git(mirror,['fetch','--no-tags','--no-recurse-submodules','--',url,base,head],logdir)


def _authority(value,head,base):
    fields={'source','run_id','criteria_sha256','head_sha','base_sha','receipts','artifacts',
            'executor_instances','reviewer_instances','authority_sha256'}
    try:
        exact(value,fields)
        if value['source'] not in ('pipeline','legacy') or value['head_sha']!=head or value['base_sha']!=base: _fail('stage_authority_unverified')
        if value['source']=='pipeline': identifier(value['run_id'])
        elif value['run_id'] is not None: _fail('stage_authority_unverified')
        for key in ('criteria_sha256','authority_sha256'): text(value[key],HASH)
        for key in ('executor_instances','reviewer_instances'):
            rows=value[key]
            if not isinstance(rows,list) or not rows or len(rows)!=len(set(rows)): _fail('stage_authority_unverified')
            for instance in rows: identifier(instance)
        if set(value['executor_instances']) & set(value['reviewer_instances']): _fail('stage_authority_unverified')
        if not isinstance(value['receipts'],list) or not isinstance(value['artifacts'],list): _fail('stage_authority_unverified')
        body={k:v for k,v in value.items() if k!='authority_sha256'}
        if policy_fingerprint(body)!=value['authority_sha256']: _fail('stage_authority_unverified')
        return strict_json(canonical(value))
    except PRSourceError: raise
    except (TypeError,ValueError,KeyError): _fail('stage_authority_unverified')


def prepare_review(connection,task,snapshot,authority,private_dir):
    """Prepare immutable material; caller supplies genuine Task3 authority.

    This validates binding/digests, not provenance authentication. Only the
    installation-owned Task3 loader may supply authority to a controller. No
    Boolean approval argument, fallback receipt or public Markdown authority.
    Instructions hash is host injected from the validated reviewer profile.
    """
    try:
        exact(snapshot,{'repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','policy_sha256',
                        'pr','commits','files','reviews','threads','ci','protection','issue_payload','issue_sha256',
                        'acceptance_statuses','ready','reasons'})
        if snapshot['ready'] is not True or snapshot['reasons']!=[]: _fail('review_source_not_ready')
        for name in ('pr','threads','ci','protection','issue_payload'):
            if not isinstance(snapshot[name],dict): _fail('review_source_unverified')
        for name in ('commits','files','reviews','acceptance_statuses'):
            if not isinstance(snapshot[name],list): _fail('review_source_unverified')
        if any(snapshot[name].get('ready') is not True or snapshot[name].get('reasons')!=[] for name in ('ci','protection')): _fail('review_source_not_ready')
        if policy_fingerprint(snapshot['issue_payload'])!=snapshot['issue_sha256']: _fail('review_source_unverified')
        repository=text(connection.repository,REPOSITORY).casefold()
        for key in ('pr_number','issue','issue_id'): integer(task[key])
        for key in ('head_sha','base_sha'): text(snapshot[key],SHA)
        head,base=snapshot['head_sha'],snapshot['base_sha']
        for key in ('pr_number','issue','issue_id','task_id'):
            if task[key]!=snapshot[key]: _fail('review_binding_mismatch')
        if repository.casefold()!=snapshot['repository'].casefold(): _fail('review_binding_mismatch')
        text(snapshot['policy_sha256'],HASH)
        profile=task['_review_profile']
        if not isinstance(profile,dict) or profile['repository'].casefold()!=repository: _fail('review_profile_unverified')
        pins=_pins(profile['superpowers'])
        if pins!=profile['superpowers']: _fail('review_profile_unverified')
        instructions=profile_fingerprint(pins); profile_sha256=profile_fingerprint(profile)
        authority=_authority(authority,head,base)
        root=Path(private_dir)
        private_paths((root,), (connection.checkout,))
        if root.exists(): _fail('private_review_path_exists')
        root.mkdir(parents=True); logs=root/'logs'; logs.mkdir()
        # Read only origin with includes disabled; do not execute the checkout.
        origin=_git(connection.checkout,['config','--no-includes','--local','--get','remote.origin.url'],logs,16384).decode('utf-8').strip()
        url='https://github.com/'+repository+'.git'
        if origin.casefold() not in (url,url.removesuffix('.git'),'git@github.com:'+repository+'.git'):
            _fail('repository_remote_mismatch')
        checkout=root/'checkout'; checkout.mkdir()
        _git(checkout,['init','--template='],logs)
        _fetch(checkout,url,base,head,logs)
        for sha in (base,head):
            actual=_git(checkout,['rev-parse','--verify',sha+'^{commit}'],logs,1024).decode('ascii').strip()
            if actual!=sha: _fail('git_source_unverified')
        _git(checkout,['merge-base','--is-ancestor',base,head],logs,1024)
        # Checkout never evaluates filters/submodules from the repository:
        # the new config has none, no global config is read, and hooks disabled.
        _git(checkout,['checkout','--detach','--force',head,'--'],logs)
        diff=_git(checkout,['diff','--no-ext-diff','--no-textconv','--binary','--full-index','--find-renames',base,head,'--'],logs)
        raw=_git(checkout,['diff','--no-ext-diff','--no-textconv','--raw','-z','--no-abbrev','--find-renames',base,head,'--'],logs)
        parts=raw.split(b'\0'); manifest=[]; blobs={}; i=0; blob_bytes=0
        while i<len(parts) and parts[i]:
            header=parts[i].decode('ascii'); i+=1
            match=re.fullmatch(r':([0-7]{6}) ([0-7]{6}) ([a-f0-9]{40}) ([a-f0-9]{40}) ([A-Z][0-9]*)',header)
            if not match: _fail('git_manifest_unverified')
            oldmode,newmode,oldsha,newsha,status=match.groups()
            path=parts[i]; i+=1; oldpath=None
            if status[0] in 'RC': oldpath=path; path=parts[i]; i+=1
            # Bytes are base64 bound; invalid UTF-8 names are never silently lost.
            entry=dict(status=status,old_mode=oldmode,new_mode=newmode,old_sha=oldsha,new_sha=newsha,
                       path_base64=base64.b64encode(path).decode('ascii'),
                       old_path_base64=None if oldpath is None else base64.b64encode(oldpath).decode('ascii'))
            for mode,sha in ((oldmode,oldsha),(newmode,newsha)):
                if mode=='160000': _fail('submodule_review_requires_input')
                if sha=='0'*40 or sha in blobs: continue
                size=int(_git(checkout,['cat-file','-s',sha],logs,1024))
                blob_bytes+=size
                if size>_BLOB_LIMIT or blob_bytes>_DIFF_LIMIT: _fail('blob_limit_exceeded')
                content=_git(checkout,['cat-file','blob',sha],logs,_BLOB_LIMIT)
                if len(content)!=size: _fail('git_manifest_unverified')
                blobs[sha]=dict(size=size,sha256=hashlib.sha256(content).hexdigest(),content_base64=base64.b64encode(content).decode('ascii'))
            manifest.append(entry)
            if len(manifest)>100000: _fail('path_limit_exceeded')
        instance=str(uuid.uuid4())
        binding={k:snapshot[k] for k in ('repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','policy_sha256')}
        material=dict(version=1,**binding,source=dict(pr=snapshot['pr'],commits=snapshot['commits'],
                      issue_payload=snapshot['issue_payload'],issue_sha256=snapshot['issue_sha256'],
                      files=snapshot['files'],reviews=snapshot['reviews'],threads=snapshot['threads'],
                      protection=snapshot['protection']),authority=authority,pins={'instructions_sha256':instructions},
                      instructions_sha256=instructions,profile_sha256=profile_sha256,ci={k:v for k,v in snapshot['ci'].items() if k!='acceptance_statuses'},
                      diff=dict(sha256=hashlib.sha256(diff).hexdigest(),content_base64=base64.b64encode(diff).decode('ascii'),
                                manifest=manifest,manifest_sha256=policy_fingerprint(manifest),blobs=blobs),
                      reviewer_instance_id=instance,attempt=1)
        request=dict(version=1,**binding,input_sha256=policy_fingerprint(material),reviewer_instance_id=instance,attempt=1,input=material)
        files={'diff.patch':diff,'manifest.json':canonical(manifest).encode('utf-8'),
               'input.json':canonical(material).encode('utf-8'),'request.json':canonical(request).encode('utf-8')}
        for name,content in files.items():
            with (root/name).open('xb') as stream: stream.write(content)
        return dict(checkout=str(checkout),request=request,diff_path=str(root/'diff.patch'),
                    manifest_path=str(root/'manifest.json'),input_path=str(root/'input.json'))
    except PRSourceError: raise
    except (OSError,ValueError,KeyError,TypeError,UnicodeError): _fail('review_source_unverified')
