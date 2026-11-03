"""Read-only child cache lookup; never executes or inserts a resource sample."""
import json
import os
from pathlib import Path
import sys
from task_tower.group_registration import load_registration_context
from task_tower.group_resources import ResourceContext,_current_observation
from task_tower.pipeline_journal import PipelineJournal

assert not any(key.upper() in ('GH_TOKEN','GITHUB_TOKEN') for key in os.environ)
groups,connections,pipeline,executor,journal,digest=sys.argv[1:]
with load_registration_context(Path(groups),Path(connections),Path(pipeline),Path(executor),
        PipelineJournal(Path(journal))) as registration:
    context=ResourceContext.from_registration(registration)
    try:
        _current_observation(context,digest)
    except ValueError:
        print(json.dumps(dict(reused=False)))
    else:
        print(json.dumps(dict(reused=True)))
        raise SystemExit(1)
