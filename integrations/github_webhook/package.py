"""Default-deny receiver staging. No secrets/config discovery or deployment effects."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
FILES={
    'integrations/github_webhook/receiver.py':'integrations/github_webhook/receiver.py',
    'integrations/github_webhook/inbox.py':'integrations/github_webhook/inbox.py',
    'integrations/github_webhook/api/index.py':'integrations/github_webhook/api/index.py',
    'schema.sql':'integrations/github_webhook/schema.sql',
    'requirements.txt':'integrations/github_webhook/requirements.txt',
    'pyproject.toml':'integrations/github_webhook/pyproject.toml',
    'vercel.json':'integrations/github_webhook/vercel.json',
}
ROUTES=('health','github/webhook','inbox/take','inbox/ack','inbox/replay')


def build(out,source_sha=None):
    out=Path(out).absolute()
    from task_tower.project_connections import safe_config_path
    safe_config_path(out/".stage-check")
    out.mkdir(exist_ok=False)
    hashes={}
    def write(name,raw):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        hashes[name]=hashlib.sha256(raw).hexdigest()
    for target,source in FILES.items():
        path=safe_config_path(ROOT/source)
        if not path.is_file() or path.stat().st_nlink!=1:raise ValueError('regular_package_source_required')
        write(target,path.read_bytes())
    for route in ROUTES:
        wrapper='from integrations.github_webhook.api.index import handler as BaseHandler\n\nclass handler(BaseHandler):\n    route = '+repr('/api/'+route)+'\n'
        write('api/'+route+'.py',wrapper.encode())
    receipt=dict(version=1,kind='receiver.package',source_sha=source_sha,source_state='committed' if source_sha else 'development',files=hashes)
    (out/'package-receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True);args=parser.parse_args(argv)
    from task_tower.child_environment import child_environment
    import os
    def git(*args):
        result=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'-c','core.hooksPath='+os.devnull,*args],cwd=ROOT,env=child_environment(os.environ),capture_output=True,timeout=10,check=True)
        return result.stdout.decode('utf-8').strip()
    if git('status','--porcelain','--untracked-files=all'):raise ValueError('clean_committed_package_source_required')
    receipt=build(args.out,git('rev-parse','HEAD'))
    print(json.dumps(dict(kind=receipt['kind'],source_sha=receipt['source_sha'],file_count=len(receipt['files']),accepted_delivery=False)))
    return 0

if __name__=='__main__':raise SystemExit(main())
