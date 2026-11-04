"""Loopback-only entry, gated by a private installed-desktop session.
Never put a reverse proxy in front of this process. Proxy headers must stay disabled.
"""
import hashlib
import os
import secrets
import time
import jdatetime
from ipaddress import ip_address
from urllib.parse import parse_qs
from fastapi import Request
from fastapi.responses import JSONResponse,RedirectResponse

class LocalOnly:
    def __init__(self,application,desktop_token=None):
        self.application=application;self.bootstrap=desktop_token
        self.session=None;self.expires=0
        self.instance=hashlib.sha256((desktop_token or '').encode()).hexdigest()
    async def __call__(self,scope,receive,send):
        if scope['type']=='http':
            host=(scope.get('client') or ('',0))[0]
            try:local=ip_address(host).is_loopback
            except ValueError:local=False
            if not local:
                response=JSONResponse({'detail':'ورود و ثبت فقط روی سیستم مرکزی مجاز است؛ برای گزارش از داشبورد استفاده کنید'},status_code=403)
            elif scope['path']=='/api/health' and scope['method']=='GET':
                response=JSONResponse({'ok':True,'version':'0.8.0','mode':'installed_central','demo':False,'today':jdatetime.date.today().strftime('%Y/%m/%d'),'instance':self.instance})
            elif scope['path']=='/desktop/start' and scope['method']=='GET':
                key=parse_qs(scope.get('query_string',b'').decode()).get('key',[''])[0]
                if self.bootstrap and secrets.compare_digest(key,self.bootstrap):
                    self.bootstrap=None;self.session=secrets.token_urlsafe(48);self.expires=time.monotonic()+8*3600
                    response=RedirectResponse('/',status_code=303)
                    response.set_cookie('maz_desktop',self.session,httponly=True,samesite='strict',max_age=8*3600)
                    response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer'
                else:response=JSONResponse({'detail':'نشست برنامه نصب‌شده معتبر نیست؛ برنامه را دوباره باز کنید'},status_code=403)
            else:
                cookie=Request(scope).cookies.get('maz_desktop','')
                if self.session and time.monotonic()<self.expires and secrets.compare_digest(cookie,self.session):
                    await self.application(scope,receive,send);return
                response=JSONResponse({'detail':'ثبت و ورود فقط از پنجره نرم‌افزار نصب‌شده مجاز است، نه مرورگر؛ start را اجرا کنید'},status_code=403)
            await response(scope,receive,send);return
        await self.application(scope,receive,send)
