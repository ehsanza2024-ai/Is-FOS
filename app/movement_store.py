"""Installed-centre transactional adapters; source rows never become implicit financial events."""
from app import domain as d
from app.workbook import rows,put,indexed_rows
from app.integration import MOVEMENTS,SPECIAL,BANK_KINDS,net

def whole(v,label):
    n=d.decimal(v or 0,label)
    if n!=n.to_integral_value():raise d.RuleError(label+' باید صحیح باشد')
    return int(n)

def add_weigh(store,data,actor,revision,entity=None):
    from app.store import uid,Conflict
    previous=next((x for x in store.read()['Weigh'] if x['id']==entity),None) if entity else None
    if entity and not previous:raise d.RuleError('ردیف باسکول یافت نشد')
    if previous:data={**previous,**data}
    r={k:d.normalize(data.get(k,'')) for k in ['operation','party','product','store','basket','reference','note','deal','destination']}
    r.update(id=uid(),date=d.date(data.get('date')))
    with store.edit(actor,'weigh.update:'+entity if entity else 'weigh.create',revision) as w:
        target=None
        if entity:
            old=next(((n,x) for n,x in indexed_rows(w,'Weigh') if x['id']==entity),None)
            if not old:raise d.RuleError('ردیف باسکول یافت نشد')
            reversed_ids={x.get('reversal_of') for x in rows(w,'Events')}
            if old[1]['operation'] in SPECIAL or any(x.get('source_weigh')==entity and x['id'] not in reversed_ids and not x.get('reversal_of') for x in rows(w,'Events')):raise d.RuleError('قبض دارای سند مالی فعال است؛ اصلاح نیازمند برگشت سند و ثبت جایگزین است')
            target=old[0];r['id']=entity
            for k in ['source_sha','source_row','source_file']:r[k]=old[1].get(k)
        if 'WeighOps' not in w:raise d.RuleError('ابتدا ساختار ۱٫۲ را ارتقا دهید')
        refs=store.refs(w);op=r['operation']
        if op not in MOVEMENTS and op not in SPECIAL:raise d.RuleError('نوع عملیات معتبر نیست')
        if not r['reference']:raise d.RuleError('شماره قبض لازم است')
        if any(x['reference']==r['reference'] and x['id']!=entity for x in rows(w,'Weigh')):raise Conflict('شماره قبض تکراری است')
        if r['party'] not in {x['name'] for x in refs['Parties']}:raise d.RuleError('طرف حساب معتبر لازم است')
        if op in SPECIAL:
            dr,cr,code,name=SPECIAL[op]
            if code:
                person=next((p for p in refs['Parties'] if p.get('code')==code),None)
                if (person and person['name']!=r['party']) or (not person and r['party']!=name):raise d.RuleError('شخص انتخابی با حساب ویژه این عملیات یکسان نیست')
            e=store._event(w,{'date':r['date'],'kind':op,'party':r['party'],'amount':data.get('amount'),'reference':'WEIGH-'+r['id'],'note':r['note']+' | قبض '+r['reference']})
            r.update(gross='0',count='0',tare='0',loss='0',waste='0',share='1',round_base='5',stock_sign=0,custody_sign=0,basket_out=0,basket_return=0,note=r['note']+' | سند '+e['id']);qty=0
        else:
            sign,cs,route,mode=MOVEMENTS[op]
            for k,sn in [('product','Products'),('store','Stores'),('basket','Baskets')]:
                if (mode=='بار' or k=='basket') and r[k] not in {x['name'] for x in refs[sn]}:raise d.RuleError('نام '+k+' معتبر لازم است')
            if route and (r['destination'] not in {x['name'] for x in refs['Stores']} or r['destination']==r['store']):raise d.RuleError('مبدأ و مقصد معتبر و متفاوت لازم است')
            r['count']=str(whole(data.get('count'),'تعداد سبد'))
            for k in ['basket_out','basket_return']:r[k]=whole(data.get(k),k)
            r['share']='1'
            if r['deal']:
                contract=next((x for x in refs['Deals'] if x['name']==r['deal']),None)
                if not contract or (contract['status']!='تأیید' and not (entity and previous.get('deal')==r['deal'])) or not int(contract['start'])<=r['date']<=int(contract['end']):raise d.RuleError('قرارداد معتبر و تأییدشده لازم است')
                if contract.get('product') and contract['product']!=r['product']:raise d.RuleError('محصول قرارداد ناسازگار است')
                r['share']=str(contract['share']) if contract['status']=='تأیید' else None
            if 'شراکتی' in op and not r['deal']:raise d.RuleError('بار شراکتی نیازمند قرارداد تأییدشده مستقل است')
            r.update(stock_sign=sign,custody_sign=cs,round_base=str(d.decimal(data.get('round_base') if data.get('round_base') not in [None,''] else 5)))
            b=next(x for x in refs['Baskets'] if x['name']==r['basket']);tare=data.get('tare')
            if tare in [None,'']:tare=b.get('tare')
            if mode=='سبد':
                if int(r['count'])<=0:raise d.RuleError('تعداد سبد باید مثبت باشد')
                r.update(gross='0',tare=str(tare or '0'),loss='0',waste='0');qty=0
            else:
                if data.get('gross') in [None,'']:raise d.RuleError('وزن باسکول لازم است')
                for k in ['gross','loss','waste']:r[k]=str(d.decimal(data.get(k) or 0))
                if tare in [None,'']:raise d.RuleError('تارای واقعی سبد لازم است؛ خودکار صفر فرض نمی‌شود')
                r['tare']=str(d.decimal(tare));qty=net(r)
        put(w,'Weigh',r,target)
        from app.integration import sync_physical
        sync_physical(w)
    return {**r,'net':str(qty)}

def resolve_bank(store,entity,data,actor,revision):
    from app.store import Conflict,uid
    with store.edit(actor,'bank.resolve:'+entity,revision) as w:
        found=next(((n,r) for n,r in indexed_rows(w,'BankStatements') if r['id']==entity),None)
        if not found:raise d.RuleError('ردیف منبع یافت نشد')
        row,r=found
        if r.get('event_id') or r.get('duplicate_of'):raise Conflict('ردیف قبلاً ثبت شده یا تکرار منبع است')
        kind=d.normalize(data.get('kind'));party=d.normalize(data.get('party'));note=d.normalize(data.get('note'))
        if r.get('issues') and (data.get('confirm_anomaly') is not True or not note):raise d.RuleError('ابهام منبع باید با تأیید صریح و توضیح مسئول رفع شود')
        dep=d.money(r.get('deposit') or 0);wd=d.money(r.get('withdrawal') or 0)
        if bool(dep)==bool(wd):raise d.RuleError('مبلغ/جهت منبع قابل ثبت نیست')
        if kind=='انتقال بین بانک‌ها':
            other=next(((n,x) for n,x in indexed_rows(w,'BankStatements') if x['id']==data.get('counterpart_id')),None)
            if not other:raise d.RuleError('ردیف مقابل انتقال لازم است')
            n2,x=other
            if x.get('event_id') or x.get('duplicate_of') or x['bank']==r['bank']:raise d.RuleError('ردیف مقابل آزاد و بانک متفاوت لازم است')
            if x.get('issues'):raise d.RuleError('ابهام ردیف مقابل ابتدا جدا رفع شود')
            xd=d.money(x.get('deposit') or 0);xw=d.money(x.get('withdrawal') or 0)
            if not ((dep and xw==dep and not xd) or (wd and xd==wd and not xw)):raise d.RuleError('دو طرف انتقال باید مبلغ برابر و جهت معکوس داشته باشند؛ کارمزد جداست')
            name='واسط انتقال بین بانک‌ها'
            if name not in {p['name'] for p in rows(w,'Parties')}:put(w,'Parties',{'id':uid(),'name':name,'role':'واسط','active':'بله','code':'SYS-TRANSFER'})
            events=[]
            for rn,record in [found,other]:
                inc=bool(d.money(record.get('deposit') or 0));e=store._event(w,{'date':record['date'],'kind':'انتقال بانکی ورود' if inc else 'انتقال بانکی خروج','party':name,'bank':record['bank'],'amount':dep or wd,'reference':'BANK-'+record['id'],'note':note})
                put(w,'BankStatements',{'event_id':e['id'],'kind':kind,'party':name,'status':'ثبت‌شده'},rn);events.append(e['id'])
            return {'event_ids':events}
        operation=next((o for o in rows(w,'Operations') if o['name']==kind and o['active']=='بله'),None)
        if not operation or [operation['debit'],operation['credit']].count('بانک')!=1:raise d.RuleError('عملیات باید دقیقاً یک طرف بانک و حساب مقابل مشخص داشته باشد')
        incoming=operation['debit']=='بانک'
        if incoming and not dep or not incoming and not wd:raise d.RuleError('نوع تسویه با جهت منبع یکسان نیست')
        if kind in ['کارمزد بانکی','برگشت کارمزد بانکی']:
            party='خدمات بانک '+r['bank']
            if party not in {p['name'] for p in rows(w,'Parties')}:put(w,'Parties',{'id':uid(),'name':party,'role':'بانک','active':'بله','code':'BANK-SERVICE-'+r['bank']})
        fee=d.money(data.get('fee_amount') or 0)
        amount=dep or wd
        if fee and (incoming or kind=='کارمزد بانکی' or fee>=amount):raise d.RuleError('کارمزد تفکیکی فقط همراه پرداخت و کمتر از مبلغ کل است')
        e=store._event(w,{'date':r['date'],'kind':kind,'party':party,'bank':r['bank'],'amount':amount-fee,'reference':'BANK-'+r['id'],'note':note})
        ids=[e['id']]
        if fee:
            fee_party='خدمات بانک '+r['bank']
            if fee_party not in {p['name'] for p in rows(w,'Parties')}:put(w,'Parties',{'id':uid(),'name':fee_party,'role':'بانک','active':'بله','code':'BANK-SERVICE-'+r['bank']})
            f=store._event(w,{'date':r['date'],'kind':'کارمزد بانکی','party':fee_party,'bank':r['bank'],'amount':fee,'reference':'BANK-FEE-'+r['id'],'note':note});ids.append(f['id'])
        put(w,'BankStatements',{'event_id':','.join(ids),'party':party,'kind':kind,'status':'ثبت‌شده','issues':'','correction':(r.get('correction') or '')+' | تأیید '+note},row)
    return {'event_ids':ids}
