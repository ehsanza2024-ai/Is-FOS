from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from decimal import Decimal
import os, json, sqlite3, logging
import jdatetime
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
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
app=FastAPI(title='مازندشت | هسته اکسل',version='0.7.0',docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')

@app.middleware('http')
async def protection(request,call_next):
    if request.method not in ['GET','HEAD','OPTIONS']:
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):return JSONResponse({'detail':'مبدأ درخواست مجاز نیست'},status_code=403)
        size=request.headers.get('content-length','0')
        try:too_large=int(size)>22*1024*1024
        except ValueError:too_large=True
        if too_large:return JSONResponse({'detail':'درخواست بیش از حد بزرگ است'},status_code=413)
        if request.url.path!='/api/login' and request.headers.get('x-mazandasht-request')!='1':return JSONResponse({'detail':'نشان درخواست لازم است'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' https://api.open-meteo.com; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'"
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
def health():return {'ok':True,'version':'0.7.0','demo':DEMO,'today':jdatetime.date.today().strftime('%Y/%m/%d'),'status':'نسخه توسعه؛ تأیید تولید نشده'}
@app.post('/api/login')
async def login(request:Request):
    b=await request.json();token,user=security.login(str(b.get('name','')),str(b.get('password','')),request.client.host)
    res=JSONResponse({'name':user['name'],'role':user['role']});res.set_cookie('maz_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=8*3600);return res
@app.post('/api/logout')
def logout(request:Request):
    security.sessions.pop(request.cookies.get('maz_session',''),None);r=JSONResponse({'ok':True});r.delete_cookie('maz_session');return r
@app.get('/api/state')
def state(request:Request):
    user=security.require(request);data=store.read();data['user']={'name':user['name'],'role':user['role']};data['demo']=DEMO or any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in data['Info']);data['check_transitions']={k:sorted(v) for k,v in CHECK_TRANSITIONS.items()}
    if user['role']!='admin':data.pop('Audit',None)
    from app.reports import exact_json
    data['trial']=exact_json(data['trial'])
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
    user=security.require(request,'finance');content=await file.read(imports.MAX_BYTES+1)
    try:m=json.loads(mapping)
    except json.JSONDecodeError:raise RuleError('نگاشت JSON معتبر نیست')
    if not isinstance(m,dict):raise RuleError('نگاشت باید یک شیء باشد')
    return imports.preview(store,content,file.filename or '',user['name'],revision,m)
@app.post('/api/import/{entity}/commit')
async def commit(entity:str,request:Request):
    user=security.require(request,'finance');b=await request.json();return imports.commit(store,entity,user['name'],b.get('revision'),b.get('selected'))
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

@app.get('/reports')
def reports_page():return FileResponse(BASE/'static/dashboard.html')

@app.get('/api/catalog')
def report_catalog(request:Request):
    user=security.require(request);data=store.read()
    return {'user':{'name':user['name'],'role':'viewer'},'read_only':True,'central':True,'demo':DEMO or any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in data['Info']),'parties':[p['name'] for p in data['Parties']],'source':'Mazandasht.xlsx','revision':data['revision']}

@app.get('/api/reports')
def report_data(request:Request,start:str|None=None,end:str|None=None,party:str|None=None):
    from app.reports import build_report,exact_json
    security.require(request);return exact_json(build_report(store.read(),start,end,party))

@app.get('/api/provenance')
def provenance(request:Request):
    from openpyxl import load_workbook
    from app.workbook import rows,SCHEMAS
    from app.store import fingerprint
    security.require(request,'admin')
    with store.lock:
        current=store.read();info={r['key']:r['value'] for r in current['Info']}
        result={'source':str(store.path.resolve()),'revision':current['revision'],'mode':info.get('mode'),'demo':DEMO or info.get('mode')=='نمونه آموزشی','events':len(current['Events']),'weigh':len(current['Weigh']),'backup':None,'explanation':'پشتیبان XLSX، تصویر کامل دفتر در زمان ذخیره است؛ پشتیبان پیش از تغییر، عمداً تراکنش جدید بعدی را ندارد. فایل JSON نسخه‌های قبلی خودکار با این دفتر ادغام نشده است.'}
        candidates=sorted(store.backups.glob('*.xlsx'),reverse=True)
        if candidates:
            p=candidates[0];w=load_workbook(p,read_only=True,data_only=False)
            old=rows(w,'Events');a={e['id'] for e in old};b={e['id'] for e in current['Events']}
            cw=load_workbook(store.path,read_only=True,data_only=False);raw=rows(cw,'Events');cw.close()
            inputs=SCHEMAS['Events'][:19]
            previous={e['id']:e for e in old};present={e['id']:e for e in raw}
            text=lambda v:'' if v is None else str(v)
            changed=[{'id':i,'fields':[k for k in inputs if text(previous[i].get(k))!=text(present[i].get(k))]} for i in sorted(a & b)]
            changed=[e for e in changed if e['fields']]
            result['backup']={'name':p.name,'sha256':fingerprint(p),'events':len(old),'same_bytes':fingerprint(p)==current['revision'],'new_event_ids':sorted(b-a),'removed_event_ids':sorted(a-b),'changed_events':changed}
            w.close()
    return result

@app.post('/api/references/{sheet}/{entity}/details')
async def reference_details(sheet:str,entity:str,request:Request):
    user=security.require(request,'admin');b=await request.json();return store.update_ref(sheet,entity,b['changes'],user['name'],b.get('revision'))

@app.post('/api/import/{entity}/rows')
async def import_rows(entity:str,request:Request):
    user=security.require(request,'finance');b=await request.json();return imports.revise(store,entity,b.get('updates',[]),user['name'],b.get('revision'))

@app.post('/api/partnership/allocate')
async def allocate(request:Request):
    user=security.require(request,'admin');b=await request.json();return store.settle(b['deal'],b['start'],b['end'],user['name'],b.get('revision'))

@app.get('/api/collaboration')
def collaboration_state(request:Request):
    from app.collaboration import AGENTS,history
    security.require(request)
    return {'mode':'محلی قاعده‌محور؛ مدل زبانی متصل نیست','agents':AGENTS,'history':history(ROOT)[-50:]}

@app.post('/api/collaboration')
async def collaboration_question(request:Request):
    from app.collaboration import advise
    user=security.require(request);b=await request.json();return advise(ROOT,store.read(),user['name'],b.get('question',''))

@app.post('/api/knowledge')
async def knowledge(request:Request):
    from app.collaboration import record
    user=security.require(request,'admin');b=await request.json()
    if b.get('kind') not in ['knowledge','proposal']:raise RuleError('نوع یادداشت معتبر نیست')
    return record(ROOT,user['name'],b['kind'],{'text':str(b.get('text',''))},store.read()['revision'])

@app.post('/api/report-package')
async def report_package(request:Request):
    from app.cloud_reports import package
    from app.store import uid
    user=security.require(request,'admin');b=await request.json();content=package(store.read(),str(b.get('password','')))
    folder=ROOT/'report-packages';folder.mkdir(exist_ok=True);name='Mazandasht-'+uid()+'.mazreport';path=folder/name
    with path.open('xb') as f:f.write(content)
    os.chmod(path,0o600)
    return {'name':name,'bytes':len(content),'download':'/api/report-package/'+name}

@app.get('/api/report-package/{name}')
def report_download(name:str,request:Request):
    security.require(request,'admin')
    if Path(name).name!=name or not name.endswith('.mazreport'):raise HTTPException(404)
    path=ROOT/'report-packages'/name
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,filename=name,media_type='application/octet-stream')


@app.get('/viewer')
def portable_viewer():return HTMLResponse((BASE/'static/dashboard.html').read_text().replace('<body>','<body data-mode="portable">'))


@app.get('/api/collaboration/export')
def collaboration_export(request:Request):
    from app.collaboration import history
    security.require(request,'admin')
    text=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in history(ROOT))
    return Response(text,media_type='application/x-ndjson',headers={'Content-Disposition':'attachment; filename="evolution.jsonl"'})
