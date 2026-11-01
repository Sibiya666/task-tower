"""Trusted subprocess fixture; intentionally has the host user's OS access."""
import argparse
import json
import os
from pathlib import Path
import sys

parser=argparse.ArgumentParser(); parser.add_argument('--request'); parser.add_argument('--result')
args=parser.parse_args(); request=json.loads(Path(args.request).read_text(encoding='utf-8'))
data=request.get('task_data',{}); mode=data.get('fixture_mode','complete')
if request['role']=='test_reviewer' and not request.get('host_checks'): sys.exit(10)
if any(key.upper() in ('GH_TOKEN','GITHUB_TOKEN') for key in os.environ): sys.exit(9)
if mode in ('mutation','mutation_fail'): (Path(request['worktree'])/request.get('host_task_policy',{}).get('spec_path','docs/spec.md')).write_text('mutated',encoding='utf-8')
if mode=='tamper_request': Path(args.request).write_bytes(b'{}')
if mode=='tamper_authority':
    request.setdefault('host_task_policy',{})['allowed_paths']=['*']
    Path(args.request).write_text(json.dumps(request),encoding='utf-8')
if mode=='log': print('x'*10000); print('e'*10000,file=sys.stderr)
if mode=='no_result': sys.exit(0)
value=dict(version=2,**request['binding'],summary='fixture')
if request['role'].endswith('_reviewer'): value.update(verdict='approve',return_stage=None,findings=[])
else: value['status']='completed'
if mode=='wrong_instance': value['instance_id']='00000000-0000-0000-0000-000000000000'
Path(args.result).write_text(json.dumps(value),encoding='utf-8')
sys.exit(2 if mode in ('exit_failure','mutation_fail') else 0)
