"""Deterministic, auditable recommendation engine. No external services."""
GRADES = ["Junior", "Middle", "Senior", "Lead"]


def next_grade(employee):
    index = GRADES.index(employee["grade"])
    return GRADES[min(index + 1, len(GRADES) - 1)]


def recommend(employee, events, history, skills):
    target = next_grade(employee)
    catalog = {event["id"]: event for event in events}
    personal = [row for row in history if row["employee_id"] == employee["employee_id"]]
    completed = {row["event_id"] for row in personal if row["status"] == "completed"}
    results = []
    for event in events:
        if event["id"] in completed or employee["role"] not in event["target_audience"]:
            continue
        factors = []
        for skill, rule in event["skill_gains"].items():
            current = employee["skills"].get(skill, 0)
            required = skills[skill]["requirements"].get(target, 0)
            gap = max(0, required - current)
            effective_gain = min(gap, rule["gain"], max(0, rule["max_level"] - current))
            if not effective_gain:
                continue
            related = [h for h in personal if skill in catalog[h["event_id"]]["skill_gains"]]
            same_format = [h for h in personal if catalog[h["event_id"]]["type"] == event["type"]]
            def probability(rows):
                return (sum(h["status"] == "completed" for h in rows) + 1) / (len(rows) + 2)
            acceptance = (probability(related) + probability(same_format)) / 2
            criticality = skills[skill].get("criticality", {}).get(target, 1)
            score = effective_gain * gap * criticality * acceptance
            factors.append(dict(skill=skill, current=current, required=required, gap=gap,
                effective_gain=effective_gain, criticality=criticality, acceptance=round(acceptance, 4),
                history_count=len(related), completed_count=sum(h["status"] == "completed" for h in related),
                score=round(score, 4)))
        if factors:
            results.append(dict(event=event, target_grade=target, score=round(sum(f["score"] for f in factors), 4), factors=factors))
    results.sort(key=lambda item: (-item["score"], item["event"]["id"]))
    return {"recommendations": results[:3], "alternatives": results[3:], "explanation_mode": "deterministic"}


def complete(employee, event, history):
    if employee["role"] not in event["target_audience"]:
        raise ValueError("Activity is not available for this role")
    if any(h["employee_id"] == employee["employee_id"] and h["event_id"] == event["id"] and h["status"] == "completed" for h in history):
        return False
    for skill, rule in event["skill_gains"].items():
        current = employee["skills"].get(skill, 0)
        employee["skills"][skill] = max(current, min(5, current + rule["gain"], rule["max_level"]))
    from datetime import date
    history.append(dict(employee_id=employee["employee_id"], event_id=event["id"], status="completed", date=date.today().isoformat()))
    return True
