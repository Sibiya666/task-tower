"""Semantic future-worktree declarations contain no physical identities."""
from pathlib import Path,PurePosixPath

TEMPLATE_PATH='{runs_root}/{run_id}/{attempt_id}/worktree'
CANDIDATES=('.agents','.claude','.opencode','AGENTS.md','opencode.json','opencode.jsonc')


def _relative(value,*,parent=False):
    from .opencode_adapter import _component
    if parent and value=='.':return PurePosixPath('.')
    if not isinstance(value,str) or not value or '\\' in value or value.startswith('/') or value.endswith('/'):
        raise ValueError('invalid_template_path')
    parts=value.split('/')
    if len(parts)>16:raise ValueError('template_depth_limit')
    for part in parts:_component(part)
    return PurePosixPath(value)


def validate_template(value,scope):
    from .opencode_adapter import _keys,_name,_sha,_component
    _keys(value,{'kind','version','path','role','source_sha','entries','ancestor_missing'})
    if (value['kind']!='worktree_template' or type(value['version']) is not int or value['version']!=1
            or value['path']!=TEMPLATE_PATH or value['path']!=scope['worktree_template']
            or value['role']!='launch_worktree' or value['source_sha']!=scope['source_sha']
            or value['ancestor_missing']!=list(CANDIDATES)):
        raise ValueError('invalid_worktree_template')
    entries=value['entries']
    if not isinstance(entries,list) or len(entries)>4096:raise ValueError('invalid_template_entries')
    seen=set();total=0
    for row in entries:
        if not isinstance(row,dict):raise ValueError('invalid_template_entry')
        path=_relative(row.get('path'));key=str(path).casefold()
        if key in seen:raise ValueError('template_path_collision')
        seen.add(key);_name(row.get('role'));kind=row.get('kind')
        if kind=='file':
            _keys(row,{'kind','path','role','bytes','sha256'});_sha(row['sha256'])
            if type(row['bytes']) is not int or not 0<=row['bytes']<=1048576:raise ValueError('invalid_template_file')
            total+=row['bytes']
        elif kind=='directory':
            _keys(row,{'kind','path','role','members'})
            members=row['members']
            if not isinstance(members,list) or len(members)>256:raise ValueError('invalid_template_members')
            names=[]
            for member in members:
                _keys(member,{'name','kind'});_component(member['name'])
                if member['kind'] not in ('file','directory'):raise ValueError('invalid_template_member')
                names.append(member['name'])
            if names!=sorted(names) or len({name.casefold() for name in names})!=len(names):raise ValueError('invalid_template_members')
        elif kind=='missing':
            _keys(row,{'kind','path','role','parent_path','missing_components'})
            parent=_relative(row['parent_path'],parent=True);parts=row['missing_components']
            if not isinstance(parts,list) or not parts or len(parts)>16:raise ValueError('invalid_template_missing')
            for part in parts:_component(part)
            if parent.joinpath(*parts)!=path:raise ValueError('invalid_template_missing')
        else:raise ValueError('invalid_template_kind')
    if total>8388608:raise ValueError('template_byte_limit')
    return len(entries),total


def validate_anchors(inventory,scope):
    root=Path(scope['runs_root']);anchors={}
    for row in inventory:
        if row['kind']=='worktree_template':continue
        path=Path(row['path'])
        if not path.is_relative_to(root):continue
        if row['kind']!='missing' or path.parent!=root or path.name not in CANDIDATES:
            raise ValueError('invalid_output_root_inventory')
        parent=row['parent_identity']
        if parent['path']!=str(root) or parent['missing_components']!=[path.name]:
            raise ValueError('invalid_output_root_anchor')
        anchors[path.name]=parent['identity']
    if set(anchors)!=set(CANDIDATES) or len({tuple(value[key] for key in ('device','file_id','kind','reparse')) for value in anchors.values()})!=1:
        raise ValueError('missing_output_root_anchors')
    return anchors[CANDIDATES[0]]


def _ordered(rows):return sorted(rows,key=lambda row:row['path'].casefold())


def relative_observation(row,worktree):
    """Project only semantic comparison data; never mutate the physical record."""
    path=Path(row['path']).relative_to(worktree).as_posix()
    if not path or path=='.':raise ValueError('invalid_worktree_observation')
    value=dict(kind=row['kind'],path=path,role=row['role'])
    if row['kind']=='file':value.update(bytes=row['bytes'],sha256=row['sha256'])
    elif row['kind']=='directory':value['members']=[dict(name=m['name'],kind=m['kind']) for m in row['members']]
    elif row['kind']=='missing':
        parent=Path(row['parent_identity']['path']).relative_to(worktree).as_posix()
        value.update(parent_path=parent,missing_components=list(row['parent_identity']['missing_components']))
    else:raise ValueError('invalid_worktree_observation')
    return value


def inventory_matches(expected,observed,scope):
    import uuid
    from .opencode_files import validate_identity
    templates=[row for row in expected if row['kind']=='worktree_template']
    if len(templates)!=1:raise ValueError('exactly_one_template_required')
    declaration=templates[0];validate_template(declaration,scope);validate_anchors(expected,scope)
    tree=Path(observed['worktree']);root=Path(scope['runs_root']);parts=tree.relative_to(root).parts
    if len(parts)!=3 or parts[-1]!='worktree' or any(str(uuid.UUID(value))!=value for value in parts[:2]):
        raise ValueError('invalid_worktree_binding')
    generated={tree.parent:{},tree.parent.parent:{}}
    semantics=[];external=[]
    for row in observed['inventory']:
        path=Path(row['path'])
        if path.is_relative_to(tree):semantics.append(relative_observation(row,tree))
        elif path.parent in generated and path.name in CANDIDATES:
            if row['kind']!='missing':return False
            parent=row['parent_identity'];validate_identity(parent['identity'],kind='directory')
            if parent['path']!=str(path.parent) or parent['missing_components']!=[path.name]:return False
            generated[path.parent][path.name]=parent['identity']
        else:external.append(row)
    for rows in generated.values():
        if set(rows)!=set(CANDIDATES) or len({tuple(value[key] for key in ('device','file_id','kind','reparse')) for value in rows.values()})!=1:return False
    return (_ordered(semantics)==_ordered(declaration['entries']) and
            _ordered(external)==_ordered([row for row in expected if row['kind']!='worktree_template']))


def file_grants(inventory,scope,worktree):
    """Called only after installed pins/source validate; actual IDs are fresh."""
    from .opencode_files import safe_path,identity,forbidden_state_path
    template=next(row for row in inventory if row['kind']=='worktree_template')
    validate_template(template,scope)
    result={}
    for row in inventory:
        if row['kind']=='file':
            if forbidden_state_path(row['path']):raise ValueError('unsupported_credential_dependent_discovery')
            result[row['path']]=dict(row)
    for row in template['entries']:
        if row['kind']!='file':continue
        relative=_relative(row['path'])
        eligible=(str(relative)=='AGENTS.md' and row['role']=='instruction' or
                  str(relative) in ('opencode.json','opencode.jsonc') and row['role']=='project_config' or
                  str(relative) in ('.opencode/opencode.json','.opencode/opencode.jsonc') and row['role']=='config_json')
        path=safe_path(str(Path(worktree).joinpath(*relative.parts)))
        if forbidden_state_path(path):raise ValueError('unsupported_credential_dependent_discovery')
        if not eligible:raise ValueError('unsupported_template_file')
        info=path.lstat();actual=identity(info)
        if actual['kind']!='file' or info.st_nlink!=1:raise ValueError('unsafe_template_file')
        result[str(path)]=dict(kind='file',path=str(path),role=row['role'],bytes=row['bytes'],sha256=row['sha256'],identity=actual)
    return result
