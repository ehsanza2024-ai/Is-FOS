import shutil
from decimal import Decimal
import pytest
from openpyxl import load_workbook
from app.store import Store,fingerprint,Conflict
from app.domain import RuleError,net_weight
from app.workbook import put,rows
from app.integration import physical
from app.reports import build_report
from app.bank_reconcile import reconcile

@pytest.fixture(scope='module')
def movement_template(tmp_path_factory):
    return Store(tmp_path_factory.mktemp('movements-template'),True).path
@pytest.fixture
def ledger(tmp_path,movement_template):
    shutil.copy2(movement_template,tmp_path/'Mazandasht.xlsx');return Store(tmp_path)

def ref(s,sheet,**data):return s.add_ref(sheet,data,'test',fingerprint(s.path))
def weigh(s,**kw):
    data={'date':14050814,'operation':'ورود','party':'باغدار نمونه','product':'پرتقال آموزشی','store':'انبار آموزشی','basket':'سبد آموزشی سفید','count':10,'gross':100,'reference':'W1'};data.update(kw);return s.add_weigh(data,'test',fingerprint(s.path))

def test_exact_legacy_no_rounding_and_tare_always_subtracted():
    assert net_weight(2290,139,'1.5',1,0,0)==Decimal('2060.685')
    assert net_weight(1845,132,'.635','2.5',0,5)==1715
    with pytest.raises(RuleError):net_weight(10,1,None)

def test_transfer_moves_two_locations_not_total(ledger):
    ref(ledger,'Stores',name='انبار دوم');weigh(ledger)
    weigh(ledger,operation='انتقال',destination='انبار دوم',reference='T1')
    report=physical(ledger.read());q={r['store']:Decimal(r['qty']) for r in report['balances']}
    assert q=={'انبار آموزشی':0,'انبار دوم':85}
    assert not ledger.read()['Events'] and not ledger.read()['stock']
    with pytest.raises(RuleError):weigh(ledger,operation='انتقال',destination='انبار آموزشی',reference='T2')

def test_custody_independent_of_fruit_weight(ledger):
    weigh(ledger,operation='خروج سبد امانت',count=40,reference='B1',gross='')
    weigh(ledger,operation='ورود سبد خالی',count=15,reference='B2',gross='')
    r=physical(ledger.read());assert r['custody'][0]['count']==25
    assert not ledger.read()['Events']

def test_tip_creates_debt_then_payment_settles_without_double_expense(ledger):
    ref(ledger,'Parties',name='انعام مصطفی',code='X001')
    weigh(ledger,operation='انعام مصطفی',party='انعام مصطفی',amount=1000,reference='TIP1')
    d=ledger.read();t={x['name']:x['balance'] for x in d['trial']}
    assert t['هزینه انعام']==1000 and t['حساب‌های پرداختنی']==-1000 and t['بانک']==0
    ledger.add_event({'date':14050814,'kind':'پرداخت','party':'انعام مصطفی','bank':'بانک آموزشی','amount':400,'reference':'PAY-TIP'},'test',d['revision'])
    r=build_report(ledger.read(),party='انعام مصطفی')
    assert r['parties'][0]['payable']==600 and r['profit_loss']['expenses']==1000

def test_wrong_special_party_cannot_create_debt(ledger):
    ref(ledger,'Parties',name='انعام مصطفی',code='X001');before=fingerprint(ledger.path)
    with pytest.raises(RuleError):weigh(ledger,operation='انعام مصطفی',amount=1000)
    assert before==fingerprint(ledger.path)

def bankrow(s,**kw):
    d={'id':'BANK1','date':14050814,'bank':'بانک آموزشی','deposit':0,'withdrawal':120,'status':'نیازمند تأیید','issues':''};d.update(kw)
    with s.edit('test','stage',fingerprint(s.path)) as w:put(w,'BankStatements',d)
    return d

def test_bank_split_atomic_and_idempotent(ledger):
    bankrow(ledger)
    r=ledger.resolve_bank('BANK1',{'kind':'پرداخت','party':'باغدار نمونه','fee_amount':20},'test',fingerprint(ledger.path))
    assert len(r['event_ids'])==2
    d=ledger.read();t={x['name']:x['balance'] for x in d['trial']}
    assert t['بانک']==-120 and t['کارمزد بانکی']==20 and t['حساب‌های پرداختنی']==100 and sum(t.values())==0
    with pytest.raises(Conflict):ledger.resolve_bank('BANK1',{'kind':'پرداخت','party':'باغدار نمونه'},'test',d['revision'])

def test_bank_ambiguity_and_duplicate_are_not_auto_posted(ledger):
    bankrow(ledger,issues='نیازمند بررسی')
    with pytest.raises(RuleError):ledger.resolve_bank('BANK1',{'kind':'پرداخت','party':'باغدار نمونه'},'test',fingerprint(ledger.path))
    assert not ledger.read()['Events']

def test_bank_direction_mismatch_does_not_post(ledger):
    bankrow(ledger)
    with pytest.raises(RuleError):ledger.resolve_bank('BANK1',{'kind':'دریافت','party':'باغدار نمونه'},'test',fingerprint(ledger.path))
    assert not ledger.read()['Events']

def test_excel_fx_and_low_chroma_row_rules(ledger):
    w=load_workbook(ledger.path);assert len(w['Dashboard']._charts)==2
    assert w.defined_names['ReportCurrency'].attr_text.startswith("'Settings'")
    assert 'ReportFactor' in w['Events']['AG3'].value or any('ReportFactor' in str(c.value) for c in w['Events'][3])
    assert any(rule.formula==['$F3>0'] and rule.dxf.fill.fgColor.rgb.endswith('EEF0F2') for rules in w['BankStatements'].conditional_formatting._cf_rules.values() for rule in rules)
    assert w['Weigh']['M3'].value.count('FLOOR')==1 and 'H3*J3' in w['Weigh']['M3'].value
    assert w['Weigh']['M2'].comment and 'خالص' in w['Weigh']['M2'].comment.text


def record(i,deposit,withdrawal,balance,time='10:00'):
    return {'id':str(i),'bank':'fake','date':'14050814','time':time,'reference':str(i),'raw':{},'credit_source':deposit,'debit_source':withdrawal,'balance_source':balance,'possible_balance_shifted_column':None}

def test_unique_balance_path_corrects_reversed_direction():
    records=[record(1,0,10,90,'09:00'),record(2,20,0,70,'10:00')]
    out,summary=reconcile(records)
    assert records[1]['credit_source']==20  # input immutable
    assert out[1]['debit_source']==20 and out[1]['credit_source']==0 and summary['direction_corrections']==1

def test_duplicate_cash_identity_kept_with_source_link():
    r=record(1,0,10,90);duplicate={**r,'id':'2'}
    out,summary=reconcile([r,duplicate]);assert len(out)==2 and out[1]['duplicate_of']=='1' and summary['duplicates']==1

def test_reordered_same_time_fee_and_principal():
    records=[record(1,0,10,90,'09:00'),record(2,0,2,68),record(3,0,20,70)]
    out,summary=reconcile(records);assert summary['reconciled']==3 and not summary['direction_corrections']

def test_unprovable_balance_stays_pending():
    out,summary=reconcile([record(1,0,10,90,'09:00'),record(2,0,20,55,'10:00')])
    assert summary['pending']==1 and not out[1]['reconciled']

def test_unbilled_weigh_correction_preserves_source(ledger):
    from app.movement_store import add_weigh
    r=weigh(ledger)
    changed=add_weigh(ledger,{'gross':120},'test',fingerprint(ledger.path),r['id'])
    assert changed['id']==r['id'] and changed['net']=='105'
    assert len(ledger.read()['Weigh'])==1 and not ledger.read()['Events']

def test_loan_principal_bank_post_is_not_income_or_expense(ledger):
    bankrow(ledger,deposit=120,withdrawal=0)
    ledger.resolve_bank('BANK1',{'kind':'دریافت اصل وام','party':'باغدار نمونه'},'test',fingerprint(ledger.path))
    r=build_report(ledger.read());assert r['profit_loss']['net_profit']==0
    t={x['name']:x['balance'] for x in ledger.read()['trial']}
    assert t['بانک']==120 and t['تسهیلات مالی']==-120

def test_custom_currency_reference_keeps_ratio_without_guess(ledger):
    ref(ledger,'Currencies',name='یوان',rial_per_unit='85000.125')
    assert next(r for r in ledger.read()['Currencies'] if r['name']=='یوان')['rial_per_unit']=='85000.125'
    with pytest.raises(RuleError):ref(ledger,'Currencies',name='ارز نامعتبر',rial_per_unit='0')
