"""Traceable local advisory workspace, not a secretly trained or connected LLM.
User text/knowledge is data, never executable schema/code/financial instructions.
"""
from pathlib import Path
import hashlib,json,os
from datetime import datetime,timezone
from filelock import FileLock
from app.domain import RuleError
AGENTS=[{'id':'coordinator','name':'هماهنگ‌کننده','scope':'تقسیم درخواست و پیشنهاد مسیر ثبت؛ بدون اجرای خودکار'}, {'id':'accountant','name':'راهنمای حسابداری','scope':'توازن، سرفصل و سودوزیان'}, {'id':'partner','name':'تحلیلگر شراکت','scope':'درصد تاریخی، سود/زیان و تخصیص دوره'}, {'id':'auditor','name':'بازبین داده','scope':'تکرار، کد/نام خالی، منشأ و تطبیق'}, {'id':'developer','name':'همکار توسعه','scope':'ثبت پیشنهاد تغییر ساختار؛ بدون اجرای کد یا SQL'}]

def history(root):
    path=Path(root)/'evolution.jsonl';records=[];previous='0'*64
    if not path.exists():return []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:r=json.loads(line);digest=r.pop('hash')
        except (ValueError,KeyError):raise RuleError('دفتر تکامل خراب است؛ بازنویسی خودکار انجام نشد')
        raw=json.dumps(r,ensure_ascii=False,sort_keys=True).encode()
        if r['previous_hash']!=previous or hashlib.sha256(raw).hexdigest()!=digest:raise RuleError('زنجیره دفتر تکامل تغییر کرده است')
        r['hash']=digest;previous=digest;records.append(r)
    return records

def record(root,actor,kind,content,revision=''):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if len(json.dumps(content,ensure_ascii=False).encode())>50000:raise RuleError('متن درخواست بیش از حد بلند است')
    with FileLock(str(root/'evolution.lock'),timeout=15):
        previous=history(root)
        entry={'timestamp':datetime.now(timezone.utc).isoformat(),'actor':actor,'kind':kind,'content':content,'revision':revision,'previous_hash':previous[-1]['hash'] if previous else '0'*64}
        entry['hash']=hashlib.sha256(json.dumps(entry,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with (root/'evolution.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        os.chmod(root/'evolution.jsonl',0o600)
    return entry

def advise(root,data,actor,question):
    question=str(question).strip()
    if not question or len(question)>6000:raise RuleError('پرسش باید بین ۱ و ۶۰۰۰ نویسه باشد')
    tasks=[]
    if any(w in question for w in ['شریک','شراکت','سهم','درصد','صافی']):tasks.append({'agent':'partner','answer':'ابتدا درصد سهم و سیاست «اصیل؛ تقسیم سود دوره» را صریح تعیین کنید. سود عملیاتی از فروش منهای بهای تمام‌شده و هزینه دوره است؛ خرید کالا هزینه دوره نیست. تخصیص سود شریک، بدهی ایجاد می‌کند و پرداخت بانکی سند جدا دارد. مالکیت مشترک و امانی را با این مدل یکی نکنید.'})
    if any(w in question for w in ['بانک','اکسل','فایل','تکرار','کد','خالی']):tasks.append({'agent':'auditor','answer':'فایل را در میز ورود داده بارگذاری کنید؛ همه ردیف‌ها را بررسی کنید. کد و نام ناسازگار یا مرجع تکراری باید اصلاح شوند. شخص ناشناخته را فقط پس از تأیید با تعریف سریع بسازید؛ تشخیص عملیات از متن بانک خودکار نیست.'})
    if any(w in question for w in ['ساختار','گروه','دیتابیس','ایجاد','عملیات']):tasks.append({'agent':'developer','answer':'برای گروه، زیرگروه، حساب و عملیات از تعاریف پایه استفاده کنید؛ هر عملیات بدهکار/بستانکار صریح دارد. نگاشت تاریخی سند ثابت می‌ماند. تغییر ساختار دلخواه باید به‌عنوان پیشنهاد ثبت و با آزمون و مهاجرت نسخه‌دار بررسی شود؛ دستیار کد یا SQL اجرا نمی‌کند.'})
    if not tasks:tasks.append({'agent':'accountant','answer':'نوع رویداد، تاریخ شمسی، طرف حساب و مرجع یکتا را تعیین کنید؛ سپس مانده، سودوزیان و تراز دوره را کنترل کنید. خرید/فروش از موجودی کنترل‌شده و اصلاح سند قطعی از برگشت با علت انجام می‌شود.'})
    result={'mode':'راهنمای محلی قاعده‌محور؛ مدل زبانی متصل یا آموزش‌دیده نیست','question':question,'tasks':tasks,'context':{'revision':data['revision'],'posted_events':len(data['Events']),'contracts':len(data['Deals']),'trial_difference':sum(x['balance'] for x in data['trial'])},'executed_actions':[]}
    record(root,actor,'advice',result,data['revision']);return result
