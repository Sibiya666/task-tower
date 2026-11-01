"""Foreground Issue delivery dispatcher; never a development executor."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

from .project_connections import load_connections, safe_config_path
from .github_tasks import GitHubTasks
from .github_source import GitHubSource
from .project_worker import verified_done


def validate_paths(connections_path, config_path, journal_path, connections):
    paths = [safe_config_path(p) for p in (connections_path, config_path, journal_path)]
    journal = paths[2]
    paths += [safe_config_path(str(journal) + suffix) for suffix in ('-wal', '-shm', '-journal')]
    for index, path in enumerate(paths):
        if any(path.resolve().is_relative_to(c.checkout.resolve()) for c in connections):
            raise ValueError('Private dispatcher paths must be outside connected checkouts')
        for other in paths[:index]:
            if str(path.resolve()).casefold() == str(other.resolve()).casefold() or (
                    path.exists() and other.exists() and os.path.samefile(path, other)):
                raise ValueError('Private dispatcher paths must be distinct')
    return paths[2]


def _source(connection):
    from .github_source import resolve_token
    return GitHubSource(connection.repository, token=resolve_token())


def _identity(snapshot, candidate):
    project = snapshot.get(candidate['repository'].casefold())
    if not project or project.get('error'):
        return False
    metadata = project.get('metadata', {}).get(candidate['issue'])
    if not isinstance(metadata, dict) or metadata.get('kind') != 'task':
        return False
    aliases = [metadata[k] for k in ('task_id', 'legacy_id', 'id') if k in metadata]
    return bool(aliases) and all(value == candidate['task_id'] for value in aliases) and len(
        project['index'].get(candidate['task_id'], [])) == 1


def tick(connections, config, journal_path, *, dry_run=False, store_factory=GitHubTasks,
         source_factory=_source, invoke=None, authority_check=None, forbidden_paths=()):
    from .dispatch_selection import collect_snapshot, select_ready
    from .dispatch_delivery import DeliveryJournal, deliver, backend_fingerprint, run_backend
    report = dict(projects=[], selection={'ready': [], 'excluded': []}, deliveries=[], operational_failure=False)
    if not config.get('allowlist') or not config.get('backend'):
        report['disabled'] = 'empty_allowlist' if not config.get('allowlist') else 'missing_backend'
        return report
    snapshot = collect_snapshot(connections, store_factory=store_factory, source_factory=source_factory)
    selection = select_ready(snapshot, config['allowlist'], verify_done=verified_done)
    report.update(projects=selection['projects'], selection=selection)
    report['operational_failure'] = any(p.get('status') == 'unavailable' for p in selection['projects'])
    journal = DeliveryJournal(journal_path, readonly=dry_run,
        checkouts=[c.checkout for c in connections], forbidden_paths=forbidden_paths)
    rows = journal.rows()
    existing = {(r['repository'].casefold(),r['issue']): r for r in rows}
    backend = config['backend']
    fingerprint = backend_fingerprint(backend)
    authorized = {(r['repository'].casefold(),r['issue'],r['task_id']) for r in config['allowlist']}
    def current():
        return authority_check is None or authority_check()
    def guarded_invoke(trusted, request):
        if not current(): return {'status':'unknown','reason':'backend_failed'}
        return (invoke or run_backend)(trusted, request)
    try:
        if not dry_run:
            # The cursor advances before invocation; revoked rows still consume their fair turn.
            for row in journal.lookup_rows(limit=8):
                candidate = dict(row)
                key = (row['repository'].casefold(),row['issue'],row['task_id'])
                if key not in authorized or row['backend_fingerprint'] != fingerprint or not _identity(snapshot,row) or not current():
                    report['deliveries'].append({k:row[k] for k in ('repository','issue','task_id')} | {'state':'needs_input','reason':'authorization_mismatch'})
                    report['operational_failure'] = True
                    continue
                candidate['runner_label'] = snapshot[row['repository'].casefold()]['connection'].runner_label
                report['deliveries'].append(deliver(candidate,backend,journal,invoke=guarded_invoke))
        submits = 0
        for candidate in selection['ready']:
            old = existing.get((candidate['repository'].casefold(),candidate['issue']))
            if old:
                continue
            if dry_run or submits >= 8:
                report['deliveries'].append(dict(candidate, state='planned' if dry_run else 'deferred',reason='dry_run' if dry_run else 'submit_budget'))
                continue
            # Every send uses a newly collected dependency/lifecycle snapshot.
            fresh = collect_snapshot(connections,store_factory=store_factory,source_factory=source_factory)
            for repository, current_project in fresh.items():
                if current_project.get('error'):
                    report['operational_failure'] = True
                    for visible in report['projects']:
                        if visible['repository'] == repository:
                            visible.update(status='unavailable',reason='source_unavailable')
            project = fresh.get(candidate['repository'].casefold())
            try:
                if not project or project.get('error'): raise ValueError()
                latest = project['store'].get(candidate['issue'])
                if (not isinstance(latest, dict) or type(latest.get('number')) is not int
                        or latest['number'] != candidate['issue'] or latest.get('state') not in ('open','closed')):
                    raise ValueError()
                latest_meta = project['store'].metadata(latest)
                old_meta = project['metadata'].get(candidate['issue'])
                if latest_meta != old_meta:
                    # A changed identity could invalidate the repository-wide duplicate index.
                    raise ValueError()
                project['issues'][candidate['issue']] = latest
            except Exception:
                report['deliveries'].append(dict(candidate,state='excluded',reason='revalidation_failed'))
                continue
            fresh_selection = select_ready(fresh, config['allowlist'], verify_done=verified_done)
            if candidate not in fresh_selection['ready'] or not current():
                report['deliveries'].append(dict(candidate,state='excluded',reason='revalidation_failed'))
                continue
            submits += 1
            report['deliveries'].append(deliver(candidate,backend,journal,invoke=guarded_invoke,lookup_existing=False))
        reported = {(d['repository'].casefold(), d['issue']) for d in report['deliveries']}
        for row in rows:
            if (row['repository'].casefold(),row['issue']) not in reported:
                report['deliveries'].append({k:row[k] for k in ('repository','issue','task_id')} | {
                    'state': 'accepted' if row['status']=='accepted' else 'deferred',
                    'status':row['status'], 'reason':'accepted' if row['status']=='accepted' else 'lookup_budget'})
        if any(d.get('status') == 'unknown' for d in report['deliveries']):
            report['operational_failure'] = True
        if any(d.get('state',d.get('status')) in ('unknown','needs_input') for d in report['deliveries']):
            report['operational_failure'] = True
        return report
    finally:
        close = getattr(journal,'close',None)
        if close: close()


def main(argv=None, *, sleep=time.sleep):
    from .dispatch_selection import load_dispatch_config
    from .dispatch_delivery import DeliveryJournal
    parser = argparse.ArgumentParser(description='Foreground authorized Issue dispatcher')
    for name in ('connections','config','journal'):
        parser.add_argument('--'+name,type=Path,required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--once',action='store_true')
    mode.add_argument('--status',action='store_true')
    parser.add_argument('--dry-run',action='store_true')
    args = parser.parse_args(argv)
    if args.status and args.dry_run: parser.error('--status cannot be combined with --dry-run')
    operational = False
    try:
        while True:
            operational = False
            connections = load_connections(args.connections)
            validate_paths(args.connections,args.config,args.journal,connections)
            config = load_dispatch_config(args.config,connections)
            expected = (args.connections.read_bytes(),args.config.read_bytes())
            def authority_check():
                try:
                    validate_paths(args.connections,args.config,args.journal,connections)
                    return expected == (args.connections.read_bytes(),args.config.read_bytes())
                except (ValueError,OSError): return False
            operational = True
            if args.status:
                journal = DeliveryJournal(args.journal,readonly=True,forbidden_paths=(args.connections,args.config),checkouts=[c.checkout for c in connections])
                try:
                    report = {'deliveries':[{k:v for k,v in row.items() if k not in ('receipt_id','delivery_id','backend_fingerprint')} for row in journal.rows()]}
                finally:
                    close=getattr(journal,'close',None)
                    if close: close()
            else:
                report = tick(connections,config,args.journal,dry_run=args.dry_run,authority_check=authority_check,forbidden_paths=(args.connections,args.config))
            print(json.dumps(report,ensure_ascii=True,sort_keys=True))
            if args.once or args.status or args.dry_run or report.get('disabled'):
                return 1 if report.get('operational_failure') else 0
            sleep(config['interval_seconds'])
    except KeyboardInterrupt:
        return 0
    except (ValueError,OSError,sqlite3.Error):
        print(json.dumps({'error':'journal_operational_failure' if operational else 'invalid_configuration'}),file=sys.stderr)
        return 1 if operational else 2


if __name__ == '__main__':
    raise SystemExit(main())
