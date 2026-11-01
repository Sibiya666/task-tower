"""Durable create intents. An unknown outcome never authorizes another POST."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from .project_connections import safe_config_path


class CreationJournal:
    def __init__(self, path):
        self.path = safe_config_path(path)

    @contextmanager
    def transaction(self):
        """Commit each reservation before the caller can send an API request."""
        try:
            safe_config_path(self.path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            for path in (self.path, Path(str(self.path)+'-journal'), Path(str(self.path)+'-wal'), Path(str(self.path)+'-shm')):
                safe_config_path(path)
                if path.exists() and path.stat().st_nlink != 1:
                    raise ValueError('Unsafe creation journal hardlink')
            with closing(sqlite3.connect(self.path, timeout=10)) as database, database:
                database.execute('PRAGMA synchronous=FULL')
                database.execute('BEGIN IMMEDIATE')
                application_id=database.execute('PRAGMA application_id').fetchone()[0]
                tables=database.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if application_id != 1414808387 and (application_id != 0 or tables):
                    raise ValueError('Unrecognized private creation journal; existing database preserved')
                database.execute('PRAGMA application_id=1414808387')
                database.execute('CREATE TABLE IF NOT EXISTS create_intents (kind TEXT NOT NULL, repository TEXT NOT NULL, identity TEXT NOT NULL, resource TEXT, PRIMARY KEY(kind,repository,identity))')
                yield database
        except (OSError, sqlite3.Error):
            raise ValueError('Private creation journal unavailable; restore access and retry without deleting the journal') from None

    def reserve(self, kind, repository, identity):
        with self.transaction() as database:
            row = database.execute('SELECT resource FROM create_intents WHERE kind=? AND repository=? AND identity=?', (kind,repository,identity)).fetchone()
            if row is not None:
                return False
            database.execute('INSERT INTO create_intents(kind,repository,identity) VALUES(?,?,?)', (kind,repository,identity))
            return True

    def reconcile(self, kind, repository, identity, resource):
        """Retain resolved IDs; disappearance must never silently reset intent."""
        with self.transaction() as database:
            row = database.execute('SELECT resource FROM create_intents WHERE kind=? AND repository=? AND identity=?', (kind,repository,identity)).fetchone()
            if row is not None and row[0] is not None and row[0] != resource:
                raise ValueError('Creation journal resource disagrees with unique remote identity; inspect existing resources')
            database.execute('INSERT INTO create_intents(kind,repository,identity,resource) VALUES(?,?,?,?) ON CONFLICT(kind,repository,identity) DO UPDATE SET resource=excluded.resource', (kind,repository,identity,resource))
