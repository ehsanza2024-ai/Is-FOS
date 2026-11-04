"""Upgrade only the canonical ledger; never apply this to the 14 legacy files."""
from openpyxl.styles import Font,PatternFill
from openpyxl.workbook.defined_name import DefinedName
from app.workbook import SCHEMAS,CAPACITY,rows,indexed_rows,put,validation
from app.extensions import defaults,POLICY

def install(w):
    for sn in ['Groups','Accounts','Operations']:
        if sn not in w:
            s=w.create_sheet(sn);s.append(SCHEMAS[sn]);s.append(SCHEMAS[sn]);s.row_dimensions[1].hidden=True;s.sheet_view.rightToLeft=True;s.freeze_panes='C3'
            for c in s[2]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='123D33')
        if not rows(w,sn):
            for record in defaults()[sn]:put(w,sn,record)
        w.defined_names.add(DefinedName(sn+'Names',attr_text=f"'{sn}'!$B$3:INDEX('{sn}'!$B$3:$B${CAPACITY+2},MAX(1,COUNTA('{sn}'!$B$3:$B${CAPACITY+2})))"))
    for sn in ['Parties','Deals','Events']:
        for n,key in enumerate(SCHEMAS[sn],1):
            w[sn].cell(1,n,key)
            if w[sn].cell(2,n).value is None:w[sn].cell(2,n,key)
    # Stable local party codes for existing canonical records; never infer bank identities.
    parties=list(indexed_rows(w,'Parties'));used={str(r.get('code')) for _,r in parties if r.get('code')}
    if len(used)!=sum(bool(r.get('code')) for _,r in parties):
        from app.domain import RuleError
        raise RuleError('کدهای موجود اشخاص تکراری‌اند؛ ارتقا بدون تغییر متوقف شد')
    counter=1
    for row,r in parties:
        if r.get('code'):continue
        while 'P'+str(counter).zfill(6) in used:counter+=1
        code='P'+str(counter).zfill(6);used.add(code);put(w,'Parties',{'code':code},row)
    for dv in list(w['Events'].data_validations.dataValidation):
        if str(dv.sqref)==f'C3:C{CAPACITY+2}':w['Events'].data_validations.dataValidation.remove(dv)
    validation(w['Events'],3,'OperationsNames')
    for sheet,col,ref in [('Groups',3,'GroupsNames'),('Accounts',4,'GroupsNames'),('Operations',3,'AccountsNames'),('Operations',4,'AccountsNames'),('Parties',6,'GroupsNames')]:
        s=w[sheet]
        from openpyxl.utils import get_column_letter
        target=f'{get_column_letter(col)}3:{get_column_letter(col)}{CAPACITY+2}'
        for dv in list(s.data_validations.dataValidation):
            if str(dv.sqref)==target:s.data_validations.dataValidation.remove(dv)
        validation(s,col,ref)
        s.column_dimensions['A'].hidden=True
    for n in range(3,CAPACITY+3):
        for col,snapshot,opcol in [(21,'AC','C'),(22,'AD','D')]:
            w['Events'].cell(n,col,f'=IF(B{n}="","",IF({snapshot}{n}<>"",{snapshot}{n},IFERROR(INDEX(Operations!${opcol}$3:${opcol}${CAPACITY+2},MATCH(C{n},Operations!$B$3:$B${CAPACITY+2},0)),"")))')
        # Contract principal policy is explicit; allocation is created by the central service only.
        w['Controls'].cell(n,2,f'=IF(Events!B{n}="","",IF(OR(Events!T{n}<=0,Events!U{n}="",Events!V{n}="",COUNTIF(Parties!$B$3:$B$1002,Events!D{n})<>1),"نوع، مبلغ یا طرف حساب نامعتبر",IF(AND(Events!C{n}="فروش",Events!K{n}<=0),"بهای تمام‌شده لازم است",IF(AND(Events!P{n}<>"",IFERROR(INDEX(Deals!$I$3:$I$1002,MATCH(Events!P{n},Deals!$B$3:$B$1002,0)),"")<>"{POLICY}"),"سیاست شراکت تعیین نشده",""))))')
        for col,ac in [(1,'A'),(2,'B'),(3,'C')]:w['Trial'].cell(n,col,f'=IF(Accounts!B{n}="","",Accounts!{ac}{n})')
        w['Trial'].cell(n,4,f'=IF(B{n}="",0,SUMIF(Journal!$D$3:$D$4002,B{n},Journal!$E$3:$E$4002))')
        w['Trial'].cell(n,5,f'=IF(B{n}="",0,SUMIF(Journal!$D$3:$D$4002,B{n},Journal!$F$3:$F$4002))')
        w['Trial'].cell(n,6,f'=D{n}-E{n}')
    w['Trial'].cell(CAPACITY+4,2,'کنترل توازن');w['Trial'].cell(CAPACITY+4,6,f'=SUM(D3:D{CAPACITY+2})-SUM(E3:E{CAPACITY+2})')
    for n,r in enumerate(rows(w,'Info'),3):
        if r['key']=='schema_version':put(w,'Info',{'value':'1.1'},n)

    # Complete all-ledger statements remain calculable without the Python service.
    def statement(name,entries):
        if name not in w:w.create_sheet(name)
        s=w[name];s.sheet_view.rightToLeft=True;s.freeze_panes='B3';s.column_dimensions['A'].width=48;s.column_dimensions['B'].width=28
        s.cell(1,1,'کل دفتر تا آخرین سند قطعی؛ همه مبالغ ریال. گزارش دوره‌ای در داشبورد.');s.cell(2,1,'عنوان');s.cell(2,2,'مبلغ ریال')
        for row,(label,formula) in enumerate(entries,3):s.cell(row,1,label);s.cell(row,2,formula).number_format='#,##0;[Red](#,##0)'
        for c in s[2]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='123D33')
    statement('ProfitLoss',[
        ('درآمدها','= -SUMIF(Trial!$C$3:$C$1002,"revenue",Trial!$F$3:$F$1002)'),
        ('بهای تمام‌شده فروش','=SUMIF(Trial!$B$3:$B$1002,"بهای تمام‌شده",Trial!$F$3:$F$1002)'),
        ('سایر هزینه‌ها و سهم سود شریک','=SUMIF(Trial!$C$3:$C$1002,"expense",Trial!$F$3:$F$1002)-B4'),
        ('کل هزینه‌ها','=B4+B5'),('سود/زیان خالص پس از تخصیص','=B3-B6')])
    statement('BalanceSheet',[
        ('دارایی‌ها','=SUMIF(Trial!$C$3:$C$1002,"asset",Trial!$F$3:$F$1002)'),
        ('بدهی‌ها','=-SUMIF(Trial!$C$3:$C$1002,"liability",Trial!$F$3:$F$1002)'),
        ('سرمایه','=-SUMIF(Trial!$C$3:$C$1002,"equity",Trial!$F$3:$F$1002)'),
        ('سود/زیان انباشته همین دفتر','=ProfitLoss!B7'),
        ('اختلاف تراز (باید صفر باشد)','=B3-B4-B5-B6')])
    for n,r in enumerate(rows(w,'Guide'),3):
        if r['topic']=='کنترل':put(w,'Guide',{'instruction':'اکسل مستقل نقش و قفل اجرایی ندارد. خرید هزینه دوره نیست. سود/زیان و تراز کل دفتر در ProfitLoss و BalanceSheet است. مدل اصیل/تقسیم سود فقط با قرارداد تأییدشده؛ تخصیص و قفل دوره را از مرکز انجام دهید. همزمان با سرویس، Excel را ویرایش نکنید.'},n)

    from app.integration import install as install_movements
    install_movements(w)
