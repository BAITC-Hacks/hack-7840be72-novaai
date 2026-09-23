import csv
import json
import unittest
from copy import deepcopy
from pathlib import Path
from backend.engine import recommend, complete
ROOT = Path(__file__).resolve().parents[1]

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.employee = json.loads((ROOT/'data/employees.json').read_text(encoding='utf-8'))[0]
        self.events = json.loads((ROOT/'data/events.json').read_text(encoding='utf-8'))
        self.skills = json.loads((ROOT/'data/skills.json').read_text(encoding='utf-8'))
        with (ROOT/'data/activity_history.csv').open(encoding='utf-8') as f:
            self.history = list(csv.DictReader(f))
    def ranked(self):
        return recommend(self.employee,self.events,self.history,self.skills)['recommendations']
    def test_jury_case(self):
        rows=self.ranked()
        self.assertEqual(rows[0]['event']['id'],'system-lab')
        speaking=next(x for x in rows if x['event']['id']=='speaking-club')
        self.assertEqual(speaking['factors'][0]['history_count'],3)
        self.assertLess(speaking['factors'][0]['acceptance'],rows[0]['factors'][0]['acceptance'])
    def test_completion_idempotent(self):
        self.assertTrue(complete(self.employee,self.events[0],self.history))
        self.assertFalse(complete(self.employee,self.events[0],self.history))
        self.assertEqual(self.employee['skills']['SK_SYSTEM_DESIGN'],3)
        self.assertNotIn('system-lab',[r['event']['id'] for r in self.ranked()])
    def test_cap_never_reduces_skill(self):
        self.employee['skills']['SK_SYSTEM_DESIGN']=5
        complete(self.employee,self.events[0],self.history)
        self.assertEqual(self.employee['skills']['SK_SYSTEM_DESIGN'],5)
    def test_no_history(self):
        self.history=[]
        self.assertEqual(self.ranked()[0]['factors'][0]['acceptance'],0.5)
    def test_no_events(self):
        self.events=[]
        self.assertEqual(self.ranked(),[])
    def test_audience(self):
        self.employee['role']='Designer'
        self.assertEqual(self.ranked(),[])
        with self.assertRaises(ValueError): complete(self.employee,self.events[0],self.history)
    def test_no_gap(self):
        self.employee['skills']={k:5 for k in self.skills}
        self.assertEqual(self.ranked(),[])

if __name__=='__main__': unittest.main()
