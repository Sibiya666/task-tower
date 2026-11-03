"""Host-only registration context. Loading metadata never admits execution."""
from contextlib import ExitStack
import os
from pathlib import Path
import time

from .executor import _paths
from .executor_profiles import load_executor_config
from .pipeline_policy import load_pipeline_config
from .group_policy import load_group_config
from .project_connections import load_connections, safe_config_path
from .pipeline_journal import _pin_identity, _open_database_pin
from .executor_queue import _private_stat

class RegistrationUnavailable(ValueError):
    """Closed operational reasons; never stored run/delivery authority."""
    def __init__(self,reason):
        if reason not in {'group_runtime_unavailable','group_registration_required','group_policy_revoked','group_binding_mismatch','group_migration_required'}:
            raise ValueError('Invalid registration operational reason')
        self.reason=reason
        super().__init__(reason)

class RegistrationRecoveryRequired(ValueError):
    pass

class RegistrationContext:
    """Retained host file references created exclusively by actual source loading."""
    def __init__(self):
        raise TypeError('Use load_registration_context')
    def __enter__(self):
        try:
            self.revalidate()
            return self
        except BaseException:
            self.close()
            raise
    def __exit__(self,*exc):
        self.close()
    def close(self):
        if not self._closed:
            self._closed=True
            self._stack.close()
    def revalidate(self):
        if self._closed or time.monotonic()>=self.deadline:
            raise ValueError('Unavailable registration context')
        self.journal._assert_existing()
        for path,(fd,identity,raw) in self._sources.items():
            self.journal._wait_seconds()
            safe_config_path(path)
            current=_pin_identity(_private_stat(path))
            opened=_pin_identity(os.fstat(fd))
            if not os.path.samestat(identity,current) or not os.path.samestat(identity,opened):
                raise ValueError('Registration source identity changed')
            if path.read_bytes()!=raw:
                raise ValueError('Registration source bytes changed')
        # A caller may retain this host context, but its mutable normalized
        # dictionaries never replace authority freshly derived from held files.
        connections=load_connections(self.connections_path)
        executor=load_executor_config(self.executor_path,connections)
        pipeline=load_pipeline_config(self.pipeline_path,connections,executor)
        current=load_group_config(self.groups_path,connections,executor,pipeline)
        if current!=self.policy:
            raise ValueError('Registration loaded authority changed')
        # Loaders may spend time/read multiple files; close that race as well.
        for path,(fd,identity,raw) in self._sources.items():
            self.journal._wait_seconds()
            if not os.path.samestat(identity,_pin_identity(_private_stat(path))) or not os.path.samestat(identity,_pin_identity(os.fstat(fd))) or path.read_bytes()!=raw:
                raise ValueError('Registration source changed while loading')

def load_registration_context(groups_path,connections_path,pipeline_path,executor_path,journal):
    """Hold same existing J and genuine private source identities within one budget."""
    ctx=object.__new__(RegistrationContext)
    ctx._stack=ExitStack();ctx._closed=False;ctx.deadline=time.monotonic()+60
    ctx.journal=journal;ctx._sources={}
    try:
        ctx._stack.enter_context(journal.operation_deadline(ctx.deadline))
        identity=ctx._stack.enter_context(journal._pinned_database())
        if identity is None:raise ValueError('Missing existing registration journal')
        ctx.identity=identity
        ctx._stack.enter_context(journal._existing_database(identity))
        # Recognition must precede any writer or source-profile/pin loading.
        report=journal.inspect_group_migration()
        if report['status']=='recovery_required':raise RegistrationRecoveryRequired()
        if report.get('version')==1:raise RegistrationUnavailable('group_migration_required')
        if report.get('version')!=2:raise ValueError('Invalid existing registration journal')
        paths=[safe_config_path(Path(x)) for x in (groups_path,connections_path,pipeline_path,executor_path)]
        for path in paths:
            journal._wait_seconds()
            before=_pin_identity(_private_stat(path));fd=_open_database_pin(path)
            ctx._stack.callback(os.close,fd)
            if not os.path.samestat(before,_pin_identity(os.fstat(fd))):
                raise ValueError('Registration source replaced')
            ctx._sources[path]=(fd,before,path.read_bytes())
        ctx.groups_path,ctx.connections_path,ctx.pipeline_path,ctx.executor_path=paths
        ctx.connections=load_connections(ctx.connections_path)
        families=[*paths,journal.path]
        sidecars=[Path(str(path)+s) for path in families for s in ('-journal','-wal','-shm')]
        _paths([*families,*sidecars],ctx.connections,transient_paths=sidecars)
        ctx.executor=load_executor_config(ctx.executor_path,ctx.connections)
        ctx.pipeline=load_pipeline_config(ctx.pipeline_path,ctx.connections,ctx.executor)
        ctx.policy=load_group_config(ctx.groups_path,ctx.connections,ctx.executor,ctx.pipeline)
        if ctx.policy['version']!=2 or ctx.policy['canonical_journal']!=str(journal.path):
            raise RegistrationUnavailable('group_binding_mismatch')
        ctx.revalidate()
        return ctx
    except BaseException:
        ctx.close()
        raise


# Registration event bodies are neutral immutable provenance, not execution inputs.
import base64
import copy
import hashlib
import json
from .pipeline_inputs import canonical_json, digest_manifest
from . import group_policy as gp


def _json(value):
    from .group_storage import _json as parse
    return parse(value)


def _identity(info):
    return dict(version=1,st_dev=info.st_dev,st_ino=info.st_ino)


def _snapshot(context):
    manifests=gp.policy_manifests(context.policy)
    return dict(group={k:copy.deepcopy(v) for k,v in context.policy.items() if not k.startswith('_')},
        group_raw_base64=base64.b64encode(context._sources[context.groups_path][2]).decode('ascii'),
        **manifests,source_sha256={key:hashlib.sha256(context._sources[path][2]).hexdigest()
        for key,path in zip(('groups','pipeline','executor','connections'),
            (context.groups_path,context.pipeline_path,context.executor_path,context.connections_path))})


def _epoch(snapshot,number,kind,when):
    group=snapshot['group'];capacity=snapshot['capacity']
    return dict(epoch=number,installation_id=group['installation_id'],change_kind=kind,
        policy_sha256=group['policy_sha256'],authorization_sha256=group['authorization_sha256'],
        group_maximum=group['capacity']['max_executors'],pipeline_maximum=capacity['pipeline_capacity']['max_executors'],
        executor_maximum=capacity['executor_capacity']['max_executors'],effective_maximum=group['effective_capacity']['max_executors'],
        max_inflight=group['effective_capacity']['max_inflight'],
        resource_policy_json=canonical_json(group['capacity']).decode(),
        capacity_matrix_json=canonical_json(capacity).decode(),capacity_sha256=group['capacity_sha256'],registered_at=when)


def _insert(db,table,row):
    db.execute('INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))


def register(journal,context):
    from .group_storage import _stopped,_event,_json
    from .pipeline_journal import _now
    if type(context) is not RegistrationContext or context.journal is not journal:
        raise ValueError('Invalid registration context')
    context.revalidate()
    with journal._db(True,initialize=False) as db:
        context.revalidate();_stopped(db,journal)
        previous=db.execute('SELECT * FROM group_installation').fetchone()
        snapshot=_snapshot(context);group=snapshot['group'];when=_now()
        if previous is None:
            number=1;kind='initial'
            installation=dict(singleton=1,installation_id=group['installation_id'],canonical_journal=str(journal.path),
                journal_file_identity_json=canonical_json(_identity(context.identity)).decode(),groups_config_path=str(context.groups_path),
                current_capacity_epoch=1,current_policy_sha256=group['policy_sha256'],
                current_authorization_sha256=group['authorization_sha256'],bound_at=when)
        else:
            previous=dict(previous)
            if any(previous[key]!=value for key,value in dict(installation_id=group['installation_id'],
                canonical_journal=str(journal.path),groups_config_path=str(context.groups_path),
                journal_file_identity_json=canonical_json(_identity(context.identity)).decode()).items()):
                raise RegistrationUnavailable('group_binding_mismatch')
            old=db.execute('SELECT * FROM group_capacity_epochs WHERE epoch=?',(previous['current_capacity_epoch'],)).fetchone()
            if group['policy_sha256']==old['policy_sha256'] and group['authorization_sha256']==old['authorization_sha256'] and group['capacity_sha256']==old['capacity_sha256']:
                context.revalidate()
                return dict(status='already_registered',installation_id=group['installation_id'],epoch=old['epoch'])
            kind='capacity_only' if group['authorization_sha256']==old['authorization_sha256'] else 'authorization_change'
            number=old['epoch']+1
            installation=dict(previous,current_capacity_epoch=number,current_policy_sha256=group['policy_sha256'],current_authorization_sha256=group['authorization_sha256'])
        epoch=_epoch(snapshot,number,kind,when)
        # Preflight serialized size before any mutation, including raw-G base64 expansion.
        adoptions=[]
        if previous is None:
            for lease in db.execute('SELECT l.*,r.profile_id,r.profile_fingerprint FROM group_resource_leases l JOIN runs r USING(run_id) ORDER BY l.action_id'):
                grant=group['harness_resources'].get(lease['profile_id']);fingerprint=snapshot['authorization']['profiles'].get(lease['profile_id'])
                estimate=None
                if lease['held'] and grant is not None and fingerprint==lease['profile_fingerprint']:
                    cpu=grant['cpu_millis']+100;memory=grant['memory_bytes']+64*1024*1024
                    if cpu<=2**63-1 and memory<=2**63-1:
                        estimate=dict(cpu_millis=cpu,memory_bytes=memory,harness_pool=grant['pool_id'])
                adoptions.append(dict(action_id=lease['action_id'],run_id=lease['run_id'],profile_id=lease['profile_id'],
                    profile_fingerprint=lease['profile_fingerprint'],capacity_epoch=number,estimate=estimate))
        body=dict(version=1,installation=installation,epoch=epoch,policy_snapshot=snapshot,legacy_adoptions=adoptions)
        _json(canonical_json(body).decode())
        if previous is None:
            _insert(db,'group_installation',installation)
            _insert(db,'group_capacity_epochs',epoch)
            db.execute('UPDATE group_reservations SET capacity_epoch=?',(number,))
            for adoption in adoptions:
                estimate=adoption['estimate']
                db.execute('UPDATE group_resource_leases SET capacity_epoch=?,cpu_millis=?,memory_bytes=?,harness_pool=?,unknown_estimate=? WHERE action_id=?',
                    (number,estimate['cpu_millis'] if estimate else None,estimate['memory_bytes'] if estimate else None,
                     estimate['harness_pool'] if estimate else None,int(estimate is None),adoption['action_id']))
        else:
            _insert(db,'group_capacity_epochs',epoch)
            updated=db.execute('UPDATE group_installation SET current_capacity_epoch=?,current_policy_sha256=?,current_authorization_sha256=? WHERE singleton=1 AND current_capacity_epoch=? AND current_policy_sha256=? AND current_authorization_sha256=?',
                (number,group['policy_sha256'],group['authorization_sha256'],previous['current_capacity_epoch'],previous['current_policy_sha256'],previous['current_authorization_sha256'])).rowcount
            if updated!=1:raise ValueError('Registration epoch changed')
        _event(db,'binding' if previous is None else 'capacity_epoch',body,when=when)
        context.revalidate()
    return dict(status='registered' if previous is None else kind,installation_id=group['installation_id'],epoch=number)


def discover(journal):
    with journal.operation_deadline(time.monotonic()+60),journal._pinned_database() as identity:
        if identity is None:raise ValueError('Missing existing registration journal')
        with journal._existing_database(identity),journal._db(False,initialize=False) as db:
            if db.execute('PRAGMA user_version').fetchone()[0]!=2:return None
            row=db.execute('SELECT * FROM group_installation').fetchone()
            if row is not None:journal._registration_expectation=identity
            return None if row is None else dict(row)



def _closed(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys):raise ValueError('Invalid stored registration fields')
    return value


def _validate_authority(authority):
    """Validate saved normalized types without consulting files, tools or pins."""
    import re
    from .pipeline_journal import _sha
    from .project_connections import REPOSITORY
    for profile,h in authority['profiles'].items():gp._name(profile);_sha(h)
    _closed(authority['limits'],set(gp.LIMITS)-{'max_active'})
    for key,value in authority['limits'].items():
        _,low,high=gp.LIMITS[key];gp._integer(value,low,high)
    connections={}
    for connection in authority['connections']:
        _closed(connection,('repository','checkout','runner_label','trusted_publishers'))
        repository=gp._name(connection['repository'],REPOSITORY)
        if repository!=repository.casefold() or repository in connections:raise ValueError('Invalid stored connection identity')
        gp._name(connection['runner_label'])
        if not isinstance(connection['checkout'],str) or not Path(connection['checkout']).is_absolute():raise ValueError('Invalid stored checkout')
        accounts=connection['trusted_publishers']
        if not isinstance(accounts,list) or any(not isinstance(a,str) or '--' in a or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?',a) for a in accounts) or len({a.casefold() for a in accounts})!=len(accounts):raise ValueError('Invalid stored publisher list')
        connections[repository]=connection
    identities=set();aliases=set()
    for task in authority['tasks']:
        _closed(task,gp.TASK_FIELDS)
        repository=gp._name(task['repository'],REPOSITORY);gp._integer(task['issue'],1,2**63-1);gp._name(task['task_id'],gp.TASK_ID)
        gp._name(task['runner_label']);profile=gp._name(task['executor_profile'])
        if repository!=repository.casefold() or repository not in connections or profile not in authority['profiles'] or connections[repository]['runner_label']!=task['runner_label']:raise ValueError('Invalid saved task scope')
        identity=(repository,task['issue']);alias=(repository,task['task_id'])
        if identity in identities or alias in aliases:raise ValueError('Duplicate saved task')
        identities.add(identity);aliases.add(alias)
        if gp._components(task['components'])!=task['components']:raise ValueError('Noncanonical saved components')
        paths=task['allowed_paths']
        if not isinstance(paths,list) or not paths:raise ValueError('Missing saved paths')
        for path in paths:gp._relative(path)
        for i,path in enumerate(paths):
            if any(gp._contains(path.casefold(),other.casefold()) or gp._contains(other.casefold(),path.casefold()) for other in paths[i+1:]):raise ValueError('Overlapping saved task paths')
        for key in ('spec_path','plan_path','evidence_dir'):
            gp._relative(task[key])
            if not any(gp._contains(path,task[key]) for path in paths):raise ValueError('Saved artifact outside scope')
        if task['spec_path'].endswith('/') or task['plan_path'].endswith('/') or task['spec_path'].casefold()==task['plan_path'].casefold() or not task['evidence_dir'].endswith('/') or any(gp._contains(task['evidence_dir'].casefold(),task[k].casefold()) or task['evidence_dir'].casefold().startswith(task[k].casefold()+'/') for k in ('spec_path','plan_path')):raise ValueError('Invalid saved artifact overlap')
        checks=task['checks'];seen=set()
        if not isinstance(checks,list) or not checks:raise ValueError('Missing stored checks')
        for check in checks:
            _closed(check,('id','argv','timeout_seconds'));gp._name(check['id']);gp._integer(check['timeout_seconds'],1,3600)
            if check['id'] in seen:raise ValueError('Duplicate stored check')
            seen.add(check['id']);argv=check['argv']
            if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a or '\x00' in a for a in argv) or not Path(argv[0]).is_absolute() or Path(argv[0]).suffix.casefold() in ('.bat','.cmd'):raise ValueError('Invalid stored check argv')
        ci=_closed(task['ci_substitution'],('enabled','required_platforms'))
        if type(ci['enabled']) is not bool or not isinstance(ci['required_platforms'],list) or any(type(v) is not str or v not in ('windows','macos','linux') for v in ci['required_platforms']) or len(set(ci['required_platforms']))!=len(ci['required_platforms']) or bool(ci['required_platforms'])!=ci['enabled']:raise ValueError('Invalid stored CI')
        publish=_closed(task['publish'],('enabled','remote','base_ref','publisher_account'))
        if type(publish['enabled']) is not bool or publish['remote']!='origin' or publish['base_ref']!='refs/heads/main' or not isinstance(publish['publisher_account'],str) or publish['publisher_account'].casefold() not in [a.casefold() for a in connections[repository]['trusted_publishers']]:raise ValueError('Invalid stored publication scope')


def _normalize_raw(raw,authority):
    _closed(raw,{'version','installation_id','canonical_journal','projects'}|({'capacity'} if 'capacity' in raw else set()))
    if type(raw['version']) is not int or raw['version']!=2:raise ValueError('Invalid stored group version')
    if not isinstance(raw['projects'],list):raise ValueError('Invalid stored projects')
    tasks={(t['repository'],t['issue']):t for t in authority['tasks']}
    profiles=authority['profiles'];connections={c['repository'] for c in authority['connections']}
    projects=[]
    for p in raw['projects']:
        required={'repository','groups','routes','aggregates'}
        if not isinstance(p,dict) or not required<=set(p) or set(p)-required-{'base_update','accepted_main_sources'}:raise ValueError('Invalid saved project')
        repository=gp._name(p['repository'],gp.REPOSITORY).casefold()
        if repository not in connections:raise ValueError('Unknown stored project')
        groups=[]
        for g in p['groups']:
            required={'id','components','role_profiles'}
            if not isinstance(g,dict) or not required<=set(g) or set(g)-required-{'capacity','max_inflight'}:raise ValueError('Invalid saved group')
            roles=_closed(g['role_profiles'],gp.ROLES)
            for profile in roles.values():
                if gp._name(profile) not in profiles:raise ValueError('Unknown stored role profile')
            groups.append(dict(id=gp._name(g['id']),components=gp._components(g['components']),role_profiles=roles,
                capacity=gp._cap(g.get('capacity')),max_inflight=gp._cap(g.get('max_inflight'))))
        if len({g['id'] for g in groups})!=len(groups):raise ValueError('Duplicate saved group')
        index={g['id']:g for g in groups};routes=[]
        for route in p['routes']:
            _closed(route,('issue','task_id','group'));gp._integer(route['issue'],1,2**63-1);gp._name(route['task_id'],gp.TASK_ID)
            task=tasks[(repository,route['issue'])];g=index[gp._name(route['group'])]
            if task['task_id']!=route['task_id'] or any(profile!=task['executor_profile'] for profile in g['role_profiles'].values()):raise ValueError('Stored route widens authority')
            if g['components']!=['*'] and not set(task['components'])<=set(g['components']):raise ValueError('Stored component scope mismatch')
            routes.append(route)
        aggregates=[];seen=set()
        for aggregate in p['aggregates']:
            _closed(aggregate,('issue','task_id','required_children'));gp._integer(aggregate['issue'],1,2**63-1);gp._name(aggregate['task_id'],gp.TASK_ID)
            if aggregate['issue'] in seen or not any(r['issue']==aggregate['issue'] and r['task_id']==aggregate['task_id'] for r in routes):raise ValueError('Invalid stored aggregate')
            seen.add(aggregate['issue']);children=aggregate['required_children']
            if not isinstance(children,list) or not children:raise ValueError('Invalid saved children')
            children=[gp._name(c,gp.REPOSITORY+r'#[1-9][0-9]*').casefold() for c in children]
            if len(set(children))!=len(children):raise ValueError('Duplicate saved child')
            aggregates.append(dict(issue=aggregate['issue'],task_id=aggregate['task_id'],required_children=sorted(children)))
        update=p.get('base_update',dict(enabled=False,max_updates=0));_closed(update,('enabled','max_updates'))
        if type(update['enabled']) is not bool or bool(gp._integer(update['max_updates'],0,2))!=update['enabled']:raise ValueError('Invalid stored update')
        grants=p.get('accepted_main_sources',[]);seen=set()
        if not isinstance(grants,list):raise ValueError('Invalid saved source grants')
        for grant in grants:
            _closed(grant,('executor_profile','profile_sha256','anchor_sha'))
            profile=gp._name(grant['executor_profile']);gp._name(grant['anchor_sha'],'[a-f0-9]{40}')
            if profile in seen or grant['profile_sha256']!=profiles.get(profile):raise ValueError('Invalid stored source grant')
            seen.add(profile)
        projects.append(dict(repository=repository,groups=groups,routes=routes,aggregates=aggregates,base_update=update,accepted_main_sources=grants))
    if len({p['repository'] for p in projects})!=len(projects):raise ValueError('Duplicate stored project')
    return projects


def validate_snapshot(snapshot,installation):
    from .pipeline_journal import _uuid,_sha
    _closed(snapshot,('group','group_raw_base64','authorization','capacity','source_sha256'))
    group=snapshot['group'];authority=snapshot['authorization'];capacity=snapshot['capacity']
    _closed(group,('version','installation_id','canonical_journal','projects','capacity','harness_resources','effective_capacity','policy_sha256','authorization_sha256','capacity_sha256'))
    _closed(snapshot['source_sha256'],('groups','pipeline','executor','connections'))
    for h in snapshot['source_sha256'].values():_sha(h)
    raw=base64.b64decode(snapshot['group_raw_base64'],validate=True)
    if base64.b64encode(raw).decode()!=snapshot['group_raw_base64']:raise ValueError('Noncanonical saved base64')
    parsed=json.loads(raw.decode('utf-8'),object_pairs_hook=gp._pairs)
    _uuid(parsed['installation_id'])
    if type(group['version']) is not int or group['version']!=2 or parsed['installation_id']!=group['installation_id'] or parsed['canonical_journal']!=group['canonical_journal']:
        raise ValueError('Stored raw group identity mismatch')
    if group['installation_id']!=installation['installation_id'] or group['canonical_journal']!=installation['canonical_journal']:raise ValueError('Stored installation identity mismatch')
    if hashlib.sha256(raw).hexdigest()!=group['policy_sha256'] or group['policy_sha256']!=snapshot['source_sha256']['groups']:raise ValueError('Stored raw group hash mismatch')
    _closed(authority,('version','installation_id','canonical_journal','projects','harness_resources','config_path','tasks','profiles','limits','connections'))
    if authority['config_path']!=installation['groups_config_path']:raise ValueError('Stored authority path mismatch')
    if not isinstance(authority['tasks'],list) or not isinstance(authority['connections'],list) or not isinstance(authority['profiles'],dict):raise ValueError('Invalid stored authority')
    for profile,h in authority['profiles'].items():gp._name(profile);_sha(h)
    _validate_authority(authority)
    projects=_normalize_raw(parsed,authority)
    if canonical_json(projects)!=canonical_json(group['projects']):raise ValueError('Raw/normalized stored group mismatch')
    default=dict(mode='auto',max_executors=None,max_inflight=None,max_cpu_millis=None,max_memory_bytes=None,fallback=None)
    if canonical_json(gp._capacity(parsed.get('capacity',default)))!=canonical_json(group['capacity']):raise ValueError('Stored capacity mismatch')
    _closed(capacity,('capacity','effective_capacity','executor_capacity','pipeline_capacity','harness_caps','groups'))
    for limits in (capacity['executor_capacity'],capacity['pipeline_capacity']):
        _closed(limits,('max_executors','max_inflight'))
        for cap in limits.values():gp._cap(cap)
    effective=dict(group['capacity'])
    for key in ('max_executors','max_inflight'):effective[key]=gp._minimum(group['capacity'][key],capacity['executor_capacity'][key],capacity['pipeline_capacity'][key])
    if canonical_json(effective)!=canonical_json(group['effective_capacity']):raise ValueError('Invalid stored effective minima')
    if not isinstance(group['harness_resources'],dict) or not group['harness_resources']:raise ValueError('Missing stored resources')
    resources=copy.deepcopy(group['harness_resources'])
    for profile,grant in resources.items():
        if gp._name(profile) not in authority['profiles']:raise ValueError('Unknown stored grant')
        _closed(grant,('pool_id','cpu_millis','memory_bytes','max_parallel'));gp._name(grant['pool_id'])
        gp._integer(grant['cpu_millis'],1,2**63-1);gp._integer(grant['memory_bytes'],1,2**63-1);gp._cap(grant.pop('max_parallel'))
    expected={k:copy.deepcopy(v) for k,v in group.items() if k not in {'capacity','effective_capacity','policy_sha256','authorization_sha256','capacity_sha256'}}
    expected['harness_resources']=resources
    for p in expected['projects']:
        for g in p['groups']:del g['capacity'],g['max_inflight']
    expected.update({k:authority[k] for k in ('config_path','tasks','profiles','limits','connections')})
    expected_capacity=dict(capacity=group['capacity'],effective_capacity=effective,executor_capacity=capacity['executor_capacity'],pipeline_capacity=capacity['pipeline_capacity'],harness_caps={k:v['max_parallel'] for k,v in group['harness_resources'].items()},groups=[dict(repository=p['repository'],id=g['id'],capacity=g['capacity'],max_inflight=g['max_inflight']) for p in projects for g in p['groups']])
    if canonical_json(expected)!=canonical_json(authority) or canonical_json(expected_capacity)!=canonical_json(capacity) or digest_manifest(authority)!=group['authorization_sha256'] or digest_manifest(capacity)!=group['capacity_sha256']:
        raise ValueError('Stored registration manifests disagree')


def validate_stored(db,journal):
    from .pipeline_journal import _uuid,_sha
    from .group_storage import _utc
    rows=[dict(r) for r in db.execute('SELECT * FROM group_installation')]
    epochs=[dict(r) for r in db.execute('SELECT * FROM group_capacity_epochs ORDER BY epoch')]
    events=[dict(r) for r in db.execute("SELECT * FROM group_events WHERE kind IN('binding','capacity_epoch') ORDER BY sequence")]
    if not rows:
        if epochs or events:raise ValueError('Unbound registration history')
        return None
    if len(rows)!=1 or not epochs or len(events)!=len(epochs):raise ValueError('Incomplete registration history')
    installation=rows[0];_uuid(installation['installation_id']);_utc(installation['bound_at'])
    if installation['singleton']!=1 or installation['canonical_journal']!=str(journal.path):raise ValueError('Foreign registration')
    identity=_closed(_json(installation['journal_file_identity_json']),('version','st_dev','st_ino'))
    if type(identity['version']) is not int or identity['version']!=1 or type(identity['st_dev']) is not int or identity['st_dev']<0 or type(identity['st_ino']) is not int or identity['st_ino']<=0:raise ValueError('Invalid stored file identity')
    current=_pin_identity(_private_stat(journal.path))
    if identity!=_identity(current):raise ValueError('Registered journal physical identity changed')
    adoptions={};previous=None;initial_sequence=None
    immutable=('singleton','installation_id','canonical_journal','journal_file_identity_json','groups_config_path','bound_at')
    for number,(epoch,event) in enumerate(zip(epochs,events),1):
        body=_json(event['body_json']);_closed(body,('version','installation','epoch','policy_snapshot','legacy_adoptions'))
        if type(body['version']) is not int or body['version']!=1 or digest_manifest(body)!=event['body_sha256'] or event['run_id'] is not None:raise ValueError('Invalid registration event')
        saved=body['installation'];_closed(saved,installation)
        if any(saved[k]!=installation[k] for k in immutable) or type(saved['current_capacity_epoch']) is not int or saved['current_capacity_epoch']!=number:raise ValueError('Registration immutable binding changed')
        if saved['current_policy_sha256']!=epoch['policy_sha256'] or saved['current_authorization_sha256']!=epoch['authorization_sha256']:raise ValueError('Historical registration pointer mismatch')
        validate_snapshot(body['policy_snapshot'],saved)
        _utc(epoch['registered_at'])
        kind='initial' if previous is None else ('capacity_only' if epoch['authorization_sha256']==previous['authorization_sha256'] else 'authorization_change')
        expected=_epoch(body['policy_snapshot'],number,kind,event['recorded_at'])
        if canonical_json(epoch)!=canonical_json(body['epoch']) or canonical_json(epoch)!=canonical_json(expected) or event['kind']!=('binding' if number==1 else 'capacity_epoch'):raise ValueError('Registration epoch body mismatch')
        if previous and _utc(epoch['registered_at'])<_utc(previous['registered_at']):raise ValueError('Registration time moved backward')
        if number==1:
            if epoch['registered_at']!=installation['bound_at']:raise ValueError('Registration boundary mismatch')
            initial_sequence=event['sequence']
            for adoption in body['legacy_adoptions']:
                _closed(adoption,('action_id','run_id','profile_id','profile_fingerprint','capacity_epoch','estimate'))
                _uuid(adoption['action_id']);_uuid(adoption['run_id']);_sha(adoption['profile_fingerprint'])
                if adoption['action_id'] in adoptions or type(adoption['capacity_epoch']) is not int or adoption['capacity_epoch']!=1:raise ValueError('Invalid adoption identity')
                row=db.execute('SELECT * FROM runs WHERE run_id=?',(adoption['run_id'],)).fetchone()
                if row is None or adoption['profile_id']!=row['profile_id'] or adoption['profile_fingerprint']!=row['profile_fingerprint']:raise ValueError('Adoption changed original profile')
                estimate=adoption['estimate'];snapshot=body['policy_snapshot']
                if estimate is not None:
                    _closed(estimate,('cpu_millis','memory_bytes','harness_pool'))
                    grant=snapshot['group']['harness_resources'].get(row['profile_id'])
                    if grant is None or snapshot['authorization']['profiles'].get(row['profile_id'])!=row['profile_fingerprint'] or estimate!=dict(cpu_millis=grant['cpu_millis']+100,memory_bytes=grant['memory_bytes']+64*1024*1024,harness_pool=grant['pool_id']):raise ValueError('Unproven adopted estimate')
                    gp._integer(estimate['cpu_millis'],1,2**63-1);gp._integer(estimate['memory_bytes'],1,2**63-1)
                adoptions[adoption['action_id']]=adoption
        elif body['legacy_adoptions']!=[]:raise ValueError('Later epoch rewrote adoption')
        previous=epoch
    if installation['current_capacity_epoch']!=len(epochs) or installation['current_policy_sha256']!=previous['policy_sha256'] or installation['current_authorization_sha256']!=previous['authorization_sha256']:raise ValueError('Current registration pointer mismatch')
    leases={r['action_id']:dict(r) for r in db.execute('SELECT * FROM group_resource_leases')}
    if set(leases)!=set(adoptions):raise ValueError('Missing or extra adopted lease')
    for action_id,lease in leases.items():
        adoption=adoptions[action_id];estimate=adoption['estimate']
        if lease['run_id']!=adoption['run_id'] or lease['capacity_epoch']!=1 or lease['observation_id'] is not None or lease['unknown_estimate']!=int(estimate is None) or any(lease[k]!=(estimate[k] if estimate else None) for k in ('cpu_millis','memory_bytes','harness_pool')):raise ValueError('Adopted lease provenance mismatch')
        if not any(_json(event['body_json']).get('action_id')==action_id for event in db.execute("SELECT body_json FROM group_events WHERE kind='observation' AND sequence<?",(initial_sequence,))):raise ValueError('Adoption lacks prior origin boundary')
    return dict(installation=installation,adoptions=adoptions)


def guard_execution(journal,config,*,known_run=False):
    """A recognized registration never falls through a legacy entry point."""
    from .pipeline_journal import PipelineJournal
    if not isinstance(journal,PipelineJournal):
        raise ValueError('Invalid pipeline journal')
    if not journal.path.exists():
        if known_run or config.get('version')==2 or config.get('_executor_config',{}).get('version')==2 or getattr(journal,'_registration_expectation',None) is not None or getattr(config.get('_cli_args'),'groups_config',None) is not None:
            raise ValueError('Missing existing pipeline journal')
        return
    metadata=journal.registered_groups()
    args=config.get('_cli_args')
    explicit=getattr(args,'groups_config',None)
    if metadata is None:
        if explicit is not None or config.get('version')==2 or config.get('_executor_config',{}).get('version')==2:
            raise RegistrationUnavailable('group_registration_required')
        return
    if explicit is not None and str(explicit)!=metadata['groups_config_path']:
        raise RegistrationUnavailable('group_binding_mismatch')
    if args is not None:
        try:
            with load_registration_context(Path(metadata['groups_config_path']),args.connections,args.config,args.executor_config,journal) as context:
                group=context.policy
                if group['installation_id']!=metadata['installation_id']:raise RegistrationUnavailable('group_binding_mismatch')
                if group['policy_sha256']!=metadata['current_policy_sha256'] or group['authorization_sha256']!=metadata['current_authorization_sha256']:
                    raise RegistrationUnavailable('group_policy_revoked')
                with journal._db(False,initialize=False) as db:
                    saved=db.execute('SELECT capacity_sha256 FROM group_capacity_epochs WHERE epoch=?',(metadata['current_capacity_epoch'],)).fetchone()
                    if saved is None or group['capacity_sha256']!=saved[0]:raise RegistrationUnavailable('group_policy_revoked')
        except (RegistrationUnavailable,RegistrationRecoveryRequired):raise
        except (ValueError,OSError,KeyError,TypeError):
            # Recheck J first so source revocation never masks loss/replacement of J.
            journal.registered_groups()
            raise RegistrationUnavailable('group_policy_revoked') from None
    raise RegistrationUnavailable('group_runtime_unavailable')
