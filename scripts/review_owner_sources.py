"""Read original owner files; write a new complete review workbook, never a live ledger."""
from pathlib import Path
import argparse,json,os,tempfile
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from app.source_review import build_review

def write_review(review,target):
    target=Path(target)
    if target.exists():raise FileExistsError('خروجی موجود بازنویسی نمی‌شود؛ مسیر تازه انتخاب کنید')
    target.parent.mkdir(exist_ok=True,parents=True);w=Workbook();w.remove(w.active)
    labels={'source_row':'ردیف در فایل اصلی','date':'تاریخ','operation':'نوع عملیات','party_code':'کد شخص ـ تطبیق دقیق','party_name':'نام شخص','product_name':'نام محصول','product_code':'کد محصول','basket_name':'نام سبد','basket_code':'کد سبد','count':'تعداد سبد','gross':'وزن ناخالص','net_candidate_current_weigh':'خالص طبق فرمول باسکول ـ غیرقطعی','net_candidate_independent':'خالص طبق فایل شراکتی ـ غیرقطعی','bank':'بانک','debit_source':'برداشت ـ واحد منبع','credit_source':'واریز ـ واحد منبع','balance_source':'مانده ـ واحد منبع','source_unit':'واحد پول منبع','errors':'موارد بررسی','reference':'سند یا قبض','owner_literal':'نام/یادداشت درج‌شده در بانک','narrative_literal':'شرح بانک','user_description':'شرح تکمیلی','extra_description':'شرح دوم','confirmed_party_name':'نام شخص مورد تأیید شما','confirmed_party_code':'کد شخص مورد تأیید شما','confirmed_operation':'عملیات مورد تأیید شما','confirmed_fee_source':'کارمزد تفکیکی ـ واحد منبع','confirmed_direction':'جهت اصلاح‌شده مورد تأیید','confirmed_unit':'واحد پول مورد تأیید','id':'شناسه ثابت ردیف','raw':'اصل مقادیر سلول‌ها','source':'فایل و اثرانگشت منبع','linked_weigh_id':'پیوند به همان ردیف باسکول','financial_posts':'تعداد ثبت مالی قطعی','deleted_rows':'تعداد ردیف حذف‌شده','weigh_rows':'کل ردیف‌های باسکول','joint_rows':'کل ردیف‌های شراکتی','joint_linked':'شراکتی پیوندشده بدون تکرار','bank_rows':'کل ردیف‌های بانک','bank_exact_party_matches':'تطبیق دقیق کد یا نام بانک','bank_unresolved_parties':'نیازمند تعیین کد شخص','bank_fee_rows':'ردیف کارمزد مستقل','weigh_missing_net':'خالص نامعلوم بدون حدس تارا','joint_weight_conflicts':'اختلاف فرمول وزن شراکتی','weigh_operations':'تفکیک عملیات باسکول','raw_cells':'اصل همه ستون‌های بانک','possible_balance_shifted_column':'مانده احتمالی ستون جابه‌جا ـ تأییدنشده','fee':'کارمزد مستقل','embedded_fee':'مبلغ همراه کارمزد تفکیک‌نشده','posted':'ثبت شده؟','financial_posted':'ثبت مالی شده؟','physical_posted':'ثبت موجودی شده؟','append_as_new_weigh':'به باسکول دوباره افزوده شود؟'}
    def sheet(name,records):
        s=w.create_sheet(name);s.sheet_view.rightToLeft=True;s.freeze_panes='C2'
        keys=list(dict.fromkeys(k for r in records for k in r)) if records else ['status'];s.append([labels.get(k,k) for k in keys])
        for record in records:
            s.append([None]*len(keys))
            for i,k in enumerate(keys,1):
                v=record.get(k)
                if isinstance(v,(dict,list)):v=json.dumps(v,ensure_ascii=False,default=str)
                if isinstance(v,int) and abs(v)>999999999999999:v=str(v)
                if isinstance(v,str) and len(v)>32767:raise ValueError('متن سلول بیش از ظرفیت Excel؛ هیچ ردیفی بریده نشد')
                cell=s.cell(s.max_row,i);cell.value=v
                if isinstance(v,str):cell.data_type='s'
                cell.alignment=Alignment(vertical='top',wrap_text=True)
        for c in s[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='173F35')
        for col in s.columns:s.column_dimensions[col[0].column_letter].width=24
        s.auto_filter.ref=s.dimensions
    sheet('کنترل کل',[review['summary']]);sheet('تصمیم‌های لازم',[{'موضوع':k,'ابهام':v} for k,v in review['decisions_required'].items()])
    sheet('همه ردیف‌های باسکول',review['weigh']);sheet('تطبیق شراکتی',review['joint'])
    sheet('همه ردیف‌های بانک',[r for b in review['banks'] for r in b['records']]);sheet('کنترل بانک',[{'bank':b['bank'],**b['summary']} for b in review['banks']]);sheet('پاورقی بانک',[{'bank':b['bank'],**r} for b in review['banks'] for r in b['excluded']])
    sheet('پرسش کدهای بانک',[{'bank':b['bank'],'source_row':r['source_row'],'id':r['id'],'date':r['date'],'debit_source':r['debit_source'],'credit_source':r['credit_source'],'reference':r['reference'],'owner_literal':r['owner_literal'],'narrative_literal':r['narrative_literal'],'user_description':r['raw'].get('توضیحات'),'extra_description':r['raw'].get('توضیحات 2'),'raw':r['raw'],'suggested_candidates':r['candidates'],'confirmed_party_name':None,'confirmed_party_code':None,'confirmed_operation':None,'confirmed_fee_source':None,'confirmed_direction':None,'confirmed_unit':r['source_unit']} for b in review['banks'] for r in b['records'] if r['match']!='exact' and not r['fee']])
    for name,records in review['references'].items():sheet('تعاریف '+name,records)
    if review['references'].get('Parties'):
        parties=w['تعاریف Parties'];names=[c.value for c in parties[1]];name_col=parties.cell(1,names.index('Name')+1).column_letter
        w.defined_names.add(DefinedName('ReviewPartyNames',attr_text=f"'تعاریف Parties'!${name_col}$2:${name_col}${parties.max_row}"))
        questions=w['پرسش کدهای بانک'];headers=[c.value for c in questions[1]]
        if 'نام شخص مورد تأیید شما' in headers and questions.max_row>1:
            col=questions.cell(1,headers.index('نام شخص مورد تأیید شما')+1).column_letter
            dv=DataValidation(type='list',formula1='=ReviewPartyNames',allow_blank=True);questions.add_data_validation(dv);dv.add(f'{col}2:{col}{questions.max_row}')
    fd,tmp=tempfile.mkstemp(suffix='.xlsx',dir=target.parent);os.close(fd)
    try:w.save(tmp);os.chmod(tmp,0o600);os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return target

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--legacy-info',type=Path);a=p.parse_args();r=build_review(a.folder,a.legacy_info)
    if a.output.with_suffix('.json').exists():raise FileExistsError('JSON خروجی موجود بازنویسی نمی‌شود')
    write_review(r,a.output)
    a.output.with_suffix('.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    os.chmod(a.output.with_suffix('.json'),0o600)
    print(json.dumps({'summary':r['summary'],'banks':[{'bank':b['bank'],**b['summary']} for b in r['banks']]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
