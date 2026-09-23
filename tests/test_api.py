import os
os.environ['EMPLOYEE_TOKEN']='test-employee'
os.environ['HR_TOKEN']='test-hr'
import unittest
from fastapi.testclient import TestClient
from backend.main import app

class AccessTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_health(self): self.assertEqual(self.client.get('/api/health').status_code,200)
    def test_unauthenticated(self): self.assertIn(self.client.get('/api/me').status_code,[401,403])
    def test_employee_cannot_read_hr(self):
        self.assertEqual(self.client.get('/api/hr/summary',headers={'Authorization':'Bearer test-employee'}).status_code,403)
    def test_hr_cannot_read_profile(self):
        self.assertEqual(self.client.get('/api/me',headers={'Authorization':'Bearer test-hr'}).status_code,403)
    def test_profile(self):
        self.assertEqual(self.client.get('/api/me',headers={'Authorization':'Bearer test-employee'}).json()['employee']['employee_id'],'E0028')
    def test_summary_has_no_profiles(self):
        payload=self.client.get('/api/hr/summary',headers={'Authorization':'Bearer test-hr'}).json()
        self.assertNotIn('employee_id',str(payload))
    def test_invalid_token(self):
        self.assertEqual(self.client.get('/api/me',headers={'Authorization':'Bearer invalid'}).status_code,401)
