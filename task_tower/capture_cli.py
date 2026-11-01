"""Bounded explicit capture input; no ambient session discovery."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

from .capture import MAX_INPUT, capture, promote, validate_capture
from .capture_migration import migrate_card
from .project_connections import load_connections, safe_config_path


def _read_input(name,protected):
    if name=='-':
        stream=getattr(sys.stdin,'buffer',None)
        if stream is None: raise ValueError('Binary UTF-8 stdin required')
        raw=stream.read(MAX_INPUT+1)
    else:
        path=safe_config_path(name)
        for target in protected:
            target=Path(target)
            if path==target.absolute() or (target.exists() and path.exists() and os.path.samefile(path,target)):
                raise ValueError('Input aliases private state')
        before=path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1: raise ValueError('Unsafe capture input')
        with path.open('rb') as stream:
            opened=os.fstat(stream.fileno())
            if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino): raise ValueError('Capture input changed')
            raw=stream.read(MAX_INPUT+1)
            after=os.fstat(stream.fileno())
        current=path.stat()
        signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)
        if signature(before)!=signature(after) or signature(after)!=signature(current): raise ValueError('Capture input changed')
        safe_config_path(path)
    if len(raw)>MAX_INPUT: raise ValueError('Capture input exceeds limit')
    def pairs(values):
        result={}
        for key,value in values:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return validate_capture(json.loads(raw.decode('utf-8'),object_pairs_hook=pairs))


def run(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connections',type=Path,required=True)
    parser.add_argument('--project',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    submit=commands.add_parser('submit'); submit.add_argument('--input',required=True)
    promotion=commands.add_parser('promote'); promotion.add_argument('--issue',type=int,required=True)
    migration=commands.add_parser('migrate'); migration.add_argument('--card',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        connections=load_connections(args.connections)
        selected=next((c for c in connections if c.id==args.project),None)
        if selected is None: raise ValueError('Unknown project')
        if args.command=='submit':
            private=selected.checkout/'.task-tower'
            protected=[args.connections,private/'create-intents.sqlite3',private/'capture-migrations.json']
            value=_read_input(args.input,protected)
            result=capture(selected,value)
        elif args.command=='migrate':
            path=safe_config_path(args.card)
            config=safe_config_path(args.connections)
            if path==config or (path.exists() and config.exists() and os.path.samefile(path,config)):
                raise ValueError('Migration aliases connections')
            result=migrate_card(selected,path)
        else: result=promote(selected,args.issue)
        print(json.dumps(result,ensure_ascii=True))
        return 1 if result['status']=='needs_input' else 0
    except Exception:
        # Transport exceptions and supplied content must never become diagnostics.
        print('task-tower: capture request failed; inspect connection, input and existing event before retrying',file=sys.stderr)
        return 2
