#!/usr/bin/env python3
"""اجرا در پوشه پروژه: python redownload_fa.py"""
import os, time, http.client
from urllib.request import urlopen, Request

STATIC = 'static'
WF_DIR = os.path.join(STATIC, 'icons', 'fontawesome', 'webfonts')
CSS    = os.path.join(STATIC, 'icons', 'fontawesome', 'css', 'all.min.css')

def download(url, dest, retries=8):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Connection': 'close',
    }
    for attempt in range(1, retries+1):
        try:
            req = Request(url, headers=headers)
            resp = urlopen(req, timeout=90)
            total = int(resp.headers.get('Content-Length', 0))
            data, got = [], 0
            while True:
                try:
                    buf = resp.read(32768)
                except http.client.IncompleteRead as e:
                    buf = e.partial
                if not buf:
                    break
                data.append(buf)
                got += len(buf)
            content = b''.join(data)
            if total and len(content) != total:
                raise IOError(f'{len(content)}/{total} bytes')
            with open(dest, 'wb') as f:
                f.write(content)
            print(f'  ✓ {os.path.basename(dest)} ({len(content)} bytes - دقیق)')
            return True
        except Exception as e:
            print(f'  ! تلاش {attempt}/{retries}: {e}')
            if os.path.exists(dest):
                os.remove(dest)
            time.sleep(2*attempt)
    return False


# حذف فایل‌های فعلی webfont
print('حذف فایل‌های قدیمی...')
for fname in os.listdir(WF_DIR) if os.path.isdir(WF_DIR) else []:
    os.remove(os.path.join(WF_DIR, fname))
    print(f'  حذف: {fname}')

os.makedirs(WF_DIR, exist_ok=True)

ver = '6.5.2'
files = ['fa-brands-400.woff2', 'fa-regular-400.woff2', 'fa-solid-900.woff2', 'fa-v4compatibility.woff2']
bases = [
    f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/webfonts',
    f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/webfonts',
]

print('\nدانلود مجدد webfonts (با بررسی دقیق سایز)...')
all_ok = True
for fname in files:
    dest = os.path.join(WF_DIR, fname)
    ok = False
    for base in bases:
        if download(f'{base}/{fname}', dest):
            ok = True
            break
    if not ok:
        all_ok = False
        print(f'  ✗ {fname} ناموفق')

# همچنین CSS رو دوباره دانلود کن (مطمئن باش خرابی نداره)
print('\nدانلود مجدد CSS...')
css_ok = False
for url in [
    f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/css/all.min.css',
    f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/css/all.min.css',
]:
    if download(url, CSS):
        css_ok = True
        break

if css_ok:
    c = open(CSS, encoding='utf-8', errors='ignore').read()
    c = c.replace('../webfonts/', '/static/icons/fontawesome/webfonts/')
    c = c.replace('./webfonts/',  '/static/icons/fontawesome/webfonts/')
    open(CSS, 'w', encoding='utf-8').write(c)
    print('  ✓ مسیر CSS اصلاح شد')

print('\n' + ('🎉 همه چیز با سایز دقیق دانلود شد! Ctrl+Shift+R بزنید.' if (all_ok and css_ok) else '⚠️ دوباره اجرا کنید'))