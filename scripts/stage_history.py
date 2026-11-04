"""Lossless review staging of literal dated rows. Never posts financial documents.
Original ZIP packages remain authoritative for formulas, cached values and formatting.
"""
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill
import hashlib,json,re,argparse

SKIP={'Calendar','Sync','Report','Guide','Flow','Map','Accounting','Trial','PL','BS','Lines','Cash','Monthly','Trial4','Trial6','DemoJE','Demo4','Demo6','Help','Main','Stock','Custody','A4','A4Flex','A5'}

def stage(root,output):
    out=Workbook();s=out.active;s.title='HistoryReview';s.sheet_view.rightToLeft=True
    s.append(['نسخه منبع','فایل','شیت','ردیف اصل','اثر انگشت ردیف','تکرار عیناً مشابه','داده ثابت خام JSON','حکم مهاجرت'])
    seen={};count=0
    for file in sorted(root.glob('v*/*.xlsx')):
        w=load_workbook(file,read_only=True,data_only=False)
        for sh in w:
            if sh.title in SKIP:continue
            for row in sh.iter_rows(min_row=4):
                literals={c.column_letter:str(c.value) for c in row if c.value is not None and c.data_type!='f'}
                if not any(re.fullmatch(r'1[34]\d{6}',str(c.value)) for c in row if c.value is not None and c.data_type!='f'):continue
                raw=json.dumps(literals,ensure_ascii=False,sort_keys=True)
                h=hashlib.sha256(raw.encode()).hexdigest();seen[h]=seen.get(h,0)+1
                s.append([file.parent.name,file.name,sh.title,row[0].row,h,'بله' if seen[h]>1 else 'خیر',raw,'فقط بازبینی؛ ثبت مالی ممنوع تا تطبیق واحد و مرجع'])
                count+=1
    s.freeze_panes='E2';s.auto_filter.ref=s.dimensions
    for c in s[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='153E35')
    for col,width in [('A',15),('B',24),('C',22),('D',15),('E',22),('F',20),('G',90),('H',60)]:s.column_dimensions[col].width=width
    output.parent.mkdir(parents=True,exist_ok=True);out.save(output)
    return {'staged_rows':count,'exact_repeat_occurrences':sum(n-1 for n in seen.values()),'unique_literal_fingerprints':len(seen),'financial_posts':0,'note':'Only literal dated rows; formula-only financial rows remain in the original workbooks and are not inferred.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=stage(a.root,a.output);a.output.with_suffix('.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(r)
