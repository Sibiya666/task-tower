"""Pure premerge consistency; trusted effect execution is a separate gate.

This helper cannot authenticate imported receipts or authorize any write.
The future PREffects caller must reconstruct actual typed current context,
retained records and semantic input equality before and after durable intent.
"""
from .pr_journal import BINDING, _binding
from .pr_policy import exact, identifier, integer, policy_fingerprint, text, HASH
from .pr_review import RESULT_KEYS, _result
from .pr_source import _authority, PRSourceError
from .pr_policy import canonical


def _unpublished_proof(context,source,journal,task,receipt):
    """Read-only proof before any own publication exists; never grants a write.

    Subsequent publication needs independently matched confirmed own effects.
    Until that path exists, any acceptance status or changed review parks here.
    """
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
        premerge_gate(fresh['task'],receipt,snapshot,fresh['authority'],None)
        if (fresh['private_inputs_sha256']!=material['private_inputs_sha256']
                or canonical(context.private_input_provenance)!=canonical(material['private_input_provenance'])
                or canonical(fresh['authority'])!=canonical(material['authority'])):
            raise ValueError('Current private inputs or authority changed')
        if snapshot['acceptance_statuses'] or snapshot['ci'].get('acceptance_statuses'):
            raise ValueError('Own publication requires exact acknowledgment matching')
        for key,old in material['source'].items():
            new=snapshot[key]
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
    try:
        binding=_positive_receipt(receipt)
        if (task['source']!='pipeline' or task['merge_enabled'] is not True
                or task['exclusive_writer']['enabled'] is not True or task['base_ref']!='refs/heads/main'):
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
