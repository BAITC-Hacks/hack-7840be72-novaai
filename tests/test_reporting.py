import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.reporting import mandatory_training
from backend.dataset import DatasetError, validate

class ReportingTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'db.sqlite3'
        self.app=create_app(self.path,'employee','hr',managers={'manager':['E0028'],'empty':[]},demo_mode=True)
        self.client=TestClient(self.app)
        self.manager={'Authorization':'Bearer manager'};self.hr={'Authorization':'Bearer hr'}
        with self.app.state.store.transaction() as tx:
            other=deepcopy(tx['data']['employees'][0]);other['employee_id']='E9999'
            tx['data']['employees'].append(other)
            event=deepcopy(tx['data']['events'][0]);event.update(id='required',mandatory=True,due_date='2020-01-01')
            tx['data']['events'].append(event)
            tx['data']['history'].append({'employee_id':'E9999','event_id':'required','status':'completed','date':'2020-01-01'})
            tx['changed']=True
    def test_manager_scope(self):
        result=self.client.get('/api/hr/employees',headers=self.manager).json()
        self.assertEqual([p['employee_id'] for p in result['employees']],['E0028'])
        summary=self.client.get('/api/hr/summary',headers=self.manager).json()
        self.assertEqual(summary['employee_count'],1)
        self.assertEqual(summary['participation']['completed'],0)
    def test_hr_sees_service_profiles_only(self):
        rows=self.client.get('/api/hr/employees',headers=self.hr).json()['employees']
        self.assertEqual(len(rows),2)
        for row in rows:self.assertEqual(set(row),{'employee_id','role','grade','recommendation_state','mandatory_training'})
    def test_direct_other_employee_denied(self):
        self.assertEqual(self.client.get('/api/hr/employees/E9999',headers=self.manager).status_code,404)
        self.assertEqual(self.client.get('/api/hr/employees/E0028',headers=self.manager).status_code,200)
    def test_employee_denied(self):
        self.assertEqual(self.client.get('/api/hr/employees',headers={'Authorization':'Bearer employee'}).status_code,403)
    def test_manager_cannot_import_or_read_personal_profile(self):
        self.assertEqual(self.client.post('/api/hr/import/preview',headers=self.manager,json={'files':{}}).status_code,403)
        self.assertEqual(self.client.get('/api/me',headers=self.manager).status_code,403)
    def test_empty_scope_no_fallback(self):
        self.assertEqual(self.client.get('/api/hr/employees',headers={'Authorization':'Bearer empty'}).json()['employees'],[])
    def test_mandatory_status(self):
        row=self.client.get('/api/hr/employees/E0028',headers=self.manager).json()
        self.assertEqual(row['mandatory_training'][0]['status'],'overdue')
        row=self.client.get('/api/hr/employees/E9999',headers=self.hr).json()
        self.assertEqual(row['mandatory_training'][0]['status'],'completed')
    def test_no_recommendation_reason(self):
        with self.app.state.store.transaction() as tx:
            tx['data']['events']=[];tx['changed']=True
        rows=self.client.get('/api/hr/employees',headers=self.manager).json()['employees']
        self.assertEqual(rows[0]['recommendation_state'],'catalog_gap')
        with self.app.state.store.transaction() as tx:
            tx['data']['employees'][0]['skills']={k:5 for k in tx['data']['skills']};tx['changed']=True
        rows=self.client.get('/api/hr/employees',headers=self.manager).json()['employees']
        self.assertEqual(rows[0]['recommendation_state'],'requirements_met')
    def test_invalid_deadline(self):
        data,_=self.app.state.store.read();data['events'][0]['due_date']='2026-02-30'
        with self.assertRaises(DatasetError):validate(data)
    def test_ambiguous_manager_token_rejected(self):
        with self.assertRaises(ValueError):create_app(self.path,'employee','hr',managers={'employee':['E0028']})
