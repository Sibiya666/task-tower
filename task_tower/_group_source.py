"""Fixed contained host source probe. No model/claim/effect entry point."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    parser=argparse.ArgumentParser()
    for name in ('groups-config','connections','pipeline-config','executor-config','journal','owner-id','session-id','deadline'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:
        for value in (args.owner_id,args.session_id):
            if str(uuid.UUID(value))!=value:raise ValueError('Invalid host session')
        ceiling=float(args.deadline)
        if not math.isfinite(ceiling) or ceiling<=time.monotonic():raise ValueError('Expired source budget')
        ceiling=min(ceiling,time.monotonic()+60)
        os.set_inheritable(sys.stdout.fileno(),False)
        os.set_inheritable(sys.stderr.fileno(),False)
        sequence=0
        def emit(event,**fields):
            nonlocal sequence
            sequence+=1
            value=dict(version=1,domain='groups',session_id=args.session_id,owner_id=args.owner_id,
                pid=os.getpid(),sequence=sequence,event=event,**fields)
            sys.stdout.write(json.dumps(value,separators=(',',':'))+'\n');sys.stdout.flush()
        emit('hello')
        phase=dict(phase_id=str(uuid.uuid4()),phase_kind='source',task_key=None,action_id=None,
            member='collect_source',member_sha256=None,profile_sha256=None)
        emit('phase_start',requested_seconds=60,**phase)
        from .group_registration import load_registration_context
        from .pipeline_journal import PipelineJournal
        from .group_preparation import PreparationContext
        from .source_deadline import source_deadline
        journal=PipelineJournal(Path(args.journal))
        with source_deadline(ceiling),journal.operation_deadline(ceiling):
            with load_registration_context(Path(args.groups_config),Path(args.connections),
                    Path(args.pipeline_config),Path(args.executor_config),journal) as context:
                context.deadline=min(context.deadline,ceiling)
                prepared=PreparationContext.from_registration(context)
                prepared.candidates()  # Actual reads finish; never export them as authority.
        emit('phase_end',**phase)
        emit('session_end')
        return 0
    except Exception:
        sys.stderr.write('source_collection_unverified\n');sys.stderr.flush()
        return 2


if __name__=='__main__':raise SystemExit(main())
