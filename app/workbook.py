"""Self-contained Excel system. Runtime uses this workbook as its source of truth.
Legacy packages are kept separate and must be reconciled before migration.
"""
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.workbook.properties import CalcProperties
from openpyxl.utils import get_column_letter as L
from app.domain import ACCOUNTS, KINDS

CAPACITY=1000
SCHEMAS={
 'Parties':['id','name','role','active','code','group','note'],
 'Baskets':['id','name','tare'],
 'Products':['id','name'], 'Stores':['id','name'], 'Banks':['id','name'],
 'Deals':['id','name','partner','share','start','end','product','status','policy','note'],
 'Groups':['id','name','parent','category','note'],
 'Accounts':['id','name','category','group','active','note'],
 'Operations':['id','name','debit','credit','active','note'],
 'Info':['key','value','note'],
 'Events':['id','date','kind','party','product','store','bank','qty','rate','input_amount','cost','status','reference','note','source_weigh','deal','share','sign','reversal_of','effective_amount','debit_account','credit_account','party_id','product_id','store_id','bank_id','deal_id','signed_qty','debit_snapshot','credit_snapshot','period_start','period_end'],
 'Weigh':['id','date','operation','party','product','store','basket','count','gross','tare','loss','waste','net','reference','note','deal','share','party_id','product_id','basket_id'],
 'Checks':['id','date','number','direction','party','bank','amount','due','state','reference','note'],
 'Imports':['id','created_at','digest','rows_json','errors_json','status'],
 'Audit':['id','timestamp','actor','action','entity','detail','previous_hash','hash'],
 'Journal':['source_id','date','party','account','debit','credit'],
 'Trial':['id','name','category','debit','credit','balance'],
 'Stock':['product','store','qty'],
 'Controls':['event_id','issue'],
 'Guide':['topic','instruction']}
FA={'id':'شناسه داخلی','name':'نام قابل نمایش','role':'نقش','active':'فعال','tare':'تارای واقعی هر سبد (کیلوگرم)',
 'date':'تاریخ شمسی','kind':'نوع رویداد','party':'طرف حساب','product':'محصول','store':'انبار','bank':'حساب بانکی',
 'qty':'مقدار (کیلوگرم)','rate':'فی (ریال)','input_amount':'مبلغ ورودی (ریال)','cost':'بهای تمام‌شده فروش (ریال)',
 'status':'وضعیت','reference':'شماره مرجع','note':'توضیحات','source_weigh':'شناسه باسکول منبع','deal':'قرارداد شراکت','share':'سهم ما (۰ تا ۱)',
 'sign':'ضریب سند','reversal_of':'برگشت سند','effective_amount':'مبلغ محاسبه‌شده (ریال)','debit_account':'حساب بدهکار','credit_account':'حساب بستانکار',
 'operation':'عملیات','basket':'نام نوع سبد','count':'تعداد سبد','gross':'وزن باسکول (کیلوگرم)','loss':'درصد افت','waste':'ضایعات (کیلوگرم)',
 'net':'وزن خالص رند به ۵ کیلو','number':'شماره چک','direction':'جهت','amount':'مبلغ (ریال)','due':'سررسید شمسی','state':'چرخه چک',
 'partner':'نام شریک','start':'شروع اعتبار','end':'پایان اعتبار','key':'تنظیم','value':'مقدار','topic':'موضوع','instruction':'راهنما',
 'source_id':'منبع سند','account':'حساب','debit':'بدهکار (ریال)','credit':'بستانکار (ریال)','category':'گروه حساب','balance':'مانده (ریال)'}
REFS={'party':'Parties','basket':'Baskets','product':'Products','store':'Stores','bank':'Banks','deal':'Deals'}

def indexed_rows(w,sheet):
    """Keep physical row addresses: filtering blank rows must not shift updates."""
    keys=SCHEMAS[sheet]
    for n,r in enumerate(w[sheet].iter_rows(min_row=3,values_only=True),3):
        if r[0] is not None and not str(r[0]).startswith('=') and (sheet not in ['Parties','Baskets','Products','Stores','Banks','Deals','Events','Weigh','Checks'] or r[1] is not None):
            yield n,dict(zip(keys,r[:len(keys)]))

def rows(w,sheet):
    return [r for _,r in indexed_rows(w,sheet)]

def put(w,sheet,record,row=None):
    s=w[sheet]
    if row is None:
        row=next((r for r in range(3,CAPACITY+3) if s.cell(r,2 if sheet in ['Parties','Baskets','Products','Stores','Banks','Deals','Events','Weigh','Checks'] else 1).value is None),None)
        if row is None:raise ValueError('ظرفیت هزار ردیف تکمیل شده؛ قبل از ادامه ظرفیت قالب را افزایش دهید')
    for k,v in record.items():
        if k not in SCHEMAS[sheet]:continue
        cell=s.cell(row,SCHEMAS[sheet].index(k)+1)
        if isinstance(v,str) and v.startswith(('=','+','-','@')) and k not in ['sign']:
            cell.value=v;cell.data_type='s' # untrusted text never becomes a formula
        else:cell.value=v
    return row

def validation(s,col,formula):
    dv=DataValidation(type='list',formula1=formula,allow_blank=True);dv.errorTitle='انتخاب نام';dv.error='یک نام معتبر از فهرست انتخاب کنید.';dv.showErrorMessage=True;dv.errorStyle='stop'
    s.add_data_validation(dv);dv.add(f'{L(col)}3:{L(col)}{CAPACITY+2}')

def create(path:Path,demo=False):
    w=Workbook();w.remove(w.active)
    w.calculation=CalcProperties(calcId=191029,fullCalcOnLoad=True,forceFullCalc=True)
    for name,keys in SCHEMAS.items():
        s=w.create_sheet(name);s.append(keys);s.append([FA.get(k,k) for k in keys]);s.row_dimensions[1].hidden=True
        s.sheet_view.rightToLeft=True;s.freeze_panes='D3';s.auto_filter.ref=f'A2:{L(len(keys))}{CAPACITY+2}'
        s.sheet_properties.pageSetUpPr.fitToPage=True;s.page_setup.orientation='landscape';s.page_setup.paperSize=s.PAPERSIZE_A4;s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;s.print_title_rows='2:2'
        for c in s[2]:c.fill=PatternFill('solid',fgColor='123D33');c.font=Font(name='Tahoma',bold=True,color='FFFFFF',size=11);c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
        s.row_dimensions[2].height=34
        for i,k in enumerate(keys,1):
            s.column_dimensions[L(i)].width=23
            if k=='id' or k.endswith('_id') or k in ['debit_account','credit_account','sign','reversal_of']:s.column_dimensions[L(i)].hidden=True
        for key,ref in REFS.items():
            if key in keys:validation(s,keys.index(key)+1,ref+'Names')
    for ref in ['Parties','Baskets','Products','Stores','Banks','Deals']:
        w.defined_names.add(DefinedName(ref+'Names',attr_text=f"'{ref}'!$B$3:INDEX('{ref}'!$B$3:$B${CAPACITY+2},MAX(1,COUNTA('{ref}'!$B$3:$B${CAPACITY+2})))"))
    validation(w['Events'],3,'"'+','.join(KINDS)+'"');validation(w['Events'],12,'"پیش‌نویس,قطعی"')
    validation(w['Checks'],4,'"دریافتی,پرداختی"');validation(w['Checks'],9,'"ثبت‌شده,واگذارشده,وصول‌شده,برگشتی,باطل‌شده"')
    for r in [{'key':'organization','value':'مازندشت','note':'نام روی چاپ'}, {'key':'schema_version','value':'1.1','note':'تغییر فقط با مهاجرت'}, {'key':'money_unit','value':'IRR','note':'تمام مبالغ ورودی ریال'}, {'key':'capacity','value':CAPACITY,'note':'ظرفیت ردیف در هر دفتر'}, {'key':'mode','value':'نمونه آموزشی' if demo else 'خالی','note':'داده نمونه، سابقه واقعی نیست'}]:put(w,'Info',r)
    put(w,'Guide',{'topic':'شروع','instruction':'تعاریف پایه را تکمیل کنید. همه فهرست‌ها نام نشان می‌دهند؛ شناسه‌ها پنهان‌اند. داده واقعی خودکار به این قالب مهاجرت نشده است.'})
    put(w,'Guide',{'topic':'اکسل مستقل','instruction':'بدون نرم‌افزار: رویدادها را در Events وارد کنید؛ نوع، تاریخ، نام شخص، محصول/انبار، مقدار و فی یا مبلغ، وضعیت قطعی و ضریب سند ۱ را وارد کنید. Journal، Trial و Stock فرمولی‌اند. برای اصلاح، ردیف معکوس با ضریب منفی ۱ اضافه کنید؛ اصل را حذف نکنید.'})
    put(w,'Guide',{'topic':'کنترل','instruction':'اکسل مستقل تراکنش، نقش و قفل غیرقابل دورزدن ندارد. قبل از قطعی‌کردن، موجودی، تاریخ، مبالغ، بهای تمام‌شده و توازن را کنترل کنید. شراکت مالی خودکار، ارزش‌گذاری خودکار و وصول چک با ثبت مالی خودکار در این نسخه فعال نیست.'})
    put(w,'Guide',{'topic':'فرمول','instruction':'خالص = FLOOR((باسکول − تعداد × تارا) × (۱ − افت/۱۰۰) − ضایعات، ۵). تارای خالی صفر نیست. مبلغ = ROUND(مقدار × فی،۰). فقط وضعیت قطعی وارد دفترکل می‌شود.'})
    if demo:
        for sn,records in {
            'Parties':[{'id':'p1','name':'باغدار نمونه','role':'تأمین‌کننده','active':'بله'},{'id':'p2','name':'خریدار نمونه','role':'خریدار','active':'بله'}],
            'Baskets':[{'id':'b1','name':'سبد آموزشی سفید','tare':'1.4'},{'id':'b2','name':'سبد آموزشی بدون تارا','tare':None}],
            'Products':[{'id':'pr1','name':'پرتقال آموزشی'}],'Stores':[{'id':'s1','name':'انبار آموزشی'}],'Banks':[{'id':'bk1','name':'بانک آموزشی'}]
        }.items():
            for r in records:put(w,sn,r)
    for r in range(3,CAPACITY+3):
        s=w['Events']
        s.cell(r,20,f'=IF(B{r}="","",IF(OR(C{r}="خرید",C{r}="فروش"),ROUND(H{r}*I{r},0),J{r}))')
        for col,side in [(21,0),(22,1)]:
            expression='""'
            for kind,pair in reversed(list(KINDS.items())):expression=f'IF(C{r}="{kind}","{pair[side]}",{expression})'
            s.cell(r,col,f'=IF(B{r}="","",{expression})')
        for key in ['party','product','store','bank','deal']:
            ci=SCHEMAS['Events'].index(key)+1;helper=SCHEMAS['Events'].index(key+'_id')+1;ref=REFS[key]
            s.cell(r,helper,f'=IFERROR(INDEX({ref}!$A$3:$A${CAPACITY+2},MATCH({L(ci)}{r},{ref}!$B$3:$B${CAPACITY+2},0)),"")')
        ws=w['Weigh'];ws.cell(r,13,f'=IF(B{r}="","",IF(OR(I{r}="",H{r}="",J{r}=""),"تارای نامشخص",IF((I{r}-H{r}*J{r})*(1-K{r}/100)-L{r}<0,"وزن منفی",FLOOR((I{r}-H{r}*J{r})*(1-K{r}/100)-L{r},5))))')
        for key in ['party','product','basket']:
            ci=SCHEMAS['Weigh'].index(key)+1;helper=SCHEMAS['Weigh'].index(key+'_id')+1;ref=REFS[key]
            ws.cell(r,helper,f'=IFERROR(INDEX({ref}!$A$3:$A${CAPACITY+2},MATCH({L(ci)}{r},{ref}!$B$3:$B${CAPACITY+2},0)),"")')
        for j in range(4):
            jr=(r-3)*4+j+3;sj=w['Journal'];gate=f'AND(Events!B{r}<>"",Events!L{r}="قطعی"'+(f',Events!C{r}="فروش"' if j>1 else '')+')'
            for col,expr in [(1,f'Events!A{r}'),(2,f'Events!B{r}'),(3,f'Events!D{r}'),(4,f'Events!{L(21+j)}{r}' if j<2 else ('"بهای تمام‌شده"' if j==2 else '"موجودی کالا"'))]:sj.cell(jr,col,f'=IF({gate},{expr},"")')
            val=f'Events!{L(20 if j<2 else 11)}{r}*IF(Events!R{r}="",1,Events!R{r})'
            sj.cell(jr,5,f'=IF({gate},{val if j in [0,2] else 0},0)');sj.cell(jr,6,f'=IF({gate},{val if j in [1,3] else 0},0)')
    for n,(code,name,cat) in enumerate(ACCOUNTS,3):
        put(w,'Trial',{'id':code,'name':name,'category':cat},n)
        w['Trial'].cell(n,4,f'=SUMIF(Journal!$D$3:$D$4002,B{n},Journal!$E$3:$E$4002)')
        w['Trial'].cell(n,5,f'=SUMIF(Journal!$D$3:$D$4002,B{n},Journal!$F$3:$F$4002)')
        w['Trial'].cell(n,6,f'=D{n}-E{n}')
    w['Trial'].cell(14,2,'کنترل توازن (باید صفر باشد)');w['Trial'].cell(14,6,'=SUM(D3:D12)-SUM(E3:E12)')
    for r in range(3,CAPACITY+3):
        w['Controls'].cell(r,1,f'=IF(Events!B{r}="","",Events!A{r})')
        w['Controls'].cell(r,2,f'=IF(Events!B{r}="","",IF(OR(Events!T{r}<=0,Events!U{r}="",Events!V{r}="",COUNTIF(Parties!$B$3:$B$1002,Events!D{r})<>1),"نوع، مبلغ یا طرف حساب نامعتبر",IF(AND(Events!C{r}="فروش",Events!K{r}<=0),"بهای تمام‌شده لازم است",IF(Events!P{r}<>"","شراکت نیازمند ثبت تخصصی است",""))))')
    for row in w['Journal'].iter_rows(min_row=3):
        r=(row[0].row-3)//4+3
        for c in row:
            if isinstance(c.value,str):c.value=c.value.replace(f'AND(Events!B{r}<>"",',f'AND(Controls!B{r}="",Events!B{r}<>"",')
    # Stock is a list of product/store pairs. Users may add pairs manually offline.
    for r in range(3,CAPACITY+3):
        w['Stock'].cell(r,3,f'=IF(OR(A{r}="",B{r}=""),"",SUMIFS(Events!$H$3:$H$1002,Events!$E$3:$E$1002,A{r},Events!$F$3:$F$1002,B{r},Events!$C$3:$C$1002,"خرید",Events!$L$3:$L$1002,"قطعی")-SUMIFS(Events!$H$3:$H$1002,Events!$E$3:$E$1002,A{r},Events!$F$3:$F$1002,B{r},Events!$C$3:$C$1002,"فروش",Events!$L$3:$L$1002,"قطعی"))')
    # The stock formula uses a signed helper quantity for reversals (column AB).
    w['Events'].cell(1,28,'signed_qty');w['Events'].cell(2,28,'مقدار علامت‌دار');w['Events'].column_dimensions['AB'].hidden=True
    for r in range(3,CAPACITY+3):w['Events'].cell(r,28,f'=IF(B{r}="","",H{r}*IF(R{r}="",1,R{r}))')
    for r in range(3,CAPACITY+3):w['Stock'].cell(r,3,w['Stock'].cell(r,3).value.replace('$H$','$AB$'))
    for sn in ['Parties','Baskets','Products','Stores','Banks','Deals','Events','Weigh','Checks']:
        for r in range(3,CAPACITY+3):
            if w[sn].cell(r,1).value is None:w[sn].cell(r,1,f'{sn}-{r-2:06d}')
    from app.schema import install
    install(w)
    path.parent.mkdir(parents=True,exist_ok=True);w.save(path)
    return path
