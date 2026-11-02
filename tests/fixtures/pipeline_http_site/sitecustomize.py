"""Subprocess integration replaces HTTP transport only, never source classes."""
import json
import os
from pathlib import Path
import time
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit

if os.environ.get('TT_HTTP_FIXTURE'):
    import task_tower.github_tasks as tasks
    import task_tower.github_source as source
    def transport(method,url,headers,payload,limit):
        fixture=json.loads(Path(os.environ['TT_HTTP_FIXTURE']).read_text(encoding='utf-8'))
        slow=fixture.get('slow')
        if slow and fixture.get('slow_after_claim'):
            uri=Path(fixture['slow_after_claim']).resolve().as_uri()+'?mode=ro'
            with closing(sqlite3.connect(uri,uri=True,timeout=.2)) as db:
                slow=db.execute('SELECT 1 FROM runs WHERE owner_id IS NOT NULL AND owner_pid=?',(os.getpid(),)).fetchone() is not None
        if slow:
            Path(fixture['started']).write_text('started',encoding='utf-8')
            time.sleep(60)
        if fixture.get('unavailable'):raise OSError('fixture unavailable')
        if not headers.get('Authorization','').startswith('Bearer '):raise OSError('missing host auth')
        if os.environ.get('TT_HTTP_REQUIRE_ENV_AUTH')=='1':
            expected=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
            if not expected or headers.get('Authorization')!='Bearer '+expected:raise OSError('environment-only host auth unavailable')
        path=urlsplit(url).path
        if path.endswith('/pulls'):
            records=Path(fixture['prs'])
            rows=json.loads(records.read_text(encoding='utf-8')) if records.exists() else []
            if method=='POST':
                completed=original_run(['git','--git-dir='+fixture['remote'],'rev-parse','refs/heads/'+payload['head']],capture_output=True,check=True)
                head=completed.stdout.decode().strip()
                row=dict(number=7,html_url='https://github.com/owner/repo/pull/7',state='open',title=payload['title'],body=payload['body'],user=dict(login='owner'),head=dict(sha=head,ref=payload['head'],repo=dict(full_name='owner/repo')),base=dict(sha=fixture['sha'],ref=payload['base'],repo=dict(full_name='owner/repo')))
                rows.append(row);records.write_text(json.dumps(rows),encoding='utf-8')
                if fixture.get('lost_post'):raise OSError('Lost fixture response')
                return json.dumps(row).encode('utf-8')
            return json.dumps(rows).encode('utf-8')
        if method!='GET':raise AssertionError('Fixture forbids other writes')
        issues=fixture.get('issues_by_repository',{}).get(path.split('/')[3].casefold(),fixture['issues'])
        if path.endswith('/issues'):result=issues
        elif '/comments' in path:result=[]
        elif path.endswith('/git/ref/heads/main'):result=dict(object=dict(sha=fixture['sha']))
        elif '/issues/' in path:result=next(i for i in issues if str(i['number'])==path.rsplit('/',1)[-1])
        elif path.endswith('/actions/workflows/postmerge.yml/runs'):result=dict(workflow_runs=[])
        else:raise AssertionError('Unexpected HTTP fixture route')
        return json.dumps(result).encode('utf-8')
    tasks._transport=transport
    source._http_get=lambda url,headers,limit:transport('GET',url,headers,None,limit)
    # Transport-only Git fault: retain the actual publication intent/argv and
    # block inside a real descendant, exactly where a remote transport stalls.
    import subprocess
    import sys
    original_run=subprocess.run
    def git_transport(argv,*args,**kwargs):
        fixture=json.loads(Path(os.environ['TT_HTTP_FIXTURE']).read_text(encoding='utf-8'))
        network=isinstance(argv,list) and ('ls-remote' in argv or 'push' in argv)
        if network and fixture.get('block_git') and fixture.get('block_git_command','ls-remote') in argv:
            marker=fixture['git_started']
            return original_run([sys.executable,'-c',"import os,time;from pathlib import Path;Path("+repr(marker)+").write_text(str(os.getpid()));time.sleep(60)"],*args,**kwargs)
        if network and fixture.get('remote'):argv=[fixture['remote'] if item=='origin' else item for item in argv]
        return original_run(argv,*args,**kwargs)
    subprocess.run=git_transport
