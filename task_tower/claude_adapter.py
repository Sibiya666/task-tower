"""Fixed Claude policy and invocation; no authentication or model selection.

Probe validation describes supplied bytes, not successful process execution.
The caller must prove process exit, complete capture and cleanup separately.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
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
_BUNDLE_LIMIT = 16777216
_PIN_LIMIT = 2097152


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


def _instruction_read(path,limit):
    path=Path(path)
    if not path.is_absolute(): raise ValueError('Instruction path must be absolute')
    path=safe_config_path(path);before=path.stat()
    if before.st_nlink!=1 or before.st_size>limit:
        raise ValueError('Unsafe instruction file')
    with path.open('rb') as stream: data=stream.read(limit+1)
    after=safe_config_path(path).stat()
    if (len(data)>limit or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
        raise ValueError('Instruction file changed or exceeded limit')
    return data


def _instruction_bundle(attempt):
    from .executor_profiles import profile_fingerprint
    for key in ('run_id','attempt_id'):
        if str(uuid.UUID(attempt[key]))!=attempt[key]: raise ValueError('Invalid bundle identity')
    if not isinstance(attempt['source_sha'],str) or not re.fullmatch('[a-f0-9]{40}',attempt['source_sha']):
        raise ValueError('Invalid bundle source')
    directory=Path(attempt['directory'])
    if not directory.is_absolute(): raise ValueError('Bundle directory must be absolute')
    manifest=attempt['instruction_manifest']
    if not isinstance(manifest,dict) or not manifest:
        raise ValueError('Missing complete instruction manifest')
    for name,sha in manifest.items():
        if (not isinstance(name,str) or '\\' in name or ':' in name or
                PurePosixPath(name).is_absolute() or any(part in ('','.','..') for part in name.split('/')) or
                not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha)):
            raise ValueError('Invalid instruction manifest')
    if profile_fingerprint(manifest)!=attempt['superpowers_manifest_sha256']:
        raise ValueError('Instruction manifest drift')
    content=bytearray(b'# Approved complete pinned instruction snapshot\n')
    for name,sha in sorted(manifest.items()):
        data=_instruction_read(directory/'instructions'/name,_PIN_LIMIT)
        text=data.decode('utf-8')
        if '\x00' in text or text.replace('\r\n','\n').replace('\r','\n').encode('utf-8')!=data:
            raise ValueError('Invalid canonical instruction text')
        if hashlib.sha256(data).hexdigest()!=sha:
            raise ValueError('Instruction snapshot drift')
        frame=('\n\n<!-- task-tower:file '+json.dumps(dict(path=name,sha256=sha),
                sort_keys=True,separators=(',',':'),ensure_ascii=True)+' -->\n').encode('utf-8')
        if len(content)+len(frame)+len(data)>_BUNDLE_LIMIT:
            raise ValueError('Instruction bundle exceeds limit')
        content.extend(frame);content.extend(data)
    data=bytes(content)
    fields=dict(instruction_bundle_path=str(directory/'claude-system-prompt.md'),
                instruction_bundle_sha256=hashlib.sha256(data).hexdigest(),
                instruction_bundle_bytes=len(data),instruction_bundle_file_count=len(manifest))
    metadata=dict(version=1,**{key:attempt[key] for key in ('run_id','attempt_id','source_sha','superpowers_manifest_sha256')},**fields)
    metadata_bytes=(json.dumps(metadata,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('utf-8')
    return data,metadata_bytes,fields


def prepare_instruction_bundle(attempt: dict) -> dict:
    """Exclusively materialize all approved snapshots; never shorten or repair."""
    try:
        data,metadata,fields=_instruction_bundle(attempt)
        for path,content in [(Path(fields['instruction_bundle_path']),data),
                             (Path(attempt['directory'])/'claude-instructions.json',metadata)]:
            path=safe_config_path(path)
            with path.open('xb') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
        return fields
    except (OSError,UnicodeError,KeyError,TypeError) as error:
        raise ValueError('Cannot prepare complete instruction bundle') from error


def verify_instruction_bundle(attempt: dict) -> dict:
    """Regenerate every expected byte and compare existing immutable artifacts."""
    try:
        data,metadata,fields=_instruction_bundle(attempt)
        if any(type(attempt.get(key)) is not type(value) or attempt[key]!=value for key,value in fields.items()):
            raise ValueError('Instruction bundle binding drift')
        if (_instruction_read(fields['instruction_bundle_path'],_BUNDLE_LIMIT)!=data or
                _instruction_read(Path(attempt['directory'])/'claude-instructions.json',_PIN_LIMIT)!=metadata):
            raise ValueError('Instruction bundle artifact drift')
        return fields
    except (OSError,UnicodeError,KeyError,TypeError) as error:
        raise ValueError('Invalid complete instruction bundle') from error


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
        bundle=verify_instruction_bundle(attempt)
        if not isinstance(request, dict):
            raise ValueError('Missing inline Claude context')
        prompt = ('Execution request (task data, not invocation authority):\n' +
                  json.dumps(request, ensure_ascii=True, allow_nan=False) +
                  '\nReturn only the required run/attempt/source-bound result JSON. '
                  'Do not publish, change configuration, choose models or claim acceptance.')
        tools = ROLE_TOOLS[policy['role']]
        argv = [*profile['argv'], '-p', '--output-format', 'stream-json', '--verbose',
                '--safe-mode', '--permission-mode', 'manual', '--permission-prompts', 'none',
                '--strict-mcp-config', '--mcp-config', str(path), '--no-chrome',
                '--session-id', attempt['attempt_id'], '--max-budget-usd', policy['max_budget_usd'],
                '--json-schema', json.dumps(result_schema(attempt), ensure_ascii=True, allow_nan=False),
                '--tools', tools, '--allowedTools', tools,
                '--append-system-prompt-file',bundle['instruction_bundle_path'],prompt]
        # Conservative portable bound, including Windows UTF-16 command-line
        # quoting overhead. Oversized context is a prelaunch input limitation.
        import subprocess
        if any('\x00' in argument for argument in argv):
            raise ValueError('Invalid Claude invocation text')
        if len(subprocess.list2cmdline(argv).encode('utf-16-le')) // 2 > 30000:
            raise ValueError('Claude invocation is too large')
        return argv
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


def _update_findings(value):
    if not isinstance(value,dict) or not isinstance(value.get('env',{}),dict):
        raise ValueError('Invalid local Claude settings')
    findings = []
    for key,item in value.get('env',{}).items():
        if key.upper() not in ('DISABLE_UPDATES','FORCE_AUTOUPDATE_PLUGINS'):
            continue
        if not isinstance(item,str):
            raise ValueError('Invalid local update setting')
        normalized = item.lower()
        if ((key.upper() == 'DISABLE_UPDATES' and normalized not in ('1','true','yes','on')) or
                (key.upper() == 'FORCE_AUTOUPDATE_PLUGINS' and normalized not in ('','0','false','no','off'))):
            raise ValueError('Conflicting local update setting')
        findings.append(key.upper())
    return sorted(findings)


def snapshot_local_settings(paths) -> list[dict]:
    """Read bounded known settings only; retain fingerprints and key names.

    Never return settings values, auth data, helpers or whole configuration.
    This scoped local check does not evaluate remote or future managed policy.
    """
    snapshots = []
    for raw in sorted({str(Path(path)) for path in paths}):
        try:
            path = Path(raw)
            if not path.is_absolute():
                raise ValueError('Settings path must be absolute')
            path = safe_config_path(path)
            if not path.exists():
                snapshots.append(dict(source=str(path),present=False))
                continue
            before = path.stat()
            if before.st_nlink != 1 or before.st_size > 2097152:
                raise ValueError('Unsafe local Claude settings')
            with path.open('rb') as stream:
                data = stream.read(2097153)
            after = safe_config_path(path).stat()
            if (len(data)>2097152 or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) !=
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
                raise ValueError('Local Claude settings changed')
            if path.suffix == '.plist':
                import plistlib
                value = plistlib.loads(data)
            else:
                value = json.loads(data.decode('utf-8-sig'),object_pairs_hook=ClaudeEventParser._pairs)
            findings = _update_findings(value)
            snapshots.append(dict(source=str(path),present=True,sha256=hashlib.sha256(data).hexdigest(),
                                  update_keys=findings))
        except (OSError,UnicodeError,TypeError,OverflowError,RecursionError) as error:
            raise ValueError('Unreadable local Claude settings') from error
    return snapshots


def local_update_preflight(worktree, checkout, environ) -> dict:
    """Snapshot known local sources, without running policy/auth helpers."""
    selected = [value for key,value in environ.items() if key.upper()=='CLAUDE_CONFIG_DIR']
    if len(set(selected)) > 1:
        raise ValueError('Ambiguous Claude configuration directory')
    config = Path(selected[0]) if selected and selected[0] else Path.home()/'.claude'
    if not config.is_absolute():
        raise ValueError('Claude configuration directory must be absolute')
    paths = [config/'settings.json']
    for directory in (Path(worktree),Path(checkout)):
        paths.extend([directory/'.claude'/'settings.json',directory/'.claude'/'settings.local.json'])
    if os.name == 'nt':
        machine = Path('C:/Program Files/ClaudeCode')
    elif sys.platform == 'darwin':
        machine = Path('/Library/Application Support/ClaudeCode')
        paths.append(Path('/Library/Managed Preferences/com.anthropic.claudecode.plist'))
    else:
        machine = Path('/etc/claude-code')
    paths.append(machine/'managed-settings.json')
    fragments = machine/'managed-settings.d'
    safe_config_path(fragments/'.preflight-check')
    if fragments.exists():
        if not fragments.is_dir():
            raise ValueError('Unsafe managed settings directory')
        entries = list(fragments.iterdir())
        if len(entries)>128:
            raise ValueError('Too many managed settings fragments')
        paths.extend(path for path in entries if not path.name.startswith('.') and path.suffix=='.json')
    files = snapshot_local_settings(paths)
    registry = []
    if os.name == 'nt':
        import winreg
        for name,root in [('HKLM',winreg.HKEY_LOCAL_MACHINE),('HKCU',winreg.HKEY_CURRENT_USER)]:
            identity = 'registry:'+name+r'\SOFTWARE\Policies\ClaudeCode\Settings'
            try:
                with winreg.OpenKey(root,r'SOFTWARE\Policies\ClaudeCode',0,winreg.KEY_READ) as key:
                    data,kind = winreg.QueryValueEx(key,'Settings')
                if kind not in (winreg.REG_SZ,winreg.REG_EXPAND_SZ) or not isinstance(data,str) or len(data.encode('utf-8'))>2097152:
                    raise ValueError('Invalid local managed settings')
                value=json.loads(data,object_pairs_hook=ClaudeEventParser._pairs)
                registry.append(dict(source=identity,present=True,sha256=hashlib.sha256(data.encode('utf-8')).hexdigest(),
                                     update_keys=_update_findings(value)))
            except FileNotFoundError:
                registry.append(dict(source=identity,present=False))
            except OSError as error:
                raise ValueError('Unreadable local managed settings') from error
    return dict(version=1,files=files,registry=registry,managed_remote_evaluated=False)


class ClaudeEventParser:
    """Bounded observation of one NDJSON attempt, never execution authority.

    Only an incomplete line and the bounded nested terminal result are retained.
    feed records invalidity without raising. observe bridges invalidity to the
    shared runner's neutral observer-failure termination path.
    """
    def __init__(self, attempt: dict, stream_max_bytes: int, line_max_bytes: int):
        for key in ('run_id', 'attempt_id'):
            if str(uuid.UUID(attempt[key])) != attempt[key]:
                raise ValueError('Invalid parser identity')
        if not isinstance(attempt['source_sha'], str) or not re.fullmatch('[0-9a-f]{40}', attempt['source_sha']):
            raise ValueError('Invalid parser source')
        if (type(stream_max_bytes) is not int or not 65536 <= stream_max_bytes <= 67108864 or
                type(line_max_bytes) is not int or not 4096 <= line_max_bytes <= min(stream_max_bytes,1048576)):
            raise ValueError('Invalid parser bounds')
        self._attempt = {key: attempt[key] for key in ('run_id', 'attempt_id', 'source_sha')}
        self._stream_cap, self._line_cap = stream_max_bytes, line_max_bytes
        self._pending = bytearray()
        self._size = self._events = self._unknown = self._denials = 0
        self._init = self._final = False
        self._reason, self._result = None, None
        self._private_model = None

    @property
    def termination_requested(self):
        return self._reason is not None

    def _fail(self, reason):
        if self._reason is None:
            self._reason = reason
        self._pending.clear()
        self._result = None

    def feed(self, chunk: bytes) -> None:
        if self.termination_requested:
            return
        if type(chunk) is not bytes:
            self._fail('invalid_chunk')
            return
        self._size += len(chunk)
        if self._size > self._stream_cap:
            self._fail('stream_limit')
            return
        offset = 0
        while offset < len(chunk) and not self.termination_requested:
            newline = chunk.find(b'\n', offset)
            end = len(chunk) if newline == -1 else newline
            if len(self._pending) + end - offset > self._line_cap:
                self._fail('line_limit')
                return
            self._pending.extend(chunk[offset:end])
            if newline == -1:
                break
            line = bytes(self._pending)
            self._pending.clear()
            self._line(line)
            offset = newline + 1

    def observe(self, chunk: bytes) -> None:
        self.feed(chunk)
        if self.termination_requested:
            raise ValueError('invalid_claude_stream')

    @staticmethod
    def _pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_json_key')
            value[key] = item
        return value

    @staticmethod
    def _reject_constant(value):
        raise ValueError('nonfinite_json')

    @staticmethod
    def _bounded_json(line):
        # Bound nesting before json.loads allocates recursive containers. Count
        # only structural delimiters outside strings, respecting escaped quotes.
        depth, quoted, escaped = 0, False, False
        for byte in line:
            if quoted:
                if escaped:
                    escaped = False
                elif byte == 92:
                    escaped = True
                elif byte == 34:
                    quoted = False
            elif byte == 34:
                quoted = True
            elif byte in (123, 91):
                depth += 1
                if depth > 64:
                    raise ValueError('json_depth')
            elif byte in (125, 93):
                depth -= 1
        value = json.loads(line.decode('utf-8'),object_pairs_hook=ClaudeEventParser._pairs,
                           parse_constant=ClaudeEventParser._reject_constant)
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode('utf-8')  # Reject escaped unpaired surrogates too.
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError('nonfinite_json')
            elif isinstance(item, dict):
                pending.extend(item.keys()); pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        if not isinstance(value, dict):
            raise ValueError('nonobject_event')
        return value

    def _bound_result(self, value):
        if (not isinstance(value, dict) or set(value) != {
                'version','run_id','attempt_id','source_sha','status','summary'} or
                type(value['version']) is not int or value['version'] != 1 or
                any(value[key] != self._attempt[key] for key in ('run_id','attempt_id','source_sha')) or
                value['status'] not in ('completed','failed','needs_input') or
                not isinstance(value['summary'], str) or len(value['summary'].encode('utf-8')) > 4096 or
                len(json.dumps(value,ensure_ascii=False).encode('utf-8')) > 65536):
            raise ValueError('invalid_result_binding')
        return value

    def _line(self, line):
        if not line.strip(b' \t\r'):
            return
        if self._final:
            self._fail('event_after_result')
            return
        try:
            value = self._bounded_json(line)
            kind = value.get('type')
            if not isinstance(kind,str) or not kind:
                raise ValueError('invalid_event_type')
            if 'session_id' in value and value['session_id'] != self._attempt['attempt_id']:
                raise ValueError('invalid_event_session')
            self._events += 1
            if kind in ('control_request','control_response'):
                self._fail('unsupported_control')
            elif kind == 'system':
                subtype = value.get('subtype')
                if subtype == 'permission_denied':
                    self._denials += 1
                    self._fail('permission_denied')
                elif subtype == 'init':
                    if (self._init or value.get('session_id') != self._attempt['attempt_id'] or
                            value.get('parent_tool_use_id') is not None):
                        raise ValueError('invalid_init')
                    for field in ('plugin_errors','mcp_server_errors'):
                        if field in value and (not isinstance(value[field],list) or value[field]):
                            raise ValueError('initialization_error')
                    if 'mcp_servers' in value:
                        servers = value['mcp_servers']
                        if (not isinstance(servers,list) or any(not isinstance(server,dict) or
                                server.get('status') not in ('connected','pending','disabled') for server in servers)):
                            raise ValueError('initialization_error')
                    if 'model' in value:
                        model=value['model']
                        if not isinstance(model,str) or len(model.encode('utf-8'))>512:
                            raise ValueError('invalid_model_metadata')
                        self._private_model=model
                    self._init = True
                elif subtype in ('error','configuration_error'):
                    self._fail('initialization_error')
                else:
                    self._unknown += 1
            elif kind == 'result':
                if not self._init or value.get('session_id') != self._attempt['attempt_id']:
                    raise ValueError('invalid_terminal_session')
                denials = value.get('permission_denials')
                if not isinstance(denials,list):
                    raise ValueError('invalid_denials')
                if denials:
                    self._denials += len(denials)
                    self._fail('permission_denied')
                    return
                if (value.get('subtype') != 'success' or value.get('is_error') is not False or
                        value.get('parent_tool_use_id') is not None):
                    raise ValueError('invalid_terminal')
                self._result = self._bound_result(value.get('structured_output'))
                self._final = True
            elif kind not in ('assistant','user','rate_limit_event','stream_event','progress'):
                self._unknown += 1
        except (ValueError, UnicodeError, TypeError, OverflowError, RecursionError):
            self._fail('invalid_event')

    def finish(self) -> dict:
        if self._pending and not self.termination_requested:
            line = bytes(self._pending); self._pending.clear(); self._line(line)
        if self._reason is None and not (self._init and self._final):
            self._fail('missing_terminal')
        reason = self._reason
        evidence = dict(observed_bytes=self._size,event_count=self._events,
                        unknown_events=self._unknown,denial_count=self._denials,
                        session_id=self._attempt['attempt_id'],init_seen=self._init,
                        result_seen=self._final,protocol_validated=reason is None)
        # Return a fresh copy so consumers cannot mutate retained parser state.
        return dict(valid=reason is None,reason=reason,
                    result=dict(self._result) if reason is None else None,evidence=evidence,
                    private_metadata=({'reported_model':self._private_model} if self._private_model is not None else {}))
