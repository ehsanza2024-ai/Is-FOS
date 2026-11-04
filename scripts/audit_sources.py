"""Privacy-safe structural inventory; no business rows are published."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import hashlib,json,argparse
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def audit(root):
    records=[]
    for file in sorted(root.glob('v*/*.xlsx')):
        with ZipFile(file) as z:
            book=E.fromstring(z.read('xl/workbook.xml'));rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'));targets={r.get('Id'):r.get('Target') for r in rels}
            sheets=[]
            for sh in book.findall('s:sheets/s:sheet',N):
                target=targets[sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
                xml=E.fromstring(z.read(target));sheets.append({'name':sh.get('name'),'dimension':xml.find('s:dimension',N).get('ref') if xml.find('s:dimension',N) is not None else None,'formula_count':len(xml.findall('.//s:f',N)),'validation_count':len(xml.findall('.//s:dataValidation',N))})
            records.append({'version':file.parent.name,'file':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'external_link_parts':sum(1 for x in z.namelist() if x.startswith('xl/externalLinks/externalLink') and x.endswith('.xml')),'sheets':sheets,'review':'structure_audited; financial_rows_not_reconciled'})
    return records
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=audit(a.root);a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps({'date':'2026-11-04','scope':'33 downloaded workbooks, not every file in the Drive tree','files':r},ensure_ascii=False,indent=2));print('Audited',len(r),'workbooks; formulas:',sum(s['formula_count'] for f in r for s in f['sheets']))
