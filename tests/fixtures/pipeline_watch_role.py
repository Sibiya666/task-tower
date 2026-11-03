"""Trusted test program for parked blockers and live worker ownership."""
import argparse
import json
import os
from pathlib import Path
import runpy
import time

parser=argparse.ArgumentParser();parser.add_argument('--request');parser.add_argument('--result')
args=parser.parse_args();request=json.loads(Path(args.request).read_text(encoding='utf-8'))
if any(k.upper() in ('GH_TOKEN','GITHUB_TOKEN') for k in os.environ):raise SystemExit(9)
if request['task_data'].get('fixture_mode')=='sleep':
    Path(args.request).with_name('role-started').write_text(str(os.getpid()),encoding='utf-8')
    time.sleep(60)
runpy.run_path(str(Path(__file__).with_name('pipeline_role.py')),run_name='__main__')
