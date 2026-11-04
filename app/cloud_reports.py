"""Password-encrypted, report-only handoff. No cloud tokens, SQL/auth/audit or mutation API.
Save the .mazreport into a PRIVATE free-drive folder; readers select/download it.
"""
import base64,hashlib,json,os
from datetime import datetime,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app import domain as d
from app.reports import build_report,exact_json
AAD=b'mazandasht.report.v1'
ITERATIONS=310000
MAX_PAYLOAD=50*1024*1024

def package(data,password):
    if len(password)<12:raise d.RuleError('رمز فایل گزارش حداقل ۱۲ نویسه باشد؛ رمز در فایل ذخیره نمی‌شود')
    months=sorted({str(e['date'])[:6] for e in data['Events'] if e['status']=='قطعی'})[-36:]
    variants=[('all','کل دفتر',None,None)]
    import jdatetime
    for m in months:
        y,month=int(m[:4]),int(m[4:]);last=31 if month<=6 else 30 if month<=11 else 30 if jdatetime.date(y,1,1).isleap() else 29
        variants.append((m,m[:4]+'/'+m[4:],int(m+'01'),int(m+str(last))))
    periods=[]
    for identifier,label,start,end in variants:
        report=build_report(data,start,end)
        report['events']=[{**e,'lines':d.posting(e)} for e in report['events']]
        periods.append({'id':identifier,'label':label,'report':report})
    payload={'format':'mazandasht.payload','schema':1,'created_at':datetime.now(timezone.utc).isoformat(),'revision':data['revision'],'synthetic':any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in data['Info']),'periods':periods,'tables':{k:data[k] for k in ['Parties','Accounts','Groups','Operations','Deals','Baskets','Products','Stores','Banks','Weigh','Checks']}}
    plain=json.dumps(exact_json(payload),ensure_ascii=False,separators=(',',':')).encode()
    if len(plain)>MAX_PAYLOAD:raise d.RuleError('بسته گزارش بزرگ‌تر از ۵۰ مگابایت است؛ دامنه دفتر را تفکیک کنید')
    salt=os.urandom(16);nonce=os.urandom(12);key=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS,32)
    encode=lambda b:base64.b64encode(b).decode()
    return json.dumps({'format':'mazandasht.report','version':1,'kdf':'PBKDF2-SHA256','iterations':ITERATIONS,'salt':encode(salt),'nonce':encode(nonce),'ciphertext':encode(AESGCM(key).encrypt(nonce,plain,AAD))},separators=(',',':')).encode()

def unpack(content,password):
    try:
        box=json.loads(content)
        if box['format']!='mazandasht.report' or box['version']!=1 or box['iterations']!=ITERATIONS:raise ValueError()
        dec=lambda k:base64.b64decode(box[k],validate=True)
        key=hashlib.pbkdf2_hmac('sha256',password.encode(),dec('salt'),ITERATIONS,32)
        result=json.loads(AESGCM(key).decrypt(dec('nonce'),dec('ciphertext'),AAD))
        if result['format']!='mazandasht.payload' or str(result['schema'])!='1':raise ValueError()
        return result
    except Exception:raise d.RuleError('رمز نادرست است یا بسته گزارش معتبر/سالم نیست')
