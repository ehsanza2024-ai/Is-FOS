"""Pure rules. Money is integer rial, weights Decimal kg; no float money."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_FLOOR
import re
import jdatetime

class RuleError(ValueError):
    pass

DIGITS=str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك','01234567890123456789یک')
def normalize(value):
    return str(value if value is not None else '').translate(DIGITS).strip()

def decimal(value, label='عدد', minimum=Decimal('0')):
    try:
        d=Decimal(normalize(value).replace(',','').replace('٬','').replace('٫','.'))
    except (InvalidOperation,ValueError):
        raise RuleError(f'{label} نامعتبر است')
    if not d.is_finite() or d<minimum or d>Decimal('99999999999999'):
        raise RuleError(f'{label} خارج از محدوده است')
    return d

def money(value, unit='IRR'):
    if unit not in ['IRR','IRT']:raise RuleError('واحد پول باید ریال یا تومان باشد')
    n=decimal(value,'مبلغ')*(10 if unit=='IRT' else 1)
    if n!=n.to_integral_value():raise RuleError('مبلغ باید معادل ریال صحیح باشد')
    # Excel has 15 significant decimal digits; use a conservative exact integer bound.
    if n>Decimal('99999999999999'):raise RuleError('مبلغ از ظرفیت دقیق اکسل بیشتر است')
    return int(n)

def date(value):
    s=re.sub(r'[/\-]','',normalize(value))
    if not re.fullmatch(r'\d{8}',s):raise RuleError('تاریخ شمسی را به شکل ۱۴۰۵/۰۸/۱۳ وارد کنید')
    try:
        d=jdatetime.date(int(s[:4]),int(s[4:6]),int(s[6:]))
        if not 1300<=d.year<=1500:raise ValueError()
    except ValueError:raise RuleError('تاریخ شمسی معتبر نیست')
    return int(s)

def net_weight(gross,count,tare,loss=0,waste=0):
    g=decimal(gross,'وزن باسکول');c=decimal(count,'تعداد سبد')
    if c!=c.to_integral_value():raise RuleError('تعداد سبد باید صحیح باشد')
    if tare is None or normalize(tare)=='':raise RuleError('تارای سبد نامشخص است؛ صفر را فقط در صورت واقعی بودن وارد کنید')
    t=decimal(tare,'تارا');l=decimal(loss,'درصد افت');w=decimal(waste,'ضایعات')
    if l>100:raise RuleError('درصد افت باید بین صفر و صد باشد')
    net=(g-c*t)*(1-l/100)-w
    if net<0:raise RuleError('وزن خالص منفی است')
    return (net/5).to_integral_value(rounding=ROUND_FLOOR)*5

KINDS={'خرید':('موجودی کالا','حساب‌های پرداختنی'),
       'فروش':('حساب‌های دریافتنی','درآمد فروش'),
       'دریافت':('بانک','حساب‌های دریافتنی'),
       'پرداخت':('حساب‌های پرداختنی','بانک'),
       'هزینه':('هزینه عملیاتی','بانک'),
       'سرمایه':('بانک','سرمایه'),
       'دستمزد':('هزینه دستمزد','حساب‌های پرداختنی')}
ACCOUNTS=[('1000','صندوق','asset'),('1010','بانک','asset'),
 ('1100','حساب‌های دریافتنی','asset'),('1200','موجودی کالا','asset'),
 ('2000','حساب‌های پرداختنی','liability'),('3000','سرمایه','equity'),
 ('4000','درآمد فروش','revenue'),('5000','بهای تمام‌شده','expense'),
 ('6000','هزینه عملیاتی','expense'),('6010','هزینه دستمزد','expense')]

def event(data,refs,stock):
    kind=data.get('kind','')
    if kind not in KINDS:raise RuleError('نوع رویداد معتبر نیست')
    result={k:normalize(data.get(k,'')) for k in ['party','product','store','bank','reference','note','deal','source_weigh']}
    result.update(date=date(data.get('date')),kind=kind)
    for key,sheet in [('party','Parties')]:
        if result[key] not in {r['name'] for r in refs[sheet]}:raise RuleError('طرف حساب معتبر را با نام انتخاب کنید')
    for key,sheet in [('bank','Banks'),('deal','Deals')]:
        if result[key] and result[key] not in {r['name'] for r in refs[sheet]}:raise RuleError('نام '+key+' معتبر نیست')
    if kind in ['دریافت','پرداخت','هزینه','سرمایه'] and not result['bank']:raise RuleError('حساب بانکی لازم است')
    qty=Decimal('0');rate=0;cost=0
    if kind in ['خرید','فروش']:
        for key,sheet in [('product','Products'),('store','Stores')]:
            if result[key] not in {r['name'] for r in refs[sheet]}:raise RuleError('محصول و انبار را انتخاب کنید')
        qty=decimal(data.get('qty'),'مقدار')
        if qty<=0:raise RuleError('مقدار باید مثبت باشد')
        rate=money(data.get('rate'),data.get('unit','IRR'))
        amount=int((qty*rate).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if kind=='فروش':
            if stock.get((result['product'],result['store']),Decimal('0'))<qty:raise RuleError('موجودی انبار برای این فروش کافی نیست')
            cost=money(data.get('cost'),data.get('unit','IRR'))
            if cost<=0:raise RuleError('بهای تمام‌شده تأییدشده فروش لازم است؛ روش ارزش‌گذاری خودکار هنوز فعال نیست')
    else:amount=money(data.get('amount'),data.get('unit','IRR'))
    money(amount)  # bound after multiplication too
    if amount<=0:raise RuleError('مبلغ باید مثبت باشد')
    result.update(qty=str(qty),rate=rate,amount=amount,cost=cost)
    if result['deal']:
        d=next(r for r in refs['Deals'] if r['name']==result['deal'])
        if d.get('status')!='تأیید' or not int(d['start'])<=result['date']<=int(d['end']):raise RuleError('قرارداد شراکت تأیید نشده یا خارج از دوره است')
        if d.get('product') and d['product']!=result['product']:raise RuleError('محصول با قرارداد شراکت ناسازگار است')
        share=decimal(d['share'],'سهم ما')
        if share>1:raise RuleError('سهم قرارداد باید بین صفر و یک باشد')
        result['share']=str(share)
    else:result['share']='1'
    return result

def posting(e):
    dr,cr=KINDS[e['kind']];amount=int(e['amount'])
    lines=[{'account':dr,'debit':amount,'credit':0},{'account':cr,'debit':0,'credit':amount}]
    if e['kind']=='فروش':lines += [{'account':'بهای تمام‌شده','debit':int(e['cost']),'credit':0},{'account':'موجودی کالا','debit':0,'credit':int(e['cost'])}]
    if sum(x['debit'] for x in lines)!=sum(x['credit'] for x in lines):raise RuleError('سند نامتوازن است')
    return lines

CHECK_TRANSITIONS={'ثبت‌شده':{'واگذارشده','وصول‌شده','برگشتی','باطل‌شده'},'واگذارشده':{'وصول‌شده','برگشتی'},'برگشتی':{'واگذارشده','باطل‌شده'},'وصول‌شده':set(),'باطل‌شده':set()}
