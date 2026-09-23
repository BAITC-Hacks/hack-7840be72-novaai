import socket
import tempfile
import unittest
from pathlib import Path
from backend.config import load_env
from run import free_port, stop
from unittest.mock import Mock

class ConfigTests(unittest.TestCase):
    def read(self,text,env=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';path.write_text(text,encoding='utf-8-sig')
            result={} if env is None else env
            load_env(path,result)
            return result
    def test_literal_values_and_quotes(self):
        result=self.read('# comment\nOPENAI_API_KEY="fake-secret"\nX=\'${NOT_EXPANDED}\'\nJSON={"one":"two"}\nEMPTY=\n')
        self.assertEqual(result,{'OPENAI_API_KEY':'fake-secret','X':'${NOT_EXPANDED}','JSON':'{"one":"two"}','EMPTY':''})
    def test_environment_wins(self):
        self.assertEqual(self.read('X=file',{'X':'environment'}),{'X':'environment'})
    def test_bad_line_no_partial_loading_or_secret(self):
        env={}
        with self.assertRaises(ValueError) as caught:
            self.read('GOOD=value\nFAKE-SECRET\n',env)
        self.assertEqual(env,{})
        self.assertNotIn('FAKE-SECRET',str(caught.exception))
    def test_unclosed_quote(self):
        with self.assertRaises(ValueError):self.read('KEY="fake-secret')
    def test_missing_file(self):
        env={};load_env(Path(tempfile.gettempdir())/'cq-nonexistent-config-test'/'.env',env)
        self.assertEqual(env,{})
    def test_port_skips_listener(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));sock.listen()
            occupied=sock.getsockname()[1]
            self.assertNotEqual(free_port(occupied),occupied)
    def test_stop_only_owned_live_process(self):
        process=Mock();process.poll.return_value=None
        stop(process);process.terminate.assert_called_once();process.wait.assert_called_once()
        exited=Mock();exited.poll.return_value=0
        stop(exited);exited.terminate.assert_not_called()


class JudgeLauncherTests(unittest.TestCase):
    def test_dataset_requires_separate_database(self):
        from run import configure_run
        with self.assertRaises(ValueError):configure_run({},dataset='data')
    def test_employee_binding_and_offline(self):
        from run import configure_run
        env=configure_run({'ALLOW_EXTERNAL_AI':'true'},employee='E0030',database='.runtime/jury.sqlite3',dataset='data',offline=True)
        self.assertEqual(env['EMPLOYEE_ID'],'E0030')
        self.assertEqual(env['ALLOW_EXTERNAL_AI'],'false')
        self.assertTrue(Path(env['CQ_INITIAL_DATA_DIR']).is_dir())
    def test_invalid_employee(self):
        from run import configure_run
        with self.assertRaises(ValueError):configure_run({},employee='bad id')
