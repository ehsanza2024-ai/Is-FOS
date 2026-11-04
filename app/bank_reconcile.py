"""Unique balance-path reconstruction. Original cells are never changed.
Unknown identities and accounting classifications remain pending even when cash reconciles.
"""
from collections import defaultdict
from decimal import Decimal
from app.source_review import digest,integer,key

def reconcile(records):
    records=[dict(r) for r in records];seen={};unique=[]
    for r in records:
        identity=(r['bank'],r['date'],r['time'],r.get('reference') or r['raw'].get('ردیف'),r['credit_source'],r['debit_source'],r['balance_source'])
        duplicate=seen.get(identity)
        r.update(duplicate_of=duplicate['id'] if duplicate else None,reconciled=False,reconstructed_balance=None,corrections=[])
        if not duplicate:seen[identity]=r;unique.append(r)
    groups=defaultdict(list)
    for r in unique:groups[(r['date'],r['time'])].append(r)
    groups=[groups[k] for k in sorted(groups)];anchor=None;pending=[];issues=[]
    def balance(r):
        if r['balance_source'] is not None:return r['balance_source']
        try:return integer(r.get('possible_balance_shifted_column'))
        except ValueError:return None
    def solve(block,opening,allow_flip):
        solutions=[];visits=0
        def group_step(index,current,path):
            nonlocal visits
            visits+=1
            if visits>20000 or len(solutions)>1:return
            if index==len(block):solutions.append(path);return
            g=block[index]
            def walk(remaining,value,steps):
                nonlocal visits
                visits+=1
                if visits>20000 or len(solutions)>1:return
                if not remaining:group_step(index+1,value,path+steps);return
                for r in remaining:
                    if r['credit_source'] is None or r['debit_source'] is None:continue
                    delta=r['credit_source']-r['debit_source'];target=balance(r)
                    for flip in ([False,True] if allow_flip else [False]):
                        after=value-delta if flip else value+delta
                        if target is not None and target!=after:continue
                        walk([x for x in remaining if x['id']!=r['id']],after,steps+[(r,after,flip)])
            walk(g,current,[])
        group_step(0,opening,[])
        return solutions if visits<=20000 else []
    for g in groups:
        if anchor is None:
            # Opening is inferred, never posted as equity or treated as confirmed.
            if len(g)==1 and balance(g[0]) is not None and g[0]['credit_source'] is not None:
                r=g[0];anchor=balance(r);r['reconciled']=True;r['reconstructed_balance']=anchor
            else:issues.extend(r['id'] for r in g)
            continue
        pending.append(g)
        if not any(balance(r) is not None for r in g):
            if sum(map(len,pending))>8:issues.extend(r['id'] for group in pending for r in group);pending=[];anchor=None
            continue
        paths=solve(pending,anchor,False)
        if not paths:paths=solve(pending,anchor,True)
        if len(paths)==1:
            for r,after,flip in paths[0]:
                r['reconciled']=True;r['reconstructed_balance']=after
                if flip:
                    r['credit_source'],r['debit_source']=r['debit_source'],r['credit_source'];r['corrections'].append('جهت با مسیر یکتای مبلغ و مانده اصلاح شد')
                if r['balance_source'] is None:r['corrections'].append('مانده از ستون جابه‌جا و مسیر پیوسته تطبیق شد' if r.get('possible_balance_shifted_column') else 'مانده میانی استنتاجی؛ مبلغ/جهت تا مانده بعدی تطبیق شد')
            anchor=paths[0][-1][1];pending=[]
        else:
            issues.extend(r['id'] for group in pending for r in group);pending=[]
            # Do not propagate a guessed anchor across an inconsistent block.
            anchor=None
    issues.extend(r['id'] for group in pending for r in group)
    return records,{'rows':len(records),'unique_rows':len(unique),'duplicates':sum(bool(r['duplicate_of']) for r in records),'reconciled':sum(r['reconciled'] for r in records),'direction_corrections':sum(any('جهت' in c and 'اصلاح' in c for c in r['corrections']) for r in records),'pending':len(set(issues))}
