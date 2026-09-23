import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import create_app

class SharingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.sqlite3'
        self.app=create_app(self.path,'owner-token','hr-token',accounts={'recipient-token':'E0029','stranger-token':'E0030'},demo_mode=True)
        self.client=TestClient(self.app)
        self.owner={'Authorization':'Bearer owner-token'}
        self.recipient={'Authorization':'Bearer recipient-token'}
        self.stranger={'Authorization':'Bearer stranger-token'}
        self.hr={'Authorization':'Bearer hr-token'}
        self.payload={'alias':'Architect','style':'anime','achievement_ids':[],'recipients':['E0029'],'expected_revision':1}
    def create(self):
        response=self.client.post('/api/sharing',headers=self.owner,json=self.payload)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['id']
    def test_private_by_default(self):
        self.assertEqual(self.client.get('/api/sharing',headers=self.owner).json(),{'shares':[]})
    def test_preview_does_not_publish(self):
        self.assertEqual(self.client.post('/api/sharing/preview',headers=self.owner,json=self.payload).status_code,200)
        self.test_private_by_default()
    def test_acl_and_minimal_projection(self):
        identifier=self.create()
        path='/api/shared/'+identifier
        response=self.client.get(path,headers=self.recipient)
        self.assertEqual(response.status_code,200)
        self.assertEqual(set(response.json()),{'alias','style','achievements','demo'})
        self.assertEqual(self.client.get(path,headers=self.stranger).status_code,404)
        self.assertEqual(self.client.get(path,headers=self.hr).status_code,403)
        self.assertIn(self.client.get(path).status_code,[401,403])
    def test_revoke_and_nonowner_cannot_revoke(self):
        identifier=self.create()
        self.client.delete('/api/sharing/'+identifier,headers=self.stranger)
        self.assertEqual(self.client.get('/api/shared/'+identifier,headers=self.recipient).status_code,200)
        self.client.delete('/api/sharing/'+identifier,headers=self.owner)
        self.assertEqual(self.client.get('/api/shared/'+identifier,headers=self.recipient).status_code,404)
    def test_unearned_achievement_rejected(self):
        self.payload['achievement_ids']=['system-lab']
        self.assertEqual(self.client.post('/api/sharing',headers=self.owner,json=self.payload).status_code,422)
    def test_mandatory_completion_never_shared(self):
        with self.app.state.store.transaction() as tx:
            tx['data']['events'][0]['mandatory']=True
            tx['data']['history'].append({'employee_id':'E0028','event_id':'system-lab','status':'completed','date':'2026-09-23'})
            tx['changed']=True
        self.payload.update(achievement_ids=['system-lab'],expected_revision=2)
        self.assertEqual(self.client.post('/api/sharing',headers=self.owner,json=self.payload).status_code,422)
    def test_selected_achievement_and_no_automatic_updates(self):
        self.client.post('/api/activities/system-lab/complete',headers=self.owner,json={'expected_revision':1})
        self.payload.update(achievement_ids=['system-lab'],expected_revision=2)
        identifier=self.create()
        self.client.post('/api/activities/python-lab/complete',headers=self.owner,json={'expected_revision':2})
        result=self.client.get('/api/shared/'+identifier,headers=self.recipient).json()
        self.assertEqual(len(result['achievements']),1)
    def test_persists_across_restart(self):
        identifier=self.create()
        other=TestClient(create_app(self.path,'owner-token','hr-token',accounts={'recipient-token':'E0029'}))
        self.assertEqual(other.get('/api/shared/'+identifier,headers=self.recipient).status_code,200)
    def test_import_revokes_existing_cards(self):
        from backend.dataset import FILES
        root=Path(__file__).resolve().parents[1]
        files={n:(root/'data'/n).read_text(encoding='utf-8') for n in FILES}
        identifier=self.create()
        preview=self.client.post('/api/hr/import/preview',headers=self.hr,json={'files':files}).json()
        response=self.client.post('/api/hr/import',headers=self.hr,json={'files':files,'digest':preview['digest'],'expected_revision':preview['revision']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/shared/'+identifier,headers=self.recipient).status_code,404)
    def test_recipient_cannot_read_owner_profile(self):
        self.assertEqual(self.client.get('/api/me',headers=self.recipient).status_code,404)
    def test_unknown_recipient(self):
        self.payload['recipients']=['unknown']
        self.assertEqual(self.client.post('/api/sharing',headers=self.owner,json=self.payload).status_code,422)
    def test_production_self_completion_disabled(self):
        other=TestClient(create_app(self.path,'owner-token','hr-token',demo_mode=False))
        self.assertEqual(other.post('/api/activities/system-lab/complete',headers=self.owner,json={'expected_revision':1}).status_code,403)
