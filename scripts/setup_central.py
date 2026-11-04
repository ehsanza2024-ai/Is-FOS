"""Interactive first installation. Never migrate history or reset an existing user silently."""
from pathlib import Path
import argparse
import getpass
import os
import sqlite3
from app.store import Store
from app.security import Security

BASE=Path(__file__).resolve().parents[1]

def password(label):
    value=getpass.getpass(label+' (12+ characters): ')
    if len(value)<12:raise SystemExit('Use at least 12 characters; installation cancelled.')
    if value!=getpass.getpass('Repeat password: '):raise SystemExit('Passwords do not match.')
    return value

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(os.environ.get('MAZANDASHT_DATA',BASE/'runtime/local')));a=p.parse_args()
    root=a.data.resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'Mazandasht.xlsx').exists():
        existing=Store(root,read_only=True).read()
        if any(r['key']=='mode' and r['value']=='نمونه آموزشی' for r in existing['Info']):
            raise SystemExit('Synthetic demo ledger detected. Select a separate real central data directory.')
        if any(r['key']=='schema_version' and r['value'] in ['1.0','1.1'] for r in existing['Info']):
            if input('Upgrade existing canonical schema to 1.2 with backup? [y/N]: ').strip().lower()!='y':raise SystemExit('Upgrade declined; existing ledger unchanged.')
            from scripts.upgrade_ledger import upgrade
            upgrade(root)
    if (root/'auth.sqlite3').exists():
        with sqlite3.connect((root/'auth.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            count=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if not count:raise SystemExit('Existing auth file has no users. Inspect it; installation did not overwrite it.')
        print('Existing users preserved. Use scripts.manage_user to change passwords.')
        Store(root).read();print('Existing/new workbook validated: '+str(root/'Mazandasht.xlsx'));return
    secret=password('Central admin password')
    os.environ['MAZANDASHT_PASSWORD']=secret
    os.environ.pop('MAZANDASHT_DEMO',None)
    security=Security(root)
    os.environ.pop('MAZANDASHT_PASSWORD',None)
    if input('Create a report-only viewer? [Y/n]: ').strip().lower()!='n':
        name=input('Viewer login name [viewer]: ').strip() or 'viewer'
        if name=='admin':raise SystemExit('Viewer cannot replace admin. Admin created; use manage_user for viewer.')
        security.add(name,password('Report viewer password'),'viewer')
    Store(root).read()
    print('Ready: '+str(root/'Mazandasht.xlsx'))
    print('Workbook is empty unless already present. No historical/JSON data was imported.')
    print('Run start.bat or ./start.sh. Leave the installed window running for dashboards.')
if __name__=='__main__':main()
