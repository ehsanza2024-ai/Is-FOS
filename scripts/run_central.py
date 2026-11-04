"""Own the central API, read-only dashboard, and private native WebView window.
No browser fallback: ordinary browsers, even on the central PC, cannot enter data.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
from urllib.request import urlopen

BASE=Path(__file__).resolve().parents[1]

def available(host,port):
    try:
        with socket.socket() as s:s.bind((host,port))
    except OSError:raise SystemExit(f'Port {port} is already occupied. Close the prior application; no process was killed.')

def ready(process,url,expected,timeout=45,context=None):
    limit=time.monotonic()+timeout
    while time.monotonic()<limit:
        if process.poll() is not None:raise RuntimeError('A service exited during startup; inspect the local log.')
        try:
            with urlopen(url,timeout=1,context=context) as r:body=json.load(r)
            if all(body.get(k)==v for k,v in expected.items()):return
        except (OSError,ValueError):pass
        time.sleep(.2)
    raise RuntimeError('Service startup timed out. Inspect logs; another service may occupy the port.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(os.environ.get('MAZANDASHT_DATA',BASE/'runtime/local')));p.add_argument('--central-port',type=int,default=8000);p.add_argument('--dashboard-port',type=int,default=8001);p.add_argument('--dashboard-host',default=os.environ.get('MAZANDASHT_DASHBOARD_HOST','0.0.0.0'));p.add_argument('--tls-cert',type=Path);p.add_argument('--tls-key',type=Path);a=p.parse_args()
    if a.central_port==a.dashboard_port:p.error('Central and dashboard ports must differ')
    if bool(a.tls_cert)!=bool(a.tls_key):p.error('Both TLS certificate and key are required')
    if a.tls_cert and (not a.tls_cert.is_file() or not a.tls_key.is_file()):p.error('TLS certificate/key not found')
    root=a.data.resolve()
    if not (root/'Mazandasht.xlsx').is_file() or not (root/'auth.sqlite3').is_file():
        raise SystemExit('First run install.bat / install.sh (or scripts.setup_central). No empty/demo ledger was silently created.')
    from app.store import Store
    if any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in Store(root,read_only=True).read()['Info']):
        raise SystemExit('Installed entry refuses a synthetic demo ledger. Choose the real central data directory.')
    try:import webview
    except ImportError:raise SystemExit('Desktop dependencies missing: install requirements-desktop.txt; see INSTALL_CENTRAL_FA.md.')
    available('127.0.0.1',a.central_port);available(a.dashboard_host,a.dashboard_port)
    logs=root/'logs';logs.mkdir(exist_ok=True)
    token=secrets.token_urlsafe(48)
    env=os.environ.copy();env.pop('MAZANDASHT_DEMO',None);env.pop('MAZANDASHT_PASSWORD',None)
    env['MAZANDASHT_DATA']=str(root);env['MAZANDASHT_DESKTOP_TOKEN']=token
    children=[]
    try:
        with (logs/'services.log').open('a',encoding='utf-8') as log:
            common=[sys.executable,'-m','uvicorn','--workers','1','--no-proxy-headers','--no-access-log']
            central=subprocess.Popen(common+['app.central:app','--host','127.0.0.1','--port',str(a.central_port)],cwd=BASE,env=env,stdout=log,stderr=log);children.append(central)
            dashboard_env=env.copy();dashboard_env.pop('MAZANDASHT_DESKTOP_TOKEN',None)
            # With a local HTTPS reverse proxy, set MAZANDASHT_HTTPS_ONLY=1 explicitly.
            tls=['--ssl-certfile',str(a.tls_cert.resolve()),'--ssl-keyfile',str(a.tls_key.resolve())] if a.tls_cert else []
            dashboard=subprocess.Popen(common+['app.dashboard:create_app','--factory','--host',a.dashboard_host,'--port',str(a.dashboard_port)]+tls,cwd=BASE,env=dashboard_env,stdout=log,stderr=log);children.append(dashboard)
            ready(central,f'http://127.0.0.1:{a.central_port}/api/health',{'instance':hashlib.sha256(token.encode()).hexdigest()})
            if not a.tls_cert:ready(dashboard,f'http://127.0.0.1:{a.dashboard_port}/api/health',{'mode':'read_only_dashboard','demo':False})
            else:
                # Loopback readiness only: no credentials, no financial data, no remote TLS downgrade.
                ready(dashboard,f'https://127.0.0.1:{a.dashboard_port}/api/health',{'mode':'read_only_dashboard','demo':False},context=ssl._create_unverified_context())
            print(f'Read-only dashboard: port {a.dashboard_port}. Use central-PC LAN/VPN address, never mobile localhost.')
            print('Do not expose central port or this installation folder. Closing this window stops both services.')
            webview.create_window('مازندشت | نرم‌افزار مرکزی',f'http://127.0.0.1:{a.central_port}/desktop/start?key={token}',fullscreen=True,confirm_close=True)
            webview.start(private_mode=True)
    except Exception as e:
        print(str(e)+'\nLog: '+str(logs/'services.log'),file=sys.stderr)
        raise SystemExit(1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:child.kill();child.wait()
if __name__=='__main__':main()
