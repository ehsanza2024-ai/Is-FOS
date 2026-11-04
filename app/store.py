from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from zipfile import BadZipFile
import hashlib, json, os, shutil, tempfile, uuid
from filelock import FileLock
from openpyxl import load_workbook
from app import domain as d
from app.workbook import create, rows, indexed_rows, put, SCHEMAS, CAPACITY

class Conflict(d.RuleError):pass

def stamp():return datetime.now(timezone.utc).isoformat()
def uid():return uuid.uuid4().hex

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class Store:
    def __init__(self,root,demo=False,read_only=False):
        self.root=Path(root);self.read_only=read_only
        if read_only and not (self.root/'Mazandasht.xlsx').is_file():
            raise FileNotFoundError('ابتدا نصب و دفتر مرکزی را راه‌اندازی کنید؛ داشبورد دفتر جدید نمی‌سازد')
        if not read_only:self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'Mazandasht.xlsx';self.backups=self.root/'backups'
        if not read_only:self.backups.mkdir(exist_ok=True)
        self.lock=FileLock(str(self.root/'workbook.lock'),timeout=15)
        if not read_only:
            with self.lock:
                if not self.path.exists():create(self.path,demo)

    def writable(self):
        if self.read_only:raise d.RuleError('داشبورد فقط‌خواندنی است؛ ثبت فقط در سیستم مرکزی مجاز است')

    @contextmanager
    def edit(self,actor,action,expected=None):
        self.writable()
        with self.lock:
            before=fingerprint(self.path)
            if not expected or expected!=before:raise Conflict('فایل اکسل تغییر کرده است؛ صفحه را تازه کنید و دوباره اقدام کنید')
            w=load_workbook(self.path)
            self.verify_audit(w)
            yield w
            audit=rows(w,'Audit');previous=audit[-1]['hash'] if audit else '0'*64
            entry={'id':uid(),'timestamp':stamp(),'actor':actor,'action':action,'entity':'workbook','detail':'تغییر اتمیک فایل اکسل','previous_hash':previous}
            entry['hash']=hashlib.sha256(json.dumps(entry,ensure_ascii=False,sort_keys=True).encode()).hexdigest();put(w,'Audit',entry)
            # Backup is the exact previous file. Never overwrite a source or backup.
            backup=self.backups/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-'+before[:12]+'.xlsx')
            shutil.copy2(self.path,backup)
            fd,tmp=tempfile.mkstemp(suffix='.xlsx',dir=self.root);os.close(fd)
            try:
                w.save(tmp)
                with open(tmp,'rb') as stream:os.fsync(stream.fileno())
                if fingerprint(self.path)!=before:raise Conflict('اکسل هنگام ذخیره تغییر کرد؛ خروجی جدید اعمال نشد')
                os.replace(tmp,self.path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)

    @staticmethod
    def verify_audit(w):
        previous='0'*64
        for r in rows(w,'Audit'):
            h=r.pop('hash');payload={k:v for k,v in r.items()}
            expected=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if h!=expected or r['previous_hash']!=previous:raise d.RuleError('زنجیره ممیزی تغییر کرده است؛ نوشتن متوقف شد. نسخه پشتیبان را بررسی کنید')
            previous=h

    def read(self):
        with self.lock:
            w=load_workbook(self.path);self.verify_audit(w)
            data={sn:rows(w,sn) for sn in ['Parties','Baskets','Products','Stores','Banks','Deals','Info','Weigh','Events','Checks','Audit']}
            revision=fingerprint(self.path)
        for e in data['Events']:
            e['date']=d.date(e['date'])
            if e['kind'] not in d.KINDS:raise d.RuleError('نوع رویداد موجود در اکسل پشتیبانی نمی‌شود')
            if e.get('deal') and e.get('status')=='قطعی':raise d.RuleError('سند شراکتی در دفتر تازه نیازمند تطبیق تخصصی است')
            e['qty']=str(d.decimal(e.get('qty') or 0));e['rate']=d.money(e.get('rate') or 0)
            e['amount']=int((Decimal(e['qty'])*e['rate']).quantize(Decimal('1'),rounding=d.ROUND_HALF_UP)) if e['kind'] in ['خرید','فروش'] else d.money(e.get('input_amount') or 0)
            sign=d.decimal(e['sign'] if e.get('sign') is not None else 1,minimum=Decimal('-1'))
            if sign not in [Decimal('-1'),Decimal('1')]:raise d.RuleError('ضریب سند اکسل باید ۱ یا منفی ۱ باشد')
            e['sign']=int(sign);e['cost']=d.money(e.get('cost') or 0)
            d.money(e['amount'])
            for k in ['effective_amount','debit_account','credit_account']+[x for x in SCHEMAS['Events'] if x.endswith('_id')]:e.pop(k,None)
        for c in data['Checks']:
            c['date']=d.date(c['date']);c['due']=d.date(c['due'])
            if c.get('amount') in [None,'']:raise d.RuleError('مبلغ چک در اکسل خالی است؛ صفر فرض نشد')
            c['amount']=d.money(c['amount'])
            if c['amount']<=0 or c['state'] not in d.CHECK_TRANSITIONS:raise d.RuleError('مبلغ یا وضعیت چک در اکسل معتبر نیست')
        for r in data['Weigh']:
            r['date']=d.date(r['date'])
            try:r['net']=str(d.net_weight(r['gross'],r['count'],r['tare'],r.get('loss') or 0,r.get('waste') or 0))
            except d.RuleError:r['net']=None
        data.update(revision=revision,stock=self.stock(data['Events']),trial=self.trial(data['Events']))
        return data

    @staticmethod
    def stock(events):
        result={}
        for e in events:
            if e.get('status')!='قطعی' or e['kind'] not in ['خرید','فروش']:continue
            key=(e['product'],e['store']);sign=1 if e['kind']=='خرید' else -1
            result[key]=result.get(key,Decimal(0))+Decimal(str(e.get('qty') or 0))*int(e.get('sign') or 1)*sign
        return [{'product':k[0],'store':k[1],'qty':str(v)} for k,v in result.items()]

    @staticmethod
    def trial(events):
        result={n:{'id':c,'name':n,'category':cat,'debit':0,'credit':0,'balance':0} for c,n,cat in d.ACCOUNTS}
        for e in events:
            if e.get('status')!='قطعی':continue
            for line in d.posting(e):
                r=result[line['account']];r['debit']+=line['debit']*int(e.get('sign') or 1);r['credit']+=line['credit']*int(e.get('sign') or 1);r['balance']=r['debit']-r['credit']
        return list(result.values())

    @staticmethod
    def refs(w):return {sn:rows(w,sn) for sn in ['Parties','Baskets','Products','Stores','Banks','Deals']}

    def add_ref(self,sheet,data,actor,revision):
        if sheet not in ['Parties','Baskets','Products','Stores','Banks','Deals']:raise d.RuleError('نوع تعریف مجاز نیست')
        item={k:d.normalize(data.get(k,'')) for k in SCHEMAS[sheet] if k!='id'};item['id']=uid()
        if not item['name'] or len(item['name'])>120:raise d.RuleError('نام باید بین ۱ و ۱۲۰ نویسه باشد')
        if sheet=='Baskets' and item['tare']!='':item['tare']=str(d.decimal(item['tare'],'تارا'))
        with self.edit(actor,'reference.create:'+sheet,revision) as w:
            existing=rows(w,sheet)
            if any(d.normalize(r['name'])==item['name'] for r in existing):raise d.RuleError('نام تکراری است؛ نام متمایز انتخاب کنید')
            if sheet=='Deals':
                if item['partner'] not in {r['name'] for r in rows(w,'Parties')}:raise d.RuleError('نام شریک معتبر نیست')
                share=d.decimal(item['share'],'سهم')
                if share>1:raise d.RuleError('سهم باید بین صفر و یک باشد')
                item['start']=d.date(item['start']);item['end']=d.date(item['end'])
                if item['end']<item['start']:raise d.RuleError('پایان قرارداد قبل از شروع است')
                if item['product'] and item['product'] not in {r['name'] for r in rows(w,'Products')}:raise d.RuleError('محصول قرارداد معتبر نیست')
                if item['status'] not in ['تأیید','نیاز به بازبینی','بسته']:raise d.RuleError('وضعیت قرارداد نامعتبر است')
            put(w,sheet,item)
            # Pre-populate stock report pairs for offline Excel use.
            if sheet in ['Products','Stores']:
                products=rows(w,'Products');stores=rows(w,'Stores')
                for n,(p,s) in enumerate(((p,s) for p in products for s in stores),3):
                    if n>CAPACITY+2:raise d.RuleError('ظرفیت گزارش موجودی تکمیل است')
                    put(w,'Stock',{'product':p['name'],'store':s['name']},n)
        return item

    def add_weigh(self,data,actor,revision):
        r={k:d.normalize(data.get(k,'')) for k in ['operation','party','product','store','basket','reference','note','deal']}
        r.update(id=uid(),date=d.date(data.get('date')))
        with self.edit(actor,'weigh.create',revision) as w:
            refs=self.refs(w)
            for key,sn in [('party','Parties'),('product','Products'),('store','Stores'),('basket','Baskets')]:
                if r[key] not in {x['name'] for x in refs[sn]}:raise d.RuleError('همه نام‌های مرجع را انتخاب کنید')
            b=next(x for x in refs['Baskets'] if x['name']==r['basket'])
            manual=data.get('tare');tare=b.get('tare') if manual is None or d.normalize(manual)=='' else manual
            for k in ['gross','count','loss','waste']:r[k]=str(d.decimal(data.get(k) or 0))
            net=d.net_weight(r['gross'],r['count'],tare,r['loss'],r['waste']);r['tare']=str(tare)
            r['share']='1'
            if r['deal']:
                contract=next((x for x in refs['Deals'] if x['name']==r['deal']),None)
                if not contract or contract['status']!='تأیید' or not int(contract['start'])<=r['date']<=int(contract['end']):raise d.RuleError('قرارداد معتبر و تأییدشده لازم است')
                if contract['product'] and contract['product']!=r['product']:raise d.RuleError('محصول قرارداد ناسازگار است')
                r['share']=str(contract['share'])
            if r['operation'] not in ['ورود','خروج','انتقال']:raise d.RuleError('نوع عملیات معتبر نیست')
            if not r['reference']:raise d.RuleError('شماره قبض لازم است')
            if any(x['reference']==r['reference'] for x in rows(w,'Weigh')):raise d.RuleError('شماره قبض تکراری است')
            put(w,'Weigh',r)
        r['net']=str(net);return r

    def add_event(self,data,actor,revision):
        with self.edit(actor,'event.post',revision) as w:
            result=self._event(w,data)
        return result

    def _event(self,w,data):
        old=rows(w,'Events');stock={(x['product'],x['store']):Decimal(x['qty']) for x in self.stock(old)}
        r=d.event(data,self.refs(w),stock)
        if r['deal']:raise d.RuleError('قطعی‌سازی مالی شراکتی تا تعیین نگاشت مالکیت و صافی فعال نیست؛ باسکول شراکتی و قرارداد قابل ثبت‌اند')
        if r['reference'] and any(e.get('reference')==r['reference'] and e['kind']==r['kind'] for e in old):raise Conflict('مرجع تکراری است؛ سند دوباره ثبت نشد')
        if r['source_weigh']:
            weigh=next((x for x in rows(w,'Weigh') if x['id']==r['source_weigh']),None)
            if not weigh:raise d.RuleError('باسکول منبع یافت نشد')
            if weigh.get('deal'):raise d.RuleError('باسکول شراکتی نمی‌تواند به سند عادی تبدیل شود؛ تطبیق مالکیت لازم است')
            reversed_ids={e.get('reversal_of') for e in old if e.get('reversal_of')}
            if any(e.get('source_weigh')==r['source_weigh'] and int(e.get('sign') or 1)==1 and e['id'] not in reversed_ids for e in old):raise Conflict('این باسکول قبلاً به سند فعال متصل شده است')
            if r['kind'] not in ['خرید','فروش'] or any(r[k]!=weigh[k] for k in ['party','product','store']):raise d.RuleError('اطلاعات سند با باسکول منبع یکسان نیست')
            if Decimal(r['qty'])!=d.net_weight(weigh['gross'],weigh['count'],weigh['tare'],weigh.get('loss') or 0,weigh.get('waste') or 0):raise d.RuleError('مقدار سند با وزن خالص باسکول یکسان نیست')
        r.update(id=uid(),status='قطعی',sign=1,input_amount=r['amount']);d.posting(r)
        put(w,'Events',r);return r

    def reverse(self,entity,reason,actor,revision):
        if not d.normalize(reason):raise d.RuleError('علت برگشت را وارد کنید')
        with self.edit(actor,'event.reverse:'+entity,revision) as w:
            events=rows(w,'Events');e=next((r for r in events if r['id']==entity),None)
            if not e:raise d.RuleError('سند پیدا نشد')
            if e.get('reversal_of') or any(r.get('reversal_of')==entity for r in events):raise d.RuleError('سند قبلاً برگشت خورده یا خودش برگشت است')
            if e['kind']=='خرید':
                stock={(s['product'],s['store']):Decimal(s['qty']) for s in self.stock(events)}
                if stock.get((e['product'],e['store']),0)<Decimal(str(e['qty'])):raise d.RuleError('برگشت خرید باعث موجودی منفی می‌شود')
            r={k:v for k,v in e.items() if k not in ['effective_amount','debit_account','credit_account'] and not k.endswith('_id')}
            r.update(id=uid(),sign=-1,reversal_of=entity,reference='برگشت '+entity,note=d.normalize(reason));put(w,'Events',r)
        return r

    def add_check(self,data,actor,revision):
        r={k:d.normalize(data.get(k,'')) for k in SCHEMAS['Checks'] if k not in ['id','state']}
        r.update(id=uid(),date=d.date(data.get('date')),due=d.date(data.get('due')),amount=d.money(data.get('amount'),data.get('unit','IRR')),state='ثبت‌شده')
        if not r['number'] or r['amount']<=0 or r['direction'] not in ['دریافتی','پرداختی']:raise d.RuleError('شماره، جهت و مبلغ مثبت چک لازم است')
        if r['due']<r['date']:raise d.RuleError('سررسید قبل از تاریخ ثبت است')
        with self.edit(actor,'check.create',revision) as w:
            refs=self.refs(w)
            if r['party'] not in {x['name'] for x in refs['Parties']} or r['bank'] not in {x['name'] for x in refs['Banks']}:raise d.RuleError('طرف حساب و بانک معتبر لازم است')
            if any(x['number']==r['number'] and x['bank']==r['bank'] for x in rows(w,'Checks')):raise d.RuleError('شماره چک در این بانک تکراری است')
            put(w,'Checks',r)
        return r

    def check_state(self,entity,state,actor,revision):
        with self.edit(actor,'check.transition:'+entity,revision) as w:
            found=next(((n,r) for n,r in indexed_rows(w,'Checks') if r['id']==entity),None)
            if not found:raise d.RuleError('چک پیدا نشد')
            n,r=found
            if state not in d.CHECK_TRANSITIONS.get(r['state'],set()):raise d.RuleError('تغییر وضعیت چک مجاز نیست')
            # Register operational lifecycle only, never create an implicit bank posting.
            put(w,'Checks',{'state':state},n)
        return {'state':state}

    def backup(self):
        self.writable()
        with self.lock:
            target=self.backups/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-manual.xlsx');shutil.copy2(self.path,target)
        return target

    def restore(self,name,actor,revision):
        self.writable()
        if Path(name).name!=name or not name.endswith('.xlsx'):raise d.RuleError('نام پشتیبان معتبر نیست')
        candidate=self.backups/name
        if not candidate.exists():raise d.RuleError('پشتیبان پیدا نشد')
        with self.lock:
            if fingerprint(self.path)!=revision:raise Conflict('فایل تغییر کرده است')
            backup=load_workbook(candidate);self.verify_audit(backup)
            if set(SCHEMAS)-set(backup.sheetnames):raise d.RuleError('ساختار پشتیبان معتبر نیست')
            # Restore workbook contents via the normal transactional writer; preserve current audit history.
            with self.edit(actor,'backup.restore:'+name,revision) as current:
                history=rows(current,'Audit')
                for sn in SCHEMAS:
                    if sn=='Audit':continue
                    dest=current[sn];src=backup[sn]
                    for row in dest.iter_rows(min_row=3):
                        for c in row:c.value=None
                    for row in src.iter_rows(min_row=3):
                        for c in row:dest.cell(c.row,c.column,c.value)
        return {'restored':name}
