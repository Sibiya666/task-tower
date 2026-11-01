"""Durable, process-safe postmerge review claims; interrupted runs stay claimed."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3

from .tasks import _safe_path


class Journal:
    def __init__(self, path: Path):
        self.path = _safe_path(Path(path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS reviews (
                task_id TEXT NOT NULL, "commit" TEXT NOT NULL,
                snapshot TEXT NOT NULL, status TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '', result TEXT,
                PRIMARY KEY (task_id, "commit"))''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(_safe_path(self.path), timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _key(task_id, commit):
        if (not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 256
                or any(ord(char) < 32 for char in task_id)):
            raise ValueError('Invalid task ID')
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-fA-F]{7,40}|[0-9a-fA-F]{64}', commit):
            raise ValueError('Invalid commit hash')
        return task_id, commit.lower()

    @staticmethod
    def _row(row):
        if row is None:
            return None
        result = dict(row)
        result['result'] = json.loads(result['result']) if result['result'] else None
        return result

    def get(self, task_id: str, commit: str) -> dict | None:
        with self._connect() as db:
            return self._row(db.execute('SELECT * FROM reviews WHERE task_id=? AND "commit"=?',
                                        self._key(task_id, commit)).fetchone())

    def claim(self, task_id: str, commit: str, snapshot: str) -> bool:
        key = self._key(task_id, commit)
        if not isinstance(snapshot, str):
            raise ValueError('Snapshot must be text')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            cursor = db.execute('''INSERT INTO reviews(task_id,"commit",snapshot,status)
                VALUES(?,?,?,'running') ON CONFLICT(task_id,"commit") DO UPDATE SET
                snapshot=excluded.snapshot,status='running',detail='',result=NULL
                WHERE reviews.status IN ('waiting','blocked')''', (*key, snapshot))
            return cursor.rowcount == 1

    def save_review(self, task_id: str, commit: str, result: dict) -> None:
        key = self._key(task_id, commit)
        if not isinstance(result, dict):
            raise ValueError('Review result must be an object')
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False)
        with self._connect() as db:
            cursor = db.execute('''UPDATE reviews SET status='reviewed',result=?,detail=''
                WHERE task_id=? AND "commit"=? AND status='running' ''', (payload, *key))
            if cursor.rowcount != 1:
                raise ValueError('Review requires a running claim')

    def finish(self, task_id: str, commit: str, status: str, detail: str = '') -> None:
        key = self._key(task_id, commit)
        if status not in ('done', 'needs_input', 'blocked', 'waiting') or not isinstance(detail, str):
            raise ValueError('Invalid journal outcome')
        with self._connect() as db:
            cursor = db.execute('''UPDATE reviews SET status=?,detail=?
                WHERE task_id=? AND "commit"=?''', (status, detail, *key))
            if cursor.rowcount != 1:
                raise ValueError('Missing journal claim')

    def rows(self) -> list[dict]:
        with self._connect() as db:
            rows = [self._row(row) for row in db.execute('SELECT * FROM reviews ORDER BY task_id,"commit"')]
            if db.execute("SELECT name FROM sqlite_master WHERE name='publication_receipts'").fetchone():
                for publication in db.execute('SELECT p.*, r.payload FROM publications p JOIN publication_receipts r ON p.identity=r.identity ORDER BY p.rowid'):
                    receipt=json.loads(publication['payload'])
                    for row in rows:
                        if row['task_id']==receipt['task_id'] and row['commit']==receipt['commit']:
                            row['publication']={k:publication[k] for k in ('identity','status','detail')}
            return rows

    def retry(self, task_id: str, commit: str) -> None:
        key = self._key(task_id, commit)
        with self._connect() as db:
            cursor = db.execute('''UPDATE reviews SET status='waiting',detail='',result=NULL
                WHERE task_id=? AND "commit"=? AND status NOT IN ('running','done')''', key)
            if cursor.rowcount != 1:
                raise ValueError('Retry requires an existing non-running, non-done claim')

    def recover(self, task_id: str, commit: str, confirm_stopped: bool = False) -> None:
        """Release an interrupted claim only after operator verifies reviewer termination."""
        key = self._key(task_id, commit)
        if confirm_stopped is not True:
            raise ValueError('Recovery requires confirmation that the prior reviewer stopped')
        with self._connect() as db:
            cursor = db.execute('''UPDATE reviews SET status='waiting',detail='',result=NULL
                WHERE task_id=? AND "commit"=? AND status='running' ''', key)
            if cursor.rowcount != 1:
                raise ValueError('Recovery requires an existing running claim')

    def claim_publication(self, identity, owner, now=None, lease_seconds=300):
        import time
        now = time.time() if now is None else now
        if not isinstance(identity, str) or not identity or not owner or not 120 <= lease_seconds <= 3600:
            raise ValueError('Invalid publication claim')
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS publications (
                identity TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,
                lease REAL NOT NULL, detail TEXT NOT NULL DEFAULT '')''')
            db.execute('BEGIN IMMEDIATE')
            cursor = db.execute('''INSERT INTO publications VALUES(?,?,'publishing',?,'')
                ON CONFLICT(identity) DO UPDATE SET owner=excluded.owner,status='publishing',
                lease=excluded.lease,detail='' WHERE publications.status != 'published'
                AND (publications.status != 'publishing' OR publications.lease <= ?)''',
                (identity, owner, now + lease_seconds, now))
            return cursor.rowcount == 1

    def finish_publication(self, identity, owner, status, detail=''):
        if status not in ('published', 'failed'):
            raise ValueError('Invalid publication status')
        with self._connect() as db:
            cursor=db.execute('''UPDATE publications SET status=?,detail=?,lease=0
                WHERE identity=? AND owner=? AND status='publishing' ''',
                (status, detail, identity, owner))
            if cursor.rowcount != 1: raise ValueError('Publication owner changed')

    def publication(self, identity):
        with self._connect() as db:
            exists=db.execute("SELECT name FROM sqlite_master WHERE name='publications'").fetchone()
            row=db.execute('SELECT * FROM publications WHERE identity=?',(identity,)).fetchone() if exists else None
            return dict(row) if row else None


    def save_publication_receipt(self, identity, owner, receipt):
        payload = json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS publication_receipts (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            row = db.execute('SELECT owner,status FROM publications WHERE identity=?', (identity,)).fetchone()
            if not row or row['owner'] != owner or row['status'] != 'publishing':
                raise ValueError('Publication owner changed')
            db.execute('INSERT OR IGNORE INTO publication_receipts VALUES(?,?)', (identity,payload))
            saved = db.execute('SELECT payload FROM publication_receipts WHERE identity=?',(identity,)).fetchone()[0]
            if saved != payload: raise ValueError('Publication receipt changed')
            return json.loads(saved)

    def check_publication_owner(self, identity, owner, min_remaining=60):
        import time
        row = self.publication(identity)
        if not row or row['owner'] != owner or row['status'] != 'publishing' or row['lease'] <= time.time() + min_remaining:
            raise ValueError('Publication lease expired or owner changed')
