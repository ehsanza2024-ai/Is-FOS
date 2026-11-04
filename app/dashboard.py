"""Separate read-only HTTP surface. No business mutation or workbook export routes.
Run with: uvicorn app.dashboard:create_app --factory ...
"""
from pathlib import Path
from urllib.parse import urlparse
import os
import json
import jdatetime
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import FileResponse,JSONResponse,HTMLResponse
from filelock import Timeout
from app.store import Store,Conflict
from app.security import Security
from app.domain import RuleError
from app.reports import build_report,exact_json

BASE=Path(__file__).resolve().parents[1]

def create_app(root=None,demo=None):
    demo=(os.environ.get('MAZANDASHT_DEMO')=='1') if demo is None else demo
    root=Path(root or os.environ.get('MAZANDASHT_DATA',BASE/'runtime'/('demo' if demo else 'local')))
    store=Store(root,read_only=True)
    synthetic=any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in store.read()['Info'])
    if demo and not synthetic:raise RuntimeError('حالت نمایشی روی دفتر واقعی مجاز نیست')
    security=Security(root,demo,cookie_name='maz_dashboard_session',existing_only=True)
    app=FastAPI(title='مازندشت | داشبورد فقط‌خواندنی',version='0.8.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store;app.state.security=security

    def read_data():
        data=store.read()
        if demo and not any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in data['Info']):
            raise HTTPException(409,'فایل نمایشی با دفتر غیرنمونه جایگزین شده؛ دسترسی بدون ورود متوقف شد')
        return data

    @app.middleware('http')
    async def boundary(request,call_next):
        path=request.url.path
        if request.method not in ['GET','HEAD']:
            if request.method!='POST' or path not in ['/api/login','/api/logout']:
                return JSONResponse({'detail':'داشبورد فقط‌خواندنی است؛ ثبت فقط در نرم‌افزار سیستم مرکزی مجاز است'},status_code=403)
            origin=request.headers.get('origin')
            if origin and urlparse(origin).netloc!=request.headers.get('host'):
                return JSONResponse({'detail':'مبدأ درخواست مجاز نیست'},status_code=403)
            if request.headers.get('x-mazandasht-request')!='1':
                return JSONResponse({'detail':'نشان درخواست لازم است'},status_code=403)
            try:large=int(request.headers.get('content-length','0'))>4096
            except ValueError:large=True
            if large:return JSONResponse({'detail':'درخواست بیش از حد بزرگ است'},status_code=413)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https://api.open-meteo.com; font-src 'self' data:; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(RuleError)
    async def error(request,exc):return JSONResponse({'detail':str(exc)},status_code=409 if isinstance(exc,Conflict) else 422)
    @app.exception_handler(Timeout)
    async def locked(request,exc):return JSONResponse({'detail':'دفتر مرکزی مشغول است؛ دوباره تلاش کنید'},status_code=409)

    @app.get('/')
    def index():return FileResponse(BASE/'static/dashboard.html')
    # Explicit asset allowlist: never publish the central-entry client or repository.
    @app.get('/static/{name}')
    def asset(name:str):
        if name not in ['currency.js','reports.js','portable.js','style.css','dashboard.css','print.css']:raise HTTPException(404)
        return FileResponse(BASE/'static'/name)
    @app.get('/viewer')
    def portable():return HTMLResponse((BASE/'static/dashboard.html').read_text().replace('<body>','<body data-mode="portable">'))
    @app.get('/static/fonts/{name}')
    def font(name:str):
        if name not in ['vazirmatn-arabic-400-normal.woff2','vazirmatn-arabic-700-normal.woff2']:raise HTTPException(404)
        return FileResponse(BASE/'static/fonts'/name,media_type='font/woff2')
    @app.get('/api/health')
    def health():return {'ok':True,'version':'0.8.0','mode':'read_only_dashboard','demo':synthetic,'today':jdatetime.date.today().strftime('%Y/%m/%d')}
    @app.post('/api/login')
    async def login(request:Request):
        if demo:raise HTTPException(400,'پیش‌نمایش ساختگی به ورود نیاز ندارد؛ صفحه را تازه کنید')
        content=b''
        async for chunk in request.stream():
            content+=chunk
            if len(content)>4096:raise HTTPException(413,'درخواست بیش از حد بزرگ است')
        try:b=json.loads(content)
        except (ValueError,UnicodeDecodeError):raise HTTPException(400,'بدنه درخواست معتبر نیست')
        if not isinstance(b,dict):raise HTTPException(400,'بدنه درخواست معتبر نیست')
        token,user=security.login(str(b.get('name','')),str(b.get('password','')),request.client.host)
        response=JSONResponse({'name':user['name'],'role':'viewer','read_only':True})
        response.set_cookie(security.cookie_name,token,httponly=True,samesite='strict',secure=request.url.scheme=='https' or os.environ.get('MAZANDASHT_HTTPS_ONLY')=='1',max_age=8*3600)
        return response
    @app.post('/api/logout')
    def logout(request:Request):
        security.sessions.pop(request.cookies.get(security.cookie_name,''),None)
        response=JSONResponse({'ok':True});response.delete_cookie(security.cookie_name);return response
    @app.get('/api/catalog')
    def catalog(request:Request):
        user=security.require(request);data=read_data()
        return {'user':{'name':user['name'],'role':'viewer'},'read_only':True,'demo':synthetic,'parties':[p['name'] for p in data['Parties']],'source':'Mazandasht.xlsx','revision':data['revision']}
    @app.get('/api/reports')
    def reports(request:Request,start:str|None=None,end:str|None=None,party:str|None=None):
        security.require(request)
        return exact_json(build_report(read_data(),start,end,party))
    return app
