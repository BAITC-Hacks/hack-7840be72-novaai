import json
import unittest
from pathlib import Path
from backend.dataset import FILES, DatasetError, parse_files
ROOT=Path(__file__).resolve().parents[1]
class DatasetTests(unittest.TestCase):
    def setUp(self): self.files={n:(ROOT/'data'/n).read_text(encoding='utf-8') for n in FILES}
    def test_valid_bom(self):
        self.files={k:'\ufeff'+v for k,v in self.files.items()}
        self.assertEqual(len(parse_files(self.files)['employees']),1)
    def test_missing_file(self):
        del self.files['skills.json']
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_skill_out_of_range(self):
        employees=json.loads(self.files['employees.json']);employees[0]['skills']['SK_PYTHON']=6
        self.files['employees.json']=json.dumps(employees)
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_unknown_reference(self):
        self.files['activity_history.csv']+='E0028,missing,completed,2026-01-01\n'
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_invalid_date(self):
        self.files['activity_history.csv']+='E0028,system-lab,completed,2026-02-30\n'
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_duplicate_identifier(self):
        people=json.loads(self.files['employees.json']);people.append(people[0]);self.files['employees.json']=json.dumps(people)
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_bad_csv_header(self):
        self.files['activity_history.csv']='employee,event,status,date\n'
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_duplicate_json_key(self):
        self.files['skills.json']='{"x":{},"x":{}}'
        with self.assertRaises(DatasetError):parse_files(self.files)
    def test_no_boolean_level(self):
        people=json.loads(self.files['employees.json']);people[0]['skills']['SK_PYTHON']=True;self.files['employees.json']=json.dumps(people)
        with self.assertRaises(DatasetError):parse_files(self.files)
