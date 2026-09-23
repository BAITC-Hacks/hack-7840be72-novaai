import hashlib
import json
import os
import secrets
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from .engine import recommend, complete, next_grade
from .dataset import DatasetError, MAX_BYTES, load_directory, parse_files
from .storage import Store
from .reporting import register_reporting, mandatory_training

ROOT = Path(__file__).resolve().parent.parent

class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    files: dict[str, str]
    expected_revision: int | None = None
    digest: str | None = None

class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=1)


def create_app(db_path=None, employee_token=None, hr_token=None, employee_id=None, accounts=None, demo_mode=None, managers=None, coach_gateway=None):
    app = FastAPI(title="Career Quest", version="0.2.0")
    security = HTTPBearer()
    store = Store(db_path or os.environ.get("CQ_DB_PATH", ROOT/".runtime/career-quest.sqlite3"), load_directory(ROOT/"data"))
    employee_token = employee_token if employee_token is not None else os.environ.get("EMPLOYEE_TOKEN", "")
    hr_token = hr_token if hr_token is not None else os.environ.get("HR_TOKEN", "")
    employee_id = employee_id or os.environ.get("EMPLOYEE_ID", "E0028")
    if employee_token and employee_token == hr_token:
        raise ValueError("Employee and HR tokens must be different")
    accounts = accounts if accounts is not None else json.loads(os.environ.get("EMPLOYEE_ACCOUNTS_JSON", "{}"))
    accounts = dict(accounts)
    if employee_token: accounts[employee_token] = employee_id
    if hr_token in accounts: raise ValueError("HR token must not match an employee token")
    if any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in accounts.items()):
        raise ValueError("Invalid employee account configuration")
    demo_mode = demo_mode if demo_mode is not None else os.environ.get("DEMO_MODE", "false").lower() == "true"
    managers = managers if managers is not None else json.loads(os.environ.get("MANAGER_ACCOUNTS_JSON", "{}"))
    if not isinstance(managers,dict): raise ValueError("Manager accounts must be a mapping")
    for key, ids in managers.items():
        if not isinstance(key,str) or not key or key in accounts or key == hr_token:
            raise ValueError("Manager tokens must be distinct")
        if not isinstance(ids,list) or any(not isinstance(value,str) or not value for value in ids):
            raise ValueError("Manager scope must be a list of employee IDs")
    app.state.store = store

    @app.middleware("http")
    async def body_limit(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            # Bound actual streamed bytes; Content-Length can be omitted or forged.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BYTES * 2:
                    return JSONResponse(status_code=413, content={"detail":"Request exceeds 24 MiB"})
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DatasetError)
    async def invalid_dataset(request, error):
        return JSONResponse(status_code=422, content={"detail":error.errors})

    def identity(credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials
        for key, person_id in accounts.items():
            if secrets.compare_digest(token.encode("utf-8"),key.encode("utf-8")): return {"role":"employee", "employee_id":person_id}
        if hr_token and secrets.compare_digest(token.encode("utf-8"), hr_token.encode("utf-8")): return {"role":"hr"}
        for key, ids in managers.items():
            if secrets.compare_digest(token.encode("utf-8"),key.encode("utf-8")): return {"role":"manager", "employee_ids":ids}
        raise HTTPException(401, "Invalid credentials")

    def employee_auth(role=Depends(identity)):
        if role["role"] != "employee": raise HTTPException(403, "Employee access required")
        return role["employee_id"]

    def hr_auth(role=Depends(identity)):
        if role["role"] != "hr": raise HTTPException(403, "HR access required")

    def employee(data, person_id):
        value = next((e for e in data["employees"] if e["employee_id"] == person_id), None)
        if not value: raise HTTPException(404, "Account profile absent from dataset; ask administrator to configure EMPLOYEE_ID")
        return value

    def profile(data, revision, person_id):
        person = employee(data, person_id)
        target = next_grade(person)
        requirements = {k:v["requirements"].get(target,0) for k,v in data["skills"].items()}
        total = sum(requirements.values())
        ready = sum(min(person["skills"].get(k,0),v) for k,v in requirements.items())
        return {"employee":person,"target_grade":target,"requirements":requirements,"revision":revision,
            "readiness":round(100*ready/total) if total else 100, "demo_mode":demo_mode,
            "history":[h for h in data["history"] if h["employee_id"] == person_id],
            "mandatory_training":mandatory_training(person,data)}

    @app.get("/api/health")
    def health(): return {"status":"ok","version":"0.2.0"}

    @app.get("/api/session")
    def session(role=Depends(identity)): return {**role, "demo_mode":demo_mode}

    @app.get("/api/me", dependencies=[Depends(employee_auth)])
    def me(person_id=Depends(employee_auth)):
        data, revision = store.read()
        return profile(data, revision, person_id)

    @app.get("/api/recommendations", dependencies=[Depends(employee_auth)])
    def recommendations(person_id=Depends(employee_auth)):
        data, revision = store.read()
        return {**recommend(employee(data, person_id),data["events"],data["history"],data["skills"]), "revision":revision}

    @app.post("/api/activities/{event_id}/complete", dependencies=[Depends(employee_auth)])
    def finish(event_id: str, payload: CompletionRequest, person_id=Depends(employee_auth)):
        if not demo_mode: raise HTTPException(403,"Self-completion is available only in explicit demo mode; LMS verification is required")
        with store.transaction() as tx:
            data = tx["data"]
            if payload.expected_revision != tx["revision"]:
                raise HTTPException(409, "Data changed; refresh profile before completing activity")
            event = next((e for e in data["events"] if e["id"] == event_id), None)
            if not event: raise HTTPException(404, "Unknown activity")
            try: tx["changed"] = complete(employee(data, person_id),event,data["history"])
            except ValueError as error: raise HTTPException(403,str(error))
            return {"changed":tx["changed"],"profile":profile(data,tx["revision"]+int(tx["changed"]),person_id)}

    register_reporting(app, store, identity)

    def prepare(payload):
        data = parse_files(payload.files)
        digest = hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        return data, digest

    @app.post("/api/hr/import/preview", dependencies=[Depends(hr_auth)])
    def preview(payload: ImportRequest):
        data, digest = prepare(payload)
        _, revision = store.read()
        warnings = []
        if not any(e["employee_id"]==employee_id for e in data["employees"]):
            warnings.append("Current employee account is absent; it will lose profile access after import. Configure EMPLOYEE_ID on the server.")
        return {"counts":{k:len(v) for k,v in data.items()},"digest":digest,"revision":revision,"warnings":warnings}

    @app.post("/api/hr/import", dependencies=[Depends(hr_auth)])
    def import_dataset(payload: ImportRequest):
        data, digest = prepare(payload)
        if payload.digest != digest: raise HTTPException(409,"Preview this exact dataset before importing")
        with store.transaction() as tx:
            if payload.expected_revision != tx["revision"]:
                raise HTTPException(409,"Data changed since preview; preview again")
            tx["db"].execute("DELETE FROM shares")
            tx["data"] = data
            tx["changed"] = True
            revision = tx["revision"] + 1
        return {"imported":True,"revision":revision}

    from .coach import register_coach
    register_coach(app, store.read, employee_auth, coach_gateway)
    from .sharing import register_sharing
    register_sharing(app, store, employee_auth, set(accounts.values()), demo_mode)
    return app

app = create_app()
