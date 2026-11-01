"""Explicit session content capture. Provenance is data, never execution authority.

Serialize first creation per project across installations. Durable local intents
prevent replay locally; they are not a distributed creation lock. Promotion uses
a cooperating local process lock and fresh remote recheck. GitHub body PATCH has
no documented server CAS here: external editors must serialize promotion, and
an edit between the final GET and PATCH remains a cross-host/manual-edit race.
"""
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import uuid
import unicodedata
from urllib.parse import urlsplit

from .creation_journal import CreationJournal
from .github_tasks import GitHubTasks, GitHubRequestError, parse_metadata, replace_metadata
from .github_source import GitHubSourceError
from .project_connections import REPOSITORY

MAX_INPUT=65536
MAX_TEXT=32768


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def _text(value, limit, *, nonempty=True):
    if not isinstance(value,str) or '\0' in value or (nonempty and not value.strip()) or len(value)>limit:
        raise ValueError('Invalid capture text')
    try: value.encode('utf-8')
    except UnicodeError: raise ValueError('Invalid capture text') from None
    return value


def safe_url(value):
    _text(value,2048)
    if '\\' in value or any(ord(c)<=32 or unicodedata.category(c)=='Cc' for c in value): raise ValueError('Invalid capture URL')
    try:
        parts=urlsplit(value)
        if parts.scheme!='https' or not parts.hostname or parts.username is not None or parts.password is not None: raise ValueError()
        parts.port
    except ValueError: raise ValueError('Invalid capture URL') from None
    return value


def _qualified(value):
    if not isinstance(value,str) or not re.fullmatch(REPOSITORY+r'#[1-9][0-9]*',value):
        raise ValueError('Invalid capture relationship')
    return value


def validate_capture(envelope):
    try:
        if not isinstance(envelope,dict) or set(envelope)-{'version','event_id','kind','title','original_text','session','intent','relations'}: raise ValueError()
        if type(envelope.get('version')) is not int or envelope['version']!=1: raise ValueError()
        if envelope.get('kind') not in ('idea','task') or envelope.get('intent') not in ('record','execute_requested'): raise ValueError()
        event=_text(envelope.get('event_id'),36)
        normalized=str(uuid.UUID(event))
        if event.lower()!=normalized: raise ValueError()
        value=dict(envelope,event_id=normalized)
        _text(value.get('title'),256)
        original=_text(value.get('original_text'),MAX_TEXT)
        if len(original.encode('utf-8'))>MAX_TEXT: raise ValueError()
        session=value.get('session')
        if not isinstance(session,dict) or set(session)-{'provider','id','url'}: raise ValueError()
        _text(session.get('provider'),128); _text(session.get('id'),128)
        if 'url' in session: safe_url(session['url'])
        relations=value.get('relations',{})
        if not isinstance(relations,dict) or set(relations)-{'parent','sub_issues','milestone','sources'}: raise ValueError()
        if 'parent' in relations: _qualified(relations['parent'])
        children=relations.get('sub_issues',[])
        if not isinstance(children,list) or len(children)>100 or len(set(map(str,children)))!=len(children): raise ValueError()
        for child in children: _qualified(child)
        if 'milestone' in relations:
            milestone=relations['milestone']
            if not isinstance(milestone,dict) or set(milestone)!={'repository','number'} or not isinstance(milestone['repository'],str) or not re.fullmatch(REPOSITORY,milestone['repository']) or type(milestone['number']) is not int or milestone['number']<1: raise ValueError()
        sources=relations.get('sources',[])
        if not isinstance(sources,list) or len(sources)>100: raise ValueError()
        for source in sources: safe_url(source)
        if len(_json(value))>MAX_INPUT: raise ValueError()
        # Return a detached canonical JSON value; caller mutation cannot change intent.
        return json.loads(_json(value))
    except (ValueError,TypeError,KeyError,UnicodeError,OverflowError):
        raise ValueError('Invalid capture envelope') from None


def _encode(value):
    raw=_json(value)
    return dict(version=1,encoding='base64-json',payload=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest())


def _decode(record):
    try:
        if not isinstance(record,dict) or set(record)!={'version','encoding','payload','sha256'} or type(record['version']) is not int or record['version']!=1 or record['encoding']!='base64-json': raise ValueError()
        if not isinstance(record['payload'],str) or len(record['payload'])>4*((MAX_INPUT+2)//3): raise ValueError()
        raw=base64.b64decode(record['payload'],validate=True)
        if len(raw)>MAX_INPUT or hashlib.sha256(raw).hexdigest()!=record['sha256']: raise ValueError()
        value=json.loads(raw.decode('utf-8'))
        if _json(value)!=raw: raise ValueError()
        return value
    except (ValueError,TypeError,KeyError,UnicodeError,binascii.Error):
        raise ValueError('Invalid capture provenance') from None


def capture_metadata(value):
    return dict(version=1,kind=value['kind'],status='open',capture=_encode(value))


def decode_capture(metadata):
    if not isinstance(metadata,dict) or 'capture' not in metadata: raise ValueError('Capture provenance unavailable')
    value=_decode(metadata['capture'])
    validated=validate_capture(value)
    if value!=validated: raise ValueError('Invalid capture provenance')
    if metadata.get('kind')!=value['kind'] and not (metadata.get('kind')=='task' and value['kind']=='idea' and 'capture_promotion' in metadata):
        raise ValueError('Conflicting capture kind')
    return validated


def capture_projection(metadata):
    value=decode_capture(metadata)
    result=dict(original_text=value['original_text'],session=value['session'],event_id=value['event_id'],intent=value['intent'],original_kind=value['kind'],requested_relations=value.get('relations',{}))
    if 'capture_promotion' in metadata:
        promotion=_decode(metadata['capture_promotion'])
        if not isinstance(promotion,dict) or set(promotion)!={'previous_kind','event_id','at'} or promotion.get('previous_kind')!='idea' or promotion.get('event_id')!=value['event_id'] or metadata.get('kind')!='task' or value['kind']!='idea': raise ValueError('Invalid promotion provenance')
        try: datetime.fromisoformat(promotion['at'])
        except (ValueError,TypeError): raise ValueError('Invalid promotion provenance') from None
        result['promotion']=promotion
    return result


def capture_body(value,metadata):
    # HTML escaping neutralizes comment delimiters even inside fences/JSON.
    excerpt=html.escape(value['original_text'][:4096],quote=True)
    body=replace_metadata('Explicit session capture\n\n'+excerpt,metadata)
    if len(body)>65536: raise ValueError('Capture body exceeds GitHub limit')
    return body


def _journal(connection):
    return CreationJournal(connection.checkout/'.task-tower'/'create-intents.sqlite3')


def _result(connection,issue,status,errors=None):
    number=issue.get('number')
    if type(number) is not int or number<1 or 'pull_request' in issue: raise ValueError('Capture outcome uncertain; inspect the existing event')
    return dict(status=status,number=number,issue_url=f'https://github.com/{connection.repository}/issues/{number}',source_errors=errors or [])


def _scope_relations(connection,value):
    relations=value.get('relations',{})
    refs=([relations['parent']] if 'parent' in relations else [])+relations.get('sub_issues',[])
    if any(ref.rsplit('#',1)[0].casefold()!=connection.repository.casefold() for ref in refs):
        raise ValueError('Relationship requires an explicitly connected authorized repository')
    if 'milestone' in relations and relations['milestone']['repository'].casefold()!=connection.repository.casefold():
        raise ValueError('Milestone requires the selected repository')


def _repair(connection,store,issue,value,status):
    from .projects_board import sync_issue
    result=_result(connection,issue,status)
    try:
        result['project_sync']=sync_issue(connection,store,issue['number'])
    except (ValueError,GitHubSourceError,KeyError,TypeError): result['project_sync']=dict(status='unavailable')
    if result['project_sync'].get('status')!='synced':
        result['source_errors'].append('Project membership or status unavailable; retry the same event to repair this Issue')
    try: _repair_relations(connection,store,issue,value.get('relations',{}))
    except (ValueError,GitHubSourceError,KeyError,TypeError):
        result['source_errors'].append('Relationships unavailable or conflicting; inspect links and retry the same event')
    if result['source_errors']: result['status']='needs_input'
    return result


def capture(connection,envelope,*,store=None):
    from .project_onboarding import preflight
    value=validate_capture(envelope)
    _scope_relations(connection,value)
    metadata=capture_metadata(value)
    body=capture_body(value,metadata)
    store=store if store is not None else GitHubTasks(connection)
    repository=preflight(connection,store)
    journal=_journal(connection)
    identity=value['session']['provider']+':'+value['event_id']
    digest=metadata['capture']['sha256']

    def find():
        matches=[]
        for issue in store.list_issues():
            current=store.metadata(issue)
            if not current or 'capture' not in current: continue
            remote=decode_capture(current)
            capture_projection(current)
            if remote['event_id']==value['event_id'] and remote['session']['provider']==value['session']['provider']:
                if current['capture']['sha256']!=digest: raise ValueError('Capture payload conflict; inspect the existing event')
                matches.append(issue)
        if len(matches)>1: raise ValueError('Ambiguous capture identity; inspect existing Issues')
        return matches[0] if matches else None

    existing=find()
    if existing:
        journal.reconcile_payload('capture',repository['id'],identity,str(existing['number']),digest)
        return _repair(connection,store,existing,value,'existing')
    _validate_relation_targets(store,value.get('relations',{}))
    if not journal.reserve_payload('capture',repository['id'],identity,digest):
        raise ValueError('Capture outcome uncertain or missing; preserve the journal and inspect the existing event; no POST retried')
    try:
        issue=store.request('POST','/issues',dict(title=html.escape(value['title'],quote=True)[:256],body=body))
        _result(connection,issue,'captured')
    except (GitHubSourceError,ValueError,TypeError,AttributeError):
        issue=find()
        if issue is None: raise ValueError('Capture outcome uncertain; preserve the journal and inspect the existing event; no POST retried') from None
    journal.reconcile_payload('capture',repository['id'],identity,str(issue['number']),digest)
    return _repair(connection,store,issue,value,'captured')


def promote(connection,number,*,store=None):
    from .project_onboarding import preflight
    if type(number) is not int or number<1: raise ValueError('Invalid Issue number')
    store=store if store is not None else GitHubTasks(connection)
    repository=preflight(connection,store)
    key=hashlib.sha256((str(repository['id'])+':'+str(number)).encode()).hexdigest()
    lock=CreationJournal(connection.checkout/'.task-tower'/('promotion-'+key+'.sqlite3'))
    with lock.transaction():
        issue=store.get(number)
        metadata=store.metadata(issue)
        value=decode_capture(metadata)
        capture_projection(metadata)
        identity=value['session']['provider']+':'+value['event_id']
        _journal(connection).reconcile_payload('capture',repository['id'],identity,str(number),metadata['capture']['sha256'])
        if metadata['kind']=='task': return _result(connection,issue,'existing')
        updated=dict(metadata,kind='task',capture_promotion=_encode(dict(previous_kind='idea',event_id=value['event_id'],at=datetime.now(timezone.utc).isoformat())))
        body=replace_metadata(issue.get('body'),updated)
        fresh=store.get(number)
        if fresh.get('body')!=issue.get('body') or fresh.get('updated_at')!=issue.get('updated_at'):
            raise ValueError('Issue changed during promotion; inspect and retry')
        # This is a drift check, not server-enforced CAS. See module contract.
        changed=store.update(number,body=body)
        result=_result(connection,changed,'promoted')
        result['editing_constraint']='Serialize external editing during promotion; the final GET/PATCH race is not server protected'
        return result


def _repair_relations(connection,store,issue,relations):
    if not any(key in relations for key in ('parent','sub_issues','milestone')): return
    number=issue['number']
    if 'parent' in relations:
        parent_number=int(relations['parent'].rsplit('#',1)[1])
        if parent_number==number: raise ValueError('Invalid self relationship')
        current=_native_parent(store,number)
        if current and not _same_issue(current,connection.repository,parent_number): raise ValueError('Conflicting native parent')
        if not current:
            store.get(parent_number)
            store.request('POST',f'/issues/{parent_number}/sub_issues',dict(sub_issue_id=issue['id']))
    if relations.get('sub_issues'):
        current=store.request('GET',f'/issues/{number}/sub_issues?per_page=100')
        if not isinstance(current,list): raise ValueError('Native relationships unavailable')
        for ref in relations['sub_issues']:
            child_number=int(ref.rsplit('#',1)[1])
            if child_number==number: raise ValueError('Invalid self relationship')
            if any(_same_issue(row,connection.repository,child_number) for row in current): continue
            child=store.get(child_number)
            parent=_native_parent(store,child_number)
            if parent and not _same_issue(parent,connection.repository,number): raise ValueError('Conflicting native parent')
            if not parent: store.request('POST',f'/issues/{number}/sub_issues',dict(sub_issue_id=child['id']))
    if 'milestone' in relations:
        wanted=relations['milestone']['number']
        fresh=store.get(number)
        current=fresh.get('milestone')
        if current and current.get('number')!=wanted: raise ValueError('Conflicting native milestone')
        if not current:
            store.request('GET',f'/milestones/{wanted}')
            store.request('PATCH',f'/issues/{number}',dict(milestone=wanted))


def _same_issue(issue,repository,number):
    return (isinstance(issue,dict) and issue.get('number')==number and
            issue.get('html_url','').casefold()==f'https://github.com/{repository}/issues/{number}'.casefold())


def _native_parent(store,number):
    try: return store.request('GET',f'/issues/{number}/parent')
    except GitHubRequestError as error:
        # The target Issue was separately fetched; GitHub uses 404 for no parent.
        # A refused add still surfaces as a recoverable source error.
        if error.http_status==404: return None
        raise


def _validate_relation_targets(store,relations):
    """Resolve requested targets before the first remote mutation."""
    try:
        refs=([relations['parent']] if 'parent' in relations else [])+relations.get('sub_issues',[])
        for ref in refs:
            number=int(ref.rsplit('#',1)[1])
            issue=store.get(number)
            if issue.get('number')!=number or 'pull_request' in issue: raise ValueError()
        if 'milestone' in relations:
            number=relations['milestone']['number']
            milestone=store.request('GET',f'/milestones/{number}')
            if not isinstance(milestone,dict) or milestone.get('number')!=number: raise ValueError()
    except (ValueError,GitHubSourceError,KeyError,TypeError):
        raise ValueError('Requested relationship target unavailable; inspect connection and links') from None


def relationship_projection(connection,store,issue):
    """Fetch native links; unavailable is distinct from an empty hierarchy."""
    number=issue['number']; errors=[]
    def identity(row):
        if not isinstance(row,dict) or type(row.get('number')) is not int or row['number']<1: raise ValueError()
        url=row.get('html_url')
        if not isinstance(url,str) or not re.fullmatch(r'https://github\.com/'+REPOSITORY+r'/issues/[1-9][0-9]*',url): raise ValueError()
        repository=url.removeprefix('https://github.com/').rsplit('/issues/',1)[0]
        if int(url.rsplit('/',1)[1])!=row['number']: raise ValueError()
        return dict(id=repository+'#'+str(row['number']),source=url)
    result={}
    try:
        parent=_native_parent(store,number)
        result['parent']=identity(parent) if parent else None
    except (ValueError,GitHubSourceError,KeyError,TypeError,AttributeError):
        result['parent']=dict(status='unavailable'); errors.append('Native parent unavailable')
    try:
        children=[]
        for page in range(1,11):
            rows=store.request('GET',f'/issues/{number}/sub_issues?per_page=100&page={page}')
            if not isinstance(rows,list) or len(rows)>100: raise ValueError()
            children.extend(identity(row) for row in rows)
            if len(rows)<100: break
        else: raise ValueError()
        result['sub_issues']=children
    except (ValueError,GitHubSourceError,KeyError,TypeError,AttributeError):
        result['sub_issues']=dict(status='unavailable'); errors.append('Native sub-issues unavailable')
    milestone=issue.get('milestone')
    if milestone is None: result['milestone']=None
    else:
        try:
            n=milestone['number']
            if type(n) is not int or n<1: raise ValueError()
            source=f'https://github.com/{connection.repository}/milestone/{n}'
            result['milestone']=dict(id=f'{connection.repository}@milestone/{n}',number=n,source=source,title=str(milestone.get('title','')))
        except (ValueError,KeyError,TypeError):
            result['milestone']=dict(status='unavailable'); errors.append('Native milestone unavailable')
    return result,errors
