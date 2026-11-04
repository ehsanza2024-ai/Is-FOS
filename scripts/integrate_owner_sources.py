"""Owner-approved intake into a NEW canonical workbook; originals and existing ledgers refused.
No independent Sherakati data is read or imported. Source bank rows stay pending financial classification.
"""
import argparse,hashlib,json
from pathlib import Path
from collections import Counter
from decimal import Decimal
from app import domain as d
from app.store import Store,uid
from app.workbook import rows,put,indexed_rows
from app.source_review import reference_data,weigh_review,bank_statement,source,key,digest,raw
from app.bank_reconcile import reconcile
from app.integration import MOVEMENTS,SPECIAL
from openpyxl import load_workbook

def integrate(folder,keshavarzi,legacy_info,output):
    folder=Path(folder);output=Path(output);refs=reference_data(folder/'Info.xlsx');weigh=weigh_review(folder/'Weigh.xlsx',refs)
    bank_inputs=[(folder/'پرینت حساب صادرات 9009.xlsx','صادرات 9009'),(folder/'پرینت حساب صادرات 2006.xlsx','صادرات 2006'),(folder/'پرینت حساب مهر ایران.xlsx','مهر ایران'),(Path(keshavarzi),'کشاورزی')]
    banks=[]
    for path,bank in bank_inputs:
        b=bank_statement(path,refs['Parties'],bank,'IRR');b['reconciled'],b['reconciliation']=reconcile(b['records']);banks.append(b)
    expected={x['id'] for x in weigh}|{r['id'] for b in banks for r in b['records']}
    store=Store(output);state=store.read()
    if state.get('SourceRows'):
        if {r['id'] for r in state['SourceRows']}==expected and any(r['key']=='owner_policy_revision' and r['value']=='2026-11-05-all-weigh' for r in state['Info']):return store,{'idempotent':True,'weigh_rows':len(state['Weigh']),'bank_rows':len(state['BankStatements'])}
        raise d.RuleError('منابع با مهاجرت قبلی متفاوت‌اند؛ دفتر موجود بازنویسی نمی‌شود')
    if state['Events'] or state['Weigh'] or state['Parties'] or state.get('BankStatements'):raise d.RuleError('فقط دفتر تازه و خالی؛ جایگزینی دفتر نصب‌شده نیازمند مسیر مهاجرت جدا و تطبیق است')
    # Source default parameters, explicitly selected by owner; never inferred from basket capacity.
    old=load_workbook(legacy_info,read_only=True,data_only=False,keep_links=False);params={str(r[0]):r[2] for r in old['Params'].values if len(r)>2 and r[0] in ['P01','P02']}
    tare=d.decimal(params.get('P01'),'تارای قدیمی');purchase_loss=d.decimal(params.get('P02'),'افت خرید قدیمی')
    group_data={s:list(old[s].values) for s in ['Groups','MainGroups','SubGroups','WorkGroups','Accounts']};old.close();oldsource=source(legacy_info)
    mapped={};notes=[]
    with store.edit('مالک؛ انتخاب‌های تأییدشده ۱۴۰۵/۰۸/۱۴','owner.integrate.sources',state['revision']) as w:
        for sn in ['Parties','Baskets','Products','Stores','Banks']:
            mapped[sn]={};names=set()
            for x in refs[sn]:
                code=key(x.get('Code'));name=d.normalize(x.get('Name'));original_name=name
                if not code or not name:continue
                system_categories={'Asset':'asset','Liability':'liability','Expense':'expense','Revenue':'revenue','Equity':'equity'}
                if sn=='Parties' and x.get('Role') in system_categories:
                    category=system_categories[x['Role']]
                    chart=next((a for a in rows(w,'Accounts') if a['name']==name),None)
                    if not chart:
                        from app.extensions import CATEGORIES
                        put(w,'Accounts',{'id':'legacy-'+code,'name':name,'category':category,'group':CATEGORIES[category],'active':'بله','note':'سرفصل سیستمی منبع؛ شخص حقیقی نیست'})
                    put(w,'ReferenceMap',{'id':digest([sn,code]),'sheet':'Accounts','source_code':code,'name':name,'source_file':x['_source']['file'],'source_sha':x['_source']['sha256'],'source_row':x['_row'],'note':'تطبیق ماهیت سیستمی؛ اصل تعریف در منبع حفظ شده'})
                    continue
                if sn=='Parties' and code in ['X001','X002','X020']:name=next(v[3] for v in SPECIAL.values() if v[2]==code)
                if name in names:
                    suffix=d.normalize(x.get('Group') or x.get('Role') or 'تعریف هم‌نام');name=name+' — '+suffix
                    if name in names:name+=' ('+str(sum(v.startswith(name) for v in names)+1)+')'
                names.add(name);record={'id':sn+'-'+code,'name':name};mapped[sn][code]=name
                if sn=='Parties':record.update(code=code,role=d.normalize(x.get('Role')),active='بله' if x.get('Active')=='بله' else 'خیر',note=str(x.get('Note') or ''))
                if sn=='Products':record.update(group=x.get('Group'),note=x.get('Note'))
                if sn=='Baskets':record['tare']=x.get('Tare kg')
                put(w,sn,record)
                put(w,'ReferenceMap',{'id':digest([sn,code]),'sheet':sn,'source_code':code,'name':name,'source_file':x['_source']['file'],'source_sha':x['_source']['sha256'],'source_row':x['_row'],'note':json.dumps({k:v for k,v in x.items() if not k.startswith('_')},ensure_ascii=False)})
        # Master metadata dimensions are not automatically P&L ledger accounts.
        for n,r in enumerate(group_data['Groups'][6:],7):
            for i,v in enumerate(r):
                if v is None or str(v).startswith('='):continue
                parent=raw(group_data['Groups'][5][i]);kind='زیرماهیت شخص' if i<8 else str(parent)
                put(w,'Dimensions',{'id':digest(['matrix',i,n]),'name':d.normalize(v),'kind':kind,'parent':parent,'note':'INFO قدیمی؛ بعد گزارش‌دهی، نه ثبت خودکار مالی'})
        for sn in ['MainGroups','SubGroups','WorkGroups']:
            for n,r in enumerate(group_data[sn][6:],7):
                if not r[0] or not r[1] or str(r[1]).startswith('='):continue
                name=r[2] if sn=='SubGroups' else r[1]
                if not name:continue
                put(w,'Dimensions',{'id':str(r[0]),'name':name,'kind':sn,'parent':r[1] if sn=='SubGroups' else '', 'note':str(r[3] or '') if sn=='SubGroups' and len(r)>3 else str(r[2] or '') if len(r)>2 else ''})
        for source_row,r in enumerate(group_data['Accounts'][6:],7):
            if not r[0] or not r[3] or str(r[3]).startswith('='):continue
            code=d.normalize(r[0]).upper();p=next(((n,p) for n,p in indexed_rows(w,'Parties') if p.get('code')==code),None)
            if p:put(w,'Parties',{'nature':r[1],'subgroup':r[2]},p[0])
        defaultbasket='نوع سبد نامعلوم — تارای قاعده قدیمی';defaultstore='محل ثبت قدیمی — انبار نامشخص'
        put(w,'Baskets',{'id':'basket-legacy-tare','name':defaultbasket,'tare':str(tare)});put(w,'Stores',{'id':'store-legacy-unknown','name':defaultstore})
        # Literal product names may be quick-defined; an empty name remains unknown.
        for r in weigh:
            code=r.get('product_code')
            if code and code not in mapped['Products'] and not str(r['raw'].get('36') or '').startswith('Partner legacy!'):
                name=d.normalize(code);mapped['Products'][code]=name
                if name not in {x['name'] for x in rows(w,'Products')}:put(w,'Products',{'id':'literal-'+digest(name)[:20],'name':name})
        imported=[];excluded=[]
        for r in weigh:
            origin=str(r['raw'].get('36') or '')
            excluded_joint=False  # Latest owner instruction: every row already in Weigh, no separate SH import
            put(w,'SourceRows',{'id':r['id'],'source_file':r['source']['file'],'source_sha':r['source']['sha256'],'source_sheet':'Entry','source_row':r['source_row'],'payload':json.dumps(r['raw'],ensure_ascii=False),'status':'مستثنا طبق دستور مالک' if excluded_joint else 'واردشده به باسکول','reason':'فقط منبع مستقل شراکتی وارد نشود؛ همه ردیف‌های موجود باسکول حفظ شوند' if excluded_joint else ''})
            if excluded_joint:excluded.append(r['id']);continue
            if r['deal'] and r['deal'] not in {x['name'] for x in rows(w,'Deals')}:
                put(w,'Deals',{'id':'pending-'+r['deal'],'name':r['deal'],'partner':r.get('party_name') or '', 'share':'0','start':14050101,'end':14051229,'product':'','status':'نیاز به بازبینی','policy':'','note':'اصل مرجع فایل باسکول؛ هویت/سهم قرارداد تأیید نشده. صفر ذخیره‌شده سهم تأییدشده نیست.'})
            b=mapped['Baskets'].get(r.get('basket_code'),defaultbasket);basket=next(x for x in rows(w,'Baskets') if x['name']==b)
            t=r.get('tare_manual') if r.get('tare_manual') is not None else basket.get('tare')
            if t is None:raise d.RuleError('تارای واقعی تعریف‌شده موجود نیست؛ از قاعده دیگر برای سبد مشخص استفاده نمی‌شود')
            loss=Decimal(r['loss_fraction'])*100 if r.get('loss_fraction') is not None else purchase_loss if r['operation']=='خرید مرکبات' else Decimal(0)
            record={'id':r['id'],'date':d.date(r['date']),'operation':r['operation'],'party':mapped['Parties'].get(r['party_code'],''),'product':mapped['Products'].get(r['product_code'],''),'store':mapped['Stores'].get(r.get('source_store'),defaultstore),'basket':b,'destination':mapped['Stores'].get(r.get('destination_store'),''),'count':r['count'] if r['count'] is not None else '0','gross':r['gross'],'tare':str(t),'loss':str(loss),'waste':r['waste'] or '0','reference':r['reference'] or r['legacy_id'],'note':'منبع '+origin+' | قاعده مبدأ تأییدشده؛ نوع سبد قدیمی نامشخص' if b==defaultbasket else origin,'deal':r.get('deal') or '', 'share':None if r.get('deal') else '1','round_base':'5' if origin.startswith('Partner legacy!') else '0','stock_sign':MOVEMENTS[r['operation']][0],'custody_sign':0,'source_sha':r['source']['sha256'],'source_row':r['source_row'],'source_file':r['source']['file'],'basket_out':r.get('basket_out') or 0,'basket_return':r.get('basket_return') or 0}
            try:value=str(d.net_weight(record['gross'],record['count'],record['tare'],record['loss'],record['waste'],record['round_base']))
            except d.RuleError:value=None;record['note']+=' | وزن/تعداد ناقص؛ خالص نامعلوم'
            if r['count'] is None:record['note']+=' | شمار خالی طبق قاعده مبدأ صفر محاسبه شد؛ قابل اصلاح'
            if not record['party'] or not record['product']:record['note']+=' | شخص/محصول نامشخص؛ سند مالی خودکار ممنوع'
            put(w,'Weigh',record);imported.append({**record,'computed_net':value})
        for b in banks:
            for r in b['reconciled']:
                put(w,'SourceRows',{'id':r['id'],'source_file':r['source']['file'],'source_sha':r['source']['sha256'],'source_sheet':'Sheet1','source_row':r['source_row'],'payload':json.dumps(r['raw_cells'],ensure_ascii=False),'status':'اصل صورت‌حساب حفظ شد','reason':''})
                issues=[]
                if not r['reconciled'] and not r['duplicate_of']:issues.append('مسیر مانده قطعی نیست')
                if r.get('embedded_fee'):issues.append('اصل وجه و کارمزد تفکیک نشده')
                if not r.get('party_code') and not r['fee']:issues.append('شخص/نوع تسویه تعیین نشده')
                corrections=' | '.join(r['corrections'])
                put(w,'BankStatements',{'id':r['id'],'date':d.date(r['date']),'bank':r['bank'],'time':r['time'],'reference':r['reference'] or r['raw'].get('ردیف') or '', 'deposit':r['credit_source'],'withdrawal':r['debit_source'],'balance':r['reconstructed_balance'] if r['reconciled'] else r['balance_source'],'party':mapped['Parties'].get(r.get('party_code'),''),'party_code':r.get('party_code') or '', 'kind':'برگشت کارمزد بانکی' if r['fee'] and r['credit_source'] else 'کارمزد بانکی' if r['fee'] else ('دریافت' if r['credit_source'] else 'پرداخت'), 'status':'تکرار منبع' if r['duplicate_of'] else 'نیازمند تأیید تسویه','duplicate_of':r['duplicate_of'] or '', 'source_file':r['source']['file'],'source_sha':r['source']['sha256'],'source_row':r['source_row'],'raw_json':json.dumps(r['raw_cells'],ensure_ascii=False),'issues':' | '.join(issues),'correction':corrections})
        for n,x in enumerate(rows(w,'Info'),3):
            if x['key']=='mode':put(w,'Info',{'value':'اطلاعات مالک؛ ثبت مالی در انتظار تطبیق'},n)
        from app.integration import sync_physical
        sync_physical(w)
        from app.excel_design import apply as apply_design
        apply_design(w)
        decisions={'banks':'چهار بانک؛ همه IRR','tare':'همیشه کسر شود','weights':'قواعد مبدأ؛ خرید قدیم تارا P01 و افت P02؛ گردکردن صفر','sherakati':'همه ۲۶۲ ردیف موجود Weigh وارد شوند؛ از فایل مستقل شراکتی داده تازه وارد نشود','aliases':'نام‌های کوتاه تأیید قطعی نشده','reconcile':'اصلاح فقط با مسیر یکتای مبلغ و مانده'}
        put(w,'Info',{'key':'owner_policy_revision','value':'2026-11-05-all-weigh','note':'آخرین دستور مالک'})
        put(w,'Info',{'key':'owner_integration_decisions','value':json.dumps(decisions,ensure_ascii=False),'note':'پاسخ‌های مالک در همین جلسه؛ نه پیش‌فرض برنامه'})
        put(w,'Guide',{'topic':'داده مالک','instruction':'خرید/فروش باسکول فقط حرکت فیزیکی است؛ نرخ و سند خرید/فروش مالی ندارد. بانک‌ها در BankStatements با اصل و اصلاح قابل ردیابی‌اند؛ بدون تعیین شخص/ماهیت و تأیید تسویه، سند مالی نیستند. افتتاحیه بانک/اشخاص استنتاجی قطعی نشده است.'})
    result=store.read();summary={'weigh_imported':len(imported),'sherakati_excluded':len(excluded),'bank_rows':len(result['BankStatements']),'financial_events':len(result['Events']),'sources_preserved':len(result['SourceRows']),'pending_net':sum(r['computed_net'] is None for r in imported),'missing_party':sum(not r['party'] for r in imported),'missing_product':sum(not r['product'] for r in imported),'net_total':str(sum(Decimal(r['computed_net']) for r in imported if r['computed_net'] is not None)),'by_operation':{op:{'rows':sum(r['operation']==op for r in imported),'gross':str(sum(Decimal(r['gross']) for r in imported if r['operation']==op and r['gross'] is not None)),'net':str(sum(Decimal(r['computed_net']) for r in imported if r['operation']==op and r['computed_net'] is not None))} for op in Counter(r['operation'] for r in imported)},'bank_reconciliation':[{'bank':b['bank'],**b['reconciliation']} for b in banks],'decisions':decisions}
    (output/'INTEGRATION-CONTROL.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return store,summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--keshavarzi',type=Path,required=True);p.add_argument('--legacy-info',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s,summary=integrate(a.folder,a.keshavarzi,a.legacy_info,a.output);print(json.dumps(summary,ensure_ascii=False,indent=2))
