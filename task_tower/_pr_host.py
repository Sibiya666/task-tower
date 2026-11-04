"""Fixed contained host entry; no model child inherits its control writer."""
import argparse
import os
import sys
import time
import uuid
from pathlib import Path
from .pr_context import PRPrivateInputs,PRHostContext
from .pr_journal import PRJournal
from .pr_worker import Controller,step
from .pr_supervision import _Wire,PRProgress
from .executor_profiles import profile_fingerprint


def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    for flag in ('connections','config','journal','stop-file'):parser.add_argument('--'+flag,type=Path,required=True)
    for flag in ('owner-id','session-id','first-repository','input-manifest-sha256'):parser.add_argument('--'+flag,required=True)
    parser.add_argument('--first-pr',type=int,required=True)
    parser.add_argument('--pipeline-config',type=Path);parser.add_argument('--once',action='store_true')
    args=parser.parse_args(argv)
    descriptor=os.dup(sys.stdout.fileno());os.set_inheritable(descriptor,False)
    null=os.open(os.devnull,os.O_WRONLY)
    try:os.dup2(null,1);os.dup2(null,2)
    finally:os.close(null)
    wire=_Wire(descriptor,args.session_id,args.owner_id)
    action=str(uuid.uuid4())
    try:
        wire.send('hello')
        wire.send('phase_start',action_id=action,kind='preflight',repository=None,pr_number=None,input_sha256=None)
        inputs=PRPrivateInputs(args.connections,args.config,args.journal,args.pipeline_config)
        # Independently validate source/private aliases before opening any PR
        # writer. Keep these original file pins through the owned handoff.
        with PRHostContext.from_inputs(inputs) as preflight:
            before=preflight.private_input_provenance
            if profile_fingerprint(before)!=args.input_manifest_sha256:raise ValueError('Changed host launch inputs')
            journal=PRJournal(args.journal)
            with journal.owner(args.owner_id):
                with PRHostContext.from_inputs(inputs) as context:
                    after=context.private_input_provenance
                    if ({k:v for k,v in before.items() if k!='pr_journal'}!=
                            {k:v for k,v in after.items() if k!='pr_journal'}
                            or before['pr_journal'] is not None and before['pr_journal']!=after['pr_journal']):
                        raise ValueError('Changed original host inputs')
                    preflight._check_pins()
                    controller=Controller.from_context(context,journal,args.owner_id)
                    progress=PRProgress.from_controller(controller,wire,args.stop_file)
                    wire.send('phase_end',action_id=action)
                    context._lifecycle=progress
                    while not args.stop_file.exists():
                        report=step(controller.config,journal,owner_id=args.owner_id)
                        wire.send('report',report=report)
                        if args.once:break
                        wire.send('idle')
                        deadline=time.monotonic()+progress.interval_seconds
                        while not args.stop_file.exists() and time.monotonic()<deadline:time.sleep(.1)
        wire.send('end');return 0
    except (ValueError,OSError,RuntimeError):return 1
    finally:os.close(descriptor)


if __name__=='__main__':raise SystemExit(main())
