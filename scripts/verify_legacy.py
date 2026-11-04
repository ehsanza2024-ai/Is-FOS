"""Verify every original formula and non-worksheet package part survived the patch."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json,argparse
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def verify(source,output):
    reports=[]
    for file in sorted(source.glob('*.xlsx')):
        with ZipFile(file) as before,ZipFile(output/file.name) as after:
            missing=set(before.namelist())-set(after.namelist());assert not missing,(file.name,missing)
            formulas=0;checked=0
            for member in before.namelist():
                if member.startswith('xl/worksheets/') and member.endswith('.xml') and '/_rels/' not in member:
                    old=E.fromstring(before.read(member));new=E.fromstring(after.read(member))
                    cells={c.get('r'):c for c in new.findall('s:sheetData/s:row/s:c',NS)}
                    for c in old.findall('s:sheetData/s:row/s:c',NS):
                        f=c.find('s:f',NS)
                        if f is None:continue
                        assert c.get('r') in cells,(file.name,member,c.get('r'))
                        nf=cells[c.get('r')].find('s:f',NS)
                        assert nf is not None and E.tostring(f,method='c14n')==E.tostring(nf,method='c14n'),(file.name,member,c.get('r'))
                        formulas+=1
                    # Extensions (including x14 DVs) are required to survive byte-independent XML roundtrip.
                    for ext in old.findall('s:extLst',NS):
                        nxt=new.find('s:extLst',NS);assert nxt is not None
                        assert E.tostring(ext,method='c14n')==E.tostring(nxt,method='c14n'),(file.name,'extLst')
                elif member!='xl/workbook.xml':
                    assert before.read(member)==after.read(member),(file.name,member,'changed payload')
                    checked+=1
            reports.append({'file':file.name,'original_formulas_preserved':formulas,'unchanged_other_package_parts':checked,'missing_parts':0})
    return reports
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('report',type=Path);a=p.parse_args();r=verify(a.source,a.output);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2));print('Verified',len(r),'workbooks;',sum(x['original_formulas_preserved'] for x in r),'original formulas preserved')
