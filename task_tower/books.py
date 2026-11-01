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


def aggregate(connections, store_factory=GitHubTasks, include_library=False):
    report = dict(fetched_at=datetime.now(timezone.utc).isoformat(), entries=[], errors=[])
    for connection in connections:
        try:
            store = store_factory(connection)
            for issue in store.list_issues():
                number = issue.get('number')
                if type(number) is not int or number < 1: raise ValueError()
                metadata = parse_metadata(issue.get('body'))
                if metadata and metadata.get('kind') == 'task':
                    from .project_worker import issue_lifecycle
                    metadata = issue_lifecycle(store, issue)
                status = task_status(metadata)
                if metadata and metadata.get('status') == 'done':
                    try:
                        from .project_worker import verified_done
                        from .github_source import GitHubSource
                        authorization = store.headers.get('Authorization', '')
                        source = GitHubSource(connection.repository, token=authorization.removeprefix('Bearer ') or None)
                        if verified_done(connection, store, source, issue): status = 'done'
                        else: raise ValueError()
                    except Exception:
                        report['errors'].append(dict(project=connection.id, source=f'https://github.com/{connection.repository}/issues/{number}', error='Completion evidence unavailable or unverified'))
                report['entries'].append(dict(id=f'{connection.repository}#{number}', project=connection.id, book='ideas' if metadata and metadata.get('kind') == 'idea' else 'tasks', title=str(issue.get('title', '')), status=status, remote_state=issue.get('state'), source=f'https://github.com/{connection.repository}/issues/{number}'))
        except Exception:
            report['errors'].append(dict(project=connection.id, source=f'https://github.com/{connection.repository}/issues', error='Issues unavailable or incomplete'))
        if include_library:
            try:
                store = store_factory(connection)
                for entry in store.library():
                    report['entries'].append(dict(entry, id=entry['source'], project=connection.id, book='library', status='source'))
            except Exception:
                report['errors'].append(dict(project=connection.id, source=f'https://github.com/{connection.repository}', error='Library unavailable or incomplete'))
    return report


def _output_path(path, sources, overwrite, checkouts=()):
    from .tasks import _safe_path
    path = _safe_path(path)
    for checkout in checkouts:
        checkout = Path(checkout).resolve()
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
        cards.append('<article data-project="' + esc(entry['project']) + '" data-book="' + esc(entry['book']) + '"><h2>' + esc(entry['title']) + '</h2><p>' + esc(entry['project']) + ' · ' + esc(entry['status']) + '</p><a rel="noreferrer" href="' + esc(source) + '">Source</a></article>')
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
