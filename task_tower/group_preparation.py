"""Genuine private initial-preparation reads; resource/clone writes stay closed."""
import copy
import json
import os
from types import SimpleNamespace
from .group_registration import RegistrationContext
from .group_policy import group_binding
from .pipeline_inputs import canonical_json,digest_manifest


def binding_authorization_projection(binding):
    """Pure exact comparison preimage; no imported dictionary grants authority."""
    fields={'status','reason','group_id','role_profiles','components','capacity','harness_resources','harness_pools',
        'version','installation_id','canonical_journal','repository','issue','task_id','runner_label','executor_profile',
        'profile_sha256','role_pins','budgets','task_policy','base_update','accepted_main_source','authorization_sha256','capacity_sha256'}
    if not isinstance(binding,dict) or set(binding)!=fields or type(binding['version']) is not int or binding['version']!=2:
        raise ValueError('Invalid group authority binding')
    result=copy.deepcopy(binding)
    for field in ('capacity','capacity_sha256','harness_pools'):del result[field]
    for resource in result['harness_resources'].values():
        if set(resource)!={'pool_id','cpu_millis','memory_bytes','max_parallel'}:raise ValueError('Invalid group resource binding')
        del resource['max_parallel']
    return result


class PreparationContext:
    """Held real source/runtime authority, never an imported graph dictionary."""
    def __init__(self):
        raise TypeError('Use PreparationContext.from_registration')

    @classmethod
    def from_registration(cls,registration):
        from .source_deadline import source_deadline
        if type(registration) is not RegistrationContext:raise ValueError('Actual registration context required')
        with source_deadline(registration.deadline):
            return cls._collect(registration)

    @classmethod
    def _collect(cls,registration):
        from .pipeline import _runtime
        from .pipeline_policy import admission_authorized,_current
        from .dispatch_selection import collect_snapshot
        from .capture import relationship_projection
        from .group_graph import build_graph,observe_results,evaluate_graph
        from .group_resources import ResourceContext
        if type(registration) is not RegistrationContext:raise ValueError('Actual registration context required')
        registration.revalidate()
        journal=registration.journal
        resource=ResourceContext.from_registration(registration)
        # This is the actual installed runtime closure, not the convenience
        # context.pipeline copy or a caller-supplied approval function.
        args=SimpleNamespace(connections=registration.connections_path,config=registration.pipeline_path,
            executor_config=registration.executor_path,journal=journal.path,groups_config=registration.groups_path)
        connections,loaded_journal,runtime=_runtime(args)
        if loaded_journal.path!=journal.path or not _current(runtime):raise ValueError('Invalid current group runtime')
        registration.revalidate()
        context=object.__new__(cls)
        context._registration=registration;context._runtime=runtime;context._resources=resource
        context._pid=os.getpid();context._records={};context._snapshots={}
        with journal._db(False,initialize=False) as db:
            queued=[dict(r) for r in db.execute("SELECT r.*,g.binding_sha256 AS queued_binding_sha256,g.binding_json AS queued_binding_json FROM runs r JOIN group_runs g USING(run_id) WHERE g.run_kind='group' AND r.state='queued' AND r.cancel_requested=0 ORDER BY r.repository,r.issue LIMIT 256")]
        if not queued:return context
        snapshot=collect_snapshot(connections)
        relationships={}
        for repository,project in sorted(snapshot.items()):
            if project['error']:continue
            for number,issue in sorted(project['issues'].items()):
                registration.revalidate()
                projection,_=relationship_projection(project['connection'],project['store'],issue)
                relationships[repository+'#'+str(number)]=projection
        graph=build_graph(snapshot,registration.policy,relationships)
        accepted=observe_results(connections,snapshot)
        evaluation=evaluate_graph(graph,accepted)
        for run in queued:
            registration.revalidate()
            identity=run['repository']+'#'+str(run['issue'])
            node=evaluation['nodes'].get(identity)
            if node is None or node['status']!='ready':continue
            tasks=[t for t in runtime['tasks'] if t['repository'].casefold()==run['repository'] and
                t['issue']==run['issue'] and t['task_id']==run['task_id'] and t['runner_label']==run['runner_label']]
            if len(tasks)!=1:continue
            private=registration.policy['_tasks'].get((run['repository'],run['issue']))
            if private is None:continue
            binding=group_binding(registration.policy,private)
            if binding['status']!='ready':continue
            original=json.loads(run['queued_binding_json'])
            if (original['authorization_sha256']!=binding['authorization_sha256']
                    or canonical_json(binding_authorization_projection(original))!=canonical_json(binding_authorization_projection(binding))):continue
            # Accepted-main opt-in needs its actual proof/resolver consumer;
            # never silently substitute pinned mode for an unresolved grant.
            if binding['accepted_main_source'] is not None:continue
            admission=admission_authorized(runtime,tasks[0],snapshot)
            if admission is None:continue
            from .pipeline_journal import _now
            body=dict(version=1,kind='initial_preparation',run_id=run['run_id'],delivery_id=run['delivery_id'],
                repository=run['repository'],issue_id=admission['issue_id'],task_id=run['task_id'],
                graph_snapshot_sha256=graph['snapshot_sha256'],graph=graph,accepted_results=accepted,evaluation=evaluation,
                source_admission=admission,source_policy_sha256=runtime['policy_sha256'],
                authorization_sha256=binding['authorization_sha256'],queued_group_binding_sha256=run['queued_binding_sha256'],
                current_group_binding=binding,current_group_binding_sha256=digest_manifest(binding),observed_at=_now())
            raw=canonical_json(body)
            context._records[run['run_id']]=raw
        registration.revalidate()
        if not _current(runtime):raise ValueError('Group runtime changed during preparation reads')
        return context

    def candidates(self):
        if self._pid!=os.getpid():raise ValueError('Foreign preparation collector process')
        self._registration.revalidate()
        return [json.loads(raw) for _,raw in sorted(self._records.items())]

    def initial_admission(self,run_id):
        """Explicit admission2 projection only; this does not claim or write J."""
        from .pipeline_policy import _current
        from .pipeline_journal import PipelineJournal
        if self._pid!=os.getpid():raise ValueError('Foreign preparation collector process')
        self._registration.revalidate()
        if not _current(self._runtime):raise ValueError('Current preparation policy changed')
        raw=self._records.get(run_id)
        if raw is None:raise ValueError('Missing actual preparation source')
        body=json.loads(raw)
        scope=self._resources._snapshot()
        with self._registration.journal._db(False,initialize=False) as db:
            row=db.execute("SELECT r.*,g.binding_sha256 AS queued_binding_sha256,g.authorization_sha256 AS queued_authorization_sha256 FROM runs r JOIN group_runs g USING(run_id) WHERE r.run_id=? AND g.run_kind='group'",(run_id,)).fetchone()
            if (row is None or row['state']!='queued' or row['cancel_requested'] or row['owner_id'] is not None
                    or row['delivery_id']!=body['delivery_id'] or row['queued_binding_sha256']!=body['queued_group_binding_sha256']
                    or row['queued_authorization_sha256']!=body['authorization_sha256']
                    or body['source_policy_sha256']!=self._runtime['policy_sha256']):raise ValueError('Original preparation binding changed')
            source=PipelineJournal._admission(body['source_admission'])
            if source['policy_sha256']!=body['source_policy_sha256']:raise ValueError('Actual source policy mismatch')
            result=dict(source,version=2,policy_sha256=row['policy_sha256'],source_policy_sha256=source['policy_sha256'],
                authorization_sha256=body['authorization_sha256'],capacity_epoch=scope['policy_epoch'],
                source_snapshot_sha256=digest_manifest(body),group_binding_sha256=body['queued_group_binding_sha256'])
        self._registration.revalidate()
        return result
