"""Build reproducible-content source package and optional private Excel delivery.
No auth, runtime database, live workbook, password or browser dependency is packaged.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse,hashlib,json
from app.workbook import create

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.8.0'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def public_files():
    for folder in ['app','static','scripts','tests','docs','templates','.github']:
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.log'] and p.name!='START_HERE_FA.html':yield p
    names=['README.md','.gitignore','.gitattributes']+[p.name for pattern in ['requirements*.txt','*.sh','*.bat'] for p in sorted(ROOT.glob(pattern))]
    for name in names:
        p=ROOT/name
        if p.exists():yield p

def pack(target,items,notice):
    checks={name:sha(path) for path,name in items}
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for path,name in items:z.write(path,name)
        z.writestr('DELIVERY-NOTICE.txt',notice)
        z.writestr('SHA256SUMS.json',json.dumps(checks,ensure_ascii=False,indent=2))
    return {'file':target.name,'bytes':target.stat().st_size,'sha256':sha(target),'members':len(items)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-sources',type=Path);p.add_argument('--repaired',type=Path);p.add_argument('--history',type=Path);p.add_argument('--bank-review',type=Path);p.add_argument('--output',type=Path,default=ROOT/'private'/'delivery');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    from scripts.build_viewer import build
    build()
    create(ROOT/'templates/Mazandasht-Blank.xlsx')
    software=[(f,'Software/'+str(f.relative_to(ROOT))) for f in public_files()]+[(ROOT/'docs/START_HERE_FA.html','START-HERE-FA.html')]
    outputs=[pack(a.output/f'Mazandasht-Software-{VERSION}.zip',software,'نسخه ۰٫۸؛ پذیرش Excel/PC مقصد لازم است؛ نصب اسکریپتی مرکزی + داشبورد فقط‌خواندنی؛ بدون داده واقعی و بدون EXE امضاشده. START-HERE-FA.html و Software/docs/INSTALL_CENTRAL_FA.md و docs/SYSTEM_HELP_FA.md را بخوانید. نصب اولیه آنلاین و پذیرش روی PC مقصد لازم است. مهاجرت مالی تاریخچه انجام نشده است.')]
    if a.private_sources:
        if not a.repaired or not a.history:p.error('Private delivery requires --repaired and --history')
        items=software+[(f,'Sources/'+str(f.relative_to(a.private_sources))) for f in sorted(a.private_sources.rglob('*')) if f.is_file()]+[(f,'Excel-v1.11/'+f.name) for f in sorted(a.repaired.glob('*')) if f.is_file()]+[(a.history,'Migration-Review/'+a.history.name)]
        if a.history.with_suffix('.json').exists():items.append((a.history.with_suffix('.json'),'Migration-Review/summary.json'))
        if a.bank_review:items += [(f,'Bank-Review/'+f.name) for f in sorted(a.bank_review.glob('*')) if f.is_file()]
        outputs.append(pack(a.output/f'Mazandasht-Private-Consolidated-{VERSION}-2026-11-05.zip',items,'محرمانه — شامل فایل‌های واقعی مالک. در GitHub عمومی بارگذاری نکنید. Sources اصل‌های دست‌نخورده (شامل صورت‌حساب بانک جدید)، Bank-Review بازبینی و تطبیق بدون ثبت، Excel-v1.11 اصلاح نام‌ها و Migration-Review staging است. دفترکل تاریخی خودکار مهاجرت نشده. نرم‌افزار ۰٫۸ با نصب اسکریپتی و داشبورد فقط‌خواندنی، نسخه توسعه است، نه محصول نهایی پذیرفته‌شده. START-HERE-FA.html و Software/docs/INSTALL_CENTRAL_FA.md و EXCEL_CHANGES_FA.html را بخوانید. همه ۱۴ فایل اصلاحی را کنار هم نگه دارید. پوسته نصب‌شده/Excel Desktop/iOS مقصد هنوز پذیرش می‌خواهند.'))
    (a.output/'DELIVERY_MANIFEST.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2));print(json.dumps(outputs,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
