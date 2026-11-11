"""Typed exact-main evidence validation; model completion never closes Beads."""
import copy
import re

def accept(attempt,evidence):
    a=attempt;e=evidence
    from ..reporter_verification import require_reporter_receipt
    require_reporter_receipt(a)
    required={'version','kind','repository','pr_number','head_sha','base_sha','main_sha','runtime_tests','ci_run_id','artifact_digests','postmerge_review','fetch','validation'}
    if not isinstance(e,dict) or set(e)!=required or type(e['version']) is not int or e['version']!=1:raise ValueError('invalid_acceptance')
    if a.get('phase')!='postmerge' or any(e.get(k)!=a.get(k) for k in ('repository','pr_number','head_sha','base_sha','main_sha')):raise ValueError('acceptance_identity_mismatch')
    if type(e['ci_run_id']) is not int or e['ci_run_id']<1:raise ValueError('ci_identity_required')
    digests=e['artifact_digests']
    if not isinstance(digests,list) or not digests or len(set(digests))!=len(digests) or any(not isinstance(d,str) or not re.fullmatch('[0-9a-f]{64}',d) for d in digests):raise ValueError('artifact_digests_required')
    f=e['fetch']
    if (not isinstance(f,dict) or f.get('successful') is not True or f.get('main_sha')!=a['main_sha']
            or type(f.get('seconds')) not in (int,float) or not 0<=f['seconds']<=60
            or type(f.get('local_seconds')) not in (int,float) or not 0<=f['local_seconds']<=10):raise ValueError('fresh_fetch_required')
    r=e['postmerge_review']
    if (not isinstance(r,dict) or set(r)!={'verdict','findings','head_sha','base_sha','reviewer_thread_id'}
            or r.get('verdict')!='approve' or r.get('findings')!=[] or r.get('head_sha')!=a['main_sha'] or r.get('base_sha')!=a['base_sha']
            or not isinstance(r.get('reviewer_thread_id'),str) or not r['reviewer_thread_id']
            or r['reviewer_thread_id'] in [a.get('author_thread_id'),*a.get('review_threads',[])]):raise ValueError('fresh_postmerge_review_required')
    if e['kind']=='runtime.validation':
        if len(digests)!=5 or e['runtime_tests']!='passed' or e['validation']!={'exact_once':True,'fresh_discovery':True,'matrix_successful':True}:raise ValueError('runtime_validation_required')
    elif e['kind']=='documentation.validation':
        if (len(digests)!=1 or a.get('validation_kind')!='documentation.validation' or e['runtime_tests']!='not_run'
                or e['validation']!={'scope':'docs','fresh_validation':True,'runtime_shards':'skipped'}):raise ValueError('documentation_is_not_runtime')
    else:raise ValueError('unknown_validation_kind')
    return dict(copy.deepcopy(a),accepted_evidence=copy.deepcopy(e))


class AcceptanceStore:
    def reserve_delivery(self,a):
        from .beads import ServiceError
        policy=self.delivery_policies.get(a['project_id'])
        if policy!=a.get('delivery_policy') and a.get('delivery_policy') is not None:raise ServiceError('delivery_policy_changed')
        if policy and policy['mode'] in ('local','owner_pr'):return
        if a.get('source_issue') and not a.get('reporter_verification'):return
        if a.get('source_issue') and a.get('phase')!='postmerge':self.validate_issue_event(a,'reporter_verified',dict(verification=a['reporter_verification']))
        r=self.delivery_projects.get(a['project_id'])
        if r is None:raise ServiceError('delivery_not_configured',403)
        row=self.db.execute('SELECT attempt_id FROM acceptance_repository WHERE repository=?',(r,)).fetchone()
        if row and row[0]!=a['attempt_id']:raise ServiceError('repository_delivery_busy',retryable=True)
        with self.db:self.db.execute('INSERT OR IGNORE INTO acceptance_repository VALUES (?,?)',(r,a['attempt_id']))

    def accept_delivery(self,request_id,attempt_id,connector_id,merge,evidence):
        """Trusted connector receipt. Persist acceptance BEFORE native close intent.

        A duplicate or restart may read back the closed task/history. It must
        never repeat an ambiguous close, even when the task still appears open.
        """
        from .store import encoded,utc
        from .beads import ServiceError,identity
        import hashlib,json
        identity(request_id)
        with self.lock:
            a=self.attempt(attempt_id,connector_id)
            fingerprint=encoded([merge,evidence,a['reporter_verification']]) if a.get('source_issue') and a.get('reporter_verification') else encoded([merge,evidence])
            row=self.db.execute('SELECT * FROM acceptance_effects WHERE attempt_id=?',(attempt_id,)).fetchone()
            if row:
                if row['fingerprint']!=fingerprint or row['request_id']!=request_id:raise ServiceError('acceptance_conflict')
                if a['phase']=='accepted':return a
                return self._close_readback(a,json.loads(row['data']))
            if a['phase'] not in ('awaiting_merge','postmerge'):raise ServiceError('acceptance_fenced')
            self.beads.ensure_event_history(a['project_id'])
            if a.get('delivery_policy',{}).get('mode') in ('local','owner_pr'):raise ServiceError('owner_acceptance_required')
            if (not isinstance(merge,dict) or set(merge)!={'repository','pr_number','head_sha','base_sha','main_sha'}
                    or any(merge[k]!=a[k] for k in ('head_sha','base_sha'))):raise ServiceError('merge_identity_mismatch')
            if merge.get('repository')!=self.delivery_projects.get(a['project_id']):raise ServiceError('repository_forbidden',403)
            self.validate_execution(a['attempt_id'],a['connector_id'],delivery=True)
            proposed=dict(a,phase='postmerge',validation_kind=evidence.get('kind') if isinstance(evidence,dict) else None,**merge)
            try:accepted=accept(proposed,evidence)
            except ValueError:raise ServiceError('acceptance_invalid') from None
            # This receipt arrived via authenticated fixed connector delivery, not
            # agentMessage. Its postmerge thread cannot be any existing author/reviewer.
            thread=evidence['postmerge_review']['reviewer_thread_id']
            for r in self.db.execute('SELECT data FROM attempts'):
                other=json.loads(r[0])
                if thread in [other.get('author_thread_id'),*other.get('review_threads',[])]:raise ServiceError('postmerge_reviewer_not_new')
            repo=merge['repository']
            busy=self.db.execute('SELECT attempt_id FROM acceptance_repository WHERE repository=?',(repo,)).fetchone()
            if busy and busy[0]!=attempt_id:raise ServiceError('repository_acceptance_busy')
            reason='Headless accepted '+merge['main_sha']+' evidence '+hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()+' request '+request_id
            record=dict(reason=reason,accepted=accepted)
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO acceptance_repository VALUES (?,?)',(repo,attempt_id))
                self.db.execute('INSERT INTO acceptance_effects VALUES (?,?,?,?,?)',(attempt_id,request_id,fingerprint,'close_intent',encoded(record)))
                self._save_attempt(accepted)
            # Never let an uncertain close trigger another close. Even failure
            # before native start is conservatively reconciled through readback.
            try:self.beads.close(a['project_id'],a['bead_id'],a['actor'],reason)
            except Exception:pass
            return self._close_readback(accepted,record)

    def _close_readback(self,a,record):
        from .beads import ServiceError
        from .store import encoded
        try:
            row=self.beads.show(a['project_id'],a['bead_id'])
            history=self.beads.history(a['project_id'],a['bead_id'])
            matches=[e for e in history if e.get('issue_id')==a['bead_id'] and e.get('event_type')=='closed'
                     and e.get('actor')==a['actor'] and e.get('new_value')==record['reason'] and isinstance(e.get('id'),str)]
            if row.get('status')!='closed' or row.get('assignee')!=a['actor'] or len(matches)!=1:raise ValueError()
        except Exception:
            a=dict(a,phase='needs_reconciliation')
            with self.db:self._save_attempt(a)
            raise ServiceError('close_needs_reconciliation') from None
        a=dict(record['accepted'],phase='accepted',quiescent=True,canonical_close=dict(event_id=matches[0]['id'],owner=a['actor']))
        with self.db:
            self._save_attempt(a)
            self.db.execute("UPDATE acceptance_effects SET state='closed' WHERE attempt_id=?",(a['attempt_id'],))
            self.db.execute("UPDATE lifecycle_commands SET state='acknowledged' WHERE attempt_id=? AND state='queued'",(a['attempt_id'],))
            self.db.execute('DELETE FROM acceptance_repository WHERE repository=? AND attempt_id=?',(a['repository'],a['attempt_id']))
        return a
