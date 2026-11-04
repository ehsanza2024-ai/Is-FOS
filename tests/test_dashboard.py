import hashlib
import os
from pathlib import Path
import shutil
import pytest
from fastapi.testclient import TestClient
from app.store import Store,fingerprint
from app.security import Security
from app.domain import RuleError
from app.dashboard import create_app

HEADERS={'X-Mazandasht-Request':'1'}

@pytest.fixture(scope='module')
def dashboard(tmp_path_factory):
    root=tmp_path_factory.mktemp('reports')
    store=Store(root)
    os.environ['MAZANDASHT_PASSWORD']='Dashboard-admin-test-password'
    security=Security(root);security.add('viewer','Dashboard-viewer-test-password','viewer')
    app=create_app(root,demo=False)
    with TestClient(app) as client:yield client,app,root

def auth(client,name='admin'):
    client.cookies.clear()
    password='Dashboard-admin-test-password' if name=='admin' else 'Dashboard-viewer-test-password'
    return client.post('/api/login',json={'name':name,'password':password},headers=HEADERS)

def test_dashboard_requires_auth_and_has_separate_cookie(dashboard):
    c,app,root=dashboard;c.cookies.clear()
    assert c.get('/api/reports').status_code==401
    assert c.get('/api/catalog').status_code==401
    r=auth(c);assert r.status_code==200
    assert 'maz_dashboard_session=' in r.headers['set-cookie']
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    assert c.get('/api/catalog').json()['user']['role']=='viewer'
    assert c.get('/api/reports').json()['profit_loss']['net_profit']=='0'
    assert c.get('/api/reports').headers['cache-control']=='no-store'

@pytest.mark.parametrize('name',['admin','viewer'])
def test_even_admin_cannot_write_or_export(dashboard,name):
    c,app,root=dashboard;auth(c,name)
    before=fingerprint(root/'Mazandasht.xlsx');auth_before=fingerprint(root/'auth.sqlite3');backups=list((root/'backups').iterdir())
    for path in ['/api/events','/api/events/id/reverse','/api/references/Parties','/api/weigh','/api/checks','/api/checks/id/state','/api/import/preview','/api/import/id/commit','/api/backup','/api/restore','/api/users']:
        r=c.post(path,json={},headers=HEADERS);assert r.status_code==403,path
    for method in ['put','patch','delete']:
        assert getattr(c,method)('/api/reports',headers=HEADERS).status_code==403
    for path in ['/api/export','/api/backups','/api/state','/api/provenance','/openapi.json','/static/app.js','/Mazandasht.xlsx']:
        assert c.get(path).status_code==404,path
    assert fingerprint(root/'Mazandasht.xlsx')==before and fingerprint(root/'auth.sqlite3')==auth_before
    assert list((root/'backups').iterdir())==backups

def test_dashboard_csrf_bad_filter_logout(dashboard):
    c,app,root=dashboard;auth(c)
    assert c.post('/api/login',json={},headers={**HEADERS,'Origin':'https://attacker.invalid'}).status_code==403
    assert c.post('/api/logout',json={}).status_code==403
    assert c.get('/api/reports?start=14050814&end=14050813').status_code==422
    assert c.post('/api/logout',json={},headers=HEADERS).status_code==200
    assert c.get('/api/reports').status_code==401

def test_dashboard_uses_live_xlsx_without_snapshot_cache(dashboard):
    c,app,root=dashboard;auth(c)
    before=c.get('/api/reports').json()['revision']
    store=Store(root);store.add_ref('Parties',{'name':'new real-time party'},'test',before)
    assert c.get('/api/reports').json()['revision']!=before
    assert 'new real-time party' in c.get('/api/catalog').json()['parties']

def test_read_only_store_has_no_bootstrap_or_mutation(tmp_path):
    missing=tmp_path/'missing'
    with pytest.raises(FileNotFoundError):Store(missing,read_only=True)
    assert not missing.exists()
    with pytest.raises(FileNotFoundError):Security(missing,existing_only=True)
    assert not missing.exists()
    store=Store(tmp_path/'existing');readonly=Store(store.root,read_only=True)
    before=fingerprint(store.path)
    with pytest.raises(RuleError):readonly.backup()
    with pytest.raises(RuleError):readonly.restore('none','test',before)
    with pytest.raises(RuleError):readonly.add_ref('Products',{'name':'forbidden'},'test',before)
    assert before==fingerprint(store.path)

def test_demo_flag_cannot_disable_auth_on_real_workbook(dashboard):
    c,app,root=dashboard
    with pytest.raises(RuntimeError,match='واقعی'):create_app(root,demo=True)

def test_dashboard_html_assets(dashboard):
    c,app,root=dashboard
    html=c.get('/').text
    assert 'reports.js' in html and 'src="/static/app.js"' not in html
    for asset in ['reports.js','style.css','dashboard.css','print.css']:
        assert c.get('/static/'+asset).status_code==200

def test_bad_login_payload_fails_without_financial_changes(dashboard):
    c,app,root=dashboard;before=fingerprint(root/'Mazandasht.xlsx')
    assert c.post('/api/login',content='not json',headers=HEADERS).status_code==400
    assert c.post('/api/login',json=[],headers=HEADERS).status_code==400
    assert c.post('/api/login',json={'password':'a'*5000},headers=HEADERS).status_code==413
    assert fingerprint(root/'Mazandasht.xlsx')==before

def test_running_demo_does_not_expose_replaced_real_workbook(tmp_path):
    demo=Store(tmp_path/'demo',demo=True);real=Store(tmp_path/'real')
    app=create_app(demo.root,demo=True)
    with TestClient(app) as c:
        assert c.get('/api/reports').status_code==200
        shutil.copy2(real.path,demo.path)
        assert c.get('/api/reports').status_code==409
        assert c.get('/api/catalog').status_code==409
