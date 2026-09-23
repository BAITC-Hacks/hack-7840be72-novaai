import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from backend.dataset import FILES, DatasetError, parse_files, validate
from backend.engine import recommend, required_level, complete
from backend.reporting import mandatory_training
from backend.insights import stagnation
from backend.main import create_app
from datetime import date

ROOT=Path(__file__).resolve().parents[1]
class OfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files={n:(ROOT/'examples/official'/n).read_text(encoding='utf-8-sig') for n in FILES}
        cls.data=parse_files(cls.files)
    def setUp(self):self.d=copy.deepcopy(self.data)
    def person(self):return next(p for p in self.d['employees'] if p['employee_id']=='E0028')
    def event(self,id):return next(e for e in self.d['events'] if e['id']==id)
    def recommendations(self,p=None,history=None):
        return recommend(p or self.person(),self.d['events'],self.d['history'] if history is None else history,self.d['skills'])
    def mutate_json(self,name,callback):
        files=dict(self.files);raw=json.loads(files[name]);callback(raw);files[name]=json.dumps(raw);return files
    def test_full_kit_counts(self):
        self.assertEqual([len(self.d[k]) for k in ['employees','events','skills','history']],[200,40,60,2743])
        self.assertEqual(self.d['as_of_date'],'2026-10-01')
    def test_reference_errors(self):
        files=self.mutate_json('employees.json',lambda d:d['employees'][0]['skills'].update({'UNKNOWN':1}))
        with self.assertRaises(DatasetError):parse_files(files)
    def test_duplicate_identifier(self):
        files=self.mutate_json('events.json',lambda d:d['events'].append(d['events'][0]))
        with self.assertRaises(DatasetError):parse_files(files)
    def test_mismatched_metadata(self):
        files=self.mutate_json('skills.json',lambda d:d['meta'].update(as_of_date='2026-10-02'))
        with self.assertRaises(DatasetError):parse_files(files)
    def test_bad_manager(self):
        files=self.mutate_json('employees.json',lambda d:d['employees'][0].update(manager_id='E9999'))
        with self.assertRaises(DatasetError):parse_files(files)
    def test_negative_csv_value(self):
        files=dict(self.files);rows=list(csv.DictReader(io.StringIO(files['activity_history.csv'])));rows[0]['completion_pct']='-1'
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);files['activity_history.csv']=buf.getvalue()
        with self.assertRaises(DatasetError):parse_files(files)
    def test_progress_replayed_exactly_once(self):
        self.assertEqual(self.person()['skills']['SK_SYSTEM_DESIGN'],3)
        self.assertEqual(validate(self.d),self.d)
        self.assertEqual(parse_files(self.files),self.d)
        raw_people=json.loads(self.files['employees.json'])['employees']
        raw_events={e['event_id']:e for e in json.loads(self.files['events.json'])['events']}
        rows=list(csv.DictReader(io.StringIO(self.files['activity_history.csv'])))
        for raw in raw_people:
            expected=dict(raw['skills'])
            for h in sorted(rows,key=lambda h:(h['date'],h['record_id'])):
                if h['employee_id']!=raw['employee_id'] or h['status']!='completed' or h['date']<=raw['last_review_date']:continue
                for g in raw_events[h['event_id']]['develops_skills']:
                    old=expected.get(g['skill_id'],0);expected[g['skill_id']]=max(old,min(old+g['gain'],g['max_level']))
            actual=next(p for p in self.d['employees'] if p['employee_id']==raw['employee_id'])
            self.assertEqual(actual['skills'],expected)
    def test_role_specific_requirements(self):
        s=self.d['skills']['SK_SYSTEM_DESIGN']
        self.assertEqual(required_level(s,{'role':'Backend Engineer','grade':'Middle'}),4)
        self.assertEqual(required_level(s,{'role':'HR Business Partner','grade':'Middle'}),0)
    def test_jury_case_no_minimum_skill_rule(self):
        p=self.person();p['skills']['SK_SYSTEM_DESIGN']=2;p['skills']['SK_PUBLIC_SPEAKING']=2
        self.d['events']=[self.event('EV_006'),self.event('EV_036')]
        history=[{'employee_id':'E0028','event_id':'EV_036','status':'no_show','date':day} for day in ['2026-07-01','2026-08-01','2026-09-01']]
        result=self.recommendations(p,history)
        self.assertEqual(result['recommendations'][0]['event']['id'],'EV_006')
        self.assertEqual(result['recommendations'][0]['factors'][0]['criticality'],3)
    def test_filter_prerequisites_grade_sessions_mandatory(self):
        p=self.person();event=copy.deepcopy(self.event('EV_006'));p['skills']['SK_SYSTEM_DESIGN']=2
        for patch in [{'mandatory':True},{'target_grades':['Lead']},{'prerequisites':{'SK_SYSTEM_DESIGN':5}},{'upcoming_sessions':[]}]:
            altered={**event,**patch}
            self.assertFalse(recommend(p,[altered],[],self.d['skills'])['recommendations'])
    def test_active_training_not_recommended_again(self):
        p=self.person();p['skills']['SK_SYSTEM_DESIGN']=2;e=self.event('EV_006')
        h=[{'employee_id':'E0028','event_id':e['id'],'status':'in_progress','date':'2026-09-30'}]
        self.assertFalse(recommend(p,[e],h,self.d['skills'])['recommendations'])
    def test_repeatable_event_after_prior_completion(self):
        p=self.person();p['skills']['SK_PUBLIC_SPEAKING']=0;e=self.event('EV_036')
        h=[{'employee_id':'E0028','event_id':e['id'],'status':'completed','date':'2026-09-01'}]
        self.assertTrue(recommend(p,[e],h,self.d['skills'])['recommendations'])
        self.assertTrue(complete(p,e,h));self.assertFalse(complete(p,e,h))
    def test_mandatory_uses_latest_assignment(self):
        p=self.person();self.d['history']=[{'employee_id':'E0028','event_id':'EV_001','status':'completed','date':'2025-01-01'}, {'employee_id':'E0028','event_id':'EV_001','status':'overdue','date':'2026-08-01','due_date':'2026-09-01'}]
        rows=mandatory_training(p,self.d)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'overdue')
    def test_manager_assignment_is_not_ai_recommendation(self):
        p=self.person();rows=[{'employee_id':'E0028','event_id':'EV_036','status':'no_show','assigned_by':'manager','date':d} for d in ['2026-07-01','2026-08-01','2026-09-01']]
        self.assertFalse(stagnation(p,rows,date(2026,10,1))['recommendation_tracking_available'])
    def test_api_import_profile_wallet_and_private_fields(self):
        class Offline:ready=False
        with tempfile.TemporaryDirectory() as directory:
            app=create_app(Path(directory)/'test.sqlite3','employee','hr',demo_mode=True,coach_gateway=Offline())
            c=TestClient(app);hr={'Authorization':'Bearer hr'};employee={'Authorization':'Bearer employee'}
            preview=c.post('/api/hr/import/preview',headers=hr,json={'files':self.files}).json()
            self.assertEqual(preview['counts']['employees'],200)
            self.assertEqual(preview['as_of_date'],'2026-10-01')
            self.assertEqual(c.post('/api/hr/import',headers=hr,json={'files':self.files,'expected_revision':preview['revision'],'digest':preview['digest']}).status_code,200)
            self.assertEqual(c.get('/api/me',headers=employee).json()['employee']['skills']['SK_SYSTEM_DESIGN'],3)
            self.assertEqual(c.get('/api/store',headers=employee).json()['balance'],0)
            people=c.get('/api/hr/employees',headers=hr).json()['employees']
            self.assertEqual(len(people),200)
            self.assertNotIn('feedback_rating',str(people));self.assertNotIn('career_goal',str(people))
            self.assertEqual(c.get('/api/hr/summary',headers=hr).json()['employee_count'],200)
            self.assertEqual(c.post('/api/coach',headers=employee,json={'message':'Why this step?','language':'en'}).status_code,200)
