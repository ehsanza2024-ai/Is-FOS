"""Synthetic-only fixtures: private owner data must not enter Git or CI artifacts."""
from decimal import Decimal
import json
from pathlib import Path
import pytest
from openpyxl import Workbook,load_workbook
from app.domain import RuleError
from app.source_review import decimal,integer,match_party,bank_statement,reference_data,weigh_review,joint_review
from scripts.review_owner_sources import write_review

PARTIES=[{'Code':'C001','Name':'علی آزمایشی'},{'Code':'JV003','Name':'شراکتی علی آزمایشی'}]

def statement(tmp_path,records,mehr=False,unit='ریال'):
    p=tmp_path/'source.xlsx';w=Workbook();s=w.active;s.title='Sheet1';s.append(['نوع ارز '+unit] if unit else ['بانک'])
    s.append(['تاریخ تراکنش','نوع تراکنش','مبلغ تراکنش','مانده','نام صاحب حساب','شرح'] if mehr else ['تاریخ','زمان','توضیحات','شماره سند','توضیحات 2','واریز','برداشت','مانده'])
    for r in records:s.append(r)
    w.save(p);return p

@pytest.mark.parametrize('value,expected',[('۱٬۲۳۴',Decimal(1234)),('١٢٣٤٫٥',Decimal('1234.5')),('0',Decimal(0)),('1,000,000',Decimal(1000000))])
def test_exact_decimal(value,expected):assert decimal(value)==expected

@pytest.mark.parametrize('value',[None,'','NaN','Infinity','1,2','=1+2','foo'])
def test_invalid_number_never_zero(value):
    with pytest.raises(RuleError):decimal(value)

def test_integer_requires_whole():
    assert integer('1,000')==1000
    assert integer(None,True)==0
    with pytest.raises(RuleError):integer('1.01')

def test_exact_whole_identity_not_substring_or_numeric_id():
    assert match_party(['شراکتی علی آزمایشی'],PARTIES)['party_code']=='JV003'
    assert match_party(['علی'],PARTIES)['party_code'] is None
    assert match_party(['انتقال به علی آزمایشی'],PARTIES)['party_code'] is None
    assert match_party(['123456789'],PARTIES)['party_code'] is None
    assert match_party(['شماره C001 توضیح'],PARTIES)['party_code']=='C001'
    assert match_party(['XC001Y'],PARTIES)['party_code'] is None

def test_competing_code_and_name_unresolved():
    r=match_party(['C001','شراکتی علی آزمایشی'],PARTIES)
    assert r['match']=='conflict' and r['party_code'] is None and len(r['candidates'])==2

def test_arabic_letters_and_digits_names_normalize():
    assert match_party(['علي آزمايشي'],PARTIES)['party_code']=='C001'

def test_balance_continuity_and_no_posts(tmp_path):
    p=statement(tmp_path,[['1405/07/02','10:00','C001','n2','',0,20,110],['1405/07/01','10:00','علی آزمایشی','n1','',30,0,130]])
    before=p.read_bytes();r=bank_statement(p,PARTIES,'test')
    assert p.read_bytes()==before
    assert r['unit']=='IRR' and r['summary']['rows']==2
    assert r['summary']['inferred_opening_source']==100
    assert r['summary']['continuity_checks']==1 and not r['summary']['continuity_mismatches']
    assert r['summary']['total_credit_source']==30 and r['summary']['total_debit_source']==20
    assert not any(x['posted'] for x in r['records'])
    assert bank_statement(p,PARTIES,'test')==r
    with pytest.raises(RuleError):bank_statement(p,PARTIES,'test','IRT')

def test_missing_balance_retains_amount_and_appended_cells(tmp_path):
    p=statement(tmp_path,[['1405/07/01 10:00','واریز','1,000',None,'علی آزمایشی','trace','شرح ستون هفتم']],mehr=True,unit='')
    r=bank_statement(p,PARTIES,'test');x=r['records'][0]
    assert r['unit'] is None
    assert x['credit_source']==1000 and x['balance_source'] is None
    assert x['narrative_literal']=='شرح ستون هفتم' and x['reference']=='trace'
    assert x['party_code']=='C001' and len(x['raw_cells'])==7
    assert r['summary']['total_credit_source']==1000
    assert r['summary']['missing_balances']==1 and r['summary']['layout_changes']==1

def test_shifted_balance_not_silently_mapped(tmp_path):
    p=statement(tmp_path,[['1405/07/01 10:00','برداشت','50',None,'2,000','trace','شرح']],mehr=True,unit='')
    x=bank_statement(p,PARTIES,'test')['records'][0]
    assert x['balance_source'] is None and x['possible_balance_shifted_column']=='2,000'
    assert x['owner_literal'] is None

def test_fee_refund_not_income_or_guessed_party(tmp_path):
    p=statement(tmp_path,[['1405/07/01 10:00','واریز','200','1,000','کارمزد','برگشت عملیات برداشت کارمزد']],mehr=True)
    r=bank_statement(p,PARTIES,'test');x=r['records'][0]
    assert x['fee'] and x['credit_source']==200 and x['party_code'] is None
    assert r['summary']['unresolved']==0 and r['summary']['fees']==1

def test_duplicate_records_preserved_not_dropped(tmp_path):
    row=['1405/07/01','10:00','علی آزمایشی','n1','',30,0,130]
    p=statement(tmp_path,[row,row]);r=bank_statement(p,PARTIES,'test')
    assert len(r['records'])==2 and r['records'][0]['id']!=r['records'][1]['id']
    assert len(r['summary']['duplicate_keys'])==1

def test_formula_amount_not_executed_or_dropped(tmp_path):
    p=statement(tmp_path,[['1405/07/01','10:00','C001','n1','', '=1+2',0,130]])
    x=bank_statement(p,PARTIES,'test')['records'][0]
    assert x['errors'] and x['credit_source'] is None and x['raw_cells'][5]=='=1+2'

def test_same_day_order_unproven_is_explicit(tmp_path):
    p=statement(tmp_path,[['1405/07/01','10:00','C001','n1','',30,0,130]])
    r=bank_statement(p,PARTIES,'test')
    assert r['summary']['order']=='unknown' and r['summary']['inferred_opening_source'] is None

def test_no_bridging_missing_rows_in_balance_check(tmp_path):
    p=statement(tmp_path,[['1405/07/01','10:00','','1','',30,0,130],['1405/07/02','10:00','','2','',10,0,None],['1405/07/03','10:00','','3','',20,0,160]])
    r=bank_statement(p,PARTIES,'test')
    assert r['summary']['continuity_checks']==0 and r['summary']['total_credit_source']==60

def weigh_fixture(tmp_path):
    p=tmp_path/'Weigh.xlsx';w=Workbook();s=w.active;s.title='Entry'
    for i in range(8):s.append([str(i)])
    row=[None]*42
    for c,v in {2:'W1',3:'خرید مرکبات',4:'C001',6:14050701,8:'P1',9:10,10:100,16:0,20:'سند1'}.items():row[c-1]=v
    s.append(row);w.save(p)
    refs={'Parties':PARTIES,'Products':[{'Code':'P1','Name':'کیوی'}],'Baskets':[]}
    return p,refs

def test_missing_tare_not_defaulted_and_physical_not_posted(tmp_path):
    p,refs=weigh_fixture(tmp_path);r=weigh_review(p,refs)
    assert len(r)==1 and r[0]['net_candidate_current_weigh'] is None
    assert not r[0]['physical_posted'] and not r[0]['financial_posted']
    assert r[0]['raw']['10']=='100'

def test_explicit_zero_tare_allowed_and_floor5(tmp_path):
    p,refs=weigh_fixture(tmp_path);w=load_workbook(p);w['Entry']['O9']=0;w['Entry']['J9']=103;w.save(p)
    assert weigh_review(p,refs)[0]['net_candidate_current_weigh']=='100'

def test_joint_linking_does_not_double_count(tmp_path):
    p,refs=weigh_fixture(tmp_path);weigh=weigh_review(p,refs)
    j=tmp_path/'joint.xlsx';w=Workbook();s=w.active;s.title='ورود و خروج'
    for i in range(6):s.append([str(i)])
    row=[None]*32
    for c,v in {2:14050701,7:'انتقال به سردخانه',8:'علی آزمایشی',9:'D1',12:'کیوی',14:10,16:100,28:'سند1'}.items():row[c-1]=v
    s.append(row);s=w.create_sheet('تعاریف و ثوابت');s['B5']=5;s['B6']=0;s['B7']='خیر';w.save(j)
    r=joint_review(j,weigh)
    assert len(r)==1 and r[0]['linked_weigh_id']==weigh[0]['id']
    assert not r[0]['append_as_new_weigh'] and r[0]['net_candidate_independent']=='100'

def test_review_export_formulas_are_text_and_output_immutable(tmp_path):
    review={'summary':{'x':1},'decisions_required':{},'weigh':[{'gross':'=1+2','id':'x','huge':9999999999999999}],'joint':[],'banks':[],'references':{}}
    target=tmp_path/'review.xlsx';write_review(review,target);before=target.read_bytes()
    w=load_workbook(target,data_only=False);s=w['همه ردیف‌های باسکول'];assert s['A2'].value=='=1+2' and s['A2'].data_type=='s';assert s['C2'].value=='9999999999999999'
    with pytest.raises(FileExistsError):write_review(review,target)
    assert before==target.read_bytes()

def test_transaction_type_fee_is_not_party_question(tmp_path):
    p=tmp_path/'bank.xlsx';w=Workbook();s=w.active;s.title='Sheet1';s.append(['نوع ارز ریال']);s.append(['تاریخ','نوع تراکنش','شرح','واریز','برداشت','مانده']);s.append(['1405/07/01','کارمزد','trace',0,10,100]);w.save(p)
    r=bank_statement(p,PARTIES,'test')
    assert r['records'][0]['fee'] and r['summary']['fees']==1 and r['summary']['unresolved']==0

def test_embedded_fee_never_silently_split(tmp_path):
    p=statement(tmp_path,[['1405/07/01','10:00','حواله و کارمزد','n1','',0,200,130]])
    x=bank_statement(p,PARTIES,'test')['records'][0]
    assert not x['fee'] and x['embedded_fee'] and x['debit_source']==200
    assert any('تفکیک' in e for e in x['errors'])

def test_reference_original_cells_kept_even_formula(tmp_path):
    p=tmp_path/'Info.xlsx';w=Workbook();s=w.active;s.title='Parties'
    for i in range(7):s.append([str(i)])
    s.append(['Code','Name','Extra']);s.append(['C001','علی آزمایشی','=1+2']);w.save(p)
    r=reference_data(p)['Parties'][0]
    assert r['_row']==9 and r['_raw_cells']==['C001','علی آزمایشی','=1+2']
    assert r['Extra']=='=1+2'

def test_review_confirmation_dropdown_uses_names(tmp_path):
    p=statement(tmp_path,[['1405/07/01','10:00','نام نامعلوم','n1','',30,0,130]])
    b=bank_statement(p,PARTIES,'test')
    r={'summary':{},'decisions_required':{},'weigh':[],'joint':[],'banks':[b],'references':{'Parties':PARTIES}}
    target=tmp_path/'review.xlsx';write_review(r,target);w=load_workbook(target)
    dv=w['پرسش کدهای بانک'].data_validations.dataValidation
    assert len(dv)==1 and dv[0].formula1=='=ReviewPartyNames'
    assert w.defined_names['ReviewPartyNames'].attr_text=="'تعاریف Parties'!$B$2:$B$3"
