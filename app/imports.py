"""Staged, all-or-nothing import for the explicitly supported bank schema."""
import csv, io, json, hashlib
from zipfile import ZipFile, BadZipFile
from openpyxl import load_workbook
from app.domain import RuleError
from app.workbook import rows, indexed_rows, put
from app.store import uid, stamp, Conflict

ALIASES={'date':['date','تاریخ'],'kind':['kind','نوع عملیات','عملیات'],'party':['party','طرف حساب'],
 'bank':['bank','بانک','حساب بانکی'],'amount':['amount','مبلغ'],'reference':['reference','شماره مرجع','شماره پیگیری'],'note':['note','شرح','توضیحات']}
REQUIRED=['date','kind','party','bank','amount','reference']

def parse(content,filename,mapping=None):
    if len(content)>2*1024*1024:raise RuleError('فایل باید حداکثر ۲ مگابایت باشد')
    if filename.lower().endswith('.csv'):
        try:text=content.decode('utf-8-sig')
        except UnicodeDecodeError:raise RuleError('CSV باید با UTF-8 ذخیره شود')
        data=list(csv.reader(io.StringIO(text)))
    elif filename.lower().endswith('.xlsx'):
        try:
            with ZipFile(io.BytesIO(content)) as z:
                if sum(x.file_size for x in z.infolist())>20*1024*1024 or len(z.infolist())>500:raise RuleError('حجم بازشده فایل بیش از حد مجاز است')
            w=load_workbook(io.BytesIO(content),read_only=True,data_only=False,keep_links=False)
            s=w.worksheets[0]
            if s.max_row and s.max_row>102:raise RuleError('هر نوبت حداکثر ۱۰۰ ردیف وارد کنید')
            data=[]
            for row in s.iter_rows():
                if any(c.data_type=='f' for c in row):raise RuleError('فرمول در فایل ورودی مجاز نیست؛ مقدار ثابت صادر کنید')
                data.append([c.value for c in row])
        except (BadZipFile,KeyError):raise RuleError('ساختار XLSX معتبر نیست')
    else:raise RuleError('فقط CSV و XLSX پشتیبانی می‌شود')
    if len(data)<2 or len(data)>101:raise RuleError('فایل باید سرستون و بین ۱ تا ۱۰۰ ردیف داشته باشد')
    headers=[str(x or '').strip() for x in data[0]]
    if len(set(headers))!=len(headers):raise RuleError('سرستون تکراری یا خالی را اصلاح کنید')
    mapping=mapping or {}
    indexes={}
    for key,aliases in ALIASES.items():
        selected=mapping.get(key)
        if selected:
            if selected not in headers:raise RuleError('ستون نگاشت‌شده یافت نشد: '+selected)
            indexes[key]=headers.index(selected)
        else:indexes[key]=next((i for i,h in enumerate(headers) if h in aliases),None)
    missing=[k for k in REQUIRED if indexes[k] is None]
    if missing:raise RuleError('ستون‌های لازم: '+', '.join(missing))
    result=[]
    for row in data[1:]:
        if not any(x is not None and str(x).strip() for x in row):continue
        r={k:str(row[i] or '') if i is not None and i<len(row) else '' for k,i in indexes.items()}
        r['unit']='IRR'
        result.append(r)
    return result,headers

def preview(store,content,filename,actor,revision,mapping=None):
    records,headers=parse(content,filename,mapping)
    errors=[];validated=[]
    with store.lock:
        w=load_workbook(store.path)
        for i,r in enumerate(records,2):
            if r['kind'] not in ['دریافت','پرداخت','هزینه','سرمایه']:
                errors.append({'row':i,'message':'نوع عملیات بانکی صریح لازم است؛ برداشت/واریز به‌تنهایی کافی نیست'});continue
            try:
                store._event(w,r);validated.append(r)
            except RuleError as e:errors.append({'row':i,'message':str(e)})
    digest=hashlib.sha256(content+json.dumps(mapping or {},sort_keys=True).encode()).hexdigest()
    batch={'id':uid(),'created_at':stamp(),'digest':digest,'rows_json':json.dumps(records,ensure_ascii=False),'errors_json':json.dumps(errors,ensure_ascii=False),'status':'پیش‌نمایش'}
    if len(batch['rows_json'])>30000:raise RuleError('داده طولانی است؛ فایل را به نوبت‌های کوچک‌تر تقسیم کنید')
    with store.edit(actor,'import.preview',revision) as w:
        if any(x['digest']==digest and x['status']=='ثبت‌شده' for x in rows(w,'Imports')):raise Conflict('این فایل قبلاً ثبت شده است')
        put(w,'Imports',batch)
    return {'id':batch['id'],'headers':headers,'rows':records,'errors':errors,'valid':len(validated),'total':len(records),'revision':store.read()['revision']}

def commit(store,batch_id,actor,revision):
    with store.edit(actor,'import.commit:'+batch_id,revision) as w:
        found=next(((n,r) for n,r in indexed_rows(w,'Imports') if r['id']==batch_id),None)
        if not found:raise RuleError('پیش‌نمایش پیدا نشد')
        n,batch=found
        if batch['status']=='ثبت‌شده':raise Conflict('این نوبت قبلاً ثبت شده است')
        if json.loads(batch['errors_json']):raise RuleError('پیش‌نمایش خطا دارد؛ ابتدا فایل را اصلاح کنید')
        if any(x['digest']==batch['digest'] and x['status']=='ثبت‌شده' for x in rows(w,'Imports')):raise Conflict('فایل تکراری است')
        records=json.loads(batch['rows_json'])
        for r in records:store._event(w,r)
        put(w,'Imports',{'status':'ثبت‌شده'},n)
    return {'count':len(records)}
