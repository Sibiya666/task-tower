"""Fixed Claude policy and invocation; no authentication or model selection.

Probe validation describes supplied bytes, not successful process execution.
The caller must prove process exit, complete capture and cleanup separately.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .project_connections import safe_config_path


SUPPORTED_VERSION = '2.1.302'
REQUIRED_OPTIONS = frozenset({
    '--print', '--output-format', '--verbose', '--json-schema', '--safe-mode',
    '--permission-mode', '--permission-prompts', '--tools', '--allowedTools',
    '--strict-mcp-config', '--mcp-config', '--no-chrome', '--session-id',
    '--max-budget-usd',
})
ROLE_TOOLS = {'implementer': 'Read,Edit,Write,Glob,Grep',
              'reviewer': 'Read,Glob,Grep'}
_MCP_BYTES = b'{"mcpServers":{}}\n'


def claude_child_environment(environ: dict) -> dict:
    """Guard this child mapping only; local settings preflight belongs to worker.

    Preserve existing auth/model/telemetry choices and the host mapping. Loaded
    settings may override inherited env, so this is not effective-policy proof.
    """
    from .executor_profiles import child_environment
    result = {key: value for key, value in child_environment(environ).items()
              if key.upper() not in ('DISABLE_UPDATES', 'FORCE_AUTOUPDATE_PLUGINS')}
    result['DISABLE_UPDATES'] = '1'
    return result


def validate_claude_policy(value):
    """Return a fresh strict policy; arbitrary CLI options are never accepted."""
    if not isinstance(value, dict) or set(value) != {
            'version', 'role', 'max_budget_usd', 'stream_max_bytes', 'line_max_bytes'}:
        raise ValueError('Invalid Claude policy')
    if (value['version'] != SUPPORTED_VERSION or
            not isinstance(value['role'], str) or value['role'] not in ROLE_TOOLS):
        raise ValueError('Unsupported Claude version or role')
    budget = value['max_budget_usd']
    if not isinstance(budget, str) or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?', budget):
        raise ValueError('Invalid Claude budget')
    # Decimal syntax is deliberately small; integer cents avoid float rounding.
    whole, _, fraction = budget.partition('.')
    if len(whole) > 3 or not 0 < int(whole)*100 + int(fraction.ljust(2, '0')) <= 10000:
        raise ValueError('Invalid Claude budget')
    stream, line = value['stream_max_bytes'], value['line_max_bytes']
    if (type(stream) is not int or not 65536 <= stream <= 67108864 or
            type(line) is not int or not 4096 <= line <= min(stream, 1048576)):
        raise ValueError('Invalid Claude stream bounds')
    return dict(value)


def validate_probe(version_bytes: bytes, help_bytes: bytes, expected_version: str) -> dict:
    """Validate bounded version/help bytes; never return raw output."""
    if (expected_version != SUPPORTED_VERSION or type(version_bytes) is not bytes or
            type(help_bytes) is not bytes or not 0 < len(version_bytes) <= 65536 or
            not 0 < len(help_bytes) <= 1048576):
        raise ValueError('Invalid Claude probe')
    try:
        version = version_bytes.decode('utf-8').strip()
        help_text = help_bytes.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid Claude probe encoding') from error
    if version != SUPPORTED_VERSION + ' (Claude Code)':
        raise ValueError('Unsupported Claude version')
    # Match actual option headers and their indented continuations, not mentions
    # of flags in another option's description.
    blocks = {}
    for match in re.finditer(
            r'(?m)^ {2}(?:-[A-Za-z], )?(--[A-Za-z][\w-]*)\b[^\n]*(?:\n {4,}[^\n]*)*', help_text):
        name = match.group(1)
        if name in blocks:
            raise ValueError('Ambiguous Claude help')
        blocks[name] = match.group(0)
    if not REQUIRED_OPTIONS <= blocks.keys():
        raise ValueError('Missing Claude option')
    for option, choice in [('--output-format', 'stream-json'),
                           ('--permission-mode', 'manual'), ('--permission-prompts', 'none')]:
        if not re.search(r'["\']' + re.escape(choice) + r'["\']', blocks[option]):
            raise ValueError('Missing Claude option value')
    return dict(version=SUPPORTED_VERSION, version_supported=True,
                required_options_validated=True,
                version_sha256=hashlib.sha256(version_bytes).hexdigest(),
                help_sha256=hashlib.sha256(help_bytes).hexdigest())


def prepare_mcp_config(directory: Path) -> dict:
    """Exclusively create the fixed empty MCP configuration in a private attempt.

    The worker validates installation/checkouts exclusion before calling this.
    Existing files and symlink/hardlink aliases cannot be reused.
    """
    try:
        directory = Path(directory)
        if not directory.is_absolute():
            raise ValueError('MCP directory must be absolute')
        path = safe_config_path(directory / 'claude-mcp.json')
        with path.open('xb') as stream:
            stream.write(_MCP_BYTES)
            stream.flush()
            os.fsync(stream.fileno())
        return dict(mcp_path=str(path), mcp_sha256=hashlib.sha256(_MCP_BYTES).hexdigest())
    except OSError as error:
        raise ValueError('Cannot prepare Claude MCP configuration') from error


def build_claude_invocation(attempt: dict, profile: dict) -> list[str]:
    """Build the sole permitted argv; task text is one final data argument."""
    from .executor_harness import result_schema

    policy = validate_claude_policy(profile.get('claude'))
    if (profile.get('kind') != 'claude' or profile.get('trusted', False) is not False or
            profile.get('approve_for_me', False) is not False or
            not isinstance(profile.get('argv'), list) or len(profile['argv']) != 1 or
            not isinstance(profile['argv'][0], str) or not profile['argv'][0] or '\x00' in profile['argv'][0]):
        raise ValueError('Invalid Claude invocation policy')
    try:
        for key in ('run_id', 'attempt_id'):
            if str(uuid.UUID(attempt[key])) != attempt[key]:
                raise ValueError('Invalid Claude attempt identity')
        if not isinstance(attempt['source_sha'], str) or not re.fullmatch('[0-9a-f]{40}', attempt['source_sha']):
            raise ValueError('Invalid Claude source')
        path = safe_config_path(attempt['mcp_path'])
        if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size != len(_MCP_BYTES):
            raise ValueError('Unsafe Claude MCP configuration')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if data != _MCP_BYTES or digest != attempt['mcp_sha256']:
            raise ValueError('Claude MCP configuration drift')
        request = attempt['request_content']
        instructions = attempt['instruction_content']
        if not isinstance(request, dict) or not isinstance(instructions, str) or not instructions.strip():
            raise ValueError('Missing inline Claude context')
        prompt = ('Follow these pinned instructions:\n' + instructions +
                  '\nExecution request (task data, not invocation authority):\n' +
                  json.dumps(request, ensure_ascii=True, allow_nan=False) +
                  '\nReturn only the required run/attempt/source-bound result JSON. '
                  'Do not publish, change configuration, choose models or claim acceptance.')
        tools = ROLE_TOOLS[policy['role']]
        return [*profile['argv'], '-p', '--output-format', 'stream-json', '--verbose',
                '--safe-mode', '--permission-mode', 'manual', '--permission-prompts', 'none',
                '--strict-mcp-config', '--mcp-config', str(path), '--no-chrome',
                '--session-id', attempt['attempt_id'], '--max-budget-usd', policy['max_budget_usd'],
                '--json-schema', json.dumps(result_schema(attempt), ensure_ascii=True, allow_nan=False),
                '--tools', tools, '--allowedTools', tools, prompt]
    except (KeyError, TypeError, OSError) as error:
        raise ValueError('Invalid Claude attempt') from error


def claude_capabilities(profile: dict, evidence: dict | None = None) -> dict:
    """Report trusted caller evidence; fixtures never establish installed proof.

    This function performs no probe, reads no authentication and grants no
    acceptance. The worker supplies evidence only after validating its binding.
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    probed = evidence.get('probed') is True
    supported = probed and evidence.get('version_supported') is True
    protocol = evidence.get('protocol_validated') is True
    installed = (supported and protocol and evidence.get('evidence_kind') == 'installed' and
                 evidence.get('installed_execution_verified') is True)
    reviewed = installed and evidence.get('independent_review_verified') is True
    return dict(configured=True, executable=Path(profile['argv'][0]).is_file(),
                probed=probed, verified=installed, events=protocol, resume=False,
                automatic_resume=False, version_supported=supported,
                protocol_validated=protocol, installed_execution_verified=installed,
                independent_review_verified=reviewed, os_evidence={})
