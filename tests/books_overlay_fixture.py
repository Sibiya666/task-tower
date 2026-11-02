"""Network-free real producer fixture shared by Python/native/Edge regressions."""
import hashlib
import json
from pathlib import Path
import tempfile

from task_tower.books import aggregate
from task_tower.github_tasks import replace_metadata, parse_metadata
from task_tower.overlay_books import _public
from task_tower.project_connections import ProjectConnection
from tests.test_book_projection import Store

STATUSES = ('open', 'in_progress', 'needs_input', 'awaiting_merge', 'awaiting_postmerge', 'postmerge_review', 'postmerge_failed')


def projection():
    with tempfile.TemporaryDirectory(prefix='PRIVATE-books-projection-') as directory:
        root = Path(directory).resolve()
        source = root / 'PRIVATE-card.json'
        raw = b'{"id":"private-original","title":"PRIVATE-CONTENT"}'
        source.write_bytes(raw)
        registry = root / '.task-tower' / 'capture-migrations.json'
        registry.parent.mkdir()
        registry.write_text(json.dumps(dict(version=1, records=[dict(repository='a/b', repository_id='123', legacy_id='private-original', source_path=str(source), source_sha256=hashlib.sha256(raw).hexdigest(), issue_url='https://github.com/a/b/issues/1', number=1, at='2026-11-01T00:00:00Z')])), encoding='utf-8')
        class ProjectionStore(Store):
            def metadata(self, issue): return parse_metadata(issue["body"])
            def list_issues(self):
                return [dict(number=i, title=status, body=replace_metadata('Public text', dict(version=1, kind='task', status=status)), state='closed' if i == 1 else 'open') for i, status in enumerate(STATUSES, 1)]
        report = aggregate([ProjectConnection('p', 'a/b', root, 'runner')], store_factory=lambda c: ProjectionStore())
        return dict(_public(report), sequence=1, final=True)


def escaped_library_projection():
    from types import SimpleNamespace
    from task_tower.book_library import project_library
    names=['docs/ordinary.md','docs/a#b.md','docs/a?b.md','docs/100%.md',"docs/a!()'*~.md",'docs/Ю space.md','docs/a%2fb.md','docs/a%252e.md','docs/🚀 space.md','docs/a\u0085.md','docs/a\u009f.md','docs/after.md']
    store=SimpleNamespace(library=lambda:[dict(path=p,commit='a'*40) for p in names],library_index=lambda c:None)
    rows,errors=project_library(SimpleNamespace(repository='a/b',id='p'),store)
    return dict(_public(dict(entries=rows,errors=errors,fetched_at='2026-11-02T00:00:00Z')),sequence=1,final=True)


if __name__ == '__main__':
    print(json.dumps(projection(), ensure_ascii=True))
