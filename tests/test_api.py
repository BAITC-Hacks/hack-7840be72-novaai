import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.dataset import FILES
ROOT = Path(__file__).resolve().parents[1]

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)/'test.sqlite3'
        self.app = create_app(self.db, 'test-employee', 'test-hr', demo_mode=True)
        self.client = TestClient(self.app)
        self.employee = {'Authorization':'Bearer test-employee'}
        self.hr = {'Authorization':'Bearer test-hr'}
        self.files = {n:(ROOT/'data'/n).read_text(encoding='utf-8') for n in FILES}
    def test_health(self): self.assertEqual(self.client.get('/api/health').status_code,200)
    def test_unauthenticated(self): self.assertIn(self.client.get('/api/me').status_code,[401,403])
    def test_employee_cannot_read_hr(self):
        self.assertEqual(self.client.get('/api/hr/summary',headers=self.employee).status_code,403)
    def test_hr_cannot_read_profile(self):
        self.assertEqual(self.client.get('/api/me',headers=self.hr).status_code,403)
    def test_profile(self):
        self.assertEqual(self.client.get('/api/me',headers=self.employee).json()['employee']['employee_id'],'E0028')
    def test_summary_has_no_profiles(self):
        self.assertNotIn('employee_id',str(self.client.get('/api/hr/summary',headers=self.hr).json()))
    def test_invalid_token(self):
        self.assertEqual(self.client.get('/api/me',headers={'Authorization':'Bearer invalid'}).status_code,401)
    def test_employee_cannot_import(self):
        for path in ['import','import/preview']:
            self.assertEqual(self.client.post('/api/hr/'+path,headers=self.employee,json={'files':self.files}).status_code,403)
    def test_import_roundtrip_and_revision(self):
        preview=self.client.post('/api/hr/import/preview',headers=self.hr,json={'files':self.files}).json()
        self.assertEqual(preview['counts']['employees'],1)
        payload={'files':self.files,'digest':preview['digest'],'expected_revision':preview['revision']}
        self.assertEqual(self.client.post('/api/hr/import',headers=self.hr,json=payload).status_code,200)
        self.assertEqual(self.client.post('/api/hr/import',headers=self.hr,json=payload).status_code,409)
    def test_invalid_import_leaves_database_unchanged(self):
        before=self.app.state.store.read()
        self.files['employees.json']='['
        self.assertEqual(self.client.post('/api/hr/import',headers=self.hr,json={'files':self.files}).status_code,422)
        self.assertEqual(before,self.app.state.store.read())
    def test_preview_mismatch(self):
        preview=self.client.post('/api/hr/import/preview',headers=self.hr,json={'files':self.files}).json()
        people=json.loads(self.files['employees.json']); people[0]['tenure_months']=1
        self.files['employees.json']=json.dumps(people)
        response=self.client.post('/api/hr/import',headers=self.hr,json={'files':self.files,'digest':preview['digest'],'expected_revision':preview['revision']})
        self.assertEqual(response.status_code,409)
    def test_persistence_and_idempotency(self):
        path='/api/activities/system-lab/complete'
        response=self.client.post(path,headers=self.employee,json={'expected_revision':1})
        self.assertEqual(response.status_code,200)
        revision=response.json()['profile']['revision']
        self.assertFalse(self.client.post(path,headers=self.employee,json={'expected_revision':revision}).json()['changed'])
        other=TestClient(create_app(self.db,'test-employee','test-hr',demo_mode=True))
        self.assertEqual(other.get('/api/me',headers=self.employee).json()['employee']['skills']['SK_SYSTEM_DESIGN'],3)
    def test_stale_completion(self):
        self.assertEqual(self.client.post('/api/activities/system-lab/complete',headers=self.employee,json={'expected_revision':99}).status_code,409)
    def test_account_never_follows_first_profile(self):
        with self.app.state.store.transaction() as tx:
            original=tx['data']['employees'][0]
            tx['data']['employees'].insert(0,{**original,'employee_id':'OTHER'})
            tx['changed']=True
        self.test_profile()
    def test_missing_profile_fails_closed(self):
        with self.app.state.store.transaction() as tx:
            tx['data']['employees'][0]['employee_id']='OTHER';tx['changed']=True
        self.assertEqual(self.client.get('/api/me',headers=self.employee).status_code,404)
