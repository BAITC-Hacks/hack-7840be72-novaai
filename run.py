"""Run the local demo without Docker. Only manages processes it starts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import ExitStack
from backend.config import load_env

ROOT = Path(__file__).resolve().parent

def free_port(start):
    for port in range(start, start + 100):
        with socket.socket() as sock:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                pass
    raise RuntimeError(f'No available local port in {start}..{start+99}')

def node_path():
    found = shutil.which('node')
    if found:
        return found
    candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'nodejs/node.exe'
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError('Node.js not found. Install Node.js and reopen the terminal.')

def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

def wait_ready(url, process, timeout=20):
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Server stopped during startup. See logs in .runtime.')
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.2)
    raise RuntimeError('Server startup timed out. See logs in .runtime.')

def configure_run(env, employee=None, database=None, dataset=None, offline=False):
    import re
    if employee:
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}',employee):
            raise ValueError('Invalid employee ID')
        env['EMPLOYEE_ID']=employee
    if database:
        env['CQ_DB_PATH']=str((ROOT / database).resolve())
    if dataset:
        if not database:
            raise ValueError('--dataset requires --database to protect the current demo')
        location=(ROOT / dataset).resolve()
        if not all((location/name).is_file() for name in ['employees.json','events.json','skills.json','activity_history.csv']):
            raise ValueError('Dataset folder must contain the four JSON/CSV files')
        env['CQ_INITIAL_DATA_DIR']=str(location)
    if offline:
        env['ALLOW_EXTERNAL_AI']='false'
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='Start, check the proxy, then stop both servers')
    parser.add_argument('--employee', help='Employee ID bound to the configured employee token')
    parser.add_argument('--database', help='Separate SQLite database path')
    parser.add_argument('--dataset', help='Initial dataset directory; requires --database. Existing databases are preserved.')
    parser.add_argument('--offline', action='store_true', help='Disable external AI for this run')
    args = parser.parse_args()
    env = dict(os.environ)
    load_env(environ=env)
    defaults = {'EMPLOYEE_TOKEN':'demo-employee','HR_TOKEN':'demo-hr','EMPLOYEE_ID':'E0028',
                'DEMO_MODE':'true','EMPLOYEE_ACCOUNTS_JSON':'{"demo-colleague":"E0029"}',
                'MANAGER_ACCOUNTS_JSON':'{"demo-manager":["E0028"]}','ALLOW_EXTERNAL_AI':'false'}
    for key, value in defaults.items():
        env.setdefault(key, value)
    configure_run(env,args.employee,args.database,args.dataset,args.offline)
    if args.dataset and Path(env['CQ_DB_PATH']).exists():
        print('Existing database preserved; use HR import to replace its dataset.',flush=True)
    python = ROOT / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
    vite = ROOT / 'frontend/node_modules/vite/bin/vite.js'
    if not python.is_file() or not vite.is_file():
        raise RuntimeError('Dependencies missing. Follow the Python/pnpm setup in README.md first.')
    node = node_path()
    backend_port, frontend_port = free_port(8000), free_port(5173)
    # Frontend build and preview do not need credentials or the provider key.
    frontend_env = {k:v for k,v in env.items() if k not in {
        'OPENAI_API_KEY','EMPLOYEE_TOKEN','HR_TOKEN','EMPLOYEE_ACCOUNTS_JSON','MANAGER_ACCOUNTS_JSON'}}
    frontend_env['CQ_API_TARGET'] = f'http://127.0.0.1:{backend_port}'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    subprocess.run([node,str(vite),'build','--configLoader','runner'],cwd=ROOT/'frontend',
                   env=frontend_env,check=True,creationflags=flags)
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    processes = []
    with ExitStack() as stack:
        try:
            for name, command, cwd, child_env in [
                ('backend', [str(python),'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',str(backend_port)],ROOT,env),
                ('frontend',[node,str(vite),'preview','--configLoader','runner','--host','127.0.0.1','--port',str(frontend_port),'--strictPort'],ROOT/'frontend',frontend_env)]:
                log = stack.enter_context((runtime/f'{name}-{os.getpid()}.log').open('w',encoding='utf-8'))
                processes.append(subprocess.Popen(command,cwd=cwd,env=child_env,stdout=log,stderr=subprocess.STDOUT,creationflags=flags))
            url = f'http://127.0.0.1:{frontend_port}'
            wait_ready(f'http://127.0.0.1:{backend_port}/api/health',processes[0])
            wait_ready(url+'/api/health',processes[1])
            wait_ready(url,processes[1])
            print(f'\nCareer Quest is ready: {url}\nKeep this window open. Ctrl+C stops this instance.\nLogs: {runtime}',flush=True)
            if args.smoke:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                responses={}
                for endpoint in ['me','recommendations']:
                    request=urllib.request.Request(url+'/api/'+endpoint,headers={'Authorization':'Bearer '+env['EMPLOYEE_TOKEN']})
                    with opener.open(request,timeout=10) as response:
                        responses[endpoint]=json.load(response)
                if responses['me']['employee']['employee_id']!=env['EMPLOYEE_ID']:
                    raise RuntimeError('Employee binding check failed')
                if responses['me']['revision']!=responses['recommendations']['revision']:
                    raise RuntimeError('Dataset changed during smoke check; retry')
                print('Smoke check passed: frontend, proxy, selected employee and recommendations.',flush=True)
                return
            while all(p.poll() is None for p in processes):
                time.sleep(.5)
            raise RuntimeError('A server stopped. See logs in .runtime.')
        finally:
            for process in reversed(processes):
                stop(process)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nCareer Quest stopped.')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Startup failed: {error}',file=sys.stderr)
        sys.exit(1)
