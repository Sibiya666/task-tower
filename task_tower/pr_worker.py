"""Typed bounded PR controller; publication/merge authority stays in PREffects."""
import os
from .pr_context import PRHostContext
from .pr_journal import PRJournal,BINDING
from .pr_source import PRSource
from .pr_policy import authorized_task,canonical,identifier
from .pr_effects import PREffects
from .pr_persistence import prepare_admission,run_review


def _public(row=None,*,reason=None,action='none'):
    if row is None:return dict(status='idle' if reason is None else 'needs_input',reason=reason,action=action)
    keys=('repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','input_sha256',
        'pr_receipt_sha256','postmerge_receipt_sha256','review_attempts','postmerge_attempts','effect_count')
    return dict({k:row[k] for k in keys},status=row['state'],reason=reason or row['reason'],action=action)


class Controller:
    """Only the installed actual private factory can supply host dependencies."""
    def __init__(self):raise TypeError('Use Controller.from_context')

    @classmethod
    def from_context(cls,context,journal,owner_id,*,sources=None):
        if type(context) is not PRHostContext or type(journal) is not PRJournal:raise ValueError('Actual controller objects required')
        identifier(owner_id)
        if journal._active!=owner_id:raise ValueError('Actual persistent controller owner required')
        loaded=context._fresh_inputs();provenance=context.private_input_provenance
        if provenance['pr_journal'] is None or provenance['pr_journal']['path']!=str(journal.path):raise ValueError('Foreign controller journal')
        with journal._db(False) as db:
            owner=db.execute('SELECT * FROM owners WHERE owner_id=?',(owner_id,)).fetchone()
            if owner is None or owner['status']!='active' or owner['pid']!=os.getpid():raise ValueError('Controller owner fenced')
        repositories={p['repository'].casefold() for p in loaded['policy']['projects']}
        connections={c.repository.casefold():c for c in loaded['connections']}
        if sources is None:sources={r:PRSource(connections[r],loaded['policy']) for r in repositories}
        if not isinstance(sources,dict) or set(sources)!=repositories:raise ValueError('Configured controller sources required')
        for repository,source in sources.items():
            if (type(source) is not PRSource or source.repository!=repository or source.connection!=connections[repository]
                    or canonical(source.policy)!=canonical(loaded['policy'])):raise ValueError('Foreign controller source')
        controller=object.__new__(cls)
        controller.context=context;controller.journal=journal;controller.owner_id=owner_id
        controller.sources=dict(sources);controller.cursor=0
        controller.references=tuple(sorted((p['repository'].casefold(),t['pr_number']) for p in loaded['policy']['projects'] for t in p['tasks']))
        controller.config={'_controller':controller}
        return controller

    def _transition(self,row,state,**extra):
        return self.journal.transition(row['repository'],row['pr_number'],self.owner_id,
            dict(state=row['state'],input_sha256=row['input_sha256']),dict(state=state,**extra))

    def _effects(self,row):
        return [e for e in self.journal.effects(row['repository'],row['pr_number'])
            if all(type(e['binding'][k]) is type(row[k]) and e['binding'][k]==row[k] for k in BINDING)]

    def _advance(self,task):
        journal=self.journal;context=self.context;source=self.sources[task['repository'].casefold()]
        row=journal.get(task['repository'],task['pr_number'])
        if row is None:
            prepare_admission(context,source,journal,task)
            return _public(journal.get(task['repository'],task['pr_number']),action='prepared'),True
        if row['owner_id'] not in (None,self.owner_id):return _public(row,reason='owner_fenced'),False
        if row['state'] in ('completed','cancelled','timed_out','unknown'):return _public(row),False
        effects=PREffects(source,journal,task,self.owner_id,context=context)
        if row['state'] in ('merge_intent','merge_pending'):
            observed=effects.observe_merge()
            return _public(journal.get(task['repository'],task['pr_number']),action='merge_observed',
                reason=None if observed['status']=='confirmed' else 'merge_pending'),True
        if any(e['status'] not in ('confirmed','failed') for e in self._effects(row)):
            return _public(row,reason='effect_unverified'),False
        if row['state'] in ('stale','rejected','needs_input'):
            if row['cancel_requested']:return _public(row,reason='cancelled'),False
            if any(e['kind']=='acceptance_status' and e['payload']['state']=='failure' and e['status']=='confirmed' for e in self._effects(row)):
                return _public(row),False
            effect=effects.publish_failure()
            return _public(journal.get(task['repository'],task['pr_number']),action=effect['kind']),True
        if row['state'] in ('discovered','validating','reviewing'):
            outcome=run_review(context,source,journal,task,self.owner_id)
            row=journal.get(task['repository'],task['pr_number'])
            if outcome['status']=='confirmed':
                receipt=context.review_record(row['input_sha256'])['receipt']
                row=self._transition(row,'reviewed',pr_receipt_sha256=receipt['receipt_sha256'],reviewer_instance_id=receipt['reviewer_instance_id'])
            elif outcome['status']=='failed':row=self._transition(row,'needs_input',reason='review_failed')
            return _public(row,action='review'),True
        if row['state'] in ('reviewed','publishing_acceptance'):
            receipt=context.review_record(row['input_sha256'])['receipt']
            if row['state']=='reviewed':row=self._transition(row,'publishing_acceptance')
            positive=receipt['verdict']=='approve'
            effect=effects.publish(receipt) if positive else effects.publish_failure()
            row=journal.get(task['repository'],task['pr_number'])
            if effect['kind']=='acceptance_status' and effect['status']=='confirmed':
                row=self._transition(row,'accepted' if positive else ('rejected' if receipt['verdict']=='reject' else 'needs_input'),
                    **({} if positive else dict(reason='review_'+receipt['verdict'])))
            return _public(row,action=effect['kind']),True
        if row['state']=='accepted':
            if task['merge_enabled'] is not True or task['exclusive_writer']['enabled'] is not True:
                return _public(row,reason='merge_disabled'),False
            receipt=context.review_record(row['input_sha256'])['receipt']
            effect=effects.request_merge(receipt)
            return _public(journal.get(task['repository'],task['pr_number']),action='merge',
                reason=None if effect['status']=='confirmed' else 'merge_pending'),True
        # The real postmerge/closure consumers are added next. No closed Issue,
        # merge, CI result or placeholder is treated as completion meanwhile.
        return _public(row,reason='postmerge_pending'),False


def step(config,journal,*,owner_id):
    if (not isinstance(config,dict) or set(config)!={'_controller'} or type(config['_controller']) is not Controller
            or type(journal) is not PRJournal):raise ValueError('Actual installed PR controller required')
    controller=config['_controller']
    if controller.journal is not journal or controller.owner_id!=owner_id or journal._active!=owner_id:
        raise ValueError('Foreign PR controller owner')
    try:loaded=controller.context._fresh_inputs()
    except (ValueError,OSError):return _public(reason='private_inputs_unverified')
    count=len(controller.references)
    if not count:return _public()
    report=_public()
    for _ in range(min(count,loaded['policy']['max_prs_per_tick'])):
        repository,number=controller.references[controller.cursor%count];controller.cursor=(controller.cursor+1)%count
        try:
            task=authorized_task(loaded['policy'],repository,number)
            report,acted=controller._advance(task)
            if acted:return report
        except (ValueError,OSError,TypeError,KeyError):
            row=journal.get(repository,number)
            # An exception can follow a consumed role/write intent. Never
            # scan another PR in this tick after an uncertain outcome. The
            # already-advanced cursor preserves fairness on the next tick.
            return _public(row,reason='pr_step_unverified')
    return report
