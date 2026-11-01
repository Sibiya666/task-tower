"""Publish a durable local acceptance without granting remote execution authority."""
import copy
import hashlib
import json
import re
import uuid
from types import SimpleNamespace

from . import tasks
from .github_tasks import GitHubTasks, GitHubRequestError, parse_metadata
from .github_source import GitHubSourceError

LIFECYCLE = '<!-- task-tower:lifecycle:v1\n'

class PublicationError(ValueError):
    pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def publication_id(receipt):
    return hashlib.sha256(canonical(receipt).encode()).hexdigest()

class GitHubPublisher:
    def __init__(self, repository, config, token=None, store=None, verify_source=None):
        if not isinstance(config,dict) or not isinstance(repository,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*',repository):
            raise ValueError('Invalid publication configuration')
        self.mapping=config.get('issue_tasks')
        self.account=config.get('publisher_account')
        if (not isinstance(self.mapping,dict) or not self.mapping or
            any(not re.fullmatch(r'TT-[A-Z0-9]+(?:-[A-Z0-9]+)*',str(k)) or type(v) is not int or v<1 for k,v in self.mapping.items()) or
            len(set(self.mapping.values())) != len(self.mapping) or
            not isinstance(self.account,str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?',self.account) or '--' in self.account):
            raise ValueError('Publication requires explicit task mapping and publisher account')
        self.verify_source=verify_source
        self.repository=repository
        self.store=store or GitHubTasks(SimpleNamespace(repository=repository),token=token)

    def receipt(self, path, bundle, row, required):
        card=tasks.load_task(path)
        task_id=card['id']; sha=bundle['merge_commit']
        if (task_id not in self.mapping or card['status']!='done' or row['status']!='done' or
            row['task_id']!=task_id or row['commit']!=sha or bundle['repository']!=self.repository or
            task_id not in bundle['task_ids'] or any(bundle['platforms'].get(p)!='passed' for p in required) or
            card['stages']['postmerge']['commit']!=sha):
            raise PublicationError('Publication acceptance mismatch')
        prior=copy.deepcopy(card); prior['stages']['postmerge']={'status':'pending'}
        # A pre-review card can omit the pending record entirely.
        if tasks.task_snapshot(prior)!=row['snapshot']:
            prior['stages'].pop('postmerge')
            if tasks.task_snapshot(prior)!=row['snapshot']: raise PublicationError('Publication snapshot mismatch')
        report_path=tasks._safe_path(path.parent/card['stages']['postmerge']['evidence'])
        report=json.loads(report_path.read_text(encoding='utf-8'))
        review=row['result']
        if (report.get('bundle')!=bundle or report.get('review')!=review or
            report.get('task_id')!=task_id or report.get('commit')!=sha or
            not isinstance(review,dict) or review.get('task_id')!=task_id or review.get('commit')!=sha or
            review.get('verdict')!='approve' or not isinstance(review.get('summary'),str) or not review['summary'].strip() or
            not isinstance(review.get('findings'),list) or any(not isinstance(x,str) for x in review['findings'])):
            raise PublicationError('Publication review mismatch')
        evidence={stage:{k:record[k] for k in ('evidence','reviewer','sha256','hash_scheme') if k in record}
                  for stage,record in card['stages'].items()}
        return dict(version=1,kind='local-postmerge',repository=self.repository,issue=self.mapping[task_id],
            task_id=task_id,commit=sha,bundle=bundle,required_platforms=required,
            policy=dict(executor=card['executor'],reviewer=card['stages']['postmerge']['reviewer']),
            input_snapshot=row['snapshot'],evidence=evidence,evidence_digest=hashlib.sha256(canonical(evidence).encode()).hexdigest(),
            review=dict(task_id=task_id,commit=sha,verdict='approve',summary='Independent postmerge review approved',findings=[]))

    def _remote(self, receipt):
        issue=self.store.get(receipt['issue']); meta=parse_metadata(issue.get('body'))
        if type(issue.get('id')) is not int or issue['id'] <= 0 or (receipt.get('issue_id') is not None and issue['id'] != receipt['issue_id']):
            raise PublicationError('Issue immutable identity changed')
        if (not meta or meta.get('kind')!='task' or
            (meta.get('legacy_id') or meta.get('task_id') or meta.get('id'))!=receipt['task_id']):
            raise PublicationError('Issue task identity changed')
        comparison=self.store.request('GET','/compare/'+receipt['commit']+'...main')
        if not isinstance(comparison,dict) or comparison.get('status') not in ('ahead','identical'):
            raise PublicationError('Publication commit is not on main')
        comments=[]
        for page in range(1,21):
            rows=self.store.request('GET',f"/issues/{receipt['issue']}/comments?per_page=100&page={page}")
            if not isinstance(rows,list) or len(rows)>100: raise PublicationError('Invalid publication comments')
            for comment in rows:
                if not isinstance(comment,dict) or type(comment.get('id')) is not int or not isinstance(comment.get('body'),str):
                    raise PublicationError('Invalid publication comment')
                if comment['body'].startswith(LIFECYCLE):
                    if not comment['body'].endswith('\n-->'): raise PublicationError('Invalid lifecycle receipt')
                    value=json.loads(comment['body'][len(LIFECYCLE):-4])
                    if not isinstance(value,dict): raise PublicationError('Invalid lifecycle receipt')
                    comments.append((comment,value))
            if len(rows)<100: return issue,sorted(comments,key=lambda item:item[0]['id'])
        raise PublicationError('Publication pagination limit exceeded')

    def _verify_current_source(self, receipt):
        if self.verify_source is None:
            raise PublicationError('Fresh verified source required')
        bundles=self.verify_source()
        relevant=[b for b in bundles if receipt['task_id'] in b.get('task_ids',[])]
        if not relevant:
            raise PublicationError('Fresh verified source required')
        newest=max(relevant,key=lambda b:(int(b['run_id']),int(b['attempt'])))
        if newest!=receipt['bundle']:
            raise PublicationError('Newer CI supersedes publication')

    def publish(self, path, bundle, row, required, journal):
        receipt=self.receipt(path,bundle,row,required)
        issue=self.store.get(receipt['issue'])
        if type(issue.get('id')) is not int or issue['id'] <= 0: raise PublicationError('Invalid immutable Issue ID')
        receipt['issue_id']=issue['id']
        identity=publication_id(receipt)
        owner=uuid.uuid4().hex
        if not journal.claim_publication(identity,owner,lease_seconds=3600):
            return journal.publication(identity)
        phase='fresh_source'
        try:
            self._verify_current_source(receipt)
            phase='receipt_storage'
            receipt=journal.save_publication_receipt(identity,owner,receipt)
            phase='remote_check'
            issue,comments=self._remote(receipt)
            matches=[c for c,v in comments if v.get('remote_attempt',{}).get('publication_id')==identity]
            expected={'remote_attempt':dict(kind='local-postmerge',status='done',commit=receipt['commit'],publication_id=identity,receipt=receipt),'status':'done'}
            if len(matches)>1: raise PublicationError('Ambiguous publication receipts')
            if matches:
                if len(comments)!=1: raise PublicationError('Conflicting lifecycle requires explicit reconciliation')
                matching=matches[-1]
                value=next(v for c,v in comments if c['id']==matching['id'])
                if value!=expected or matching.get('user',{}).get('login','').lower()!=self.account.lower():
                    raise PublicationError('Publication author or receipt mismatch')
                if comments[-1][0]['id']>matching['id']: raise PublicationError('Newer lifecycle supersedes acceptance')
            else:
                if comments: raise PublicationError('Existing lifecycle requires explicit reconciliation')
                journal.check_publication_owner(identity,owner)
                phase='comment_post'
                matching=self.store.request('POST',f"/issues/{receipt['issue']}/comments",{'body':LIFECYCLE+canonical(expected)+'\n-->'})
                if (not isinstance(matching,dict) or matching.get('body')!=LIFECYCLE+canonical(expected)+'\n-->' or
                    type(matching.get('id')) is not int or matching.get('user',{}).get('login','').lower()!=self.account.lower()):
                    raise PublicationError('Publication author or receipt mismatch')
            # Re-read after posting and immediately before state-only close.
            phase='final_source'
            self._verify_current_source(receipt)
            phase='local_inputs'
            fresh=self.receipt(path,bundle,row,required); fresh['issue_id']=receipt['issue_id']
            if fresh!=receipt: raise PublicationError('Accepted publication inputs changed')
            journal.check_publication_owner(identity,owner)
            phase='final_remote'
            issue,comments=self._remote(receipt)
            if len(comments)!=1 or comments[-1][0]['id']!=matching['id'] or comments[-1][1]!=expected:
                raise PublicationError('Newer lifecycle supersedes acceptance')
            if comments[-1][0].get('user',{}).get('login','').lower()!=self.account.lower():
                raise PublicationError('Publication author changed')
            journal.check_publication_owner(identity,owner)
            if issue.get('state')!='closed' or issue.get('state_reason')!='completed':
                phase='issue_close'
                closed=self.store.request('PATCH',f"/issues/{receipt['issue']}",{'state':'closed','state_reason':'completed'})
                if not isinstance(closed,dict) or closed.get('number')!=receipt['issue'] or closed.get('state')!='closed' or closed.get('state_reason')!='completed':
                    raise PublicationError('Issue close not confirmed')
            journal.finish_publication(identity,owner,'published')
        except Exception as error:
            if isinstance(error,GitHubRequestError):
                category='http_'+str(error.http_status) if error.http_status is not None else error.category
            elif isinstance(error,GitHubSourceError):
                category='source_unavailable'
            elif isinstance(error,OSError):
                category='network'
            elif isinstance(error,ValueError):
                category='proof_rejected'
            else:
                category='unavailable'
            journal.finish_publication(identity,owner,'failed',phase+': '+category)
        return journal.publication(identity)
