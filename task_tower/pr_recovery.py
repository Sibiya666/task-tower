"""Read-only original archive diagnostics; never recovery/effect authority."""
import copy
import re
from datetime import datetime
from .github_source import GitHubSource,GitHubSourceError
from .merge_events import build_merge_event
from .pr_journal import PRJournal
from .pr_policy import policy_fingerprint,canonical


def inspect_recovery(task,journal,source):
    """Expose original marker provenance without reinterpreting a live edit.

    Archive schema is checked against its OWN marker list and actual GitHub
    identities. Unlike acceptance polling, a live body mismatch is reported,
    never repaired. None of this output can restore an executable context.
    """
    if type(journal) is not PRJournal or type(source) is not GitHubSource or not isinstance(task,dict):
        raise ValueError('Actual recovery inspection objects required')
    try:
        row=journal.get(task['repository'],task['pr_number'])
        if (row is None or source.repository.casefold()!=row['repository'].casefold()
                or any(task[k]!=row[k] for k in ('issue','issue_id','task_id'))):
            raise ValueError('Foreign recovery identity')
        number=row['pr_number'];repository=source.repository
        pr=source._get('/pulls/'+str(number))
        live=build_merge_event(dict(action='closed',repository=dict(full_name=repository),pull_request=pr),
            repository,'linux','passed',1,1)
        if pr.get('number')!=number or pr.get('head',{}).get('sha') is None:
            raise ValueError('Unknown merged identity')
        if row['merge_commit'] is not None and row['merge_commit']!=live['merge_commit']:
            raise ValueError('Conflicting original merge')
        merged=datetime.fromisoformat(pr['merged_at'].replace('Z','+00:00'))
        events=[];seen=set();runs=set()
        for run in source._pages('/actions/workflows/postmerge.yml/runs?status=completed','workflow_runs'):
            refs=run.get('pull_requests',[])
            belongs=isinstance(refs,list) and any(isinstance(ref,dict) and ref.get('number')==number for ref in refs)
            if not belongs and run.get('head_sha')!=pr['head']['sha']:continue
            if (run.get('status')!='completed' or run.get('path')!='.github/workflows/postmerge.yml'
                    or run.get('event')!='pull_request' or run.get('repository',{}).get('full_name')!=repository
                    or run.get('head_sha')!=pr['head']['sha'] or not isinstance(refs,list)
                    or refs and not belongs):raise ValueError('Unknown original workflow provenance')
            run_id=source._id(run.get('id'));attempt=source._id(run.get('run_attempt'))
            created=datetime.fromisoformat(run['created_at'].replace('Z','+00:00'))
            if (merged.utcoffset() is None or created.utcoffset() is None or created<merged
                    or (run_id,attempt) in runs):raise ValueError('Invalid original run')
            runs.add((run_id,attempt))
            found=False
            for artifact in source._pages('/actions/runs/'+str(run_id)+'/artifacts','artifacts'):
                match=re.fullmatch('task-tower-merge-([1-9][0-9]*)-(linux|macos|windows)',artifact.get('name',''))
                if match is None or int(match[1])!=number:continue
                platform=match[2];artifact_id=source._id(artifact.get('id'))
                provenance=artifact.get('workflow_run',{})
                if (artifact.get('expired') is not False or provenance.get('id')!=run_id
                        or provenance.get('head_sha')!=run['head_sha'] or (run_id,attempt,platform) in seen):
                    raise ValueError('Unknown original artifact provenance')
                event=source._event(artifact)
                markers=event.get('task_ids')
                if (not isinstance(markers,list) or len(markers)>100 or len(set(markers))!=len(markers)
                        or any(not isinstance(marker,str) or re.fullmatch('TT-[A-Z0-9]+(?:-[A-Z0-9]+)*',marker) is None for marker in markers)):
                    raise ValueError('Invalid original marker list')
                # Schema validation only: this reconstruction grants no
                # acceptance and never replaces the archived event/body.
                original=copy.deepcopy(pr);original['body']='\n'.join('Task-Tower: '+marker for marker in markers)
                expected=build_merge_event(dict(action='closed',repository=dict(full_name=repository),pull_request=original),
                    repository,platform,event.get('checks'),run_id,attempt)
                if canonical(event)!=canonical(expected):raise ValueError('Invalid original event identity')
                events.append(dict(run_id=str(run_id),attempt=str(attempt),artifact_id=artifact_id,platform=platform,
                    checks=event['checks'],task_ids=list(markers),event_sha256=policy_fingerprint(event),
                    merge_commit=event['merge_commit'],run_url=event['run_url']))
                seen.add((run_id,attempt,platform));found=True
            if not found:raise ValueError('Original artifacts unavailable')
        if not events:raise ValueError('Original event unavailable')
        if source._get('/pulls/'+str(number))!=pr:raise ValueError('Live recovery metadata changed')
        conflict=any(event['task_ids'] not in ([],[row['task_id']]) for event in events)
        conflict=conflict or live['task_ids'] not in ([],[row['task_id']])
        marker_sets={tuple(event['task_ids']) for event in events}
        conflict=conflict or len(marker_sets)!=1
        action=('explicit_reconciliation_required' if conflict else 'reviewed_followup_required'
            if any(event['task_ids']!=[row['task_id']] for event in events) else 'fresh_acceptance_required')
        return dict(repository=row['repository'],pr_number=number,issue=row['issue'],issue_id=row['issue_id'],
            task_id=row['task_id'],merge_commit=live['merge_commit'],live_task_ids=live['task_ids'],
            events=sorted(events,key=lambda e:(int(e['run_id']),int(e['attempt']),e['platform'])),required_action=action)
    except (KeyError,TypeError,AttributeError,GitHubSourceError,OverflowError) as error:
        raise ValueError('Original recovery provenance unavailable') from None
