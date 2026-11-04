import shutil, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from openpyxl import load_workbook
from app.store import Store, Conflict, fingerprint
from app.domain import RuleError
from app.workbook import create, rows
from app import imports

@pytest.fixture(scope='session')
def template(tmp_path_factory):
    p=tmp_path_factory.mktemp('template')/'Mazandasht.xlsx';create(p,True);return p
@pytest.fixture
def store(tmp_path,template):
    shutil.copy2(template,tmp_path/'Mazandasht.xlsx');return Store(tmp_path)

def post(s,**overrides):
    data={'kind':'خرید','date':'14050813','party':'باغدار نمونه','product':'پرتقال آموزشی','store':'انبار آموزشی','qty':'100','rate':'1000','reference':'BUY-1'};data.update(overrides)
    return s.add_event(data,'tester',fingerprint(s.path))

def test_roundtrip_purchase_sale_bank_and_profit(store):
    post(store,kind='سرمایه',amount='200000',bank='بانک آموزشی',reference='CAP-1')
    post(store)
    sale=post(store,kind='فروش',party='خریدار نمونه',qty='40',rate='2000',cost='40000',reference='SALE-1')
    post(store,kind='دریافت',party='خریدار نمونه',amount='80000',bank='بانک آموزشی',reference='REC-1')
    post(store,kind='پرداخت',amount='100000',bank='بانک آموزشی',reference='PAY-1')
    post(store,kind='هزینه',amount='5000',bank='بانک آموزشی',reference='COST-1')
    d=store.read();t={r['name']:r['balance'] for r in d['trial']}
    assert d['stock'][0]['qty']=='60'
    assert t['موجودی کالا']==60000 and t['بانک']==175000
    assert -t['درآمد فروش']-t['بهای تمام‌شده']-t['هزینه عملیاتی']==35000
    assert sum(t.values())==0
    assert len(d['Audit'])==6 and len(list(store.backups.glob('*.xlsx')))==6
    store.reverse(sale['id'],'اشتباه در فروش','tester',d['revision'])
    assert store.read()['stock'][0]['qty']=='100'

def test_invalid_no_mutation(store):
    before=fingerprint(store.path)
    with pytest.raises(RuleError):post(store,kind='فروش',cost='100',reference='SALE-X')
    assert fingerprint(store.path)==before
    assert not list(store.backups.glob('*.xlsx'))

def test_duplicate_reference(store):
    post(store)
    with pytest.raises(Conflict):post(store)
    assert len(store.read()['Events'])==1

def test_compare_and_swap_required(store):
    rev=fingerprint(store.path);post(store)
    with pytest.raises(Conflict):store.add_ref('Products',{'name':'محصول دوم'},'test',rev)
    with pytest.raises(Conflict):store.add_ref('Products',{'name':'محصول دوم'},'test',None)

def test_simultaneous_write_only_one_wins(store):
    rev=fingerprint(store.path)
    def write(name):
        try:store.add_ref('Products',{'name':name},'test',rev);return True
        except Conflict:return False
    with ThreadPoolExecutor(2) as executor:results=list(executor.map(write,['اول','دوم']))
    assert sum(results)==1

def test_unknown_tare_blocked_zero_manual_allowed(store):
    data={'date':'14050813','operation':'ورود','party':'باغدار نمونه','product':'پرتقال آموزشی','store':'انبار آموزشی','basket':'سبد آموزشی بدون تارا','count':'10','gross':'100','reference':'W-001'}
    with pytest.raises(RuleError):store.add_weigh(data,'test',fingerprint(store.path))
    data['tare']='0';r=store.add_weigh(data,'test',fingerprint(store.path));assert r['net']=='100'
    post(store,source_weigh=r['id'])
    with pytest.raises(Conflict):post(store,source_weigh=r['id'],reference='BUY-2')

def test_missing_approval_and_zero_share_preserved(store):
    deal={'name':'شراکت آموزشی','partner':'باغدار نمونه','share':'0','start':'14050101','end':'14051229','product':'پرتقال آموزشی','status':'تأیید'}
    store.add_ref('Deals',deal,'test',fingerprint(store.path))
    assert store.read()['Deals'][0]['share']=='0'
    with pytest.raises(RuleError,match='شراکتی'):post(store,deal='شراکت آموزشی')

def test_reverse_once_and_no_negative_purchase_reversal(store):
    purchase=post(store);post(store,kind='فروش',qty='80',rate='2000',cost='80000',reference='S1')
    with pytest.raises(RuleError):store.reverse(purchase['id'],'test','test',fingerprint(store.path))

def test_formula_injection_is_text(store):
    store.add_ref('Products',{'name':'=HYPERLINK("bad")'},'test',fingerprint(store.path))
    w=load_workbook(store.path);assert w['Products']['B4'].data_type=='s'

def test_preview_commit_idempotent(store):
    content='date,kind,party,bank,amount,reference\n14050813,دریافت,خریدار نمونه,بانک آموزشی,1000,IMPORT-001\n'.encode()
    p=imports.preview(store,content,'bank.csv','test',fingerprint(store.path));assert p['errors']==[]
    assert len(store.read()['Events'])==0
    imports.commit(store,p['id'],'test',fingerprint(store.path))
    with pytest.raises(Conflict):imports.commit(store,p['id'],'test',fingerprint(store.path))
    with pytest.raises(Conflict):imports.preview(store,content,'bank.csv','test',fingerprint(store.path))
    assert len(store.read()['Events'])==1

def test_import_errors_block_whole_batch(store):
    content='date,kind,party,bank,amount,reference\n14050813,دریافت,خریدار نمونه,بانک آموزشی,1000,I1\n14050813,دریافت,نام نامعتبر,بانک آموزشی,1000,I2\n'.encode()
    p=imports.preview(store,content,'bank.csv','test',fingerprint(store.path));assert len(p['errors'])==1
    with pytest.raises(RuleError):imports.commit(store,p['id'],'test',fingerprint(store.path))
    assert not store.read()['Events']

def test_backup_restore_preserves_current_audit(store):
    backup=store.backup();post(store)
    store.restore(backup.name,'test',fingerprint(store.path));d=store.read()
    assert not d['Events'] and len(d['Audit'])==2

def test_audit_tamper_blocks_write(store):
    post(store);w=load_workbook(store.path);w['Audit']['D3']='changed';w.save(store.path)
    with pytest.raises(RuleError,match='ممیزی'):store.add_ref('Products',{'name':'new'},'test',fingerprint(store.path))

def test_checks_terminal_state_and_no_implicit_posting(store):
    r=store.add_check({'date':'14050813','due':'14050913','number':'001','direction':'دریافتی','party':'خریدار نمونه','bank':'بانک آموزشی','amount':'1000'},'test',fingerprint(store.path))
    store.check_state(r['id'],'وصول‌شده','test',fingerprint(store.path))
    with pytest.raises(RuleError):store.check_state(r['id'],'ثبت‌شده','test',fingerprint(store.path))
    assert not store.read()['Events']

def test_fractional_rial_written_outside_service_not_truncated(store):
    post(store,kind='دریافت',amount='1000',bank='بانک آموزشی',reference='R1')
    w=load_workbook(store.path);w['Events']['J3']=1000.5;w.save(store.path)
    with pytest.raises(RuleError,match='صحیح'):store.read()
