"""Pure premerge consistency; trusted effect execution is a separate gate.

This helper cannot authenticate imported receipts or authorize any write.
The future PREffects caller must reconstruct actual typed current context,
retained records and semantic input equality before and after durable intent.
"""
from .pr_journal import BINDING, _binding
from .pr_policy import exact, identifier, integer, policy_fingerprint, text, HASH
from .pr_review import RESULT_KEYS, _result
from .pr_source import _authority, PRSourceError
from .pr_policy import canonical, strict_json
import copy
import hashlib
import time
from datetime import datetime, timezone


def _unpublished_proof(context,source,journal,task,receipt):
    """Read-only proof before any own publication exists; never grants a write.

    Subsequent publication needs independently matched confirmed own effects.
    Until that path exists, any acceptance status or changed review parks here.
    """
    return _current_proof(context,source,journal,task,receipt,allow_own=False,merge_policy=True)


def _current_proof(context,source,journal,task,receipt,*,allow_own,merge_policy):
    from .pr_context import PRHostContext
    from .pr_source import PRSource
    from .pr_journal import PRJournal
    try:
        if type(context) is not PRHostContext or type(source) is not PRSource or type(journal) is not PRJournal:
            raise ValueError('Actual host objects required')
        binding=_positive_receipt(receipt)
        provenance=context.private_input_provenance
        if provenance['pr_journal'] is None or str(journal.path)!=provenance['pr_journal']['path']:
            raise ValueError('Foreign journal')
        retained=context.review_record(binding['input_sha256'])
        if canonical(retained['receipt'])!=canonical(receipt):
            raise ValueError('Receipt differs from confirmed process')
        request=retained['request']; material=request['input']
        fresh=context.current(source,task); snapshot=fresh['snapshot']
        if fresh['authority_error'] is not None:
            raise ValueError('Current stage authority unavailable')
        _positive_gate(fresh['task'],receipt,snapshot,fresh['authority'],None,merge_policy=merge_policy)
        if (fresh['private_inputs_sha256']!=material['private_inputs_sha256']
                or canonical(context.private_input_provenance)!=canonical(material['private_input_provenance'])
                or canonical(fresh['authority'])!=canonical(material['authority'])):
            raise ValueError('Current private inputs or authority changed')
        reviews=snapshot['reviews']
        if allow_own:
            reviews=_remaining_feedback(snapshot,journal.effects(binding['repository'],binding['pr_number']),
                binding,fresh['task']['publisher_account'])
        elif snapshot['acceptance_statuses'] or snapshot['ci'].get('acceptance_statuses'):
            raise ValueError('Own publication requires exact acknowledgment matching')
        for key,old in material['source'].items():
            new=reviews if key=='reviews' else snapshot[key]
            if key=='pr':
                volatile={'updated_at','comments','review_comments'}
                old={k:v for k,v in old.items() if k not in volatile}
                new={k:v for k,v in new.items() if k not in volatile}
            if canonical(old)!=canonical(new):
                raise ValueError('Current reviewed source changed')
        if canonical(material['ci'])!=canonical({k:v for k,v in snapshot['ci'].items() if k!='acceptance_statuses'}):
            raise ValueError('Current reviewed CI changed')
        # The current audit may be slow: independently resolve retained evidence
        # and pinned configuration again rather than trusting an earlier read.
        if canonical(context.review_record(binding['input_sha256']))!=canonical(retained):
            raise ValueError('Retained evidence changed during current audit')
        return dict(receipt=retained['receipt'],request=request,current=fresh)
    except (ValueError,TypeError,KeyError,AttributeError,OSError,OverflowError,RecursionError,PRSourceError):
        raise ValueError('pr_effect_unverified') from None

_RECEIPT_EXTRA={'version','verdict','summary','findings','whole_diff_reviewed','reviewer_instance_id',
    'request_sha256','result_sha256','process_sha256','receipt_sha256'}


def _positive_receipt(receipt):
    exact(receipt,BINDING|_RECEIPT_EXTRA)
    binding={key:receipt[key] for key in BINDING}; _binding(binding)
    identifier(receipt['reviewer_instance_id'])
    for key in ('request_sha256','result_sha256','process_sha256','receipt_sha256'): text(receipt[key],HASH)
    result={key:receipt[key] for key in RESULT_KEYS}; _result(result,receipt)
    if (receipt['verdict']!='approve' or receipt['whole_diff_reviewed'] is not True
            or any(finding['blocking'] for finding in receipt['findings'])):
        raise ValueError('Nonpositive PR receipt')
    if (policy_fingerprint(result)!=receipt['result_sha256']
            or policy_fingerprint({key:value for key,value in receipt.items() if key!='receipt_sha256'})!=receipt['receipt_sha256']):
        raise ValueError('Inconsistent PR receipt')
    return binding


def premerge_gate(task,receipt,current,authority,barrier):
    """Check declared facts only; does not authenticate authority or acquire a barrier.

    Actual operator/server provenance, current retained semantic equality and
    owner/clock/intent checks belong to the mandatory typed effect caller.
    """
    return _positive_gate(task,receipt,current,authority,barrier,merge_policy=True)


def _positive_gate(task,receipt,current,authority,barrier,*,merge_policy):
    try:
        binding=_positive_receipt(receipt)
        if (task['source']!='pipeline' or task['base_ref']!='refs/heads/main'
                or merge_policy and (task['merge_enabled'] is not True or task['exclusive_writer']['enabled'] is not True)):
            raise ValueError('Merge policy unavailable')
        if task['repository'].casefold()!=binding['repository']:
            raise ValueError('Foreign merge repository')
        for key in ('pr_number','issue','issue_id','task_id'):
            if type(task[key]) is not type(binding[key]) or task[key]!=binding[key]:
                raise ValueError('Foreign merge task')
        for key in BINDING-{'input_sha256'}:
            if type(current[key]) is not type(binding[key]) or current[key]!=binding[key]:
                raise ValueError('Current merge binding changed')
        if current['ready'] is not True or current['reasons']!=[]:
            raise ValueError('Current PR not ready')
        for key in ('ci','protection'):
            if current[key]['ready'] is not True or current[key]['reasons']!=[]:
                raise ValueError('Current required gate unavailable')
        pr=current['pr']
        if (type(pr['number']) is not int or pr['number']!=binding['pr_number'] or pr['state']!='open'
                or pr['draft'] is not False or pr['merged'] is not False or pr['mergeable'] is not True
                or pr['mergeable_state']!='clean' or pr['base']['ref']!='main'):
            raise ValueError('Current mergeability unavailable')
        for side,key in (('head','head_sha'),('base','base_sha')):
            if (pr[side]['sha']!=binding[key]
                    or pr[side]['repo']['full_name'].casefold()!=binding['repository']):
                raise ValueError('PR head/base changed')
        checked=_authority(authority,binding['head_sha'],binding['base_sha'])
        if checked['source']!='pipeline' or checked['run_id']!=task['pipeline_run_id']:
            raise ValueError('Current stage source changed')
        if receipt['reviewer_instance_id'] in checked['executor_instances']+checked['reviewer_instances']:
            raise ValueError('Reviewer is an original stage instance')
        if barrier is not None:
            exact(barrier,BINDING|{'owner_id','owner_pid','completed','proof'})
            if barrier['completed'] is not False or barrier['proof'] is not None:
                raise ValueError('Repository barrier unavailable')
            identifier(barrier['owner_id']); integer(barrier['owner_pid'])
            if any(type(barrier[key]) is not type(binding[key]) or barrier[key]!=binding[key] for key in BINDING):
                raise ValueError('Repository barrier binding changed')
        return binding
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError,PRSourceError):
        raise ValueError('pr_merge_unverified') from None


def _body_sha(body):
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def _status_body(payload):
    return {key:payload[key] for key in ('state','context','description','target_url')}


def _publication_observation(effect,response,publisher,max_bytes):
    """Pure response consistency; durable owner/current proof is separate."""
    try:
        kind=effect['kind']; payload=effect['payload']
        if kind not in ('acceptance_review','acceptance_status'): raise ValueError('Unsupported observation')
        expected=200 if kind=='acceptance_review' else 201
        exact(response,{'status','headers','body'})
        if type(response['status']) is not int or response['status']!=expected or not isinstance(response['headers'],dict):
            raise ValueError('Uncertain publication response')
        raw=response['body']
        if not isinstance(raw,bytes) or len(raw)>max_bytes: raise ValueError('Uncertain response size')
        if any(not isinstance(key,str) or not isinstance(value,str) for key,value in response['headers'].items()):
            raise ValueError('Invalid response headers')
        lengths=[v for k,v in response['headers'].items() if k.lower()=='content-length']
        if len(lengths)>1 or lengths and int(lengths[0])!=len(raw): raise ValueError('Incomplete response')
        result=strict_json(raw.decode('utf-8'))
        if not isinstance(result,dict): raise ValueError('Invalid response shape')
        integer(result['id'])
        if kind=='acceptance_review':
            if (payload['event']!='COMMENT' or result['commit_id']!=payload['commit_id']
                    or result['state']!='COMMENTED' or result['body']!=payload['body']):
                raise ValueError('Uncertain review observation')
            author=result['user']['login']; digest=_body_sha(payload['body'])
        else:
            body=_status_body(payload)
            if any(result.get(key)!=value for key,value in body.items()): raise ValueError('Uncertain status observation')
            author=result['creator']['login']; digest=policy_fingerprint(body)
        if not isinstance(author,str) or author.casefold()!=publisher.casefold(): raise ValueError('Unexpected publisher')
        return dict(status='confirmed',remote_id=result['id'],body_sha256=digest,author=author)
    except (ValueError,TypeError,KeyError,AttributeError,UnicodeError,OverflowError,RecursionError):
        raise ValueError('pr_publication_response_unverified') from None


def _remaining_feedback(snapshot,effects,binding,publisher):
    """Remove only positively acknowledged exact own rows from comparison.

    The original current snapshot, including readiness and all feedback, stays
    untouched. Callers obtain effects only from the validated actual journal.
    """
    reports=list(snapshot['reviews']); statuses=list(snapshot['acceptance_statuses'])
    if canonical(statuses)!=canonical(snapshot['ci']['acceptance_statuses']):
        raise ValueError('Incoherent current acceptance statuses')
    for effect in effects:
        if (effect['status']!='confirmed' or effect['kind'] not in ('acceptance_review','acceptance_status')
                or any(type(effect['binding'][k]) is not type(binding[k]) or effect['binding'][k]!=binding[k] for k in BINDING)):
            continue
        payload=effect['payload']; observed=effect['observation']
        if observed['author'].casefold()!=publisher.casefold(): raise ValueError('Foreign confirmed publisher')
        rows=reports if effect['kind']=='acceptance_review' else statuses
        matched=[row for row in rows if type(row.get('id')) is int and row['id']==observed['remote_id']]
        if len(matched)!=1: raise ValueError('Acknowledged publication absent or ambiguous')
        row=matched[0]
        if effect['kind']=='acceptance_review':
            if (row['user']['login'].casefold()!=publisher.casefold() or row['commit_id']!=binding['head_sha']
                    or row['state']!='COMMENTED' or payload['event']!='COMMENT'
                    or row['body']!=payload['body'] or observed['body_sha256']!=_body_sha(payload['body'])):
                raise ValueError('Acknowledged review changed')
        else:
            if (row['creator']['login'].casefold()!=publisher.casefold() or payload['sha']!=binding['head_sha']
                    or any(row.get(key)!=value for key,value in _status_body(payload).items())
                    or observed['body_sha256']!=policy_fingerprint(_status_body(payload))):
                raise ValueError('Acknowledged status changed')
        rows.remove(row)
    if statuses: raise ValueError('Unacknowledged own-context publication')
    return reports


class PREffects:
    """Fixed private-host publication actions; intents are never resubmitted."""
    def __init__(self,source,journal,task,owner_id,*,context):
        from .pr_source import PRSource
        from .pr_journal import PRJournal
        from .pr_context import PRHostContext
        if type(source) is not PRSource or type(journal) is not PRJournal or type(context) is not PRHostContext:
            raise ValueError('Actual typed PR host objects required')
        identifier(owner_id)
        if not isinstance(task,dict): raise ValueError('PR task identity required')
        self.source=source; self.journal=journal; self.task=copy.deepcopy(task)
        self.owner_id=owner_id; self.context=context

    def inspect_effect(self,effect_id):
        return self.journal.effect(effect_id)

    def _proof(self,receipt):
        return _current_proof(self.context,self.source,self.journal,self.task,receipt,
            allow_own=True,merge_policy=False)

    def _live(self,effect):
        self.context._fresh_inputs()
        provenance=self.context.private_input_provenance
        if provenance['pr_journal'] is None or provenance['pr_journal']['path']!=str(self.journal.path):
            raise ValueError('PR journal identity changed')
        binding=effect['binding']
        with self.journal._db(True) as db:
            row=self.journal._get(db,binding['repository'],binding['pr_number'])
            self.journal._owned(db,row,self.owner_id); self.journal._tick(row)
            saved=self.journal._load(db,'effects','effect_id',effect['effect_id'])
            if (saved!=effect or effect['status']!='intent' or effect['owner_id']!=self.owner_id
                    or row['cancel_requested'] or row['state']!='publishing_acceptance'
                    or any(type(row[k]) is not type(binding[k]) or row[k]!=binding[k] for k in BINDING)):
                raise ValueError('PR publication intent fenced')
            remaining=min((datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))-
                datetime.now(timezone.utc)).total_seconds(),
                self.journal._clock_limits[(row['repository'],row['pr_number'])]-time.monotonic())
            if remaining<=0: raise ValueError('PR publication deadline exhausted')
            self.journal._save(db,row)
        # A SQLite wait must not hide raw-file revocation. Identity pins alone
        # do not detect an in-place private configuration edit.
        self.context._fresh_inputs()
        remaining=min((datetime.fromisoformat(row['deadline_utc'].replace('Z','+00:00'))-
            datetime.now(timezone.utc)).total_seconds(),
            self.journal._clock_limits[(row['repository'],row['pr_number'])]-time.monotonic())
        if remaining<=0:
            with self.journal._db(True) as db:
                current=self.journal._get(db,binding['repository'],binding['pr_number'])
                self.journal._owned(db,current,self.owner_id); self.journal._tick(current)
            raise ValueError('PR publication deadline exhausted')
        return remaining

    def _write(self,effect,*,publisher):
        """Exactly one allowed request through the existing host transport."""
        payload=effect['payload']; binding=effect['binding']
        prefix='https://api.github.com/repos/'+binding['repository']
        if effect['kind']=='acceptance_review':
            if payload['event']!='COMMENT': raise ValueError('Only COMMENT publication permitted')
            url=prefix+'/pulls/'+str(binding['pr_number'])+'/reviews'
            body={key:payload[key] for key in ('commit_id','event','body')}
        elif effect['kind']=='acceptance_status':
            url=prefix+'/statuses/'+binding['head_sha']; body=_status_body(payload)
        else: raise ValueError('Unsupported PR publication effect')
        headers=dict(self.source.headers)
        if headers.get('X-GitHub-Api-Version')!='2026-03-10': raise ValueError('Unexpected API version')
        headers['Content-Type']='application/json'
        timeout=min(self.source.limits['request_timeout_seconds'],self._live(effect))
        response=self.source.transport('POST',url,headers,canonical(body).encode('utf-8'),
            timeout,self.source.limits['max_response_bytes'])
        observation=_publication_observation(effect,response,publisher,self.source.limits['max_response_bytes'])
        self._live(effect)
        return observation

    def publish(self,receipt):
        self._proof(receipt); binding=_positive_receipt(receipt)
        effects=[e for e in self.journal.effects(binding['repository'],binding['pr_number'])
            if all(type(e['binding'][k]) is type(binding[k]) and e['binding'][k]==binding[k] for k in BINDING)]
        reports=[e for e in effects if e['kind']=='acceptance_review' and e['status']=='confirmed']
        statuses=[e for e in effects if e['kind']=='acceptance_status' and e['payload']['state']=='success' and e['status']=='confirmed']
        if reports and statuses: return statuses[0]
        if not reports:
            kind='acceptance_review'
            body=('Task Tower PR acceptance\nTask: '+binding['task_id']+'\nHead: '+binding['head_sha']+
                '\nBase: '+binding['base_sha']+'\nReceipt: '+receipt['receipt_sha256']+'\nVerdict: approve\n')
            payload=dict(commit_id=binding['head_sha'],event='COMMENT',body=body,receipt_sha256=receipt['receipt_sha256'])
        else:
            kind='acceptance_status'
            payload=dict(state='success',context='task-tower/pr-acceptance',sha=binding['head_sha'],
                target_url='https://github.com/'+binding['repository']+'/pull/'+str(binding['pr_number']),
                description='approve '+receipt['receipt_sha256'],receipt_sha256=receipt['receipt_sha256'])
        effect=self.journal.begin_effect(binding['repository'],binding['pr_number'],self.owner_id,kind,payload)
        try:
            fresh=self._proof(receipt)
            observation=self._write(effect,publisher=fresh['current']['task']['publisher_account'])
        except BaseException as error:
            # A committed intent is consumed even when no request was sent.
            # Lost owner cannot acknowledge on behalf of its successor.
            try: self.journal.observe(effect['effect_id'],self.owner_id,dict(status='unknown'))
            except ValueError: pass
            if not isinstance(error,Exception): raise
            raise ValueError('pr_publication_uncertain') from None
        return self.journal.observe(effect['effect_id'],self.owner_id,observation)
