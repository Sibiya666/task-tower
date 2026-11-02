"""Explicit immutable artifact declarations; never task completion evidence."""
import json
import re
from urllib.parse import quote

from .book_projection import ISSUE


def markdown_path(path):
    if not isinstance(path,str):return False
    try:path.encode('utf-8')
    except UnicodeError:return False
    return (isinstance(path,str) and path.lower().endswith('.md') and '\\' not in path
            and not any(ord(c)<32 or 127<=ord(c)<=159 for c in path)
            and all(part not in ('','.','..') for part in path.split('/'))
            and ':' not in path)


def project_library(connection, store, *, connected_repositories=None):
    repository=connection.repository; root='https://github.com/'+repository
    errors=[]; entries={}
    def error(message): errors.append(dict(project=connection.id,source=root,error=message))
    def entry(path,commit,state='unknown',declaration=None,issues=None,milestone=None,available=True):
        # A literal percent triplet could acquire structural meaning after a
        # second URL decode. Keep its artifact visible without a launch URL.
        source=None if re.search(r'%[0-9a-fA-F]{2}',path) else root+'/blob/'+commit+'/'+quote(path,safe='/')
        if source is None: error('Markdown filename source unavailable')
        return dict(id=f'{repository}:{path}@{commit}',project=connection.id,repository=repository,
                    book='library',title=path,path=path,commit=commit,source=source,
                    status='source',artifact_state=state,declaration_source=declaration,
                    issues=issues or [],milestone=milestone,available=available and source is not None)
    try:
        tree=store.library()
        for row in tree:
            path=row.get('path'); commit=row.get('commit')
            if not markdown_path(path) or not isinstance(commit,str) or not re.fullmatch('[0-9a-f]{40}',commit):
                error('Library entry unavailable or invalid');continue
            value=entry(path,commit); entries[value['id']]=value
        if getattr(store,'library_invalid_paths',0):error('Library Markdown paths unavailable')
    except Exception:
        error('Library unavailable or incomplete'); return list(entries.values()),errors
    commit=getattr(store,'library_commit',None) or (tree[0]['commit'] if tree else None)
    if commit is None: return list(entries.values()),errors
    allowed={repository} if connected_repositories is None else set(connected_repositories)
    try:
        index=store.library_index(commit)
        if index is None: return list(entries.values()),errors
        if len(json.dumps(index,ensure_ascii=False).encode('utf-8'))>262144: raise ValueError()
        if not isinstance(index,dict) or set(index)!={'version','artifacts'} or type(index['version']) is not int or index['version']!=1: raise ValueError()
        artifacts=index['artifacts']
        if not isinstance(artifacts,list) or len(artifacts)>1000: raise ValueError()
        declarations={}
        for row in artifacts:
            if not isinstance(row,dict) or set(row)-{'path','commit','state','issues','milestone'} or not {'path','commit','state'}<=set(row): raise ValueError()
            path=row['path']; sha=row['commit']; state=row['state']
            if not markdown_path(path) or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{40}',sha) or state not in ('working','accepted','superseded'): raise ValueError()
            issues=row.get('issues',[]); milestone=row.get('milestone')
            if not isinstance(issues,list) or len(issues)>1000 or any(not isinstance(i,str) or not ISSUE.fullmatch(i) or i.rsplit('#',1)[0] not in allowed for i in issues): raise ValueError()
            if milestone is not None and (not isinstance(milestone,dict) or set(milestone)!={'repository','number'} or milestone['repository'] not in allowed or type(milestone['number']) is not int or milestone['number']<1): raise ValueError()
            value=entry(path,sha,state,root+'/blob/'+commit+'/docs/task-tower-library.json',issues,milestone)
            if value['id'] in declarations and declarations[value['id']]!=value: raise ValueError()
            declarations[value['id']]=value
    except Exception:
        error('Library index unavailable or invalid'); return list(entries.values()),errors
    for identity,value in declarations.items():
        try: available=store.markdown_exists(value['commit'],value['path']) is True
        except Exception: available=False
        value['available']=available and value['source'] is not None
        if not available: error('Declared Markdown version unavailable')
        entries[identity]=value
    return list(entries.values()),errors
