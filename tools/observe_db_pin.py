"""Native POSIX diagnostics only; fresh local fixtures, no product source edits.

No-anchor cases stop at observed inode reuse, at most --cases (default20).
Then at most --cases held-read-only-fd comparisons run. This is NOT release CI.
All journals, snapshots and actual contained-runner logs remain in --output.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import uuid
from unittest.mock import patch


parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=Path.cwd())
parser.add_argument('--output',type=Path)
parser.add_argument('--cases',type=int,default=20)
args=parser.parse_args()
if not 1<=args.cases<=20:parser.error('--cases must be1..20')
if os.name!='posix':
    print(json.dumps(dict(status='not_run_non_posix',platform=os.name)),flush=True)
    raise SystemExit(0)
repo=args.repo.resolve();sys.path.insert(0,str(repo))
from task_tower import pipeline
from task_tower.pipeline_journal import PipelineJournal,SCHEMAS
from tests.test_pipeline_journal import request,policy

output=args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='task-tower-db-pin-')).resolve()
output.mkdir(parents=True,exist_ok=True)
if any(output.iterdir()):raise RuntimeError('Diagnostic output must be a fresh empty directory')
env=dict(os.environ,PYTHONPATH=str(repo)+os.pathsep+os.environ.get('PYTHONPATH',''))


def dump(path,value):path.write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf-8')
def identity(info):return dict(dev=info.st_dev,ino=info.st_ino,nlink=info.st_nlink,mode=info.st_mode)
def chain(error):
    rows=[];seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error));rows.append(dict(type=type(error).__name__,message=str(error),errno=getattr(error,'errno',None),sqlite_errorcode=getattr(error,'sqlite_errorcode',None),sqlite_errorname=getattr(error,'sqlite_errorname',None)))
        error=error.__cause__ or error.__context__
    return rows
def context_snapshot(journal):
    return dict(rows=journal.status()['runs'],controller=journal.controller_health())


def hot_fixture(directory,controller=False):
    directory.mkdir();journal=PipelineJournal(directory/'state.db')
    for number in range(1,81):journal.submit(request(number),policy())
    owner=str(uuid.uuid4());controller_owner=str(uuid.uuid4()) if controller else None
    if controller_owner:journal.claim_controller(controller_owner,'b'*64)
    saved=directory/'before-crash.json'
    code="""import json,os,sqlite3,sys
from pathlib import Path
from task_tower.pipeline_journal import PipelineJournal
j=PipelineJournal(Path(sys.argv[1]))
with j.owner(sys.argv[2]):
 row=j.claim(sys.argv[2],2)
 Path(sys.argv[3]).write_text(json.dumps(dict(claimed=row,rows=j.status()['runs'],history=j.history(row['run_id']),controller=j.controller_health())))
 db=sqlite3.connect(sys.argv[1]);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=1');db.execute('PRAGMA cache_spill=ON');db.execute('BEGIN IMMEDIATE');db.execute('UPDATE runs SET policy_sha256=?',('c'*64,));os._exit(23)
"""
    capture=directory/'crash-streams';capture.mkdir()
    outcome=pipeline.processes.run_command([sys.executable,'-c',code,str(journal.path),owner,str(saved)],directory,20,env=env,cancel_requested=lambda:False,capture=dict(directory=capture,max_bytes_per_stream=65536))
    if outcome.get('exit_code')!=23 or outcome.get('cleanup_confirmed') is not True:raise RuntimeError('Actual contained crash did not complete: '+json.dumps(outcome))
    before=json.loads(saved.read_text());assert before['claimed']['owner_pid']==outcome['pid']
    raw=directory/'crashed-bytes';raw.mkdir()
    for path in (journal.path,Path(str(journal.path)+'-journal')):shutil.copy2(path,raw/path.name)
    try:journal.status()
    except ValueError as error:
        errors=chain(error)
        if not any(row['sqlite_errorcode']==sqlite3.SQLITE_READONLY_ROLLBACK for row in errors):raise
    else:raise AssertionError('Actual SQLite spill did not leave a hot journal')
    done=threading.Event();done.set()
    host=SimpleNamespace(owner=owner,done=done,outcome=outcome,close=lambda:None)
    state=dict(owner=controller_owner,stop=threading.Event(),workers=[host],dispatcher=None,ticks=0,failures=0)
    return journal,state,before,outcome


def pin(path):
    # Existing file only; no SQLite connection, creation, recovery or WAL action.
    return os.open(path,os.O_RDONLY|os.O_NOFOLLOW|getattr(os,'O_CLOEXEC',0))


def replacement_case(number,anchored):
    directory=output/(('anchor-' if anchored else 'no-anchor-')+str(number))
    journal,state,before,outcome=hot_fixture(directory)
    replacement=directory/'replacement.db'
    replacement_journal=PipelineJournal(replacement);replacement_journal.submit(request(999),policy())
    expected_replacement=context_snapshot(replacement_journal)
    events=[];fd=None;result={}
    try:
        if anchored:
            before_bytes={p:p.read_bytes() for p in (journal.path,Path(str(journal.path)+'-journal'))}
            fd=pin(journal.path)
            assert os.path.samestat(os.fstat(fd),journal.path.stat())
            assert before_bytes=={p:p.read_bytes() for p in before_bytes}
            events.append(dict(kind='os_readonly_pin_before_actual_shutdown',fd=identity(os.fstat(fd))))
        original=PipelineJournal._recover_existing
        def replace_after_real_recovery(target):
            recovered=original(target)
            old=target.path.stat();held_before=identity(os.fstat(fd)) if fd is not None else None
            target.path.unlink();shutil.copy2(replacement,target.path)
            new=target.path.stat();held_after=identity(os.fstat(fd)) if fd is not None else None
            event=dict(kind='actual_unlink_copy_after_real_recovery',before_unlink=identity(old),after_copy=identity(new),fd_before=held_before,fd_after=held_after,reused_dev_ino=os.path.samestat(old,new))
            events.append(event);print(json.dumps(dict(case=number,anchored=anchored,**event)),flush=True)
            return recovered
        started=time.monotonic()
        with patch.object(PipelineJournal,'_recover_existing',replace_after_real_recovery):confirmed=pipeline._shutdown({},journal,state,cancel_runs=True)
        result=dict(case=number,anchored=anchored,confirmed=confirmed,duration=time.monotonic()-started,events=events,actual_runner=outcome,before_claimed=before['claimed'],after=context_snapshot(journal),replacement_unchanged=context_snapshot(journal)==expected_replacement)
        assert state['_shutdown_journal_done'].is_set()
        assert len([e for e in events if e['kind']=='actual_unlink_copy_after_real_recovery'])==1
        if anchored:
            assert confirmed is False,'Pinned original inode was incorrectly accepted as replaced pathname'
            assert result['replacement_unchanged'],'Diagnostic performed logical mutations on the replacement'
    except BaseException as error:
        result=dict(case=number,anchored=anchored,error=chain(error),events=events)
        dump(directory/'result.json',result);raise
    finally:
        if fd is not None:os.close(fd)
    dump(directory/'result.json',result)
    print(json.dumps(dict(case=number,anchored=anchored,confirmed=result['confirmed'],duration=result['duration'])),flush=True)
    return result


def commit_case(anchored):
    directory=output/('commit-anchor' if anchored else 'commit-no-anchor')
    journal,state,before,outcome=hot_fixture(directory,controller=True)
    original=PipelineJournal._assert_existing;events=[];fd=pin(journal.path) if anchored else None
    def unlink_before_real_commit(target):
        db=sys._getframe(1).f_locals.get('db')
        if db is not None and db.in_transaction:
            old=target.path.stat();target.path.unlink();events.append(dict(kind='actual_precommit_unlink',before=identity(old),fd=identity(os.fstat(fd)) if fd is not None else None))
        return original(target)
    try:
        started=time.monotonic()
        with patch.object(PipelineJournal,'_assert_existing',unlink_before_real_commit):confirmed=pipeline._shutdown({},journal,state,cancel_runs=True)
        assert confirmed is False
        assert state['_shutdown_journal_done'].is_set()
        exists=journal.path.exists();restored=None
        if exists:
            restored=dict(rows=journal.status()['runs']==before['rows'],claimed=journal.status(before['claimed']['run_id'])==before['claimed'],history=journal.history(before['claimed']['run_id'])==before['history'],controller=journal.controller_health()==before['controller'])
            assert all(restored.values())
            with contextlib.closing(sqlite3.connect(journal.path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                assert db.execute('PRAGMA application_id').fetchone()[0]==1414808656
                schemas={row[0]:row[1] for row in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")}
                assert schemas==SCHEMAS
            assert journal.claim(str(uuid.uuid4()),2) is None
            assert journal.history(before['claimed']['run_id'])==before['history']
        result=dict(anchored=anchored,confirmed=confirmed,duration=time.monotonic()-started,physical_outcome='restored_exact_original' if exists else 'absent_no_creation',restored_checks=restored,events=events,actual_runner=outcome)
        dump(directory/'result.json',result);print(json.dumps(dict(commit_boundary=True,**result)),flush=True)
        return result
    finally:
        if fd is not None:os.close(fd)


summary=dict(platform=sys.platform,python=sys.executable,sqlite=sqlite3.sqlite_version,output=str(output),no_anchor=[],anchored=[],commit=[])
try:
    observed=False
    for number in range(args.cases):
        row=replacement_case(number,False);summary['no_anchor'].append(row)
        mutation=next(e for e in row['events'] if e['kind']=='actual_unlink_copy_after_real_recovery')
        if mutation['reused_dev_ino']:
            observed=True;break
    summary['native_inode_reuse_observed']=observed
    summary['causal_status']='native_reuse_captured' if observed else 'not_proven_no_reuse_within_bound'
    for number in range(args.cases):summary['anchored'].append(replacement_case(number,True))
    summary['commit']=[commit_case(False),commit_case(True)]
    summary['status']='diagnostic_completed_not_release_qualification'
except BaseException as error:
    summary['status']='diagnostic_failed';summary['error']=chain(error)
    dump(output/'summary.json',summary);raise
dump(output/'summary.json',summary)
manifest={str(path.relative_to(output)):hashlib.sha256(path.read_bytes()).hexdigest() for path in output.rglob('*') if path.is_file()}
dump(output/'manifest.json',manifest)
print(json.dumps(dict(status=summary['status'],causal_status=summary['causal_status'],no_anchor_cases=len(summary['no_anchor']),anchored_cases=len(summary['anchored']),output=str(output))),flush=True)
