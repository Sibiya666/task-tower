"""Installation-local delivery intents and bounded trusted file adapter protocol."""
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import string
import tempfile
import uuid

from . import processes
from .project_connections import safe_config_path
from .executor_queue import _private_stat

APP_ID = 1414808644
RECEIPT = re.compile(r'[A-Za-z0-9._:-]{1,256}', re.ASCII)
COLUMNS = 'repository,issue,task_id,delivery_id,backend_fingerprint,status,detail,receipt_id'
DELIVERIES_SCHEMA = "CREATE TABLE deliveries(repository TEXT NOT NULL, issue INTEGER NOT NULL, task_id TEXT NOT NULL, delivery_id TEXT NOT NULL UNIQUE, backend_fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('unknown','accepted')), detail TEXT NOT NULL, receipt_id TEXT, PRIMARY KEY(repository,issue))"
METADATA_SCHEMA = 'CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)' 


def _identity(candidate):
    repository, issue, task = (candidate.get(k) for k in ('repository','issue','task_id'))
    if (not isinstance(repository,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',repository)
            or type(issue) is not int or issue <= 0 or not isinstance(task,str) or not re.fullmatch(r'TT-[A-Z0-9-]+',task)):
        raise ValueError('Invalid delivery identity')
    return repository.casefold(), issue, task


class DeliveryJournal:
    def __init__(self, path, *, readonly=False, forbidden_paths=(), checkouts=()):
        self.path = safe_config_path(path)
        self.readonly = readonly
        self.forbidden_paths = tuple(Path(p) for p in forbidden_paths)
        self.checkouts = tuple(Path(p).resolve() for p in checkouts)
        self._safe()

    def _safe(self):
        paths = [self.path, *(Path(str(self.path)+s) for s in ('-journal','-wal','-shm'))]
        for path in paths:
            safe_config_path(path)
            info=_private_stat(path,transient=path!=self.path) if path.exists() else None
            canonical = str(path.resolve()).casefold()
            for checkout in self.checkouts:
                root = str(checkout).casefold().rstrip('/\\')
                if canonical == root or canonical.startswith(root + os.sep):
                    raise ValueError('Delivery journal must be outside checkouts')
            for other in self.forbidden_paths:
                safe_config_path(other)
                other_info=_private_stat(other) if other.exists() else None
                if canonical == str(other.resolve()).casefold() or (info is not None and other_info is not None and os.path.samestat(info,other_info)):
                    raise ValueError('Delivery journal aliases an input')

    @contextmanager
    def _database(self, *, write=False):
        if write and self.readonly: raise ValueError('Read-only delivery journal')
        try:
            self._safe()
            if not write and not self.path.exists():
                yield None
                return
            if write:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                self._safe()
            # mode=ro alone can create WAL shared-memory/sidecar files. Installation
            # journals use DELETE mode; refuse WAL before opening SQLite, retaining
            # any uncheckpointed state for investigation rather than ignoring it.
            if self.path.exists():
                with self.path.open('rb') as stream:
                    header = stream.read(100)
                if (header[:16] == b'SQLite format 3\x00' and header[18:20] != b'\x01\x01'
                        or any(Path(str(self.path)+suffix).exists() for suffix in ('-wal','-shm'))):
                    raise ValueError('Unsupported WAL delivery journal; preserve all journal files')
            uri = self.path.resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(self.path if write else uri,uri=not write,timeout=10)) as db:
                db.row_factory = sqlite3.Row
                if write:
                    db.execute('PRAGMA synchronous=FULL')
                    db.execute('BEGIN IMMEDIATE')
                else: db.execute('PRAGMA query_only=ON')
                app = db.execute('PRAGMA application_id').fetchone()[0]
                version = db.execute('PRAGMA user_version').fetchone()[0]
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if write and app == 0 and version == 0 and not tables:
                    db.execute('PRAGMA application_id='+str(APP_ID))
                    db.execute('PRAGMA user_version=1')
                    db.execute(DELIVERIES_SCHEMA)
                    db.execute(METADATA_SCHEMA)
                elif app != APP_ID or version != 1 or tables != {'deliveries','metadata'}:
                    raise ValueError('Unrecognized delivery journal')
                if [r[1] for r in db.execute('PRAGMA table_info(deliveries)')] != COLUMNS.split(','):
                    raise ValueError('Unrecognized delivery journal schema')
                schemas = {r['name']:r['sql'] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'")}
                if schemas != {'deliveries':DELIVERIES_SCHEMA,'metadata':METADATA_SCHEMA}:
                    raise ValueError('Unrecognized delivery journal constraints')
                if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
                    raise ValueError('Unrecognized delivery journal schema')
                for saved in db.execute('SELECT '+COLUMNS+' FROM deliveries'):
                    row = dict(saved)
                    repository, issue, task = _identity(row)
                    try:
                        valid_uuid = str(uuid.UUID(row['delivery_id'])) == row['delivery_id']
                    except (ValueError, TypeError, AttributeError):
                        valid_uuid = False
                    if (repository != row['repository'] or not valid_uuid
                            or not isinstance(row['backend_fingerprint'],str)
                            or not re.fullmatch('[a-f0-9]{64}',row['backend_fingerprint'])
                            or row['status'] not in {'unknown','accepted'}
                            or row['detail'] not in {'intent_committed','accepted'}
                            or (row['status']=='unknown' and row['receipt_id'] is not None)
                            or (row['status']=='accepted' and (not isinstance(row['receipt_id'],str) or not RECEIPT.fullmatch(row['receipt_id'])))):
                        raise ValueError('Invalid delivery journal row')
                for metadata in db.execute('SELECT key,value FROM metadata'):
                    try:
                        cursor = json.loads(metadata['value'])
                        valid = (metadata['key']=='lookup_cursor' and isinstance(cursor,list) and len(cursor)==2
                                 and isinstance(cursor[0],str) and type(cursor[1]) is int and cursor[1]>0)
                    except (ValueError,TypeError):
                        valid = False
                    if not valid: raise ValueError('Invalid delivery journal cursor')
                try:
                    yield db
                    if write: db.commit()
                except BaseException:
                    if write: db.rollback()
                    raise
        except (OSError,sqlite3.Error) as error:
            raise ValueError('Delivery journal unavailable; preserve journal and restore access') from error

    def rows(self):
        with self._database() as db:
            return [] if db is None else [dict(r) for r in db.execute('SELECT '+COLUMNS+' FROM deliveries ORDER BY repository,issue')]

    def reserve(self,candidate,backend_fingerprint):
        repository, issue, task = _identity(candidate)
        if not isinstance(backend_fingerprint,str) or not re.fullmatch('[a-f0-9]{64}',backend_fingerprint):
            raise ValueError('Invalid backend fingerprint')
        with self._database(write=True) as db:
            row=db.execute('SELECT '+COLUMNS+' FROM deliveries WHERE repository=? AND issue=?',(repository,issue)).fetchone()
            winner=row is None
            if winner:
                db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,?,NULL)',(repository,issue,task,str(uuid.uuid4()),backend_fingerprint,'unknown','intent_committed'))
                row=db.execute('SELECT '+COLUMNS+' FROM deliveries WHERE repository=? AND issue=?',(repository,issue)).fetchone()
            result=dict(row)
        return result,winner

    def accept(self,delivery_id,receipt_id):
        if not isinstance(receipt_id,str) or not RECEIPT.fullmatch(receipt_id): raise ValueError('Invalid accepted receipt')
        with self._database(write=True) as db:
            db.execute("UPDATE deliveries SET status='accepted',detail='accepted',receipt_id=? WHERE delivery_id=? AND status='unknown'",(receipt_id,delivery_id))

    def lookup_rows(self,limit=8):
        if type(limit) is not int or not 0 <= limit <= 8: raise ValueError('Invalid lookup limit')
        with self._database(write=True) as db:
            rows=[dict(r) for r in db.execute("SELECT "+COLUMNS+" FROM deliveries WHERE status='unknown' ORDER BY repository,issue")]
            saved=db.execute("SELECT value FROM metadata WHERE key='lookup_cursor'").fetchone()
            cursor=json.loads(saved[0]) if saved else None
            if cursor is not None:
                rows=[r for r in rows if [r['repository'],r['issue']]>cursor]+[r for r in rows if [r['repository'],r['issue']]<=cursor]
            selected=rows[:limit]
            if selected:
                last=selected[-1]
                db.execute("INSERT INTO metadata VALUES('lookup_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps([last['repository'],last['issue']]),))
        return selected


def _backend(backend):
    if not isinstance(backend,dict) or set(backend)!={'argv','cwd','timeout_seconds'}: raise ValueError('Invalid dispatcher backend')
    argv=backend['argv']; cwd=Path(backend['cwd']); timeout=backend['timeout_seconds']
    if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a or '\x00' in a for a in argv): raise ValueError('Invalid dispatcher backend')
    for arg in argv:
        try:
            for literal,field,format_spec,conversion in string.Formatter().parse(arg):
                if field is not None and (field not in {'request','result','checkout'} or format_spec or conversion): raise ValueError()
        except ValueError: raise ValueError('Invalid dispatcher backend template') from None
    if not cwd.is_absolute() or not cwd.is_dir() or type(timeout) is not int or not 1<=timeout<=300: raise ValueError('Invalid dispatcher backend')
    if '{' in argv[0] or '}' in argv[0]: raise ValueError('Invalid dispatcher executable')
    executable=shutil.which(argv[0])
    if not executable or Path(executable).suffix.lower() in {'.cmd','.bat'}: raise ValueError('Unavailable dispatcher executable')
    return dict(argv=[str(Path(executable).resolve()),*argv[1:]],cwd=str(cwd.resolve()),timeout_seconds=timeout)


def backend_fingerprint(backend):
    return hashlib.sha256(json.dumps(_backend(backend),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError()
        result[key]=value
    return result


def run_backend(backend,request):
    trusted=_backend(backend)
    if set(request)!={'operation','delivery_id','repository','issue','task_id','runner_label'} or request['operation'] not in {'submit','lookup'}: raise ValueError('Invalid adapter request')
    _identity(request)
    failed=dict(status='unknown',reason='invalid_result')
    try:
        with tempfile.TemporaryDirectory(prefix='task-tower-dispatch-') as directory:
            root=Path(directory).resolve(); request_path=root/'request.json'; result_path=root/'result.json'
            request_path.write_text(json.dumps(request,ensure_ascii=True),encoding='utf-8')
            argv=[arg.format(request=str(request_path),result=str(result_path),checkout=trusted['cwd']) for arg in trusted['argv']]
            outcome=processes.run_command(argv,trusted['cwd'],trusted['timeout_seconds'])
            if outcome.get('status')!='passed' or outcome.get('exit_code')!=0:
                return dict(status='unknown',reason='backend_failed')
            info=result_path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400 or info.st_size>65536): return failed
            flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0)
            with os.fdopen(os.open(result_path,flags),'rb') as stream:
                opened=os.fstat(stream.fileno())
                if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino): return failed
                payload=stream.read(65537)
            if len(payload)>65536: return failed
            result=json.loads(payload.decode('utf-8'),object_pairs_hook=_unique)
            if not isinstance(result,dict) or type(result.get('version')) is not int or result['version']!=1 or result.get('delivery_id')!=request['delivery_id']: return failed
            status=result.get('status')
            if status not in {'accepted','unknown','not_found'} or (status=='not_found' and request['operation']!='lookup'): return failed
            if set(result)!=({'version','delivery_id','status','receipt_id'} if status=='accepted' else {'version','delivery_id','status'}): return failed
            if status=='accepted':
                receipt=result['receipt_id']
                if not isinstance(receipt,str) or not RECEIPT.fullmatch(receipt): return failed
                return dict(status=status,receipt_id=receipt)
            return dict(status=status)
    except (OSError,ValueError,TypeError,UnicodeError): return failed


def deliver(candidate,backend,journal,*,invoke=run_backend,lookup_existing=True):
    repository,issue,task=_identity(candidate)
    fingerprint=backend_fingerprint(backend)
    row,winner=journal.reserve(candidate,fingerprint)
    report=dict(repository=repository,issue=issue,task_id=task,state='needs_input',status='unknown',reason='unknown_outcome')
    if row['task_id']!=task or row['backend_fingerprint']!=fingerprint:
        return dict(report,reason='delivery_identity_mismatch')
    if row['status']=='accepted': return dict(report,state='accepted',status='accepted',reason='accepted')
    if not winner and not lookup_existing: return dict(report,reason='lookup_deferred')
    request=dict(operation='submit' if winner else 'lookup',delivery_id=row['delivery_id'],repository=repository,issue=issue,task_id=task,runner_label=candidate['runner_label'])
    try: result=invoke(backend,request)
    except Exception: result=dict(status='unknown',reason='backend_failed')
    if isinstance(result,dict) and result.get('status')=='accepted' and isinstance(result.get('receipt_id'),str) and RECEIPT.fullmatch(result['receipt_id']):
        journal.accept(row['delivery_id'],result['receipt_id'])
    # Re-read: concurrent accepted acknowledgments always win over stale negative lookups.
    current=next(r for r in journal.rows() if r['delivery_id']==row['delivery_id'])
    if current['status']=='accepted': return dict(report,state='accepted',status='accepted',reason='accepted')
    reason=result.get('reason') if isinstance(result,dict) else None
    return dict(report,reason=reason if reason in {'backend_failed','invalid_result'} else 'unknown_outcome')



