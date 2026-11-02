"""Bounded public Issue fields. Source prose is inert text, never authority."""
import re

from .github_tasks import START, END, task_status

ISSUE = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*')
URL = re.compile(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:(?:issues|pull|milestone|actions/runs)/[1-9][0-9]*|blob/[0-9a-f]{40}/[^?#\s\\]+\.md)')
STATUSES = {'open','in_progress','needs_input','awaiting_merge','awaiting_postmerge','postmerge_review','postmerge_failed','done','pending','queued','running','reviewed'}


def identity_issue(connection, issue):
    number=issue['number']
    if type(number) is not int or number < 1: raise ValueError('Invalid Issue identity')
    return dict(id=f'{connection.repository}#{number}', repository=connection.repository,
                number=number, project=connection.id, book='tasks', title=issue.get('title') if isinstance(issue.get('title'),str) else '',
                status='open', remote_state=issue.get('state') if issue.get('state') in ('open','closed') else None,
                source=f'https://github.com/{connection.repository}/issues/{number}', verification='pending',
                description='', phase=None, blockers=[], blocked_by=[], results=[], history=[],
                relationships={key:dict(status='unavailable') for key in ('parent','sub_issues','milestone')})


def project_issue(connection, store, issue, metadata):
    row=identity_issue(connection,issue); errors=[]
    def error(message):
        errors.append(dict(project=connection.id,source=row['source'],error=message))
    def bounded(value, limit, field):
        if not isinstance(value,str): error(field+' unavailable'); return None
        if len(value)>limit: error(field+' limit exceeded')
        return value[:limit]
    meta=metadata if isinstance(metadata,dict) else {}
    known={'version','kind','status','phase','blocked_by','blockers','results','stages','remote_attempt',
           '_lifecycle_history','_lifecycle_author','capture','capture_promotion','legacy_id','task_id','id',
           'legacy_card','executor','dependencies','acceptance','title','description'}
    if set(meta)-known: error('Unknown detail fields unavailable')
    row.update(book='ideas' if meta.get('kind')=='idea' else 'tasks',status=task_status(meta),verification='pending' if meta.get('status')=='done' else 'not_required')
    body=issue.get('body') or ''
    if not isinstance(body,str): body=''; error('Description unavailable')
    # Remove the entire metadata suffix even when its closing marker is malformed.
    begin=body.find('<!-- task-tower:')
    if begin>=0:
        finish=body.find(END,begin)
        body=body[:begin]+(body[finish+len(END):] if finish>=0 else '')
    raw=body.encode('utf-8')
    if len(raw)>32768: error('Description limit exceeded')
    row['description']=raw[:32768].decode('utf-8',errors='ignore')
    if 'phase' in meta: row['phase']=bounded(meta['phase'],256,'Phase')
    for field in ('blockers','blocked_by','results'):
        values=meta.get(field,[])
        if not isinstance(values,list): error(field+' unavailable'); continue
        if len(values)>100: error(field+' limit exceeded')
        for value in values[:100]:
            if not isinstance(value,str): error(field+' unavailable'); continue
            if field=='blocked_by' and not ISSUE.fullmatch(value): error('blocked_by unavailable'); continue
            if field=='results' and not URL.fullmatch(value): error('results unavailable'); continue
            row[field].append(bounded(value,256,field) if field=='blockers' else value)
    def attempt(value):
        if not isinstance(value,dict): error('Attempt unavailable'); return {}
        result={}
        for key in ('status','kind','run_id','run_attempt','commit','publication_id','ci_run'):
            if key not in value: continue
            item=value[key]
            if key=='status': valid=item in STATUSES if isinstance(item,str) else False
            elif key=='kind': valid=item in ('local-postmerge','actions') if isinstance(item,str) else False
            elif key in ('commit','publication_id'): valid=isinstance(item,str) and bool(re.fullmatch('[0-9a-f]{'+('40' if key=='commit' else '64')+'}',item))
            else: valid=type(item) in (int,str) and bool(re.fullmatch('[1-9][0-9]*',str(item))) and len(str(item))<=32
            if valid: result[key]=item
            else: error('Attempt field unavailable')
        if 'review' in value:
            review=value['review']
            if not isinstance(review,dict): error('Review unavailable')
            else:
                result['review']={}
                if review.get('verdict') in ('approve','reject','needs_input'): result['review']['verdict']=review['verdict']
                if isinstance(review.get('commit'),str) and re.fullmatch('[0-9a-f]{40}',review['commit']): result['review']['commit']=review['commit']
        return result
    if 'remote_attempt' in meta: row['remote_attempt']=attempt(meta['remote_attempt'])
    history=meta.get('_lifecycle_history',[])
    if not isinstance(history,list): error('History unavailable'); history=[]
    if len(history)>100: error('History limit exceeded')
    for item in history[:100]:
        if not isinstance(item,dict): error('History unavailable'); continue
        entry={}
        if isinstance(item.get('status'),str) and item['status'] in STATUSES: entry['status']=item['status']
        elif 'status' in item: error('History status unavailable')
        if 'remote_attempt' in item: entry['remote_attempt']=attempt(item['remote_attempt'])
        row['history'].append(entry)
    if 'stages' in meta:
        stages=meta['stages']
        if not isinstance(stages,dict): error('Stages unavailable')
        else:
            row['stages']={}
            for key in ('spec','development','test','postmerge'):
                item=stages.get(key)
                if item is None: continue
                if not isinstance(item,dict) or item.get('status') not in ('pending','accepted'): error('Stage unavailable'); continue
                row['stages'][key]={'status':item['status']}
                # Local evidence paths and arbitrary receipt objects are intentionally excluded.
                if isinstance(item.get('commit'),str) and re.fullmatch('[0-9a-f]{40}',item['commit']): row['stages'][key]['commit']=item['commit']
    for key in ('created_at','updated_at'):
        if key in issue:
            if isinstance(issue[key],str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',issue[key]): row[key]=issue[key]
            else: error('Timestamp unavailable')
    from .capture import relationship_projection, capture_projection
    row['relationships'], relationship_errors=relationship_projection(connection,store,issue)
    for message in relationship_errors: error(message)
    milestone=row['relationships'].get('milestone')
    if isinstance(milestone,dict) and 'title' in milestone:
        original=issue.get('milestone',{}).get('title')
        milestone['title']=bounded(original,256,'Milestone title') or ''
    if 'capture' in meta:
        try: row['capture']=capture_projection(meta)
        except (ValueError,KeyError,TypeError): error('Capture provenance unavailable')
    return row,errors
