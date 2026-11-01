"""Project-first connection setup. No credentials or remote errors are persisted."""
import argparse
import json
from pathlib import Path
import re
import sys

from .github_source import MAX_BYTES, MAX_PAGES, resolve_token
from .github_tasks import _transport
from .project_connections import ProjectConnection, connection_snapshot, write_connections
from .creation_journal import CreationJournal

STATES = ('open', 'in_progress', 'awaiting_merge', 'awaiting_postmerge',
          'postmerge_review', 'postmerge_failed', 'needs_input', 'done')
ALIASES = {'open': ('open', 'todo'), 'in_progress': ('in progress', 'in_progress'), 'done': ('done',)}
HELP = 'GitHub project setup unavailable; install gh, run gh auth login, then gh auth refresh -s project with human authorization and rerun setup'


class OnboardingError(ValueError):
    pass


DETAILS = '''id title url viewerCanUpdate owner{... on User{id login} ... on Organization{id login}}
repositories(first:100){nodes{id} pageInfo{hasNextPage}}
fields(first:100){nodes{... on ProjectV2Field{id name dataType} ... on ProjectV2SingleSelectField{id name dataType options{id name color description}}} pageInfo{hasNextPage}}'''


class ProjectAPI:
    def __init__(self, *, token=None, transport=None, headers=None):
        self.transport = transport or _transport
        self.headers = headers or {'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'Task-Tower'}
        if headers is None:
            token = token if token is not None else (resolve_token() if transport is None else None)
            if token: self.headers['Authorization'] = 'Bearer '+token

    def query(self, query, variables):
        try:
            raw = self.transport('POST','https://api.github.com/graphql',dict(self.headers),dict(query=query,variables=variables),MAX_BYTES)
            if not isinstance(raw,bytes) or len(raw)>MAX_BYTES: raise ValueError()
            value=json.loads(raw)
            if not isinstance(value,dict) or value.get('errors') or not isinstance(value.get('data'),dict): raise ValueError()
            return value['data']
        except Exception:
            raise OnboardingError(HELP) from None

    def identity(self, repository):
        owner,name=repository.split('/')
        data=self.query('query RepositoryIdentity($owner:String!,$name:String!){repository(owner:$owner,name:$name){id nameWithOwner viewerPermission owner{id login __typename}}}',dict(owner=owner,name=name))
        try:
            repo=data['repository']
            if repo['viewerPermission'] not in ('ADMIN','MAINTAIN','WRITE') or repo['nameWithOwner'].casefold()!=repository.casefold() or repo['owner']['__typename'] not in ('User','Organization'): raise ValueError()
            for value in (repo['id'],repo['owner']['id']): node_id(value)
            return repo
        except (KeyError,TypeError,ValueError): raise OnboardingError(HELP) from None

    def projects(self, node, owner=False):
        rows=[]; cursor=None; seen=set()
        kind='OwnerProjects' if owner else 'LinkedProjects'
        fragment='... on User{projectsV2(first:100,after:$cursor){nodes{'+DETAILS+'} pageInfo{hasNextPage endCursor}}} ... on Organization{projectsV2(first:100,after:$cursor){nodes{'+DETAILS+'} pageInfo{hasNextPage endCursor}}}' if owner else '... on Repository{projectsV2(first:100,after:$cursor){nodes{'+DETAILS+'} pageInfo{hasNextPage endCursor}}}'
        for _ in range(MAX_PAGES):
            data=self.query('query '+kind+'($id:ID!,$cursor:String){node(id:$id){'+fragment+'}}',dict(id=node,cursor=cursor))
            try:
                page=data['node']['projectsV2']; items=page['nodes']; info=page['pageInfo']
                if not isinstance(items,list) or any(not isinstance(item,dict) for item in items): raise ValueError()
                rows.extend(items)
                if info['hasNextPage'] is False: return rows
                cursor=info['endCursor']
                if not isinstance(cursor,str) or not cursor or cursor in seen: raise ValueError()
                seen.add(cursor)
            except (KeyError,TypeError,ValueError): raise OnboardingError('Incomplete GitHub project discovery; select a Project after repairing access') from None
        raise OnboardingError('GitHub project discovery page limit reached; setup stopped')

    def details(self, identity):
        try:
            project=self.query('query ProjectDetails($id:ID!){node(id:$id){... on ProjectV2{'+DETAILS+'}}}',dict(id=node_id(identity)))['node']
            if not isinstance(project,dict) or project['id']!=identity: raise ValueError()
            return project
        except (KeyError,TypeError,ValueError): raise OnboardingError(HELP) from None


def node_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value): raise OnboardingError('Invalid GitHub project identity')
    return value


def validate_project(project, repo, *, linked=True):
    try:
        node_id(project['id'])
        url=project['url']
        owner=repo['owner']
        kind='users' if owner['__typename']=='User' else 'orgs'
        if not re.fullmatch(r'https://github\.com/'+kind+'/'+re.escape(owner['login'])+r'/projects/[1-9][0-9]*',url,re.I): raise ValueError()
        if project['owner']['id']!=owner['id'] or project['viewerCanUpdate'] is not True: raise ValueError()
        repositories=project['repositories']
        if repositories['pageInfo']['hasNextPage'] is not False: raise ValueError()
        if linked and repo['id'] not in [row['id'] for row in repositories['nodes']]: raise ValueError()
    except (KeyError,TypeError,ValueError): raise OnboardingError('GitHub project owner, repository linkage or write access does not match; select a writable linked Project') from None
    return project


def status_mapping(project, existing=None):
    try:
        fields=project['fields']
        if fields['pageInfo']['hasNextPage'] is not False: raise ValueError()
        configured=existing and existing['status_field_id']
        matches=[f for f in fields['nodes'] if f.get('id')==configured] if configured else [f for f in fields['nodes'] if f.get('name','').casefold()=='status']
        if len(matches)!=1 or matches[0].get('dataType')!='SINGLE_SELECT': raise ValueError()
        field=matches[0]; node_id(field['id']); options=field['options']
        if not isinstance(options,list) or any(not isinstance(o,dict) for o in options): raise ValueError()
        by_id={o['id']:o for o in options}
        if len(by_id)!=len(options): raise ValueError()
        mapping=dict(existing['status_options']) if existing else {}
        if any(option not in by_id for option in mapping.values()): raise ValueError()
        for state in STATES:
            prior=existing and existing['status_options'].get(state)
            candidates=[o for o in options if o['id']==prior] if prior else [o for o in options if o['name'].casefold() in ALIASES.get(state,(state,))]
            if len(candidates)>1 or (prior and not candidates): raise ValueError()
            if candidates: mapping[state]=node_id(candidates[0]['id'])
        return field,mapping
    except (KeyError,TypeError,ValueError): raise OnboardingError('GitHub project Status field/options are incompatible or ambiguous; preserve existing settings and repair the field') from None


def ensure_project_connection(config_path, connection_id, repository, checkout, runner_label, project_url=None, *, token=None, transport=None):
    """Onboard once; repeat setup reconciles existing resources without deleting data."""
    candidate=ProjectConnection(connection_id,repository,Path(checkout).resolve(),runner_label,project_url)
    try: before,connections=connection_snapshot(config_path)
    except (OSError,ValueError): raise OnboardingError('Invalid or unsafe private connections configuration; existing configuration preserved') from None
    old=next((c for c in connections if c.id.casefold()==connection_id.casefold()),None)
    if old and old.repository.casefold()!=repository.casefold(): raise OnboardingError('Connection ID already belongs to another repository')
    if any(c.repository.casefold()==repository.casefold() and c is not old for c in connections): raise OnboardingError('Repository already belongs to another connection ID')
    if old and project_url and old.project_url and old.project_url!=project_url: raise OnboardingError('Connection already selects another Project; explicit config repair required')
    api=ProjectAPI(token=token,transport=transport)
    repo=api.identity(repository)
    journal=CreationJournal(Path(config_path).with_name(Path(config_path).name+'.create-intents.sqlite3'))
    # The repository node survives renames and canonical spelling changes.
    project_key='repository-project'
    selected_url=project_url or (old.project_url if old else None)
    linked=api.projects(repo['id'])
    # Exhaust both collections before deciding uniqueness or absence.
    owned=api.projects(repo['owner']['id'],owner=True)
    if selected_url:
        matches=[p for p in {p['id']:p for p in linked+owned}.values() if p.get('url')==selected_url]
    else:
        matches=linked
        if not matches:
            title='Task Tower: '+repo['nameWithOwner']
            matches=[p for p in owned if p.get('title')==title and not p.get('repositories',{}).get('nodes')]
    if len(matches)>1: raise OnboardingError('Ambiguous GitHub projects; rerun with --project-url')
    if not matches:
        if selected_url: raise OnboardingError('Selected GitHub project is inaccessible or belongs to another owner')
        title='Task Tower: '+repo['nameWithOwner']
        if not journal.reserve('project',repo['id'],project_key):
            raise OnboardingError('GitHub project creation outcome uncertain or previously resolved resource unavailable; inspect owner Projects and rerun with --project-url. Preserve the private creation journal; no create retried')
        try:
            data=api.query('mutation CreateProject($owner:ID!,$title:String!,$repository:ID!){createProjectV2(input:{ownerId:$owner,title:$title,repositoryId:$repository}){projectV2{id}}}',dict(owner=repo['owner']['id'],title=title,repository=repo['id']))
            identity=node_id(data['createProjectV2']['projectV2']['id'])
            project=api.details(identity)
        except (OnboardingError,KeyError,TypeError):
            reconciled={p['id']:p for p in api.projects(repo['id'])+api.projects(repo['owner']['id'],owner=True) if p.get('title')==title and (not p.get('repositories',{}).get('nodes') or repo['id'] in [r.get('id') for r in p.get('repositories',{}).get('nodes',[])])}
            if len(reconciled)!=1: raise OnboardingError('GitHub project creation outcome uncertain; inspect owner Projects and rerun with --project-url; no create retried') from None
            project=next(iter(reconciled.values()))
    else: project=matches[0]
    validate_project(project,repo,linked=False)
    url=project['url']; identity=project['id']
    if old and old.board and old.board['project_id']!=identity: raise OnboardingError('Stored GitHub project node and selected URL disagree')
    try: journal.reconcile('project',repo['id'],project_key,identity)
    except ValueError:
        raise OnboardingError('Project retained at '+url+'; private creation journal could not reconcile. Preserve the journal, inspect its existing resource identity, and rerun with --project-url '+url) from None
    if repo['id'] not in [r['id'] for r in project['repositories']['nodes']]:
        try: api.query('mutation LinkProject($project:ID!,$repository:ID!){linkProjectV2ToRepository(input:{projectId:$project,repositoryId:$repository}){repository{id}}}',dict(project=identity,repository=repo['id']))
        except OnboardingError: pass
        project=api.details(identity)
    validate_project(project,repo)
    existing=old.board if old else None
    field,mapping=status_mapping(project,existing)
    if not set(STATES)<=mapping.keys():
        # GitHub retains IDs when existing option IDs are included. Verify the
        # authoritative result rather than trusting a mutation acknowledgement.
        options=[{k:o[k] for k in ('id','name','color','description') if k in o} for o in field['options']]
        options += [dict(name=state,color='GRAY',description='Task Tower '+state) for state in STATES if state not in mapping]
        try: api.query('mutation UpdateStatus($field:ID!,$options:[ProjectV2SingleSelectFieldOptionInput!]){updateProjectV2Field(input:{fieldId:$field,singleSelectOptions:$options}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}',dict(field=field['id'],options=options))
        except OnboardingError: pass
        refreshed=api.details(identity)
        newfield,mapping=status_mapping(refreshed,existing)
        actual={o['id']:o for o in newfield['options']}
        if any(actual.get(o['id'])!=o for o in field['options']) or not set(STATES)<=mapping.keys(): raise OnboardingError('Status update uncertain or existing options changed; inspect '+url+' and rerun; no update retried')
        field=newfield
    board=dict(project_id=identity,status_field_id=field['id'],status_options=mapping)
    connection=ProjectConnection(candidate.id,repo['nameWithOwner'],candidate.checkout,candidate.runner_label,url,board,old.trusted_publishers if old else [])
    updated=[connection if c is old else c for c in connections]
    if old is None: updated.append(connection)
    try: write_connections(config_path,updated,expected=before)
    except (OSError,ValueError): raise OnboardingError('Remote setup retained at '+url+'; private configuration changed or could not be saved. Rerun setup with --project-url '+url) from None
    return connection


def preflight(connection, store):
    if not connection.board or not connection.project_url: raise OnboardingError('GitHub project needs setup; run task_tower connect before importing Issues')
    api=ProjectAPI(transport=store.transport,headers=dict(store.headers))
    repo=api.identity(connection.repository)
    project=validate_project(api.details(connection.board['project_id']),repo)
    if project['url']!=connection.project_url: raise OnboardingError('GitHub project URL and node ID disagree')
    field,mapping=status_mapping(project,connection.board)
    if not set(STATES)<=mapping.keys(): raise OnboardingError('GitHub project status mapping incomplete; rerun connect')
    return repo


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('config','id','repository','checkout','runner-label'): parser.add_argument('--'+name,required=True)
    parser.add_argument('--project-url')
    args=parser.parse_args(argv)
    try:
        connection=ensure_project_connection(args.config,args.id,args.repository,args.checkout,args.runner_label,args.project_url)
        print(json.dumps(dict(status='ready',id=connection.id,repository=connection.repository,project_url=connection.project_url)))
        return 0
    except (ValueError,OSError):
        print('task-tower: '+str(sys.exc_info()[1]),file=sys.stderr)
        return 2
