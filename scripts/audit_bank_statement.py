"""Read-only reconciliation for the supplied Keshavarzi column layout.
No unit, opening balance, party identity or accounting purpose is guessed.
"""
import argparse,hashlib,json,csv
from pathlib import Path
from openpyxl import load_workbook,Workbook
from app.domain import money,RuleError,normalize

def audit(path,unit=None):
    w=load_workbook(path,read_only=True,data_only=False,keep_links=False);s=w.worksheets[0];data=list(s.values);w.close()
    headers=[normalize(x) for x in data[0]];required=['تاریخ','صاحب حساب','واریز','برداشت','موجودی','توضیحات']
    if any(h not in headers for h in required):raise RuleError('ستون‌های صورت‌حساب کشاورزی یافت نشد')
    rows=[];seen=set();duplicates=[];issues=[];deposit=withdrawal=0
    for line,values in enumerate(data[1:],2):
        r=dict(zip(headers,values))
        if all(v in [None,''] for v in values):issues.append({'source_row':line,'error':'ردیف خالی'});continue
        credit=money(r['واریز'] or 0);debit=money(r['برداشت'] or 0);balance=money(r['موجودی'])
        if bool(credit)==bool(debit):issues.append({'source_row':line,'error':'جهت مبلغ مبهم/صفر'})
        identity=json.dumps([str(x) for x in values],ensure_ascii=False);digest=hashlib.sha256(identity.encode()).hexdigest()
        if digest in seen:duplicates.append(line)
        seen.add(digest);deposit+=credit;withdrawal+=debit
        owner=normalize(r['صاحب حساب']);rows.append({'source_row':line,'date':normalize(r['تاریخ']),'party':owner,'credit':credit,'debit':debit,'balance':balance,'note':normalize(r['توضیحات']),'row_fingerprint':digest,'identity_status':'کد/شماره؛ هویت نامشخص' if owner.isdigit() else ('کارمزد؛ شخص نیست' if owner=='کارمزد' else 'نام اعلام‌شده بانک؛ نیازمند تطبیق'),'status':'ثبت مالی نشده'})
    mismatches=[]
    for newer,older in zip(rows,rows[1:]):
        difference=newer['balance']-older['balance']-newer['credit']+newer['debit']
        if difference:mismatches.append({'source_row':newer['source_row'],'difference_source_units':difference})
    opening=rows[-1]['balance']-rows[-1]['credit']+rows[-1]['debit'] if rows else None
    summary={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_rows':len(data)-1,'review_rows':len(rows),'order':'ترتیب فایل از جدید به قدیم؛ بررسی پیوستگی ردیف‌های مجاور','source_unit':unit or 'نامشخص؛ ارقام خام، نه ریال/تومان تأییدشده','total_credit_source_units':deposit,'total_debit_source_units':withdrawal,'net_source_units':deposit-withdrawal,'latest_balance_source_units':rows[0]['balance'] if rows else None,'inferred_opening_source_units':opening,'opening_status':'استنتاج از نخستین تراکنش زمانی؛ مانده افتتاحیه مستقل ارائه نشده','continuity_checks':max(0,len(rows)-1),'continuity_mismatches':mismatches,'duplicate_exact_rows':duplicates,'ambiguous_or_numeric_owner_rows':sum(r['party'].isdigit() or not r['party'] for r in rows),'fee_rows':sum(r['party']=='کارمزد' for r in rows),'issues':issues,'financial_posts':0,'limits':'تطبیق زنجیره مانده، جایگزین تأیید واحد، هویت، ماهیت حسابداری یا تأیید بانک نیست'}
    return summary,rows

def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--unit',choices=['IRR','IRT']);a=p.parse_args();summary,records=audit(a.source,a.unit);a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'bank-reconciliation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    book=Workbook();s=book.active;s.title='Bank-Review';columns=list(records[0]) if records else ['status'];s.append(columns)
    for r in records:
        for i,k in enumerate(columns,1):
            value=r[k];cell=s.cell(s.max_row if i>1 else s.max_row+1,i);cell.value=value;cell.data_type='s' if isinstance(value,str) else cell.data_type
    s.freeze_panes='A2';s.auto_filter.ref=s.dimensions;s.sheet_view.rightToLeft=True
    for c in s.columns:s.column_dimensions[c[0].column_letter].width=25
    info=book.create_sheet('Reconciliation');info.append(['کنترل','مقدار'])
    for k,v in summary.items():
        cell=info.cell(info.max_row+1,1,k);info.cell(cell.row,2,json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else str(v)).data_type='s'
    book.save(a.output/'Bank-Review.xlsx');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
