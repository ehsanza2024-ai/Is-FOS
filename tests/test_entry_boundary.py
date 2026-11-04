import asyncio
import hashlib
import httpx
import pytest
from fastapi import FastAPI
from app.entry_boundary import LocalOnly

@pytest.fixture
def boundary():
    core=FastAPI()
    @core.get('/')
    def index():return {'screen':'central'}
    @core.post('/api/events')
    def entry():return {'written':True}
    return LocalOnly(core,'test-single-use-bootstrap-secret')

def run(test):asyncio.run(test())

def test_remote_admin_cannot_bypass_with_proxy_headers(boundary):
    async def case():
        transport=httpx.ASGITransport(app=boundary,client=('192.168.1.22',2222))
        async with httpx.AsyncClient(transport=transport,base_url='http://central') as c:
            for path in ['/','/api/health','/desktop/start?key=test-single-use-bootstrap-secret']:
                assert (await c.get(path,headers={'X-Forwarded-For':'127.0.0.1'})).status_code==403
            assert (await c.post('/api/events',headers={'X-Forwarded-For':'127.0.0.1','X-Mazandasht-Request':'1','Cookie':'maz_session=admin; maz_desktop=forged'})).status_code==403
    run(case)

def test_ordinary_browser_on_central_cannot_enter_data(boundary):
    async def case():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=boundary,client=('127.0.0.1',2222)),base_url='http://central') as c:
            assert (await c.get('/')).status_code==403
            assert (await c.post('/api/events')).status_code==403
            health=await c.get('/api/health');assert health.status_code==200
            assert health.json()['instance']==hashlib.sha256(b'test-single-use-bootstrap-secret').hexdigest()
            assert (await c.get('/desktop/start?key=wrong')).status_code==403
    run(case)

def test_installed_window_single_use_session_and_expiry(boundary):
    async def case():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=boundary,client=('127.0.0.1',2222)),base_url='http://central') as c:
            r=await c.get('/desktop/start?key=test-single-use-bootstrap-secret')
            assert r.status_code==303 and r.headers['location']=='/'
            assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
            assert (await c.get('/')).status_code==200
            assert (await c.post('/api/events')).json()['written'] is True
            assert (await c.get('/desktop/start?key=test-single-use-bootstrap-secret')).status_code==403
            boundary.expires=0
            assert (await c.post('/api/events')).status_code==403
    run(case)

def test_missing_launcher_secret_fails_closed():
    async def case():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=LocalOnly(FastAPI()),client=('127.0.0.1',1)),base_url='http://central') as c:
            assert (await c.get('/desktop/start?key=')).status_code==403
    run(case)
