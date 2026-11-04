"""Explicit audited upgrade of canonical 1.0/1.1 XLSX. Legacy workbooks refused."""
import argparse
from pathlib import Path
from app.store import Store,fingerprint
from app.workbook import rows
from app.schema import install

def upgrade(root):
    if not (Path(root)/'Mazandasht.xlsx').is_file():raise ValueError('Existing canonical ledger required; no new ledger was created')
    store=Store(root,read_only=False)
    data=store.read()
    version=next((r['value'] for r in data['Info'] if r['key']=='schema_version'),None)
    if version not in ['1.0','1.1','1.2']:raise ValueError('Unsupported canonical schema; never upgrade legacy workbooks here')
    with store.edit('مدیر ارتقا','schema.upgrade.1.2',data['revision']) as w:install(w)
    return fingerprint(store.path)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);a=p.parse_args();print(upgrade(a.data))
