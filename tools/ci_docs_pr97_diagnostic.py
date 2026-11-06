"""One temporary PR97 observation; never an acceptance producer or validator fix."""
import argparse
from collections import deque
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

TARGET_SHA = 'caddddd6da41847b20737cf7a40fe89b8c4e6d70'
SOURCE_SHA256 = '1b4f6e8d231364eff4e6150eecbc1e975f78030d67a81a7dbd54f3a1cc32a3b5'
REASONS = frozenset(('resource_limit git_or_resource_error prose_limit malformed_blob '
    'malformed_head missing_parent malformed_diff markdown_parser_limit destination_limit '
    'path_limit malformed_tree ancestor_depth_limit invalid_identity not_documentation_scope '
    'new_broken_local_links documentation_validation_failed').split())
STATUSES = frozenset('passed failed timeout unavailable unknown cancelled cleanup_failed'.split())


def valid_source(head, data):
    return head == TARGET_SHA and hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest() == SOURCE_SHA256


def error_chain(error, module):
    chain, seen = [], set()
    while error is not None and len(chain) < 4 and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, module.DocumentationError):
            # Never format arbitrary exception values or type names into output.
            reason = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
            chain.append('documentation:'+ (reason if reason in REASONS else 'unknown'))
        else:
            chain.append(next((name for kind, name in ((OSError,'os_error'),(UnicodeError,'unicode_error'),
                (ValueError,'value_error')) if isinstance(error,kind)), 'unknown'))
        error = error.__cause__
    return chain


def operation(args):
    if not args:
        return 'unknown'
    if args[:2] == ('cat-file','-s'):
        return 'blob_size'
    if args[:2] == ('cat-file','blob'):
        return 'blob'
    return args[0] if args[0] in ('rev-parse','cat-file','diff','ls-tree') else 'unknown'


def observe(module, target):
    """Delegate originals unchanged; only fixed-size scalar bookkeeping is added."""
    started=time.monotonic()
    original_git, original_run, original_broken=module._Source.git,module.run_command,module._broken
    tail=deque(maxlen=8)
    state={'git_calls':0,'process_calls':0,'broken_calls':0,'phase':'classify','current':None,'observer_failed':False}
    report={'version':1,'kind':'diagnostic.observation','diagnostic_only':True,
            'target_sha':TARGET_SHA,'source_sha256_lf':SOURCE_SHA256,
            'original_limits':{'seconds':module.MAX_SECONDS,'supervisor_reserve_seconds':5,
                'capture_bytes':module.MAX_CAPTURE_BYTES,'prose_bytes':module.MAX_PROSE_BYTES,
                'output_bytes':module.MAX_OUTPUT_BYTES}}
    @contextmanager
    def bookkeeping():
        # Observer faults must neither alter original execution nor masquerade
        # as an original refusal (even if _classify catches ValueError).
        try:
            yield
        except Exception:
            state['observer_failed']=True
    def run(*args, **kwargs):
        current=None
        with bookkeeping():
            state['process_calls']+=1
            current=state['current']
            if current is not None:
                current['process_called']=True
        result=original_run(*args,**kwargs)
        with bookkeeping():
            if current is not None:
                status=result.get('status')
                current['process_status']=status if type(status) is str and status in STATUSES else 'unknown'
                for key in ('cleanup_confirmed','stdout_truncated','stderr_truncated'):
                    current[key]=result.get(key) is True
                for key in ('stdout_bytes','stderr_bytes','exit_code'):
                    value=result.get(key)
                    current[key]=value if type(value) is int and -2**32 <= value <= 2**32 else None
        return result
    def git(source,*args,**kwargs):
        event=None
        before=time.monotonic()
        with bookkeeping():
            state['git_calls']+=1
            event={'sequence':state['git_calls'],'operation':operation(args),'phase':state['phase'],
                   'process_called':False}
            state['current']=event
        try:
            return original_git(source,*args,**kwargs)
        except BaseException:
            with bookkeeping():
                if event is not None:
                    event['raised']=True
            raise
        finally:
            with bookkeeping():
                if event is not None:
                    event.update(elapsed_seconds=round(time.monotonic()-before,6),
                        deadline_remaining_seconds=round(source.deadline-time.monotonic(),6),
                        prose_bytes=source.prose_bytes,capture_bytes=source.capture_bytes)
                    tail.append(event)
            state['current']=None
    def broken(source,revision):
        with bookkeeping():
            state['broken_calls']+=1
            state['phase']='baseline_links' if state['broken_calls']==1 else 'current_links'
        return original_broken(source,revision)
    module._Source.git,module.run_command,module._broken=git,run,broken
    try:
        module.validate(target,repository='Sibiya666/task-tower',pr_number=97,phase='postmerge')
        report['outcome']='passed'
    except Exception as error:
        report.update(outcome='refused',error_chain=error_chain(error,module))
    finally:
        module._Source.git,module.run_command,module._broken=original_git,original_run,original_broken
    if state['observer_failed']:
        report['outcome']='observer_failed'
        report.pop('error_chain',None)
    report.update(elapsed_seconds=round(time.monotonic()-started,6),git_calls=state['git_calls'],
        process_calls=state['process_calls'],broken_calls=state['broken_calls'],
        tail=list(tail),omitted_operations=max(0,state['git_calls']-len(tail)))
    return report


def encode_report(report):
    data=(json.dumps(report,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n').encode('ascii')
    if len(data)>16384:
        raise ValueError('diagnostic_output_limit')
    return data


def load_target(target):
    target=Path(target).resolve(strict=True)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN','GITHUB_TOKEN')}
    env.update(GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0',
               GIT_OPTIONAL_LOCKS='0',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
    head=subprocess.run(['git','-C',str(target),'rev-parse','--verify','HEAD^{commit}'],
        env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        timeout=10,check=True).stdout.decode('ascii').strip()
    module_path=target/'task_tower/ci_docs.py'
    if not valid_source(head,module_path.read_bytes()):
        raise ValueError('source_guard')
    sys.path.insert(0,str(target))
    module=importlib.import_module('task_tower.ci_docs')
    if Path(module.__file__).resolve()!=module_path or module.MAX_SECONDS!=30:
        raise ValueError('import_guard')
    return module,target


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args(argv)
    try:
        module,target=load_target(args.target)
    except Exception:
        report={'version':1,'kind':'diagnostic.observation','diagnostic_only':True,
                'target_sha':TARGET_SHA,'outcome':'guard_refused'}
    else:
        try:
            report=observe(module,target)
        except Exception:
            report={'version':1,'kind':'diagnostic.observation','diagnostic_only':True,
                    'target_sha':TARGET_SHA,'outcome':'observer_failed'}
    try:
        data=encode_report(report)
        Path(args.report).write_bytes(data)
    except Exception:
        print('diagnostic output refused')
        return 2
    print(data.decode('ascii').rstrip())
    return 0 if report['outcome']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
