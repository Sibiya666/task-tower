"""Private installed PR supervision and independent metadata commands."""
import argparse
import json
from pathlib import Path
from .project_connections import load_connections,REPOSITORY
from .pr_policy import private_paths,text,integer
from .pr_journal import PRJournal
from .pr_worker import _public


class _Parser(argparse.ArgumentParser):
    def error(self,message):
        print(json.dumps(dict(status='needs_input',reason='invalid_pr_arguments')))
        raise SystemExit(2)


def _metadata(row):return dict(_public(row),cancel_requested=row['cancel_requested'])


def main(argv=None):
    parser=_Parser(description='Task Tower PR worker metadata')
    commands=parser.add_subparsers(dest='operation',required=True,parser_class=_Parser)
    for operation in ('status','cancel','reconcile','watch','work'):
        child=commands.add_parser(operation)
        for flag in ('connections','config','journal'):child.add_argument('--'+flag,type=Path,required=True)
        if operation in ('watch','work'):
            child.add_argument('--pipeline-config',type=Path)
            if operation=='work':child.add_argument('--once',action='store_true',required=True)
        else:child.add_argument('--repository',required=operation!='status')
        if operation in ('cancel','reconcile'):child.add_argument('--pr',type=int,required=True)
        if operation=='reconcile':child.add_argument('--inspect',action='store_true',required=True)
    args=parser.parse_args(argv)
    try:
        if args.operation in ('watch','work'):
            from .pr_context import PRPrivateInputs
            from .pr_supervision import supervise
            result=supervise(PRPrivateInputs(args.connections,args.config,args.journal,args.pipeline_config),
                once=args.operation=='work')
            print(json.dumps(result,sort_keys=True))
            return 1 if result['status'] in ('needs_input','unknown','timed_out') or result['reason'] is not None else 0
        connections=load_connections(args.connections)
        private_paths((args.connections,args.config,args.journal),tuple(c.checkout for c in connections))
        repository=None if args.repository is None else text(args.repository,REPOSITORY).casefold()
        journal=PRJournal(args.journal)
        if args.operation=='status':
            report=dict(status='ok',tasks=[_metadata(row) for row in journal.rows(repository)])
        else:
            number=integer(args.pr)
            row=journal.get(repository,number)
            if row is None:raise ValueError('Unknown PR metadata')
            if args.operation=='cancel':
                journal.cancel(repository,number);report=_metadata(journal.get(repository,number))
            else:
                report=_metadata(row)
                report['effects']=[dict(effect_id=e['effect_id'],kind=e['kind'],status=e['status'],
                    input_sha256=e['binding']['input_sha256']) for e in journal.effects(repository,number)]
                barrier=journal.barrier(repository)
                report['barrier']=None if barrier is None else dict(repository=barrier['repository'],
                    pr_number=barrier['pr_number'],completed=barrier['completed'],input_sha256=barrier['input_sha256'])
        print(json.dumps(report,sort_keys=True));return 0
    except (OSError,ValueError):
        reason='pr_execution_unverified' if args.operation in ('watch','work') else 'pr_metadata_unverified'
        print(json.dumps(dict(status='needs_input',reason=reason)));return 2


if __name__=='__main__':raise SystemExit(main())
