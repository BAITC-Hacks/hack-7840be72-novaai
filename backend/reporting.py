"""Service views: explicit projections and server-side team scoping."""
from datetime import date
from fastapi import Depends, HTTPException
from .engine import recommend, next_grade
from .insights import stagnation


def mandatory_training(person, data, today=None):
    today = today or date.today()
    rows = []
    for event in data["events"]:
        if not event.get("mandatory", False) or person["role"] not in event["target_audience"]:
            continue
        history = [h for h in data["history"] if h["employee_id"] == person["employee_id"] and h["event_id"] == event["id"]]
        completed = [h for h in history if h["status"] == "completed"]
        due = event.get("due_date")
        status = "completed" if completed else "overdue" if due and date.fromisoformat(due) < today else "pending"
        rows.append({"event_id":event["id"], "title":event["title"], "due_date":due,
                     "status":status, "completed_at":max((h["date"] for h in completed), default=None)})
    return rows


def recommendation_state(person, data):
    if recommend(person,data["events"],data["history"],data["skills"])["recommendations"]:
        return "available"
    target=next_grade(person)
    gaps=any(person["skills"].get(k,0)<v["requirements"].get(target,0) for k,v in data["skills"].items())
    return "catalog_gap" if gaps else "requirements_met"


def register_reporting(app, store, identity):
    def staff(claims=Depends(identity)):
        if claims["role"] not in {"hr","manager"}: raise HTTPException(403,"Staff access required")
        return claims

    def scoped(data, claims):
        if claims["role"] == "hr": return data["employees"]
        allowed=set(claims["employee_ids"])
        return [p for p in data["employees"] if p["employee_id"] in allowed]

    @app.get("/api/hr/summary")
    def summary(claims=Depends(staff)):
        data, revision=store.read()
        people=scoped(data,claims)
        ids={p["employee_id"] for p in people}
        history=[h for h in data["history"] if h["employee_id"] in ids]
        deficits={}
        for person in people:
            target=next_grade(person)
            for skill,info in data["skills"].items():
                if person["skills"].get(skill,0)<info["requirements"].get(target,0): deficits[skill]=deficits.get(skill,0)+1
        participation={s:sum(h["status"]==s for h in history) for s in ["completed","skipped","declined"]}
        return {"employee_count":len(people),"without_recommendations":sum(recommendation_state(p,data)!="available" for p in people),
                "skill_deficits":deficits,"participation":participation,"revision":revision}

    @app.get("/api/hr/employees")
    def employees(claims=Depends(staff)):
        data, revision=store.read()
        rows=[]
        for person in sorted(scoped(data,claims),key=lambda p:p["employee_id"]):
            rows.append({"employee_id":person["employee_id"],"role":person["role"],"grade":person["grade"],
                "recommendation_state":recommendation_state(person,data),"mandatory_training":mandatory_training(person,data),"stagnation":stagnation(person,data["history"])})
        return {"employees":rows,"revision":revision}

    @app.get("/api/hr/employees/{person_id}")
    def employee_detail(person_id:str, claims=Depends(staff)):
        data, revision=store.read()
        person=next((p for p in scoped(data,claims) if p["employee_id"]==person_id),None)
        if not person: raise HTTPException(404,"Employee not found in your scope")
        return {"employee_id":person["employee_id"],"role":person["role"],"grade":person["grade"],
            "recommendation_state":recommendation_state(person,data),"mandatory_training":mandatory_training(person,data),"stagnation":stagnation(person,data["history"]),"revision":revision}

    @app.post("/api/hr/employees/{person_id}/support-proposal")
    def support_proposal(person_id:str, claims=Depends(staff)):
        data, revision=store.read()
        person=next((p for p in scoped(data,claims) if p["employee_id"]==person_id),None)
        if not person: raise HTTPException(404,"Employee not found in your scope")
        candidates=recommend(person,data["events"],data["history"],data["skills"])["recommendations"]
        return {"employee_id":person_id,"target_grade":next_grade(person),"revision":revision,
            "mode":"rule_based_draft","sent":False,
            "activities":[{"id":c["event"]["id"],"title":c["event"]["title"],"format":c["event"]["type"]} for c in candidates],
            "mentor_request":{"status":"directory_required","focus_skills":list(dict.fromkeys(f["skill"] for c in candidates[:1] for f in c["factors"]))},
            "signals":stagnation(person,data["history"])}
