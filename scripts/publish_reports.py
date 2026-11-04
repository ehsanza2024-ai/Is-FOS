"""Publish a password-encrypted report file to a chosen local/synced PRIVATE folder."""
import argparse,getpass,os
from pathlib import Path
from app.store import Store
from app.cloud_reports import package

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(os.environ.get('MAZANDASHT_DATA','runtime/local')));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    password=getpass.getpass('Report file password (12+ characters): ')
    if password!=getpass.getpass('Repeat: '):raise SystemExit('Passwords do not match')
    store=Store(a.data,read_only=True);data=store.read();content=package(data,password)
    a.output.mkdir(parents=True,exist_ok=True);target=a.output/('Mazandasht-'+data['revision'][:12]+'.mazreport')
    with target.open('xb') as f:f.write(content)
    os.chmod(target,0o600)
    print('Encrypted report only: '+str(target));print('Keep this file private; share the password separately. This is a snapshot, not live cloud synchronization.')
if __name__=='__main__':main()
