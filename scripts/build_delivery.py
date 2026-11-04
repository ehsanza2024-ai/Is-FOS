"""Build reproducible-content source package and optional private Excel delivery.
No auth, runtime database, live workbook, password or browser dependency is packaged.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse,hashlib,json
from app.workbook import create

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def public_files():
    for folder in ['app','static','scripts','tests','docs','templates']:
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.log']:yield p
    for name in ['README.md','requirements.txt','requirements.lock.txt','start.sh','start.bat','.gitignore','.gitattributes']:
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
    p=argparse.ArgumentParser();p.add_argument('--private-sources',type=Path);p.add_argument('--repaired',type=Path);p.add_argument('--history',type=Path);p.add_argument('--output',type=Path,default=ROOT/'private'/'delivery');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);create(ROOT/'templates/Mazandasht-Blank.xlsx')
    software=[(f,'Software/'+str(f.relative_to(ROOT))) for f in public_files()]
    outputs=[pack(a.output/'Mazandasht-Software-0.5.0.zip',software,'نسخه توسعه ۰٫۵؛ بدون داده واقعی و بدون نصب‌کننده EXE. راه‌اندازی README و Guide را بخوانید. پذیرش مالی نهایی انجام نشده است.')]
    if a.private_sources:
        if not a.repaired or not a.history:p.error('Private delivery requires --repaired and --history')
        items=software+[(f,'Sources/'+str(f.relative_to(a.private_sources))) for f in sorted(a.private_sources.rglob('*')) if f.is_file()]+[(f,'Excel-v1.11/'+f.name) for f in sorted(a.repaired.glob('*')) if f.is_file()]+[(a.history,'Migration-Review/'+a.history.name)]
        if a.history.with_suffix('.json').exists():items.append((a.history.with_suffix('.json'),'Migration-Review/summary.json'))
        outputs.append(pack(a.output/'Mazandasht-Private-Consolidated-2026-11-04.zip',items,'محرمانه — شامل فایل‌های واقعی مالک. در GitHub عمومی بارگذاری نکنید. Sources اصل‌های دست‌نخورده، Excel-v1.11 اصلاح نام‌ها و Migration-Review staging است. دفترکل تاریخی خودکار مهاجرت نشده. نرم‌افزار ۰٫۵ نسخه توسعه است، نه محصول نهایی پذیرفته‌شده. همه ۱۴ فایل اصلاحی را کنار هم نگه دارید و راهنمای Software/docs/USER_GUIDE_FA.md را بخوانید.'))
    (a.output/'DELIVERY_MANIFEST.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2));print(json.dumps(outputs,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
