"""Schema 1.1: explicit chart/mappings, snapshot posting, principal profit-sharing only."""
from decimal import Decimal,ROUND_HALF_UP
from app import domain as d

POLICY='اصیل؛ تقسیم سود دوره'
ALLOCATIONS={'تخصیص سود شریک':('سهم سود شریک','حساب‌های پرداختنی'),'تخصیص زیان شریک':('حساب‌های دریافتنی','سهم زیان شریک')}
CATEGORIES={'asset':'دارایی‌ها','liability':'بدهی‌ها','equity':'سرمایه','revenue':'درآمدها','expense':'هزینه‌ها'}
EXTRA_ACCOUNTS=[('6020','سهم سود شریک','expense'),('4010','سهم زیان شریک','revenue')]

def defaults():
    return {
        'Groups':[{'id':'group-'+cat,'name':name,'parent':'','category':cat,'note':''} for cat,name in CATEGORIES.items()],
        'Accounts':[{'id':code,'name':name,'category':cat,'group':CATEGORIES[cat],'active':'بله','note':''} for code,name,cat in d.ACCOUNTS+EXTRA_ACCOUNTS],
        'Operations':[{'id':'op-'+str(n),'name':kind,'debit':pair[0],'credit':pair[1],'active':'بله','note':''} for n,(kind,pair) in enumerate({**d.KINDS,**ALLOCATIONS}.items(),1)]
    }

def active_allocations(events,deal):
    reversed_ids={e.get('reversal_of') for e in events}
    return [e for e in events if e.get('deal')==deal and e['kind'] in ALLOCATIONS and e.get('status')=='قطعی' and int(e.get('sign') or 1)==1 and e['id'] not in reversed_ids]

def require_open(events,deal,day):
    if deal and any(int(e['period_start'])<=day<=int(e['period_end']) for e in active_allocations(events,deal)):
        raise d.RuleError('دوره شراکت تخصیص یافته است؛ ابتدا سند تخصیص را با علت برگشت دهید')

def sharing(data,deal,start=None,end=None):
    contract=next((c for c in data['Deals'] if c['name']==deal),None)
    if not contract:raise d.RuleError('قرارداد پیدا نشد')
    start=d.date(start or contract['start']);end=d.date(end or contract['end'])
    if start>end or start<int(contract['start']) or end>int(contract['end']):raise d.RuleError('بازه تسهیم باید داخل قرارداد باشد')
    events=[e for e in data['Events'] if e.get('deal')==deal and e.get('status')=='قطعی' and start<=int(e['date'])<=end]
    operational=[e for e in events if e['kind'] not in ALLOCATIONS]
    shares={str(Decimal(str(e.get('share'))).normalize()) for e in operational}
    if len(shares)>1:raise d.RuleError('درصدهای تاریخی دوره متفاوت‌اند؛ دوره را تفکیک کنید')
    share=d.decimal(next(iter(shares)) if shares else contract['share'],'سهم')
    if share>1:raise d.RuleError('سهم بیشتر از یک مجاز نیست')
    chart={a['name']:a['category'] for a in data.get('Accounts',defaults()['Accounts'])}
    profit=0
    for e in operational:
        for line in d.posting(e):
            if chart[line['account']] in ['revenue','expense']:profit+=(line['credit']-line['debit'])*int(e.get('sign') or 1)
    partner=int((Decimal(abs(profit))*(1-share)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))*(1 if profit>=0 else -1)
    allocated=sum(int(e['amount'])*int(e.get('sign') or 1)*(1 if e['kind']=='تخصیص سود شریک' else -1) for e in events if e['kind'] in ALLOCATIONS)
    return {'deal':deal,'policy':contract.get('policy') or 'تعیین‌نشده','partner':contract['partner'],'start':start,'end':end,'company_share':str(share),'operating_profit':profit,'partner_share_amount':partner,'company_profit':profit-partner,'allocated':allocated,'remaining':partner-allocated,'source_ids':[e['id'] for e in operational]}
