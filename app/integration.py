"""Canonical physical movements and source-bank review. No implicit sale or opening balance."""
from collections import defaultdict
from decimal import Decimal
from openpyxl.styles import Font,PatternFill
from openpyxl.workbook.defined_name import DefinedName
from app import domain as d
from app.workbook import SCHEMAS,CAPACITY,rows,put,validation

# Physical quantities are not ownership valuation or profit allocation.
MOVEMENTS={
 'ورود':(1,0,False,'بار'),'خروج':(-1,0,False,'بار'),'انتقال':(0,0,True,'بار'),
 'خرید مرکبات':(1,0,False,'بار'),'فروش':(-1,0,False,'بار'),
 'مرجوعی خرید':(-1,0,False,'بار'),'مرجوعی فروش':(1,0,False,'بار'),
 'خرید شراکتی':(1,0,False,'بار'),'فروش شراکتی':(-1,0,False,'بار'),
 'ورود شراکتی':(1,0,False,'بار'),'خروج شراکتی':(-1,0,False,'بار'),
 'انتقال شراکتی':(0,0,True,'بار'),'انتقال به سورتینگ':(0,0,True,'بار'),
 'خروج از سورتینگ':(0,0,True,'بار'),'انتقال به سردخانه':(0,0,True,'بار'),
 'خروج از سردخانه':(0,0,True,'بار'),'خروج نهایی':(-1,0,False,'بار'),
 'برگشت بار':(1,0,False,'بار'),'ضایعات':(-1,0,False,'بار'),
 'خروج سبد امانت':(0,1,False,'سبد'),'ورود سبد خالی':(0,-1,False,'سبد'),
 'خروج سبد':(0,1,False,'سبد'),'ورود سبد':(0,-1,False,'سبد')}
SPECIAL={
 'انعام مصطفی':('هزینه انعام','حساب‌های پرداختنی','X001','انعام مصطفی'),
 'هزینه باسکول احمد زاهدی':('هزینه خدمات باسکول','حساب‌های پرداختنی','X002','احمد زاهدی'),
 'هزینه باسکول احمد موسویان':('هزینه خدمات باسکول','حساب‌های پرداختنی','X020','احمد موسویان'),
 'درآمد باسکول':('حساب‌های دریافتنی','درآمد خدمات باسکول',None,None)}
EXTRA=[('6100','کارمزد بانکی','expense'),('6110','هزینه انعام','expense'),('6120','هزینه خدمات باسکول','expense'),('4020','درآمد خدمات باسکول','revenue'),('1300','واسط انتقال بین بانک‌ها','asset'),('2300','تسهیلات مالی','liability'),('1250','اسناد دریافتنی','asset'),('2200','اسناد پرداختنی','liability')]
BANK_KINDS={'دریافت','پرداخت','کارمزد بانکی','برگشت کارمزد بانکی'}
NEW_SHEETS=['WeighOps','BankStatements','SourceRows','Dimensions','ReferenceMap','PhysicalStock','BasketCustody','Currencies','Settings']

def net(r):
    return d.net_weight(r.get('gross'),r.get('count'),r.get('tare'),r.get('loss') or 0,r.get('waste') or 0,5 if r.get('round_base') in [None,''] else r['round_base'])

def install(w):
    for sn in NEW_SHEETS:
        if sn not in w:
            s=w.create_sheet(sn);s.append(SCHEMAS[sn]);s.append([__import__('app.workbook',fromlist=['FA']).FA.get(k,k) for k in SCHEMAS[sn]]);s.row_dimensions[1].hidden=True;s.sheet_view.rightToLeft=True;s.freeze_panes='D3'
            s.auto_filter.ref=f'A2:T{CAPACITY+2}'
            for c in s[2]:c.fill=PatternFill('solid',fgColor='123D33');c.font=Font(bold=True,color='FFFFFF')
            for c in s[2]:s.column_dimensions[c.column_letter].width=25
            s.column_dimensions['A'].hidden=True
    for sn in ['Weigh','Parties','Products']:
        for n,k in enumerate(SCHEMAS[sn],1):
            w[sn].cell(1,n,k)
            if w[sn].cell(2,n).value is None:w[sn].cell(2,n,__import__('app.workbook',fromlist=['FA']).FA.get(k,k))
    if not rows(w,'WeighOps'):
        for n,(name,(sign,custody,route,mode)) in enumerate(MOVEMENTS.items()):put(w,'WeighOps',{'id':'WM'+str(n),'name':name,'stock_sign':sign,'custody_sign':custody,'route':'بله' if route else 'خیر','mode':mode})
        for n,name in enumerate(SPECIAL):put(w,'WeighOps',{'id':'WF'+str(n),'name':name,'stock_sign':0,'custody_sign':0,'route':'خیر','mode':'مالی'})
    from app.extensions import CATEGORIES
    names={x['name'] for x in rows(w,'Accounts')}
    for code,name,cat in EXTRA:
        if name not in names:put(w,'Accounts',{'id':code,'name':name,'category':cat,'group':CATEGORIES[cat],'active':'بله','note':'تفکیک جریان واقعی از تسویه'})
    ops={x['name'] for x in rows(w,'Operations')}
    for name,pair in {**{k:v[:2] for k,v in SPECIAL.items()},'کارمزد بانکی':('کارمزد بانکی','بانک'),'برگشت کارمزد بانکی':('بانک','کارمزد بانکی'),'انتقال بانکی خروج':('واسط انتقال بین بانک‌ها','بانک'),'انتقال بانکی ورود':('بانک','واسط انتقال بین بانک‌ها'),'دریافت اصل وام':('بانک','تسهیلات مالی'),'بازپرداخت اصل وام':('تسهیلات مالی','بانک'),'برداشت مالک':('سرمایه','بانک'),'پاس چک پرداختی':('اسناد پرداختنی','بانک'),'وصول چک دریافتی':('بانک','اسناد دریافتنی')}.items():
        if name not in ops:put(w,'Operations',{'id':'financial-'+name,'name':name,'debit':pair[0],'credit':pair[1],'active':'بله','note':'تعهد از تسویه جداست'})
    w.defined_names.add(DefinedName('WeighOpsNames',attr_text=f"'WeighOps'!$B$3:INDEX('WeighOps'!$B$3:$B${CAPACITY+2},MAX(1,COUNTA('WeighOps'!$B$3:$B${CAPACITY+2})))"))
    for sheet,col,ref in [('Weigh',3,'WeighOpsNames'),('Weigh',21,'StoresNames'),('BankStatements',9,'PartiesNames'),('BankStatements',3,'BanksNames')]:
        target=__import__('openpyxl.utils',fromlist=['get_column_letter']).get_column_letter(col)
        for dv in list(w[sheet].data_validations.dataValidation):
            if str(dv.sqref)==f'{target}3:{target}{CAPACITY+2}':w[sheet].data_validations.dataValidation.remove(dv)
        validation(w[sheet],col,ref)
    for r in range(3,CAPACITY+3):
        for col,opcol in [(25,'C'),(26,'D')]:
            if w['Weigh'].cell(r,col).value is None:w['Weigh'].cell(r,col,f'=IF(C{r}="","",IFERROR(INDEX(WeighOps!${opcol}$3:${opcol}$1002,MATCH(C{r},WeighOps!$B$3:$B$1002,0)),0))')
        # Mandatory tare, but basket-only and financial rows carry no fruit weight.
        w['Weigh'].cell(r,13,f'=IF(B{r}="","",IF(IFERROR(INDEX(WeighOps!$F$3:$F$1002,MATCH(C{r},WeighOps!$B$3:$B$1002,0)),"بار")<>"بار",0,IF(OR(I{r}="",H{r}="",J{r}=""),"تارای نامشخص",IF((I{r}-H{r}*J{r})*(1-K{r}/100)-L{r}<0,"وزن منفی",IF(AND(X{r}<>"",X{r}=0),(I{r}-H{r}*J{r})*(1-K{r}/100)-L{r},FLOOR((I{r}-H{r}*J{r})*(1-K{r}/100)-L{r},IF(X{r}="",5,X{r})))))))')
        if w['Weigh'].cell(r,10).value is None:w['Weigh'].cell(r,10,f'=IF(G{r}="","",IFERROR(IF(INDEX(Baskets!$C$3:$C$1002,MATCH(G{r},Baskets!$B$3:$B$1002,0))="","",INDEX(Baskets!$C$3:$C$1002,MATCH(G{r},Baskets!$B$3:$B$1002,0))),""))')
    for n,x in enumerate(rows(w,'Info'),3):
        if x['key']=='schema_version':put(w,'Info',{'value':'1.2'},n)

def physical(data,start=None,end=None,party=None):
    balances=defaultdict(Decimal);custody=defaultdict(int);movements=[]
    for r in data['Weigh']:
        if (end and int(r['date'])>end) or (party and r['party']!=party):continue
        op=MOVEMENTS.get(r['operation'])
        if not op:continue
        sign,cs,route,mode=op
        try:qty=net(r) if mode=='بار' else Decimal(0)
        except d.RuleError:continue
        k=(r['party'],r['product'],r['basket'],r.get('deal') or '')
        if route:
            balances[k+(r['store'],)]-=qty;balances[k+(r.get('destination') or 'مقصد نامعلوم',)]+=qty
        else:balances[k+(r['store'],)]+=sign*qty
        baskets=int(Decimal(str(r.get('basket_out') or 0)))-int(Decimal(str(r.get('basket_return') or 0)))
        if mode=='سبد':baskets=cs*int(Decimal(str(r['count'])))
        custody[(r['party'],r['basket'])]+=baskets
        if not start or int(r['date'])>=start:movements.append({**r,'net':str(qty),'custody_change':baskets})
    return {'balances':[{'party':k[0],'product':k[1],'basket':k[2],'deal':k[3],'store':k[4],'qty':str(v)} for k,v in balances.items()],'custody':[{'party':k[0],'basket':k[1],'count':v} for k,v in custody.items()],'movements':movements,'note':'موجودی فیزیکی؛ با موجودی مالی یا سود شراکت یکی نیست. منفی یعنی ورودی/افتتاحیه یا انتقال ناقص.'}

def bank_rows_report(data,start=None,end=None,party=None):
    records=[r for r in data.get('BankStatements',[]) if (not start or int(r['date'])>=start) and (not end or int(r['date'])<=end) and (not party or r.get('party')==party)]
    return {'rows':records,'counts':dict(__import__('collections').Counter(r['status'] for r in records)),'note':'اصل صورت‌حساب و وضعیت تطبیق؛ فقط ردیف دارای سند متصل در مانده دفترکل اثر دارد. مانده منبع، مانده افتتاحیه تأییدشده نیست.'}


def sync_physical(w):
    """Existing movement dimensions only; no cartesian product or valued inventory assumption."""
    import hashlib
    dimensions=[];custody=[]
    for r in rows(w,'Weigh'):
        if r['operation'] not in MOVEMENTS:continue
        for store in [r.get('store'),r.get('destination')]:
            if store:
                k=(r.get('party') or '',r.get('product') or '',store,r.get('basket') or '',r.get('deal') or '')
                if k not in dimensions:dimensions.append(k)
        k=(r.get('party') or '',r.get('basket') or '')
        if k[1] and k not in custody:custody.append(k)
    for n,k in enumerate(dimensions,3):
        if n>CAPACITY+2:raise d.RuleError('ظرفیت ابعاد فیزیکی تکمیل شده')
        put(w,'PhysicalStock',dict(zip(['id','party','product','store','basket','deal'],['physical-'+hashlib.sha256(str(k).encode()).hexdigest()[:16],*k])),n)
        crit=f',Weigh!$D$3:$D$1002,B{n},Weigh!$E$3:$E$1002,C{n},Weigh!$G$3:$G$1002,E{n},Weigh!$P$3:$P$1002,F{n}'
        qty=f'SUMIFS(Weigh!$M$3:$M$1002,Weigh!$F$3:$F$1002,D{n},Weigh!$Y$3:$Y$1002,1{crit})-SUMIFS(Weigh!$M$3:$M$1002,Weigh!$F$3:$F$1002,D{n},Weigh!$Y$3:$Y$1002,-1{crit})+SUMIFS(Weigh!$M$3:$M$1002,Weigh!$U$3:$U$1002,D{n}{crit})-SUMIFS(Weigh!$M$3:$M$1002,Weigh!$F$3:$F$1002,D{n},Weigh!$U$3:$U$1002,"<>"{crit})'
        w['PhysicalStock'].cell(n,7,'='+qty)
    for n,k in enumerate(custody,3):
        put(w,'BasketCustody',{'id':'custody-'+str(n),'party':k[0],'basket':k[1]},n)
        w['BasketCustody'].cell(n,4,f'=SUMIFS(Weigh!$V$3:$V$1002,Weigh!$D$3:$D$1002,B{n},Weigh!$G$3:$G$1002,C{n})-SUMIFS(Weigh!$W$3:$W$1002,Weigh!$D$3:$D$1002,B{n},Weigh!$G$3:$G$1002,C{n})+SUMPRODUCT((Weigh!$D$3:$D$1002=B{n})*(Weigh!$G$3:$G$1002=C{n})*IFERROR(Weigh!$Z$3:$Z$1002*Weigh!$H$3:$H$1002,0))')
