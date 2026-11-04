"""Read-only local Beads projection for Books; never task execution authority."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time

from .project_connections import safe_config_path, REPOSITORY
from .processes import run_command

BEAD = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}"
PROJECT = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"
ROW_LIMIT, EVENT_LIMIT = 1000, 5000

def _json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('Duplicate key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique)

def load_config(path):
    path=safe_config_path(path)
    if path.stat().st_size>1048576: raise ValueError('Configuration limit')
    value=_json(path.read_text(encoding='utf-8'))
    if (not isinstance(value,dict) or set(value)!={'version','executable','projects'}
            or type(value['version']) is not int or value['version']!=1
            or not isinstance(value['projects'],list) or len(value['projects'])>16): raise ValueError('Invalid Beads config')
    if not Path(value['executable']).is_absolute(): raise ValueError('Absolute executable required')
    executable=safe_config_path(Path(value['executable']))
    if not executable.is_absolute() or not executable.is_file() or executable.suffix.lower()!='.exe': raise ValueError('Invalid executable')
    seen=set(); repos=set(); directories=set()
    for row in value['projects']:
        if (not isinstance(row,dict) or set(row)!={'id','repository','directory'}
                or not isinstance(row['id'],str) or not re.fullmatch(PROJECT,row['id'])
                or not isinstance(row['repository'],str) or not re.fullmatch(REPOSITORY,row['repository'])): raise ValueError('Invalid project')
        directory=Path(row['directory'])
        if not directory.is_absolute(): raise ValueError('Absolute directory required')
        safe_config_path(directory/'.beads/metadata.json')
        if not directory.is_absolute() or not directory.is_dir(): raise ValueError('Invalid directory')
        if row['id'] in seen or row['repository'].casefold() in repos or str(directory).casefold() in directories: raise ValueError('Duplicate project')
        seen.add(row['id']);repos.add(row['repository'].casefold());directories.add(str(directory).casefold())
    return value

def _text(value,limit=8192):
    if not isinstance(value,str): raise ValueError('Invalid source text')
    return value.encode('utf-8')[:limit].decode('utf-8',errors='ignore')

def project_rows(project,repository,rows,events):
    if not isinstance(rows,list) or len(rows)>ROW_LIMIT or not isinstance(events,list) or len(events)>EVENT_LIMIT: raise ValueError('Source limit')
    def identity(bead):
        if not isinstance(bead,str) or not re.fullmatch(BEAD,bead): raise ValueError('Invalid bead')
        return repository+':beads:'+project+':'+bead
    records={};result=[]
    for row in rows:
        if not isinstance(row,dict): raise ValueError('Invalid row')
        bead=row['id']; qualified=identity(bead)
        if bead in records: raise ValueError('Duplicate bead')
        state=_text(row['status'],64)
        if not re.fullmatch('[a-z][a-z0-9_]{0,63}',state): raise ValueError('Invalid state')
        entry=dict(id=qualified,repository=repository,project=project,book='tasks',source=None,
            source_kind='beads',bead_id=bead,title=_text(row['title']),status='closed' if state=='done' else state,
            remote_state=state,verification='not_required',description=_text(row.get('description',''),32768),
            assignee=_text(row.get('assignee',''),256),phase=_text(row.get('issue_type','task'),64),
            blockers=[],blocked_by=[],results=[],history=[],relationships=dict(parent=None,sub_issues=[],milestone=None))
        for key in ('created_at','updated_at'):
            if key in row: entry[key]=_text(row[key],128)
        records[bead]=entry;result.append(entry)
    for row in rows:
        entry=records[row['id']];parent=row.get('parent')
        if parent:
            entry['relationships']['parent']={'id':identity(parent)}
            if parent in records: records[parent]['relationships']['sub_issues'].append({'id':entry['id']})
        dependencies=row.get('dependencies',[])
        if not isinstance(dependencies,list) or len(dependencies)>100: raise ValueError('Dependency limit')
        for dep in dependencies:
            if not isinstance(dep,dict): raise ValueError('Invalid dependency')
            if dep.get('type')=='blocks': entry['blocked_by'].append(identity(dep['depends_on_id']))
    previous=0
    for event in events:
        if not isinstance(event,dict) or type(event.get('seq')) is not int or event['seq']<=previous: raise ValueError('Invalid event order')
        previous=event['seq']; bead=event.get('issue_id')
        if bead not in records: continue
        history=records[bead]['history']; state=event.get('issue',{}).get('status')
        item=dict(at=_text(event['ts'],128),actor=_text(event.get('actor',''),256),operation=_text(event['op'],64))
        if isinstance(state,str): item['status']=_text(state,64)
        history.append(item)
        if len(history)>100: raise ValueError('History limit')
    return result

def _read(executable,directory,args,remaining):
    directory=Path(directory)
    metadata=safe_config_path(directory/'.beads/metadata.json')
    if metadata.stat().st_size>65536: raise ValueError('Metadata limit')
    installed=_json(metadata.read_text(encoding='utf-8'))
    if installed.get('backend')!='dolt' or installed.get('dolt_mode')!='embedded': raise ValueError('Local embedded source required')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('BEADS_','BD_','DOLT_','GIT_')) and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
    env['BEADS_DIR']=str(directory/'.beads')
    with tempfile.TemporaryDirectory(prefix='task-tower-beads-') as cap:
        process=run_command([str(executable),*args],directory,max(.1,min(remaining,15)),env=env,capture=dict(directory=Path(cap),max_bytes_per_stream=8*1024*1024))
        if (process.get('status')!='passed' or process.get('exit_code')!=0 or process.get('cleanup_confirmed') is not True
                or any(process.get(s+'_truncated') or process.get(s+'_tail_unknown') for s in ('stdout','stderr'))): raise ValueError('Beads read unavailable')
        raw=(Path(cap)/'stdout.log').read_text(encoding='utf-8')
        if 'events' in args: return [_json(line) for line in raw.splitlines() if line.strip()]
        return _json(raw)

def read_projects(path,*,reader=None,on_update=None):
    reader=reader or _read;config=load_config(path);deadline=time.monotonic()+25
    report=dict(fetched_at=datetime.now(timezone.utc).isoformat(),entries=[],errors=[],repositories=[r['repository'].casefold() for r in config['projects']])
    for project in config['projects']:
        def error(message): report['errors'].append(dict(project=project['id'],source='',error=message))
        try:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise ValueError('Deadline')
            args=['--readonly','--sandbox','--json','list','--all','--limit',str(ROW_LIMIT+1)]
            rows=reader(config['executable'],project['directory'],args,remaining)
            entries=project_rows(project['id'],project['repository'],rows,[])
            report['entries'].extend(entries)
            if on_update: on_update(report)
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise ValueError('Deadline')
                setting=reader(config['executable'],project['directory'],['--readonly','--sandbox','--json','config','get','events-journal'],remaining)
                enabled=isinstance(setting,dict) and (setting.get('value') is True or setting.get('value')=='true')
                if not enabled:error('Beads chronology journal is disabled or unavailable')
                remaining=deadline-time.monotonic()
                if remaining<=0:raise ValueError('Deadline')
                events=reader(config['executable'],project['directory'],['--readonly','--sandbox','--json','events','export','--limit',str(EVENT_LIMIT+1)],remaining)
                updated=project_rows(project['id'],project['repository'],rows,events)
                for entry,new in zip(entries,updated): entry.update(new)
                sequences=[event['seq'] for event in events]
                created={event.get('issue_id') for event in events if event.get('op')=='create'}
                last={event.get('issue_id'):event.get('issue') for event in events}
                fields=('status','title','description','assignee','created_at','updated_at')
                current=all(isinstance(last.get(row['id']),dict) and
                    all((row.get(key) or '')==(last[row['id']].get(key) or '') for key in fields) for row in rows)
                if (sequences!=list(range(1,len(events)+1))
                        or any(row['id'] not in created for row in rows) or not current):
                    error('Beads chronology is partial; earlier changes are unavailable')
            except Exception: error('Beads chronology unavailable or limit exceeded')
        except Exception: error('Local Beads tasks unavailable or limit exceeded')
        if on_update: on_update(report)
    return report
