import importlib
import pytest
from fastapi.testclient import TestClient
from app.store import fingerprint

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import os
    root=tmp_path_factory.mktemp('api')
    os.environ['MAZANDASHT_DATA']=str(root);os.environ['MAZANDASHT_DEMO']='0';os.environ['MAZANDASHT_PASSWORD']='Test-only-password-2026'
    import app.main as module
    module=importlib.reload(module)
    with TestClient(module.app) as c:yield c,module

def login(c,name='admin',password='Test-only-password-2026'):
    return c.post('/api/login',json={'name':name,'password':password},headers={'X-Mazandasht-Request':'1'})

def test_authentication_required(client):
    c,m=client;c.cookies.clear();assert c.get('/api/state').status_code==401
    assert login(c).status_code==200;assert c.get('/api/state').status_code==200

def test_csrf_cross_origin(client):
    c,m=client;login(c)
    assert c.post('/api/backup',headers={'Origin':'https://attacker.example','X-Mazandasht-Request':'1'}).status_code==403
    assert c.post('/api/backup').status_code==403

def test_viewer_cannot_post(client):
    c,m=client;login(c)
    assert c.post('/api/users',json={'name':'viewer','password':'Test-viewer-password','role':'viewer'},headers={'X-Mazandasht-Request':'1'}).status_code==200
    login(c,'viewer','Test-viewer-password')
    assert c.get('/api/state').status_code==200
    assert c.post('/api/events',json={'data':{},'revision':'x'},headers={'X-Mazandasht-Request':'1'}).status_code==403
    assert c.get('/api/backups').status_code==403

def test_static_shell_and_headers(client):
    c,m=client;r=c.get('/');assert r.status_code==200
    assert 'script-src' in r.headers['content-security-policy']
    assert c.get('/static/app.js').status_code==200
