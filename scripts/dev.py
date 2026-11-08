"""Cross-platform project-local setup and supervised development startup.

Standard library only. This bootstrap intentionally parses on Python 3.8+ so it
can locate an installed compatible interpreter; the project itself requires 3.12+.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fuzzy_network_risk.config_integrity import frozen_text_matches
MIN_PYTHON=(3,12)
BACKEND_PORT=8000
FRONTEND_PORT=5173
PYTHON_ADVICE='Install Python 3.12+ (3.14 recommended for the pinned stack) from https://www.python.org/downloads/. No Python runtime will be downloaded automatically.'
NODE_ADVICE='Install native Node.js 24.15+ LTS (or 22.22.2+) with its bundled npm from https://nodejs.org/. No system software is installed automatically.'
HELP='''Fuzzy Network Risk: project-local development commands
  make / make run  prepare missing dependencies; run FastAPI + Vite
  make setup       prepare web-app Python (requirements-web.txt) and npm dependencies
  make backend     prepare Python; run only FastAPI on 127.0.0.1:8000
  make frontend    prepare npm; run only Vite on 127.0.0.1:5173
  make test        prepare contributor dependencies (requirements-dev.txt); run all tests
  make build       prepare dependencies; typecheck and build frontend
  make check       report readiness without installing or writing markers
  make help        show this help
Ctrl+C stops owned services and descendants. Occupied ports are never reused.
Without Make: python scripts/dev.py <command> (python3 on macOS).
No dataset download, Git LFS operation, training or reconstruction is performed.
'''


class LaunchError(RuntimeError): pass


def windows(): return sys.platform=='win32'


def version_tuple(text):
    match=re.search(r'(\d+)\.(\d+)\.(\d+)',text)
    if not match: raise LaunchError('Cannot parse version: '+text)
    return tuple(map(int,match.groups()))


def node_compatible(version):
    # Intersection of the locked Vite/Vitest/jsdom engine constraints.
    return (version[0]==22 and version>=(22,22,2)) or (version[0]==24 and version>=(24,15,0)) or version[0]>=26


def environment(root=ROOT):
    if root.name=='web': root=root.parent
    env=os.environ.copy()
    for key in ['PYTHONHOME','PYTHONPATH','NODE_ENV']: env.pop(key,None)
    env.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1',PYTHONNOUSERSITE='1',
        PYTHON_MANAGER_AUTOMATIC_INSTALL='false',PYLAUNCHER_ALLOW_INSTALL='',
        PIP_CACHE_DIR=str(root/'.cache/pip'),NPM_CONFIG_CACHE=str(root/'.cache/npm'),
        MPLCONFIGDIR=str(root/'.cache/matplotlib'),TEMP=str(root/'.tmp'),TMP=str(root/'.tmp'))
    return env


def capture(args,root=ROOT,timeout=30):
    try:
        p=subprocess.run(list(map(str,args)),cwd=root,env=environment(root),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc: raise LaunchError('Cannot execute '+str(args[0])+': '+str(exc)) from exc
    if p.returncode: raise LaunchError('Command failed: '+str(args[0])+'\n'+(p.stderr or p.stdout).strip())
    return p.stdout.strip()


def python_info(executable,root=ROOT):
    code='import sys,json,platform; print(json.dumps({"version":list(sys.version_info[:3]),"prefix":sys.prefix,"base_prefix":sys.base_prefix,"executable":sys.executable,"machine":platform.machine()}))'
    return json.loads(capture([executable,'-I','-c',code],root))


def choose_python(root=ROOT):
    candidates=[sys.executable]
    if windows() and shutil.which('py'):
        try:
            listing=capture(['py','-0p'],root)
            candidates.extend(m.group(1).strip() for line in listing.splitlines() if (m:=re.search(r'([A-Za-z]:\\.*python(?:\d+(?:\.\d+)?)?\.exe)\s*$',line,re.I)))
        except LaunchError: pass
    for name in ['python3.14','python3.13','python3.12','python3','python']:
        found=shutil.which(name)
        if found: candidates.append(found)
    for candidate in dict.fromkeys(candidates):
        try:
            info=python_info(candidate,root)
            if tuple(info['version'][:2])>=MIN_PYTHON: return Path(info['executable']),info
        except (LaunchError,ValueError): continue
    raise LaunchError(PYTHON_ADVICE)


def venv_python(root=ROOT,is_windows=None):
    return root/'.venv'/('Scripts/python.exe' if (windows() if is_windows is None else is_windows) else 'bin/python')


def valid_venv(root=ROOT):
    directory=root/'.venv'; executable=venv_python(root)
    if not directory.exists(): return None
    if directory.is_symlink() or getattr(directory,'is_junction',lambda:False)() or not (directory/'pyvenv.cfg').is_file() or not executable.is_file():
        raise LaunchError('Existing .venv is invalid or external. Repair/move it yourself; it will not be overwritten.')
    try: info=python_info(executable,root)
    except (LaunchError,ValueError) as exc: raise LaunchError('Existing .venv cannot run. Repair/move it yourself; it will not be replaced.') from exc
    if Path(info['prefix']).resolve()!=directory.resolve() or info['prefix']==info['base_prefix'] or tuple(info['version'][:2])<MIN_PYTHON:
        raise LaunchError('Existing .venv belongs to another location or incompatible Python. It will not be replaced.')
    return executable,info


# Installation profiles: the web application, or the full contributor set used by `test`.
PROFILES={'web':'requirements-web.txt','dev':'requirements-dev.txt'}


def requirements(root=ROOT,declaration='requirements-web.txt'):
    visited=set(); pins={}; digest=hashlib.sha256()
    def read(path):
        path=path.resolve()
        try: relative=path.relative_to(root.resolve())
        except ValueError: raise LaunchError('Requirement include escapes the repository')
        if path in visited: return
        visited.add(path)
        if not path.is_file(): raise LaunchError('Missing dependency declaration: '+str(relative))
        content=path.read_bytes(); digest.update(str(relative).encode()); digest.update(content)
        for raw in content.decode('utf-8-sig').splitlines():
            line=raw.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('-r '): read(path.parent/line[3:].strip()); continue
            match=re.fullmatch(r'([\w.-]+)==([^\s;]+)',line)
            if not match: raise LaunchError('Unsupported dependency declaration: '+line)
            name=re.sub(r'[-_.]+','-',match[1]).lower()
            if pins.get(name,match[2])!=match[2]: raise LaunchError(f'Conflicting pins for {name}: {pins[name]} and {match[2]}')
            pins[name]=match[2]
    read(root/declaration)
    if not (root/'pyproject.toml').is_file(): raise LaunchError('Missing pyproject.toml; restore the tracked project metadata.')
    digest.update((root/'pyproject.toml').read_bytes())
    return pins,digest.hexdigest()


def read_state(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): return {}


def write_state(path,state):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.new'); temporary.write_text(json.dumps(state,sort_keys=True),encoding='utf-8')
    os.replace(temporary,path)


class Lease:
    """OS lock released even on abrupt exit; no PID guessing/stale PID killing."""
    def __init__(self,path): self.path=path; self.handle=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('a+b')
        try:
            if windows():
                import msvcrt
                self.handle.seek(0); self.handle.write(b'0'); self.handle.flush(); self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close(); self.handle=None
            raise LaunchError('Another launcher is using this repository ('+self.path.stem+'). Stop it first; no process was killed.') from exc
        return self
    def __exit__(self,*args):
        if self.handle is not None:
            if windows():
                import msvcrt
                self.handle.seek(0); msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            self.handle.close(); self.handle=None


def run_command(args,root=ROOT):
    print('+ '+subprocess.list2cmdline(list(map(str,args))),flush=True)
    # Installation/test/build helpers get the same ownership guarantees as the
    # web servers, including compiler/native-tool descendants.
    child=Child('command',args,root)
    try:
        while child.process.poll() is None: time.sleep(.1)
        code=child.process.returncode
    finally: child.close()
    if code: raise LaunchError('Command exited '+str(code)+'. Check the output above; no dependency state was recorded.')


def python_health(executable,pins,root=ROOT):
    code='''import importlib.metadata as m,json,re,sys
installed={re.sub(r"[-_.]+","-",d.metadata["Name"]).lower():d.version for d in m.distributions()}
pins=json.loads(sys.argv[1]); mismatch={k:v for k,v in pins.items() if installed.get(k)!=v}
try:
 import fastapi,uvicorn,numpy,pandas
except Exception as e:
 print(json.dumps({"ok":False,"detail":str(e),"mismatch":mismatch}));sys.exit(0)
print(json.dumps({"ok":not mismatch,"mismatch":mismatch}))'''
    try: return json.loads(capture([executable,'-I','-c',code,json.dumps(pins)],root))
    except (LaunchError,ValueError): return {'ok':False}


def ensure_python(root=ROOT,profile='web'):
    declaration=PROFILES[profile]
    pins,digest=requirements(root,declaration)
    valid=valid_venv(root)
    if valid is None:
        base,_=choose_python(root); print('Creating repository-local .venv',flush=True)
        run_command([base,'-m','venv',root/'.venv'],root); valid=valid_venv(root)
    executable,info=valid
    signature={'requirements':digest,'python':info,'platform':sys.platform}
    # Separate markers: switching between `run` and `test` must not force reinstalls.
    marker=root/'.tmp/launcher'/('python.json' if profile=='web' else f'python-{profile}.json'); previous=read_state(marker)
    health=python_health(executable,pins,root)
    if not health['ok'] or (previous and previous!=signature):
        # Existing historical environments may have been created --without-pip.
        try: capture([executable,'-m','pip','--version'],root)
        except LaunchError: run_command([executable,'-m','ensurepip','--upgrade'],root)
        print('Synchronizing pinned Python dependencies inside .venv',flush=True)
        command=[executable,'-m','pip','install']
        if health.get('detail') and not health.get('mismatch'): command.append('--force-reinstall')
        run_command(command+['-r',root/declaration],root)
        if not python_health(executable,pins,root)['ok']: raise LaunchError('Python dependency verification failed after installation')
    else: print('Python dependencies verified; no installation needed.',flush=True)
    write_state(marker,signature)
    return executable


def node_tools(root=ROOT):
    node=shutil.which('node'); npm=shutil.which('npm.cmd' if windows() else 'npm')
    if not node or not npm: raise LaunchError('Node.js/npm not found. '+NODE_ADVICE)
    info=json.loads(capture([node,'-p','JSON.stringify({version:process.versions.node,arch:process.arch,platform:process.platform})'],root))
    if not node_compatible(version_tuple(info['version'])): raise LaunchError('Incompatible Node '+info['version']+'. '+NODE_ADVICE)
    resolved=Path(npm).resolve()
    options=[resolved,resolved.parent/'node_modules/npm/bin/npm-cli.js',Path(node).resolve().parent/'node_modules/npm/bin/npm-cli.js']
    cli=next((p for p in options if p.suffix=='.js' and p.is_file()),None)
    if cli is None: raise LaunchError('npm-cli.js is missing; repair the Node/npm installation. '+NODE_ADVICE)
    command=[str(node),str(cli)] # no .cmd shell quoting, works with spaces/Unicode
    version=capture(command+['--version'],root)
    if version_tuple(version)[0]<10: raise LaunchError('npm 10+ required; use the npm bundled with supported Node.js.')
    return str(node),command,info,version


def frontend_health(root,lock,node):
    web=root/'web'; modules=web/'node_modules'
    if not modules.is_dir() or not (modules/'.package-lock.json').is_file(): return False
    for relative,spec in lock.get('packages',{}).items():
        if not relative: continue
        if not relative.startswith('node_modules/') or '..' in Path(relative).parts: raise LaunchError('Unexpected lockfile package path')
        actual=read_state(web/relative/'package.json')
        if not actual and spec.get('optional'): continue
        if actual.get('version')!=spec.get('version'): return False
    for name in ['vite','vitest','tsc']:
        if not (modules/'.bin'/(name+'.cmd' if windows() else name)).is_file(): return False
    try:
        capture([node,'--input-type=module','-e',"await Promise.all(['vite','react','react-dom','jsdom'].map(x=>import(x)))"],web)
        return True
    except LaunchError: return False


def ensure_frontend(root=ROOT):
    node,npm,info,npm_version=node_tools(root); web=root/'web'
    modules=web/'node_modules'
    if modules.is_symlink() or getattr(modules,'is_junction',lambda:False)():
        raise LaunchError('node_modules is a linked/external installation. Repair it yourself; npm ci will not overwrite it.')
    lock_path=web/'package-lock.json'
    if not (web/'package.json').is_file(): raise LaunchError('Missing web/package.json; restore the tracked frontend manifest.')
    if not lock_path.is_file(): raise LaunchError('Missing web/package-lock.json. Restore it from the project; startup will not generate or upgrade it.')
    lock=read_state(lock_path)
    if lock.get('lockfileVersion')!=3 or not lock.get('packages'): raise LaunchError('Invalid npm lockfile; restore the tracked lockfile.')
    digest=hashlib.sha256((web/'package.json').read_bytes()+lock_path.read_bytes()).hexdigest()
    state={'declarations':digest,'node':info,'npm':npm_version}
    marker=root/'.tmp/launcher/frontend.json'; previous=read_state(marker)
    if not frontend_health(root,lock,node) or (previous and previous!=state):
        print('Installing locked frontend dependencies (npm ci)',flush=True)
        run_command(npm+['ci','--include=dev','--no-audit','--no-fund'],web)
        if not frontend_health(root,lock,node): raise LaunchError('Frontend installation verification failed. Check native package/platform compatibility.')
    else: print('Frontend dependencies verified; no installation needed.',flush=True)
    if digest!=hashlib.sha256((web/'package.json').read_bytes()+lock_path.read_bytes()).hexdigest(): raise LaunchError('Dependency lock/declarations changed unexpectedly; no marker saved.')
    write_state(marker,state)
    return node,npm


def model_assets(root=ROOT):
    files=['config/fuzzy/task04/selected_manifest.json','config/fuzzy/task04/selected_v4.json','config/fuzzy/task04/selected_policies.json',
        'web/catalog/examples.json','reports/dataset/provenance.json','reports/dataset/classes.csv',
        'reports/fuzzy/metrics.json','reports/fuzzy/task02b/comparison_summary.csv','reports/fuzzy/task04/comparison.csv']
    missing=[p for p in files if not (root/p).is_file()]
    if missing: raise LaunchError('Required frozen model/display files missing: '+', '.join(missing)+'. Restore tracked project files; no dataset reconstruction or model training is needed.')
    try: manifest=json.loads((root/files[0]).read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc: raise LaunchError('Invalid selected model manifest') from exc
    if not {'model_id','configuration_version','model_sha256','policy_sha256'}.issubset(manifest):
        raise LaunchError('Selected model manifest lacks required version/hash fields; restore the tracked manifest.')
    for name,key in [('selected_v4.json','model_sha256'),('selected_policies.json','policy_sha256')]:
        if not frozen_text_matches((root/'config/fuzzy/task04'/name).read_bytes(),manifest.get(key)):
            raise LaunchError('Frozen model content hash mismatch: '+name)
    return manifest


def port_available(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        if windows(): sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try: sock.bind(('127.0.0.1',port)); return True
        except OSError: return False


class WindowsJob:
    """Owned process trees only; closing the job kills any surviving descendants."""
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_=[('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),('minimum',c.c_size_t),('maximum',c.c_size_t),('active',w.DWORD),('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(c.Structure): _fields_=[(n,c.c_ulonglong) for n in ['read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes']]
        class Extended(c.Structure): _fields_=[('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
        self.c=c; self.api=c.WinDLL('kernel32',use_last_error=True)
        self.api.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR]; self.api.CreateJobObjectW.restype=w.HANDLE
        self.api.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]; self.api.SetInformationJobObject.restype=w.BOOL
        self.api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]; self.api.AssignProcessToJobObject.restype=w.BOOL
        self.api.CloseHandle.argtypes=[w.HANDLE]; self.api.CloseHandle.restype=w.BOOL
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle: raise c.WinError(c.get_last_error())
        limits=Extended(); limits.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle,9,c.byref(limits),c.sizeof(limits)):
            error=c.get_last_error(); self.close(); raise c.WinError(error)
    def assign(self,process):
        if not self.api.AssignProcessToJobObject(self.handle,int(process._handle)): raise self.c.WinError(self.c.get_last_error())
    def close(self):
        if self.handle: self.api.CloseHandle(self.handle); self.handle=None


class Child:
    def __init__(self,name,args,root=ROOT):
        self.name=name; self.job=WindowsJob() if windows() else None; self.process=None
        try:
            kwargs={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if windows() else {'start_new_session':True}
            self.process=subprocess.Popen(list(map(str,args)),cwd=root,env=environment(root),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',**kwargs)
            if self.job: self.job.assign(self.process)
        except BaseException:
            if self.process and self.process.poll() is None: self.process.terminate(); self.process.wait(timeout=5)
            if self.job: self.job.close()
            raise
        self.reader=threading.Thread(target=self._output,daemon=True); self.reader.start()
    def _output(self):
        for line in self.process.stdout:
            try: print('['+self.name+'] '+line.rstrip(),flush=True)
            except (OSError,ValueError): return
    def check(self):
        code=self.process.poll()
        if code is not None: raise LaunchError(self.name+' exited unexpectedly ('+str(code)+'). See its output above.')
    def close(self):
        try:
            if windows():
                if self.process.poll() is None:
                    try: self.process.send_signal(signal.CTRL_BREAK_EVENT)
                    except OSError: pass # non-console hosts: Job Object still owns cleanup
            else:
                try: os.killpg(self.process.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            try: self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                if not windows():
                    try: os.killpg(self.process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
        finally:
            if self.job: self.job.close()
            else:
                # Parent exit does not prove its descendants exited. A session
                # group can outlive its root (e.g. native bundler helper).
                try: os.killpg(self.process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
            self.process.wait(timeout=5); self.reader.join(timeout=2); self.process.stdout.close()


def http_json(url):
    # Ignore unrelated global proxy settings for loopback health probes.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url,timeout=.7) as response: return json.load(response)


def wait_ready(children,port,manifest=None,timeout=45):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        for child in children: child.check()
        try:
            if manifest:
                health=http_json('http://127.0.0.1:'+str(port)+'/api/health')
                if health.get('model_id')!=manifest['model_id'] or health.get('configuration_version')!=manifest['configuration_version']:
                    raise LaunchError('Port '+str(port)+' serves a different model/application. No existing process will be killed.')
                return
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://127.0.0.1:'+str(port)+'/',timeout=.7) as response:
                if response.status==200: return
        except (OSError,urllib.error.URLError,ValueError): pass
        time.sleep(.15)
    raise LaunchError('Timed out waiting for port '+str(port)+'. Owned children will be stopped; inspect startup output.')


def serve(action,python=None,node=None,root=ROOT,smoke_seconds=None):
    manifest=model_assets(root); selected=['backend','frontend'] if action=='run' else [action]
    ports={'backend':BACKEND_PORT,'frontend':FRONTEND_PORT}
    for name in selected:
        if not port_available(ports[name]): raise LaunchError('Port '+str(ports[name])+' is occupied ('+name+'). Stop that service yourself. No duplicate was started.')
    children=[]
    old_break=None
    def interrupt(*_): raise KeyboardInterrupt()
    if windows(): old_break=signal.signal(signal.SIGBREAK,interrupt)
    try:
        if 'backend' in selected:
            children.append(Child('backend',[python,'-m','uvicorn','fuzzy_network_risk.webapp.api:app','--app-dir',root/'src','--host','127.0.0.1','--port',str(BACKEND_PORT)],root))
            wait_ready(children,BACKEND_PORT,manifest)
        if 'frontend' in selected:
            children.append(Child('frontend',[node,root/'web/node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(FRONTEND_PORT),'--strictPort'],root/'web'))
            wait_ready(children,FRONTEND_PORT)
        print('READY '+('UI http://127.0.0.1:5173 | ' if 'frontend' in selected else '')+('API http://127.0.0.1:8000 | docs /docs' if 'backend' in selected else 'API requires make backend in another terminal'),flush=True)
        start=time.monotonic()
        while True:
            for child in children: child.check()
            if smoke_seconds is not None and time.monotonic()-start>=smoke_seconds: raise KeyboardInterrupt()
            time.sleep(.2)
    except KeyboardInterrupt: print('\nStopping owned services...',flush=True)
    finally:
        # Repeated Ctrl+C must not interrupt ownership cleanup midway.
        previous=signal.signal(signal.SIGINT,signal.SIG_IGN)
        if windows(): signal.signal(signal.SIGBREAK,signal.SIG_IGN)
        try:
            for child in reversed(children): child.close()
        finally:
            signal.signal(signal.SIGINT,previous)
            if windows(): signal.signal(signal.SIGBREAK,old_break)
        print('Owned services stopped.',flush=True)


def check(root=ROOT,via_make=False):
    errors=[]
    for name,fn in [('Python',lambda:choose_python(root)[1]),('Node/npm',lambda:node_tools(root)[2:]),('Model assets',lambda:model_assets(root)['model_id']),('Existing .venv',lambda:valid_venv(root))]:
        try: print(name+': '+str(fn()),flush=True)
        except LaunchError as exc: errors.append(str(exc)); print(name+': '+str(exc),flush=True)
    make=shutil.which('make') or shutil.which('gmake')
    print('GNU Make: '+(make or ('invoked by Make' if via_make else 'missing; see docs/launcher.md')),flush=True)
    if not make and not via_make: errors.append('GNU Make is an external prerequisite; see docs/launcher.md. Python CLI fallback is available.')
    try:
        existing=valid_venv(root)
        if not existing or not python_health(existing[0],requirements(root)[0],root)['ok']: errors.append('Python dependencies need make setup.')
        tools=node_tools(root)
        if not frontend_health(root,read_state(root/'web/package-lock.json'),tools[0]): errors.append('Frontend dependencies need make setup.')
    except LaunchError as exc: errors.append(str(exc))
    for port in [BACKEND_PORT,FRONTEND_PORT]:
        available=port_available(port)
        print('Port '+str(port)+': '+('available' if available else 'occupied (no process changed)'),flush=True)
        if not available: errors.append('Port '+str(port)+' is occupied.')
    for error in errors: print('Not ready: '+error,flush=True)
    print('Dataset/LFS: not read or required. This command installs nothing.',flush=True)
    return 1 if errors else 0


def main(argv=None,root=ROOT):
    parser=argparse.ArgumentParser(description=HELP,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action',nargs='?',default='run',choices=['run','setup','backend','frontend','test','build','check','help'])
    parser.add_argument('--via-make',action='store_true'); parser.add_argument('--smoke-seconds',type=float,help='Maintainer smoke test: stop through the interrupt cleanup path after readiness')
    args=parser.parse_args(argv)
    if args.action=='help': print(HELP); return 0
    if args.action=='check': return check(root,args.via_make)
    base,info=choose_python(root)
    if tuple(sys.version_info[:2])<MIN_PYTHON:
        return subprocess.call([str(base),str(Path(__file__).resolve()),*(sys.argv[1:] if argv is None else argv)],env=environment(root))
    selected=['backend'] if args.action=='backend' else ['frontend'] if args.action=='frontend' else ['backend','frontend']
    if args.action in ['run','backend','frontend']:
        for name,port in [('backend',BACKEND_PORT),('frontend',FRONTEND_PORT)]:
            if name in selected and not port_available(port): raise LaunchError('Port '+str(port)+' is occupied. Stop the existing service; no installation/server startup was attempted.')
    model_assets(root)
    root.joinpath('.tmp').mkdir(exist_ok=True)
    with ExitStack() as stack:
        for name in selected: stack.enter_context(Lease(root/'.tmp/launcher'/(name+'.lock')))
        with Lease(root/'.tmp/launcher/setup.lock'):
            python=ensure_python(root,'dev' if args.action=='test' else 'web') if args.action!='frontend' else None
            node=npm=None
            if args.action!='backend': node,npm=ensure_frontend(root)
        if args.action=='setup': print('Project dependencies ready.',flush=True); return 0
        if args.action=='test':
            # Python tool subprocesses inherit this environment, never user temp.
            run_command([python,'-m','pytest','-q','-p','no:cacheprovider','--basetemp',root/'.tmp/launcher/pytest'],root)
            run_command(npm+['test'],root/'web'); return 0
        if args.action=='build': run_command(npm+['run','build'],root/'web'); return 0
        serve(args.action,python,node,root,args.smoke_seconds)
    return 0


if __name__=='__main__':
    try: sys.exit(main())
    except LaunchError as exc: print('ERROR: '+str(exc),file=sys.stderr); sys.exit(1)
    except KeyboardInterrupt: print('\nSetup interrupted; no success marker was saved for an incomplete installation.',file=sys.stderr); sys.exit(130)
    except OSError as exc: print('ERROR: Startup/setup OS operation failed: '+str(exc)+'. Check checkout permissions and runtime installation.',file=sys.stderr); sys.exit(1)
