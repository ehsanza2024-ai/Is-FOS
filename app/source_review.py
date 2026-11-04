"""Lossless owner-source intake and exact reconciliation; never posts or deletes.
An accounting identity is not inferred from amount, substring or a bank direction.
"""
from collections import Counter,defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import hashlib,json,re
from openpyxl import load_workbook
from app.domain import normalize,date,RuleError

VERSION=1

def text(v):return normalize(v).replace('\u200c',' ').replace('\u200e','').replace('\u200f','').replace('\r',' ').strip()
def key(v):return re.sub(r'\s+',' ',text(v)).strip()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
def decimal(v):
    if v is None or key(v)=='':raise RuleError('عدد خالی است؛ صفر فرض نشد')
    if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:[,٬]\d{3})+)(?:[.٫]\d+)?',text(v)):raise RuleError('قالب عدد نامعتبر')
    try:n=Decimal(text(v).replace(',','').replace('٬','').replace('٫','.'))
    except Exception:raise RuleError('عدد نامعتبر')
    if not n.is_finite():raise RuleError('عدد نامتناهی/نامعتبر')
    return n

def integer(v,blank_zero=False):
    n=Decimal(0) if blank_zero and (v is None or key(v)=='') else decimal(v)
    if n!=n.to_integral_value():raise RuleError('عدد صحیح لازم است')
    return int(n)

def raw(v):
    if isinstance(v,bool) or v is None:return v
    # Keep stored cell text separate from calculations, including formulas and leading zeroes.
    return str(v)

def source(path):
    path=Path(path);return {'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def rows(path,sheet):
    w=load_workbook(path,read_only=True,data_only=False,keep_links=False)
    try:return list(w[sheet].values)
    finally:w.close()

def reference_data(path):
    out={};provenance=source(path)
    w=load_workbook(path,read_only=True,data_only=False,keep_links=False)
    try:
        for sn in w.sheetnames:
            s=list(w[sn].values);headers=[str(x or '') for x in s[7]]
            out[sn]=[{**dict(zip(headers,[raw(v) for v in r])),'_row':n,'_source':provenance,'_raw_cells':[raw(v) for v in r]} for n,r in enumerate(s[8:],9) if r[0] is not None and not str(r[0]).startswith('=')]
    finally:w.close()
    return out

def match_party(cells,parties):
    """Explicit whole-code / whole-name matches only; competing codes stay unresolved.
    Account numbers, a partial name, a narrative inference and fuzzy similarity are not identities.
    """
    segments=[key(c) for c in cells if c is not None];candidates={};evidence=defaultdict(list)
    for p in parties:
        code=key(p.get('Code'));name=key(p.get('Name'))
        if not code or not name:continue
        for s in segments:
            if s==code or re.search(r'(?<![\w])'+re.escape(code)+r'(?![\w])',s,re.I):evidence[code].append('کد صریح در داده منبع')
            if s==name:evidence[code].append('نام کامل برابر تعریف')
        if evidence[code]:candidates[code]=p
    if len(candidates)==1:
        code=next(iter(candidates));return {'party_code':code,'party_name':key(candidates[code]['Name']),'match':'exact','evidence':sorted(set(evidence[code])),'candidates':[code]}
    return {'party_code':None,'party_name':None,'match':'conflict' if candidates else 'unresolved','evidence':[],'candidates':sorted(candidates)}

def bank_statement(path,parties,bank,unit=None):
    data=rows(path,'Sheet1');provenance=source(path);header=None;line=None
    for n,r in enumerate(data[:40],1):
        hs=[key(v) for v in r]
        if ('تاریخ' in hs or 'تاریخ تراکنش' in hs) and ('برداشت' in hs or 'مبلغ تراکنش' in hs):header=hs;line=n;break
    if header is None:raise RuleError('سرستون صورت‌حساب شناخته نشد')
    metadata=' '.join(key(x) for r in data[:line-1] for x in r if x is not None)
    if 'ریال' in metadata and 'تومان' in metadata:raise RuleError('دو واحد پول در سربرگ منبع؛ تأیید لازم است')
    detected='IRR' if 'ریال' in metadata else 'IRT' if 'تومان' in metadata else None
    if unit and unit not in ['IRR','IRT']:raise RuleError('واحد منبع معتبر نیست')
    if detected and unit and detected!=unit:raise RuleError('واحد انتخاب‌شده با سربرگ بانک تعارض دارد')
    unit=detected or unit
    records=[];excluded=[]
    for n,r in enumerate(data[line:],line+1):
        values={h:raw(r[i]) for i,h in enumerate(header) if h and i<len(r)}
        d=next((values.get(k) for k in ['تاریخ تراکنش','تاریخ'] if values.get(k)),None)
        if not d or not re.match(r'^1[34]\d{2}[/\-]?\d{2}[/\-]?\d{2}',text(d)):
            if any(v is not None and key(v) for v in r):excluded.append({'source_row':n,'raw':[raw(v) for v in r],'reason':'سربرگ/پاورقی یا ردیف فاقد تاریخ تراکنش؛ حذف از اصل نشده'})
            continue
        errors=[];day=re.match(r'^1[34]\d{2}[/\-]?\d{2}[/\-]?\d{2}',text(d))[0]
        try:day=str(date(day))
        except RuleError as e:errors.append(str(e))
        # The appended Mehr rows introduce a seventh column without changing the header.
        # Keep literal cells intact; expose candidate fields, never silently move a balance.
        appended='مبلغ تراکنش' in values and len(r)>6 and r[6] is not None
        owner=values.get('نام صاحب حساب',values.get('صاحب حساب'))
        narrative=raw(r[6]) if appended else values.get('شرح')
        possible_balance=raw(r[4]) if appended and r[4] is not None and re.fullmatch(r'\d{1,3}(?:,\d{3})+',text(r[4])) else None
        if possible_balance:owner=None
        if appended:errors.append('چیدمان ردیف افزوده با سربرگ یکسان نیست؛ ستون ۷ شرح و ستون ۵ گاهی مانده است')
        debit=credit=balance=None
        try:
            if 'مبلغ تراکنش' in values:
                amount=integer(values['مبلغ تراکنش']);direction=key(values.get('نوع تراکنش'))
                if direction not in ['برداشت','واریز']:raise RuleError('جهت بانکی نامشخص')
                debit=amount if direction=='برداشت' else 0;credit=amount if direction=='واریز' else 0
            else:debit=integer(values.get('برداشت'),True);credit=integer(values.get('واریز'),True)
            if debit<0 or credit<0 or bool(debit)==bool(credit):raise RuleError('جهت/مبلغ بانکی نامعتبر')
        except RuleError as e:errors.append(str(e));debit=credit=None
        try:balance=integer(values.get('مانده',values.get('موجودی')))
        except RuleError as e:errors.append('مانده منبع قابل کنترل نیست: '+str(e))
        fields=[owner,narrative]+[values.get(k) for k in ['شرح2','توضیحات','توضیحات 2','نوع تراکنش']]
        matched=match_party(fields,parties)
        fee=any(key(v).startswith(('کارمزد','برداشت کارمزد','برگشت عملیات برداشت کارمزد')) for v in [owner,narrative,values.get('توضیحات'),values.get('نوع تراکنش')])
        embedded_fee=not fee and any('کارمزد' in key(v) for v in fields)
        if embedded_fee:errors.append('شرح شامل کارمزد است؛ سهم کارمزد از اصل پرداخت تفکیک نشده')
        own_account=re.search(r'شماره سپرده\s*:\s*(\d+)',metadata)
        if own_account and credit and 'برگشت' not in key(narrative) and re.search(r'از سپرده\s*'+re.escape(own_account[1])+r'(?!\d)',key(narrative)):errors.append('جهت واریز با شرح انتقال از همین سپرده تعارض دارد؛ خودکار اصلاح نشد')
        if matched['match']!='exact':errors.append('کد طرف حساب نیازمند تعیین است' if not fee else 'کارمزد بانک؛ حساب هزینه نیازمند نگاشت تأییدشده')
        if unit is None:errors.append('واحد پول منبع صریح نیست')
        rid=digest([provenance['sha256'],'Sheet1',n])
        record={'id':rid,'bank':bank,'source_row':n,'date':day,'time':values.get('زمان') or text(d)[10:].strip(),'debit_source':debit,'credit_source':credit,'balance_source':balance,'source_unit':unit,'reference':raw(r[5]) if appended else values.get('شماره سند') or None,'possible_balance_shifted_column':possible_balance,'owner_literal':owner,'narrative_literal':narrative,'fee':fee,'embedded_fee':embedded_fee,**matched,'errors':errors,'raw':values,'raw_cells':[raw(v) for v in r],'source':provenance,'posted':False}
        record['duplicate_key']=digest([bank,record['date'],record['time'],debit,credit,record['reference'],fields]);records.append(record)
    valid=[r for r in records if r['debit_source'] is not None];days=[r['date'] for r in valid]
    order='unknown' if len(set(days))<2 else 'ascending' if days==sorted(days) else 'descending' if days==sorted(days,reverse=True) else 'unknown'
    mismatches=[];checks=0
    if order!='unknown':
        for a,b in zip(records,records[1:]):
            if any(x[k] is None for x in (a,b) for k in ['debit_source','credit_source','balance_source']):continue
            newer,older=(b,a) if order=='ascending' else (a,b);diff=newer['balance_source']-older['balance_source']-newer['credit_source']+newer['debit_source'];checks+=1
            if diff:mismatches.append({'source_row':newer['source_row'],'difference_source_units':diff})
    duplicates=[k for k,c in Counter(r['duplicate_key'] for r in records).items() if c>1]
    oldest=records[0] if order=='ascending' and records else records[-1] if order=='descending' and records else None
    if oldest and any(oldest[k] is None for k in ['debit_source','credit_source','balance_source']):oldest=None
    return {'source':provenance,'bank':bank,'header_row':line,'unit':unit,'records':records,'excluded':excluded,'summary':{'rows':len(records),'unit':unit,'order':order,'total_credit_source':sum(r['credit_source'] for r in valid),'total_debit_source':sum(r['debit_source'] for r in valid),'continuity_checks':checks,'continuity_mismatches':mismatches,'inferred_opening_source':oldest['balance_source']-oldest['credit_source']+oldest['debit_source'] if oldest else None,'opening_confirmed':False,'exact_matches':sum(r['match']=='exact' for r in records),'unresolved':sum(r['match']!='exact' and not r['fee'] for r in records),'embedded_fee_rows':sum(r['embedded_fee'] for r in records),'missing_balances':sum(r['balance_source'] is None for r in records),'layout_changes':sum(r['possible_balance_shifted_column'] is not None or any('چیدمان' in e for e in r['errors']) for r in records),'fees':sum(r['fee'] for r in records),'duplicate_keys':duplicates,'financial_posts':0}}

def weigh_review(path,refs):
    data=rows(path,'Entry');provenance=source(path);records=[]
    parties={key(r['Code']):r for r in refs['Parties']};products={key(r['Code']):r for r in refs['Products']};baskets={key(r['Code']):r for r in refs['Baskets']}
    for n,r in enumerate(data[8:],9):
        if len(r)<6 or r[5] is None:continue
        literal=lambda i:None if i>len(r) or r[i-1] is None or str(r[i-1]).startswith('=') else raw(r[i-1])
        errors=[];code=key(literal(4));p=parties.get(code);pr=products.get(key(literal(8)));basket=baskets.get(key(literal(7)));net=None
        try:
            day=str(date(literal(6)))
            if not p:errors.append('کد شخص در Info یافت نشد')
            if not pr:errors.append('کد محصول در Info یافت نشد')
            count=integer(literal(9));gross=decimal(literal(10));tare=decimal(literal(15)) if literal(15) is not None else decimal(basket.get('Tare kg')) if basket else None
            if count<0 or gross<0:raise RuleError('تعداد/وزن منفی')
            if tare is None:errors.append('نوع سبد/تارای واقعی خالی؛ خالص قطعی محاسبه نشده')
            else:
                loss=decimal(literal(16) or '0');waste=decimal(literal(17) or '0')
                if not 0<=loss<=1 or waste<0 or tare<0:raise RuleError('افت/ضایعات/تارا نامعتبر')
                value=(gross-Decimal(count)*tare)*(1-loss)-waste
                if value<0:raise RuleError('وزن خالص منفی')
                net=str((value/5).to_integral_value(rounding=ROUND_FLOOR)*5)
        except RuleError as e:errors.append(str(e));day=text(literal(6))
        if literal(23):errors.append('قرارداد شراکتی و روش وزن/درصد نیازمند تطبیق با فایل مستقل')
        records.append({'id':digest([provenance['sha256'],'Entry',n]),'source_row':n,'legacy_id':literal(2),'date':day,'operation':literal(3),'party_code':code,'party_name':key(p['Name']) if p else None,'product_code':literal(8),'product_name':key(pr['Name']) if pr else None,'basket_code':literal(7),'basket_name':basket.get('Name') if basket else None,'count':literal(9),'gross':literal(10),'tare_manual':literal(15),'loss_fraction':literal(16),'waste':literal(17),'net_candidate_current_weigh':net,'source_store':literal(18),'destination_store':literal(19),'reference':literal(20),'basket_out':literal(21),'basket_return':literal(22),'deal':literal(23),'share_override':literal(24),'special_amount_irr':literal(25),'rate':literal(12),'errors':errors,'raw':{str(i+1):raw(v) for i,v in enumerate(r) if v is not None},'source':provenance,'financial_posted':False,'physical_posted':False})
    return records

def joint_review(path,weigh):
    data=rows(path,'ورود و خروج');provenance=source(path);settings=rows(path,'تعاریف و ثوابت');apply_tare=key(settings[6][1])=='بله';round_base=decimal(settings[4][1]);default_loss=decimal(settings[5][1]);
    if round_base<=0 or not 0<=default_loss<=100:raise RuleError('ثوابت وزن شراکتی نامعتبر است')
    basket_tares={key(r[1]):r[2] for r in settings[94:115] if len(r)>2 and r[1] and r[2] is not None};records=[]
    for n,r in enumerate(data[6:],7):
        if r[1] is None:continue
        errors=[];net=None
        try:
            day=str(date(r[1]));gross=decimal(r[15]);count=integer(r[13]);percent=decimal(r[16]) if r[16] is not None else None;loss_kg=decimal(r[17]) if r[17] is not None else None
            if percent is not None and loss_kg is not None:raise RuleError('درصد و کیلو افت همزمان وارد شده؛ تقدم نیازمند تأیید')
            loss=loss_kg if loss_kg is not None else gross*(percent if percent is not None else default_loss)/100
            if count<0 or gross<0:raise RuleError('وزن/تعداد منفی')
            if loss<0 or loss>gross:raise RuleError('افت خارج از محدوده')
            tare=decimal(basket_tares.get(key(r[12]))) *count if apply_tare else Decimal(0)
            if gross-loss-tare<0:raise RuleError('وزن منفی؛ صفرسازی خودکار انجام نشد')
            net=str(((gross-loss-tare)/round_base).to_integral_value(rounding=ROUND_FLOOR)*round_base)
        except RuleError as e:errors.append(str(e));day=text(r[1])
        matches=[x for x in weigh if x['date']==day and key(x['reference'])==key(r[27]) and x['gross']==raw(r[15]) and x['count']==raw(r[13])]
        if len(matches)!=1:errors.append('پیوند یکتای ردیف باسکول پیدا نشد')
        linked=matches[0] if len(matches)==1 else None
        if linked and linked['net_candidate_current_weigh']!=net:errors.append('اختلاف وزن خالص میان فایل مستقل و باسکول تبدیل‌شده')
        records.append({'id':digest([provenance['sha256'],'ورود و خروج',n]),'source_row':n,'date':day,'operation':raw(r[6]),'party':raw(r[7]),'deal':raw(r[8]),'product':raw(r[11]),'count':raw(r[13]),'gross':raw(r[15]),'apply_tare':apply_tare,'round_base':str(round_base),'net_candidate_independent':net,'net_candidate_current_weigh':linked['net_candidate_current_weigh'] if linked else None,'linked_weigh_id':linked['id'] if linked else None,'reference':raw(r[27]),'errors':errors,'raw':{str(i+1):raw(v) for i,v in enumerate(r) if v is not None},'source':provenance,'append_as_new_weigh':False,'financial_posted':False})
    return records


def build_review(folder,legacy_info=None):
    folder=Path(folder);refs=reference_data(folder/'Info.xlsx');weigh=weigh_review(folder/'Weigh.xlsx',refs);joint=joint_review(folder/'سیستم مدیریت بار شراکتی.xlsx',weigh)
    refs['JointDefinitions']=[{'source_row':n,'raw':{str(i+1):raw(v) for i,v in enumerate(r) if v is not None},'_source':source(folder/'سیستم مدیریت بار شراکتی.xlsx')} for n,r in enumerate(rows(folder/'سیستم مدیریت بار شراکتی.xlsx','تعاریف و ثوابت'),1) if any(v is not None and not str(v).startswith('=') for v in r)]
    if legacy_info:
        legacy_source=source(legacy_info)
        legacy_book=load_workbook(legacy_info,read_only=True,data_only=False,keep_links=False)
        try:
            for tab in ['Groups','MainGroups','SubGroups','WorkGroups','Accounts','Params','TxnTypes','Ops','Baskets','Products_Buy','Products_Sell','Warehouses','Banks','Cheques','Staff']:
                if tab in legacy_book:
                    refs['Legacy.'+tab]=[{'source_row':n,'raw':{str(i+1):raw(v) for i,v in enumerate(r) if v is not None},'_source':legacy_source} for n,r in enumerate(legacy_book[tab].values,1) if any(v is not None and not str(v).startswith('=') for v in r)]
        finally:legacy_book.close()
    banks=[bank_statement(folder/name,refs['Parties'],bank) for name,bank in [('پرینت حساب صادرات 9009.xlsx','صادرات 9009'),('پرینت حساب صادرات 2006.xlsx','صادرات 2006'),('پرینت حساب مهر ایران.xlsx','مهر ایران')]]
    return {'format':'mazandasht.owner-source-review','version':VERSION,'references':refs,'weigh':weigh,'joint':joint,'banks':banks,'decisions_required':{'weigh_tare':'۲۴۸ ردیف فاقد تارا؛ فایل قدیم ۱٫۵ و فایل شراکتی بدون کسر تارا','joint_contract':'P-1405-01 در Info با JV001/نارنگی/سهم صفر، در داده با JV003/کیوی/درصد نامطمئن','scale_account':'X002 با نام درآمد و عملیات هزینه؛ جهت باید تأیید شود','bank_scope':'سه خروجی جدید یا کشاورزی نیز؟ جایگزینی کدام دفتر؟'},'summary':{'weigh_rows':len(weigh),'weigh_operations':dict(Counter(x['operation'] for x in weigh)),'weigh_missing_net':sum(x['net_candidate_current_weigh'] is None for x in weigh),'joint_rows':len(joint),'joint_linked':sum(bool(x['linked_weigh_id']) for x in joint),'joint_weight_conflicts':sum(x['net_candidate_independent']!=x['net_candidate_current_weigh'] for x in joint),'bank_rows':sum(len(b['records']) for b in banks),'bank_exact_party_matches':sum(b['summary']['exact_matches'] for b in banks),'bank_unresolved_parties':sum(b['summary']['unresolved'] for b in banks),'bank_fee_rows':sum(b['summary']['fees'] for b in banks),'financial_posts':0,'deleted_rows':0}}
