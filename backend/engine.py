"""Deterministic, auditable recommendation engine. No external services."""
from datetime import date

GRADES = ["Junior", "Middle", "Senior", "Lead"]


def next_grade(employee):
    index = GRADES.index(employee["grade"])
    return GRADES[min(index + 1, len(GRADES) - 1)]


def reference_date(employee):
    return employee.get('as_of_date') or date.today().isoformat()


def required_level(skill, employee):
    target = next_grade(employee)
    if skill.get('role_requirements'):
        return skill['role_requirements'].get(employee['role'], {}).get(target, 0)
    return skill['requirements'].get(target, 0)


def critical_weight(skill, employee):
    target = next_grade(employee)
    if skill.get('role_requirements'):
        return skill.get('role_criticality', {}).get(employee['role'], {}).get(target, 1)
    return skill.get('criticality', {}).get(target, 1)


def eligible(employee, event):
    if employee['role'] not in event['target_audience']:
        return False
    if event.get('target_grades') and employee['grade'] not in event['target_grades']:
        return False
    return all(employee['skills'].get(k, 0) >= n for k, n in event.get('prerequisites', {}).items())


def event_format(event):
    return event.get('format') or event['type']


def recommend(employee, events, history, skills):
    target = next_grade(employee)
    catalog = {event["id"]: event for event in events}
    today = reference_date(employee)
    personal = [row for row in history if row["employee_id"] == employee["employee_id"] and row["date"] <= today]
    completed = {row["event_id"] for row in personal if row["status"] == "completed"}
    results = []
    for event in events:
        if event.get('mandatory', False) or not eligible(employee,event):
            continue
        event_history = [h for h in personal if h['event_id']==event['id']]
        if event['id'] in completed and not event.get('repeatable',False):
            continue
        if event.get('repeatable') and any(h['status']=='completed' and h['date']==today for h in event_history):
            continue
        latest=max(event_history,key=lambda h:(h['date'],h.get('record_id') or ''),default=None)
        if latest and latest['status']=='in_progress':
            continue
        if event.get('upcoming_sessions') is not None and event.get('format')!='self_paced' and not any(day>=today for day in event['upcoming_sessions']):
            continue
        factors = []
        for skill, rule in event["skill_gains"].items():
            current = employee["skills"].get(skill, 0)
            required = required_level(skills[skill], employee)
            gap = max(0, required - current)
            effective_gain = min(gap, rule["gain"], max(0, rule["max_level"] - current))
            if not effective_gain:
                continue
            related = [h for h in personal if h["status"] not in {"in_progress","overdue"} and not catalog[h["event_id"]].get("mandatory",False) and skill in catalog[h["event_id"]]["skill_gains"]]
            same_format = [h for h in personal if h["status"] not in {"in_progress","overdue"} and not catalog[h["event_id"]].get("mandatory",False) and event_format(catalog[h["event_id"]]) == event_format(event)]
            def probability(rows):
                return (sum(h["status"] == "completed" for h in rows) + 1) / (len(rows) + 2)
            acceptance = (probability(related) + probability(same_format)) / 2
            criticality = critical_weight(skills[skill], employee)
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
    if not eligible(employee,event):
        raise ValueError("Activity is not available for this role")
    today=reference_date(employee)
    personal=[h for h in history if h['employee_id']==employee['employee_id'] and h['event_id']==event['id'] and h['date']<=today]
    completed=[h for h in personal if h['status']=='completed']
    latest=max(personal,key=lambda h:(h['date'],h.get('record_id') or ''),default=None)
    if event.get('mandatory') and employee.get('as_of_date') and not personal:
        raise ValueError('Mandatory activity has not been assigned')
    if event.get('mandatory'):
        if latest and latest['status']=='completed':return False
    elif event.get('repeatable'):
        if any(h['date']==today for h in completed):return False
    elif completed:return False
    if event.get('upcoming_sessions') is not None and event.get('format')!='self_paced' and not any(day>=today for day in event['upcoming_sessions']):
        raise ValueError('No available session')
    for skill, rule in event["skill_gains"].items():
        current = employee["skills"].get(skill, 0)
        employee["skills"][skill] = max(current, min(5, current + rule["gain"], rule["max_level"]))
    history.append(dict(employee_id=employee["employee_id"], event_id=event["id"], status="completed", date=today, due_date=latest.get("due_date") if latest else None))
    return True
