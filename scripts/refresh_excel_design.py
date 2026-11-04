"""Audited visual refresh of a canonical workbook; never rewrites source archives."""
from pathlib import Path
import argparse
from app.store import Store,fingerprint
from app.excel_design import apply
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);a=p.parse_args()
    if not (a.data/'Mazandasht.xlsx').is_file():raise SystemExit('Existing canonical workbook required')
    s=Store(a.data)
    with s.edit('مدیر طراحی','presentation.refresh',fingerprint(s.path)) as w:apply(w)
    print('Design refreshed with an exact prior backup; base amounts unchanged.')
