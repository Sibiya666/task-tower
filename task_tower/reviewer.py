"""Independent bounded review through a pinned, read-only reviewer protocol."""
import hashlib
import copy
import json
import math
import os
from pathlib import Path
import re

from .processes import run_command


RESULT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['task_id', 'commit', 'verdict', 'summary', 'findings'],
    'properties': {'task_id': {'type': 'string'}, 'commit': {'type': 'string'},
                   'verdict': {'type': 'string', 'enum': ['approve', 'reject', 'needs_input']},
                   'summary': {'type': 'string'},
                   'findings': {'type': 'array', 'items': {'type': 'string'}}}}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class ReviewRunner:
    def __init__(self, config):
        self.config = config

    def review_bound(self,checkout,task,bundle,output_dir,*,binding,executor_profile):
        """Full installation profile, fresh private instructions, host envelope.

        This opt-in protocol does not translate a full profile into the legacy
        single-file reviewer configuration used by review().
        """
        from .pr_evidence import PostmergeReviewBinding
        from .pr_policy import canonical,strict_json,exact,integer,policy_fingerprint
        from .executor_profiles import _pins,profile_fingerprint,child_environment,_path
        from .pr_review import _private_directory
        from .project_connections import safe_config_path
        from .pipeline_inputs import _ordinary
        if type(binding) is not PostmergeReviewBinding:
            raise ValueError('Host postmerge binding required')
        profile=copy.deepcopy(executor_profile)
        required={'kind','repository','checkout','runner_label','argv','source_ref','timeout_seconds',
            'log_max_bytes','max_attempts','trusted','approve_for_me','runs_dir','superpowers'}
        exact(profile,required)
        if (profile['kind'] not in ('codex','custom') or profile['approve_for_me'] is not False or
                type(profile['trusted']) is not bool or profile['kind']=='custom' and not profile['trusted'] or
                profile['repository'].casefold()!=binding.pr_binding['repository']):
            raise ValueError('Invalid bound readonly profile')
        timeout=integer(profile['timeout_seconds'],1,3600)
        limit=integer(profile['log_max_bytes'],1,67108864)
        argv=profile['argv']
        if (not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a or '\0' in a for a in argv) or
                profile['kind']=='codex' and len(argv)!=1 or not _path(argv[0]).is_file()):
            raise ValueError('Invalid bound reviewer argv')
        pins=_pins(profile['superpowers'])
        if pins!=profile['superpowers']: raise ValueError('Profile must already be normalized')
        request=binding.request(task,bundle,profile)
        checkout=Path(checkout).resolve()
        if not checkout.is_dir(): raise ValueError('Missing bound readonly checkout')
        output=_private_directory(output_dir,checkout)
        if output.is_relative_to(Path(pins['root'])) or Path(pins['root']).is_relative_to(output):
            raise ValueError('Bound output overlaps source instructions')
        snapshot=output/'instructions'; snapshot.mkdir(); snapshot_hashes={}
        for name in pins['manifest']:
            source=safe_config_path(Path(pins['root'])/name); _ordinary(source)
            destination=safe_config_path(snapshot/name)
            destination.parent.mkdir(parents=True,exist_ok=True);safe_config_path(destination)
            raw=source.read_bytes();snapshot_hashes[destination]=hashlib.sha256(raw).hexdigest()
            with destination.open('xb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
        copied_pins=dict(pins,root=str(snapshot))
        if _pins(copied_pins)!=copied_pins or _pins(profile['superpowers'])!=pins:
            raise ValueError('Instruction source or snapshot changed during preparation')
        metadata=dict(source_sha256=profile_fingerprint(pins),pins=copied_pins)
        request_path=output/'request.json'; result_path=output/'result.json'
        schema_path=output/'schema.json'; instructions_path=output/'instructions.json'
        immutable={request_path:canonical(request).encode('utf-8'),schema_path:canonical(RESULT_SCHEMA).encode('utf-8'),
            instructions_path:canonical(metadata).encode('utf-8')}
        for path,raw in immutable.items():
            with path.open('xb') as stream:stream.write(raw)
        if profile['kind']=='custom':
            command=[*argv,'--request',str(request_path),'--result',str(result_path)]
        else:
            command=[*argv,'exec','--json','--sandbox','read-only','--output-schema',str(schema_path),
                '--output-last-message',str(result_path),'-C',str(checkout),
                'Read AGENTS.md, the complete pinned Superpowers instruction snapshot identified by '+str(instructions_path)+
                ', and the immutable postmerge request at '+str(request_path)+
                '. Independently verify the task criteria, accepted stages and exact-main CI. Do not implement changes. '
                'Return only the required postmerge review JSON.']
        execution=run_command(command,checkout,timeout,env=child_environment(os.environ),
            capture=dict(directory=output,max_bytes_per_stream=limit))
        if (execution.get('status')!='passed' or execution.get('started') is not True or
                execution.get('cleanup_confirmed') is not True or execution.get('exit_code')!=0 or
                type(execution.get('pid')) is not int or execution['pid']<1 or
                any(execution.get(s+'_tail_unknown') is not False for s in ('stdout','stderr'))):
            raise ValueError('Bound reviewer process unconfirmed')
        for path,raw in immutable.items():
            _ordinary(path)
            if path.stat().st_size!=len(raw) or path.read_bytes()!=raw: raise ValueError('Bound reviewer input metadata changed')
        if _pins(profile['superpowers'])!=pins or _pins(copied_pins)!=copied_pins:
            raise ValueError('Full instruction source or snapshot changed')
        for path,digest in snapshot_hashes.items():
            _ordinary(path)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ValueError('Private instruction snapshot bytes changed')
        _ordinary(result_path)
        if result_path.stat().st_size>1024*1024: raise ValueError('Bound result exceeds limit')
        response=strict_json(result_path.read_bytes())
        exact(response,set(RESULT_SCHEMA['required']))
        if (response['task_id']!=task['id'] or response['commit']!=bundle['merge_commit'] or
                response['verdict'] not in ('approve','reject','needs_input') or
                not isinstance(response['summary'],str) or not response['summary'].strip() or
                not isinstance(response['findings'],list) or any(not isinstance(f,str) for f in response['findings'])):
            raise ValueError('Invalid bound postmerge result')
        process={key:execution[key] for key in ('pid','exit_code','started','cleanup_confirmed')}
        envelope=dict(request=request,result=response,process=process,result_sha256=policy_fingerprint(response),
            reviewer_instance_id=binding.reviewer_instance_id)
        envelope['receipt_sha256']=policy_fingerprint(envelope)
        return envelope

    def review(self, checkout: Path, task: dict, bundle: dict, output_dir: Path) -> dict:
        task_id = task.get('id', task.get('task_id', ''))
        commit = bundle.get('merge_commit', '')
        def unavailable(summary):
            return dict(task_id=task_id, commit=commit, verdict='needs_input', summary=summary, findings=[])
        try:
            config = self.config
            kind = config.get('kind')
            if kind not in ('codex', 'custom'):
                return unavailable('Unsupported reviewer kind.')
            timeout = config.get('timeout_seconds')
            if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
                return unavailable('Reviewer timeout must be positive, finite and at most 3600 seconds.')
            pin = config.get('superpowers', {})
            skill = Path(pin['path'])
            if not skill.is_absolute() or not re.fullmatch('[0-9a-fA-F]{64}', pin['sha256']) or hashlib.sha256(skill.read_bytes()).hexdigest() != pin['sha256'].lower():
                return unavailable('Superpowers skill pin is invalid or changed.')
            if not isinstance(task_id, str) or not task_id or not isinstance(commit, str) or not re.fullmatch('[0-9a-fA-F]{40}', commit):
                return unavailable('Review identity is invalid.')
            checkout, output_dir = Path(checkout).resolve(), Path(output_dir).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            request, result, schema = (output_dir / name for name in ('request.json', 'result.json', 'schema.json'))
            result.unlink(missing_ok=True)
            request.write_text(json.dumps(dict(task=task, bundle=bundle, checkout=str(checkout), superpowers=pin), ensure_ascii=False), encoding='utf-8')
            schema.write_text(json.dumps(RESULT_SCHEMA), encoding='utf-8')
            if kind == 'custom':
                template = config.get('review_argv')
                if not isinstance(template, list) or not template or any(not isinstance(arg, str) or not arg for arg in template):
                    return unavailable('Custom reviewer requires a nonempty argument array.')
                argv = [arg.format(request=str(request), result=str(result), checkout=str(checkout)) for arg in template]
            else:
                executable = config.get('executable', 'codex')
                if not isinstance(executable, str) or not executable:
                    return unavailable('Reviewer executable must be a nonempty string.')
                prompt = (f'Read AGENTS.md in the checkout and the pinned Superpowers skill at {skill}. '
                          'Read applicable verification and independent review skills. Evaluate the task criteria, prior '
                          'acceptances and verified CI bundle in the request. Do not implement changes. '
                          f'Request JSON: {request}. Return only the required review JSON for task {task_id}, commit {commit}.')
                argv = [executable, 'exec', '--json', '--sandbox', 'read-only', '--output-schema', str(schema),
                        '--output-last-message', str(result), '-C', str(checkout), prompt]
            env = {key: value for key, value in os.environ.items() if key.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN')}
            execution = run_command(argv, checkout, timeout, env=env)
            if execution['status'] != 'passed':
                return unavailable('Reviewer process did not complete successfully (' + execution['status'] + ').')
            if result.stat().st_size > 1024 * 1024:
                return unavailable('Reviewer response exceeds the size limit.')
            response = json.loads(result.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
            if (not isinstance(response, dict) or set(response) != set(RESULT_SCHEMA['required'])
                    or response['task_id'] != task_id or response['commit'] != commit
                    or response['verdict'] not in ('approve', 'reject', 'needs_input')
                    or not isinstance(response['summary'], str) or not response['summary'].strip()
                    or not isinstance(response['findings'], list)
                    or any(not isinstance(item, str) for item in response['findings'])):
                return unavailable('Reviewer response is invalid or does not match the requested task and commit.')
            return response
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return unavailable('Reviewer configuration or response could not be validated.')

