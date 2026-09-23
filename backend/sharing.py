"""Explicit consent, allowlisted snapshots and authenticated recipient ACLs."""
import json
import secrets
from contextlib import closing
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    alias: str = Field(min_length=1,max_length=40)
    style: Literal["anime","football"]
    achievement_ids: list[str] = Field(max_length=10)
    recipients: list[str] = Field(min_length=1,max_length=20)
    expected_revision: int = Field(ge=1)


def register_sharing(app, store, employee_auth, known_accounts, demo_mode):
    def eligible(data, owner):
        completed = {h["event_id"] for h in data["history"] if h["employee_id"]==owner and h["status"]=="completed"}
        return {e["id"]:e["title"] for e in data["events"] if e["id"] in completed and not e.get("mandatory",False)}

    def snapshot(payload, data, owner):
        if not any(e["employee_id"]==owner for e in data["employees"]):
            raise HTTPException(404,"Profile absent")
        if any(person not in known_accounts or person==owner for person in payload.recipients):
            raise HTTPException(422,"Recipients must be other registered employee IDs")
        if len(set(payload.achievement_ids)) != len(payload.achievement_ids):
            raise HTTPException(422,"Duplicate achievement")
        allowed = eligible(data,owner)
        if any(key not in allowed for key in payload.achievement_ids):
            raise HTTPException(422,"Only completed voluntary activities can be shared")
        # Explicit projection: no employee_id, scores, grade, skills, balance or history.
        return {"alias":payload.alias,"style":payload.style,
                "achievements":[allowed[key] for key in payload.achievement_ids],"demo":demo_mode}

    @app.get("/api/sharing/options")
    def options(owner=Depends(employee_auth)):
        data, revision = store.read()
        return {"achievements":[{"id":key,"title":title} for key,title in eligible(data,owner).items()],"revision":revision}

    @app.post("/api/sharing/preview")
    def preview(payload: ShareRequest, owner=Depends(employee_auth)):
        data, revision = store.read()
        if payload.expected_revision != revision: raise HTTPException(409,"Refresh before sharing")
        return {"card":snapshot(payload,data,owner),"recipients":list(dict.fromkeys(payload.recipients))}

    @app.post("/api/sharing")
    def share(payload: ShareRequest, owner=Depends(employee_auth)):
        with store.transaction() as tx:
            if payload.expected_revision != tx["revision"]: raise HTTPException(409,"Refresh before sharing")
            card = snapshot(payload,tx["data"],owner)
            count = tx["db"].execute("SELECT COUNT(*) FROM shares WHERE owner=?",(owner,)).fetchone()[0]
            if count>=20: raise HTTPException(409,"Revoke an existing card before creating another")
            identifier = secrets.token_urlsafe(24)
            tx["db"].execute("INSERT INTO shares VALUES (?,?,?,?)",(identifier,owner,json.dumps(list(dict.fromkeys(payload.recipients))),json.dumps(card)))
        return {"id":identifier,"card":card}

    @app.get("/api/sharing")
    def mine(owner=Depends(employee_auth)):
        with closing(store.connect()) as db:
            rows=db.execute("SELECT id,recipients,card FROM shares WHERE owner=?",(owner,)).fetchall()
        return {"shares":[{"id":i,"recipients":json.loads(a),"card":json.loads(c)} for i,a,c in rows]}

    @app.delete("/api/sharing/{identifier}")
    def revoke(identifier:str, owner=Depends(employee_auth)):
        with store.transaction() as tx:
            tx["db"].execute("DELETE FROM shares WHERE id=? AND owner=?",(identifier,owner))
        return {"revoked":True}

    @app.get("/api/shared/{identifier}")
    def read(identifier:str, viewer=Depends(employee_auth)):
        with closing(store.connect()) as db:
            row=db.execute("SELECT owner,recipients,card FROM shares WHERE id=?",(identifier,)).fetchone()
        if row is None or (viewer!=row[0] and viewer not in json.loads(row[1])):
            raise HTTPException(404,"Card unavailable or access revoked")
        return json.loads(row[2])
