import csv
import json
import os
import secrets
from copy import deepcopy
from pathlib import Path
from threading import RLock
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .engine import recommend, complete, next_grade

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Career Quest", version="0.1.0")
security = HTTPBearer()
lock = RLock()
data = {name: json.loads((ROOT / "data" / (name + ".json")).read_text(encoding="utf-8")) for name in ["employees", "events", "skills"]}
with (ROOT / "data/activity_history.csv").open(encoding="utf-8", newline="") as stream:
    data["history"] = list(csv.DictReader(stream))
EMPLOYEE_TOKEN = os.environ.get("EMPLOYEE_TOKEN", "")
HR_TOKEN = os.environ.get("HR_TOKEN", "")


def identity(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if EMPLOYEE_TOKEN and secrets.compare_digest(token, EMPLOYEE_TOKEN):
        return "employee"
    if HR_TOKEN and secrets.compare_digest(token, HR_TOKEN):
        return "hr"
    raise HTTPException(401, "Invalid credentials; configure tokens on the server")


def employee_auth(role=Depends(identity)):
    if role != "employee":
        raise HTTPException(403, "Employee access required")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/me", dependencies=[Depends(employee_auth)])
def me():
    with lock:
        employee = deepcopy(data["employees"][0])
        target = next_grade(employee)
        requirements = {k: v["requirements"].get(target, 0) for k,v in data["skills"].items()}
        total = sum(requirements.values())
        ready = sum(min(employee["skills"].get(k, 0), v) for k,v in requirements.items())
        return {"employee": employee, "target_grade": target, "requirements": requirements,
                "readiness": round(100 * ready / total) if total else 100,
                "history": [h for h in data["history"] if h["employee_id"] == employee["employee_id"]]}


@app.get("/api/recommendations", dependencies=[Depends(employee_auth)])
def recommendations():
    with lock:
        return recommend(data["employees"][0], data["events"], data["history"], data["skills"])


@app.post("/api/activities/{event_id}/complete", dependencies=[Depends(employee_auth)])
def finish(event_id: str):
    with lock:
        event = next((e for e in data["events"] if e["id"] == event_id), None)
        if not event:
            raise HTTPException(404, "Unknown activity")
        try:
            changed = complete(data["employees"][0], event, data["history"])
        except ValueError as error:
            raise HTTPException(403, str(error))
        return {"changed": changed, "profile": me()}


@app.get("/api/hr/summary")
def hr(role=Depends(identity)):
    if role != "hr":
        raise HTTPException(403, "HR access required")
    with lock:
        deficits = {}
        no_step = 0
        for employee in data["employees"]:
            target = next_grade(employee)
            for skill, info in data["skills"].items():
                if employee["skills"].get(skill, 0) < info["requirements"].get(target, 0):
                    deficits[skill] = deficits.get(skill, 0) + 1
            no_step += not recommend(employee, data["events"], data["history"], data["skills"])["recommendations"]
        return {"employee_count": len(data["employees"]), "without_recommendations": no_step, "skill_deficits": deficits}
