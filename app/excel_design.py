"""Native Excel presentation: row semantics, linked settings, charts and conceptual metadata.
Base monetary input is always IRR; display conversions are separate formula columns.
"""
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule,DataBarRule
from openpyxl.chart import BarChart,DoughnutChart,Reference
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils import get_column_letter as L
from app.workbook import SCHEMAS,CAPACITY,FA,rows,put,validation

COLORS={'in':'EAF4ED','out':'EDF3FA','transfer':'F0EDFA','basket':'F2F4E8','return':'FFF4E4','fee':'F9EEEE','income':'EBF6F3'}
TITLES={'Weigh':'باسکول | جریان دقیق محموله','BankStatements':'خزانه | اصل، تطبیق، تسویه','Events':'دفتر رویدادها | تعهد تا تسویه','Trial':'تراز | تصویر متوازن دفتر','PhysicalStock':'موجودی فیزیکی | مستقل از ارزش‌گذاری','BasketCustody':'سبد امانی | تعهد قابل پیگیری','Settings':'مرکز تنظیمات | یک مبنا، نمایش یکپارچه','Currencies':'ارزها | هر واحد ارز برابر چند ریال'}
CONCEPTS={'party':'بعد شخص در گردش تعهد، تسویه و گزارش مانده؛ نام مرجع به شناسه پایدار اشخاص متصل است.', 'product':'بعد محصول در اتصال قبض، خرید/فروش و موجودی؛ قلم نامعلوم با محصول دیگر ادغام نمی‌شود.','basket':'مرجع وزن ظرف و تفکیک گردش امانی؛ تعداد × تارای هر ظرف از وزن ناخالص کسر می‌شود.','tare':'تارای هر سبد به کیلوگرم؛ مقدار ردیف، مبنای تاریخی محاسبه است. تغییر تعریف سبد نباید مقدار قطعی قبلی را عوض کند.','net':'خالص = (ناخالص − تعداد × تارا) × (۱ − افت/۱۰۰) − ضایعات؛ صفر بودن مبنای گردکردن یعنی نتیجه دقیق و ۵ یعنی مضرب پایین‌تر ۵.','source_weigh':'رابطه قبض با سند خرید/فروش؛ اتصال فعال یکتا مانع دوباره‌شماری مالی همان قبض است.','deal':'بعد قرارداد؛ حرکت فیزیکی، سهم اقتصادی و تقسیم سود دوره مفاهیم مجزا هستند. قرارداد بازبینی‌نشده مبنای ثبت مالی خودکار نیست.','deposit':'گردش افزایشی بانک به ریال؛ دریافت لزوماً درآمد نیست. تسویه طلب، انتقال داخلی و وام ماهیت‌های متفاوت دارند.','withdrawal':'گردش کاهشی بانک به ریال؛ پرداخت لزوماً هزینه نیست. تسویه بدهی از ایجاد هزینه جداست.','input_amount':'مبلغ پایه ریال؛ ستون نمایشی ارز، اصل مبلغ و ثبت دوبل را تغییر نمی‌دهد.','status':'وضعیت اتصال/کنترل ردیف؛ صورت‌حساب منبع با سند قطعی دفترکل یکسان نیست.','reference':'کلید ارتباط عملیاتی قبض، بانک یا سند؛ یکتایی مرجع همراه با منبع مانع ثبت چندباره می‌شود.','round_base':'صفر: بدون گردکردن وزن؛ عدد مثبت: گردکردن رو به پایین به مضرب آن.','rial_per_unit':'تعداد ریال معادل یک واحد ارز؛ ریال=۱ و تومان=۱۰. نرخ خالی به معنی نامعلوم است، نه صفر یا نرخ ساختگی.','correction':'شرح تغییر قابل اثبات؛ اصل مقادیر در SourceRows و raw_json حفظ می‌شود.','balance':'مانده این گزارش؛ مانده منبع بانک تأیید افتتاحیه مالی نیست.','gross':'وزن ناخالص باسکول به کیلوگرم؛ نبود اندازه‌گیری با صفر تفاوت دارد.','stock_sign':'ضریب حرکت فیزیکی؛ انتقال به دو محل اثر معکوس دارد و جمع کل را تغییر نمی‌دهد.','custody_sign':'مثبت: سبد نزد طرف حساب؛ منفی: برگشت یا بدهی معکوس امانی.','share':'سهم تاریخی ردیف؛ قرارداد نامطمئن نباید سهم پیش‌فرضِ ظاهراً قطعی ایجاد کند.'}
MONEY={'Events':['input_amount','cost','effective_amount'],'BankStatements':['deposit','withdrawal','balance'],'Journal':['debit','credit'],'Trial':['debit','credit','balance'],'Checks':['amount']}


def apply(w):
    for sn,fields in SCHEMAS.items():
        if sn not in w:continue
        for col,key in enumerate(fields,1):
            w[sn].cell(2,col,FA.get(key,w[sn].cell(2,col).value or key))
            if key in ['party_id','product_id','basket_id','bank_id','store_id','deal_id','source_sha']:
                w[sn].column_dimensions[L(col)].hidden=True
    for name in MONEY:w[name].conditional_formatting._cf_rules.clear()
    # Settings are user-owned values. Reapplying presentation never resets them.
    defaults=[('organization','مازندشت','نام مجموعه در عناوین گزارش'),('slogan','داده روشن؛ تصمیم مطمئن.','عبارت برند در صفحات مدیریتی'),('footer','از محموله تا مانده؛ یک مسیر قابل‌ردیابی.','عبارت انتهای گزارش'),('report_currency','ریال','واحد نمایش پول؛ مبالغ پایه همچنان ریال‌اند'),('display_decimals',2,'تعداد اعشار نمایش ارزی؛ اصل ریال تغییر نمی‌کند')]
    existing={r['key'] for r in rows(w,'Settings')}
    for k,v,n in defaults:
        if k not in existing:put(w,'Settings',{'key':k,'value':v,'note':n})
    if not rows(w,'Currencies'):
        for code,name,rate in [('IRR','ریال',1),('IRT','تومان',10),('USD','دلار آمریکا',None),('EUR','یورو',None)]:put(w,'Currencies',{'id':code,'name':name,'rial_per_unit':rate})
    for n in range(3,CAPACITY+3):
        if w['Currencies'].cell(n,1).value is None:w['Currencies'].cell(n,1,'CUR-'+str(n-2).zfill(6))
    from openpyxl.worksheet.datavalidation import DataValidation
    rate_validation=DataValidation(type='decimal',operator='greaterThan',formula1='0',allow_blank=True);rate_validation.showErrorMessage=True;rate_validation.error='نرخ باید مثبت باشد یا خالی بماند.'
    w['Currencies'].add_data_validation(rate_validation);rate_validation.add('C3:C1002')
    positions={r['key']:n for n,r in __import__('app.workbook',fromlist=['indexed_rows']).indexed_rows(w,'Settings')}
    for name,k in [('CompanyTitle','organization'),('BrandSlogan','slogan'),('ReportCurrency','report_currency'),('ReportDecimals','display_decimals')]:w.defined_names.add(DefinedName(name,attr_text=f"'Settings'!$B${positions[k]}"))
    w.defined_names.add(DefinedName('CurrencyNames',attr_text="'Currencies'!$B$3:INDEX('Currencies'!$B$3:$B$1002,MAX(1,COUNTA('Currencies'!$B$3:$B$1002)))"))
    precision_validation=DataValidation(type='whole',operator='between',formula1=0,formula2=8);precision_validation.showErrorMessage=True;precision_validation.error='تعداد اعشار از صفر تا هشت است.'
    w['Settings'].add_data_validation(precision_validation);precision_validation.add('B'+str(positions['display_decimals']))
    target='B'+str(positions['report_currency'])
    for existing_dv in list(w['Settings'].data_validations.dataValidation):
        if str(existing_dv.sqref)==target:w['Settings'].data_validations.dataValidation.remove(existing_dv)
    dv=__import__('openpyxl.worksheet.datavalidation',fromlist=['DataValidation']).DataValidation(type='list',formula1='=CurrencyNames');w['Settings'].add_data_validation(dv);dv.add(target)
    for name in ['Dashboard','Help']:
        if name in w:w.remove(w[name])
    dash=w.create_sheet('Dashboard',0);dash.sheet_view.rightToLeft=True;dash.sheet_view.showGridLines=False;dash.freeze_panes='B7'
    for c in range(1,15):dash.column_dimensions[L(c)].width=15
    for span,value in [('A1:N2','=CompanyTitle & " | نبض مجموعه"'),('A3:N3','=BrandSlogan'),('A5:N5','داشبورد عملیات و کیفیت داده | گردش منبع با مانده قطعی دفتر متفاوت است')]:
        dash.merge_cells(span);c=dash[span.split(':')[0]];c.value=value;c.font=Font(name='Tahoma',size=20 if '1:' in span else 11,bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='173F35');c.alignment=Alignment(horizontal='right',vertical='center')
    stats=[('ردیف‌های باسکول','=COUNT(Weigh!B3:B1002)'),('ردیف‌های بانک','=COUNTA(BankStatements!A3:A1002)'),('سند مالی قطعی','=COUNTIF(Events!L3:L1002,"قطعی")'),('تکرار صورت‌حساب','=COUNTIF(BankStatements!L3:L1002,"تکرار منبع")'),('شخص نامعلوم باسکول','=COUNTIFS(Weigh!B3:B1002,">0",Weigh!D3:D1002,"")'),('محصول نامعلوم باسکول','=COUNTIFS(Weigh!B3:B1002,">0",Weigh!E3:E1002,"")')]
    for i,(label,formula) in enumerate(stats):
        col=1+(i%3)*5;row=7+(i//3)*4;dash.merge_cells(start_row=row,start_column=col,end_row=row,end_column=col+3);dash.cell(row,col,label);dash.cell(row+1,col,formula).font=Font(name='Tahoma',bold=True,size=24,color='173F35')
    dash['A16']='بانک';dash['B16']='واریز منبع';dash['C16']='برداشت منبع';dash['D16']='ارز نمایش';dash['E16']='واریز نمایشی';dash['F16']='برداشت نمایشی'
    banknames=[x['name'] for x in rows(w,'Banks') if 'تعریف نشده' not in x['name']]
    for n,name in enumerate(banknames,17):
        dash.cell(n,1,name)
        for col,sourcecol in [(2,'F'),(3,'G')]:dash.cell(n,col,f'=SUMIFS(BankStatements!${sourcecol}$3:${sourcecol}$1002,BankStatements!$C$3:$C$1002,A{n},BankStatements!$L$3:$L$1002,"<>تکرار منبع")')
        dash.cell(n,4,'=ReportCurrency')
        for c,base in [(5,'B'),(6,'C')]:dash.cell(n,c,f'=IF(ReportFactor>0,ROUND({base}{n}/ReportFactor,ReportDecimals),"نرخ تعریف نشده")')
    chart=BarChart();chart.type='col';chart.title='گردش بانک‌ها | بدون دوباره‌شماری منبع';chart.y_axis.title='ارز انتخابی';chart.add_data(Reference(dash,min_col=5,max_col=6,min_row=16,max_row=max(17,16+len(banknames))),titles_from_data=True);chart.set_categories(Reference(dash,min_col=1,min_row=17,max_row=max(17,16+len(banknames))));chart.width=22;chart.height=10;dash.add_chart(chart,'H16')
    dash['A29']='عملیات باسکول';dash['B29']='تعداد ردیف'
    for n,op in enumerate([r['name'] for r in rows(w,'WeighOps')],30):dash.cell(n,1,op);dash.cell(n,2,f'=COUNTIF(Weigh!$C$3:$C$1002,A{n})')
    chart2=BarChart();chart2.type='bar';chart2.title='ترکیب حرکت‌ها | ورود، خروج و انتقال';chart2.add_data(Reference(dash,min_col=2,min_row=29,max_row=29+len(rows(w,'WeighOps'))),titles_from_data=True);chart2.set_categories(Reference(dash,min_col=1,min_row=30,max_row=29+len(rows(w,'WeighOps'))));chart2.width=22;chart2.height=17;dash.add_chart(chart2,'H37')
    dash['A60']='تنظیم ارز';dash['B60']='=ReportCurrency';dash['A61']='ریال معادل یک واحد';dash['B61']='=IFERROR(INDEX(Currencies!$C$3:$C$1002,MATCH(ReportCurrency,Currencies!$B$3:$B$1002,0)),0)';w.defined_names.add(DefinedName('ReportFactor',attr_text="'Dashboard'!$B$61"))
    for n,sn in enumerate(['Weigh','BankStatements','PhysicalStock','BasketCustody','Events','Settings','Currencies','Help'],64):dash.cell(n,1,TITLES.get(sn,sn));dash.cell(n,1).hyperlink=f"#'{sn}'!A1";dash.cell(n,1).style='Hyperlink'
    help_sheet=w.create_sheet('Help');help_sheet.sheet_view.rightToLeft=True;help_sheet.sheet_view.showGridLines=False;help_sheet.column_dimensions['A'].width=8;help_sheet.column_dimensions['B'].width=115
    help_sheet.append(['بخش','مازندشت | مرجع کاربری، روابط و توسعه']);help_sheet.append(['مبنا','ریال، ارز پایه و مرجع ذخیره‌سازی است. تبدیل نمایش، ثبت دوبل یا ورودی‌های قبلی را عوض نمی‌کند.'])
    for sn in SCHEMAS:
        if sn in ['Audit','Imports','SourceRows']:continue
        s=w[sn];s.sheet_view.showGridLines=False;s.sheet_view.zoomScale=85;s.sheet_view.rightToLeft=True;s.freeze_panes='D3';s.sheet_properties.pageSetUpPr.fitToPage=True;s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;s.print_title_rows='2:2';s.sheet_properties.tabColor='537D70' if sn in ['Weigh','PhysicalStock','BasketCustody'] else '8196AA'
        s.oddHeader.center.text='&Bمازندشت | '+TITLES.get(sn,'عملیات یکپارچه')+'&B';s.oddHeader.center.size=11;s.oddHeader.center.font='Tahoma,Bold';s.oddFooter.right.text='از محموله تا مانده؛ یک مسیر قابل‌ردیابی.';s.oddFooter.left.text='صفحه &P از &N';s.sheet_properties.outlinePr.summaryRight=False
        for i,k in enumerate(SCHEMAS[sn],1):
            c=s.cell(2,i);c.value=FA.get(k,k);c.font=Font(name='Tahoma',size=10,bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='254F44');c.alignment=Alignment(horizontal='center',wrap_text=True,vertical='center')
            concept=CONCEPTS.get(k,f'بعد «{FA.get(k,k)}» در {TITLES.get(sn,sn)}؛ رابطه‌ها با شناسه پایدار و مقدار پایه حفظ می‌شوند. شرح فنی و گردش داده در Help آمده است.')
            c.comment=Comment(concept,'مازندشت | معماری داده');c.comment.width=400;c.comment.height=120
            s.column_dimensions[L(i)].width=24 if k not in ['note','issues','correction'] else 45
            if k in ['source_sha','raw_json','payload','party_code','stock_sign','custody_sign'] or k.endswith('_id'):s.column_dimensions[L(i)].hidden=True
            for n in range(3,CAPACITY+3):
                cell=s.cell(n,i);cell.font=Font(name='Tahoma',size=10,color='253B36');cell.fill=PatternFill(fill_type=None);cell.alignment=Alignment(vertical='center',horizontal='right')
                if k in ['gross','net','tare','waste','qty']:cell.number_format='#,##0.000;[Red](#,##0.000);–'
                elif k in ['deposit','withdrawal','balance','amount','input_amount','effective_amount','debit','credit','cost','rate']:cell.number_format='#,##0;[Red](#,##0);–'
        s.row_dimensions[2].height=34
        for dv in s.data_validations.dataValidation:
            dv.showInputMessage=True;dv.promptTitle='رابطه مرجع';dv.prompt='نام این بعد به تعریف پایه متصل است؛ تغییر نام یا کلید، روی ارتباط گزارش‌ها اثر دارد. توضیح کامل در Help.'
        help_sheet.append([sn,TITLES.get(sn,sn)+' — '+(' | '.join(FA.get(k,k) for k in SCHEMAS[sn]))])
    for sn,fields in MONEY.items():
        s=w[sn]
        for field in fields:
            col=SCHEMAS[sn].index(field)+1;tag='fx_'+field
            target=next((c.column for c in s[1] if c.value==tag),None) or s.max_column+1;s.cell(1,target,tag);s.cell(2,target,FA.get(field,field)+' — ارز نمایشی').font=Font(name='Tahoma',bold=True,color='FFFFFF');s.cell(2,target).fill=PatternFill('solid',fgColor='537D70');s.column_dimensions[L(target)].width=27
            for n in range(3,CAPACITY+3):s.cell(n,target,f'=IF(B{n}="","",IF(ReportFactor>0,ROUND({L(col)}{n}/ReportFactor,ReportDecimals),"نرخ تعریف نشده"))').number_format='#,##0.00;[Red](#,##0.00);–'
    for sn in ['ProfitLoss','BalanceSheet']:
        s=w[sn];s.cell(2,3,'مبلغ — ارز نمایشی')
        for n in range(3,8):s.cell(n,3,f'=IF(ReportFactor>0,ROUND(B{n}/ReportFactor,ReportDecimals),"نرخ تعریف نشده")').number_format='#,##0.00;[Red](#,##0.00);–'
    ws=w['Weigh'];ws.conditional_formatting._cf_rules.clear();end=L(max(len(SCHEMAS['Weigh']),ws.max_column))
    from app.integration import MOVEMENTS,SPECIAL
    for name in [*MOVEMENTS,*SPECIAL]:
        color=COLORS['transfer'] if any(k in name for k in ['انتقال','سورتینگ','سردخانه']) else COLORS['basket'] if 'سبد' in name else COLORS['return'] if 'مرجوعی' in name or 'برگشت' in name else COLORS['fee'] if 'هزینه' in name or 'انعام' in name else COLORS['income'] if 'درآمد' in name else COLORS['in'] if name.startswith(('خرید','ورود')) else COLORS['out']
        ws.conditional_formatting.add(f'A3:{end}{CAPACITY+2}',FormulaRule(formula=[f'$C3="{name}"'],fill=PatternFill('solid',fgColor=color)))
    bs=w['BankStatements'];bs.conditional_formatting._cf_rules.clear();bs.conditional_formatting.add(f'A3:{L(bs.max_column)}{CAPACITY+2}',FormulaRule(formula=['$F3>0'],fill=PatternFill('solid',fgColor='EEF0F2')))
    # Native Events bank receipts use a known operation, not the sign of an arbitrary expense.
    w['Events'].conditional_formatting._cf_rules.clear();w['Events'].conditional_formatting.add(f'A3:{L(w["Events"].max_column)}{CAPACITY+2}',FormulaRule(formula=['OR($C3="دریافت",$C3="سرمایه",$C3="برگشت کارمزد بانکی")'],fill=PatternFill('solid',fgColor='EEF0F2')))
    from openpyxl.formatting.rule import Rule
    from openpyxl.styles.differential import DifferentialStyle
    from openpyxl.styles.numbers import NumberFormat
    for sn in MONEY:
        sheet=w[sn]
        for c in sheet[1]:
            if str(c.value).startswith('fx_'):
                for precision in range(9):
                    code='#,##0'+('.'+'0'*precision if precision else '')
                    rule=Rule(type='expression',dxf=DifferentialStyle(numFmt=NumberFormat(numFmtId=180+precision,formatCode=code)),formula=[f'ReportDecimals={precision}'])
                    sheet.conditional_formatting.add(f'{c.column_letter}3:{c.column_letter}{CAPACITY+2}',rule)
    for s in [dash,help_sheet]:
        for row in s:
            for c in row:
                if not c.font.bold:c.font=Font(name='Tahoma',size=11,color='253B36')
                c.alignment=Alignment(horizontal='right',vertical='top',wrap_text=True)
    from pathlib import Path
    guide=Path(__file__).resolve().parents[1]/'docs/SYSTEM_HELP_FA.md'
    if guide.exists():
        for line in guide.read_text().splitlines():
            if line.strip():help_sheet.append(['مرجع جامع',line.lstrip('# ').replace('**','')])
    for n in range(3,help_sheet.max_row+1):
        help_sheet.cell(n,2).alignment=Alignment(horizontal='right',vertical='top',wrap_text=True)
        help_sheet.cell(n,2).font=Font(name='Tahoma',size=11,color='253B36')
        help_sheet.row_dimensions[n].height=min(360,max(28,18*((len(str(help_sheet.cell(n,2).value or ''))+89)//90)))
    w['Guide'].sheet_state='hidden';w['Settings'].column_dimensions['A'].hidden=False
    w.active=0
