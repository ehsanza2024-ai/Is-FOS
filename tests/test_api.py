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

def test_provenance_distinguishes_prewrite_backup(client,tmp_path,monkeypatch):
    from app.store import Store
    c,m=client;login(c)
    store=Store(tmp_path/'provenance',demo=True);monkeypatch.setattr(m,'store',store)
    before=fingerprint(store.path)
    r=c.post('/api/events',json={'data':{'kind':'دریافت','date':'14050813','party':'خریدار نمونه','bank':'بانک آموزشی','amount':'1000','reference':'PROVENANCE-1'},'revision':before},headers={'X-Mazandasht-Request':'1'})
    assert r.status_code==200
    source=c.get('/api/provenance').json()
    assert source['events']==1 and source['backup']['events']==0
    assert source['backup']['sha256']==before
    assert source['backup']['new_event_ids']==[r.json()['id']]
    assert not source['backup']['same_bytes'] and source['backup']['changed_events']==[]
    assert source['source'].endswith('Mazandasht.xlsx')
    m.security.add('provenanceviewer','Provenance-viewer-password','viewer')
    login(c,'provenanceviewer','Provenance-viewer-password')
    assert c.get('/api/provenance').status_code==403

def test_installed_entry_and_remote_read_only_integration(client):
    import asyncio
    import httpx
    from app.entry_boundary import LocalOnly
    from app.dashboard import create_app
    c,m=client
    boundary=LocalOnly(m.app,'integration-private-window-secret')
    async def case():
        transport=httpx.ASGITransport(app=boundary,client=('127.0.0.1',2000))
        async with httpx.AsyncClient(transport=transport,base_url='http://central') as installed:
            assert (await installed.post('/api/login',json={'name':'admin','password':'Test-only-password-2026'})).status_code==403
            assert (await installed.get('/desktop/start?key=integration-private-window-secret')).status_code==303
            assert (await installed.post('/api/login',json={'name':'admin','password':'Test-only-password-2026'})).status_code==200
            for sheet,name in [('Parties','Central integration party'),('Banks','Central integration bank')]:
                revision=(await installed.get('/api/state')).json()['revision']
                assert (await installed.post('/api/references/'+sheet,json={'data':{'name':name},'revision':revision},headers={'X-Mazandasht-Request':'1'})).status_code==200
            revision=(await installed.get('/api/state')).json()['revision']
            result=await installed.post('/api/events',json={'revision':revision,'data':{'kind':'سرمایه','date':'14050813','party':'Central integration party','bank':'Central integration bank','amount':'1000','reference':'INSTALLED-CAP-1'}},headers={'X-Mazandasht-Request':'1'})
            assert result.status_code==200
        async with httpx.AsyncClient(transport=transport,base_url='http://central') as ordinary:
            assert (await ordinary.get('/api/state')).status_code==403
        dashboard=create_app(m.store.root,demo=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=dashboard,client=('192.168.1.30',4000)),base_url='http://reports') as remote:
            assert (await remote.post('/api/login',json={'name':'admin','password':'Test-only-password-2026'},headers={'X-Mazandasht-Request':'1'})).status_code==200
            report=(await remote.get('/api/reports')).json()
            assert report['banks']==[{'name':'Central integration bank','balance':'1000'}]
            assert (await remote.post('/api/events',json={},headers={'X-Mazandasht-Request':'1'})).status_code==403
            assert (await remote.get('/api/export')).status_code==404
    asyncio.run(case())
