import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.rewards import reward_amount
from backend.dataset import FILES

ROOT=Path(__file__).resolve().parents[1]
class RewardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'db.sqlite3'
        self.app=create_app(self.path,'employee','hr',demo_mode=True,accounts={'other':'OTHER'},managers={'manager':['E0028']})
        self.client=TestClient(self.app)
        self.headers={'Authorization':'Bearer employee'}
    def wallet(self):return self.client.get('/api/store',headers=self.headers).json()
    def finish(self):
        revision=self.app.state.store.read()[1]
        return self.client.post('/api/activities/system-lab/complete',headers=self.headers,json={'expected_revision':revision})
    def order(self,item='book',key=None,epoch=None):
        return self.client.post('/api/store/redeem',headers=self.headers,json={'item_id':item,'request_id':key or str(uuid4()),'expected_epoch':epoch or self.wallet()['epoch']})
    def test_initial_wallet_and_catalog(self):
        wallet=self.wallet();self.assertEqual(wallet['balance'],0)
        self.assertEqual({i['category'] for i in wallet['catalog']},{'work','self','family'})
        self.assertEqual(wallet['history'],[])
    def test_completion_once_and_persistence(self):
        self.assertEqual(self.finish().json()['coins_earned'],100)
        self.assertEqual(self.finish().json()['coins_earned'],0)
        self.assertEqual(self.wallet()['balance'],100)
        restarted=TestClient(create_app(self.path,'employee','hr',demo_mode=True))
        self.assertEqual(restarted.get('/api/store',headers=self.headers).json()['balance'],100)
    def test_mandatory_no_coins(self):
        with self.app.state.store.transaction() as tx:
            next(e for e in tx['data']['events'] if e['id']=='system-lab')['mandatory']=True;tx['changed']=True
        self.assertTrue(self.finish().json()['changed']);self.assertEqual(self.wallet()['balance'],0)
    def test_capped_and_irrelevant_gains(self):
        data,_=self.app.state.store.read();p=data['employees'][0];e=next(e for e in data['events'] if e['id']=='system-lab')
        p['skills']['SK_SYSTEM_DESIGN']=4
        self.assertEqual(reward_amount(p,e,data['skills']),0)
        p['skills']['SK_SYSTEM_DESIGN']=2;e['skill_gains']['SK_SYSTEM_DESIGN']['max_level']=2
        self.assertEqual(reward_amount(p,e,data['skills']),0)
    def test_insufficient_and_unknown(self):
        self.assertEqual(self.order().status_code,409)
        self.assertEqual(self.order('made-up').status_code,404)
        self.assertEqual(self.wallet()['balance'],0)
    def test_redeem_idempotency(self):
        self.finish();key=str(uuid4());first=self.order(key=key);self.assertEqual(first.status_code,200)
        self.assertFalse(first.json()['replayed']);self.assertTrue(self.order(key=key).json()['replayed'])
        self.assertEqual(self.wallet()['balance'],0);self.assertEqual(len(self.wallet()['history']),2)
        self.assertEqual(self.order('merch',key=key).status_code,409)
    def test_concurrent_double_spend(self):
        self.finish()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.order().status_code,range(2)))
        self.assertEqual(sorted(results),[200,409]);self.assertEqual(self.wallet()['balance'],0)
    def test_concurrent_same_request(self):
        self.finish();key=str(uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.order(key=key).status_code,range(2)))
        self.assertEqual(results,[200,200]);self.assertEqual(len(self.wallet()['history']),2)
    def test_rbac_and_isolation(self):
        self.finish()
        for token in ['hr','manager']:
            self.assertEqual(self.client.get('/api/store',headers={'Authorization':'Bearer '+token}).status_code,403)
        self.assertIn(self.client.get('/api/store').status_code,[401,403])
        with self.app.state.store.transaction() as tx:
            tx['data']['employees'].append({**tx['data']['employees'][0],'employee_id':'OTHER'});tx['changed']=True
        other=self.client.get('/api/store',headers={'Authorization':'Bearer other'}).json()
        self.assertEqual(other['balance'],0);self.assertEqual(other['history'],[])
    def test_disabled_outside_demo(self):
        c=TestClient(create_app(self.path,'employee','hr',demo_mode=False))
        self.assertFalse(c.get('/api/store',headers=self.headers).json()['redemption_enabled'])
        self.assertEqual(c.post('/api/store/redeem',headers=self.headers,json={'item_id':'book','request_id':str(uuid4()),'expected_epoch':1}).status_code,403)
    def test_import_resets_and_rejects_old_request(self):
        self.finish();old=self.wallet()['epoch']
        files={n:(ROOT/'data'/n).read_text(encoding='utf-8') for n in FILES};hr={'Authorization':'Bearer hr'}
        preview=self.client.post('/api/hr/import/preview',headers=hr,json={'files':files}).json()
        self.assertEqual(self.client.post('/api/hr/import',headers=hr,json={'files':files,'digest':preview['digest'],'expected_revision':preview['revision']}).status_code,200)
        self.assertEqual(self.wallet()['balance'],0);self.assertEqual(self.wallet()['history'],[])
        self.assertEqual(self.order(epoch=old).status_code,409)
    def test_cannot_forge_price_or_owner(self):
        payload={'item_id':'book','request_id':str(uuid4()),'expected_epoch':1,'cost':0,'owner':'OTHER'}
        self.assertEqual(self.client.post('/api/store/redeem',headers=self.headers,json=payload).status_code,422)
    def test_wallet_absent_profile(self):
        self.assertEqual(self.client.get('/api/store',headers={'Authorization':'Bearer other'}).status_code,404)
