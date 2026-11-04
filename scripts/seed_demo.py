"""Synthetic fixtures only. Never run against an operational workbook."""
from pathlib import Path
from app.store import Store, fingerprint
from app.workbook import rows,put

def seed(root):
    s=Store(root,True)
    with s.lock:
        from openpyxl import load_workbook
        w=load_workbook(s.path)
        info={x['key']:x['value'] for x in rows(w,'Info')}
        if info.get('mode')!='نمونه آموزشی':raise ValueError('Refusing to seed a non-demo workbook')
        if rows(w,'Events'):return
    with s.edit('سازنده داده آموزشی','demo.seed',fingerprint(s.path)) as w:
        for month,buy,sell,rate in [('06','4000','1500','180000'),('07','5000','3000','200000'),('08','6000','4500','220000')]:
            common={'date':'1405'+month+'10','party':'باغدار نمونه','bank':'بانک آموزشی','product':'پرتقال آموزشی','store':'انبار آموزشی'}
            for data in [
                dict(common,kind='سرمایه',amount='500000000',reference='DEMO-CAP-'+month),
                dict(common,kind='خرید',qty=buy,rate='120000',reference='DEMO-BUY-'+month),
                dict(common,kind='فروش',party='خریدار نمونه',qty=sell,rate=rate,cost=str(int(sell)*120000),reference='DEMO-SALE-'+month),
                dict(common,kind='دریافت',party='خریدار نمونه',amount=str(int(sell)*int(rate)),reference='DEMO-REC-'+month),
                dict(common,kind='پرداخت',amount=str(int(buy)*120000),reference='DEMO-PAY-'+month),
                dict(common,kind='هزینه',amount='18000000',reference='DEMO-COST-'+month),
                dict(common,kind='دستمزد',amount='25000000',reference='DEMO-WAGE-'+month)
            ]:s._event(w,data)
        put(w,'Checks',{'id':'demo-check-1','date':14050810,'due':14050910,'number':'آموزشی ۰۰۱','direction':'دریافتی','party':'خریدار نمونه','bank':'بانک آموزشی','amount':60000000,'state':'ثبت‌شده','reference':'DEMO-CHECK-1','note':'اطلاعات کاملاً مصنوعی'})
        put(w,'Checks',{'id':'demo-check-2','date':14050810,'due':14050825,'number':'آموزشی ۰۰۲','direction':'پرداختی','party':'باغدار نمونه','bank':'بانک آموزشی','amount':40000000,'state':'ثبت‌شده','reference':'DEMO-CHECK-2','note':'اطلاعات کاملاً مصنوعی'})
        put(w,'Stock',{'product':'پرتقال آموزشی','store':'انبار آموزشی'},3)
    s.add_weigh({'date':'14050813','operation':'ورود','party':'باغدار نمونه','product':'پرتقال آموزشی','store':'انبار آموزشی','basket':'سبد آموزشی سفید','count':'100','gross':'2140','loss':'0','waste':'0','reference':'آموزشی ۱۰۱'},'سازنده داده آموزشی',fingerprint(s.path))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path,nargs='?',default=Path('runtime/demo'));a=p.parse_args();seed(a.root);print('Synthetic demo ready:',a.root)
