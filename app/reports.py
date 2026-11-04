"""Read-only reports derived from posted events, never from editable balances.
Dates are Jalali document dates. Cheque state is current, not a historical snapshot.
"""
from collections import defaultdict
from datetime import datetime, timezone
from app.domain import date, posting, RuleError
from app.store import Store

PARTY_ACCOUNTS={'حساب‌های دریافتنی','حساب‌های پرداختنی'}

def build_report(data,start=None,end=None,party=None):
    start=date(start) if start else None
    end=date(end) if end else None
    if start and end and start>end:raise RuleError('از تاریخ نباید بعد از تا تاریخ باشد')
    if party and party not in {p['name'] for p in data['Parties']}:raise RuleError('نام طرف حساب معتبر نیست')
    posted=[e for e in data['Events'] if e['status']=='قطعی']
    all_asof=[e for e in posted if not end or e['date']<=end]
    asof=[e for e in all_asof if not party or e['party']==party]
    period=[e for e in asof if not start or e['date']>=start]
    before=[e for e in asof if start and e['date']<start]
    trial=Store.trial(period,data.get('Accounts'));closing=Store.trial(all_asof,data.get('Accounts'))
    category=lambda cat:sum(r['balance'] for r in closing if r['category']==cat)
    income=sum(-r['balance'] for r in trial if r['category']=='revenue')
    expenses=sum(r['balance'] for r in trial if r['category']=='expense')
    byname={r['name']:r['balance'] for r in trial}
    receivables=defaultdict(int);payables=defaultdict(int);banks=defaultdict(int)
    statements=[];opening=0;running=0
    for e in before:
        opening+=sum((l['debit']-l['credit'])*e['sign'] for l in posting(e) if l['account'] in PARTY_ACCOUNTS)
    running=opening
    for e in asof:
        for line in posting(e):
            delta=(line['debit']-line['credit'])*e['sign']
            if line['account']=='حساب‌های دریافتنی':receivables[e['party']]+=delta
            if line['account']=='حساب‌های پرداختنی':payables[e['party']]-=delta
    for e in all_asof:
        for line in posting(e):
            if line['account']=='بانک':banks[e['bank'] or 'بانک نامشخص']+=(line['debit']-line['credit'])*e['sign']
    for e in sorted(period,key=lambda e:e['date']):
        lines=[l for l in posting(e) if l['account'] in PARTY_ACCOUNTS]
        if not lines:continue
        dr=sum(l['debit']*e['sign'] for l in lines);cr=sum(l['credit']*e['sign'] for l in lines)
        running+=dr-cr
        statements.append({'id':e['id'],'date':e['date'],'party':e['party'],'kind':e['kind'],'reference':e['reference'],'note':e['note'],'debit':dr,'credit':cr,'balance':running})
    parties=[{'name':p['name'],'receivable':receivables[p['name']],'payable':payables[p['name']],'net':receivables[p['name']]-payables[p['name']]} for p in data['Parties'] if not party or p['name']==party]
    reversals={e.get('reversal_of') for e in all_asof if e.get('reversal_of')}
    used={e.get('source_weigh') for e in all_asof if e['kind'] in ['خرید','فروش'] and e['sign']==1 and e['id'] not in reversals}
    pending=[{k:r.get(k) for k in ['id','date','operation','party','product','store','basket','net','reference','deal']} for r in data['Weigh'] if r['operation'] in ['ورود','خروج','خرید مرکبات','فروش','خرید شراکتی','فروش شراکتی'] and r['id'] not in used and (not start or int(r['date'])>=start) and (not end or int(r['date'])<=end) and (not party or r['party']==party)]
    earnings=-category('revenue')-category('expense')
    sheet={'assets':category('asset'),'liabilities':-category('liability'),'capital':-category('equity'),'retained_profit':earnings}
    sheet['difference']=sheet['assets']-sheet['liabilities']-sheet['capital']-earnings
    from app.integration import physical,bank_rows_report
    return {
        'settings':{x['key']:x.get('value') for x in data.get('Settings',[])},'currencies':data.get('Currencies',[]),
        'physical':physical(data,start,end,party),'bank_statements':bank_rows_report(data,start,end,party),
        'revision':data['revision'],'generated_at':datetime.now(timezone.utc).isoformat(),'unit':'IRR',
        'filters':{'from':start,'to':end,'party':party or ''},
        'profit_loss':{'revenue':income,'cogs':byname['بهای تمام‌شده'],'operating_expense':byname['هزینه عملیاتی'],'wages':byname['هزینه دستمزد'],'expenses':expenses,'net_profit':income-expenses,'partner_profit_expense':byname.get('سهم سود شریک',0),'partner_loss_income':-byname.get('سهم زیان شریک',0)},
        'balance_sheet':sheet,'trial':trial,'parties':parties,'banks':[{'name':k,'balance':v} for k,v in banks.items()],
        'statement':{'opening':opening,'closing':running,'rows':statements},
        'unbilled_receipts':pending,'stock':Store.stock(all_asof),
        'partnerships':partnership_reports(data,start,end),
        'events':[{**e,'lines':posting(e)} for e in period],'groups':data.get('Groups',[]),
        'checks':[c for c in data['Checks'] if not party or c['party']==party],
        'counts':{'posted_period':len(period),'pending_receipts':len(pending),'open_checks':sum(c['state'] not in ['وصول‌شده','باطل‌شده'] for c in data['Checks'] if not party or c['party']==party)},
        'notes':['گزارش مدیریتی است؛ تأیید قانونی/مالیاتی نشده.', 'رسید فاکتورنشده یعنی قبض فاقد سند خرید/فروش متصل؛ وضعیت فاکتور کاغذی مستقل ثبت نشده.', 'وضعیت مالی، بانک و موجودی برای کل مجموعه تا تاریخ پایان هستند؛ وضعیت چک‌ها جاری است.', 'مانده مثبت شخص یعنی خالص طلب مجموعه؛ منفی یعنی خالص بدهی مجموعه.']
    }

def exact_json(value):
    """Avoid silent JavaScript loss above Number.MAX_SAFE_INTEGER, including totals."""
    if isinstance(value,bool) or value is None:return value
    if isinstance(value,int):return str(value)
    if isinstance(value,list):return [exact_json(v) for v in value]
    if isinstance(value,dict):return {k:exact_json(v) for k,v in value.items()}
    return value


def partnership_reports(data,start=None,end=None):
    from app.extensions import sharing
    result=[]
    for contract in data.get('Deals',[]):
        a=max(start or int(contract['start']),int(contract['start']));b=min(end or int(contract['end']),int(contract['end']))
        if a>b:continue
        try:result.append(sharing(data,contract['name'],a,b))
        except RuleError as e:result.append({'deal':contract['name'],'error':str(e)})
    return result
