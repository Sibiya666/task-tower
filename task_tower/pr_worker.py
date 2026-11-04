"""Typed bounded PR controller; publication/merge authority stays in PREffects."""
import os
from .pr_context import PRHostContext
from .pr_journal import PRJournal,BINDING
from .pr_source import PRSource,PRSourceError
from .github_source import GitHubSource,GitHubSourceError
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
    def from_context(cls,context,journal,owner_id,*,sources=None,main_sources=None):
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
        if main_sources is None:
            main_sources={r:GitHubSource(connections[r].repository) for r in repositories}
            for repository,source in sources.items():
                if 'Authorization' in source.headers:
                    main_sources[repository].headers['Authorization']=source.headers['Authorization']
        if (not isinstance(main_sources,dict) or set(main_sources)!=repositories or
                any(type(source) is not GitHubSource or source.repository.casefold()!=repository for repository,source in main_sources.items())):
            raise ValueError('Actual configured main sources required')
        controller=object.__new__(cls)
        controller.context=context;controller.journal=journal;controller.owner_id=owner_id
        controller.sources=dict(sources);controller.cursor=0
        controller.main_sources=dict(main_sources);controller._mains={}
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
        unresolved=[e for e in self._effects(row) if e['status'] not in ('confirmed','failed')]
        if unresolved and (row['state']!='awaiting_closure' or any(e['kind'] not in ('comment_post','issue_close') for e in unresolved)):
            return _public(row,reason='effect_unverified'),False
        if row['state']=='awaiting_main':
            from .pr_main import prepare_main
            prepared=prepare_main(context,source,self.main_sources[source.repository],journal,task,self.owner_id)
            if prepared is None:return _public(row,reason='main_ci_pending'),False
            self._mains[(row['repository'],row['pr_number'])]=prepared
            row=self._transition(row,'awaiting_postmerge')
            return _public(row,action='main_prepared'),True
        if row['state']=='awaiting_postmerge':
            from .pr_main import review_main
            prepared=self._mains.get((row['repository'],row['pr_number']))
            observed,result=review_main(prepared)
            envelope=result['host_review']
            approved=(observed['status']=='confirmed' and result['status']=='done' and envelope['result']['verdict']=='approve')
            row=self._transition(row,'awaiting_closure' if approved else 'needs_input',
                **(dict(postmerge_receipt_sha256=envelope['receipt_sha256']) if approved else dict(reason='postmerge_not_accepted')))
            return _public(row,action='postmerge_review'),True
        if row['state']=='awaiting_closure':
            from .pr_main import publish_main
            prepared=self._mains.get((row['repository'],row['pr_number']))
            result,publication=publish_main(prepared)
            if result['status']=='published':
                if publication is None or publication['phase']!='published':raise ValueError('Actual completion publication required')
                journal.complete_barrier(row['repository'],self.owner_id,publication['completion_proof'])
                return _public(journal.get(row['repository'],row['pr_number']),action='closure_completed'),True
            if result['status']=='needs_input':row=self._transition(row,'needs_input',reason='publication_not_accepted')
            return _public(row,action=result['action'] if result['action']!='none' else 'publication_observed'),True
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
        except (ValueError,OSError,TypeError,KeyError,PRSourceError,GitHubSourceError):
            row=journal.get(repository,number)
            # An exception can follow a consumed role/write intent. Never
            # scan another PR in this tick after an uncertain outcome. The
            # already-advanced cursor preserves fairness on the next tick.
            return _public(row,reason='pr_step_unverified')
    return report
