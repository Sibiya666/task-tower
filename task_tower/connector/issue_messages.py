"""Public effects with durable intent and readback, using the existing host journal."""
import hashlib
import json
import re
from ..service.store import encoded


def source_identity(source):
    if not isinstance(source,dict) or set(source)!={"repository","repository_id","issue_number","reporter_id"}:
        raise ValueError("invalid_issue_source")
    if any(type(source[k]) is not int or source[k]<1 for k in ("repository_id","issue_number","reporter_id")) or not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+",source["repository"]):
        raise ValueError("invalid_issue_source")
    return dict(source)


class IssueMessenger:
    def __init__(self,host,store,source):
        self.host,self.store,self.source=host,store,source_identity(source)
        with store.lock,store.db:
            store.db.execute("CREATE TABLE IF NOT EXISTS issue_public_effects (effect_key TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,data TEXT NOT NULL)")

    def _fresh(self,issue):
        s=self.source
        if type(issue) is not int or issue!=s["issue_number"]: raise ValueError("issue_binding_mismatch")
        r=s["repository"]
        if self.host._request(r,"GET","/").get("id")!=s["repository_id"]: raise ValueError("repository_binding_mismatch")
        row=self.host._request(r,"GET","/issues/"+str(issue))
        if row.get("number")!=issue or row.get("user",{}).get("id")!=s["reporter_id"] or row.get("pull_request"):
            raise ValueError("reporter_binding_mismatch")
        return row

    def _intent(self,effect_id,kind,body):
        if not isinstance(effect_id,str) or not 1<=len(effect_id)<=256 or not isinstance(body,str) or len(body.encode())>16000:
            raise ValueError("invalid_public_effect")
        key=hashlib.sha256(encoded(dict(source=self.source,effect_id=effect_id,kind=kind)).encode()).hexdigest()
        fingerprint=hashlib.sha256(body.encode()).hexdigest()
        row=self.store.db.execute("SELECT fingerprint,data FROM issue_public_effects WHERE effect_key=?",(key,)).fetchone()
        if row:
            if row[0]!=fingerprint: raise ValueError("public_effect_conflict")
            return key,json.loads(row[1]),False
        data=dict(kind=kind,state="intent")
        with self.store.db: self.store.db.execute("INSERT INTO issue_public_effects VALUES (?,?,?)",(key,fingerprint,encoded(data)))
        return key,data,True

    def _save(self,key,data):
        with self.store.db: self.store.db.execute("UPDATE issue_public_effects SET data=? WHERE effect_key=?",(encoded(data),key))
        return data

    def ensure_comment(self,effect_id,issue,body):
        with self.store.lock:
            self._fresh(issue); key,data,new=self._intent(effect_id,"comment",body)
            if data["state"]=="confirmed": return data["receipt"]
            public=body+"\n\n<!-- task-tower-effect:"+key+" -->"
            path="/issues/"+str(issue)+"/comments"; r=self.source["repository"]
            rows=self.host._pages(r,path)
            matches=[v for v in rows if v.get("body")==public and v.get("user",{}).get("id")==self.host._creator()]
            if not matches and new:
                try: self.host._request(r,"POST",path,dict(body=public))
                except Exception: pass
                try:
                    matches=[v for v in self.host._pages(r,path) if v.get("body")==public and v.get("user",{}).get("id")==self.host._creator()]
                except Exception: matches=[]
            if len(matches)!=1 or type(matches[0].get("id")) is not int or matches[0]["id"]<1:
                self._save(key,dict(kind="comment",state="unknown"))
                raise ValueError("public_comment_needs_reconciliation")
            row=matches[0]; url="https://github.com/"+r+"/issues/"+str(issue)+"#issuecomment-"+str(row["id"])
            if row.get("html_url")!=url: raise ValueError("public_comment_identity_mismatch")
            receipt=dict(comment_id=row["id"],url=url,effect_sha256=key)
            self._save(key,dict(kind="comment",state="confirmed",receipt=receipt)); return receipt

    def finalize_issue(self,accepted_attempt,effect_id):
        a=accepted_attempt; s=self.source
        if (a.get("phase")!="accepted" or not a.get("canonical_close") or not a.get("accepted_evidence") or a.get("repository")!=s["repository"] or a.get("source_issue")!=s or not re.fullmatch(r"[a-f0-9]{40}",a.get("main_sha",""))):
            raise ValueError("canonical_issue_acceptance_required")
        with self.store.lock:
            issue=s["issue_number"]; current=self._fresh(issue)
            key,data,new=self._intent(effect_id,"close",a["main_sha"])
            if data["state"]=="confirmed": return data["receipt"]
            if new and current.get("state")=="open":
                try: self.host._request(s["repository"],"PATCH","/issues/"+str(issue),dict(state="closed",state_reason="completed"))
                except Exception: pass
            current=self._fresh(issue)
            if current.get("state")!="closed":
                self._save(key,dict(kind="close",state="unknown")); raise ValueError("issue_close_needs_reconciliation")
            receipt=dict(state="closed",url="https://github.com/"+s["repository"]+"/issues/"+str(issue),main_sha=a["main_sha"])
            self._save(key,dict(kind="close",state="confirmed",receipt=receipt)); return receipt
