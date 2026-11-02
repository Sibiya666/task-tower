"""Foreground executor admission, inspection and cancellation CLI."""
import argparse
import json
import os
import stat
from pathlib import Path
import sys
import tempfile
from .executor_profiles import load_executor_config, profile_fingerprint
from .executor_queue import ExecutionQueue, validate_request
from .project_connections import load_connections, safe_config_path


def adapter(request,config,queue,*,authority_check=None):
    r=validate_request(request)
    unknown=dict(version=1,delivery_id=r['delivery_id'],status='unknown')
    rows=[row for row in config['allowlist'] if row['repository'].casefold()==r['repository'] and all(row[k]==r[k] for k in ('issue','task_id','runner_label'))]
    if len(rows)!=1: return unknown
    row=rows[0]; profile=config['profiles'].get(row['profile'])
    if profile is None or (authority_check is not None and not authority_check()): return unknown
    try:
        if r['operation']=='submit': return queue.submit(r,profile_fingerprint(profile),profile_id=row['profile'])
        receipt=queue.lookup(r['delivery_id'])
        if receipt is None: return dict(version=1,delivery_id=r['delivery_id'],status='not_found')
        saved=queue.status(receipt['receipt_id'])
        if any(saved[k]!=r[k] for k in ('repository','issue','task_id','runner_label')) or saved['profile_id']!=row['profile'] or saved['profile_fingerprint']!=profile_fingerprint(profile): return unknown
        return receipt
    except (ValueError,OSError): return unknown


def _paths(paths,connections,*,transient_paths=()):
    def key(raw):
        try:value=os.fspath(raw)
        except TypeError:raise ValueError('Invalid executor private path') from None
        if not isinstance(value,str):raise ValueError('Invalid executor private path')
        return os.path.abspath(value).casefold()
    if not isinstance(transient_paths,(list,tuple,set,frozenset)):raise ValueError('Invalid executor transient paths')
    paths=list(paths);members={key(path) for path in paths}
    transient={key(path) for path in transient_paths}
    suffixes=('-journal','-wal','-shm')
    for path in transient:
        suffix=next((s for s in suffixes if path.endswith(s)),None)
        if path not in members or suffix is None or path[:-len(suffix)] not in members:raise ValueError('Invalid executor transient path')
    checked=[]
    for raw in paths:
        path=safe_config_path(raw)
        try:info=path.stat()
        except FileNotFoundError:
            if key(path) not in transient and path.exists():raise
            info=None
        if info is not None and info.st_nlink!=1:
            if info.st_nlink!=0 or key(path) not in transient or not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Unsafe executor private file')
            # A stat can finish after SQLite unlinks its rollback sidecar.
            # Recheck the current entry without following a replacement link.
            safe_config_path(path)
            try:current=path.lstat()
            except FileNotFoundError:current=None
            if current is not None and (not stat.S_ISREG(current.st_mode) or getattr(current,'st_file_attributes',0)&0x400 or current.st_nlink not in (0,1)):
                raise ValueError('Unsafe executor private file')
        if any(path.resolve().is_relative_to(c.checkout) for c in connections): raise ValueError('Executor private files must be outside checkouts')
        for other in checked:
            if str(path.resolve()).casefold()==str(other.resolve()).casefold():raise ValueError('Executor private file collision')
            try:same=path.exists() and other.exists() and os.path.samefile(path,other)
            except FileNotFoundError:
                if not any(key(p) in transient for p in (path,other)):raise
                same=False
            if same:raise ValueError('Executor private file collision')
        checked.append(path)
    return checked


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate executor JSON key')
        result[key]=value
    return result


def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary=tempfile.mkstemp(prefix='.executor-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        safe_config_path(path); os.replace(temporary,path)
    finally: Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Foreground authorized development executor')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('adapter','work','status','cancel','retry'):
        command=sub.add_parser(name)
        for option in ('connections','queue'): command.add_argument('--'+option,type=Path,required=True)
        if name in ('adapter','work','retry'): command.add_argument('--config',type=Path,required=True)
        if name=='adapter':
            command.add_argument('--request',type=Path,required=True); command.add_argument('--result',type=Path,required=True)
        if name=='work': command.add_argument('--once',action='store_true',required=True)
        if name in ('status','cancel','retry'): command.add_argument('--run-id',required=True)
    args=parser.parse_args(argv)
    try:
        safe_config_path(args.connections)
        before=args.connections.read_bytes(); connections=load_connections(args.connections)
        inputs=[args.connections]
        if args.command in ('adapter','work','retry'): inputs.append(args.config)
        if args.command=='adapter': inputs.extend((args.request,args.result))
        sidecars=[Path(str(args.queue)+s) for s in ('-journal','-wal','-shm')]
        _paths([*inputs,args.queue,*sidecars],connections,transient_paths=sidecars)
        queue=ExecutionQueue(args.queue,checkouts=[c.checkout for c in connections],forbidden_paths=inputs)
        if args.command in ('status','cancel'):
            report=queue.status(args.run_id)
            if not any(c.repository.casefold()==report['repository'] and c.runner_label==report['runner_label'] for c in connections): raise ValueError('Executor run disconnected')
            if args.connections.read_bytes()!=before: raise ValueError('Connections changed')
            if args.command=='cancel': queue.cancel(args.run_id); report=queue.status(args.run_id)
        else:
            policy=args.config.read_bytes(); config=load_executor_config(args.config,connections)
            def authority_check():
                try:
                    _paths([*inputs,args.queue],connections)
                    return args.connections.read_bytes()==before and args.config.read_bytes()==policy
                except (OSError,ValueError): return False
            if args.command=='adapter':
                if args.request.stat().st_size>65536: raise ValueError('Oversize executor request')
                request=json.loads(args.request.read_text(encoding='utf-8'),object_pairs_hook=_unique)
                report=adapter(request,config,queue,authority_check=authority_check)
                _paths([*inputs,args.queue],connections)
                _write(args.result,report)
                return 0
            from .executor_worker import execute_one
            config['_connections']=connections
            config['_authority_check']=authority_check
            if args.command=='retry':
                from .executor_worker import _authorized
                job=queue.status(args.run_id)
                profile=config['profiles'].get(job['profile_id'])
                if profile is None or not _authorized(config,job,profile): raise ValueError('Retry authority unavailable')
                queue.retry_prelaunch(args.run_id,profile_fingerprint=profile_fingerprint(profile),max_attempts=profile['max_attempts'])
                report=dict(run_id=args.run_id,status='queued')
            else:
                queue.recover()
                report=execute_one(config,queue)
        print(json.dumps(report,sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError):
        print('task-tower executor: invalid or unavailable private state',file=sys.stderr)
        return 2
