"""Non-destructive OOXML patch: never round-trip legacy workbooks through openpyxl.
Only input DVs, new name selectors and canonical-code formula cells are changed.
All package parts, extensions, external links and existing formulas are preserved.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re, json, hashlib, argparse
from collections import Counter
from lxml import etree as E
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter as letter, column_index_from_string as index

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
N={'s':NS}; Q=lambda t:f'{{{NS}}}{t}'
MAP={'SourceIDs':('__Weigh',2,3,'بار منبع'),'AcctCodes':('Parties',1,2,'طرف حساب'),'AcctInput':('Parties',1,2,'طرف حساب'),
 'BasketCodes':('Baskets',1,2,'نوع سبد'),'ProductCodes':('Products',1,2,'محصول'),
 'StoreCodes':('Stores',1,2,'انبار'),'BankCodes':('Banks',1,2,'بانک'),
 'DealCodes':('Deals',1,2,'قرارداد شراکت'),'WageCodes':('Wage',1,2,'نرخ کارکرد'),
 'FxCodes':('Fx',1,2,'واحد پول'),'InvoiceAccounts':('Parties',1,2,'طرف حساب')}

def setcell(root, address, value=None, formula=None, cache=None):
 sd=root.find(Q('sheetData')); rn=int(re.search(r'\d+',address)[0])
 row=sd.find(f"{Q('row')}[@r='{rn}']")
 if row is None:
  row=E.Element(Q('row'),r=str(rn))
  following=next((x for x in sd if int(x.get('r'))>rn),None)
  if following is None:sd.append(row)
  else:sd.insert(sd.index(following),row)
 c=row.find(f"{Q('c')}[@r='{address}']")
 if c is None:
  c=E.Element(Q('c'),r=address); ci=index(re.sub(r'\d','',address))
  following=next((x for x in row if index(re.sub(r'\d','',x.get('r')))>ci),None)
  if following is None:row.append(c)
  else:row.insert(row.index(following),c)
 for child in list(c):c.remove(child)
 c.attrib.pop('t',None)
 if formula is not None:
  E.SubElement(c,Q('f')).text=formula.removeprefix('=')
  if cache is not None:c.set('t','str');E.SubElement(c,Q('v')).text=str(cache)
 elif value is not None:
  c.set('t','inlineStr');E.SubElement(E.SubElement(c,Q('is')),Q('t')).text=str(value)
 return c

def hidecol(root,col,hide=True,width=23):
 cols=root.find(Q('cols'))
 if cols is None:
  cols=E.Element(Q('cols'));root.insert(root.index(root.find(Q('sheetData'))),cols)
 # Split grouped column definitions rather than accidentally hiding neighbouring inputs.
 for old in list(cols):
  lo,hi=int(old.get('min')),int(old.get('max'))
  if lo<=col<=hi:
   attrs=dict(old.attrib);cols.remove(old)
   for a,b in [(lo,col-1),(col+1,hi)]:
    if a<=b:E.SubElement(cols,Q('col'),**{**attrs,'min':str(a),'max':str(b)})
 E.SubElement(cols,Q('col'),min=str(col),max=str(col),width=str(width),customWidth='1',hidden='1' if hide else '0')
 sorted_cols=sorted(cols,key=lambda c:int(c.get('min')));cols[:]=sorted_cols

def repair(source:Path,dest:Path,info:Path):
 wb=load_workbook(source,data_only=False); iw=load_workbook(info,data_only=True)
 cached=load_workbook(source,data_only=True)
 parts={}; report=[]
 with ZipFile(source) as z: parts={n:z.read(n) for n in z.namelist()}
 book=E.fromstring(parts['xl/workbook.xml']); rel=E.fromstring(parts['xl/_rels/workbook.xml.rels'])
 targets={r.get('Id'):r.get('Target') for r in rel}
 names={x.get('name'):x.text for x in book.findall('s:definedNames/s:definedName',N)}
 parties={str(r[0]):r[1] for r in iw['Parties'].iter_rows(min_row=9,values_only=True) if r[0]}
 roots={}
 for sn in book.findall('s:sheets/s:sheet',N):
  target=targets[sn.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
  path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
  roots[sn.get('name')]=(path,E.fromstring(parts[path]))
 for sheet in wb:
  root=roots[sheet.title][1];nextcol=sheet.max_column+2
  for dv in list(root.findall('s:dataValidations/s:dataValidation',N)):
   f=dv.find(Q('formula1')); key=(f.text or '').lstrip('=') if f is not None else ''
   if key not in MAP:continue
   # Do not rewrite existing calculated inputs (read-only report selectors are OK).
   spec=MAP[key];rs=iw[spec[0]] if key!='SourceIDs' else load_workbook(source.parent/'Weigh.xlsx',data_only=False)['Entry']; mapping={}; labels=[];counts=Counter()
   for row in rs.iter_rows(min_row=9,values_only=True):
    if not row[0]:continue
    code=str(row[0]);label=str(row[spec[2]-1] or '')
    if key=='SourceIDs':
     if not row[5] or not row[1]:continue
     code=str(row[1]);label='بار '+str(row[19] or '')+' · '+str(parties.get(str(row[3]),row[3] or 'بدون نام'))+' · '+str(row[5])
    if key in ['DealCodes','WageCodes']:
     label=('شراکت با ' if key=='DealCodes' else 'نرخ کارکرد ')+str(parties.get(label,label))
     label+=' · دوره '+str(row[3] if key=='DealCodes' else row[6])
    counts[label]+=1
    if counts[label]>1:label+=f' · گزینه {counts[label]}'
    mapping[code]=label;labels.append((code,label))
   if not labels:continue
   # Local lookup snapshot uses stable codes; dynamic references to Sync/Info allow refresh.
   syncname='Sync' if 'Sync' in roots else spec[0]
   syncroot=roots[syncname][1];base=wb[syncname].max_column+2
   # Allocate beyond any helpers already appended in this pass.
   dim=syncroot.find(Q('dimension'))
   existingmax=max([index(re.sub(r'\d','',c.get('r'))) for c in syncroot.findall('s:sheetData/s:row/s:c',N)] or [base])
   base=max(base,existingmax+2);cc,nc=letter(base),letter(base+1)
   ref=names.get(key,'');m=re.match(r"'?([^'!]+)'?!\$(\w+)\$(\d+)",ref)
   dynamic=key in ['AcctCodes','AcctInput','BasketCodes','ProductCodes','StoreCodes','BankCodes','FxCodes','InvoiceAccounts']
   sync_cols={'AcctCodes':('A','B'),'AcctInput':('A','B'),'BasketCodes':('D','E'),'ProductCodes':('G','H'),'StoreCodes':('R','S'),'BankCodes':('P','Q'),'FxCodes':('A','B'),'InvoiceAccounts':('AY','AZ')}
   if dynamic:
    codecol,namecol=sync_cols[key]
    count=300
    for j in range(9,count+9):
     cached_code,cached_label=labels[j-9] if j-9<len(labels) else ('','')
     sc=f"'{syncname}'!{codecol}{j}";sl=f"'{syncname}'!{namecol}{j}"
     setcell(syncroot,f'{cc}{j}',formula=f'IF({sc}="","",{sc})',cache=cached_code)
     duplicate=f"COUNTIF('{syncname}'!${namecol}$9:{namecol}{j},{sl})"
     setcell(syncroot,f'{nc}{j}',formula=f'IF({sc}="","",{sl}&IF({duplicate}>1," · گزینه "&{duplicate},""))',cache=cached_label)
   else:
    count=len(labels)
    for j,(code,label) in enumerate(labels,9):
     setcell(syncroot,f'{cc}{j}',value=code);setcell(syncroot,f'{nc}{j}',value=label)
   hidecol(syncroot,base);hidecol(syncroot,base+1)
   end=8+count;drange=f"'{syncname}'!${nc}$9:${nc}${end}";crange=f"'{syncname}'!${cc}$9:${cc}${end}"
   dn=book.find(Q('definedNames'))
   if dn is None:dn=E.SubElement(book,Q('definedNames'))
   newname='UI_'+key+'_'+str(nextcol)
   E.SubElement(dn,Q('definedName'),name=newname).text=f"'{syncname}'!${nc}$9:INDEX({drange},MAX(1,COUNTIF({crange},\"?*\")))"
   selectors=[];original=str(dv.get('sqref'))
   from openpyxl.worksheet.cell_range import MultiCellRange
   for area in MultiCellRange(original).ranges:
    if area.min_col!=area.max_col:raise ValueError('Unexpected multi-column validation')
    newletter=letter(nextcol);selectors.append(f'{newletter}{area.min_row}:{newletter}{area.max_row}')
    headerrow=8 if area.min_row>=9 else max(1,area.min_row-1)
    setcell(root,f'{newletter}{headerrow}',value=spec[3]+' (انتخاب نام)')
    for rownum in range(area.min_row,area.max_row+1):
     old=sheet.cell(rownum,area.min_col);val=old.value
     if val is not None and not str(val).startswith('='):
      label=mapping.get(str(val),str(val));setcell(root,f'{newletter}{rownum}',value=label)
     elif val is not None:
      # Do not replace formulas that may be part of an unrelated workflow.
      continue
     setcell(root,old.coordinate,formula=f'IF({newletter}{rownum}="","",IFERROR(INDEX({crange},MATCH({newletter}{rownum},{drange},0)),""))',cache=val)
    if area.min_row>=9 and area.max_row>100:hidecol(root,area.min_col)
    hidecol(root,nextcol,False,28);nextcol+=1
   dv.set('sqref',' '.join(selectors));f.text=newname
   dv.set('showErrorMessage','1');dv.set('errorStyle','stop');dv.set('errorTitle','انتخاب نام معتبر');dv.set('error','نام را از فهرست انتخاب کنید؛ کد به‌صورت خودکار محاسبه می‌شود.')
   dv.set('showDropDown','0')
   report.append({'sheet':sheet.title,'old_range':original,'selector':' '.join(selectors),'type':key,'choices':len(labels),'refresh':'live_sync' if dynamic else 'snapshot'})
  if report and sheet['A1'].value is None:
   setcell(root,'A1',value='نسخه اصلاح‌شده: ورودی نام در ستون‌های انتهای شیت؛ کدهای پنهان را ویرایش نکنید.')
 for sn,(path,root) in roots.items():
  dim=root.find(Q('dimension'))
  if dim is not None:
   maxcol=max(index(re.sub(r'\d','',c.get('r'))) for c in root.findall('s:sheetData/s:row/s:c',N))
   dim.set('ref',f'A1:{letter(maxcol)}{wb[sn].max_row}')
  parts[path]=E.tostring(root,encoding='utf-8')
 calc=book.find(Q('calcPr'))
 if calc is None:calc=E.SubElement(book,Q('calcPr'))
 calc.set('fullCalcOnLoad','1');calc.set('forceFullCalc','1');calc.set('calcMode','auto')
 parts['xl/workbook.xml']=E.tostring(book,encoding='utf-8')
 dest.parent.mkdir(parents=True,exist_ok=True)
 with ZipFile(dest,'w',ZIP_DEFLATED) as z:
  for n,b in parts.items():z.writestr(n,b)
 return {'file':source.name,'sha256_before':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256_after':hashlib.sha256(dest.read_bytes()).hexdigest(),'selectors':report,'note':'نام اقلام اصلی به Sync پیوند دارد؛ نام قرارداد، نرخ و شناسه بار snapshot است. اصل و نسخه اصلاحی را جدا نگه دارید.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 results=[repair(f,a.output/f.name,a.source/'Info.xlsx') for f in sorted(a.source.glob('*.xlsx'))]
 (a.output/'repair-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 print('Repaired',len(results),'workbooks; selectors',sum(len(r['selectors']) for r in results))
