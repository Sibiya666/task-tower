"""Scoped cloud transport inside the existing foreground connector; no new worker."""
import hashlib
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from .github_app import _NoRedirect
from ..service.store import encoded


class ConsumerHTTP:
    def __init__(self,url,consumer,credential):
        parsed=urlsplit(url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query or parsed.fragment or parsed.path not in ("","/"):
            raise ValueError("trusted_https_transport_required")
        self._url=url.rstrip("/");self._consumer=consumer;self._credential=credential
    def _request(self,path,payload):
        raw=encoded(dict(payload,consumer=self._consumer)).encode()
        request=Request(self._url+path,data=raw,headers={"Authorization":"Bearer "+self._credential(),"Content-Type":"application/json"},method="POST")
        from ..service.beads import strict_json
        with build_opener(_NoRedirect()).open(request,timeout=15) as response: raw=response.read(1048577)
        if len(raw)>1048576:raise ValueError("transport_response_limit")
        value=strict_json(raw.decode("utf-8"))
        if not isinstance(value,dict):raise ValueError("invalid_transport_response")
        return value
    def take(self,limit):return self._request("/api/inbox/take",dict(limit=limit))["deliveries"]
    def ack(self,key,digest):return self._request("/api/inbox/ack",dict(delivery_id=key,receipt_hash=digest))


class IssueTransport:
    def __init__(self,store,remote,binding,handler):
        if set(binding)!={"app_id","installation_id","repository_id"} or any(type(v) is not int or v<1 for v in binding.values()):raise ValueError("invalid_transport_binding")
        self.store,self.remote,self.binding,self.handler=store,remote,dict(binding),handler
        with store.lock,store.db:store.db.execute("CREATE TABLE IF NOT EXISTS issue_transport_receipts (delivery_key TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,state TEXT NOT NULL,data TEXT NOT NULL)")
    def _validate(self,event):
        if not isinstance(event,dict) or event.get("version")!=1 or any(event.get(k)!=v for k,v in self.binding.items()) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",event.get("delivery_id","")) or not re.fullmatch(r"[a-f0-9]{64}",event.get("payload_sha256","")) or not isinstance(event.get("body"),dict) or len(encoded(event).encode())>1048576:raise ValueError("foreign_or_invalid_delivery")
        return hashlib.sha256(encoded([self.binding,event["delivery_id"]]).encode()).hexdigest(),hashlib.sha256(encoded(event).encode()).hexdigest()
    def tick(self):
        events=self.remote.take(1)
        if not isinstance(events,list) or len(events)>1:raise ValueError("bounded_transport_required")
        for event in events:
            key,fingerprint=self._validate(event)
            with self.store.lock:
                row=self.store.db.execute("SELECT fingerprint,state,data FROM issue_transport_receipts WHERE delivery_key=?",(key,)).fetchone()
                if row and row[0]!=fingerprint:raise ValueError("delivery_hash_conflict")
                if row and row[1]=="handled":receipt=json.loads(row[2])
                else:
                    if row:
                        receipt=self.handler.readback(event,"issue-delivery-"+key)
                        if receipt is None:raise ValueError("delivery_effect_needs_reconciliation")
                    else:
                        with self.store.db:self.store.db.execute("INSERT INTO issue_transport_receipts VALUES (?,?,?,?)",(key,fingerprint,"intent","{}"))
                        try:
                            sender=event["body"].get("sender",{})
                            eligible="pull_request" not in event["body"].get("issue",{}) and event.get("event") in ("issues","issue_comment") and sender.get("type")=="User" and (event.get("event")=="issues" and event.get("action") in ("opened","edited","reopened") or event.get("event")=="issue_comment" and event.get("action") in ("created","edited","deleted"))
                            receipt=self.handler(event,"issue-delivery-"+key) if eligible else dict(state="ignored")
                        except Exception:raise ValueError("delivery_effect_needs_reconciliation") from None
                    if not isinstance(receipt,dict):raise ValueError("invalid_effect_receipt")
                    with self.store.db:self.store.db.execute("UPDATE issue_transport_receipts SET state='handled',data=? WHERE delivery_key=?",(encoded(receipt),key))
                digest=hashlib.sha256(encoded(receipt).encode()).hexdigest()
            ack=self.remote.ack(event["delivery_id"],digest)
            if ack.get("receipt_hash")!=digest or ack.get("state")!="acked":raise ValueError("cloud_ack_mismatch")


class IssueEventHandler:
    def __init__(self,project,source,api,connector,messenger_factory):
        self.project,self.source,self.api,self.connector,self.messenger_factory=project,source,api,connector,messenger_factory
    def _number(self,event):
        number=event["body"].get("issue",{}).get("number")
        if type(number) is not int or number<1:raise ValueError("issue_number_required")
        return number
    def __call__(self,event,request_id):
        number=self._number(event);snapshot=self.source.snapshot(number,inspect_scope=False)
        result=self.api.request("POST","/v1/issues/admit",dict(version=1,project_id=self.project,request_id=request_id,issue_number=number,source_revision=snapshot["source_revision"]))["issue"]
        if result["state"]=="accepted" and (event.get("action")=="reopened" or result.get("source_revision")!=snapshot["source_revision"]):
            result=dict(result,state="needs_input",reason="accepted_revision_requires_owner")
        if result["state"]=="clarify":
            s={k:snapshot[k] for k in ("repository","repository_id","issue_number","reporter_id")}
            self.messenger_factory(s).ensure_comment("clarify:"+snapshot["source_revision"],number,"Please provide reproduction steps, expected behavior, acceptance criteria and existing files to change, using the issue template. The issue remains open while details are missing.")
        if result["state"]=="needs_input":
            messages={
                "accepted_revision_requires_owner":"This issue already has an accepted result. A new revision requires a repository owner decision; reopening does not restart the old task.",
                "owner_admission_required":"This request needs review by the repository owner before execution. No automatic task was started.",
                "runtime_scope_required":"The request is waiting for the repository owner to complete runtime verification. No automatic task was started.",
                "unsupported_source_scope":"This request needs manual scope review. Automatic changes require declared existing supported files; execution/authentication settings are protected.",
                "policy_budget_exhausted":"This request is waiting for the repository execution/admission budget. No automatic task was started.",
            }
            reason=result.get("reason")
            if reason in messages:
                s={k:snapshot[k] for k in ("repository","repository_id","issue_number","reporter_id")}
                self.messenger_factory(s).ensure_comment("needs-input:"+reason,number,messages[reason])
        if result["state"]=="published":self._dispatch(result)
        return result
    def _dispatch(self,receipt):
        attempt=self.connector.claim(self.project,receipt["bead_id"])
        if attempt is None:return
        a=self.api.request("GET","/v1/attempts/"+attempt["attempt_id"])["attempt"]
        if a["phase"]=="claimed" and not a.get("managed"):self.api.dispatch(a["attempt_id"],receipt["base_sha"])
    def readback(self,event,request_id):
        from urllib.parse import urlencode
        result=self.api.request("GET","/v1/issues?"+urlencode(dict(project_id=self.project,issue_number=self._number(event))))["issue"]
        if result and result["state"]=="published":self._dispatch(result)
        return result
