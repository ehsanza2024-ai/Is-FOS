"""Local interactive user/password administration. Passwords never go in arguments."""
from pathlib import Path
import argparse, os, getpass, sqlite3
from app.security import Security,ROLES

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(os.environ.get('MAZANDASHT_DATA','runtime/local')));p.add_argument('--name',required=True);p.add_argument('--role',choices=ROLES,default='viewer');a=p.parse_args()
    if not (a.data/'auth.sqlite3').is_file():raise SystemExit('First run scripts.setup_central to create the central installation.')
    password=getpass.getpass('New password (12+ characters): ')
    if password!=getpass.getpass('Repeat password: '):raise SystemExit('Passwords do not match')
    if len(password)<12:raise SystemExit('Use at least 12 characters')
    security=Security(a.data,existing_only=True)
    with sqlite3.connect(security.path) as db:
        db.execute('DELETE FROM users WHERE name=?',(a.name,));security._insert(db,a.name,password,a.role)
    print('Local user updated. Restart the server to revoke existing sessions.')
if __name__=='__main__':main()
