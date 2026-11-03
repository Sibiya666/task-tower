"""Single-installation PR journal with non-expiring owners and effect intents.

SQLite serializes local state; a lifetime advisory lock excludes another watch.
Neither PID death nor lock expiry transfers an existing PR/effect's ownership.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .pr_policy import (HASH, SHA, TASK, canonical, exact, identifier, integer,
    policy_fingerprint, private_paths, strict_json, text)
from .project_connections import REPOSITORY

APP_ID=1414811722
SCHEMAS={
    'prs':'CREATE TABLE prs(repository TEXT NOT NULL, pr_number INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(repository,pr_number))',
    'owners':'CREATE TABLE owners(owner_id TEXT PRIMARY KEY, pid INTEGER NOT NULL, status TEXT NOT NULL)',
    'barriers':'CREATE TABLE barriers(repository TEXT PRIMARY KEY, body TEXT NOT NULL)',
    'effects':'CREATE TABLE effects(effect_id TEXT PRIMARY KEY, body TEXT NOT NULL)',
    'publications':'CREATE TABLE publications(publication_id TEXT PRIMARY KEY, body TEXT NOT NULL)',
    'revisions':'CREATE TABLE revisions(repository TEXT NOT NULL, pr_number INTEGER NOT NULL, binding_sha256 TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(repository,pr_number,binding_sha256))',
}
SEQUENCE=('discovered','validating','reviewing','reviewed','publishing_acceptance','accepted',
    'merge_intent','merge_pending','awaiting_main','awaiting_postmerge','awaiting_closure','completed')
SIDE={'stale','rejected','needs_input','unknown','cancelled','timed_out'}
BINDING={'repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','input_sha256','policy_sha256'}
ROW_EXTRA={'task_timeout_seconds','max_review_attempts','admitted_utc','deadline_utc','last_seen_utc',
    'state','reason','owner_id','owner_pid','review_attempts','postmerge_attempts','effect_count','cancel_requested',
    'pr_receipt_sha256','reviewer_instance_id','merge_commit','postmerge_receipt_sha256'}
PHASES=('prepared','comment_intent','comment_confirmed','close_intent','closure_observed','published')
PROOF={'repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','merge_commit','main_sha',
    'bundle_sha256','pr_receipt_sha256','postmerge_receipt_sha256','publication_id','verified_done','issue_state','state_reason'}


def _now():
    return datetime.now(timezone.utc)


class _ClockFence(Exception):
    def __init__(self,row,reason):
        self.row=row; self.reason=reason
        row['state']='unknown' if reason=='clock_uncertain' else 'timed_out'
        row['reason']=reason


def _stamp(value):
    return value.isoformat(timespec='microseconds').replace('+00:00','Z')


def _date(value):
    if not isinstance(value,str) or not value.endswith('Z'): raise ValueError('Invalid PR clock')
    try: result=datetime.fromisoformat(value[:-1]+'+00:00')
    except ValueError: raise ValueError('Invalid PR clock') from None
    if _stamp(result)!=value: raise ValueError('Invalid PR clock')
    return result


def _binding(value, *, optional=False):
    exact(value,BINDING,{'task_timeout_seconds','max_review_attempts'} if optional else ())
    text(value['repository'],REPOSITORY)
    if value['repository']!=value['repository'].casefold(): raise ValueError('Noncanonical PR repository')
    for key in ('pr_number','issue','issue_id'): integer(value[key])
    text(value['task_id'],TASK)
    for key in ('head_sha','base_sha'): text(value[key],SHA)
    for key in ('input_sha256','policy_sha256'): text(value[key],HASH)


def _identity(repository,pr_number):
    return text(repository,REPOSITORY).casefold(),integer(pr_number)


def _row(value):
    exact(value,BINDING|ROW_EXTRA)
    _binding({k:value[k] for k in BINDING})
    integer(value['task_timeout_seconds'],60,604800); integer(value['max_review_attempts'],1,5)
    integer(value['review_attempts'],0,value['max_review_attempts']); integer(value['postmerge_attempts'],0,1)
    integer(value['effect_count'],0)
    if type(value['cancel_requested']) is not bool or value['state'] not in set(SEQUENCE)|SIDE: raise ValueError('Invalid PR state')
    if value['reason'] is not None: text(value['reason'],r'[a-z][a-z0-9_]{0,99}')
    if value['owner_id'] is not None: identifier(value['owner_id']); integer(value['owner_pid'])
    elif value['owner_pid'] is not None or value['state'] not in {'discovered','cancelled'}: raise ValueError('Invalid PR owner')
    admitted=_date(value['admitted_utc']); deadline=_date(value['deadline_utc']); seen=_date(value['last_seen_utc'])
    if deadline!=admitted+timedelta(seconds=value['task_timeout_seconds']) or seen<admitted: raise ValueError('Invalid PR deadline')
    for key in ('pr_receipt_sha256','postmerge_receipt_sha256'):
        if value[key] is not None: text(value[key],HASH)
    if value['reviewer_instance_id'] is not None: identifier(value['reviewer_instance_id'])
    if value['merge_commit'] is not None: text(value['merge_commit'],SHA)


def _proof(proof):
    exact(proof,PROOF)
    _binding({k:proof[k] for k in BINDING-{'input_sha256','policy_sha256'}} | {
        'input_sha256':'0'*64,'policy_sha256':'0'*64})
    for key in ('merge_commit','main_sha'): text(proof[key],SHA)
    for key in ('bundle_sha256','pr_receipt_sha256','postmerge_receipt_sha256','publication_id'): text(proof[key],HASH)
    if proof['merge_commit']!=proof['main_sha'] or proof['verified_done'] is not True or proof['issue_state']!='closed' or proof['state_reason']!='completed': raise ValueError('Incomplete PR proof')


def _payload(kind,payload):
    shapes={
        'pr_review':{'reviewer_instance_id','request_sha256'},
        'postmerge_review':{'reviewer_instance_id','request_sha256','merge_commit'},
        'acceptance_status':{'state','context','sha','target_url','description','receipt_sha256'},
        'acceptance_review':{'commit_id','event','body','receipt_sha256'},
        'merge':{'sha','merge_method','merge_action','bypass_rules'},
        'comment_post':{'publication_id','body_sha256'},
        'issue_close':{'publication_id','issue_id','state','state_reason'},
    }
    if kind not in shapes: raise ValueError('Invalid PR effect kind')
    exact(payload,shapes[kind])
    for key,value in payload.items():
        if key.endswith('sha256') or key=='publication_id': text(value,HASH)
        elif key in ('sha','commit_id','merge_commit'): text(value,SHA)
        elif key=='reviewer_instance_id': identifier(value)
        elif key=='issue_id': integer(value)
    if kind=='merge' and (payload['merge_method']!='merge' or payload['merge_action']!='direct_merge' or payload['bypass_rules'] is not False): raise ValueError('Unsupported merge action')
    if kind=='acceptance_status':
        if payload['state'] not in ('pending','failure','success') or payload['context']!='task-tower/pr-acceptance': raise ValueError('Invalid acceptance status')
        text(payload['target_url'],r'https://github\.com/[^\s]+'); text(payload['description'])
        if len(payload['description'])>140: raise ValueError('Acceptance description too large')
    if kind=='acceptance_review':
        if payload['event']!='COMMENT': raise ValueError('Not a human review')
        text(payload['body'])
    if kind=='issue_close' and (payload['state']!='closed' or payload['state_reason']!='completed'): raise ValueError('Invalid close action')


def _observation(kind,value):
    allowed={
        'pr_review':{'result_sha256','receipt_sha256','reviewer_instance_id','process'},
        'postmerge_review':{'result_sha256','receipt_sha256','reviewer_instance_id','process'},
        'acceptance_status':{'remote_id','body_sha256','author'},
        'acceptance_review':{'remote_id','body_sha256','author'},
        'merge':{'request_uuid','merge_commit','main_sha','parents','result'},
        'comment_post':{'remote_id','body_sha256','author'},
        'issue_close':{'issue_id','state','state_reason'},
    }
    exact(value,{'status'},allowed[kind])
    if value['status'] not in ('confirmed','unknown','needs_input','failed'): raise ValueError('Invalid effect observation')
    for key,item in value.items():
        if key.endswith('sha256'): text(item,HASH)
        elif key in ('remote_id','issue_id'): integer(item)
        elif key in ('request_uuid','reviewer_instance_id'): identifier(item)
        elif key in ('merge_commit','main_sha'): text(item,SHA)
        elif key=='parents':
            if not isinstance(item,list) or len(item)!=2: raise ValueError('Invalid merge parents')
            for parent in item: text(parent,SHA)
        elif key=='author': text(item,r'[A-Za-z0-9][A-Za-z0-9\[\]-]{0,99}')
        elif key=='result' and item not in ('pending','merged','failed','enqueued'): raise ValueError('Invalid merge result')
        elif key=='state' and item!='closed': raise ValueError('Invalid Issue state')
        elif key=='state_reason' and item!='completed': raise ValueError('Invalid Issue reason')
        elif key=='process':
            exact(item,{'pid','exit_code','started','cleanup_confirmed'})
            if type(item['started']) is not bool or type(item['cleanup_confirmed']) is not bool: raise ValueError('Invalid review process')
            no_launch=(value['status']=='failed' and kind in ('pr_review','postmerge_review')
                and item==dict(pid=None,exit_code=None,started=False,cleanup_confirmed=True))
            if not no_launch:
                integer(item['pid']); integer(item['exit_code'],-2**31,2**32-1)
    if value['status']=='confirmed':
        required=allowed[kind]-({'request_uuid'} if kind=='merge' else set())
        if not required<=set(value): raise ValueError('Incomplete effect observation')
        if kind=='issue_close' and (value['state']!='closed' or value['state_reason']!='completed'): raise ValueError('Unclosed Issue')
        if kind=='merge' and (value['result']!='merged' or value['main_sha']!=value['merge_commit']): raise ValueError('Unconfirmed merge')
        if kind in ('pr_review','postmerge_review') and (value['process']['started'] is not True or value['process']['cleanup_confirmed'] is not True or value['process']['exit_code']!=0): raise ValueError('Unclean review process')
    if value['status']=='failed':
        if kind not in ('pr_review','postmerge_review') or 'process' not in value or value['process']['cleanup_confirmed'] is not True: raise ValueError('Unproven failed review cleanup')
        if value['process']['started'] is not True and value['process']!=dict(pid=None,exit_code=None,started=False,cleanup_confirmed=True):raise ValueError('Unproven no-launch review')


def _receipt(receipt):
    # Preserve the legacy v1 body exactly. Adding immutable Issue ID is additive.
    exact(receipt,{'version','kind','repository','issue','issue_id','task_id','commit','bundle',
        'required_platforms','policy','input_snapshot','evidence','evidence_digest','review'})
    if type(receipt['version']) is not int or receipt['version']!=1 or receipt['kind']!='local-postmerge': raise ValueError('Invalid publication receipt')
    text(receipt['repository'],REPOSITORY); text(receipt['task_id'],TASK)
    integer(receipt['issue']); integer(receipt['issue_id']); text(receipt['commit'],SHA)
    text(receipt['input_snapshot'],HASH); text(receipt['evidence_digest'],HASH)
    for key in ('bundle','policy','evidence','review'):
        if not isinstance(receipt[key],dict) or not receipt[key]: raise ValueError('Missing publication evidence')
    if policy_fingerprint(receipt['evidence'])!=receipt['evidence_digest']: raise ValueError('Publication evidence mismatch')
    exact(receipt['policy'],{'executor','reviewer'})
    for value in receipt['policy'].values(): text(value)
    review=receipt['review']; exact(review,{'task_id','commit','verdict','summary','findings'})
    if review['task_id']!=receipt['task_id'] or review['commit']!=receipt['commit'] or review['verdict']!='approve' or review['findings']!=[]: raise ValueError('Publication review mismatch')
    text(review['summary'])
    platforms=receipt['required_platforms']
    if not isinstance(platforms,list) or not platforms or any(p not in ('windows','macos','linux') for p in platforms) or len(set(platforms))!=len(platforms): raise ValueError('Invalid publication platforms')
    if receipt['bundle'].get('repository')!=receipt['repository'] or receipt['bundle'].get('merge_commit')!=receipt['commit']: raise ValueError('Publication bundle mismatch')


def _body(receipt):
    identity=policy_fingerprint(receipt)
    expected={'remote_attempt':dict(kind='local-postmerge',status='done',commit=receipt['commit'],
        publication_id=identity,receipt=receipt),'status':'done'}
    return '<!-- task-tower:lifecycle:v1\n'+canonical(expected)+'\n-->'


def _publication_binding(publication,binding,owner_id):
    """One exact revision owns both sides of every publication effect edge."""
    if (publication['repository']!=publication['binding']['repository']
            or publication['pr_number']!=publication['binding']['pr_number']
            or publication['binding']!=binding or publication['owner_id']!=owner_id):
        raise ValueError('Publication revision/owner mismatch')


def _publication_effect(publication,effect):
    _publication_binding(publication,effect['binding'],effect['owner_id'])
    kind=effect['kind']
    key='comment_effect_id' if kind=='comment_post' else 'close_effect_id'
    if (kind not in ('comment_post','issue_close') or publication[key]!=effect['effect_id']
            or effect['payload']['publication_id']!=publication['publication_id']):
        raise ValueError('Publication effect reference mismatch')
    if kind=='comment_post' and effect['payload']['body_sha256']!=publication['body_sha256']:
        raise ValueError('Publication comment body mismatch')
    if kind=='issue_close' and effect['payload']['issue_id']!=publication['binding']['issue_id']:
        raise ValueError('Publication close identity mismatch')


class PRJournal:
    def __init__(self,path,*,checkouts=(),forbidden_paths=()):
        self.path=Path(path); self.checkouts=tuple(checkouts); self.forbidden_paths=tuple(forbidden_paths)
        self._active=None; self._clock_limits={}; self._safe()

    def _safe(self):
        private_paths((self.path,*self.forbidden_paths),self.checkouts)

    @contextmanager
    def _db(self,write=False):
        self._safe()
        if not write and not self.path.exists(): yield None; return
        if write: self.path.parent.mkdir(parents=True,exist_ok=True); self._safe()
        if self.path.exists():
            header=self.path.read_bytes()[:100]
            if header[:16]==b'SQLite format 3\x00' and header[18:20]!=b'\x01\x01' or any(Path(str(self.path)+s).exists() for s in ('-wal','-shm')): raise ValueError('Unsupported PR WAL state')
        try:
            with closing(sqlite3.connect(self.path if write else self.path.resolve().as_uri()+'?mode=ro',uri=not write,timeout=5)) as db:
                db.row_factory=sqlite3.Row
                if write: db.execute('PRAGMA synchronous=FULL'); db.execute('BEGIN IMMEDIATE')
                else: db.execute('PRAGMA query_only=ON')
                app=db.execute('PRAGMA application_id').fetchone()[0]; version=db.execute('PRAGMA user_version').fetchone()[0]
                objects={(r['type'],r['name'],r['sql']) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
                if write and app==0 and version==0 and not objects:
                    db.execute('PRAGMA application_id='+str(APP_ID)); db.execute('PRAGMA user_version=1')
                    for sql in SCHEMAS.values(): db.execute(sql)
                elif app!=APP_ID or version!=1 or objects!={('table',name,sql) for name,sql in SCHEMAS.items()}: raise ValueError('Unrecognized PR journal schema')
                self._validate(db)
                try:
                    yield db
                    if write: self._validate(db); db.commit()
                except _ClockFence as error:
                    # A detected clock failure is itself durable evidence. Do not
                    # roll it back and allow a later tick to silently recover.
                    self._save(db,error.row); self._validate(db); db.commit()
                    raise ValueError('PR clock/deadline fenced') from None
                except BaseException:
                    if write: db.rollback()
                    raise
        except sqlite3.Error: raise ValueError('PR journal unavailable') from None

    def _load(self,db,table,key,value):
        row=None if db is None else db.execute('SELECT body FROM '+table+' WHERE '+key+'=?',(value,)).fetchone()
        return None if row is None else strict_json(row['body'])

    def _get(self,db,repository,pr_number):
        row=None if db is None else db.execute('SELECT body FROM prs WHERE repository=? AND pr_number=?',(repository,pr_number)).fetchone()
        return None if row is None else strict_json(row['body'])

    def _save(self,db,row):
        _row(row)
        db.execute('INSERT OR REPLACE INTO prs VALUES(?,?,?)',(row['repository'],row['pr_number'],canonical(row)))

    def _validate(self,db):
        owners={}
        for owner in db.execute('SELECT * FROM owners'):
            identifier(owner['owner_id']); integer(owner['pid'])
            if owner['status'] not in ('active','retired'): raise ValueError('Invalid PR owner registry')
            owners[owner['owner_id']]=dict(owner)
        rows={}
        for saved in db.execute('SELECT * FROM prs'):
            row=strict_json(saved['body']); _row(row)
            if row['repository']!=saved['repository'] or row['pr_number']!=saved['pr_number']: raise ValueError('PR key mismatch')
            if row['owner_id'] is not None and (row['owner_id'] not in owners or row['owner_pid']!=owners[row['owner_id']]['pid']): raise ValueError('PR owner mismatch')
            rows[(row['repository'],row['pr_number'])]=row
        revisions={}
        for saved in db.execute('SELECT * FROM revisions'):
            row=strict_json(saved['body']); _row(row)
            key=(row['repository'],row['pr_number']); current=rows.get(key)
            digest=policy_fingerprint({k:row[k] for k in BINDING})
            if current is None or saved['binding_sha256']!=digest or saved['repository']!=row['repository'] or saved['pr_number']!=row['pr_number']: raise ValueError('Invalid PR revision')
            if any(row[k]!=current[k] for k in ('issue','issue_id','task_id','admitted_utc','deadline_utc','task_timeout_seconds','max_review_attempts','owner_id','owner_pid')): raise ValueError('PR revision identity changed')
            if row['review_attempts']>current['review_attempts'] or row['effect_count']>current['effect_count'] or row['state'] not in ('stale','rejected','needs_input'): raise ValueError('Invalid PR revision counters')
            revisions[digest]=row
        barriers={}
        for saved in db.execute('SELECT * FROM barriers'):
            barrier=strict_json(saved['body']); exact(barrier,BINDING|{'owner_id','owner_pid','completed','proof'})
            _binding({k:barrier[k] for k in BINDING}); identifier(barrier['owner_id']); integer(barrier['owner_pid'])
            row=rows.get((barrier['repository'],barrier['pr_number']))
            if saved['repository']!=barrier['repository'] or row is None or any(barrier[k]!=row[k] for k in BINDING|{'owner_id','owner_pid'}) or type(barrier['completed']) is not bool: raise ValueError('Invalid PR barrier')
            if barrier['completed']: _proof(barrier['proof'])
            elif barrier['proof'] is not None: raise ValueError('Premature PR proof')
            barriers[barrier['repository']]=barrier
        effects={}
        for saved in db.execute('SELECT * FROM effects'):
            effect=strict_json(saved['body']); exact(effect,{'effect_id','kind','binding','owner_id','owner_pid','payload','status','observation'})
            identifier(effect['effect_id']); identifier(effect['owner_id']); integer(effect['owner_pid']); _binding(effect['binding'])
            _payload(effect['kind'],effect['payload'])
            row=rows.get((effect['binding']['repository'],effect['binding']['pr_number']))
            if row is not None and any(effect['binding'][k]!=row[k] for k in BINDING): row=revisions.get(policy_fingerprint(effect['binding']))
            if saved['effect_id']!=effect['effect_id'] or row is None or any(effect['binding'][k]!=row[k] for k in BINDING) or effect['owner_id']!=row['owner_id'] or effect['owner_pid']!=row['owner_pid']: raise ValueError('Invalid PR effect binding')
            if effect['status']=='intent':
                if effect['observation'] is not None: raise ValueError('Invalid PR intent')
            else:
                _observation(effect['kind'],effect['observation'])
                if effect['observation']['status']!=effect['status']: raise ValueError('Invalid PR observation')
            effects[effect['effect_id']]=effect
        for row in rows.values():
            current=[e for e in effects.values() if all(e['binding'][k]==row[k] for k in BINDING)]
            self._state_evidence(row,current)
            historical=[e for e in effects.values() if e['binding']['repository']==row['repository'] and e['binding']['pr_number']==row['pr_number']]
            if row['effect_count']!=len(historical) or row['review_attempts']!=sum(e['kind']=='pr_review' for e in historical) or row['postmerge_attempts']!=sum(e['kind']=='postmerge_review' for e in historical): raise ValueError('PR effect counters mismatch')
        publications={}
        for saved in db.execute('SELECT * FROM publications'):
            publication=strict_json(saved['body']); self._validate_publication(publication,rows,revisions,effects)
            if saved['publication_id']!=publication['publication_id']: raise ValueError('Publication key mismatch')
            publications[publication['publication_id']]=publication
        for effect in effects.values():
            if effect['kind'] in ('comment_post','issue_close'):
                publication=publications.get(effect['payload']['publication_id'])
                if publication is None: raise ValueError('Publication effect without receipt')
                _publication_effect(publication,effect)

    @staticmethod
    def _state_evidence(row,effects):
        if row['state'] not in SEQUENCE or SEQUENCE.index(row['state'])<SEQUENCE.index('reviewed'): return
        reviews=[e for e in effects if e['kind']=='pr_review' and e['status']=='confirmed']
        if len(reviews)!=1 or reviews[0]['observation']['receipt_sha256']!=row['pr_receipt_sha256'] or reviews[0]['observation']['reviewer_instance_id']!=row['reviewer_instance_id']: raise ValueError('PR review receipt missing')
        if SEQUENCE.index(row['state'])>=SEQUENCE.index('accepted'):
            statuses=[e for e in effects if e['kind']=='acceptance_status' and e['payload']['state']=='success' and e['status']=='confirmed']
            reports=[e for e in effects if e['kind']=='acceptance_review' and e['status']=='confirmed']
            if len(statuses)!=1 or len(reports)!=1 or any(e['payload']['receipt_sha256']!=row['pr_receipt_sha256'] for e in statuses+reports): raise ValueError('PR acceptance publication missing')
        if SEQUENCE.index(row['state'])>=SEQUENCE.index('merge_intent'):
            merges=[e for e in effects if e['kind']=='merge']
            if len(merges)!=1: raise ValueError('Merge intent missing')
            if SEQUENCE.index(row['state'])>=SEQUENCE.index('awaiting_main') and (merges[0]['status']!='confirmed' or merges[0]['observation']['merge_commit']!=row['merge_commit']): raise ValueError('Merge proof missing')
        if SEQUENCE.index(row['state'])>=SEQUENCE.index('awaiting_closure'):
            posts=[e for e in effects if e['kind']=='postmerge_review' and e['status']=='confirmed']
            if len(posts)!=1 or posts[0]['observation']['receipt_sha256']!=row['postmerge_receipt_sha256'] or posts[0]['payload']['reviewer_instance_id']==row['reviewer_instance_id']: raise ValueError('Independent postmerge receipt missing')

    def _owned(self,db,row,owner_id):
        identifier(owner_id)
        owner=db.execute('SELECT * FROM owners WHERE owner_id=?',(owner_id,)).fetchone()
        if self._active!=owner_id or owner is None or owner['status']!='active' or owner['pid']!=os.getpid() or row is None or row['owner_id'] not in (None,owner_id): raise ValueError('PR ownership fenced')
        if row['owner_id'] is None: row['owner_id']=owner_id; row['owner_pid']=os.getpid()

    def _tick(self,row):
        now=_now(); monotonic=time.monotonic(); key=(row['repository'],row['pr_number'])
        if now<_date(row['last_seen_utc']): raise _ClockFence(row,'clock_uncertain')
        deadline=_date(row['deadline_utc'])
        if key not in self._clock_limits: self._clock_limits[key]=monotonic+max(0,(deadline-now).total_seconds())
        if now>=deadline or monotonic>=self._clock_limits[key]: raise _ClockFence(row,'deadline_exceeded')
        row['last_seen_utc']=_stamp(now)

    @contextmanager
    def owner(self,owner_id):
        identifier(owner_id)
        if self._active is not None: raise ValueError('PR owner already active')
        self._safe(); self.path.parent.mkdir(parents=True,exist_ok=True); self._safe()
        lock_path=Path(str(self.path)+'.owner-lock')
        with lock_path.open('a+b') as lock:
            try:
                if os.name=='nt':
                    import msvcrt
                    lock.seek(0)
                    if lock.read(1)==b'': lock.write(b'0'); lock.flush()
                    lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise ValueError('PR owner lock held') from None
            registered=False
            try:
                with self._db(True) as db:
                    if db.execute('SELECT 1 FROM owners WHERE owner_id=?',(owner_id,)).fetchone(): raise ValueError('PR owner cannot restart')
                    db.execute('INSERT INTO owners VALUES(?,?,?)',(owner_id,os.getpid(),'active'))
                registered=True; self._active=owner_id
                yield owner_id
            finally:
                self._active=None
                try:
                    if registered:
                        with self._db(True) as db: db.execute("UPDATE owners SET status='retired' WHERE owner_id=?",(owner_id,))
                finally:
                    if os.name=='nt': lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                    else: fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

    def admit(self,binding):
        binding=dict(binding); _binding(binding,optional=True)
        timeout=integer(binding.pop('task_timeout_seconds',86400),60,604800)
        attempts=integer(binding.pop('max_review_attempts',2),1,5)
        with self._db(True) as db:
            row=self._get(db,binding['repository'],binding['pr_number'])
            if row is not None:
                if row['task_timeout_seconds']!=timeout or row['max_review_attempts']!=attempts or any(row[k]!=binding[k] for k in ('issue','issue_id','task_id')): raise ValueError('Immutable PR admission changed')
                if all(row[k]==v for k,v in binding.items()): return row
                self._owned(db,row,self._active); self._tick(row)
                barrier=self._load(db,'barriers','repository',binding['repository'])
                if row['state'] not in ('stale','rejected','needs_input') or row['cancel_requested'] or row['merge_commit'] is not None or (barrier is not None and not barrier['completed']): raise ValueError('PR revision fenced')
                if binding['input_sha256']==row['input_sha256'] or row['review_attempts']>=row['max_review_attempts']: raise ValueError('PR revision input/budget fenced')
                old_digest=policy_fingerprint({k:row[k] for k in BINDING}); new_digest=policy_fingerprint(binding)
                if db.execute('SELECT 1 FROM revisions WHERE binding_sha256=?',(new_digest,)).fetchone(): raise ValueError('PR revision already consumed')
                effects=[strict_json(r['body']) for r in db.execute('SELECT body FROM effects')]
                previous=[e for e in effects if policy_fingerprint(e['binding'])==old_digest]
                reviews=[e for e in previous if e['kind']=='pr_review']
                if any(e['status'] not in ('confirmed','failed') for e in previous) or len(reviews)>1 or any(e['observation']['process']['cleanup_confirmed'] is not True for e in reviews): raise ValueError('Prior PR work uncertain')
                db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(row['repository'],row['pr_number'],old_digest,canonical(row)))
                row.update(binding); row.update(state='discovered',reason=None,pr_receipt_sha256=None,
                    reviewer_instance_id=None,postmerge_receipt_sha256=None)
                self._save(db,row); return row
            now=_now(); row=dict(binding,task_timeout_seconds=timeout,max_review_attempts=attempts,
                admitted_utc=_stamp(now),deadline_utc=_stamp(now+timedelta(seconds=timeout)),last_seen_utc=_stamp(now),
                state='discovered',reason=None,owner_id=None,owner_pid=None,review_attempts=0,postmerge_attempts=0,
                effect_count=0,cancel_requested=False,pr_receipt_sha256=None,reviewer_instance_id=None,merge_commit=None,postmerge_receipt_sha256=None)
            self._save(db,row); return row

    def get(self,repository,pr_number):
        repository,pr_number=_identity(repository,pr_number)
        with self._db() as db: return self._get(db,repository,pr_number)

    def rows(self,repository=None):
        if repository is not None: repository=text(repository,REPOSITORY).casefold()
        with self._db() as db:
            return [] if db is None else [strict_json(r['body']) for r in db.execute('SELECT body FROM prs ORDER BY repository,pr_number') if repository is None or strict_json(r['body'])['repository']==repository]

    def effect(self,effect_id):
        """Inspect a validated immutable intent; absence grants no replay right."""
        identifier(effect_id)
        with self._db() as db: return self._load(db,'effects','effect_id',effect_id)

    def effects(self,repository,pr_number):
        repository,pr_number=_identity(repository,pr_number)
        with self._db() as db:
            values=[] if db is None else [strict_json(r['body']) for r in db.execute('SELECT body FROM effects ORDER BY rowid')]
            return [r for r in values if r['binding']['repository']==repository and r['binding']['pr_number']==pr_number]

    def transition(self,repository,pr_number,owner_id,expected,update):
        repository,pr_number=_identity(repository,pr_number)
        exact(expected,{'state','input_sha256'}); exact(update,{'state'},{'reason','pr_receipt_sha256','reviewer_instance_id','merge_commit','postmerge_receipt_sha256'})
        with self._db(True) as db:
            row=self._get(db,repository,pr_number); self._owned(db,row,owner_id); self._tick(row)
            if any(row[k]!=v for k,v in expected.items()): raise ValueError('PR CAS mismatch')
            before=row['state']; after=update['state']
            allowed=({SEQUENCE[SEQUENCE.index(before)+1]} if before in SEQUENCE[:-1] else set())
            if before=='merge_intent': allowed.add('awaiting_main')
            if before in SEQUENCE[:-1]: allowed|=SIDE
            if after not in allowed or after in {'merge_intent','merge_pending','completed'}: raise ValueError('Invalid PR transition')
            if row['cancel_requested'] and after not in SIDE: raise ValueError('PR cancellation fenced')
            for key,value in update.items():
                if key not in ('state','reason') and row[key] is not None and row[key]!=value: raise ValueError('Immutable PR evidence')
                if key=='pr_receipt_sha256' and value is not None and any(strict_json(r['body'])['pr_receipt_sha256']==value for r in db.execute('SELECT body FROM revisions WHERE repository=? AND pr_number=?',(repository,pr_number))): raise ValueError('Prior PR receipt reused')
                row[key]=value
            if after=='reviewing':
                if row['review_attempts']>=row['max_review_attempts']: raise ValueError('PR review budget exceeded')
            self._save(db,row); return row

    def barrier(self,repository):
        repository=text(repository,REPOSITORY).casefold()
        with self._db() as db:
            row=self._load(db,'barriers','repository',repository)
            return row if row is not None and not row['completed'] else None

    def acquire_barrier(self,repository,pr_number,owner_id,binding):
        """Acquire only this PR's barrier; a recovery follow-up cannot replace it.

        Provenance-bound follow-up continuation belongs to the controller's
        later recovery seam, not to a Boolean release/transfer escape hatch.
        """
        repository,pr_number=_identity(repository,pr_number)
        supplied=dict(binding); _binding(supplied,optional=True)
        with self._db(True) as db:
            row=self._get(db,repository,pr_number); self._owned(db,row,owner_id); self._tick(row)
            if row['state']!='accepted' or row['cancel_requested'] or any(row[k]!=supplied[k] for k in BINDING): raise ValueError('Invalid barrier binding')
            prior=self._load(db,'barriers','repository',repository)
            if prior is not None and not prior['completed']:
                if prior['pr_number']!=pr_number or prior['owner_id']!=owner_id: raise ValueError('Repository barrier held')
                return prior
            result={k:row[k] for k in BINDING|{'owner_id','owner_pid'}}; result.update(completed=False,proof=None)
            db.execute('INSERT OR REPLACE INTO barriers VALUES(?,?)',(repository,canonical(result))); self._save(db,row); return result

    def begin_effect(self,repository,pr_number,owner_id,kind,payload):
        repository,pr_number=_identity(repository,pr_number); _payload(kind,payload)
        with self._db(True) as db:
            row=self._get(db,repository,pr_number); self._owned(db,row,owner_id); self._tick(row)
            failure_status=(kind=='acceptance_status' and payload['state']=='failure' and row['state'] in ('stale','rejected','needs_input'))
            if row['cancel_requested'] or (row['state'] in SIDE|{'completed'} and not failure_status): raise ValueError('PR effect fenced')
            effects=[strict_json(r['body']) for r in db.execute('SELECT body FROM effects')]
            for prior in effects:
                if all(prior['binding'][k]==row[k] for k in BINDING) and prior['status'] not in ('confirmed','failed'): raise ValueError('Unresolved PR effect fenced')
                if all(prior['binding'][k]==row[k] for k in BINDING) and prior['kind']==kind:
                    # Status phases are distinct writes; each phase still only once.
                    if kind!='acceptance_status' or prior['payload']['state']==payload['state']: raise ValueError('PR effect already intended')
            states={'pr_review':{'reviewing'},'postmerge_review':{'awaiting_postmerge'},
                'acceptance_status':{'validating','reviewing','reviewed','publishing_acceptance','rejected','stale','needs_input'},
                'acceptance_review':{'publishing_acceptance'},'merge':{'accepted'},
                'comment_post':{'awaiting_closure'},'issue_close':{'awaiting_closure'}}
            if row['state'] not in states[kind]: raise ValueError('PR effect out of sequence')
            if kind=='acceptance_status':
                if payload['sha']!=row['head_sha']: raise ValueError('Acceptance head mismatch')
                if payload['state']=='success' and (row['state']!='publishing_acceptance' or payload['receipt_sha256']!=row['pr_receipt_sha256']): raise ValueError('Acceptance receipt missing')
                if payload['state']=='pending' and (row['state'] not in ('validating','reviewing') or payload['receipt_sha256']!=row['input_sha256']): raise ValueError('Pending acceptance binding mismatch')
                if payload['state']=='failure' and payload['receipt_sha256'] not in (row['pr_receipt_sha256'],row['input_sha256']): raise ValueError('Failure acceptance binding mismatch')
            if kind=='acceptance_review' and (payload['commit_id']!=row['head_sha'] or payload['receipt_sha256']!=row['pr_receipt_sha256']): raise ValueError('Acceptance report mismatch')
            if kind in ('merge','postmerge_review','comment_post','issue_close'):
                barrier=self._load(db,'barriers','repository',repository)
                if barrier is None or barrier['completed'] or barrier['pr_number']!=pr_number or barrier['owner_id']!=owner_id: raise ValueError('PR effect lacks barrier')
            if kind=='merge':
                if payload['sha']!=row['head_sha']: raise ValueError('Merge head mismatch')
                row['state']='merge_intent'
            if kind in ('pr_review','postmerge_review'):
                if payload['reviewer_instance_id']==row['reviewer_instance_id']: raise ValueError('Reviewer instance reused')
                if any(e['payload'].get('reviewer_instance_id')==payload['reviewer_instance_id'] for e in effects): raise ValueError('Historical reviewer instance reused')
                if kind=='pr_review':
                    if payload['request_sha256']!=row['input_sha256'] or row['review_attempts']>=row['max_review_attempts']: raise ValueError('PR review binding/budget mismatch')
                    row['review_attempts']+=1
                if kind=='postmerge_review':
                    if row['postmerge_attempts'] or payload['merge_commit']!=row['merge_commit']: raise ValueError('Postmerge review fenced')
                    row['postmerge_attempts']=1
            if kind in ('comment_post','issue_close'):
                publication=self._load(db,'publications','publication_id',payload['publication_id'])
                expected='prepared' if kind=='comment_post' else 'comment_confirmed'
                if publication is None or publication['phase']!=expected or publication['owner_id']!=owner_id: raise ValueError('Publication effect out of sequence')
                _publication_binding(publication,{k:row[k] for k in BINDING},owner_id)
                if kind=='comment_post' and payload['body_sha256']!=publication['body_sha256']: raise ValueError('Publication body mismatch')
                if kind=='issue_close' and payload['issue_id']!=row['issue_id']: raise ValueError('Publication Issue mismatch')
            effect=dict(effect_id=str(uuid.uuid4()),kind=kind,binding={k:row[k] for k in BINDING},
                owner_id=owner_id,owner_pid=os.getpid(),payload=json.loads(canonical(payload)),status='intent',observation=None)
            row['effect_count']+=1
            db.execute('INSERT INTO effects VALUES(?,?)',(effect['effect_id'],canonical(effect)))
            if kind in ('comment_post','issue_close'):
                publication['phase']='comment_intent' if kind=='comment_post' else 'close_intent'
                publication['comment_effect_id' if kind=='comment_post' else 'close_effect_id']=effect['effect_id']
                db.execute('UPDATE publications SET body=? WHERE publication_id=?',(canonical(publication),publication['publication_id']))
            self._save(db,row); return effect

    def observe(self,effect_id,owner_id,observation):
        identifier(effect_id)
        with self._db(True) as db:
            effect=self._load(db,'effects','effect_id',effect_id)
            if effect is None: raise ValueError('Unknown PR effect')
            _observation(effect['kind'],observation)
            row=self._get(db,effect['binding']['repository'],effect['binding']['pr_number'])
            self._owned(db,row,owner_id)
            if any(effect['binding'][k]!=row[k] for k in BINDING): raise ValueError('Historical PR effect is immutable')
            if effect['owner_id']!=owner_id or effect['status']=='confirmed': raise ValueError('PR effect ownership/observation fenced')
            if effect['kind'] in ('pr_review','postmerge_review') and 'reviewer_instance_id' in observation and observation['reviewer_instance_id']!=effect['payload']['reviewer_instance_id']: raise ValueError('Reviewer observation mismatch')
            if effect['observation'] is not None:
                for key,value in effect['observation'].items():
                    if key!='status' and observation.get(key)!=value: raise ValueError('Conflicting PR observation')
            if effect['kind']=='merge' and observation['status']=='confirmed':
                # Recheck after BEGIN IMMEDIATE, in the transaction that
                # records completion. A prior host check may precede a lock wait.
                self._tick(row)
                barrier=self._load(db,'barriers','repository',row['repository'])
                if (row['cancel_requested'] or row['state'] not in ('merge_intent','merge_pending')
                        or row['owner_pid']!=os.getpid() or effect['owner_pid']!=os.getpid()
                        or barrier is None or barrier['completed'] is not False or barrier['proof'] is not None
                        or barrier['owner_id']!=owner_id or barrier['owner_pid']!=os.getpid()
                        or any(type(barrier[k]) is not type(row[k]) or barrier[k]!=row[k] for k in BINDING)):
                    raise ValueError('Merge confirmation transaction fenced')
                if observation['parents']!=[row['base_sha'],row['head_sha']]: raise ValueError('Unexpected merge parents')
                row['merge_commit']=observation['merge_commit']; row['state']='awaiting_main'
            elif effect['kind']=='merge' and observation.get('request_uuid'):
                row['state']='merge_pending'
            effect['status']=observation['status']; effect['observation']=json.loads(canonical(observation))
            db.execute('UPDATE effects SET body=? WHERE effect_id=?',(canonical(effect),effect_id)); self._save(db,row)
            return effect

    def cancel(self,repository,pr_number):
        repository,pr_number=_identity(repository,pr_number)
        with self._db(True) as db:
            row=self._get(db,repository,pr_number)
            if row is None: raise ValueError('Unknown PR')
            row['cancel_requested']=True
            if row['state']=='discovered': row['state']='cancelled'
            self._save(db,row)

    def _validate_publication(self,value,rows,revisions,effects):
        exact(value,{'publication_id','repository','pr_number','owner_id','binding','receipt','receipt_sha256',
            'body_sha256','phase','comment_id','comment_effect_id','close_effect_id','completion_proof'})
        text(value['publication_id'],HASH); identifier(value['owner_id']); _binding(value['binding']); _receipt(value['receipt'])
        receipt=value['receipt']; row=rows.get((value['repository'],value['pr_number']))
        if row is not None and any(value['binding'][k]!=row[k] for k in BINDING):
            row=revisions.get(policy_fingerprint(value['binding']))
        if row is None: raise ValueError('Publication binding mismatch')
        _publication_binding(value,{k:row[k] for k in BINDING},row['owner_id'])
        if value['receipt_sha256']!=policy_fingerprint(receipt) or value['publication_id']!=value['receipt_sha256']: raise ValueError('Publication digest mismatch')
        body=_body(receipt)
        import hashlib
        if value['body_sha256']!=hashlib.sha256(body.encode('utf-8')).hexdigest(): raise ValueError('Publication body digest mismatch')
        if receipt['repository'].casefold()!=row['repository'] or any(receipt[k]!=row[k] for k in ('issue','issue_id','task_id')) or receipt['commit']!=row['merge_commit']: raise ValueError('Publication identity mismatch')
        if value['phase'] not in set(PHASES)|{'unknown','needs_input'}: raise ValueError('Invalid publication phase')
        for key,kind in (('comment_effect_id','comment_post'),('close_effect_id','issue_close')):
            if value[key] is not None:
                identifier(value[key]); effect=effects.get(value[key])
                if effect is None or effect['kind']!=kind or effect['payload']['publication_id']!=value['publication_id']: raise ValueError('Publication effect mismatch')
                _publication_effect(value,effect)
                if effect['owner_pid']!=row['owner_pid']: raise ValueError('Publication effect process mismatch')
        phase=value['phase']
        if phase=='prepared' and any(value[k] is not None for k in ('comment_id','comment_effect_id','close_effect_id')): raise ValueError('Premature publication intent')
        if phase in ('comment_intent','comment_confirmed') and value['close_effect_id'] is not None: raise ValueError('Premature Issue close intent')
        if value['close_effect_id'] is not None and value['comment_effect_id'] is None: raise ValueError('Close without comment intent')
        if phase in PHASES[1:] and value['comment_effect_id'] is None: raise ValueError('Missing comment intent')
        if value['comment_id'] is not None and value['comment_effect_id'] is None: raise ValueError('Comment acknowledgment without intent')
        if phase in PHASES[2:] or value['close_effect_id'] is not None or value['comment_id'] is not None:
            integer(value['comment_id']); effect=effects[value['comment_effect_id']]
            if effect['status']!='confirmed' or effect['observation']['remote_id']!=value['comment_id'] or effect['observation']['body_sha256']!=value['body_sha256']: raise ValueError('Unconfirmed publication comment')
        elif value['comment_id'] is not None: integer(value['comment_id'])
        if phase in PHASES[3:] and value['close_effect_id'] is None: raise ValueError('Missing close intent')
        if phase in PHASES[4:]:
            effect=effects[value['close_effect_id']]
            if effect['status']!='confirmed' or effect['observation']['issue_id']!=row['issue_id']: raise ValueError('Unconfirmed Issue closure')
        if phase=='published':
            _proof(value['completion_proof']); self._match_proof(value['completion_proof'],row,value)
        elif value['completion_proof'] is not None: raise ValueError('Premature completion proof')

    def publication(self,publication_id):
        text(publication_id,HASH)
        with self._db() as db: return self._load(db,'publications','publication_id',publication_id)

    def prepare_publication(self,repository,pr_number,owner_id,receipt):
        repository,pr_number=_identity(repository,pr_number); _receipt(receipt)
        with self._db(True) as db:
            row=self._get(db,repository,pr_number); self._owned(db,row,owner_id); self._tick(row)
            barrier=self._load(db,'barriers','repository',repository)
            if row['state']!='awaiting_closure' or barrier is None or barrier['completed'] or barrier['pr_number']!=pr_number or row['cancel_requested']: raise ValueError('Publication lacks barrier')
            publication_id=policy_fingerprint(receipt)
            prior=self._load(db,'publications','publication_id',publication_id)
            if prior is not None:
                _publication_binding(prior,{k:row[k] for k in BINDING},owner_id)
                if prior['receipt']!=receipt or prior['owner_id']!=owner_id: raise ValueError('Publication collision')
                return prior
            if any(strict_json(r['body'])['repository']==repository and strict_json(r['body'])['pr_number']==pr_number for r in db.execute('SELECT body FROM publications')): raise ValueError('PR already has publication')
            import hashlib
            body=_body(receipt)
            value=dict(publication_id=publication_id,repository=repository,pr_number=pr_number,owner_id=owner_id,
                binding={k:row[k] for k in BINDING},receipt=json.loads(canonical(receipt)),receipt_sha256=publication_id,
                body_sha256=hashlib.sha256(body.encode('utf-8')).hexdigest(),phase='prepared',comment_id=None,
                comment_effect_id=None,close_effect_id=None,completion_proof=None)
            db.execute('INSERT INTO publications VALUES(?,?)',(publication_id,canonical(value))); self._save(db,row); return value

    def record_publication(self,publication_id,owner_id,expected_phase,update):
        text(publication_id,HASH); exact(update,{'phase'},{'comment_id','completion_proof'})
        with self._db(True) as db:
            value=self._load(db,'publications','publication_id',publication_id)
            if value is None or value['phase']!=expected_phase or value['owner_id']!=owner_id: raise ValueError('Publication CAS mismatch')
            row=self._get(db,value['repository'],value['pr_number']); self._owned(db,row,owner_id)
            allowed={'comment_intent':{'comment_confirmed','unknown','needs_input'},'close_intent':{'closure_observed','unknown','needs_input'},
                'closure_observed':{'published','unknown','needs_input'},'prepared':{'unknown','needs_input'},'comment_confirmed':{'unknown','needs_input'}}
            if expected_phase=='unknown':
                # Positive read-only inspection may resolve the existing intent
                # for its still-live owner. It never creates another request.
                if value['close_effect_id'] is not None: allowed['unknown']={'closure_observed'}
                elif value['comment_effect_id'] is not None: allowed['unknown']={'comment_confirmed'}
            if update['phase'] not in allowed.get(expected_phase,set()): raise ValueError('Invalid publication transition')
            if 'comment_id' in update and value['comment_id'] not in (None,update['comment_id']): raise ValueError('Immutable publication comment')
            value.update(json.loads(canonical(update)))
            db.execute('UPDATE publications SET body=? WHERE publication_id=?',(canonical(value),publication_id)); return value

    @staticmethod
    def _match_proof(proof,row,publication):
        for key in ('repository','pr_number','issue','issue_id','task_id','head_sha','base_sha','merge_commit','pr_receipt_sha256','postmerge_receipt_sha256'):
            if proof[key]!=row[key]: raise ValueError('Completion proof mismatch')
        if proof['publication_id']!=publication['publication_id'] or proof['bundle_sha256']!=policy_fingerprint(publication['receipt']['bundle']): raise ValueError('Completion publication mismatch')

    def complete_barrier(self,repository,owner_id,proof):
        repository=text(repository,REPOSITORY).casefold(); _proof(proof)
        with self._db(True) as db:
            barrier=self._load(db,'barriers','repository',repository)
            if barrier is None or barrier['completed'] or barrier['owner_id']!=owner_id: raise ValueError('Barrier ownership fenced')
            row=self._get(db,repository,barrier['pr_number']); self._owned(db,row,owner_id)
            publication=self._load(db,'publications','publication_id',proof['publication_id'])
            if row['state']!='awaiting_closure' or publication is None or publication['phase']!='published' or publication['completion_proof']!=proof: raise ValueError('Incomplete barrier proof')
            self._match_proof(proof,row,publication)
            barrier['completed']=True; barrier['proof']=json.loads(canonical(proof)); row['state']='completed'
            db.execute('UPDATE barriers SET body=? WHERE repository=?',(canonical(barrier),repository)); self._save(db,row); return barrier
