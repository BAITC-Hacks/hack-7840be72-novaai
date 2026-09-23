import unittest
import tempfile
import json
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient
from backend.insights import stagnation,six_months_before
from backend.main import create_app
from backend.dataset import FILES,parse_files
class InsightTests(unittest.TestCase):
    person={'employee_id':'E','tenure_months':12}
    def row(self,day,status='completed',recommended=False):
        return {'employee_id':'E','event_id':'event','status':status,'date':day,'recommended':recommended}
    def test_calendar_boundary(self):
        self.assertEqual(six_months_before(date(2026,8,31)),date(2026,2,28))
        self.assertFalse(stagnation(self.person,[self.row('2026-03-23')],date(2026,9,23))['flagged'])
        self.assertTrue(stagnation(self.person,[self.row('2026-03-22')],date(2026,9,23))['flagged'])
    def test_no_history_unknown(self):
        value=stagnation(self.person,[],date(2026,9,23))
        self.assertFalse(value['flagged']);self.assertTrue(value['insufficient_history'])
    def test_legacy_skips_not_recommendations(self):
        rows=[self.row('2026-09-0'+str(i),'skipped') for i in [1,2,3]]
        self.assertFalse(stagnation(self.person,rows,date(2026,9,23))['flagged'])
    def test_marked_skips_and_break(self):
        rows=[self.row('2026-09-0'+str(i),'skipped',True) for i in [1,2,3]]
        self.assertIn('three_recommendations_skipped',stagnation(self.person,rows,date(2026,9,23))['reasons'])
        rows.append(self.row('2026-09-04','completed',True))
        self.assertFalse(stagnation(self.person,rows,date(2026,9,23))['flagged'])
    def test_future_records_ignored(self):
        self.assertFalse(stagnation(self.person,[self.row('2027-01-01','skipped',True)]*3,date(2026,9,23))['flagged'])
    def test_old_history_no_completions(self):
        self.assertTrue(stagnation(self.person,[self.row('2026-01-01','declined')],date(2026,9,23))['flagged'])
    def test_optional_csv_column(self):
        root=Path(__file__).resolve().parents[1]
        files={n:(root/'data'/n).read_text(encoding='utf-8') for n in FILES}
        files['activity_history.csv']='employee_id,event_id,status,date,recommended\nE0028,system-lab,skipped,2026-09-01,true\n'
        self.assertTrue(parse_files(files)['history'][0]['recommended'])
    def test_proposal_is_scoped_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            app=create_app(Path(d)/'test.db','employee','hr',managers={'manager':[]})
            client=TestClient(app);before=app.state.store.read()
            path='/api/hr/employees/E0028/support-proposal'
            self.assertEqual(client.post(path,headers={'Authorization':'Bearer employee'}).status_code,403)
            self.assertEqual(client.post(path,headers={'Authorization':'Bearer manager'}).status_code,404)
            response=client.post(path,headers={'Authorization':'Bearer hr'})
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.json()['sent'])
            self.assertEqual(response.json()['mentor_request']['status'],'directory_required')
            self.assertEqual(before,app.state.store.read())
