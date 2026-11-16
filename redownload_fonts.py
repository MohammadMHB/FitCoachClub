#!/usr/bin/env python3
"""اجرا در پوشه پروژه: python redownload_fonts.py"""
import os, time, http.client
from urllib.request import urlopen, Request

STATIC = 'static'

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
            data = []
            got = 0
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
            print(f'  ✓ {os.path.basename(dest)} ({len(content)} bytes, exact match)')
            return True
        except Exception as e:
            print(f'  ! تلاش {attempt}/{retries}: {e}')
            if os.path.exists(dest):
                os.remove(dest)
            time.sleep(2*attempt)
    return False


# حذف فایل‌های خراب فعلی
for fname in ['Vazirmatn-Regular.woff2', 'Vazirmatn-Bold.woff2']:
    p = os.path.join(STATIC, 'fonts', fname)
    if os.path.exists(p):
        os.remove(p)
        print(f'حذف شد: {fname}')

print('\nدانلود مجدد (با بررسی دقیق سایز)...')
ver = 'v33.003'
files = {
    'Vazirmatn-Regular.woff2': [
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/webfonts/Vazirmatn-Regular.woff2',
        f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{ver}/fonts/webfonts/Vazirmatn-Regular.woff2',
    ],
    'Vazirmatn-Bold.woff2': [
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/webfonts/Vazirmatn-Bold.woff2',
        f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{ver}/fonts/webfonts/Vazirmatn-Bold.woff2',
    ],
}

ok = True
for fname, urls in files.items():
    dest = os.path.join(STATIC, 'fonts', fname)
    success = False
    for url in urls:
        if download(url, dest):
            success = True
            break
    if not success:
        ok = False
        print(f'  ✗ {fname} ناموفق')

print('\n' + ('🎉 فونت‌ها با سایز دقیق دانلود شدند! Ctrl+Shift+R بزنید.' if ok else '⚠️ دوباره اجرا کنید: python redownload_fonts.py'))