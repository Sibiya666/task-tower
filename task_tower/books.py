"""Fresh, source-linked books and a standalone escaped browser view."""
import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sys
import tempfile

from .github_tasks import GitHubTasks, parse_metadata, task_status
from .project_connections import load_connections


def aggregate(connections, store_factory=GitHubTasks, include_library=False, *, on_update=None):
    from copy import deepcopy
    from .book_projection import identity_issue, project_issue
    from .book_library import project_library
    connections=list(connections)
    report = dict(fetched_at=datetime.now(timezone.utc).isoformat(), entries=[], errors=[])
    projects=[]; candidates=[]
    def publish():
        if on_update is not None: on_update(deepcopy(report))
    def error(connection, source, message):
        report['errors'].append(dict(project=connection.id,source=source,error=message))
    # Identity publication is deliberately independent of every detail/proof endpoint.
    for connection in connections:
        source=f'https://github.com/{connection.repository}/issues'
        try:
            store=store_factory(connection); issues={}; rows={}
            projects.append((connection,store,issues,rows))
            for issue in store.list_issues():
                try:
                    row=identity_issue(connection,issue)
                    if row['number'] in issues: raise ValueError()
                    issues[row['number']]=issue; rows[row['number']]=row
                    report['entries'].append(row)
                except Exception: error(connection,source,'Issue identity unavailable or duplicated')
        except Exception: error(connection,source,'Issues unavailable or incomplete')
        publish()
    if include_library:
        for connection,store,issues,rows in projects:
            library,errors=project_library(connection,store,connected_repositories={c.repository for c in connections})
            report['entries'].extend(library); report['errors'].extend(errors); publish()
    for connection,store,issues,rows in projects:
        for number,issue in issues.items():
            row=rows[number]; metadata=None; lifecycle_ok=True
            try:
                metadata=parse_metadata(issue.get('body'))
                if metadata and metadata.get('kind')=='task':
                    from .project_worker import issue_lifecycle
                    metadata=issue_lifecycle(store,issue)
            except Exception:
                lifecycle_ok=False
                error(connection,row['source'],'Issue metadata or lifecycle unavailable')
            try:
                projected,errors=project_issue(connection,store,issue,metadata)
                if not lifecycle_ok: projected['verification']='unverified'; projected['status']='needs_input'
                row.update(projected); report['errors'].extend(errors)
                if lifecycle_ok and metadata and metadata.get('status')=='done': candidates.append((connection,store,issue,row))
            except Exception:
                row['verification']='unverified'
                error(connection,row['source'],'Issue details unavailable')
            publish()
        if hasattr(connection,'checkout'):
            try:
                from .capture_migration import book_migrations
                for migration in book_migrations(connection):
                    found=False
                    for entry in report['entries']:
                        if entry['project']==connection.id and entry['source']==migration['issue_url']:
                            found=True
                            entry.setdefault('migrations',[]).append(migration)
                            if 'relationships' not in entry:
                                from .capture import relationship_projection
                                entry['relationships'],errors=relationship_projection(connection,store,issues[migration['number']])
                                for error in errors:
                                    report['errors'].append(dict(project=connection.id,source=entry['source'],error=error))
                    if migration['number'] is not None and not found:
                        report['errors'].append(dict(project=connection.id,source=migration['issue_url'],error='Legacy canonical Issue unavailable; preserve migration provenance'))
                    if migration['status']!='current':
                        report['errors'].append(dict(project=connection.id,source=migration['issue_url'] or f'https://github.com/{connection.repository}/issues',error='Legacy migration '+migration['status']+'; inspect original source and existing Issue'))
            except (ValueError,OSError):
                report['errors'].append(dict(project=connection.id,source=f'https://github.com/{connection.repository}/issues',error='Legacy migration provenance unavailable'))
        publish()
    for connection,store,issue,row in candidates:
        try:
            from .project_worker import verified_done
            from .github_source import GitHubSource
            authorization=store.headers.get('Authorization','')
            source=GitHubSource(connection.repository,token=authorization.removeprefix('Bearer ') or None)
            if verified_done(connection,store,source,issue) is not True: raise ValueError()
            row.update(status='done',verification='verified')
        except Exception:
            row['verification']='unverified'
            error(connection,row['source'],'Completion evidence unavailable or unverified')
        publish()
    return report


def _output_path(path, sources, overwrite, checkouts=()):
    from .tasks import _safe_path
    path = _safe_path(path)
    for checkout in checkouts:
        checkout = Path(checkout).resolve()
        registry=checkout/'.task-tower'/'capture-migrations.json'
        protected=(registry,registry.with_name(registry.name+'.lock.sqlite3'))
        for target in protected:
            if path==target or (path.exists() and target.exists() and os.path.samefile(path,target)):
                raise ValueError('Report cannot replace migration provenance')
        if path.is_relative_to(checkout):
            parts = path.relative_to(checkout).parts
            if not parts or parts[0] not in ('runtime', '.task-tower'):
                raise ValueError('Report must not replace project source')
    for source in sources:
        if source is not None:
            source = Path(source).resolve()
            if path == source or (path.exists() and source.exists() and os.path.samefile(path, source)):
                raise ValueError('Report cannot replace an input source')
    if path.exists() and (not overwrite or not path.is_file()):
        raise ValueError('Report exists; refresh requires --overwrite')
    return path


def _write_report(path, text, sources, overwrite, checkouts=()):
    path = _output_path(path, sources, overwrite, checkouts)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.books-')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        _output_path(path, sources, overwrite, checkouts)
        if overwrite:
            os.replace(temporary, path)
        else:
            # Atomic no-clobber publication; an existing destination is never truncated.
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def render_html(report):
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for entry in report['entries']:
        source = entry.get('source', '')
        source = source if isinstance(source, str) and source.startswith('https://github.com/') else '#'
        links=[]
        provenance=entry.get('capture',{})
        candidates=[('Session',provenance.get('session',{}).get('url'))]
        candidates.extend(('Related source',url) for url in provenance.get('requested_relations',{}).get('sources',[]))
        relationships=entry.get('relationships',{})
        for key in ('parent','milestone'):
            row=relationships.get(key)
            if isinstance(row,dict): candidates.append((key.capitalize(),row.get('source')))
        children=relationships.get('sub_issues',[])
        if isinstance(children,list): candidates.extend(('Sub-issue',row.get('source')) for row in children if isinstance(row,dict))
        from .capture import safe_url
        for label,url in candidates:
            if url is None: continue
            try: safe_url(url)
            except ValueError: continue
            links.append('<a rel="noreferrer" href="'+esc(url)+'">'+esc(label)+'</a>')
        session=provenance.get('session',{})
        session_text='<p>Session: '+esc(session.get('provider',''))+' / '+esc(session.get('id',''))+'</p>' if session else ''
        session_text+=''.join('<p>Legacy migration: '+esc(row.get('status','unavailable'))+'</p>' for row in entry.get('migrations',[]))
        cards.append('<article data-project="' + esc(entry['project']) + '" data-book="' + esc(entry['book']) + '"><h2>' + esc(entry['title']) + '</h2><p>' + esc(entry['project']) + ' · ' + esc(entry['status']) + '</p>'+session_text+'<a rel="noreferrer" href="' + esc(source) + '">Source</a> '+ ' '.join(links)+'</article>')
    errors = ''.join('<li>' + esc(error['project']) + ': ' + esc(error['error']) + '</li>' for error in report['errors'])
    projects = ''.join('<option>' + esc(project) + '</option>' for project in sorted({e['project'] for e in report['entries']}))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Task Tower books</title>
<style>body{font:18px system-ui;max-width:850px;margin:3em auto;padding:1em;background:#f5f2e9;color:#242a2d}article{background:white;padding:1.5em;margin:1em 0;border-radius:12px}select,button{font:inherit;margin:.3em;padding:.4em}h2{overflow-wrap:anywhere}#errors{color:#8a2719}</style>
<h1>Task Tower books</h1><p>Fetched ''' + esc(report.get('fetched_at', 'unknown')) + '''. This saved snapshot does not update automatically.</p>
<label>Project <select id="project"><option value="">All projects</option>''' + projects + '''</select></label>
<label>Book <select id="book"><option value="">All books</option><option value="ideas">Ideas</option><option value="tasks">Tasks</option><option value="library">Library</option></select></label>
<ul id="errors">''' + errors + '''</ul><main>''' + ''.join(cards) + '''</main><p id="count"></p><button id="prev">Previous</button><button id="next">Next</button>
<script>const cards=[...document.querySelectorAll('article')],project=document.querySelector('#project'),book=document.querySelector('#book');let page=0;function draw(){let rows=cards.filter(x=>(!project.value||x.dataset.project===project.value)&&(!book.value||x.dataset.book===book.value));page=Math.max(0,Math.min(page,Math.ceil(rows.length/3)-1));cards.forEach(x=>x.hidden=true);rows.slice(page*3,page*3+3).forEach(x=>x.hidden=false);document.querySelector('#count').textContent=rows.length+' entries · page '+(page+1)+' / '+Math.max(1,Math.ceil(rows.length/3));document.querySelector('#prev').disabled=page===0;document.querySelector('#next').disabled=(page+1)*3>=rows.length}project.onchange=book.onchange=()=>{page=0;draw()};document.querySelector('#prev').onclick=()=>{page--;draw()};document.querySelector('#next').onclick=()=>{page++;draw()};draw();</script></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fresh GitHub project books')
    parser.add_argument('--connections', required=True, type=Path)
    parser.add_argument('--format', choices=('json', 'html'), default='json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--overwrite', action='store_true', help='Explicitly refresh an existing report; never an input source')
    parser.add_argument('--project')
    parser.add_argument('--book', choices=('ideas', 'tasks', 'library'))
    parser.add_argument('--import-card', type=Path, help='Explicit idempotent legacy Issue import; requires --project')
    args = parser.parse_args(argv)
    try:
        sources = (args.connections, args.import_card)
        if args.output: _output_path(args.output, sources, args.overwrite)
        connections = load_connections(args.connections)
        checkouts = [connection.checkout for connection in connections]
        if args.output: _output_path(args.output, sources, args.overwrite, checkouts)
        if args.project:
            connections = [c for c in connections if c.id == args.project]
            if not connections: raise ValueError('Unknown project')
        if args.import_card:
            if not args.project: raise ValueError('Import requires one explicit project')
            result = GitHubTasks(connections[0]).import_card(args.import_card)
            print(json.dumps(dict(number=result['number'], source=f'https://github.com/{connections[0].repository}/issues/{result["number"]}',project_sync=result['project_sync'])))
            return 0 if result['project_sync']['status']=='synced' else 1
        report = aggregate(connections, include_library=args.book in (None, 'library'))
        if args.book: report['entries'] = [e for e in report['entries'] if e['book'] == args.book]
        text = render_html(report) if args.format == 'html' else json.dumps(report, ensure_ascii=False, indent=2)
        if args.output: _write_report(args.output, text, sources, args.overwrite, checkouts)
        else:
            if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
            print(text)
        return 1 if report['errors'] else 0
    except (ValueError, OSError):
        print('task-tower: books request failed; check connections and GitHub access', file=sys.stderr)
        return 2
