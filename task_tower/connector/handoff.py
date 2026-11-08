"""Reviewed local/owner-PR handoff. This adapter has no merge/close operation."""
import copy
import json
from .delivery import independent
from ..service.store import encoded
from ..delivery_policy import validate_receipt


class HandoffDelivery:
    def __init__(self,host,store,trees,policies,automatic=None):
        self.host,self.store,self.trees=host,store,trees
        self.policies=copy.deepcopy(policies);self.automatic=automatic
        with store.lock,store.db:
            store.db.execute('CREATE TABLE IF NOT EXISTS handoffs (attempt_id TEXT PRIMARY KEY,data TEXT NOT NULL)')

    def run(self,command,api,stop):
        a=command['attempt'];policy=self.policies.get(a['project_id'])
        if policy!=a.get('delivery_policy'):raise ValueError('delivery_policy_changed')
        if policy['mode']=='task_tower':
            if self.automatic is None:raise ValueError('automatic_delivery_unavailable')
            return self.automatic.run(command,api,stop)
        if stop.is_set():raise ValueError('delivery_interrupted')
        independent(a)
        if (a['attempt_id'],a['project_id'])!=(command['attempt_id'],command['project_id']):raise ValueError('handoff_identity')
        if self.trees.source(a['project_id'],a['attempt_id'],a['base_sha'])!=a['source']:raise ValueError('handoff_source_changed')
        with self.store.lock:
            row=self.store.db.execute('SELECT data FROM handoffs WHERE attempt_id=?',(a['attempt_id'],)).fetchone()
        if row:
            previous=json.loads(row[0])
            if previous['attempt']!=a:raise ValueError('handoff_identity_changed')
            if 'result' not in previous:raise ValueError('handoff_needs_reconciliation')
            return previous['result']
        # Write intent before any push/PR. A lost response never repeats effects.
        data=dict(attempt=copy.deepcopy(a))
        with self.store.lock,self.store.db:
            self.store.db.execute('INSERT INTO handoffs VALUES (?,?)',(a['attempt_id'],encoded(data)))
        receipt=dict(kind='reviewed.local',policy=copy.deepcopy(policy),head_sha=a['head_sha'],base_sha=a['base_sha'])
        if policy['mode']=='owner_pr':
            row=self.host.prepare_pr(a,base_ref=policy['base'])
            if (row.get('repository')!=policy['repository'] or row.get('head_repository')!=policy['repository']
                    or row.get('base_ref')!=policy['base'] or row.get('base_sha')!=a['base_sha']
                    or row.get('head_sha')!=a['head_sha'] or row.get('branch')!='codex/headless-'+a['attempt_id']
                    or row.get('state')!='open' or row.get('merged') is not False):raise ValueError('handoff_pr_changed')
            receipt.update(kind='reviewed.pr',pr_number=row['number'])
        validate_receipt(receipt,policy,a['head_sha'],a['base_sha'])
        data['result']=dict(phase='handoff',receipt=receipt)
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE handoffs SET data=? WHERE attempt_id=?',(encoded(data),a['attempt_id']))
        return data['result']
