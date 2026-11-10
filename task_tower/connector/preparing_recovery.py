"""Approved legacy preparing attach; unknown effects are never replayed."""
from ..preparing_recovery import validate_receipt,code_source,fingerprint
from .diagnostics import GitFailure

class PreparingRecovery:
    def __init__(self,store,trees,*,approved=None):
        if trees.store is not store:raise ValueError('preparing_connector_changed')
        if approved is not None and not isinstance(approved,dict):raise ValueError('preparing_approval_registry_invalid')
        self.store,self.trees=store,trees
        self.approved={k:frozenset(v) if isinstance(v,(set,frozenset)) else v for k,v in (approved or {}).items()}

    def run(self,receipt):
        # The first pass rejects an unapproved request before source observations.
        from ..preparing_recovery import parse_receipt
        r=parse_receipt(receipt)
        r=validate_receipt(r,self.approved,connector_id=self.store.connector_id,source_sha=r['engine_sha'])
        r=validate_receipt(r,self.approved,connector_id=self.store.connector_id,source_sha=code_source())
        digest=fingerprint(r)
        with self.store.lock:
            prior=self.store.preparing_operation(r['operation_id'])
            if prior is not None:return self._known(prior,digest)
            command=self.store.command(r['command_id'])['command']
            self.trees.inspect_preparing(r,command)
            old=self.store.command(r['command_id'])
            cleanup={key:old.get(key) for key in ('cleanup_resources','cleanup_confirmed')}
            if fingerprint(cleanup)!=r['cleanup_sha256']:raise ValueError('preparing_cleanup_changed')
            self.store.begin_preparing(r)
        try:
            tree=self.trees.attach_preparing(r,command)
            return self.store.complete_preparing(r,tree)
        except Exception as error:
            # A lost return after an atomic commit reads the known result only.
            prior=self.store.preparing_operation(r['operation_id'])
            if prior is not None and prior['state']=='prepared':return self._known(prior,digest)
            self.store.unknown_preparing(r)
            if isinstance(error,GitFailure):raise
            raise ValueError('preparing_attach_unknown') from None

    @staticmethod
    def _known(prior,digest):
        if prior['receipt_sha256']!=digest:raise ValueError('preparing_operation_conflict')
        if prior['state']!='prepared':raise ValueError('preparing_operation_unknown')
        return dict(prior['result'])
