"""Independent bounded review through a pinned, read-only reviewer protocol."""
import hashlib
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

