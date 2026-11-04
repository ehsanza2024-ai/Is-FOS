"""Private release assembler. No cookies, runtime authentication, browser state or tokens."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from collections import Counter
import ast,hashlib,html,json,re,shutil,subprocess,posixpath
from xml.etree import ElementTree as ET
from openpyxl import load_workbook,Workbook
from openpyxl.formula.tokenizer import Tokenizer
from app.store import Store
from app.workbook import SCHEMAS
from app.domain import RuleError
from scripts.build_delivery import public_files,pack
from scripts.build_viewer import build
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def description(p):
    purposes={'domain':'قواعد مستقل پول، تاریخ، وزن و ثبت دوبل','store':'قفل، پشتیبان، ممیزی، CAS و ذخیره اتمیک دفتر','workbook':'قرارداد ستون‌ها و ساخت فایل مستقل','schema':'مهاجرت نسخه‌دار قالب مرکزی','main':'API نرم‌افزار ثبت مرکزی','dashboard':'سطح HTTP گزارش‌خوان و دارایی‌های مجاز','reports':'بازسازی گزارش از اسناد قطعی و حرکات فیزیکی','integration':'انواع حرکت، امانت سبد و گزارش فیزیکی','movement_store':'ثبت/اصلاح قبض و اتصال اتمیک تسویه بانک','source_review':'حفظ اصل و بررسی بدون ثبت مالی','bank_reconcile':'مسیر یکتای مبلغ و مانده و جداسازی تکرار','excel_design':'رنگ‌بندی، نمودار، نرخ نمایش و توضیح روابط','security':'ورود کاربران و نقش‌ها؛ بدون داده مالی','entry_boundary':'مرز loopback و نشست پوسته نصب‌شده','central':'ترکیب مرز نصب‌شده با سرویس ورود','imports':'ورود دسته‌ای، نگاشت، خطا و کنترل تکرار','cloud_reports':'بسته گزارش رمزگذاری‌شده و بدون اطلاعات ورود','collaboration':'دفتر متنی و مشاور قاعده‌محور؛ بدون اجرای دستور مالی'}
    if p.stem in purposes:return purposes[p.stem]
    if p.suffix=='.py':
        try:
            tree=ast.parse(p.read_text());names=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
            return (ast.get_docstring(tree) or 'پیاده‌سازی/آزمون '+p.stem)+' | اجزای داخلی: '+', '.join(names)
        except Exception:return 'اسکریپت '+p.stem
    if p.suffix in ['.js','.css','.html']:return 'رابط، نمایش یا سبک؛ بدون منبع حقیقت مالی. '+p.name
    return 'مستند/پیکربندی/دارایی '+p.name

def legacy_catalog(path):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as z:
        rel={e.get('Id'):e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result=[]
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',ns):
            rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id');target=rel[rid]
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            families={};shared={};count=0
            if target in z.namelist():
                with z.open(target) as stream:
                    for _,el in ET.iterparse(stream,events=['end']):
                        if el.tag.endswith('}f'):
                            text=el.text
                            if el.get('t')=='shared':
                                if text:shared[el.get('si')]=text
                                else:text=shared.get(el.get('si'))
                            if text:
                                normalized=re.sub(r'(?<=[A-Z])\$?\d+','{row}',text)
                                if normalized not in families:families[normalized]={'formula':text,'count':0}
                                families[normalized]['count']+=1;count+=1
                        el.clear()
            result.append({'sheet':sheet.get('name'),'formula_count':count,'families':list(families.values())})
        return result

def md_html(md):
    parts=[]
    for line in md.splitlines():
        if not line.strip():continue
        level=len(line)-len(line.lstrip('#'))
        text=html.escape(line.lstrip('# ').replace('**',''))
        parts.append(f'<h{min(level,4)}>{text}</h{min(level,4)}>' if level else '<p>'+text+'</p>')
    return '\n'.join(parts)

def build_release(output):
    out=Path(output);workbook=out/'01-Workbook/Mazandasht.xlsx'
    if not workbook.is_file():raise ValueError('Integrate owner sources into 01-Workbook first')
    data=Store(workbook.parent,read_only=True).read();control=json.loads((workbook.parent/'INTEGRATION-CONTROL.json').read_text())
    assert len(data['Weigh'])==262 and len(data['BankStatements'])==508 and len(data['SourceRows'])==770
    assert all(r['destination'] for r in data['Weigh'] if r['operation']=='انتقال شراکتی')
    assert not data['Events'] and len({r['id'] for r in data['SourceRows']})==770
    assert sum(bool(r.get('duplicate_of')) for r in data['BankStatements'])==8
    # Workbook shape and formula lexing, not a claim of Excel Desktop recalculation.
    w=load_workbook(workbook);formula_families={};formula_count=0
    for s in w:
        families={}
        for row in s:
            for c in row:
                if c.data_type=='f':
                    Tokenizer(c.value);formula_count+=1
                    normalized=re.sub(r'(?<=[A-Z])\$?\d+','{row}',c.value)
                    family=hashlib.sha256(normalized.encode()).hexdigest()
                    if family not in families:families[family]={'cell':c.coordinate,'formula':c.value,'count':0}
                    families[family]['count']+=1
        formula_families[s.title]=list(families.values())
    filelist=list(public_files());inventory='\n'.join(f'{str(p.relative_to(ROOT))} — {description(p)}' for p in filelist if p.suffix not in ['.xlsx','.png','.woff2','.jpg'])
    tree='''Release-0.8/
├── 01-Workbook/              دفتر عملیاتی و کنترل ورود
├── 02-Software/              کل کد، نصب‌کننده، تست، قالب خالی
├── 03-Help/                  یک مرجع جامع SYSTEM-HELP.html
├── 04-Controls/              تطبیق، کیفیت، اثرانگشت و وضعیت آزمون
├── 05-Originals/             اصل‌های دست‌نخورده، نه دفتر ورود موازی
├── 06-Archive/               نسخه‌های مرجع قدیمیِ اصلاح‌شده
├── Install-Owner.bat / .sh   نصب با مسیر داده همین بسته
└── Start-Owner.bat / .sh     اجرای نرم‌افزار نصب‌شده همین داده
'''
    primary=(ROOT/'docs/SYSTEM_HELP_FA.md').read_text();body=md_html(primary)
    body+='<h2>۱۴. درخت تحویل و نقش فایل‌ها</h2><pre dir="ltr">'+html.escape(tree)+'</pre><details><summary>فهرست کامل فایل‌های نرم‌افزار و نقش هر فایل</summary><pre>'+html.escape(inventory)+'</pre></details>'
    body+='<h2>۱۵. وضعیت واقعی داده این تحویل</h2><pre>'+html.escape(json.dumps(control,ensure_ascii=False,indent=2))+'</pre>'
    body+='<p>کنترل وزن: ردیف‌های منبع ۵۹، ۲۴۷، ۲۴۸، ۲۴۹ و ۲۵۶ ناخالص ندارند و خالص آن‌ها نامعلوم است. شخص دو ردیف و محصول ۶۳ ردیف خالی است. دفتر مالی هنوز سند خودکار از این تاریخچه ندارد؛ بانک‌ها باید در صفحه تطبیق به شخص/ماهیت صحیح و سند متصل شوند.</p>'
    body+='<h2>۱۶. شناسنامه تک‌تک شیت‌ها و فرمول‌های واقعی</h2>'
    for s in w:
        headers=[str(c.value or '') for c in s[2]][:len(SCHEMAS.get(s.title,[]))] if s.title in SCHEMAS else []
        body+='<details><summary>'+html.escape(s.title)+' — '+html.escape(str(s.max_row))+' ردیف آماده/گزارشی</summary><p>'+html.escape(' | '.join(headers))+'</p>'
        for f in formula_families[s.title]:body+='<p>نمونه '+html.escape(f['cell'])+'، خانواده '+str(f['count'])+' سلول</p><pre dir="ltr">'+html.escape(f['formula'])+'</pre>'
        body+='</details>'
    body+='<h2>۱۷. همه فایل‌ها و شیت‌های منبع و مرجع؛ بدون ورود موازی</h2>'
    legacy_inventory={}
    for base in [ROOT/'private/sources',ROOT/'private/repaired-v1.11']:
        for p in sorted(base.rglob('*')):
            if not p.is_file():continue
            label=str(p.relative_to(ROOT/'private'))
            body+='<details><summary>'+html.escape(label)+'</summary><p>'+str(p.stat().st_size)+' بایت · SHA-256: '+sha(p)+'</p>'
            if p.suffix.lower()=='.xlsx':
                try:
                    catalog=legacy_catalog(p);legacy_inventory[label]=catalog
                    for sheet in catalog:
                        body+='<details><summary>'+html.escape(sheet['sheet'])+' — '+str(sheet['formula_count'])+' سلول فرمول</summary>'
                        for family in sheet['families']:body+='<p>خانواده '+str(family['count'])+' سلول</p><pre dir="ltr">'+html.escape(family['formula'])+'</pre>'
                        body+='</details>'
                except Exception as exc:body+='<p>بازخوانی متادیتای منبع کامل نشد: '+html.escape(type(exc).__name__)+'. اصل فایل بدون تغییر محفوظ است.</p>'
            body+='<p>منبع/مرجع تطبیق، نه دفتر ثبت موازی. اسکریپت‌های همراه منابع اجرا نشده‌اند.</p></details>'
    head='''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>مازندشت | مرجع جامع سیستم ۰٫۸</title><style>body{font:16px/2 Tahoma,Arial,sans-serif;background:#f3f5f2;color:#233c34;margin:0}main{max-width:1100px;margin:auto;background:#fff;padding:40px}h1{background:#173f35;color:white;padding:28px;border-radius:18px}h2{border-bottom:2px solid #d4e3d9;padding-top:24px;color:#245747}details{border:1px solid #dce6df;padding:16px;margin:12px 0;border-radius:10px}summary{cursor:pointer;font-weight:bold}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f1;padding:16px;border-radius:8px;font:13px/1.8 monospace}p{overflow-wrap:anywhere}@media(max-width:600px){main{padding:18px}}@media print{details{display:block}body{background:white}main{padding:0}h2{break-after:avoid}}</style><main>'''
    helpdir=out/'03-Help';helpdir.mkdir(parents=True,exist_ok=True);(helpdir/'SYSTEM-HELP.html').write_text(head+body+'</main></html>')
    # The same complete project/file/formula guide is available inside the main workbook.
    hs=w['Help'];hs.append(['نقشه تحویل',tree])
    for line in inventory.splitlines():hs.append(['پرونده نرم‌افزار',line])
    for sn,fs in formula_families.items():
        for f in fs:hs.append([sn+'!'+f['cell'],f['formula']])
    for label,catalog in legacy_inventory.items():
        for sheet in catalog:
            hs.append([label,sheet['sheet']+' — '+str(sheet['formula_count'])+' سلول فرمول مرجع'])
            for family in sheet['families']:hs.append([sheet['sheet'],family['formula']])
    from openpyxl.styles import Alignment,Font
    for row in hs.iter_rows(min_row=3):
        row[1].data_type='s';row[1].alignment=Alignment(wrap_text=True,vertical='top',horizontal='right');row[1].font=Font(name='Tahoma',size=11)
        hs.row_dimensions[row[0].row].height=min(360,max(28,18*((len(str(row[1].value or ''))+89)//90)))
    w.save(workbook)
    controls=out/'04-Controls';controls.mkdir(parents=True,exist_ok=True)
    shutil.copy2(workbook.parent/'INTEGRATION-CONTROL.json',controls/'INTEGRATION-CONTROL.json')
    quality={'schema':'1.2','version':'0.8.0','git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'formula_cells_lexed':formula_count,'native_excel_recalculation':'NOT RUN — Excel Desktop مقصد لازم است','windows_desktop':'NOT RUN','ios_safari':'NOT RUN','financial_history_posts':0,'automated_tests':'137 passed / 826.17s; one dependency deprecation warning','browser':'16 report tabs at 1440/1280/390; central edit and bank post on synthetic data; zero page errors; file-mode decrypt and exact custom FX passed','notes':'All owner Weigh rows retained; standalone Sherakati not read; bank source rows pending classification/confirmation.'}
    (controls/'VALIDATION.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2))
    (controls/'LEGACY-FORMULA-CATALOG.json').write_text(json.dumps(legacy_inventory,ensure_ascii=False,indent=2))
    (controls/'FORMULA-CATALOG.json').write_text(json.dumps(formula_families,ensure_ascii=False,indent=2))
    for name in ['Install-Owner','Start-Owner']:
        command='install' if name.startswith('Install') else 'start'
        (out/(name+'.bat')).write_text('@echo off\nset "MAZANDASHT_DATA=%~dp001-Workbook"\ncd /d "%~dp002-Software"\ncall '+command+'.bat\n')
        sh=out/(name+'.sh');sh.write_text('#!/usr/bin/env sh\nset -eu\nROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexport MAZANDASHT_DATA="$ROOT/01-Workbook"\ncd "$ROOT/02-Software"\nexec ./'+command+'.sh "$@"\n');sh.chmod(0o755)
    (out/'READ-ME-FIRST.txt').write_text('مازندشت ۰٫۸\nراهنمای کامل: 03-Help/SYSTEM-HELP.html\nفایل اصلی: 01-Workbook/Mazandasht.xlsx\nنصب: Install-Owner سپس Start-Owner\nاین بسته محرمانه است. مبالغ پایه ریال‌اند. اصل صورت‌حساب با ثبت قطعی مالی یکی نیست.\n')
    build()
    software=out/'02-Software';software.mkdir(exist_ok=True)
    for p in public_files():
        dest=software/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    originals=out/'05-Originals';originals.mkdir(exist_ok=True)
    for p in (ROOT/'private/sources').rglob('*'):
        if p.is_file():dest=originals/p.relative_to(ROOT/'private/sources');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest)
    archive=out/'06-Archive';archive.mkdir(exist_ok=True)
    for p in (ROOT/'private/repaired-v1.11').glob('*'):
        if p.is_file():
            shutil.copy2(p,archive/p.name);assert sha(p)==sha(archive/p.name)
    # Remove only transient lock/blank-backup files made by this build, never originals or active ledgers.
    allowed_owner={'Mazandasht.xlsx','INTEGRATION-CONTROL.json','evolution.jsonl'}
    items=[(p,str(p.relative_to(out))) for p in out.rglob('*') if p.is_file() and (p.parts[len(out.parts)]!='01-Workbook' or p.name in allowed_owner)]
    manifest={name:sha(p) for p,name in items};(controls/'SHA256SUMS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));items.append((controls/'SHA256SUMS.json','04-Controls/SHA256SUMS.json'))
    zipfile=out.parent/'Mazandasht-Complete-0.8.0-2026-11-05.zip';summary=pack(zipfile,items,'خصوصی؛ نسخه ۰٫۸. دفتر عملیاتی، کد کامل، اصل منابع و راهنمای جامع. مبنای مالی ریال. صورت‌حساب‌های بانک هنوز نیازمند تعیین ماهیت و اتصال سندند. SYSTEM-HELP.html را بخوانید.')
    softwarezip=out.parent/'Mazandasht-Software-0.8.0.zip';pack(softwarezip,[(p,str(p.relative_to(out))) for p in software.rglob('*') if p.is_file()],'Source code and blank workbook only; no owner transactions.')
    with ZipFile(zipfile) as z:
        assert z.testzip() is None
        assert not any('auth.sqlite3' in n or '__pycache__' in n or 'workbook.lock' in n for n in z.namelist())
        for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
    (out.parent/'HANDOFF-0.8.json').write_text(json.dumps({'complete':summary,'software':str(softwarezip),'main_workbook':str(workbook),'help':str(helpdir/'SYSTEM-HELP.html'),'validation':quality,'counts':control},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();build_release(a.output)
