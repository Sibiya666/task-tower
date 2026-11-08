"""Conservative, Git-object-only prose CI routing.

Local links are a deliberately small Markdown subset, not a CommonMark renderer
or external URL checker. No link is opened on the filesystem or network.
"""
import argparse
import io
import json
from pathlib import Path
import posixpath
import re
import tempfile
import time
import unicodedata
from urllib.parse import unquote

from .processes import run_command

MAX_SECONDS = 30
MAX_PROSE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
# Conservative parser limits refuse validation; they never discard excess links.
MAX_DESTINATION_CHARS = 4096
MAX_PATH_CHARS = 4096
MAX_ANCESTOR_DEPTH = 128
MAX_MARKDOWN_LINE_CHARS = 65536
MAX_PARSER_ITEMS = 100000
_OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


class DocumentationError(ValueError):
    """Source facts, supported links or resource limits refused validation."""


def _safe_path(path):
    return (bool(path) and not path.startswith('/') and '\\' not in path
            and all(not unicodedata.category(c).startswith('C') for c in path)
            and all(p not in ('', '.', '..') and not p.startswith('.') for p in path.split('/')))


def _prose(path):
    return (_safe_path(path) and (path in ('README.md', 'AGENTS.md')
            or (path.startswith('docs/') and path.endswith('.md')
                and not path.startswith('docs/templates/'))))


class _Source:
    def __init__(self, repo):
        self.repo = str(Path(repo).absolute())
        self.deadline = time.monotonic() + MAX_SECONDS
        self.cache = {}
        self.blob_sizes = {}
        self.prose_bytes = 0
        self.capture_bytes = 0

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise DocumentationError('resource_limit')
        return remaining

    def git(self, *args, cap=MAX_OUTPUT_BYTES):
        # Capture drains retain bounded prefixes, rather than communicate()'s
        # unbounded allocation. Supervisor kills/reaps the whole process tree.
        import os
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith('GIT_') and k.upper() not in ('GH_TOKEN', 'GITHUB_TOKEN')}
        env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
                   GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
                   GIT_CONFIG_GLOBAL=os.devnull)
        cap = min(cap, (MAX_CAPTURE_BYTES-self.capture_bytes)//2)
        remaining = self.remaining()
        if cap <= 0 or remaining <= 5:
            raise DocumentationError('resource_limit')
        with tempfile.TemporaryDirectory(prefix='ci-docs-') as directory:
            result = run_command(['git', '-C', self.repo, '-c', 'core.quotePath=false', *args], self.repo,
                                 remaining - 5,
                                 env=env, capture={'directory': directory, 'max_bytes_per_stream': max(1, cap)})
            self.remaining()
            self.capture_bytes += result.get('stdout_bytes', 0) + result.get('stderr_bytes', 0)
            if (result.get('status') != 'passed' or not result.get('cleanup_confirmed')
                    or result.get('stdout_truncated') or result.get('stderr_truncated')
                    or result.get('stdout_bytes', cap+1) > cap):
                raise DocumentationError('git_or_resource_error')
            return (Path(directory)/'stdout.log').read_bytes()

    def blob(self, oid, *, size=None):
        if size is not None and (type(size) is not int or size < 0):
            raise DocumentationError('malformed_blob_size')
        if oid in self.cache:
            if size is not None and size != self.blob_sizes[oid]:
                raise DocumentationError('malformed_blob_size')
            return self.cache[oid]
        if oid not in self.cache:
            remaining = MAX_PROSE_BYTES - self.prose_bytes
            if size is None:
                size = int(self.git('cat-file', '-s', oid, cap=64))
            if size < 0 or size > remaining:
                raise DocumentationError('prose_limit')
            data = self.git('cat-file', 'blob', oid, cap=max(1, size))
            if len(data) != size:
                raise DocumentationError('malformed_blob')
            self.prose_bytes += size
            self.cache[oid] = data.decode('utf-8', errors='strict')
            self.blob_sizes[oid] = size
        return self.cache[oid]


def _classify(source):
    report = dict(mode='full', head=None, base=None, reason='unknown_source', changed_paths=[])
    try:
        head = source.git('rev-parse', '--verify', 'HEAD^{commit}', cap=128).decode('ascii').strip()
        if not _OID.fullmatch(head):
            raise DocumentationError('malformed_head')
        report['head'] = head
        commit = source.git('cat-file', 'commit', head)
        header = commit.split(b'\n\n', 1)[0].splitlines()
        parents = [line[7:].decode('ascii') for line in header if line.startswith(b'parent ')]
        if parents:
            report['base'] = parents[0]
        if len(parents) != 2 or not all(_OID.fullmatch(p) for p in parents):
            report['reason'] = 'not_normal_merge'
            return report
        for parent in parents:
            if source.git('cat-file', '-t', parent, cap=32) != b'commit\n':
                raise DocumentationError('missing_parent')
        raw = source.git('diff', '--raw', '-z', '--no-renames', '--no-ext-diff', '--no-textconv', '--abbrev=64', parents[0], head, '--')
        if not raw:
            report['reason'] = 'empty_change'
            return report
        fields = raw.split(b'\0')
        if fields.pop() != b'' or len(fields) % 2:
            raise DocumentationError('malformed_diff')
        eligible = True
        for metadata, name in zip(fields[::2], fields[1::2]):
            source.remaining()
            bits = metadata.decode('ascii').split(' ')
            if (len(bits) != 5 or not re.fullmatch(r':[0-7]{6}', bits[0])
                    or not re.fullmatch(r'[0-7]{6}', bits[1])
                    or not all(_OID.fullmatch(x) for x in bits[2:4])
                    or bits[4] not in ('A', 'M', 'D', 'T')):
                raise DocumentationError('malformed_diff')
            path = name.decode('utf-8', errors='strict')
            report['changed_paths'].append(path)
            old, new = bits[0][1:], bits[1]
            valid_modes = ((old, new) == ('000000', '100644') if bits[4] == 'A' else
                           (old, new) == ('100644', '000000') if bits[4] == 'D' else
                           (old, new) == ('100644', '100644') and bits[4] == 'M')
            eligible = eligible and _prose(path) and valid_modes
        report.update(mode='docs' if eligible else 'full', reason='regular_prose_only' if eligible else 'non_prose_change')
    except (DocumentationError, OSError, UnicodeError, ValueError):
        report.update(mode='full', reason='source_unavailable_or_malformed')
    return report


def classify(repo='.'):
    """Return actual source routing; every uncertainty selects full checks."""
    return _classify(_Source(repo))


def _without_code(text, checkpoint):
    lines, fence = [], None
    items = 0
    for line in io.StringIO(text):
        checkpoint()
        items += 1
        if items > MAX_PARSER_ITEMS or len(line) > MAX_MARKDOWN_LINE_CHARS:
            raise DocumentationError('markdown_parser_limit')
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append('\n')
        elif marker:
            fence = marker[1]
            lines.append('\n')
        else:
            lines.append(line)
    text = ''.join(lines)
    # Pair exact-length backtick runs in linear scanning; unmatched runs remain.
    runs = []
    for run in re.finditer(r'`+', text):
        checkpoint()
        items += 1
        if items > MAX_PARSER_ITEMS:
            raise DocumentationError('markdown_parser_limit')
        runs.append(run)
    checkpoint()
    next_run, pairs = {}, {}
    for run in reversed(runs):
        checkpoint()
        length = run.end()-run.start()
        if length in next_run:
            pairs[run.start()] = next_run[length]
        next_run[length] = run
    out, end = [], 0
    for run in runs:
        checkpoint()
        if run.start() < end or run.start() not in pairs:
            continue
        out.append(text[end:run.start()])
        close = pairs[run.start()]
        end = close.end()
        out.append(' ')
    out.append(text[end:])
    return ''.join(out)


def _destination(text, start, inline, checkpoint):
    """Read angle or balanced bare destinations, including escaped parens."""
    checkpoint()
    origin = start
    while start < len(text) and text[start].isspace():
        if text[start] in '\r\n':
            return None, start+1
        if start-origin >= MAX_DESTINATION_CHARS:
            raise DocumentationError('destination_limit')
        if (start-origin) % 256 == 0:
            checkpoint()
        start += 1
    angle = start < len(text) and text[start] == '<'
    if angle:
        start += 1
    chars, depth, index = [], 0, start
    while index < len(text):
        if index-origin >= MAX_DESTINATION_CHARS:
            raise DocumentationError('destination_limit')
        if (index-origin) % 256 == 0:
            checkpoint()
        char = text[index]
        if char in '\r\n':
            return (None if angle else ''.join(chars).strip()), index+1
        if char == '\\' and index+1 < len(text):
            if text[index+1] in '\r\n':
                return None, index+2
            chars.extend(text[index:index+2])
            index += 2
            continue
        if angle and char == '>':
            return ''.join(chars), index+1
        if not angle:
            if char == '(':
                depth += 1
            elif char == ')':
                if depth == 0:
                    return ''.join(chars).strip(), index+1
                depth -= 1
            if char in '\r\n' or (not inline and char.isspace() and depth == 0):
                return ''.join(chars).strip(), index+1
            if char.isspace() and index+1 < len(text) and text[index+1] in ('"', "'") and depth == 0:
                return ''.join(chars).strip(), index+1
        chars.append(char)
        index += 1
    return (''.join(chars).strip() if not angle and not inline else None), index


def _links(text, checkpoint):
    checkpoint()
    text = _without_code(text, checkpoint)
    # Definitions are destinations even when their labels are currently unused.
    for line in io.StringIO(text):
        checkpoint()
        match = re.match(r'^ {0,3}\[[^\]\n]+\]:', line)
        if match is None:
            continue
        value, _ = _destination(line, match.end(), False, checkpoint)
        if value is not None:
            yield value
    index = 0
    while index < len(text):
        if index % 256 == 0:
            checkpoint()
        if text[index] == '\\':
            index += 2
            continue
        if text[index:index+2] == '](':
            value, end = _destination(text, index+2, True, checkpoint)
            if value is not None:
                yield value
            index = end
            continue
        index += 1
    checkpoint()


def _target(referrer, destination):
    if len(destination) > MAX_DESTINATION_CHARS:
        raise DocumentationError('destination_limit')
    value = re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', r'\1', destination)
    if not value or value.startswith('#') or value.startswith('//') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value):
        return None
    value = unquote(value.split('#', 1)[0].split('?', 1)[0], encoding='utf-8', errors='strict')
    if not value:
        return None
    if value.startswith('/'):
        value = value[1:]
        resolved = posixpath.normpath(value)
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(referrer), value))
    if len(resolved) > MAX_PATH_CHARS:
        raise DocumentationError('path_limit')
    if '\\' in resolved or any(unicodedata.category(c).startswith('C') for c in resolved):
        return '!invalid:' + resolved
    return resolved


def _broken(source, revision):
    raw = source.git('ls-tree', '-r', '-t', '-l', '-z', '--full-tree', revision)
    entries = {'.': ('040000', 'tree', revision, None)}
    if raw and not raw.endswith(b'\0'):
        raise DocumentationError('malformed_tree')
    for record in raw.split(b'\0')[:-1]:
        source.remaining()
        metadata, name = record.split(b'\t', 1)
        fields = metadata.decode('ascii').split()
        if len(fields) != 4:
            raise DocumentationError('malformed_tree')
        mode, kind, oid, advertised_size = fields
        if kind == 'blob' and re.fullmatch(r'(?:0|[1-9][0-9]{0,19})', advertised_size):
            size = int(advertised_size)
        elif kind in ('tree', 'commit') and advertised_size == '-':
            size = None
        else:
            raise DocumentationError('malformed_tree')
        path = name.decode('utf-8', errors='strict')
        if len(path) > MAX_PATH_CHARS:
            raise DocumentationError('path_limit')
        if not _OID.fullmatch(oid) or mode not in ('100644', '100755', '120000', '160000', '040000'):
            raise DocumentationError('malformed_tree')
        entries[path] = (mode, kind, oid, size)
    broken, count = set(), 0
    for path, (mode, kind, oid, size) in entries.items():
        source.remaining()
        # All regular tracked Markdown can refer to a changed target, even
        # outside the deliberately narrow fast-classification allowlist.
        if mode not in ('100644', '100755') or kind != 'blob' or not path.endswith('.md'):
            continue
        # ls-tree supplies the size of this immutable Git object. Retain the
        # bounded content read and exact byte check without a second process
        # for cat-file -s on every unique Markdown blob.
        for destination in _links(source.blob(oid, size=size), source.remaining):
            source.remaining()
            target = _target(path, destination)
            if target is None:
                continue
            count += 1
            if (target not in entries or target == '..' or target.startswith('../')
                    or entries[target][0] in ('120000', '160000')):
                broken.add((path, target))
                continue
            if target.count('/') > MAX_ANCESTOR_DEPTH:
                raise DocumentationError('ancestor_depth_limit')
            slash = target.find('/')
            while slash != -1:
                source.remaining()
                if entries.get(target[:slash], ('',))[0] != '040000':
                    broken.add((path, target))
                    break
                slash = target.find('/', slash+1)
    return broken, count


def validate(repo='.', *, repository, pr_number, phase):
    """Recompute classification and refuse anything short of proven docs pass."""
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
            or type(pr_number) is not int or pr_number <= 0 or phase not in ('pr', 'postmerge')):
        raise DocumentationError('invalid_identity')
    source = _Source(repo)
    report = _classify(source)
    if report['mode'] != 'docs':
        raise DocumentationError('not_documentation_scope')
    try:
        source.git('diff', '--check', '--no-ext-diff', '--no-textconv', report['base'], report['head'], '--')
        baseline, _ = _broken(source, report['base'])
        current, checked = _broken(source, report['head'])
        if current - baseline:
            raise DocumentationError('new_broken_local_links')
        source.remaining()
    except (OSError, UnicodeError, ValueError) as error:
        raise DocumentationError('documentation_validation_failed') from error
    return dict(version=1, kind='documentation.validation', mode='docs', head=report['head'],
                base=report['base'], repository=repository, pr_number=pr_number, phase=phase,
                checks='passed', runtime_tests='not_run', validation='whitespace_and_new_local_links',
                local_links_checked=checked, historical_broken_links=len(baseline), prose_bytes=source.prose_bytes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--scope', action='store_true')
    mode.add_argument('--validate', action='store_true')
    parser.add_argument('--report', required=True)
    parser.add_argument('--github-output')
    parser.add_argument('--repository')
    parser.add_argument('--pr', type=int)
    parser.add_argument('--phase', choices=('pr', 'postmerge'))
    args = parser.parse_args(argv)
    try:
        if args.scope:
            if not args.github_output:
                parser.error('--scope requires --github-output')
            report = classify()
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(report, ensure_ascii=True)+'\n', encoding='utf-8')
            with Path(args.github_output).open('a', encoding='utf-8', newline='\n') as output:
                output.write('mode=docs\n' if report['mode'] == 'docs' else 'mode=full\n')
        else:
            if args.repository is None or args.pr is None or args.phase is None:
                parser.error('--validate requires --repository, --pr and --phase')
            report = validate(repository=args.repository, pr_number=args.pr, phase=args.phase)
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(report, ensure_ascii=True)+'\n', encoding='utf-8')
    except (DocumentationError, OSError):
        parser.exit(1, 'documentation validation/source/output refused\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
