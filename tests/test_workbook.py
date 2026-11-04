from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from app.workbook import create
from scripts.repair_legacy import repair

def test_standalone_names_and_formulas(tmp_path):
    p=tmp_path/'Mazandasht.xlsx';create(p,True);w=load_workbook(p)
    assert w['Events']['T3'].value.startswith('=IF(B3=')
    assert w['Weigh']['M3'].value.startswith('=IF(B3=')
    assert w['Events'].column_dimensions['A'].hidden
    assert w['Events'].column_dimensions['W'].hidden
    assert any(d.formula1=='BasketsNames' and str(d.sqref)=='G3:G1002' for d in w['Weigh'].data_validations.dataValidation)
    assert 'Controls!B3=""' in w['Journal']['A3'].value
    assert 'Events!$AB$3:$AB$1002' in w['Stock']['C3'].value
    assert w['Trial']['F14'].value=='=SUM(D3:D12)-SUM(E3:E12)'

def test_xml_repair_preserves_formulas_extensions_and_package_parts(tmp_path):
    iw=Workbook();iw.active.title='Baskets';iw['Baskets'].append(['header']);iw['Baskets']['A9']='BK01';iw['Baskets']['B9']='سبد سفید'
    iw.create_sheet('Parties');info=tmp_path/'Info.xlsx';iw.save(info)
    w=Workbook();s=w.active;s.title='Entry';s['A1']='=1+1';s['G8']='نوع سبد';s['G9']='BK01';s['K9']='=G9&"!"';w.create_sheet('Sync')
    w.defined_names.add(DefinedName('BasketCodes',attr_text='Sync!$D$9:$D$308'))
    dv=DataValidation(type='list',formula1='BasketCodes');s.add_data_validation(dv);dv.add('G9:G1008')
    source=tmp_path/'Basket.xlsx';w.save(source)
    with ZipFile(source,'a') as z:z.writestr('customXml/sentinel.xml',b'<sensitive-extension>preserve</sensitive-extension>')
    out=tmp_path/'out.xlsx';report=repair(source,out,info)
    assert len(report['selectors'])==1
    r=load_workbook(out);assert r['Entry']['K9'].value==s['K9'].value
    assert r['Entry']['A1'].value=='=1+1'
    assert r['Entry']['G9'].value.startswith('=IF(')
    assert r['Entry'].column_dimensions['G'].hidden
    selector=report['selectors'][0]['selector'].split(':')[0]
    assert r['Entry'][selector].value=='سبد سفید'
    assert all(d.formula1!='BasketCodes' for d in r['Entry'].data_validations.dataValidation)
    with ZipFile(out) as z:assert z.read('customXml/sentinel.xml')==b'<sensitive-extension>preserve</sensitive-extension>'
