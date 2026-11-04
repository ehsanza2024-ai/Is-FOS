from pathlib import Path
import shutil,json
import pytest
from app.store import Store,fingerprint,Conflict
from app.domain import RuleError
from app.extensions import POLICY,sharing
from app.cloud_reports import package,unpack
from app.collaboration import advise,history,record
from app import imports

@pytest.fixture(scope='module')
def master(tmp_path_factory):
    root=tmp_path_factory.mktemp('extended-master');return Store(root,demo=True).path
@pytest.fixture
def extended(tmp_path,master):
    shutil.copy2(master,tmp_path/'Mazandasht.xlsx');return Store(tmp_path)
def ref(s,sheet,**r):return s.add_ref(sheet,r,'test',fingerprint(s.path))
def event(s,**r):
    base={'date':'14050813','party':'باغدار نمونه','bank':'بانک آموزشی','reference':'ref-'+str(len(s.read()['Events']))};base.update(r)
    return s.add_event(base,'test',fingerprint(s.path))
def contract(s,share='60'):
    return ref(s,'Deals',name='قرارداد سود',partner='باغدار نمونه',share_percent=share,start='14050101',end='14051229',product='پرتقال آموزشی',status='تأیید',policy=POLICY)

def test_chart_operation_posting_snapshot_and_group_classification(extended):
    s=extended;assert all(p['code'] for p in s.read()['Parties']);ref(s,'Groups',name='هزینه حمل',parent='هزینه‌ها')
    ref(s,'Accounts',name='کرایه بار',group='هزینه حمل')
    ref(s,'Operations',name='پرداخت کرایه بار',debit='کرایه بار',credit='بانک')
    e=event(s,kind='پرداخت کرایه بار',amount=12345)
    data=s.read();trial={t['name']:t for t in data['trial']}
    assert trial['کرایه بار']['balance']==12345 and trial['کرایه بار']['category']=='expense'
    assert sum(t['balance'] for t in trial.values())==0
    assert e['debit_snapshot']=='کرایه بار'
    with pytest.raises(RuleError):ref(s,'Operations',name='تغییر موجودی',debit='موجودی کالا',credit='بانک')

def test_principal_contract_allocation_and_period_lock(extended):
    s=extended;contract(s)
    event(s,kind='خرید',deal='قرارداد سود',product='پرتقال آموزشی',store='انبار آموزشی',qty=100,rate=1000)
    event(s,kind='فروش',deal='قرارداد سود',party='خریدار نمونه',product='پرتقال آموزشی',store='انبار آموزشی',qty=40,rate=2000,cost=40000)
    event(s,kind='هزینه',deal='قرارداد سود',amount=10000)
    r=sharing(s.read(),'قرارداد سود');assert r['operating_profit']==30000 and r['company_profit']==18000 and r['partner_share_amount']==12000
    a=s.settle('قرارداد سود','14050801','14050829','test',fingerprint(s.path))
    trial={t['name']:t['balance'] for t in s.read()['trial']};assert trial['سهم سود شریک']==12000
    with pytest.raises(Conflict):s.settle('قرارداد سود','14050801','14050829','test',fingerprint(s.path))
    with pytest.raises(RuleError,match='دوره'):event(s,kind='هزینه',deal='قرارداد سود',amount=1000)
    s.reverse(a['event_id'],'اصلاح تخصیص','test',fingerprint(s.path))
    event(s,kind='هزینه',deal='قرارداد سود',amount=1000)
    assert sharing(s.read(),'قرارداد سود')['partner_share_amount']==11600

def test_contract_inventory_cannot_be_borrowed_from_another_scope(extended):
    s=extended;contract(s)
    event(s,kind='خرید',product='پرتقال آموزشی',store='انبار آموزشی',qty=100,rate=1000)
    with pytest.raises(RuleError,match='موجودی'):event(s,kind='فروش',deal='قرارداد سود',product='پرتقال آموزشی',store='انبار آموزشی',qty=10,rate=2000,cost=10000)

def test_loss_allocation_zero_and_hundred_percent(extended):
    s=extended;contract(s,share='0');event(s,kind='هزینه',deal='قرارداد سود',amount=101)
    r=s.settle('قرارداد سود','14050801','14050829','test',fingerprint(s.path))
    assert r['partner_share_amount']==-101 and r['company_profit']==0
    t={x['name']:x['balance'] for x in s.read()['trial']};assert t['حساب‌های دریافتنی']==101 and t['سهم زیان شریک']==-101

def test_report_encryption_no_credentials_and_tamper_rejected(extended):
    s=extended;event(s,kind='سرمایه',amount=999)
    content=package(s.read(),'Private-report-test-password');result=unpack(content,'Private-report-test-password')
    assert result['periods'][0]['report']['banks'][0]['balance']=='999'
    assert 'Audit' not in result['tables'] and 'auth' not in result and 'password' not in json.dumps(result)
    with pytest.raises(RuleError):unpack(content,'wrong')
    box=json.loads(content);box['ciphertext']=box['ciphertext'][:-4]+'AAAA'
    with pytest.raises(RuleError):unpack(json.dumps(box),'Private-report-test-password')

def test_advisory_is_traceable_and_never_executes_financial_commands(extended):
    s=extended;before=fingerprint(s.path)
    result=advise(s.root,s.read(),'test','ساختار را عوض کن و سهم شریک و بانک را ثبت کن')
    assert not result['executed_actions'] and len(result['tasks'])==3 and before==fingerprint(s.path)
    record(s.root,'test','knowledge',{'text':'این متن دستور اجرایی نیست'},before)
    assert history(s.root)[-1]['kind']=='knowledge'
    path=s.root/'evolution.jsonl';path.write_text(path.read_text().replace('test','tampered',1))
    with pytest.raises(RuleError):history(s.root)

def test_import_retains_all_rows_and_correction_of_unknown_party(extended):
    s=extended
    content=('date,kind,party,bank,amount,reference\n'+''.join(f'14050813,دریافت,شخص جدید,بانک آموزشی,1000,R{i}\n' for i in range(125))).encode()
    batch=imports.preview(s,content,'bank.csv','test',fingerprint(s.path))
    assert len(batch['rows'])==125 and len(batch['errors'])==125
    p=ref(s,'Parties',name='شخص جدید');assert p['code'].startswith('P')
    corrected=imports.revise(s,batch['id'],[],'test',fingerprint(s.path));assert not corrected['errors']
    imports.commit(s,batch['id'],'test',fingerprint(s.path),selected=[0,124]);assert len(s.read()['Events'])==2

def test_import_explicit_unit_and_party_code_consistency(extended):
    s=extended
    csv='تاریخ,عملیات,صاحب حساب,بانک,برداشت,واریز,شماره مرجع\n14050813,دریافت,خریدار نمونه,بانک آموزشی,0,1000,UNIT-1\n'.encode()
    raw,_=imports.parse(csv,'bank.csv');normalized,errors=imports.validate(s,raw);assert errors and 'واحد' in errors[0]['message']
    raw,_=imports.parse(csv,'bank.csv',{'_unit':'IRT'});normalized,errors=imports.validate(s,raw);assert not errors
    person=ref(s,'Parties',name='صاحب کد مشخص');raw[0].update(party_code=person['code']);assert 'ناسازگار' in imports.validate(s,raw)[1][0]['message']

def test_reconciliation_read_only_synthetic(tmp_path):
    from openpyxl import Workbook
    from scripts.audit_bank_statement import audit
    p=tmp_path/'synthetic-bank.xlsx';w=Workbook();s=w.active;s.append(['تاریخ','صاحب حساب','واریز','برداشت','موجودی','توضیحات'])
    s.append(['14050813','123456',0,20,130,'برداشت']);s.append(['14050812','کارمزد',0,10,150,'کارمزد']);s.append(['14050811','نام نمونه',100,0,160,'واریز']);w.save(p)
    before=fingerprint(p);summary,records=audit(p)
    assert summary['financial_posts']==0 and summary['continuity_checks']==2 and not summary['continuity_mismatches']
    assert summary['inferred_opening_source_units']==60 and summary['ambiguous_or_numeric_owner_rows']==1
    assert fingerprint(p)==before
