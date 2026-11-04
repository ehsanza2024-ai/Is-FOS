from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from decimal import Decimal
import os, json, sqlite3, logging
import jdatetime
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from filelock import Timeout
from app.store import Store, Conflict
from app.domain import RuleError, CHECK_TRANSITIONS
from app.security import Security
from app import imports

BASE=Path(__file__).resolve().parents[1]
DEMO=os.environ.get('MAZANDASHT_DEMO')=='1'
ROOT=Path(os.environ.get('MAZANDASHT_DATA',str(BASE/'runtime'/('demo' if DEMO else 'local'))))
store=Store(ROOT,DEMO);security=Security(ROOT,DEMO)
app=FastAPI(title='مازندشت | هسته اکسل',version='0.5.0',docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')

@app.middleware('http')
async def protection(request,call_next):
    if request.method not in ['GET','HEAD','OPTIONS']:
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):return JSONResponse({'detail':'مبدأ درخواست مجاز نیست'},status_code=403)
        size=request.headers.get('content-length','0')
        try:too_large=int(size)>3*1024*1024
        except ValueError:too_large=True
        if too_large:return JSONResponse({'detail':'درخواست بیش از حد بزرگ است'},status_code=413)
        if request.url.path!='/api/login' and request.headers.get('x-mazandasht-request')!='1':return JSONResponse({'detail':'نشان درخواست لازم است'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
    response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(RuleError)
async def rule_error(request,exc):return JSONResponse({'detail':str(exc)},status_code=409 if isinstance(exc,Conflict) else 422)
@app.exception_handler(Timeout)
async def locked(request,exc):return JSONResponse({'detail':'فایل در حال استفاده است؛ دوباره تلاش کنید'},status_code=409)
@app.exception_handler(PermissionError)
async def excel_locked(request,exc):return JSONResponse({'detail':'فایل اکسل باز یا قفل است؛ آن را ببندید و دوباره تلاش کنید'},status_code=409)

@app.get('/')
def index():return FileResponse(BASE/'static/index.html')
@app.get('/api/health')
def health():return {'ok':True,'version':'0.5.0','demo':DEMO,'today':jdatetime.date.today().strftime('%Y/%m/%d'),'status':'نسخه توسعه؛ تأیید تولید نشده'}
@app.post('/api/login')
async def login(request:Request):
    b=await request.json();token,user=security.login(str(b.get('name','')),str(b.get('password','')),request.client.host)
    res=JSONResponse({'name':user['name'],'role':user['role']});res.set_cookie('maz_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=8*3600);return res
@app.post('/api/logout')
def logout(request:Request):
    security.sessions.pop(request.cookies.get('maz_session',''),None);r=JSONResponse({'ok':True});r.delete_cookie('maz_session');return r
@app.get('/api/state')
def state(request:Request):
    user=security.require(request);data=store.read();data['user']={'name':user['name'],'role':user['role']};data['demo']=DEMO;data['check_transitions']={k:sorted(v) for k,v in CHECK_TRANSITIONS.items()}
    if user['role']!='admin':data.pop('Audit',None)
    return data
@app.post('/api/references/{sheet}')
async def reference(sheet:str,request:Request):
    user=security.require(request,'admin');b=await request.json();return store.add_ref(sheet,b['data'],user['name'],b.get('revision'))
@app.post('/api/weigh')
async def weigh(request:Request):
    user=security.require(request,'operate');b=await request.json();return store.add_weigh(b['data'],user['name'],b.get('revision'))
@app.post('/api/events')
async def events(request:Request):
    user=security.require(request,'finance');b=await request.json();return store.add_event(b['data'],user['name'],b.get('revision'))
@app.post('/api/events/{entity}/reverse')
async def reverse(entity:str,request:Request):
    user=security.require(request,'finance');b=await request.json();return store.reverse(entity,b.get('reason',''),user['name'],b.get('revision'))
@app.post('/api/checks')
async def checks(request:Request):
    user=security.require(request,'finance');b=await request.json();return store.add_check(b['data'],user['name'],b.get('revision'))
@app.post('/api/checks/{entity}/state')
async def check_state(entity:str,request:Request):
    user=security.require(request,'finance');b=await request.json();return store.check_state(entity,b['state'],user['name'],b.get('revision'))
@app.post('/api/import/preview')
async def preview(request:Request,file:UploadFile=File(...),revision:str=Form(...),mapping:str=Form('{}')):
    user=security.require(request,'finance');content=await file.read(2*1024*1024+1)
    try:m=json.loads(mapping)
    except json.JSONDecodeError:raise RuleError('نگاشت JSON معتبر نیست')
    if not isinstance(m,dict):raise RuleError('نگاشت باید یک شیء باشد')
    return imports.preview(store,content,file.filename or '',user['name'],revision,m)
@app.post('/api/import/{entity}/commit')
async def commit(entity:str,request:Request):
    user=security.require(request,'finance');b=await request.json();return imports.commit(store,entity,user['name'],b.get('revision'))
@app.get('/api/export')
def export(request:Request):
    security.require(request);return FileResponse(store.backup(),filename='Mazandasht.xlsx')
@app.get('/api/backups')
def backups(request:Request):
    security.require(request,'admin');return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(store.backups.glob('*.xlsx'),reverse=True)]
@app.post('/api/backup')
def backup(request:Request):
    security.require(request,'admin');return {'name':store.backup().name}
@app.post('/api/restore')
async def restore(request:Request):
    user=security.require(request,'admin');b=await request.json();return store.restore(b['name'],user['name'],b['revision'])
@app.post('/api/users')
async def users(request:Request):
    user=security.require(request,'admin');b=await request.json()
    try:security.add(str(b['name']),str(b['password']),str(b['role']))
    except (ValueError,sqlite3.IntegrityError) as e:raise RuleError('نام تکراری یا مشخصات کاربر نامعتبر است؛ رمز حداقل ۱۲ نویسه')
    return {'ok':True}
@app.get('/api/insights')
def insights(request:Request):
    security.require(request);s=store.read();net=sum(r['credit']-r['debit'] for r in s['trial'] if r['category']=='revenue')-sum(r['debit']-r['credit'] for r in s['trial'] if r['category']=='expense')
    return {'mode':'تحلیل قاعده‌محور محلی؛ مدل هوش مصنوعی متصل نیست','items':[{'title':'کنترل توازن','value':sum(x['balance'] for x in s['trial']),'unit':'ریال','source':'Journal → Trial'}, {'title':'سود خالص ثبت‌شده','value':net,'unit':'ریال','source':'Trial: درآمد − هزینه'}, {'title':'سبد فاقد تارای مرجع','value':sum(1 for x in s['Baskets'] if x['tare'] in [None,'']),'unit':'مورد','source':'Baskets.tare'}, {'title':'قرارداد نیازمند بازبینی','value':sum(1 for x in s['Deals'] if x['status']!='تأیید'),'unit':'مورد','source':'Deals.status'}]}
