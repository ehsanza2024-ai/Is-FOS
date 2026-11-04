"""Local authentication; technical SQLite only, financial truth remains Excel."""
import hashlib, hmac, os, secrets, sqlite3, time
from pathlib import Path
from fastapi import Request, HTTPException

ROLES={'admin':{'read','operate','finance','admin'},'finance':{'read','operate','finance'},'operator':{'read','operate'},'viewer':{'read'}}

class Security:
    def __init__(self,root,demo=False,cookie_name="maz_session",existing_only=False):
        self.demo=demo;self.sessions={};self.failures={};self.path=Path(root)/'auth.sqlite3'
        self.cookie_name=cookie_name;self.existing_only=existing_only
        if existing_only:
            if not demo and not self.path.is_file():raise FileNotFoundError('کاربران مرکزی را ابتدا ایجاد کنید')
            return
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,salt TEXT NOT NULL,digest TEXT NOT NULL,role TEXT NOT NULL)')
            if not db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
                password=os.environ.get('MAZANDASHT_PASSWORD') or secrets.token_urlsafe(18)
                self._insert(db,'admin',password,'admin')
                if not os.environ.get('MAZANDASHT_PASSWORD') and not demo:print('Initial local admin password (change via environment on first setup): '+password,flush=True)
        os.chmod(self.path,0o600)

    @staticmethod
    def _insert(db,name,password,role):
        if role not in ROLES or len(password)<12 or not name or len(name)>80:raise ValueError('نام، نقش و رمز حداقل ۱۲ نویسه لازم است')
        salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),310000).hex()
        db.execute('INSERT INTO users VALUES (?,?,?,?)',(name,salt,digest,role))

    def add(self,name,password,role):
        if self.existing_only:raise HTTPException(403,'مدیریت کاربران فقط در سیستم مرکزی مجاز است')
        with sqlite3.connect(self.path) as db:self._insert(db,name,password,role)

    def login(self,name,password,ip):
        now=time.monotonic();previous=self.failures.get(ip,[]);previous=[t for t in previous if now-t<300]
        if len(previous)>=8:raise HTTPException(429,'تلاش‌های ناموفق زیاد است؛ پنج دقیقه بعد تلاش کنید')
        with sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True) as db:r=db.execute('SELECT salt,digest,role FROM users WHERE name=?',(name,)).fetchone()
        salt=r[0] if r else 'not-a-user'
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),310000).hex()
        if not r or not hmac.compare_digest(digest,r[1]):self.failures[ip]=previous+[now];raise HTTPException(401,'نام کاربری یا رمز نادرست است')
        token=secrets.token_urlsafe(32);self.sessions[token]={'name':name,'role':r[2],'expires':now+8*3600};self.failures.pop(ip,None)
        return token,self.sessions[token]

    def require(self,request:Request,permission='read'):
        if self.demo:user={'name':'کاربر محیط آموزشی','role':'admin'}
        else:
            user=self.sessions.get(request.cookies.get(self.cookie_name,''))
            if not user or user['expires']<time.monotonic():raise HTTPException(401,'ابتدا وارد شوید')
        if permission not in ROLES[user['role']]:raise HTTPException(403,'مجوز این عملیات را ندارید')
        return user
