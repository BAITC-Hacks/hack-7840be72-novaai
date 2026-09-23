"""Explainable support signals, not a prediction of employee attrition."""
import calendar
from datetime import date


def six_months_before(today):
    month_index=today.year*12+today.month-1-6
    year,month=divmod(month_index,12);month+=1
    return date(year,month,min(today.day,calendar.monthrange(year,month)[1]))


def stagnation(person, history, today=None):
    today=today or date.today()
    cutoff=six_months_before(today)
    rows=[h for h in history if h['employee_id']==person['employee_id'] and date.fromisoformat(h['date'])<=today]
    completed=[date.fromisoformat(h['date']) for h in rows if h['status']=='completed']
    last=max(completed,default=None)
    coverage=bool(rows) and min(date.fromisoformat(h['date']) for h in rows)<cutoff and person['tenure_months']>=6
    inactive=(last<cutoff) if last else coverage
    # Equal-day ordering is unknown. A completion/decline on that day breaks a skip streak.
    streak=0
    recommended=[h for h in rows if h.get('recommended',False)]
    days={h['date'] for h in recommended}
    for day in sorted(days,reverse=True):
        group=[h for h in recommended if h['date']==day]
        if any(h['status']!='skipped' or not h.get('recommended',False) for h in group):break
        streak+=len(group)
    reasons=[]
    if inactive:reasons.append('no_completion_six_months')
    if streak>=3:reasons.append('three_recommendations_skipped')
    return {'flagged':bool(reasons),'reasons':reasons,'insufficient_history':not completed and not coverage,
            'recommendation_tracking_available':any(h.get('recommended',False) for h in rows)}
