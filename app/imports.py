"""Review all source rows; explicit mappings, no guessed party/operation or silent truncation.
Pending JSON is technical staging; only committed Events affect the Excel ledger.
"""
import csv,io,json,hashlib,os,tempfile
from pathlib import Path
from zipfile import ZipFile,BadZipFile
from openpyxl import load_workbook
from app import domain as d
from app.domain import RuleError
from app.workbook import rows,indexed_rows,put,CAPACITY
from app.store import uid,stamp,Conflict
MAX_BYTES=20*1024*1024
MAX_ROWS=50000
ALIASES={'date':['date','تاریخ'],'kind':['kind','نوع عملیات','عملیات'],'party':['party','طرف حساب','نام صاحب حساب','نام شخص','صاحب حساب'], 'party_code':['party_code','کد حساب','کد شخص'],'bank':['bank','بانک','حساب بانکی'],'amount':['amount','مبلغ'],'debit':['debit','برداشت','بدهکار'],'credit':['credit','واریز','بستانکار'],'reference':['reference','شماره مرجع','شماره پیگیری'],'note':['note','شرح','توضیحات'],'unit':['unit','واحد','واحد مبلغ']}
REQUIRED=['date','kind','party','bank','amount','reference']

def parse(content,filename,mapping=None):
    if len(content)>MAX_BYTES:raise RuleError('فایل بیش از ۲۰ مگابایت است؛ فایل را تقسیم کنید')
    mapping=mapping or {};sheet=mapping.get('_sheet')
    if not isinstance(mapping.get('_defaults',{}),dict):raise RuleError('مقادیر پیش‌فرض باید شیء JSON باشند')
    if filename.lower().endswith('.csv'):
        try:
            table=csv.reader(io.StringIO(content.decode('utf-8-sig')));data=[]
            for n,row in enumerate(table):
                if n>MAX_ROWS:raise RuleError('بیش از ۵۰ هزار ردیف؛ فایل را تقسیم کنید')
                data.append(row)
        except UnicodeDecodeError:raise RuleError('CSV باید UTF-8 باشد')
    elif filename.lower().endswith('.xlsx'):
        try:
            with ZipFile(io.BytesIO(content)) as z:
                if sum(x.file_size for x in z.infolist())>100*1024*1024 or len(z.infolist())>1500:raise RuleError('حجم بازشده فایل بیش از حد مجاز است')
            w=load_workbook(io.BytesIO(content),read_only=True,data_only=False,keep_links=False)
            s=w[sheet] if sheet else w.worksheets[0]
            if s.max_column and s.max_column>100:raise RuleError('حداکثر ۱۰۰ ستون در یک ورودی پشتیبانی می‌شود')
            if s.max_row and s.max_row>MAX_ROWS+1:raise RuleError('بیش از ۵۰ هزار ردیف؛ فایل را تقسیم کنید')
            data=[]
            for row in s.iter_rows():
                if any(c.data_type=='f' for c in row):raise RuleError('فایل ورودی فرمول دارد؛ خروجی مقدار ثابت و شیت صحیح را انتخاب کنید؛ فرمول حدس زده نمی‌شود')
                data.append([c.value for c in row])
            w.close()
        except (BadZipFile,KeyError):raise RuleError('ساختار XLSX یا شیت انتخابی معتبر نیست')
    else:raise RuleError('فقط CSV و XLSX پشتیبانی می‌شود')
    if not 2<=len(data)<=MAX_ROWS+1:raise RuleError('فایل باید سرستون و ۱ تا ۵۰ هزار ردیف داشته باشد')
    headers=[str(x if x is not None else '').strip() for x in data[0]]
    if len(headers)>100 or any(not h for h in headers) or len(set(headers))!=len(headers):raise RuleError('سرستون خالی/تکراری یا بیش از ۱۰۰ ستون است')
    indexes={}
    for key,aliases in ALIASES.items():
        selected=mapping.get(key)
        if selected and selected not in headers:raise RuleError('ستون نگاشت‌شده یافت نشد: '+str(selected))
        indexes[key]=headers.index(selected) if selected else next((i for i,h in enumerate(headers) if h in aliases),None)
    result=[]
    for number,row in enumerate(data[1:],2):
        r={k:str(row[i] if row[i] is not None else '') if i is not None and i<len(row) else '' for k,i in indexes.items()}
        for k,v in mapping.get('_defaults',{}).items():
            if k in ALIASES and not r[k]:r[k]=str(v)
        r.update(unit=r.get('unit') or mapping.get('_unit') or ('IRR' if 'amount' in headers else ''),source_row=number)
        # Blank source rows remain visible as errors; not dropped or assigned zero.
        result.append(r)
    return result,headers

def validate(store,records):
    with store.lock:
        w=load_workbook(store.path);refs=store.refs(w);old=rows(w,'Events');w.close()
    names={d.normalize(p['name']):p['name'] for p in refs['Parties']};codes={str(p.get('code')):p['name'] for p in refs['Parties'] if p.get('code')}
    seen={(e['kind'],d.normalize(e.get('reference'))) for e in old if e.get('reference')};errors=[];normalized=[]
    for index,raw in enumerate(records):
        r=dict(raw);issues=[]
        code=d.normalize(r.get('party_code'));name=d.normalize(r.get('party'))
        if code and code in codes:
            if name and name!=d.normalize(codes[code]):issues.append('کد و نام صاحب حساب ناسازگارند')
            if not name:r['party']=codes[code]
        elif code:issues.append('کد حساب ناشناخته؛ تعریف یا اصلاح کنید')
        if not r.get('amount') and (r.get('debit') or r.get('credit')):
            try:
                debit=d.money(r.get('debit') or 0);credit=d.money(r.get('credit') or 0)
                if bool(debit)==bool(credit):issues.append('برداشت و واریز باید دقیقاً یکی مثبت باشد')
                elif r.get('kind') in ['دریافت','سرمایه'] and credit:r['amount']=str(credit)
                elif r.get('kind') in ['پرداخت','هزینه'] and debit:r['amount']=str(debit)
                else:issues.append('عملیات انتخابی با جهت بانکی سازگار نیست')
            except RuleError as e:issues.append(str(e))
        if r.get('unit') not in ['IRR','IRT']:issues.append('واحد مبلغ باید صریحاً IRR (ریال) یا IRT (تومان) باشد')
        missing=[k for k in REQUIRED if not d.normalize(r.get(k))]
        if missing:issues.append('فیلد خالی: '+', '.join(missing))
        if r.get('kind') not in ['دریافت','پرداخت','هزینه','سرمایه']:issues.append('نوع بانکی صریح لازم است؛ از شرح بانک حدس زده نمی‌شود')
        key=(r.get('kind'),d.normalize(r.get('reference')))
        if key in seen:issues.append('مرجع تکراری در فایل یا دفتر موجود')
        if key[1]:seen.add(key)
        if not issues:
            try:d.event(r,refs,{})
            except RuleError as e:issues.append(str(e))
        if issues:errors.append({'index':index,'row':r.get('source_row',index+2),'message':'؛ '.join(issues)})
        normalized.append(r)
    return normalized,errors

def save_stage(store,identifier,records):
    folder=store.root/'import-staging';folder.mkdir(exist_ok=True)
    payload=json.dumps(records,ensure_ascii=False).encode();digest=hashlib.sha256(payload).hexdigest();path=folder/(identifier+'-'+digest+'.json')
    if not path.exists():
        fd,tmp=tempfile.mkstemp(dir=folder)
        try:
            with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o600);os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return json.dumps({'file':path.name,'sha256':digest},ensure_ascii=False)

def read_stage(store,batch):
    descriptor=json.loads(batch['rows_json'])
    if isinstance(descriptor,list):return descriptor  # 0.6 staged batches
    name=descriptor['file']
    if Path(name).name!=name:raise RuleError('مسیر staging معتبر نیست')
    payload=(store.root/'import-staging'/name).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=descriptor['sha256']:raise RuleError('فایل staging تغییر کرده است')
    return json.loads(payload)

def preview(store,content,filename,actor,revision,mapping=None):
    store.writable()
    records,headers=parse(content,filename,mapping);records,errors=validate(store,records)
    digest=hashlib.sha256(content+json.dumps(mapping or {},sort_keys=True).encode()).hexdigest();identifier=uid()
    descriptor=save_stage(store,identifier,records)
    with store.edit(actor,'import.review',revision) as w:
        if any(x['digest']==digest and x['status']=='ثبت‌شده' for x in rows(w,'Imports')):raise Conflict('این فایل قبلاً ثبت شده است')
        put(w,'Imports',{'id':identifier,'created_at':stamp(),'digest':digest,'rows_json':descriptor,'errors_json':'[]','status':'بازبینی'})
    return {'id':identifier,'headers':headers,'rows':records,'errors':errors,'valid':len(records)-len(errors),'total':len(records),'revision':store.read()['revision']}

def revise(store,identifier,updates,actor,revision):
    with store.edit(actor,'import.correct',revision) as w:
        n,batch=next(((n,r) for n,r in indexed_rows(w,'Imports') if r['id']==identifier),(None,None))
        if batch is None or batch['status']=='ثبت‌شده':raise RuleError('نوبت قابل اصلاح نیست')
        records=read_stage(store,batch)
        for update in updates:
            i=update.get('index');changes=update.get('changes')
            if not isinstance(i,int) or not 0<=i<len(records) or not isinstance(changes,dict) or set(changes)-set(ALIASES):raise RuleError('ویرایش ردیف معتبر نیست')
            records[i].update({k:d.normalize(v) for k,v in changes.items()})
        records,errors=validate(store,records);put(w,'Imports',{'rows_json':save_stage(store,identifier,records)},n)
    return {'id':identifier,'rows':records,'errors':errors,'total':len(records),'valid':len(records)-len(errors),'revision':store.read()['revision']}

def commit(store,batch_id,actor,revision,selected=None):
    with store.edit(actor,'import.commit:'+batch_id,revision) as w:
        found=next(((n,r) for n,r in indexed_rows(w,'Imports') if r['id']==batch_id),None)
        if not found:raise RuleError('پیش‌نمایش پیدا نشد')
        n,batch=found
        if batch['status']=='ثبت‌شده':raise Conflict('این نوبت قبلاً ثبت شده است')
        records=read_stage(store,batch)
        if selected is not None:
            if not isinstance(selected,list) or len(set(selected))!=len(selected) or any(not isinstance(i,int) or not 0<=i<len(records) for i in selected):raise RuleError('ردیف‌های انتخابی نامعتبر است')
            records=[records[i] for i in selected]
        if not records:raise RuleError('هیچ ردیفی انتخاب نشده است')
        records,errors=validate(store,records)
        if errors:raise RuleError('نوبت خطا دارد؛ ابتدا نام/کد، تکرارها و فیلدهای خالی را اصلاح کنید')
        free=sum(1 for i in range(3,CAPACITY+3) if w['Events'].cell(i,2).value is None)
        if len(records)>free:raise RuleError(f'ظرفیت آزاد دفتر {free} ردیف است؛ نمایش/بازبینی ورودی محدود به این تعداد نیست، ثبت نیازمند دفتر با ظرفیت کافی است')
        for r in records:store._event(w,r)
        put(w,'Imports',{'status':'ثبت‌شده'},n)
    return {'count':len(records)}
