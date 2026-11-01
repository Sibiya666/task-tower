"""Local, shell-free interactive harness launch preparation."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import string
import stat
import tempfile

BUILTINS = ('codex', 'claude', 'opencode')
CAPABILITIES = dict(interactive_launch=True, callbacks=False, structured_events=False,
                    resume=False, independent_review=False, autonomous_merge=False)


def _state(project):
    path = project / '.task-tower'
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    reparse = (info is not None and
               getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    if path.is_symlink() or reparse:
        raise ValueError('.task-tower must not be a symlink, junction, or reparse point')
    if path.exists() and not path.is_dir():
        raise ValueError('.task-tower must be a directory')
    return path


def load_config(project: Path) -> dict | None:
    path = _state(Path(project).resolve()) / 'config.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('config.json must not be a symlink')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read local harness configuration: {exc}') from exc
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Unsupported local harness configuration')
    pin = value.get('superpowers')
    if (not isinstance(pin, dict) or not isinstance(pin.get('path'), str)
            or not isinstance(pin.get('sha256'), str) or len(pin['sha256']) != 64
            or any(c not in '0123456789abcdef' for c in pin['sha256'])):
        raise ValueError('Invalid saved Superpowers skill pin; reconfigure local settings')
    return value


def _atomic(path, text):
    # Replace directory entries rather than opening existing symlinks/hardlinks.
    _state(path.parent.parent)
    path.parent.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.bootstrap-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _descriptor(value):
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Custom adapter requires version=1')
    if not isinstance(value.get('id'), str) or not value['id'].strip():
        raise ValueError('Custom adapter requires an id')
    argv = value.get('launch_argv')
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg or '\0' in arg for arg in argv):
        raise ValueError('Custom adapter requires nonempty string launch_argv')
    caps = value.get('capabilities')
    if not isinstance(caps, dict) or caps.get('interactive_launch') is not True:
        raise ValueError('Custom adapter requires interactive_launch=true')
    for arg in argv:
        try:
            fields = list(string.Formatter().parse(arg))
        except ValueError as exc:
            raise ValueError('Invalid adapter placeholder') from exc
        if any(field is not None and (field not in ('project', 'instructions') or spec or conversion)
               for _, field, spec, conversion in fields):
            raise ValueError('Only {project} and {instructions} placeholders are allowed')
    return value


def _executable(value):
    if not isinstance(value, str) or not value or '\0' in value:
        raise ValueError('An executable is required')
    found = shutil.which(value)
    if found is None:
        raise ValueError(f'Executable not found: {value}; install it separately or use --executable')
    path = Path(found).resolve()
    if platform.system() == 'Windows' and path.suffix.lower() != '.exe':
        raise ValueError('Windows requires a native .exe executable; shims need a custom adapter with an explicit native interpreter')
    return str(path)


def prepare(project: Path, harness: str, superpowers: Path | None = None,
            adapter: Path | None = None, executable: str | None = None,
            persist: bool = True) -> dict:
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('Project directory does not exist')
    state = _state(project)
    saved = load_config(project) or {}
    harness = harness or saved.get('harness')
    if harness not in (*BUILTINS, 'custom'):
        raise ValueError('Choose codex, claude, opencode, or custom')
    skill = superpowers or saved.get('superpowers', {}).get('path')
    if skill is None:
        candidates = [project / '.agents/skills/using-superpowers/SKILL.md',
                      project / '.claude/skills/using-superpowers/SKILL.md',
                      project / '.superpowers/skills/using-superpowers/SKILL.md']
        skill = next((p for p in candidates if p.is_file()), None)
    if skill is None:
        raise ValueError('Superpowers SKILL.md required; use --superpowers PATH')
    skill = Path(skill).resolve()
    if skill.name != 'SKILL.md' or not skill.is_file():
        raise ValueError('Superpowers path must name a real SKILL.md')
    digest = hashlib.sha256(skill.read_bytes()).hexdigest()
    if superpowers is None and saved.get('superpowers', {}).get('sha256') not in (None, digest):
        raise ValueError('Superpowers skill changed; explicitly reconfigure with --superpowers')
    context = state / 'context.md'
    config = dict(version=1, harness=harness, superpowers=dict(path=str(skill), sha256=digest))
    if executable is None and harness == saved.get('harness'):
        executable = saved.get('executable')
    config['executable'] = executable
    if harness == 'custom':
        if adapter is not None:
            try:
                descriptor = json.loads(Path(adapter).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise ValueError(f'Cannot read custom adapter: {exc}') from exc
        else:
            descriptor = saved.get('adapter')
        descriptor = _descriptor(descriptor)
        # Store the explicitly trusted snapshot; changes to its source are never silently loaded.
        config['adapter'] = descriptor
        argv = [arg.format(project=str(project), instructions=str(context)) for arg in descriptor['launch_argv']]
        argv[0] = _executable(executable or argv[0])
    else:
        prompt = f'Read and follow the project bootstrap instructions at {context}'
        argv = [_executable(executable or harness)]
        if harness == 'opencode':
            argv.extend([str(project), '--prompt', prompt])
        else:
            argv.append(prompt)
    if persist:
        _atomic(context, f'# Task Tower bootstrap context\n\nProject: {project}\n\nRead and apply Superpowers: {skill}\nSHA-256: {digest}\n\nRead the project AGENTS.md and applicable instructions.\nThis context delivers instructions; it does not prove skill execution.\n')
        _atomic(state / 'config.json', json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    return dict(argv=argv, cwd=str(project), capabilities=CAPABILITIES.copy(),
                platform=platform.system(), config=config,
                note=None if persist else 'Dry run: context/config are not written; argv references the future context path.')
