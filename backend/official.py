"""Strict adapter for the organizer's Career Quest v1 schema."""
import csv
import io
from datetime import date
from typing import Annotated, Literal
from pydantic import Field, AfterValidator, ValidationError
from .dataset import Model, Identifier, Level, Grade, Gain, DatasetError

def iso(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError('Expected YYYY-MM-DD')
    return value
Day = Annotated[str, AfterValidator(iso)]
Text = Annotated[str, Field(min_length=1, max_length=4000)]

class Meta(Model):
    dataset: Literal['Career Quest']
    version: Literal['1.0']
    as_of_date: Day
class Goal(Model):
    target_role: Text
    target_grade: Grade
class Person(Model):
    employee_id: Identifier
    full_name: Text
    department: Text
    role: Text
    grade: Grade
    manager_id: Identifier | None
    hire_date: Day
    tenure_months: Annotated[int, Field(ge=0,le=1200)]
    work_format: Literal['office','hybrid','remote']
    preferred_language: Literal['kk','ru','en']
    career_goal: Goal | None
    skills: dict[Identifier,Level]
    last_review_date: Day
class Development(Gain):
    skill_id: Identifier
class Activity(Model):
    event_id: Identifier
    title: Text
    description: Text
    type: Literal['compliance','onboarding','course','workshop','mentoring','certification','meetup']
    format: Literal['online','offline','self_paced']
    duration_hours: Annotated[float, Field(gt=0,le=10000)]
    mandatory: bool
    target_roles: Annotated[list[Text],Field(min_length=1)]
    target_grades: Annotated[list[Grade],Field(min_length=1)]
    develops_skills: list[Development]
    prerequisites: dict[Identifier,Level]
    upcoming_sessions: list[Day]
class Competency(Model):
    skill_id: Identifier
    name: Text
    type: Literal['hard','soft']
    category: Text
    description: Text
class Profile(Model):
    role: Text
    grade: Grade
    required_skills: dict[Identifier,Level]
    critical_skills: list[Identifier]
class PeopleFile(Model):
    meta: Meta
    employees: Annotated[list[Person],Field(min_length=1,max_length=10000)]
class EventsFile(Model):
    meta: Meta
    events: Annotated[list[Activity],Field(max_length=5000)]
class SkillsFile(Model):
    meta: Meta
    proficiency_scale: dict[str,Text]
    skills: Annotated[list[Competency],Field(min_length=1,max_length=1000)]
    role_profiles: list[Profile]
class Record(Model):
    record_id: Identifier
    employee_id: Identifier
    event_id: Identifier
    date: Day
    due_date: Day | None
    status: Literal['completed','in_progress','dropped','no_show','declined','overdue']
    completion_pct: Annotated[int,Field(ge=0,le=100)]
    score: Annotated[int,Field(ge=0,le=100)] | None
    feedback_rating: Annotated[int,Field(ge=1,le=5)] | None
    assigned_by: Literal['self','manager','hr']

HEADER=['record_id','employee_id','event_id','date','due_date','status','completion_pct','score','feedback_rating','assigned_by']

def adapt(raw, history_text):
    def fail(path,message):
        raise DatasetError([{'path':path,'message':message}])
    try:
        people=PeopleFile.model_validate(raw['employees']).model_dump()
        events=EventsFile.model_validate(raw['events']).model_dump()
        skills=SkillsFile.model_validate(raw['skills']).model_dump()
        reader=csv.DictReader(io.StringIO(history_text.lstrip('\ufeff')),strict=True)
        if reader.fieldnames!=HEADER: fail('activity_history.csv','Unexpected official CSV header')
        history=[]
        for index,row in enumerate(reader):
            if index>=200000:fail('activity_history.csv','Too many records')
            for key in ['completion_pct','score','feedback_rating']:
                value=row.get(key)
                if value=='' and key!='completion_pct': row[key]=None
                elif isinstance(value,str) and value.isascii() and value.isdigit(): row[key]=int(value)
                else:fail(f'history.{index}.{key}','Expected integer or allowed empty value')
            if row.get('due_date')=='':row['due_date']=None
            history.append(Record.model_validate(row).model_dump())
    except ValidationError as error:
        raise DatasetError([{'path':'official.'+'.'.join(map(str,e['loc'])),'message':e['msg']} for e in error.errors()]) from error
    except (csv.Error,ValueError) as error:
        if isinstance(error,DatasetError):raise
        fail('official','Malformed CSV or field value')
    as_of=people['meta']['as_of_date']
    if any(doc['meta']!=people['meta'] for doc in [events,skills]):fail('meta','Metadata must match across files')
    if set(skills['proficiency_scale'])!={str(i) for i in range(6)}:fail('proficiency_scale','Expected levels 0 to 5')
    def unique(rows,key,path):
        result={r[key]:r for r in rows}
        if len(result)!=len(rows):fail(path,'Duplicate identifier')
        return result
    persons=unique(people['employees'],'employee_id','employees')
    catalog=unique(events['events'],'event_id','events')
    competencies=unique(skills['skills'],'skill_id','skills')
    unique(history,'record_id','history')
    profiles={}
    normalized={k:{'name':v['name'],'requirements':{},'criticality':{},'role_requirements':{},'role_criticality':{}} for k,v in competencies.items()}
    for p in skills['role_profiles']:
        key=(p['role'],p['grade'])
        if key in profiles:fail('role_profiles','Duplicate role/grade')
        profiles[key]=p
        if not set(p['critical_skills'])<=set(p['required_skills']):fail('role_profiles','Critical skill must have a requirement')
        for k,n in p['required_skills'].items():
            if k not in normalized:fail('role_profiles','Unknown skill')
            normalized[k]['role_requirements'].setdefault(p['role'],{})[p['grade']]=n
            normalized[k]['role_criticality'].setdefault(p['role'],{})[p['grade']]=3 if k in p['critical_skills'] else 1
    roles={p['role'] for p in skills['role_profiles']}
    for role in roles:
        previous={}
        for grade in ['Junior','Middle','Senior','Lead']:
            if (role,grade) not in profiles:fail('role_profiles','Missing grade for role')
            req=profiles[(role,grade)]['required_skills']
            if any(req.get(k,0)<n for k,n in previous.items()):fail('role_profiles','Requirements decrease with grade')
            previous=req
    for p in persons.values():
        if (p['role'],p['grade']) not in profiles:fail('employees','Unknown role/grade')
        if set(p['skills'])-set(normalized):fail('employees','Unknown skill')
        if not p['hire_date']<=p['last_review_date']<=as_of:fail('employees','Invalid review/hire date')
        goal=p['career_goal']
        if goal and (goal['target_role'],goal['target_grade']) not in profiles:fail('career_goal','Unknown role/grade')
        if p['manager_id']:
            manager=persons.get(p['manager_id'])
            if not manager or manager['employee_id']==p['employee_id'] or manager['grade']!='Lead' or manager['department']!=p['department']:
                fail('employees.manager_id','Invalid department manager')
    converted=[]
    for e in catalog.values():
        if set(e['target_roles'])-roles:fail('events.target_roles','Unknown role')
        gains=unique(e['develops_skills'],'skill_id','events.develops_skills')
        if (set(gains)|set(e['prerequisites']))-set(normalized):fail('events','Unknown skill')
        if e['format']=='self_paced' and e['upcoming_sessions']:fail('events','Self-paced sessions must be empty')
        if any(d<as_of for d in e['upcoming_sessions']):fail('events','Upcoming session before snapshot')
        converted.append({'id':e['event_id'],'title':e['title'],'type':e['type'],'format':e['format'],
            'mandatory':e['mandatory'],'target_audience':e['target_roles'],'target_grades':e['target_grades'],
            'skill_gains':{k:{'gain':g['gain'],'max_level':g['max_level']} for k,g in gains.items()},
            'prerequisites':e['prerequisites'],'upcoming_sessions':e['upcoming_sessions'],
            'repeatable':e['event_id']=='EV_036'})
    seen_completed=set()
    for h in sorted(history,key=lambda h:(h['date'],h['record_id'])):
        p=persons.get(h['employee_id']);e=catalog.get(h['event_id'])
        if not p or not e:fail('history','Unknown employee or event')
        if h['date']>as_of:fail('history.date','History after snapshot')
        if h['status']=='completed' and h['completion_pct']!=100:fail('history','Completed must be 100 percent')
        if h['status']!='completed' and h['completion_pct']>95:fail('history','Unfinished progress must be <=95')
        if h['status'] in {'no_show','declined'} and h['completion_pct']!=0:fail('history','No-show/declined must be zero')
        if h['status']=='no_show' and e['format']=='self_paced':fail('history','No-show requires a session')
        if h['due_date'] and not e['mandatory']:fail('history.due_date','Only mandatory events have deadlines')
        if h['status']=='overdue' and (not e['mandatory'] or not h['due_date'] or h['due_date']>=as_of):fail('history','Invalid overdue status')
        if h['status']=='completed':
            key=(h['employee_id'],h['event_id'])
            if key in seen_completed and e['event_id']!='EV_036' and not e['mandatory']:fail('history','Non-repeatable completion repeated')
            seen_completed.add(key)
            if h['date']>p['last_review_date']:
                for g in e['develops_skills']:
                    current=p['skills'].get(g['skill_id'],0)
                    p['skills'][g['skill_id']]=max(current,min(current+g['gain'],g['max_level'],5))
    return {'as_of_date':as_of,'employees':[{'employee_id':p['employee_id'],'role':p['role'],'grade':p['grade'],
        'tenure_months':p['tenure_months'],'skills':p['skills'],'as_of_date':as_of,'career_goal':p['career_goal']} for p in persons.values()],
        'events':converted,'skills':normalized,'history':[{k:h[k] for k in ['employee_id','event_id','status','date','due_date','assigned_by','record_id']} for h in history]}
