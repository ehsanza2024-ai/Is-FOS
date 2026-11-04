from copy import deepcopy
from decimal import Decimal
import pytest
from app.domain import event,RuleError
from app.reports import build_report,exact_json

@pytest.fixture
def data():
    refs={'Parties':[{'name':'supplier'},{'name':'customer'}],'Products':[{'name':'orange'}],'Stores':[{'name':'store'}],'Banks':[{'name':'bank'}],'Deals':[]}
    events=[]
    def add(kind,reference,day,**extra):
        r=event(dict(kind=kind,date=day,party='supplier',product='orange',store='store',bank='bank',reference=reference,**extra),refs,{('orange','store'):Decimal('100')})
        r.update(id=reference,sign=1,status='قطعی',reversal_of='');events.append(r)
    add('سرمایه','cap',14050101,amount=200000)
    add('خرید','buy',14050102,qty=100,rate=1000)
    # dict(..., **extra) intentionally doesn't duplicate party above.
    r=event({'kind':'فروش','date':14050801,'party':'customer','product':'orange','store':'store','qty':40,'rate':2000,'cost':40000,'reference':'sale'},refs,{('orange','store'):Decimal('100')});r.update(id='sale',sign=1,status='قطعی',reversal_of='');events.append(r)
    r=event({'kind':'دریافت','date':14050802,'party':'customer','bank':'bank','amount':80000,'reference':'recv'},refs,{});r.update(id='recv',sign=1,status='قطعی',reversal_of='');events.append(r)
    add('پرداخت','pay',14050803,amount=100000)
    add('هزینه','cost',14050804,amount=5000)
    return {**refs,'Events':events,'Weigh':[],'Checks':[],'revision':'a'*64}

def test_reports_financial_fixture_and_equation(data):
    r=build_report(data,'۱۴۰۵/۰۸/۰۱','14050804')
    assert r['profit_loss']['net_profit']==35000
    assert r['profit_loss']['revenue']==80000
    assert r['balance_sheet']=={'assets':235000,'liabilities':0,'capital':200000,'retained_profit':35000,'difference':0}
    assert r['banks']==[{'name':'bank','balance':175000}]
    assert r['stock'][0]['qty']=='60'
    assert r['counts']['posted_period']==4
    assert sum(x['balance'] for x in r['trial'])==0

def test_statement_opening_period_closing_and_party_filter(data):
    r=build_report(data,'14050801','14050804','supplier')
    assert r['statement']['opening']==-100000
    assert r['statement']['closing']==0
    assert len(r['statement']['rows'])==1
    assert r['statement']['rows'][0]['debit']==100000
    assert r['parties']==[{'name':'supplier','receivable':0,'payable':0,'net':0}]
    # Bank, inventory and balance sheet always describe the company, not partial party flows.
    assert r['banks'][0]['balance']==175000 and r['balance_sheet']['assets']==235000
    assert r['profit_loss']['net_profit']==-5000
    before=build_report(data,end='14050801',party='customer')
    assert before['parties'][0]['receivable']==80000

def test_unbilled_receipt_asof_and_reversed_invoice(data):
    data['Weigh']=[{'id':'w1','date':14050101,'operation':'ورود','party':'supplier','net':'100'}]
    data['Events'][1]['source_weigh']='w1'
    assert len(build_report(data,end='14050101')['unbilled_receipts'])==1
    assert not build_report(data,end='14050102')['unbilled_receipts']
    reversal=deepcopy(data['Events'][1]);reversal.update(id='rev',reversal_of='buy',sign=-1,date=14050103);data['Events'].append(reversal)
    assert len(build_report(data,end='14050103')['unbilled_receipts'])==1
    assert not build_report(data,party='customer')['unbilled_receipts']

def test_draft_and_reversal_do_not_inflate_profit(data):
    draft=deepcopy(data['Events'][2]);draft['status']='پیش‌نویس';data['Events'].append(draft)
    reversal=deepcopy(data['Events'][2]);reversal.update(id='reverse-sale',reversal_of='sale',sign=-1);data['Events'].append(reversal)
    r=build_report(data)
    assert r['profit_loss']['net_profit']==-5000
    assert r['stock'][0]['qty']=='100'
    assert r['balance_sheet']['difference']==0

@pytest.mark.parametrize('filters',[{'start':'x'},{'end':'14051230'},{'start':'14050802','end':'14050801'},{'party':'unknown'}])
def test_invalid_filters_rejected(data,filters):
    with pytest.raises(RuleError):build_report(data,**filters)

def test_exact_json_preserves_large_totals():
    n=2**53+1
    assert exact_json({'amount':n,'rows':[0,-n],'ok':True,'none':None})=={'amount':str(n),'rows':['0',str(-n)],'ok':True,'none':None}
